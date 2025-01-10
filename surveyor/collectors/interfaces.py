# collectors/interfaces.py
from typing import Dict
from .base import CommandCollector
from surveyor.normalizers.interfaces import InterfaceNormalizer
from surveyor.tfsm_fire import TextFSMAutoEngine
from surveyor.ssh.pysshpass import ssh_client


class InterfaceCollector(CommandCollector):
    PLATFORM_MAPPINGS = {
        "cisco": {
            "command": "show interfaces",
            "template_hint": "cisco_ios_show_interfaces"
        },
        "nxos": {
            "command": "show interface",
            "template_hint": "cisco_nxos_show_interface"
        },
        "arista": {
            "command": "show interfaces",
            "template_hint": "arista_eos_show_interfaces"
        }
    }

    def __init__(self, device_info: dict, engine: TextFSMAutoEngine, credentials: Dict):
        super().__init__(device_info)
        self.engine = engine
        self.normalizer = InterfaceNormalizer()
        self.credentials = credentials

    def execute_command(self, command: str) -> str:
        client = ssh_client(
            host=self.device_info['ip'],
            user=self.credentials['username'],
            password=self.credentials['password'],
            cmds=command,
            invoke_shell=False,
            prompt=self.device_info['detected_prompt'],
            prompt_count=1,
            timeout=30,
            disable_auto_add_policy=False,
            look_for_keys=False,
            inter_command_time=1
        )
        return client