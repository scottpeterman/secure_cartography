# collectors/base.py
from abc import ABC, abstractmethod
from typing import Dict, Optional

class CommandCollector(ABC):
   def __init__(self, device_info: Dict):
       self.device_info = device_info
       self.vendor = device_info.get('detected_vendor')
       self.paging_commands = device_info.get('paging_commands', [])

   @abstractmethod
   def execute_command(self, command: str) -> str:
       """Execute command on device and return output"""
       pass

   @abstractmethod
   def collect(self) -> Dict:
       """Collect and process command output"""
       pass

   def pre_commands(self) -> Optional[str]:
       """Return any pre-processing commands needed"""
       if self.vendor and self.paging_commands:
           return "\n".join(cmd[1] for cmd in self.paging_commands)
       return None