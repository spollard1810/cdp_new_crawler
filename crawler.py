import threading
import queue
import logging
import traceback
from typing import Dict, List
from devices import NetworkDevice
from data import DeviceDatabase

class NetworkCrawler:
    def __init__(self, seed_device: str, excluded_hosts: List[str] = None, included_hosts: List[str] = None):
        self.seed_device = seed_device
        self.excluded_hosts = excluded_hosts or []
        self.included_hosts = included_hosts or []
        self.db = DeviceDatabase()
        self.workers = []
        self.running = False
        
        # Configure logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('crawler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Initialized crawler with seed device: {seed_device}")
        self.logger.info(f"Excluded hosts: {self.excluded_hosts}")
        self.logger.info(f"Included hosts: {self.included_hosts}")

    def _should_process_hostname(self, hostname: str) -> bool:
        """Check if a hostname should be processed"""
        if hostname in self.excluded_hosts:
            self.logger.debug(f"Hostname {hostname} is in excluded list")
            return False
        if self.included_hosts and hostname not in self.included_hosts:
            self.logger.debug(f"Hostname {hostname} is not in included list")
            return False
        return True

    def start(self, num_workers: int = 4):
        """Start the crawler with the specified number of worker threads"""
        self.logger.info(f"Starting crawler with {num_workers} workers")
        self.running = True
        
        # Clear any existing queue
        self.db.clear_queue()
        
        # Add seed device to queue
        self.db.add_to_queue(self.seed_device)
        self.logger.info(f"Added seed device {self.seed_device} to queue")
        
        # Start worker threads
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker, name=f"Worker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            self.logger.info(f"Started worker thread {worker.name}")

    def _process_device(self, hostname: str) -> List[str]:
        """Process a single device and return list of discovered neighbors"""
        self.logger.info(f"Processing device: {hostname}")
        device = NetworkDevice(hostname)
        
        try:
            # Connect to device
            if not device.connect():
                self.logger.error(f"Failed to connect to device {hostname}")
                return []
            
            # Get device info
            device_info = device.get_device_info()
            if device_info:
                self.db.add_device(device_info)
                self.logger.info(f"Added device info for {hostname}")
            
            # Get CDP neighbors
            neighbors = device.get_cdp_neighbors()
            self.logger.info(f"Found {len(neighbors)} neighbors for {hostname}")
            
            # Filter and add valid neighbors to queue
            valid_neighbors = []
            for neighbor in neighbors:
                if self._should_process_hostname(neighbor):
                    valid_neighbors.append(neighbor)
                    self.db.add_to_queue(neighbor)
            
            self.logger.info(f"Added {len(valid_neighbors)} valid neighbors to queue")
            return valid_neighbors
            
        except Exception as e:
            self.logger.error(f"Error processing device {hostname}: {str(e)}")
            self.logger.error(traceback.format_exc())
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
                
                # Process device and get neighbors
                neighbors = self._process_device(hostname)
                
                # Mark device as processed
                self.db.mark_processed(hostname)
                self.logger.info(f"Marked {hostname} as processed")
                
                # Log queue status
                status = self.db.get_queue_status()
                self.logger.info(f"Queue status: {status['pending']} pending, {status['processed']} processed")
                
            except Exception as e:
                self.logger.error(f"Error in worker thread: {str(e)}")
                self.logger.error(traceback.format_exc())

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