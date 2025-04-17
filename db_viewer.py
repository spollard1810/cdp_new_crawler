import sqlite3
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
import sys
from typing import Dict, List

console = Console()

def get_db_path() -> str:
    """Get database path from user or use default"""
    default_path = 'network_devices.db'
    path = Prompt.ask("Enter database path", default=default_path)
    return path

def get_devices(db_path: str) -> List[Dict]:
    """Get all devices from database"""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    hostname,
                    ip,
                    serial_number,
                    device_type,
                    version,
                    platform,
                    rommon,
                    config_register,
                    mac_address,
                    uptime,
                    last_crawled
                FROM devices
                ORDER BY hostname
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        console.print(f"[red]Error reading database: {str(e)}[/red]")
        sys.exit(1)

def display_devices(devices: List[Dict]):
    """Display devices in a formatted table"""
    if not devices:
        console.print("[yellow]No devices found in database[/yellow]")
        return
    
    # Create table
    table = Table(title="Network Devices Inventory")
    
    # Add columns
    table.add_column("Hostname", style="cyan")
    table.add_column("IP", style="green")
    table.add_column("Serial", style="magenta")
    table.add_column("Type", style="blue")
    table.add_column("Version", style="yellow")
    table.add_column("Platform", style="red")
    table.add_column("Last Crawled", style="white")
    
    # Add rows
    for device in devices:
        table.add_row(
            device['hostname'] or '',
            device['ip'] or '',
            device['serial_number'] or '',
            device['device_type'] or '',
            device['version'] or '',
            device['platform'] or '',
            device['last_crawled'] or ''
        )
    
    console.print(table)
    
    # Display summary
    console.print(f"\n[bold]Total Devices:[/bold] {len(devices)}")

def display_device_details(devices: List[Dict]):
    """Display detailed information for a specific device"""
    if not devices:
        console.print("[yellow]No devices found in database[/yellow]")
        return
    
    # Get hostname from user
    hostnames = [device['hostname'] for device in devices if device['hostname']]
    if not hostnames:
        console.print("[yellow]No hostnames found in database[/yellow]")
        return
    
    hostname = Prompt.ask(
        "Enter hostname to view details",
        choices=hostnames,
        default=hostnames[0]
    )
    
    # Find the device
    device = next((d for d in devices if d['hostname'] == hostname), None)
    if not device:
        console.print(f"[red]Device {hostname} not found[/red]")
        return
    
    # Create table for device details
    table = Table(title=f"Device Details: {hostname}")
    
    # Add columns
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    # Add rows
    for key, value in device.items():
        if value:  # Only show non-empty values
            table.add_row(key.replace('_', ' ').title(), str(value))
    
    console.print(table)

def main():
    console.print("[bold]Network Device Database Viewer[/bold]")
    
    # Get database path
    db_path = get_db_path()
    
    # Get devices
    devices = get_devices(db_path)
    
    # Main menu loop
    while True:
        console.print("\n[bold]Options:[/bold]")
        console.print("1. View all devices")
        console.print("2. View device details")
        console.print("3. Exit")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3"])
        
        if choice == "1":
            display_devices(devices)
        elif choice == "2":
            display_device_details(devices)
        elif choice == "3":
            console.print("[yellow]Exiting...[/yellow]")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user. Exiting...[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1) 