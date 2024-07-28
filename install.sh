#!/bin/sh

Echo "Installing dependencies"
opkg install python3-pip
pip3 install bleak
pip3 install asyncio
pip3 install argparse
Echo "Dependencies installed"

# set permissions
chmod -R 777 /data/VenusOS-BLESensorClient/

# create a symlink to the service directory to make it start automatically by the daemon manager
ln -s /data/VenusOS-BLESensorClient/service/ /opt/victronenergy/service/VenusOS-BLESensorClient
ln -s /data/VenusOS-BLESensorClient/service/ /service/VenusOS-BLESensorClient
Echo "Service symlink created"

# backup old PageDeviceInfo.qml once. New firmware upgrade will remove the backup
if [ ! -f /opt/victronenergy/gui/qml/PageDeviceInfo.qml.backup ]; then
    cp /opt/victronenergy/gui/qml/PageDeviceInfo.qml /opt/victronenergy/gui/qml/PageDeviceInfo.qml.backup
    Echo "Backup of PageDeviceInfo.qml created"
fi

# copy new pages
cp qml/PageBleSensorClient.qml /opt/victronenergy/gui/qml/
# copy altered PageDeviceInfo.qml
cp qml/PageDeviceInfo.qml /opt/victronenergy/gui/qml/
Echo "Copied new pages"

# restart gui
svc -t /service/gui
Echo "GUI restarted"

# start service
svc -t /service/VenusOS-BLESensorClient
Echo "Service started"
