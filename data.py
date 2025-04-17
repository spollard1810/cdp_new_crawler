import sqlite3
from typing import Dict, List
import csv
from datetime import datetime

class DeviceDatabase:
    def __init__(self, db_path: str = 'network_devices.db'):
        self.db_path = db_path
        self._init_db()

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
            
            # Create crawl_queue table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_queue (
                    hostname TEXT PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT 0
                )
            ''')
            
            conn.commit()

    def add_device(self, device_info: Dict):
        """Add or update device information in the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO devices (
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
            
            conn.commit()

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
        """Get the next unprocessed device from the queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get the oldest unprocessed device
            cursor.execute('''
                SELECT hostname FROM crawl_queue
                WHERE processed = 0
                ORDER BY added_at ASC
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            if result:
                return result[0]
            return None

    def mark_processed(self, hostname: str):
        """Mark a device as processed in the queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE crawl_queue
                SET processed = 1
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
            
            cursor.execute('''
                SELECT * FROM devices
            ''')
            
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(rows) 