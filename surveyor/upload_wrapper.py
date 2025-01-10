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
    """Extract relevant paths from jobs file"""
    paths = {}

    # Get db_path from Device Config Backup job
    config_backup_job = next((j for j in job_data['jobs'] if j['name'] == "Device Config Backup"), None)
    if config_backup_job:
        try:
            db_index = config_backup_job['args'].index('--db')
            paths['db_path'] = config_backup_job['args'][db_index + 1]
        except (ValueError, IndexError):
            return None

    # Get base_path from any job with json output
    for job in job_data['jobs']:
        for arg in job['args']:
            if '.json' in str(arg):
                paths['base_path'] = str(Path(arg).parent)
                return paths

    return None if len(paths) != 2 else paths


def run_upload_script(script_name, db_path, base_path, verbose):
    """Run an individual upload script with the provided parameters"""
    python_executable = sys.executable
    script_module = f"surveyor.{script_name}"

    cmd = [
        python_executable, "-m", script_module,
        "--db", db_path,
        "--base-path", base_path
    ]

    if verbose:
        cmd.append("-v")

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {str(e)}")
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
        logger.error("Could not find required database and base paths in jobs file")
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
        if run_upload_script(script, paths['db_path'], paths['base_path'], args.verbose):
            success_count += 1
            logger.info(f"Successfully completed {script}")
        else:
            logger.error(f"Failed to run {script}")

    logger.info(f"Completed {success_count}/{len(upload_scripts)} upload scripts")


if __name__ == "__main__":
    main()