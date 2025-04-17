from typing import Optional
from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
import logging
import traceback

class DeviceConnection:
    def __init__(self, hostname: str, username: str, password: str, device_type: str):
        self.hostname = hostname
        self.connection_params = {
            'device_type': device_type,
            'host': hostname,
            'username': username,
            'password': password,
            'timeout': 20,  # Connection timeout in seconds
            'session_log': None,
            'fast_cli': False,  # Disable fast_cli for more reliable connections
            'global_delay_factor': 2,  # Increase delay factor for more reliable connections
        }
        
        # Add platform-specific parameters
        if device_type == 'cisco_nxos':
            self.connection_params.update({
                'global_delay_factor': 3,  # NX-OS often needs more time
                'read_timeout_override': 30,  # Increase read timeout for NX-OS
                'expect_string': r'#\s*$',  # NX-OS prompt pattern
                'auto_connect': False,  # Don't auto connect, we'll do it manually
            })
        elif device_type == 'cisco_xe':
            self.connection_params.update({
                'global_delay_factor': 2,
                'read_timeout_override': 25,
                'expect_string': r'#\s*$',  # IOS-XE prompt pattern
            })
        else:  # Default to IOS parameters
            self.connection_params.update({
                'global_delay_factor': 2,
                'read_timeout_override': 20,
            })
            
        self.connection: Optional[ConnectHandler] = None
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized DeviceConnection for {hostname}")

    def connect(self) -> None:
        """Establish SSH connection to the device"""
        self.logger.info(f"Attempting to connect to {self.hostname}")
        try:
            self.connection = ConnectHandler(**self.connection_params)
            
            # Handle platform-specific connection setup
            if self.connection_params['device_type'] == 'cisco_nxos':
                self.logger.debug("Handling NX-OS specific connection setup")
                # Send a newline to get the prompt
                self.connection.write_channel("\n")
                # Wait for the prompt
                self.connection.find_prompt()
                # Disable paging
                self.connection.send_command("terminal length 0", expect_string=r'#\s*$')
            elif self.connection_params['device_type'] == 'cisco_xe':
                self.logger.debug("Handling IOS-XE specific connection setup")
                # Disable paging
                self.connection.send_command("terminal length 0", expect_string=r'#\s*$')
            else:  # Default to IOS setup
                self.logger.debug("Handling IOS specific connection setup")
                # Disable paging
                self.connection.send_command("terminal length 0")
            
            self.logger.info(f"Successfully connected to {self.hostname}")
        except NetMikoTimeoutException:
            self.logger.error(f"Timeout connecting to {self.hostname}")
            raise ConnectionError(f"Timeout connecting to {self.hostname}")
        except NetMikoAuthenticationException:
            self.logger.error(f"Authentication failed for {self.hostname}")
            raise ConnectionError(f"Authentication failed for {self.hostname}")
        except Exception as e:
            self.logger.error(f"Error connecting to {self.hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise ConnectionError(f"Error connecting to {self.hostname}: {str(e)}")

    def disconnect(self) -> None:
        """Close the SSH connection"""
        if self.connection:
            self.logger.debug(f"Disconnecting from {self.hostname}")
            self.connection.disconnect()
            self.connection = None
            self.logger.info(f"Disconnected from {self.hostname}")

    def send_command(self, command: str) -> str:
        """Send a command to the device and return the output"""
        if not self.connection:
            self.logger.error(f"Not connected to device {self.hostname}")
            raise RuntimeError("Not connected to device")
            
        self.logger.debug(f"Sending command to {self.hostname}: {command}")
        try:
            # Handle platform-specific command sending
            if self.connection_params['device_type'] == 'cisco_nxos':
                output = self.connection.send_command(
                    command,
                    expect_string=r'#\s*$',
                    read_timeout=30
                )
            elif self.connection_params['device_type'] == 'cisco_xe':
                output = self.connection.send_command(
                    command,
                    expect_string=r'#\s*$',
                    read_timeout=25
                )
            else:  # Default to IOS command sending
                output = self.connection.send_command(command)
                
            if "Invalid input" in output or "Incomplete command" in output:
                self.logger.error(f"Invalid command for {self.hostname}: {command}")
                raise ValueError(f"Invalid command: {command}")
            self.logger.debug(f"Command output length: {len(output)} characters")
            return output
        except Exception as e:
            self.logger.error(f"Error sending command '{command}' to {self.hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect() 