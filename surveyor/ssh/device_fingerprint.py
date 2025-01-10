import socket
import traceback
import json
from pathlib import Path
from time import sleep
import re
from typing import Dict, Optional, Tuple, Union
import sys
import logging
from importlib import resources

from surveyor.normalizer import DeviceDataNormalizer
from surveyor.ssh.pysshpass import ssh_client
from surveyor.tfsm_fire import TextFSMAutoEngine as TextFSMParser


class DeviceFingerprinter:
    INITIAL_PROMPT = "#|>|\\$"
    VENDOR_TEMPLATES = {
        ('cisco', 'IOS'): 'cisco_ios_show_version',
        ('cisco', 'Nexus'): 'cisco_nxos_show_version',
        ('arista', 'EOS'): 'arista_eos_show_version',
        ('JUNOS',): 'juniper_junos_show_version'
    }
    PAGING_COMMANDS = {
        'cisco': ['terminal length 0', 'terminal width 511'],
        'asa': ['terminal pager 0'],
        'arista': ['terminal length 0', 'terminal width 32767'],
        'juniper': ['set cli screen-length 0', 'set cli screen-width 511'],
        'huawei': ['screen-length 0 temporary'],
        'hp': ['screen-length disable'],
        'paloalto': ['set cli pager off'],
        'fortinet': ['config system console', 'set output standard', 'end'],
        'dell': ['terminal length 0']
    }

    ERROR_PATTERNS = [
        r'% ?error',
        r'% ?invalid',
        r'% ?bad',
        r'% ?unknown',
        r'% ?incomplete',
        r'% ?unrecognized'
    ]

    def __init__(self, verbose: bool = False):
        try:
            with resources.path('surveyor', 'templates.db') as db_path:
                self.parser = TextFSMParser(str(db_path))
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Failed to initialize TextFSMParser: {str(e)}")

        self.prompt = None
        self.client = None
        self.channel = None
        self.verbose = verbose

        log_level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def log_exception(self, e: Exception, message: str):
        """Helper method to log exceptions with tracebacks"""
        self.logger.error(f"{message}: {str(e)}")
        self.logger.error(f"Traceback:\n{''.join(traceback.format_tb(e.__traceback__))}")

    def read_channel_output(self, channel, timeout: int = 1) -> str:
        """Helper method to read channel output with error handling"""
        output = ""
        try:
            sleep(timeout)
            while channel.recv_ready():
                try:
                    chunk = channel.recv(4096).decode('utf-8')
                    output += chunk
                except UnicodeDecodeError as e:
                    self.log_exception(e, "Error decoding channel output")
                    break
        except Exception as e:
            self.log_exception(e, "Error reading channel output")
            raise
        return output

    def phase1_detect_prompt(self, channel) -> Optional[str]:
        """Phase 1: Initial Prompt Detection with enhanced error handling"""
        self.logger.info("Phase 1: Detecting prompt...")

        try:
            channel.send("\n")
            output = self.read_channel_output(channel)

            if not output:
                self.logger.error("No output received during prompt detection")
                return None

            lines = [l.strip() for l in output.split('\n') if l.strip()]
            for line in reversed(lines):
                try:
                    if re.search(f".*({self.INITIAL_PROMPT})\\s*$", line):
                        detected_prompt = line.strip()
                        self.logger.info(f"Detected prompt: {detected_prompt}")
                        return detected_prompt
                except re.error as e:
                    self.log_exception(e, "Regex error in prompt detection")
                    continue

            self.logger.error("No prompt detected in output")
            return None

        except Exception as e:
            self.log_exception(e, "Error in prompt detection phase")
            raise

    def phase2_disable_paging(self, channel, prompt: str) -> Tuple[Optional[str], list]:
        """Phase 2: Paging Disable Loop with enhanced error handling"""
        self.logger.info("Phase 2: Disabling paging...")

        successful_vendors = {}

        try:
            for vendor, commands in self.PAGING_COMMANDS.items():
                try:
                    self.logger.info(f"Trying {vendor} paging commands")
                    vendor_success = True
                    successful_commands = []

                    for cmd in commands:
                        try:
                            channel.send(cmd + "\n")
                            output = self.read_channel_output(channel)

                            if not any(re.search(pattern, output, re.IGNORECASE)
                                       for pattern in self.ERROR_PATTERNS):
                                successful_commands.append((vendor, cmd))
                            else:
                                vendor_success = False
                                break

                        except Exception as e:
                            self.log_exception(e, f"Error executing {vendor} command {cmd}")
                            vendor_success = False
                            break

                    if vendor_success and successful_commands:
                        successful_vendors[vendor] = successful_commands

                except Exception as e:
                    self.log_exception(e, f"Error processing vendor {vendor}")
                    continue

            if successful_vendors:
                prompt_lower = prompt.lower()
                for vendor in successful_vendors.keys():
                    if vendor.lower() in prompt_lower:
                        return vendor, successful_vendors[vendor]

                vendor_priority = ['arista', 'juniper', 'huawei', 'paloalto', 'fortinet', 'asa', 'cisco']
                for preferred_vendor in vendor_priority:
                    if preferred_vendor in successful_vendors:
                        return preferred_vendor, successful_vendors[preferred_vendor]

            self.logger.warning("No vendor paging commands were successful")
            return None, []

        except Exception as e:
            self.log_exception(e, "Error in paging disable phase")
            raise

    def phase3_get_version(self, channel, prompt: str) -> Dict:
        self.logger.info("Phase 3: Getting version information...")

        try:
            output = self._execute_version_command(channel)
            self.logger.info(f"Raw command output length: {len(output) if isinstance(output, str) else 'error'}")

            if isinstance(output, dict) and 'error' in output:
                self.logger.error(f"Command execution failed: {output['error']}")
                return output

            template_hint = self._detect_template(output, self.VENDOR_TEMPLATES)
            self.logger.info(f"Template detection result: {template_hint}")

            try:
                parsed_result = self._parse_version_output(output, template_hint)
                self.logger.info(
                    f"Parse result keys: {parsed_result.keys() if isinstance(parsed_result, dict) else 'error'}")

                if isinstance(parsed_result, dict) and 'error' in parsed_result:
                    self.logger.error(f"Parsing failed: {parsed_result['error']}")
                    return parsed_result

                normalized = self._normalize_version_data(parsed_result)
                self.logger.info(
                    f"Normalization result keys: {normalized.keys() if isinstance(normalized, dict) else 'error'}")
                print(f"Normalized: {normalized}")

                return normalized

            except Exception as e:
                self.log_exception(e, "Error in parsing/normalization")
                raise

        except Exception as e:
            self.log_exception(e, "Error in version detection")
            raise
    def _execute_version_command(self, channel) -> Union[str, Dict]:
        """Execute show version command with error handling"""
        try:
            if self.verbose:
                self.logger.debug("Sending 'show version' command")
            channel.send("show version\n")

            output = self.read_channel_output(channel, timeout=2)
            if not output:
                self.logger.error("No output received from version command")
                return {"error": "Failed to get version information"}
            return output
        except Exception as e:
            self.log_exception(e, "Error executing version command")
            return {"error": str(e)}

    def _detect_template(self, output: str, vendor_templates: Dict) -> Optional[str]:
        """Detect appropriate template based on output with error handling"""
        try:
            if 'show version' not in output:
                self.logger.error("Output does not contain version information")
                return None

            output_lower = output.lower()
            for keywords, template in vendor_templates.items():
                if all(keyword.lower() in output_lower for keyword in keywords):
                    self.logger.info(f"Detected device type, using template: {template}")
                    return template

            if 'eos-' in output_lower or 'arista' in output_lower:
                return 'arista_eos_show_version'
            elif 'nexus' in output_lower:
                return 'cisco_nxos_show_version'
            elif 'cisco ios' in output_lower:
                return 'cisco_ios_show_version'

            self.logger.warning("No matching template found in vendor detection")
            return None
        except Exception as e:
            self.log_exception(e, "Error detecting template")
            return None

    def _parse_version_output(self, output: str, template_hint: Optional[str]) -> Dict:
        """Parse version output using TextFSM with error handling"""
        try:
            best_template, parsed_data, score = self.parser.find_best_template(output, filter_string=template_hint)
            if self.verbose:
                self.logger.debug(
                    f"TextFSM parse results - Template: {best_template}, Score: {score}, Data: {parsed_data}")

            if not best_template or not parsed_data:
                self.logger.error("Failed to find matching template or parse version information")
                return {"error": "Failed to parse version information"}

            return {
                "success": True,
                "parsed_data": parsed_data,
                "template": best_template,
                "score": score
            }
        except Exception as e:
            self.log_exception(e, "Error parsing version output")
            return {"error": str(e)}

    def _normalize_version_data(self, parsed_result: Dict) -> Dict:
        """Normalize parsed version data with error handling"""
        try:
            normalizer = DeviceDataNormalizer()
            normalized_data = normalizer.normalize(
                parsed_result["parsed_data"],
                parsed_result["template"]
            )
            return {
                "success": True,
                "device_info": normalized_data,
                "template": parsed_result["template"],
                "score": parsed_result["score"]
            }
        except Exception as e:
            self.log_exception(e, "Error normalizing version data")
            return {"error": f"Normalization failed: {str(e)}"}

    def test_ssh_port(self, host: str, timeout: int = 5) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, 22))
            sock.close()
            return result == 0
        except Exception as e:
            return False
    # def fingerprint_device(self, host: str, username: str, password: str, timeout: int = 30) -> Dict:
    #     """Main fingerprinting process with comprehensive error handling"""
    #     self.logger.info(f"Starting device fingerprinting for host: {host}")
    #
    #     if not self.test_ssh_port(host, timeout=5):
    #         return {
    #             "error": f"Port 22 not accessible on {host}"
    #         }
    #     channel = None
    #     client = None
    #     if "usrv-p1map-lan" in self.INITIAL_PROMPT:
    #         return {f"error": f"poison apple device {self.INITIAL_PROMPT}"}
    #     try:
    #         try:
    #             client = ssh_client(
    #                 host=host,
    #                 user=username,
    #                 password=password,
    #                 cmds="",
    #                 invoke_shell=True,
    #                 prompt=self.INITIAL_PROMPT,
    #                 prompt_count=1,
    #                 timeout=timeout,
    #                 disable_auto_add_policy=False,
    #                 look_for_keys=False,
    #                 inter_command_time=1,
    #                 connect_only=True
    #             )
    #         except Exception as e:
    #             self.log_exception(e, "SSH connection failed")
    #             return {"error": f"SSH connection failed: {str(e)}"}
    #
    #         if not client:
    #             return {"error": "Failed to establish SSH connection"}
    #
    #         try:
    #             channel = client.invoke_shell()
    #             sleep(2)  # Wait for banner
    #         except Exception as e:
    #             self.log_exception(e, "Failed to invoke shell")
    #             return {"error": f"Shell invocation failed: {str(e)}"}
    #
    #         try:
    #             prompt = self.phase1_detect_prompt(channel)
    #             if not prompt:
    #                 return {"error": "Failed to detect prompt"}
    #
    #             vendor, paging_commands = self.phase2_disable_paging(channel, prompt)
    #             if not vendor:
    #                 self.logger.warning("Could not identify vendor through paging commands")
    #
    #             version_result = self.phase3_get_version(channel, prompt)
    #             if "error" in version_result:
    #                 return {"error": version_result["error"]}
    #
    #             if "device_info" not in version_result:
    #                 return {"error": "Invalid version result structure"}
    #
    #             version_result["device_info"].update({
    #                 "detected_vendor": vendor,
    #                 "paging_commands": paging_commands,
    #                 "detected_prompt": prompt
    #             })
    #
    #             return version_result
    #
    #         except Exception as e:
    #             self.log_exception(e, "Error during device interaction")
    #             return {"error": f"Device interaction failed: {str(e)}"}
    #
    #     except Exception as e:
    #         self.log_exception(e, "Unhandled error in fingerprinting process")
    #         return {"error": f"Fingerprinting failed: {str(e)}"}
    #
    #     finally:
    #         try:
    #             if channel:
    #                 channel.close()
    #             if client:
    #                 client.close()
    #         except Exception as e:
    #             self.log_exception(e, "Error closing SSH connections")


    def fingerprint_device(self, host: str, username: str, password: str, timeout: int = 30) -> Dict:
        self.logger.info(f"Starting device fingerprinting for host: {host}")

        if not self.test_ssh_port(host, timeout=5):
            return {"error": f"Port 22 not accessible on {host}"}

        channel = None
        client = None

        try:
            client = ssh_client(
                host=host,
                user=username,
                password=password,
                cmds="",
                invoke_shell=True,
                prompt=self.INITIAL_PROMPT,
                prompt_count=1,
                timeout=timeout,
                disable_auto_add_policy=False,
                look_for_keys=False,
                inter_command_time=1,
                connect_only=True
            )

            if not client:
                return {"error": "Failed to establish SSH connection"}

            channel = client.invoke_shell()
            sleep(2)  # Wait for banner

            if not channel:
                return {"error": "Failed to create interactive shell"}

            prompt = self.phase1_detect_prompt(channel)
            if not prompt:
                return {"error": "Failed to detect prompt"}

            # Early termination for blacklisted prompts
            if any(banned in prompt for banned in ["usrv-p1map-lan"]):
                return {"error": f"Device {prompt} is blacklisted"}

            # Attempt paging and proceed with version only if successful
            vendor, paging_commands = self.phase2_disable_paging(channel, prompt)
            if not vendor:
                return {"error": "Failed to disable paging"}

            version_result = self.phase3_get_version(channel, prompt)
            if "error" in version_result:
                return version_result

            if "device_info" not in version_result:
                return {"error": "Invalid version result structure"}

            version_result["device_info"].update({
                "detected_vendor": vendor,
                "paging_commands": paging_commands,
                "detected_prompt": prompt
            })

            return version_result

        except Exception as e:
            self.log_exception(e, "Unhandled error in fingerprinting process")
            return {"error": f"Fingerprinting failed: {str(e)}"}
        finally:
            try:
                if channel:
                    channel.close()
                if client:
                    client.close()
            except Exception as e:
                self.log_exception(e, "Error closing SSH connections")