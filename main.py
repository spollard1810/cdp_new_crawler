import argparse
import yaml
import sys
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from rich.prompt import Prompt
from crawler import NetworkCrawler
import time

console = Console()

def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
            # Validate required fields
            required_fields = ['seed_device', 'credentials']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field in config: {field}")
            
            # Validate credentials
            required_credentials = ['username', 'password']
            for field in required_credentials:
                if field not in config['credentials']:
                    raise ValueError(f"Missing required credential field: {field}")
            
            return config
    except Exception as e:
        console.print(f"[red]Error loading config: {str(e)}[/red]")
        sys.exit(1)

def show_status(crawler: NetworkCrawler):
    """Display current crawler status"""
    status = crawler.get_status()
    
    table = Table(title="Crawler Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Devices", str(status['total']))
    table.add_row("Pending", str(status['pending']))
    table.add_row("Processed", str(status['processed']))
    
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="Network Device Crawler")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Create crawler instance with config values
    crawler = NetworkCrawler(
        seed_device=config['seed_device'],
        username=config['credentials']['username'],
        password=config['credentials']['password'],
        device_type=config['credentials'].get('device_type', 'cisco_ios'),
        max_workers=config.get('settings', {}).get('max_depth', 5),
        db_path='network_devices.db',  # Default path
        exclude_hosts=config.get('settings', {}).get('exclude_hosts', []),
        include_only=config.get('settings', {}).get('include_only', [])
    )
    
    # Main menu loop
    while True:
        console.print("\n[bold]Network Device Crawler[/bold]")
        console.print("1. Start Crawl")
        console.print("2. Show Status")
        console.print("3. Export Results")
        console.print("4. Exit")
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4"])
        
        if choice == "1":
            console.print("[yellow]Starting network crawl...[/yellow]")
            crawler.start()
            
        elif choice == "2":
            show_status(crawler)
            
        elif choice == "3":
            output_path = Prompt.ask("Enter output file path", default="network_inventory.csv")
            crawler.export_results(output_path)
            console.print(f"[green]Results exported to {output_path}[/green]")
            
        elif choice == "4":
            console.print("[yellow]Exiting...[/yellow]")
            crawler.stop()
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