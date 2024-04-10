#!/usr/bin/env python3

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
import subprocess
import sys
import os
from subprocess import check_call
import time
import struct
import signal
from os import _exit as os_exit
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop
import dbus
import dbus.service
from blesensorclient import BLESensorClient

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
                    "BLE_Char_UUID": "1e424618-a1f2-4a35-a6c3-3b65997badbe",
                    "Type": "temperature",
                    "DeviceInstance": 1300,
                    "Paths":
                        {
                            '/Temperature': {'initial': 0},
                            '/TemperatureType' : {'initial': 0},
                            '/CustomName': {'initial': 'Temp inne'},
                        }
                },
                {
                    "BLE_Char_UUID": "d167981d-6a98-4be3-adf9-d90a0dfc56b7",
                    "Type": "tank",
                    "DeviceInstance": 2301,
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

class Sensor:
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

        GLib.timeout_add(2000, exit_on_error, self._update)    # Update the dbus every 2 seconds
        
        logging.info("Service %s started" % self._servicename)

    def _update(self):
        try:
            type = self._metadata["Type"]
            if type == "temperature":
                update_sensor_data(self, "/Temperature")
                return True # always return True to keep the timeout running
            elif type == "tank":
                if update_sensor_data(self, "/Level"):
                    remaining = round(self._metadata["Paths"]["/Capacity"]["initial"] * (self._dbusservice["/Level"] / 100), 6) # calculate remaining volume based on level and capacity, round to 6 decimals since it is in m3
                    self._dbusservice["/Remaining"] = remaining
                    logging.debug("Updated %s%s to %s" % (self._servicename, "/Remaining", remaining))   
                return True # always return True to keep the timeout running
            else:
                logging.error("Unknown sensor type: %s" % type)
        except Exception as e:
            logging.error("Error updating sensor: %s", e)
        return True # always return True to keep the timeout running

    def _handlechangedvalue(self, path, value):
        logging.info("Someone else updated %s to %s" % (path, value))
        return True # accept the change

def update_sensor_data(sensor, path):
    if not sensor._bleclient.is_connected():
        logging.debug("Not connected, skipping update of %s%s" % (sensor._servicename, path))
        return False    # try again later
    metadata = sensor._metadata
    data = sensor._bleclient.read_characteristic(metadata["BLE_Char_UUID"])
    if data is None:
        return False # try again later
    logging.debug("Read characteristic (%s) value: %r", metadata["BLE_Char_UUID"], data)
    if len(data) >= 8:  # Ensure data has at least 8 bytes
        double_value = struct.unpack('d', data)[0]
        value = round(double_value, 1)
    else:
        value = int.from_bytes(data, byteorder='little')
    sensor._dbusservice[path] = value
    logging.debug("Updated %s%s to %s" % (sensor._servicename, path, sensor._dbusservice[path]))
    return True

def ensure_connection(bleClient, clientservice):
    if clientservice.dbusSettings['Enabled'] == 0:
        logging.debug("Service is disabled, skipping connection attempt")
        return True     # return True to keep the timeout running
    
    if bleClient is None:
        raise Exception("Client is None. Exiting...")  # An exception will stop the program, waiting for it to be restarted by the daemon supervisor

    logging.debug("Ensuring connection to device")
    if not bleClient.ensure_connected():
        duration = clientservice._dbusservice['/ConnectedFor']
        logging.warning("Lost connection to device after %s. Toggling Bluetooth off and on to reset connection", duration)
        subprocess.run('bluetoothctl power off', shell=True, check=True)
        # check_call("bluetoothctl power off")
        time.sleep(2)
        # check_call("bluetoothctl power on")
        subprocess.run('bluetoothctl power on', shell=True, check=True)
        time.sleep(2)
        logging.info("Ensuring connection to device after Bluetooth reset")
        if not bleClient.ensure_connected():
            logging.error("Could not connect to device after Bluetooth reset. Exiting in 1 minute...")
            time.sleep(1*60) # wait 1 minute before exiting to avoid restarting the program too quickly
            raise Exception("Could not connect to device")  # Stop the program, will be restarted by the daemon supervisor
    
    return True    # return True to keep the timeout running

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

        GLib.timeout_add(1000, exit_on_error, self._update_state)    # Update the dbus every 1 seconds

        logging.info("Service %s started" % self._servicename)

    def _handle_enabled_changed(self, setting, old, new):
        logging.info("Enabled changed from %s to %s" % (old, new))
        if new == 0:
            self._bleclient.disconnect()
        else:
            ensure_connection(self._bleclient, self)
        return True # accept the change
    
    def _update_state(self):
        logging.debug("Updating state of the Client DbusService")
        self._dbusservice['/State'] = 'Connected' if self._bleclient.is_connected() else 'Not connected'
        duration = self._bleclient.connected_for()
        if duration is not None:
            self._dbusservice['/ConnectedFor'] = str(duration).split('.')[0]
        return True

def main():
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)
    mainloop = GLib.MainLoop()
    bleClient = BLESensorClient(target_device_name)

    # Handle signals to ensure cleanup of the client
    def cleanup(signum, frame):
        try:
            logging.info('Signal handler called with signal %s', signum)
            if bleClient is not None:
                logging.info('Disconnecting client...')
                bleClient.disconnect()
            mainloop.quit()
        except Exception as e:
            logging.error('Error in signal handler: %s', e)
        finally:
            os_exit(1)  # exit the program with error code 1. sys.exit() is not used, since that throws an exception, which does not lead to a program halt when used in a dbus callback, see connection.py in the Python/Dbus libraries, line 230.
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Create the client service that will be used in the UI to monitor the client
    clientservice = ClientDbusService(bleClient)

    # Connect to the BLE server
    ensure_connection(bleClient, clientservice)    

    # Watchdog to ensure the client is connected
    GLib.timeout_add(10000, exit_on_error, ensure_connection, bleClient, clientservice)    # ensure the client is connected every 10 seconds, exit on error

    for sensor in sensors:
        Sensor(sensor, bleClient)

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop.run()
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
    