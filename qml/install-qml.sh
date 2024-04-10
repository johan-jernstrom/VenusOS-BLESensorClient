#!/bin/bash

# backup old PageDeviceInfo.qml once. New firmware upgrade will remove the backup
if [ ! -f /opt/victronenergy/gui/qml/PageDeviceInfo.qml.backup ]; then
    cp /opt/victronenergy/gui/qml/PageDeviceInfo.qml /opt/victronenergy/gui/qml/PageDeviceInfo.qml.backup
fi

# copy new pages
cp PageBleSensorClient.qml /opt/victronenergy/gui/qml/

# copy altered PageDeviceInfo.qml
cp PageDeviceInfo.qml /opt/victronenergy/gui/qml/

# restart gui
svc -t /service/gui