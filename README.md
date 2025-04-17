# Network Device Crawler

A Python-based network device crawler that uses CDP (Cisco Discovery Protocol) to discover and inventory network devices.

## Features

- Multi-threaded device discovery
- Automatic device information collection
- SQLite database for storing device information
- CSV export functionality
- Rich CLI interface
- Configurable through YAML

## Requirements

- Python 3.8+
- Network devices with CDP enabled
- SSH access to network devices

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd network-crawler
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a configuration file (config.yaml):
```yaml
seed_device: "your-starting-device"
username: "your-username"
password: "your-password"
device_type: "cisco_ios"  # or other supported device types
max_workers: 5
db_path: "network_devices.db"
```

## Usage

Run the crawler:
```bash
python main.py --config config.yaml
```

The CLI interface provides the following options:
1. Start Crawl - Begin the network discovery process
2. Show Status - Display current crawl status
3. Export Results - Export device information to CSV
4. Exit - Stop the crawler and exit

## Project Structure

- `main.py` - CLI interface
- `crawler.py` - Main crawler logic
- `devices.py` - Device connection and command handling
- `connect.py` - SSH connection management
- `parser.py` - Command output parsing
- `data.py` - Database management
- `templates/` - TextFSM templates for parsing
- `config.yaml` - Configuration file

## TextFSM Templates

The crawler uses TextFSM templates to parse command outputs. Templates are located in the `templates/` directory:
- `show_version.template` - Parses 'show version' output
- `show_cdp_neighbors_detail.template` - Parses 'show cdp neighbors detail' output

## Database Schema

The SQLite database stores the following information:
- Hostname
- IP Address
- Serial Number
- Device Type
- Version
- Platform
- ROM Monitor
- Config Register
- MAC Address
- Uptime
- Last Crawled Timestamp

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 