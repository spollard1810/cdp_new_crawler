import sqlite3
from typing import Dict, List
import csv
from datetime import datetime
import logging
import traceback

class DeviceDatabase:
    def __init__(self, db_path: str = 'network_devices.db'):
        self.db_path = db_path
        self._init_db()
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized DeviceDatabase with path: {db_path}")

    def _init_db(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create devices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    hostname TEXT PRIMARY KEY,
                    ip TEXT,
                    serial_number TEXT,
                    device_type TEXT,
                    version TEXT,
                    platform TEXT,
                    rommon TEXT,
                    config_register TEXT,
                    mac_address TEXT,
                    uptime TEXT,
                    last_crawled TIMESTAMP
                )
            ''')
            
            # Create crawl_queue table with processing state
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    hostname TEXT PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT 0,
                    processing BOOLEAN DEFAULT 0
                )
            ''')
            
            conn.commit()

    def add_device(self, device_info: Dict):
        """Add or update device information in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First check if device exists
                cursor.execute('''
                    SELECT 1 FROM devices WHERE hostname = ?
                ''', (device_info.get('hostname'),))
                
                exists = cursor.fetchone() is not None
                self.logger.info(f"Device {device_info.get('hostname')} exists in DB: {exists}")
                
                if exists:
                    # Update existing device
                    self.logger.info(f"Updating device {device_info.get('hostname')} in database")
                    cursor.execute('''
                        UPDATE devices SET
                            ip = COALESCE(?, ip),
                            serial_number = COALESCE(?, serial_number),
                            device_type = COALESCE(?, device_type),
                            version = COALESCE(?, version),
                            platform = COALESCE(?, platform),
                            rommon = COALESCE(?, rommon),
                            config_register = COALESCE(?, config_register),
                            mac_address = COALESCE(?, mac_address),
                            uptime = COALESCE(?, uptime),
                            last_crawled = ?
                        WHERE hostname = ?
                    ''', (
                        device_info.get('ip'),
                        device_info.get('serial_number'),
                        device_info.get('device_type'),
                        device_info.get('version'),
                        device_info.get('platform'),
                        device_info.get('rommon'),
                        device_info.get('config_register'),
                        device_info.get('mac_address'),
                        device_info.get('uptime'),
                        datetime.now(),
                        device_info.get('hostname')
                    ))
                    self.logger.info(f"Successfully updated device: {device_info.get('hostname')}")
                else:
                    # Insert new device
                    self.logger.info(f"Inserting new device {device_info.get('hostname')} into database")
                    cursor.execute('''
                        INSERT INTO devices (
                            hostname, ip, serial_number, device_type, version,
                            platform, rommon, config_register, mac_address, uptime,
                            last_crawled
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device_info.get('hostname'),
                        device_info.get('ip'),
                        device_info.get('serial_number'),
                        device_info.get('device_type'),
                        device_info.get('version'),
                        device_info.get('platform'),
                        device_info.get('rommon'),
                        device_info.get('config_register'),
                        device_info.get('mac_address'),
                        device_info.get('uptime'),
                        datetime.now()
                    ))
                    self.logger.info(f"Successfully inserted new device: {device_info.get('hostname')}")
                
                conn.commit()
                self.logger.info(f"Database commit successful for device: {device_info.get('hostname')}")
        except sqlite3.Error as e:
            self.logger.error(f"Database error for device {device_info.get('hostname')}: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def add_to_queue(self, hostname: str):
        """Add a device to the crawl queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # First check if device is already in queue
            cursor.execute('''
                SELECT 1 FROM crawl_queue WHERE hostname = ?
            ''', (hostname,))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO crawl_queue (hostname, processed)
                    VALUES (?, 0)
                ''', (hostname,))
                conn.commit()

    def get_next_device(self) -> str:
        """Get the next unprocessed device from the queue that isn't being processed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get the oldest unprocessed and not processing device
            cursor.execute('''
                SELECT hostname FROM crawl_queue
                WHERE processed = 0 AND processing = 0
                ORDER BY added_at ASC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            if result:
                # Mark as processing
                cursor.execute('''
                    UPDATE crawl_queue
                    SET processing = 1
                    WHERE hostname = ?
                ''', (result[0],))
                conn.commit()
                return result[0]
            return None

    def mark_processed(self, hostname: str):
        """Mark a device as processed in the queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE crawl_queue
                SET processed = 1,
                    processing = 0
                WHERE hostname = ?
            ''', (hostname,))
            
            conn.commit()

    def release_device(self, hostname: str):
        """Release a device from processing state if something went wrong"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE crawl_queue
                SET processing = 0
                WHERE hostname = ?
            ''', (hostname,))
            
            conn.commit()

    def is_device_known(self, hostname: str) -> bool:
        """Check if a device exists in the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 1 FROM devices
                WHERE hostname = ?
            ''', (hostname,))
            
            return cursor.fetchone() is not None

    def get_queue_status(self) -> Dict:
        """Get current status of the crawl queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM crawl_queue')
            total = cursor.fetchone()[0]
            
            # Get pending count
            cursor.execute('SELECT COUNT(*) FROM crawl_queue WHERE processed = 0')
            pending = cursor.fetchone()[0]
            
            # Get processed count
            cursor.execute('SELECT COUNT(*) FROM crawl_queue WHERE processed = 1')
            processed = cursor.fetchone()[0]
            
            return {
                'total': total,
                'pending': pending,
                'processed': processed
            }

    def clear_queue(self):
        """Clear the queue table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM crawl_queue')
            conn.commit()

    def export_to_csv(self, output_path: str):
        """Export device information to CSV"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get all devices with their information
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
            
            # Get column names
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            # Write to CSV
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(columns)
                
                # Write data rows
                for row in rows:
                    # Convert any None values to empty strings
                    processed_row = [str(value) if value is not None else '' for value in row]
                    writer.writerow(processed_row) 