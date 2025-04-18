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

    def parse_show_version(self, output: str, device_type: str = 'cisco_ios') -> Dict:
        """Parse show version output using TextFSM template"""
        self.logger.info("Starting to parse show version output")
        try:
            # Get the appropriate template path
            template_path = self._get_template_path('show_version', device_type)
            
            # Parse the output
            with open(template_path) as f:
                template = TextFSM(f)
                result = template.ParseText(output)
                
            self.logger.info(f"Raw parsed output: {result}")
            
            # Initialize empty dictionary for parsed data
            parsed_data = {
                'HARDWARE': '',
                'SERIAL': ''
            }
            
            # Handle different return types from TextFSM
            if isinstance(result, list) and result:
                if isinstance(result[0], dict):
                    # Case 1: List of dictionaries [{'HARDWARE': 'C8300-2N2S-4T2X', 'SERIAL': 'FLM28291QQ'}]
                    self.logger.info(f"Case 1: List of dictionaries - First result: {result[0]}")
                    parsed_data['HARDWARE'] = result[0].get('HARDWARE', '').strip('*')
                    parsed_data['SERIAL'] = result[0].get('SERIAL', '').strip('*')
                    
                elif isinstance(result[0], tuple):
                    # Case 2: List of tuples [('HARDWARE', 'C9606R*'), ('SERIAL', 'FXS2509Q208')]
                    self.logger.info(f"Case 2: List of tuples - Converting to dict")
                    temp_dict = dict(result)
                    parsed_data['HARDWARE'] = temp_dict.get('HARDWARE', '').strip('*')
                    parsed_data['SERIAL'] = temp_dict.get('SERIAL', '').strip('*')
                    
                elif isinstance(result[0], list):
                    # Case 3: List of lists [['C8300-2N2S-4T2X', 'FLM28291QQ']]
                    self.logger.info(f"Case 3: List of lists - First result: {result[0]}")
                    if len(result[0]) >= 2:
                        parsed_data['HARDWARE'] = str(result[0][0]).strip('*')
                        parsed_data['SERIAL'] = str(result[0][1]).strip('*')
                        
            elif isinstance(result, dict):
                # Case 4: Single dictionary {'HARDWARE': 'C8300-2N2S-4T2X', 'SERIAL': 'FLM28291QQ'}
                self.logger.info(f"Case 4: Single dictionary - Result: {result}")
                parsed_data['HARDWARE'] = result.get('HARDWARE', '').strip('*')
                parsed_data['SERIAL'] = result.get('SERIAL', '').strip('*')
                
            else:
                self.logger.warning(f"Unexpected result type: {type(result)}")
                
            # Clean up any remaining quotes or asterisks
            parsed_data['HARDWARE'] = parsed_data['HARDWARE'].strip("'*")
            parsed_data['SERIAL'] = parsed_data['SERIAL'].strip("'*")
            
            self.logger.info(f"Final parsed data: {parsed_data}")
            return parsed_data
            
        except Exception as e:
            self.logger.error(f"Error parsing show version: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {'HARDWARE': '', 'SERIAL': ''}

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