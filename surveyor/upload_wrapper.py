#!/usr/bin/env python3
import yaml
import sys
import os
import subprocess
from pathlib import Path
import argparse
import logging


def setup_logger(verbose):
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("upload_wrapper")


def extract_paths_from_jobs(job_data):
    """Extract relevant paths and site from jobs file"""
    paths = {}

    # Get db_path from Device Config Backup job
    config_backup_job = next((j for j in job_data['jobs'] if j['name'] == "Device Config Backup"), None)
    if config_backup_job:
        try:
            db_index = config_backup_job['args'].index('--db')
            paths['db_path'] = config_backup_job['args'][db_index + 1]
        except (ValueError, IndexError):
            return None

    # Get site and base_path from Device Fingerprint job's topology file
    fingerprint_job = next((j for j in job_data['jobs'] if j['name'] == "Device Fingerprint"), None)
    if fingerprint_job:
        try:
            topology_index = fingerprint_job['args'].index('--topology')
            topology_path = Path(fingerprint_job['args'][topology_index + 1])
            paths['site'] = topology_path.stem
            paths['base_path'] = str(topology_path.parent)
        except (ValueError, IndexError):
            return None

    return paths if all([paths.get('db_path'), paths.get('base_path'), paths.get('site')]) else None


def run_upload_script(script_name, paths, verbose):
    """Run an individual upload script with the provided parameters"""
    python_executable = sys.executable
    script_module = f"surveyor.{script_name}"
    logger = logging.getLogger("upload_wrapper")

    # For scripts that don't accept --site, we need to point directly to the site directory
    # For scripts that do accept --site, we point to the parent directory and pass --site
    if script_name in ["upload_interfaces", "upload_inventory"]:
        # These scripts accept --site parameter
        sites_dir = str(Path(paths['base_path']).parent)
        site_name = Path(paths['base_path']).name
        cmd = [
            python_executable, "-m", script_module,
            "--db", paths['db_path'],
            "--base-path", sites_dir,  # Point to parent 'sites' directory
            "--site", site_name  # Specify which site to process
        ]
    else:
        # upload_arp, upload_macs, and upload_snmp don't accept --site
        cmd = [
            python_executable, "-m", script_module,
            "--db", paths['db_path'],
            "--base-path", paths['base_path']  # Point directly to site directory
        ]

    if verbose:
        cmd.append("-v")
        logger.debug(f"Running command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            logger.debug(result.stdout)
        if result.stderr:
            logger.debug(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {script_name}: {str(e)}")
        if e.stdout:
            logger.error(f"stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"stderr: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run all database upload scripts')
    parser.add_argument('--jobs-file', required=True, help='Path to the jobs YAML file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    logger = setup_logger(args.verbose)

    # Load jobs file
    try:
        with open(args.jobs_file, 'r') as f:
            jobs_data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading jobs file: {str(e)}")
        sys.exit(1)

    # Extract required paths from jobs file
    paths = extract_paths_from_jobs(jobs_data)
    if not paths:
        logger.error("Could not find required paths in jobs file")
        sys.exit(1)

    logger.info(f"Using database path: {paths['db_path']}")
    logger.info(f"Using base path: {paths['base_path']}")

    # List of upload scripts to run
    upload_scripts = [
        "upload_arp",
        "upload_interfaces",
        "upload_inventory",
        "upload_macs",
        "upload_snmp"
    ]

    # Run each upload script
    success_count = 0
    for script in upload_scripts:
        logger.info(f"Running {script}...")
        logger.info(f"args: {args}")
        if run_upload_script(script, paths, args.verbose):
            success_count += 1
            logger.info(f"Successfully completed {script}")
        else:
            logger.error(f"Failed to run {script}")

    logger.info(f"Completed {success_count}/{len(upload_scripts)} upload scripts")


if __name__ == "__main__":
    main()