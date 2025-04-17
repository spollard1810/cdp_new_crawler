from typing import Optional
from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException

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

    def connect(self) -> None:
        """Establish SSH connection to the device"""
        try:
            self.connection = ConnectHandler(**self.connection_params)
        except NetMikoTimeoutException:
            raise ConnectionError(f"Timeout connecting to {self.hostname}")
        except NetMikoAuthenticationException:
            raise ConnectionError(f"Authentication failed for {self.hostname}")
        except Exception as e:
            raise ConnectionError(f"Error connecting to {self.hostname}: {str(e)}")

    def disconnect(self) -> None:
        """Close the SSH connection"""
        if self.connection:
            self.connection.disconnect()
            self.connection = None

    def send_command(self, command: str) -> str:
        """Send a command to the device and return the output"""
        if not self.connection:
            raise RuntimeError("Not connected to device")
            
        try:
            output = self.connection.send_command(command)
            if "Invalid input" in output or "Incomplete command" in output:
                raise ValueError(f"Invalid command: {command}")
            return output
        except Exception as e:
            raise RuntimeError(f"Error sending command '{command}': {str(e)}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect() 