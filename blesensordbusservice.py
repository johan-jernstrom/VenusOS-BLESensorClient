#!/usr/bin/env python

"""
This is a service driver for the dbus in venus os. 
It connects to a BLE server and reads values from it.
It registers a service for each sensor and the continously 
updates the dbus with the values read from the BLE server.

The service is based on the dbusdummyservice.py example from the venus os project:
https://github.com/victronenergy/velib_python/blob/master/dbusdummyservice.py
"""
import platform
import argparse
import logging
import sys
import os
from datetime import datetime
import struct
import signal
from os import _exit as os_exit
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop
import dbus
import dbus.service
from sensorbleclient import SensorBLEClient

# import victron package for updating dbus (using lib from built in service)
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-modem'))
from vedbus import VeDbusService
from ve_utils import exit_on_error
from settingsdevice import SettingsDevice

# CONFIGURATION TODO: place in config file

target_device_name = "ESP32 BLE Sensor Server" # name of the BLE server device to connect to

# array of sensors with metadata and settings
# https://github.com/victronenergy/venus/wiki/dbus#tank-levels for more information on dbus paths
sensors =   [
                {
                    "BLE_Char_UUID": "22d8381a-e6df-4ad1-a101-5e2e47c0762b",
                    "Type": "tank",
                    "DeviceInstance": 5350,
                    "Paths":
                        {
                            '/Level': {'initial': 0},
                            '/Remaining' : {'initial': 1},  #m3 remaining in tank (calculated from level and capacity)
                            '/Capacity' : {'initial': 1},   #m3 total capacity of tank (100%)
                            '/FluidType' : {'initial': 1},  #0=Fuel; 1=Fresh water; 2=Waste water; 3=Live well; 4=Oil; 5=Black water (sewage); 6=Gasoline; 7=Diesel; 8=Liquid  Petroleum Gas (LPG); 9=Liquid Natural Gas (LNG); 10=Hydraulic oil; 11=Raw water
                            '/Status' : {'initial': 0},
                            '/CustomName': {'initial': 'Vattentank'},
                            '/Standard' : {'initial': '2'},  #0=European (resistive); 1=USA (resistive); 2=Not applicable (used for Voltage and Amp sensors)
                        }
                }
                ,
                {
                    "BLE_Char_UUID": "9910102a-9d4e-41ce-be93-affba54425c4",
                    "Type": "tank",
                    "DeviceInstance": 5351,
                    "Paths":
                        {
                            '/Level': {'initial': 0},
                            '/Remaining' : {'initial': 1},  #m3 remaining in tank (calculated from level and capacity)
                            '/Capacity' : {'initial': 1},   #m3 total capacity of tank (100%)
                            '/FluidType' : {'initial': 5},  #0=Fuel; 1=Fresh water; 2=Waste water; 3=Live well; 4=Oil; 5=Black water (sewage); 6=Gasoline; 7=Diesel; 8=Liquid  Petroleum Gas (LPG); 9=Liquid Natural Gas (LNG); 10=Hydraulic oil; 11=Raw water
                            '/Status' : {'initial': 0},
                            '/CustomName': {'initial': 'Septiktank'},
                            '/Standard' : {'initial': '2'},  #0=European (resistive); 1=USA (resistive); 2=Not applicable (used for Voltage and Amp sensors)
                        }
                }
                ,
                {
                    "BLE_Char_UUID": "c6db06e1-7f34-48ff-9f1e-f2904ac78525",
                    "Type": "temperature",
                    "DeviceInstance": 4350,
                    "Paths":
                        {
                            '/Temperature': {'initial': 0},
                            '/TemperatureType' : {'initial': 0},
                            '/CustomName': {'initial': 'Temp inne'},
                        }
                }
                ,
                {
                    "BLE_Char_UUID": "df2be7ec-fb73-40b6-b2cb-3c00d37f2229", # humidity
                    "Type": "temperature",
                    "DeviceInstance": 4351,
                    "Paths":
                        {
                            '/Temperature': {'initial': 0},
                            '/TemperatureType' : {'initial': 0},
                            '/CustomName': {'initial': 'Temp ute'},
                        }
                }
                
]

# END CONFIGURATION


class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)

class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)

def dbusconnection():
    return SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else SystemBus()

class SensorDbusService:
    def __init__(self, metadata, bleclient):
        self._bleclient = bleclient
        self._metadata = metadata
        self._servicename = 'com.victronenergy.'+ str(metadata["Type"]) + '.ble_' + str(metadata["Type"]) + '_sensor_' + str(metadata["DeviceInstance"])
        self._dbusservice = VeDbusService(self._servicename, dbusconnection())

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', 'Bluetooth LE')

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', self._metadata["DeviceInstance"])
        self._dbusservice.add_path('/ProductId', 0)
        self._dbusservice.add_path('/ProductName', 'BLE Sensor Client')
        self._dbusservice.add_path('/FirmwareVersion', 1.0)
        self._dbusservice.add_path('/HardwareVersion', 1.0)
        self._dbusservice.add_path('/Connected', 1)

        for path, settings in self._metadata["Paths"].items():
            self._dbusservice.add_path(path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

        GLib.timeout_add(1000, exit_on_error, self._update)    # Update the sensor every second
        
        logging.info("Service %s started" % self._servicename)

    def _handlechangedvalue(self, path, value):
        logging.info("Someone else updated %s to %s" % (path, value))
        return True # accept the change
    
    def _update(self):
        if not self._bleclient.is_connected():
            logging.debug("Not connected, skipping update sensor since not connected")
            return True # return True to keep the timeout running
        
        type = self._metadata["Type"]
        if type == "temperature":
            self.update_sensor_value("/Temperature")
        elif type == "tank":
            if self.update_sensor_value("/Level"):
                remaining = round(self._metadata["Paths"]["/Capacity"]["initial"] * (self._dbusservice["/Level"] / 100), 6) # calculate remaining volume based on level and capacity, round to 6 decimals since it is in m3
                self._dbusservice["/Remaining"] = remaining
                logging.debug("Updated %s%s to %s" % (self._servicename, "/Remaining", remaining))   
        else:
            logging.error("Unknown sensor type: %s" % type)
        return True     # return True to keep the timeout running

    def update_sensor_value(self, path):
        metadata = self._metadata
        data = self._bleclient.get_characteristic_value(metadata["BLE_Char_UUID"])
        if data is None:
            return False # try again later
        logging.debug("Got characteristic (%s) value: %r", metadata["BLE_Char_UUID"], data)
        if len(data) >= 8:  # Ensure data has at least 8 bytes
            double_value = struct.unpack('d', data)[0]
            value = round(double_value, 1)
        else:
            value = int.from_bytes(data, byteorder='little')
        self._dbusservice[path] = value
        logging.debug("Updated %s%s to %s" % (self._servicename, path, self._dbusservice[path]))
        return True

class ClientDbusService:
    def __init__(self, bleclient):
        self._bleclient = bleclient
        self._servicename = 'com.victronenergy.BLESensorClient'
        self._dbusservice = VeDbusService(self._servicename, dbusconnection())

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', 'Bluetooth LE')

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', 1)
        self._dbusservice.add_path('/ProductId', 0)
        self._dbusservice.add_path('/ProductName', 'BLE Sensor Client')
        self._dbusservice.add_path('/FirmwareVersion', 1.0)
        self._dbusservice.add_path('/HardwareVersion', 1.0)
        self._dbusservice.add_path('/Connected', 1)

        # Create specific paths for the client
        self._dbusservice.add_path('/State', '-', writeable=True)
        self._dbusservice.add_path('/ConnectedFor', '-', writeable=True)
        self._dbusservice.add_path('/NumberOfSensors', len(sensors), writeable=True)

        # create the setting that allows enabling the RPI shutdown pin
        settingsList = {'Enabled': [ '/Settings/BLESensorClient/Enabled', 0, 0, 0 ],}
        self.dbusSettings = SettingsDevice(bus=dbus.SystemBus(), supportedSettings=settingsList, timeout = 10, eventCallback = self._handle_enabled_changed)

        GLib.timeout_add(2000, exit_on_error, self._update_state)    # Update the dbus every 2 second

        logging.info("Service %s started" % self._servicename)

    def _handle_enabled_changed(self, setting, old, new):
        logging.info("Enabled changed from %s to %s" % (old, new))
        if new == 0:
            self._bleclient.stop_monitoring()
        else:
            self._bleclient.start_monitoring()
        return True # accept the change
    
    def _update_state(self):
        logging.debug("Updating state of the Client DbusService")
        self._dbusservice['/State'] = 'Connected' if self._bleclient.is_connected() else 'Not connected'
        self._dbusservice['/ConnectedFor'] = str(datetime.now() - self._bleclient.connected_at).split('.')[0] if self._bleclient.connected_at is not None else '-'
        return True

def main():
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)
    mainloop = GLib.MainLoop()

    # pass all sensor UUIDs to the BLE client to monitor
    sensorClient = SensorBLEClient(target_device_name, [sensor["BLE_Char_UUID"] for sensor in sensors], mainloop)

    # Handle signals to ensure cleanup of the client
    def cleanup(signum, frame):
        try:
            logging.info('Signal handler called with signal %s', signum)
            if sensorClient is not None:
                logging.info('Disconnecting client...')
                sensorClient.stop_monitoring()
            mainloop.quit()
        except Exception as e:
            logging.error('Error in signal handler: %s', e)
        finally:
            os_exit(1)  # exit the program with error code 1. sys.exit() is not used, since that throws an exception, which does not lead to a program halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Create the dbus services
    clientDbusService = ClientDbusService(sensorClient)
    for sensor in sensors:
        SensorDbusService(sensor, sensorClient)

    if(clientDbusService.dbusSettings is not None):
        logging.info('Settings device created')
    
    if clientDbusService.dbusSettings["Enabled"] == 1:
        sensorClient.start_monitoring()
    else:
        logging.info('BLE Sensor Client is disabled')

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop.run()
    sensorClient.stop_monitoring()
    logging.info('Exiting...')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="sets the logging level to debug",
    )
    args = parser.parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s")
    main()
    