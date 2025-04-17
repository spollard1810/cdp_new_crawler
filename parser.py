import os
from typing import Dict, List
from textfsm import TextFSM
import re
import traceback
import logging

class CommandParser:
    def __init__(self, template_dir: str = 'templates'):
        self.template_dir = template_dir
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized CommandParser with template dir: {template_dir}")

    def _parse_with_template(self, command_output: str, template_name: str) -> List[Dict]:
        """Parse command output using a TextFSM template"""
        template_path = os.path.join(self.template_dir, f"{template_name}.template")
        
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        with open(template_path) as template_file:
            fsm = TextFSM(template_file)
            return fsm.ParseText(command_output)

    def parse_show_version(self, show_version_output: str) -> Dict:
        """Parse 'show version' command output"""
        try:
            self.logger.info(f"Starting to parse show version output")
            self.logger.debug(f"Raw show version output: {show_version_output}")
            
            parsed = self._parse_with_template(show_version_output, 'show_version')
            self.logger.info(f"Raw parsed output: {parsed}")
            
            if not parsed:
                self.logger.warning("No data was parsed from show version output")
                return {}
            
            # Get the first (and should be only) result
            result = parsed[0]
            self.logger.info(f"First parsed result: {result}")
            
            # Initialize empty values
            hardware = ''
            serial = ''
            
            # The format we're seeing is: ['Systems,', ''], ['c8300-2n2s-4t2x', 'flm28288282']
            if len(parsed) >= 2:
                # The second element contains both hardware and serial
                hardware = parsed[1][0] if len(parsed[1]) > 0 else ''
                serial = parsed[1][1] if len(parsed[1]) > 1 else ''
            
            parsed_info = {
                'HARDWARE': [hardware] if hardware else [],
                'SERIAL': [serial] if serial else []
            }
            
            self.logger.info(f"Final parsed info: {parsed_info}")
            return parsed_info
        except Exception as e:
            self.logger.error(f"Error parsing show version: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {}

    def parse_cdp_neighbors(self, cdp_output: str) -> List[Dict]:
        """Parse 'show cdp neighbors detail' command output"""
        try:
            parsed = self._parse_with_template(cdp_output, 'show_cdp_neighbors_detail')
            if not parsed:
                return []
            
            neighbors = []
            for entry in parsed:
                neighbor = {
                    'NEIGHBOR_NAME': entry[0],
                    'PLATFORM': entry[1],
                    'CAPABILITIES': entry[2],
                    'NEIGHBOR_INTERFACE': entry[3],
                    'LOCAL_INTERFACE': entry[4],
                    'MGMT_ADDRESS': entry[5],
                    'NEIGHBOR_DESCRIPTION': entry[6]
                }
                neighbors.append(neighbor)
            
            return neighbors
        except Exception as e:
            print(f"Error parsing CDP neighbors: {str(e)}")
            return []

    def clean_output(self, output: str) -> str:
        """Clean command output by removing ANSI escape sequences and extra whitespace"""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', output)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip() 