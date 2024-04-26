import QtQuick 1.1
import com.victron.velib 1.0
import "utils.js" as Utils

MbPage {
	id: root
	property string bindPrefix
	default property alias content: vModel.children

	model: VisibleItemModel {
		id: vModel
		MbItemOptions {
			description: qsTr("Connected")
			bind: Utils.path(root.bindPrefix, "/Connected")
			readonly: true
			editable: false
			unknownOptionText: qsTr("No")
			possibleValues: [
				MbOption { description: qsTr("No"); value: 0 },
				MbOption { description: qsTr("Yes"); value: 1 }
			]
		}

		MbItemValue {
			description: qsTr("Connection")
			item {
				bind: Utils.path(root.bindPrefix, "/Mgmt/Connection")
				invalidate: false
			}
		}

//////// added for BLE Sensor Client
		MbSubMenu
		{
			description: qsTr("BLE Sensor Client")
			subpage: Component { PageBleSensorClient {} }
			property VBusItem stateItem: VBusItem { bind: Utils.path(root.bindPrefix, "/ProductName") }
			show: stateItem.value === "BLE Sensor Client"
		}

		MbItemValue {
			description: qsTr("Product")
			item {
				bind: Utils.path(root.bindPrefix, "/ProductName")
				invalidate: false
			}
		}

		MbEditBox {
			id: name
			description: qsTr("Name")
			item {
				bind: Utils.path(root.bindPrefix, "/CustomName")
				invalidate: false
			}
			readonly: item.state === VeQItem.Offline
			show: item.valid
			maximumLength: 32
			enableSpaceBar: true
		}

		MbItemValue {
			description: qsTr("Product ID")
			item {
				bind: Utils.path(root.bindPrefix, "/ProductId")
				invalidate: false
			}
		}

		MbItemValue {
			description: qsTr("Firmware version")
			item {
				bind: Utils.path(root.bindPrefix, "/FirmwareVersion")
				invalidate: false
			}
		}

		MbItemValue {
			description: qsTr("Hardware version")
			item {
				bind: Utils.path(root.bindPrefix, "/HardwareVersion")
				invalidate: false
			}
			show: item.valid
		}

		MbItemValue {
			description: qsTr("VRM instance")
			item {
				bind: Utils.path(root.bindPrefix, "/DeviceInstance")
				invalidate: false
			}
		}

		MbItemValue {
			description: qsTr("Serial number")
			item {
				bind: Utils.path(root.bindPrefix, "/Serial")
				invalidate: false
			}
			show: item.valid
		}

		MbItemValue {
			description: qsTr("Device name")
			item {
				bind: Utils.path(root.bindPrefix, "/DeviceName")
				invalidate: false
			}
			show: item.valid
		}
	}
}
