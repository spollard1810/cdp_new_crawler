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
        self.logger.debug(f"Initialized CommandParser with template directory: {template_dir}")

    def _get_template_path(self, command: str, device_type: str = 'cisco_ios') -> str:
        """Get the appropriate template path based on command and device type"""
        # Map device types to their template suffixes
        template_suffixes = {
            'cisco_nxos': '_nxos',
            'cisco_xe': '',  # Use IOS templates for XE
            'cisco_ios': ''
        }
        
        suffix = template_suffixes.get(device_type, '')
        template_name = f"{command}{suffix}.template"
        template_path = os.path.join(self.template_dir, template_name)
        
        # If template doesn't exist for specific device type, fall back to IOS template
        if not os.path.exists(template_path) and suffix:
            self.logger.warning(f"Template {template_name} not found, falling back to IOS template")
            template_path = os.path.join(self.template_dir, f"{command}.template")
            
        return template_path

    def _parse_with_template(self, output: str, command: str, device_type: str = 'cisco_ios') -> List[Dict]:
        """Parse command output using TextFSM template"""
        try:
            template_path = self._get_template_path(command, device_type)
            self.logger.debug(f"Using template: {template_path}")
            
            with open(template_path) as template_file:
                template = TextFSM(template_file)
                parsed = template.ParseText(output)
                
            # Convert to list of dictionaries
            headers = template.header
            result = []
            for row in parsed:
                result.append(dict(zip(headers, row)))
                
            return result
        except Exception as e:
            self.logger.error(f"Error parsing {command} output: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def parse_show_version(self, show_version_output: str, device_type: str = 'cisco_ios') -> Dict:
        """Parse 'show version' command output"""
        try:
            self.logger.info("Starting to parse show version output")
            self.logger.debug(f"Raw show version output: {show_version_output}")
            
            parsed = self._parse_with_template(show_version_output, 'show_version', device_type)
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
            
            # The format we're seeing is: ['C8300-2N2S-4T2X', '*FLM273210MF*']
            if len(result) >= 2:
                hardware = result[0].strip('*')
                serial = result[1].strip('*')
            
            # Create the parsed info dictionary with the values
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

    def parse_cdp_neighbors(self, cdp_output: str, device_type: str = 'cisco_ios') -> List[Dict]:
        """Parse 'show cdp neighbors detail' command output"""
        try:
            self.logger.info("Starting to parse CDP neighbors output")
            self.logger.debug(f"Raw CDP output: {cdp_output}")
            
            parsed = self._parse_with_template(cdp_output, 'show_cdp_neighbors_detail', device_type)
            self.logger.info(f"Raw parsed output: {parsed}")
            
            if not parsed:
                self.logger.warning("No data was parsed from CDP output")
                return []
            
            self.logger.info(f"Successfully parsed {len(parsed)} CDP neighbors")
            return parsed
        except Exception as e:
            self.logger.error(f"Error parsing CDP neighbors: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    def clean_output(self, output: str) -> str:
        """Clean command output by removing ANSI escape sequences and extra whitespace"""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', output)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip() 