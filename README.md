# BLE Sensor Client for Venus OS

This project contains a service driver for the dbus in venus os. 
It registers a list of configured sensors as services on the dbus, connects to a Bluetooth Low Energy (BLE) server and retrieves sensor readings from it. The service currently supports temperature and tank sensors but more types are to be added.

The BLE server can for example be an ESP32 running the BLE Sensor Server code found here: [ESP32 BLE Sensor Server](https://github.com/johan-jernstrom/ESP32-BLESensorServer). But can easily be modified to run on something else.

The service automatically scan for the BLE Server and establish a connection at startup, and continue to update the service with sensor values from the server as long as connection is alive. If connection is lost, the program exits (after a short grace period) but should be restarted by the daemon service if correctly installed in venus os.

## Dependencies

This project uses the following Python libraries:
- bleak
- asyncio
- argparse
- logging
- dbus

plus some built in libraries, included in Venus Os:
- vedbus
- ve_utils 

## Installation

### Pre requisites

You need to setup some depenacies on your VenusOS first

1) SSH to IP assigned to venus device
1) Resize/Expand file system
    ```bash
    /opt/victronenergy/swupdate-scripts/resize2fs.sh
    ```
1) Update opkg
    ```bash
    opkg update
    ```
1) Install git
    ```bash
    opkg install git
    ```
1) Clone VenusOS-BLESensorClient repo<br/>
    ```bash
    cd /data/
    git clone https://github.com/johan-jernstrom/VenusOS-BLESensorClient.git
    cd VenusOS-BLESensorClient
    ```
1) Install pip
    ```bash
    opkg install python3-pip
    ```
1) Install all dependencies, eg:
    ```bash
    pip3 install bleak
    pip3 install asyncio
    ```
    **NOTE**: More dependencies might be required to be installed. Test my manually starting the program after install and verify it runs ok:
    ```bash
    python /data/VenusOS-BLESensorClient/blesensordbusservice.py
    ```

NOTE: Developed and tested on a Raspberry Pi 3B running Venus OS 3.14 LARGE

### Configuration

The target device name and the characteristics to listen for notifications are specified in the `blesensordbusservice.py` file. These will later be placed in a configuration file for easier management.

### Installing the service and UI

Executing the install script installes the service and the UI automatically.

```bash
bash install.sh
```

## Running the Client

After successful install, the driver will be run automatically after each boot by the daemon service by the Venus OS.

To run the client manually, type `python blesensordbusservice.py` in a shell. 
The client will start scanning for the device with the specified name and start retrieving sensor readings from it.

## Known issues

The bluetooth readings often fails with the following error:
```python
[org.bluez.Error.Failed] Operation failed with ATT error: 0x0e (Unlikely Error)
```

## Troubleshooting

Read logs using this command:
```bash
tail -f /var/log/VenusOS-BLESensorClient/current  | tai64nlocal
```

If not able to connect or reconnnect, power cycle the Bluetooth adapter using the following commands:

```bash
bluetoothctl power off
bluetoothctl power on
```

You can also use bluetoothctl to scan devices etc...
```bash
bluetoothctl help
```

## Future Improvements

- Move the list of sensors to a configuration file.
- Make compatible with Kwindrems SetupHelper to aid installation.