"""
This class is a BLE client that connects to and read values from a BLE server. 
It runs in a separate thread and continuously monitors the connection to the server and updates values from the server when notified.
"""
import asyncio
from datetime import datetime
from threading import Thread, Lock
import logging
import subprocess
from bleak import BleakClient, BleakScanner, BleakGATTCharacteristic

class SensorBLEClient:
    def __init__(self, target_device_name, characteristic_uuids, mainloop):
        self.mainloop = mainloop
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

    def start_monitoring(self):
        self.logger.info("Starting BLE Sensor Client...")
        if self.monitor_thread is not None:
            self.logger.warn("Monitor thread already started. Ignoring request to start again.")
            return
        self.monitor_thread = Thread(target=self._monitor,name="BLE Sensor Monitoring Thread", daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.logger.info("Stopping BLE Sensor Client...")
        if self.monitor_thread is None:
            self.logger.warn("Monitor thread not started. Ignoring request to stop.")
            return
        self.active = False         # signal to stop monitoring
        self.monitor_thread.join()  # wait for thread to stop
        self.monitor_thread = None  # reset thread

    def _monitor(self):
        asyncio.run(self._monitorAsync())

    async def _monitorAsync(self):
        self.active = True
        while self.active:
            try:
                await self._ensure_connected()
                await asyncio.sleep(1)  # check connection every 1 second
            except Exception as e:
                self.logger.error("Error monitoring client: %s", e)
                self.mainloop.quit()
        await self.__disconnect_client()
        self.logger.info("Monitoring thread stopped")
    
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

            for characteristic in self.characteristic_uuids:
                self.logger.info("Subscribing to characteristic: %s", characteristic)
                await self.client.start_notify(characteristic, self._notification_handler)
            return True
        except Exception as e:
            self.logger.error("Error connecting to device: %s", e)
            return False
        
    async def _disconnect(self):
        try:
            if self.client is not None and self.client.is_connected:
                self.logger.info("Disconnecting client...")
                await self.client.disconnect()
                self.connected_at = None
        except Exception as e:
            self.logger.error("Error disconnecting client: %s", e)
        
    def _notification_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        try:
            self.Lock.acquire()
            self.logger.info("Notification received for characteristic (%s): %r", characteristic.uuid, data)
            self.characteristic_values[characteristic.uuid] = data
        except Exception as e:
            self.logger.error("Error handling notification: %s", e)
        finally:
            if self.Lock.locked():
                self.Lock.release()
        
    async def _ensure_connected(self):
        try:
            if self.is_connected():
                return
            self.logger.info("Client is not connected. Attempting to connect...")
            if(await self._connect()):
                self.logger.info("Connected to device")
                return
            self.logger.error("Could not connect to device. Resetting Bluetooth...")
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
            logging.error("Could not connect to device after Bluetooth reset. Exiting driver...")
            raise Exception("Could not connect to device")  # Rasing exception to stop the main loop
        except Exception as e:
            self.logger.error("Error ensuring connection: %s", e)
            self.mainloop.quit()

    def get_characteristic_value(self, uuid):
        try:
            self.Lock.acquire()
            if uuid in self.characteristic_values:
                return self.characteristic_values[uuid]
            return None
        except Exception as e:
            self.logger.error("Error getting characteristic value: %s", e)
        finally:
            if self.Lock.locked():
                self.Lock.release()

    def is_connected(self):
        is_connected = self.client is not None and self.client.is_connected
        if not is_connected:
            self.logger.debug("Client is not connected")
            self.connected_at = None
        return is_connected
    
class DeviceNotFoundError(Exception):
    pass