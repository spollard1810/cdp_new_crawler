import threading
import queue
import time
from typing import Dict, List
from devices import NetworkDevice
from data import DeviceDatabase
import logging
import re

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
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _should_process_hostname(self, hostname: str) -> bool:
        """Check if a hostname should be processed based on include/exclude rules"""
        # If include_only is specified, only process those hosts
        if self.include_only:
            return any(hostname.startswith(prefix) for prefix in self.include_only)
        
        # Check exclude rules
        for exclude_pattern in self.exclude_hosts:
            if exclude_pattern.startswith('*'):
                # Handle wildcard patterns like *.example.com
                pattern = exclude_pattern.replace('*', '.*')
                if re.match(pattern, hostname):
                    return False
            elif hostname == exclude_pattern:
                return False
        
        return True

    def start(self):
        """Start the network crawler"""
        self.is_running = True
        
        # Add seed device to queue if it should be processed
        if self._should_process_hostname(self.seed_device):
            self.db.add_to_queue(self.seed_device)
        else:
            self.logger.warning(f"Seed device {self.seed_device} is excluded from processing")
            return
        
        # Start worker threads
        for _ in range(self.max_workers):
            worker = threading.Thread(target=self._worker)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        self.logger.info(f"Started crawler with {self.max_workers} workers")
        
        # Wait for all workers to complete
        for worker in self.workers:
            worker.join()
        
        self.is_running = False
        self.logger.info("Crawler completed")

    def _worker(self):
        """Worker thread that processes devices from the queue"""
        while self.is_running:
            try:
                # Get next device from queue
                hostname = self.db.get_next_device()
                if not hostname:
                    # If queue is empty, wait a bit and check again
                    time.sleep(1)
                    continue
                
                # Skip if device already processed
                if self.db.is_device_known(hostname):
                    self.db.mark_processed(hostname)
                    continue
                
                self.logger.info(f"Processing device: {hostname}")
                
                try:
                    # Create and connect to device
                    device = NetworkDevice(
                        hostname=hostname,
                        username=self.username,
                        password=self.password,
                        device_type=self.device_type
                    )
                    
                    device.connect()
                    
                    # Get device information
                    device_info = device.get_device_info()
                    self.db.add_device(device_info)
                    
                    # Get CDP neighbors
                    neighbors = device.get_cdp_neighbors()
                    
                    # Add neighbors to queue if they should be processed
                    for neighbor in neighbors:
                        neighbor_hostname = neighbor.get('hostname')
                        if neighbor_hostname and self._should_process_hostname(neighbor_hostname):
                            self.db.add_to_queue(neighbor_hostname)
                    
                    # Mark device as processed
                    self.db.mark_processed(hostname)
                    
                except Exception as e:
                    self.logger.error(f"Error processing device {hostname}: {str(e)}")
                finally:
                    if device:
                        device.disconnect()
            
            except Exception as e:
                self.logger.error(f"Worker error: {str(e)}")
                time.sleep(1)  # Prevent tight loop on error

    def get_status(self) -> Dict:
        """Get current crawler status"""
        return self.db.get_queue_status()

    def export_results(self, output_path: str):
        """Export crawl results to CSV"""
        self.db.export_to_csv(output_path)
        self.logger.info(f"Results exported to {output_path}")

    def stop(self):
        """Stop the network crawler"""
        self.is_running = False
        self.logger.info("Stopping crawler...") 