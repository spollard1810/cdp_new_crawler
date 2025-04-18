from typing import Dict, List
from connect import DeviceConnection
from parser import CommandParser
import re
import logging
import traceback
from datetime import datetime
import threading

class NetworkDevice:
    def __init__(self, hostname: str, username: str, password: str, device_type: str = 'cisco_ios', 
                 mgmt_ip: str = None, worker_id: str = None):
        self.hostname = self.clean_hostname(hostname)
        self.mgmt_ip = mgmt_ip  # Add management IP as fallback
        self.username = username
        self.password = password
        self.device_type = device_type
        self.connection = None
        self.parser = CommandParser()
        self.worker_id = worker_id or str(threading.get_ident())  # Use thread ID as worker ID if not provided
        self.platform_info = {}  # Store platform-specific information
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized NetworkDevice: {self.hostname} (mgmt_ip: {mgmt_ip})")

    @staticmethod
    def clean_hostname(hostname: str) -> str:
        """Clean hostname by removing parentheses and other special characters"""
        if not hostname:
            return hostname
            
        # Remove parentheses and their contents
        hostname = re.sub(r'\([^)]*\)', '', hostname)
        # Remove any remaining special characters except dots and hyphens
        hostname = re.sub(r'[^a-zA-Z0-9.-]', '', hostname)
        # Remove leading/trailing dots and hyphens
        hostname = hostname.strip('.-')
        return hostname

    def is_phone(self, platform: str) -> bool:
        """Check if the device is an IP Phone based on platform/model"""
        phone_identifiers = [
            'IP PHONE',
            'PHONE',
            'CIPC',  # Cisco IP Communicator
            'CTS',   # Cisco TelePresence
            'CP-'    # Cisco Phone model prefix
        ]
        is_phone = any(identifier in platform.upper() for identifier in phone_identifiers)
        self.logger.debug(f"Checking if {platform} is a phone: {is_phone}")
        return is_phone

    def is_access_point(self, platform: str) -> bool:
        """Check if the device is an access point based on platform/model"""
        ap_identifiers = ['AIR-', 'AP', 'C9130', 'C9120', 'C9115', 'C9105']
        is_ap = any(identifier in platform.upper() for identifier in ap_identifiers)
        self.logger.debug(f"Checking if {platform} is an AP: {is_ap}")
        return is_ap

    def detect_device_type(self, show_version_output: str) -> str:
        """Detect the device type based on show version output"""
        self.logger.info("Detecting device type from show version output")
        
        # Check for NX-OS
        if 'NX-OS' in show_version_output:
            self.logger.info("Detected NX-OS device")
            return 'cisco_nxos'
            
        # Check for IOS-XE
        if 'IOS-XE' in show_version_output or 'XE' in show_version_output:
            self.logger.info("Detected IOS-XE device")
            return 'cisco_xe'
            
        # Default to IOS
        self.logger.info("Detected IOS device")
        return 'cisco_ios'

    def detect_device_type_from_cdp(self, cdp_output: str) -> str:
        """Detect device type from CDP neighbor information"""
        self.logger.info("Detecting device type from CDP output")
        
        # Check for NX-OS in platform or version
        if 'NX-OS' in cdp_output or 'Nexus' in cdp_output:
            self.logger.info("Detected NX-OS device from CDP")
            return 'cisco_nxos'
            
        # Check for IOS-XE in platform or version
        if 'IOS-XE' in cdp_output or 'XE' in cdp_output or 'Catalyst' in cdp_output:
            self.logger.info("Detected IOS-XE device from CDP")
            return 'cisco_xe'
            
        # Check for IOS in platform or version
        if 'IOS' in cdp_output or 'Router' in cdp_output:
            self.logger.info("Detected IOS device from CDP")
            return 'cisco_ios'
            
        self.logger.warning("Could not determine device type from CDP")
        return None

    def connect(self) -> None:
        """Establish connection to the device, trying hostname first then mgmt IP"""
        self.logger.info(f"Attempting to connect to {self.hostname}")
        
        try:
            # Try hostname first
            try:
                self.logger.debug(f"Trying connection with hostname: {self.hostname}")
                
                # First try with the provided device type
                self.connection = DeviceConnection(
                    hostname=self.hostname,
                    username=self.username,
                    password=self.password,
                    device_type=self.device_type
                )
                self.connection.connect()
                self.logger.info(f"Successfully connected to {self.hostname} as {self.device_type}")
                return
                
            except ConnectionError as e:
                self.logger.warning(f"Failed to connect to {self.hostname}: {str(e)}")
                if not self.mgmt_ip:  # If no mgmt IP available, raise the original error
                    raise
                
                # Try mgmt IP as fallback
                self.logger.debug(f"Trying fallback connection with mgmt IP: {self.mgmt_ip}")
                self.connection = DeviceConnection(
                    hostname=self.mgmt_ip,  # Use IP instead of hostname
                    username=self.username,
                    password=self.password,
                    device_type=self.device_type
                )
                self.connection.connect()
                self.logger.info(f"Successfully connected to {self.mgmt_ip}")
        except Exception as e:
            raise

    def disconnect(self) -> None:
        """Close the device connection"""
        if self.connection:
            self.logger.debug(f"Disconnecting from {self.hostname}")
            self.connection.disconnect()
            self.connection = None
            self.logger.info(f"Disconnected from {self.hostname}")

    def send_command(self, command: str) -> str:
        """Send a command to the device and return the output"""
        if not self.connection:
            raise RuntimeError("Not connected to device")
            
        self.logger.debug(f"Sending command to {self.hostname}: {command}")
        try:
            output = self.connection.send_command(command)
            if "Invalid input" in output or "Incomplete command" in output:
                raise ValueError(f"Invalid command: {command}")
            self.logger.debug(f"Command output length: {len(output)} characters")
            return output
        except Exception as e:
            self.logger.error(f"Error sending command '{command}' to {self.hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def get_device_info(self) -> Dict:
        """Get basic device information"""
        self.logger.info(f"Getting device info from {self.hostname}")
        try:
            # First try to get CDP info to detect device type
            try:
                show_cdp = self.send_command('show cdp neighbors detail')
                cdp_info = self.parser.parse_cdp_neighbors(show_cdp, self.device_type)
                if cdp_info:
                    # Use the first neighbor's info to detect device type
                    first_neighbor = cdp_info[0]
                    platform = first_neighbor.get('PLATFORM', '')
                    version = first_neighbor.get('NEIGHBOR_DESCRIPTION', '')
                    cdp_info_str = f"{platform} {version}"
                    detected_type = self.detect_device_type_from_cdp(cdp_info_str)
                    if detected_type and detected_type != self.device_type:
                        self.logger.info(f"Detected {detected_type} from CDP, reconnecting with correct type")
                        self.device_type = detected_type
                        # Reconnect with correct type
                        self.disconnect()
                        self.connect()
            except Exception as e:
                self.logger.warning(f"Failed to get CDP info: {str(e)}")
                # Continue with current device type if CDP fails
            
            # Get version info which includes serial and model
            show_version = self.send_command('show version')
            
            # Parse based on device type using appropriate template
            version_info = self.parser.parse_show_version(show_version, self.device_type)
            
            # Handle different return types from TextFSM parsing
            hardware = ''
            serial = ''
            
            if isinstance(version_info, list):
                if version_info and isinstance(version_info[0], tuple):
                    # Handle list of tuples (e.g., [('HARDWARE', 'C9606R*'), ('SERIAL', 'FXS2509Q208')])
                    for key, value in version_info:
                        if key == 'HARDWARE':
                            hardware = value.strip("'*")  # Remove quotes and asterisks
                        elif key == 'SERIAL':
                            serial = value.strip("'*")
                elif version_info and isinstance(version_info[0], dict):
                    # Handle list of dictionaries (NX-OS style)
                    hardware = version_info[0].get('Hardware', '').strip('*')
                    serial = version_info[0].get('Serial', '')
            elif isinstance(version_info, dict):
                # Handle single dictionary (IOS style)
                hardware = version_info.get('HARDWARE', [''])[0].strip('*') if version_info.get('HARDWARE') else ''
                serial = version_info.get('SERIAL', [''])[0] if version_info.get('SERIAL') else ''
            
            # Clean up any remaining quotes or asterisks
            hardware = hardware.strip("'*")
            serial = serial.strip("'*")
            
            # Format the device info for inventory
            device_info = {
                'hostname': self.hostname,
                'ip': self.mgmt_ip,
                'serial_number': serial,
                'platform': hardware,
                'device_type': self.device_type,
                'last_crawled': datetime.now().isoformat()
            }
            
            # Log the collected device info
            self.logger.info(f"Collected device info for {self.hostname}:")
            for key, value in device_info.items():
                self.logger.info(f"  {key}: {value}")
            
            return device_info
        except Exception as e:
            self.logger.error(f"Error getting device info from {self.hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def get_cdp_neighbors(self) -> List[Dict]:
        """Get CDP neighbor information"""
        self.logger.info(f"Getting CDP neighbors from {self.hostname}")
        try:
            show_cdp = self.send_command('show cdp neighbors detail')
            self.logger.debug(f"Parsing CDP neighbors output for {self.hostname}")
            neighbors = self.parser.parse_cdp_neighbors(show_cdp, self.device_type)
            processed_neighbors = []
            
            for neighbor in neighbors:
                # Clean the hostname from CDP
                neighbor_hostname = self.clean_hostname(neighbor.pop('NEIGHBOR_NAME', ''))
                if not neighbor_hostname:
                    self.logger.warning(f"Skipping neighbor with empty hostname")
                    continue
                    
                platform = neighbor.pop('PLATFORM', '')
                version = neighbor.pop('NEIGHBOR_DESCRIPTION', '')
                
                # Try to detect device type from CDP info
                cdp_info = f"{platform} {version}"
                detected_type = self.detect_device_type_from_cdp(cdp_info)
                
                # Skip phones - don't even add them to processed neighbors
                if self.is_phone(platform):
                    self.logger.debug(f"Skipping phone device: {neighbor_hostname}")
                    continue
                
                # Basic neighbor info
                processed_neighbor = {
                    'hostname': neighbor_hostname,
                    'ip': neighbor.pop('MGMT_ADDRESS', ''),
                    'remote_interface': neighbor.pop('NEIGHBOR_INTERFACE', ''),
                    'local_interface': neighbor.pop('LOCAL_INTERFACE', ''),
                    'platform': platform,
                    'capabilities': neighbor.pop('CAPABILITIES', ''),
                    'version': version,
                    'device_type': detected_type or self.device_type  # Use detected type or fallback to current
                }
                
                # If this is an access point, format it as a device for inventory
                if self.is_access_point(processed_neighbor['platform']):
                    self.logger.debug(f"Processing access point: {neighbor_hostname}")
                    ap_info = {
                        'hostname': processed_neighbor['hostname'],
                        'hardware': [processed_neighbor['platform']],
                        'version': processed_neighbor['version'],
                        'ip': processed_neighbor['ip'],
                        'device_type': processed_neighbor['device_type'],
                        'is_access_point': True,
                        'connected_to': {
                            'device': self.hostname,
                            'interface': processed_neighbor['local_interface']
                        }
                    }
                    # Add AP-specific info to the inventory
                    processed_neighbor['device_info'] = ap_info
                
                processed_neighbors.append(processed_neighbor)
                self.logger.debug(f"Processed neighbor: {neighbor_hostname}")
            
            self.logger.info(f"Found {len(processed_neighbors)} neighbors for {self.hostname}")
            return processed_neighbors
        except Exception as e:
            self.logger.error(f"Error getting CDP neighbors from {self.hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def __str__(self) -> str:
        return f"NetworkDevice(hostname={self.hostname}, ip={self.mgmt_ip}, type={self.device_type})" 