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
            'session_log': None
        }
        self.connection: Optional[ConnectHandler] = None
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized DeviceConnection for {hostname}")

    def connect(self) -> None:
        """Establish SSH connection to the device"""
        self.logger.info(f"Attempting to connect to {self.hostname}")
        try:
            self.connection = ConnectHandler(**self.connection_params)
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