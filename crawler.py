import threading
import queue
import time
from typing import Dict, List
from devices import NetworkDevice
from data import DeviceDatabase
import logging
import re
import traceback

class NetworkCrawler:
    def __init__(self, seed_device: str, username: str, password: str, 
                 device_type: str = 'cisco_ios', max_workers: int = 5,
                 db_path: str = 'network_devices.db', exclude_hosts: List[str] = None,
                 include_only: List[str] = None):
        self.seed_device = seed_device
        self.username = username
        self.password = password
        self.device_type = device_type
        self.max_workers = max_workers
        self.db = DeviceDatabase(db_path)
        self.worker_queue = queue.Queue()
        self.workers = []
        self.is_running = False
        self.exclude_hosts = exclude_hosts or []
        self.include_only = include_only or []
        
        # Configure logging with more detail
        logging.basicConfig(
            level=logging.DEBUG,  # Changed to DEBUG for more verbose output
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('crawler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized crawler with seed device: {seed_device}")
        self.logger.debug(f"Exclude hosts: {exclude_hosts}")
        self.logger.debug(f"Include only: {include_only}")

    def _should_process_hostname(self, hostname: str) -> bool:
        """Check if a hostname should be processed based on include/exclude rules"""
        self.logger.debug(f"Checking if hostname should be processed: {hostname}")
        
        # If include_only is specified, only process those hosts
        if self.include_only:
            should_include = any(hostname.startswith(prefix) for prefix in self.include_only)
            self.logger.debug(f"Hostname {hostname} {'should' if should_include else 'should not'} be included based on include_only rules")
            return should_include
        
        # Check exclude rules
        for exclude_pattern in self.exclude_hosts:
            if exclude_pattern.startswith('*'):
                # Handle wildcard patterns like *.example.com
                pattern = exclude_pattern.replace('*', '.*')
                if re.match(pattern, hostname):
                    self.logger.debug(f"Hostname {hostname} matches exclude pattern {exclude_pattern}")
                    return False
            elif hostname == exclude_pattern:
                self.logger.debug(f"Hostname {hostname} matches exact exclude pattern")
                return False
        
        self.logger.debug(f"Hostname {hostname} passed all checks, will be processed")
        return True

    def start(self):
        """Start the network crawler"""
        self.logger.info("Starting network crawler")
        self.is_running = True
        
        # Add seed device to queue if it should be processed
        if self._should_process_hostname(self.seed_device):
            self.logger.info(f"Adding seed device to queue: {self.seed_device}")
            self.db.add_to_queue(self.seed_device)
        else:
            self.logger.warning(f"Seed device {self.seed_device} is excluded from processing")
            return
        
        # Start worker threads
        self.logger.info(f"Starting {self.max_workers} worker threads")
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker, name=f"Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            self.logger.debug(f"Started worker thread {worker.name}")
        
        self.logger.info("All worker threads started")
        
        # Wait for all workers to complete
        for worker in self.workers:
            self.logger.debug(f"Waiting for worker {worker.name} to complete")
            worker.join()
            self.logger.debug(f"Worker {worker.name} completed")
        
        self.is_running = False
        self.logger.info("Crawler completed")

    def _process_device(self, hostname: str) -> List[str]:
        """Process a single device and return list of discovered neighbors"""
        self.logger.info(f"Processing device: {hostname}")
        discovered_neighbors = []
        
        device = None
        try:
            # Create and connect to device
            self.logger.debug(f"Creating device connection for {hostname}")
            device = NetworkDevice(
                hostname=hostname,
                username=self.username,
                password=self.password,
                device_type=self.device_type
            )
            
            self.logger.debug(f"Connecting to device {hostname}")
            device.connect()
            
            # Get device information
            self.logger.debug(f"Getting device info from {hostname}")
            device_info = device.get_device_info()
            self.logger.debug(f"Device info: {device_info}")
            self.db.add_device(device_info)
            
            # Get CDP neighbors
            self.logger.debug(f"Getting CDP neighbors from {hostname}")
            neighbors = device.get_cdp_neighbors()
            self.logger.debug(f"Found {len(neighbors)} neighbors")
            
            # Collect all valid neighbors
            for neighbor in neighbors:
                neighbor_hostname = neighbor.get('hostname')
                if neighbor_hostname and self._should_process_hostname(neighbor_hostname):
                    discovered_neighbors.append(neighbor_hostname)
            
            # Mark device as processed
            self.logger.debug(f"Marking device {hostname} as processed")
            self.db.mark_processed(hostname)
            
        except Exception as e:
            self.logger.error(f"Error processing device {hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            if device:
                self.logger.debug(f"Disconnecting from device {hostname}")
                device.disconnect()
        
        return discovered_neighbors

    def _worker(self):
        """Worker thread that processes devices from the queue"""
        worker_name = threading.current_thread().name
        self.logger.info(f"{worker_name} started")
        
        while self.is_running:
            try:
                # Get next device from queue
                hostname = self.db.get_next_device()
                if not hostname:
                    self.logger.debug(f"{worker_name}: Queue empty, waiting...")
                    time.sleep(1)
                    continue
                
                # Skip if device already processed
                if self.db.is_device_known(hostname):
                    self.logger.info(f"{worker_name}: Device {hostname} already processed, skipping")
                    self.db.mark_processed(hostname)
                    continue
                
                # Process device and get discovered neighbors
                discovered_neighbors = self._process_device(hostname)
                
                # Add all discovered neighbors to queue at once
                if discovered_neighbors:
                    self.logger.info(f"{worker_name}: Adding {len(discovered_neighbors)} neighbors to queue")
                    for neighbor in discovered_neighbors:
                        self.db.add_to_queue(neighbor)
            
            except Exception as e:
                self.logger.error(f"{worker_name}: Worker error: {str(e)}")
                self.logger.error(f"{worker_name}: Traceback: {traceback.format_exc()}")
                time.sleep(1)  # Prevent tight loop on error

    def get_status(self) -> Dict:
        """Get current crawler status"""
        status = self.db.get_queue_status()
        self.logger.debug(f"Current status: {status}")
        return status

    def export_results(self, output_path: str):
        """Export crawl results to CSV"""
        self.logger.info(f"Exporting results to {output_path}")
        self.db.export_to_csv(output_path)
        self.logger.info(f"Results exported successfully")

    def stop(self):
        """Stop the network crawler"""
        self.logger.info("Stopping crawler...")
        self.is_running = False 