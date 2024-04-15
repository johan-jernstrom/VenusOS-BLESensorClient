#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import asyncio
import logging
import time
from sensorbleclient import SensorBLEClient

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

def main():
    
    logging.info("__________Starting__________")

    sensorClient = SensorBLEClient(target_device_name, [sensor["BLE_Char_UUID"] for sensor in sensors], asyncio.get_event_loop())
    sensorClient.start_monitoring()

    logging.info("_______Starting Test1_______")
    start1 = time.time()
    try:
        while True:
            time.sleep(2)
            for sensor in sensors:
                data = sensorClient.get_characteristic_value(sensor["BLE_Char_UUID"])
                if data is None:
                    logging.info("Read characteristic (%s) value: NONE", sensor["BLE_Char_UUID"])
                else:
                    logging.info("Read characteristic (%s) value: %r", sensor["BLE_Char_UUID"], data)
    except Exception as e:
        logging.error("Error: %s", e)
    logging.info("Test1 took %s hours, %s minutes, %s seconds", time.strftime("%H", time.gmtime(time.time()-start1)), time.strftime("%M", time.gmtime(time.time()-start1)), time.strftime("%S", time.gmtime(time.time()-start1)))

    # # do 10 times
    # for i in range(10):
    #     try:
    #         logging.info("_______Starting Test1_______")
    #         start1 = time.time()
    #         while True :
    #             for sensor in sensors:
    #                 data = bleClient.get_characteristic_value(sensor["BLE_Char_UUID"])
    #                 if data is None:
    #                     raise Exception("Could not read characteristic")
    #                 logging.debug("Read characteristic (%s) value: %r", sensor["BLE_Char_UUID"], data)
    #                 time.sleep(1)
    #     except Exception as e:
    #         logging.error("Error: %s", e)
    #     logging.info("Test1 took %s hours, %s minutes, %s seconds", time.strftime("%H", time.gmtime(time.time()-start1)), time.strftime("%M", time.gmtime(time.time()-start1)), time.strftime("%S", time.gmtime(time.time()-start1)))


    #     try:
    #         logging.info("_______Starting Test2_______")
    #         start2 = time.time()
    #         ensure_connection(bleClient)    
    #         sensor = sensors[0]
    #         while True :
    #             # for sensor in sensors:
    #             data = bleClient.get_characteristic_value(sensor["BLE_Char_UUID"])
    #             if data is None:
    #                 raise Exception("Could not read characteristic")
    #             logging.debug("Read characteristic (%s) value: %r", sensor["BLE_Char_UUID"], data)
    #             time.sleep(15)
    #     except Exception as e:
    #         logging.error("Error: %s", e)
    #     logging.info("Test2 took %s hours, %s minutes, %s seconds", time.strftime("%H", time.gmtime(time.time()-start2)), time.strftime("%M", time.gmtime(time.time()-start2)), time.strftime("%S", time.gmtime(time.time()-start2)))





    logging.info("__________Ending__________")

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