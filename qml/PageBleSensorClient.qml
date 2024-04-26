import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage
{
	id: root
	title: qsTr("Bluetooth Sensor Client")
    model: VisibleItemModel
    {
		MbSwitch
        {
            name: qsTr("Enabled")
            bind: Utils.path("com.victronenergy.settings", "/Settings/BLESensorClient/Enabled")
            writeAccessLevel: User.AccessUser
        }

		MbItemValue {
			description: qsTr("State")
			item.bind: Utils.path("com.victronenergy.BLESensorClient", "/State")
		}

		MbItemValue {
			description: qsTr("Connected for")
			property VBusItem stateItem: VBusItem { bind: Utils.path("com.victronenergy.BLESensorClient", "/ConnectedFor") }
			item.bind: Utils.path("com.victronenergy.BLESensorClient", "/ConnectedFor")
			show: stateItem.value != "-"
		}

		MbItemValue {
			description: qsTr("Number of sensors")
			item.bind: Utils.path("com.victronenergy.BLESensorClient", "/NumberOfSensors")
		}
    }
}