"""
This class is a BLE client that connects to and read values from a BLE server. 
It wraps the BleakClient class from the Bleak library and makes necessary calls to connect to the server and read characteristics.
It exposes synchronous methods, attachec to mainloop, for connecting to the server, reading characteristics, and checking connection status 
that can be used by the event loop of a D-Bus service.
"""
import asyncio
from datetime import datetime
from threading import Thread, Lock
import logging
import subprocess
from bleak import BleakClient, BleakScanner, BleakGATTCharacteristic

class BLESensorClient:
    def __init__(self, target_device_name, characteristic_uuids):
        self.logger = logging.getLogger(__name__) # create logger
        self.logger.info("Initializing BLE Sensor Client...")
        self.target_device_name = target_device_name
        self.device = None
        self.client = None
        self.connected_at = None
        self.characteristic_uuids = characteristic_uuids
        self.characteristic_values = {} # store characteristic values
        self.monitor_thread = None
        self.Lock = Lock()

    def StartMonitoring(self):
        self.logger.info("Starting BLE Sensor Client...")
        if self.monitor_thread is not None:
            self.logger.warn("Monitor thread already started. Ignoring request to start again.")
            return
        self.monitor_thread = Thread(target=asyncio.run, args=(self.__monitorAsync()), daemon=True)
        self.monitor_thread.start()

    def StopMonitoring(self):
        self.logger.info("Stopping BLE Sensor Client...")
        if self.monitor_thread is None:
            self.logger.warn("Monitor thread not started. Ignoring request to stop.")
            return
        self.monitor_thread.join()
        self.monitor_thread = None

    async def __monitorAsync(self):

        while True:
            try:
                await self._ensure_connected()
                await asyncio.sleep(10)  # check every 10 seconds
            except Exception as e:
                self.logger.error("Error monitoring client: %s", e)
            finally:
                self.Lock.release()

    async def _disconnect(self):
        try:
            if self.client is not None and self.client.is_connected:
                self.logger.info("Disconnecting client...")
                await self.client.disconnect()
                self.connected_at = None
        except Exception as e:
            self.logger.error("Error disconnecting client: %s", e)
    
    async def _connect(self):
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

            for characteristic in self.target_characteristics:
                self.logger.info("Subscribing to characteristic: %s", characteristic)
                await self.client.start_notify(characteristic, self._notification_handler)
            return True
        except Exception as e:
            self.logger.error("Error connecting to device: %s", e)
            return False
        
    def _notification_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        try:
            self.Lock.acquire()
            self.logger.info("Notification received for characteristic (%s): %r", characteristic.uuid, data)
            self.characteristic_values[characteristic.uuid] = data
        except Exception as e:
            self.logger.error("Error handling notification: %s", e)
        finally:
            self.Lock.release()
        
    async def _ensure_connected(self):
        try:
            if self.Is_Connected():
                return
            
            self.logger.info("Client is not connected. Attempting to connect...")
            if(await self._connect()):
                self.logger.info("Connected to device")
                return
            subprocess.run('bluetoothctl power off', shell=True, check=True)
            # check_call("bluetoothctl power off")
            await asyncio.sleep(2)
            # check_call("bluetoothctl power on")
            subprocess.run('bluetoothctl power on', shell=True, check=True)
            await asyncio.sleep(2)
            logging.info("Trying to re-connect after Bluetooth reset")
            if(await self._connect()):
                self.logger.info("Connected to device")
                return
            logging.error("Could not connect to device after Bluetooth reset. Exiting in 1 minute...")
            raise Exception("Could not connect to device")  # Stop the program, will be restarted by the daemon supervisor
        except Exception as e:
            self.logger.error("Error ensuring connection: %s", e)

    def Get_Characteristic_Value(self, uuid):
        try:
            self.Lock.acquire()
            return self.characteristic_values[uuid] if uuid in self.characteristic_values else None
        except Exception as e:
            self.logger.error("Error getting characteristic value: %s", e)
        finally:
            self.Lock.release()

    def Is_Connected(self):
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