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
                INSERT OR REPLACE INTO devices (
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
            
            cursor.execute('''
                INSERT OR IGNORE INTO crawl_queue (hostname)
                VALUES (?)
            ''', (hostname,))
            
            conn.commit()

    def get_next_device(self) -> str:
        """Get the next unprocessed device from the queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
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

    def get_queue_status(self) -> Dict:
        """Get current status of the crawl queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN processed = 0 THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) as processed
                FROM crawl_queue
            ''')
            
            result = cursor.fetchone()
            return {
                'total': result[0],
                'pending': result[1],
                'processed': result[2]
            } 