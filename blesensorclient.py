"""
This class is a BLE client that connects to and read values from a BLE server. 
It wraps the BleakClient class from the Bleak library and makes necessary calls to connect to the server and read characteristics.
It exposes synchronous methods, attachec to mainloop, for connecting to the server, reading characteristics, and checking connection status 
that can be used by the event loop of a D-Bus service.
"""
import asyncio
from datetime import datetime
import logging
from bleak import BleakClient, BleakScanner

class BLESensorClient:
    def __init__(self, target_device_name):
        self.logger = logging.getLogger(__name__) # create logger
        self.logger.info("Initializing BLE Sensor Client...")
        self.target_device_name = target_device_name
        self.device = None
        self.client = None
        self.connected_at = None

    def __enter__(self):
        self.logger.info("on enter")
        loop = asyncio.get_event_loop()
        v = loop.run_until_complete(self.__connect_client())

    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.info("on exit")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__disconnect_client())

    async def __disconnect_client(self):
        try:
            if self.client is not None and self.client.is_connected:
                self.logger.info("Disconnecting client...")
                await self.client.disconnect()
                self.connected_at = None
        except Exception as e:
            self.logger.error("Error disconnecting client: %s", e)
    
    async def __connect_client(self):
        try:
            self.logger.info("Scanning for device with name '%s'...", self.target_device_name)
            self.device = await BleakScanner.find_device_by_name(self.target_device_name, cb=dict(use_bdaddr=False))
            if self.device is None:
                self.logger.warn("Could not find device")
                return False
            self.logger.info("Device found!")
            self.client = BleakClient(self.device)
            await self.client.connect()
            self.logger.info("Connected to device!")
            self.connected_at = datetime.now()
            return True
        except Exception as e:
            self.logger.error("Error connecting to device: %s", e)
            return False
        
    def ensure_connected(self):
        try:
            if not self.is_connected():
                self.logger.info("Client is not connected. Attempting to connect...")
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.__connect_client())
            return self.is_connected()
        except Exception as e:
            self.logger.error("Error ensuring connection: %s", e)

    def read_characteristic(self, uuid):
        try:
            loop = asyncio.get_event_loop()
            value = loop.run_until_complete(self.client.read_gatt_char(uuid))
            self.logger.debug("Read characteristic (%s) value: %r", uuid, value)
            return value
        except Exception as e:
            self.logger.error("Error reading characteristic (%s): %s", uuid, e)
    
    def is_connected(self):
        is_connected = self.client is not None and self.client.is_connected
        if not is_connected:
            self.logger.debug("Client is not connected")
            self.connected_at = None
        return is_connected
    
    def connected_for(self):
        return datetime.now() - self.connected_at if self.connected_at is not None else None

    def disconnect(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.__disconnect_client())

class DeviceNotFoundError(Exception):
    pass