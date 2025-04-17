import threading
import queue
import logging
import traceback
import re
from typing import Dict, List
from devices import NetworkDevice
from data import DeviceDatabase

class NetworkCrawler:
    def __init__(self, seed_device: str, username: str, password: str, 
                 device_type: str = 'cisco_ios', max_workers: int = 5,
                 exclude_hosts: List[str] = None, include_only: List[str] = None,
                 db_path: str = 'network_devices.db'):
        self.seed_device = seed_device
        self.username = username
        self.password = password
        self.device_type = device_type
        self.max_workers = max_workers
        self.exclude_hosts = exclude_hosts or []
        self.include_only = include_only or []
        self.db = DeviceDatabase(db_path)
        self.workers = []
        self.running = False
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('crawler.log'),
                logging.StreamHandler()
            ]
        )
        
        # Set paramiko logging to WARNING level to reduce noise
        logging.getLogger('paramiko').setLevel(logging.WARNING)
        logging.getLogger('netmiko').setLevel(logging.WARNING)
        
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Initialized crawler with seed device: {seed_device}")
        self.logger.info(f"Exclude hosts: {self.exclude_hosts}")
        self.logger.info(f"Include only: {self.include_only}")

    def _clean_hostname(self, hostname: str) -> str:
        """Clean hostname to site-xx-xx format"""
        # Extract site-xx-xx pattern from FQDN
        match = re.match(r'^(site-\d+-\d+)', hostname)
        if match:
            return match.group(1)
        return hostname

    def _should_process_hostname(self, hostname: str) -> bool:
        """Check if a hostname should be processed"""
        # Clean the hostname first
        clean_hostname = self._clean_hostname(hostname)
        
        # Check if already processed
        if self.db.is_device_known(clean_hostname):
            self.logger.debug(f"Hostname {clean_hostname} already processed")
            return False
            
        if clean_hostname in self.exclude_hosts:
            self.logger.debug(f"Hostname {clean_hostname} is in excluded list")
            return False
        if self.include_only and clean_hostname not in self.include_only:
            self.logger.debug(f"Hostname {clean_hostname} is not in included list")
            return False
        return True

    def start(self):
        """Start the crawler with the specified number of worker threads"""
        self.logger.info(f"Starting crawler with {self.max_workers} workers")
        self.running = True
        
        # Clear any existing queue
        self.db.clear_queue()
        
        # Add seed device to queue if it should be processed
        if self._should_process_hostname(self.seed_device):
            self.db.add_to_queue(self.seed_device)
            self.logger.info(f"Added seed device {self.seed_device} to queue")
        else:
            self.logger.warning(f"Seed device {self.seed_device} is excluded from processing")
            return
        
        # Start worker threads
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker, name=f"Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            self.logger.info(f"Started worker thread {worker.name}")

    def _process_device(self, hostname: str) -> List[str]:
        """Process a single device and return list of discovered neighbors"""
        self.logger.info(f"Processing device: {hostname}")
        device = NetworkDevice(
            hostname=hostname,
            username=self.username,
            password=self.password,
            device_type=self.device_type,
            worker_id=threading.current_thread().name  # Pass worker thread name as ID
        )
        
        try:
            # First try connecting with hostname
            try:
                self.logger.info(f"Attempting to connect to {hostname} via hostname")
                device.connect()
            except ConnectionError as e:
                self.logger.warning(f"Failed to connect to {hostname} via hostname: {str(e)}")
                # If we have a management IP, try that as fallback
                if device.mgmt_ip:
                    self.logger.info(f"Attempting fallback connection to {hostname} via management IP: {device.mgmt_ip}")
                    device.connect()  # This will use the management IP as fallback
                else:
                    self.logger.error(f"No management IP available for {hostname}, skipping")
                    return []
            
            # Step 1: Get device info from show version
            self.logger.info(f"Getting device info from {hostname}")
            device_info = device.get_device_info()
            if not device_info:
                self.logger.error(f"Failed to get device info from {hostname}")
                return []
                
            # Step 2: Clean hostname before storing
            device_info['hostname'] = self._clean_hostname(device_info['hostname'])
            
            # Step 3: Get CDP neighbors
            self.logger.info(f"Getting CDP neighbors from {hostname}")
            neighbors = device.get_cdp_neighbors()
            if not neighbors:
                self.logger.warning(f"No CDP neighbors found for {hostname}")
                # Even if no neighbors, we should still add the device to DB
                self.db.add_device(device_info)
                return []
                
            self.logger.info(f"Found {len(neighbors)} neighbors for {hostname}")
            
            # Step 4: Process and add neighbors to queue
            valid_neighbors = []
            for neighbor in neighbors:
                # Skip if not a valid neighbor dictionary
                if not isinstance(neighbor, dict):
                    self.logger.warning(f"Invalid neighbor format: {neighbor}")
                    continue
                    
                # Get and clean the hostname
                neighbor_hostname = neighbor.get('hostname')
                if not neighbor_hostname:
                    self.logger.warning(f"Neighbor missing hostname: {neighbor}")
                    continue
                    
                clean_neighbor = self._clean_hostname(neighbor_hostname)
                if self._should_process_hostname(clean_neighbor):
                    # Store both hostname and management IP for fallback
                    neighbor_info = {
                        'hostname': clean_neighbor,
                        'mgmt_ip': neighbor.get('ip', '')  # Store the management IP for fallback
                    }
                    valid_neighbors.append(neighbor_info)
                    self.db.add_to_queue(clean_neighbor)
                    self.logger.debug(f"Added neighbor to queue: {clean_neighbor} (IP: {neighbor.get('ip', 'N/A')})")
            
            # Step 5: Only after processing neighbors, add the device to DB
            self.db.add_device(device_info)
            self.logger.info(f"Added device info for {hostname}")
            
            self.logger.info(f"Added {len(valid_neighbors)} valid neighbors to queue")
            return valid_neighbors
            
        except Exception as e:
            self.logger.error(f"Error processing device {hostname}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return []
        finally:
            device.disconnect()

    def _worker(self):
        """Worker thread function"""
        while self.running:
            try:
                # Get next device from queue
                hostname = self.db.get_next_device()
                if not hostname:
                    self.logger.debug("Queue is empty, waiting...")
                    continue
                
                try:
                    # Skip if device already processed
                    if self.db.is_device_known(hostname):
                        self.logger.info(f"Device {hostname} already processed, skipping")
                        self.db.mark_processed(hostname)
                        continue
                    
                    # Process device and get neighbors
                    neighbors = self._process_device(hostname)
                    
                    # Mark device as processed
                    self.db.mark_processed(hostname)
                    self.logger.info(f"Marked {hostname} as processed")
                    
                    # Log queue status
                    status = self.db.get_queue_status()
                    self.logger.info(f"Queue status: {status['pending']} pending, {status['processed']} processed")
                    
                except Exception as e:
                    # If anything goes wrong, release the device from processing state
                    self.logger.error(f"Error processing device {hostname}: {str(e)}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                    self.db.release_device(hostname)
                    continue
                
            except Exception as e:
                self.logger.error(f"Error in worker thread: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")

    def stop(self):
        """Stop the crawler"""
        self.logger.info("Stopping crawler...")
        self.running = False
        for worker in self.workers:
            worker.join()
        self.logger.info("Crawler stopped")

    def get_status(self) -> Dict:
        """Get current crawler status"""
        status = self.db.get_queue_status()
        self.logger.info(f"Current status: {status}")
        return status

    def export_results(self, output_path: str):
        """Export results to CSV"""
        self.logger.info(f"Exporting results to {output_path}")
        self.db.export_to_csv(output_path) 