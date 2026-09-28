import QtQuick
import qs.Commons
import "Model.js" as Model

// Two halves of a Moonlander. Click a key to select it.
Column {
  id: root

  property var layers: []
  property int layerIndex: 0
  property int selectedIndex: -1
  property color foreground: Color.foreground
  property color accent: Color.accent
  property string fontFamily: Style.font.family

  signal keyClicked(int index)

  spacing: Style.space(4)

  readonly property var layerKeys: {
    var layer = layers && layers.length > layerIndex ? layers[layerIndex] : null
    return layer && layer.keys ? layer.keys : []
  }

  Repeater {
    model: Model.ROWS

    Row {
      id: row
      required property var modelData
      spacing: Style.space(10)

      Row {
        spacing: Style.space(2)
        Repeater {
          model: row.modelData.left
          delegate: keyDelegate
        }
      }

      Row {
        spacing: Style.space(2)
        Repeater {
          model: row.modelData.right
          delegate: keyDelegate
        }
      }
    }
  }

  Component {
    id: keyDelegate
    Rectangle {
      id: key
      required property var modelData
      width: Style.space(46)
      height: Style.space(34)
      radius: Style.space(4)
      color: key.index === root.selectedIndex
        ? Style.selectionFillFor(root.foreground, root.accent)
        : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.08)
      border.width: 1
      border.color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, key.index === root.selectedIndex ? 0.9 : 0.25)

      readonly property int index: modelData
      readonly property var legend: {
        var keys = root.layerKeys
        if (!keys || index < 0 || index >= keys.length) return { main: "", sub: "" }
        return Model.legend(keys[index])
      }

      Column {
        anchors.centerIn: parent
        width: parent.width - Style.space(4)
        spacing: 0

        Text {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          elide: Text.ElideRight
          text: key.legend.main
          color: root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        Text {
          width: parent.width
          horizontalAlignment: Text.AlignHCenter
          elide: Text.ElideRight
          visible: key.legend.sub !== ""
          text: key.legend.sub
          color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.7)
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption - 1
        }
      }

      MouseArea {
        anchors.fill: parent
        onClicked: root.keyClicked(key.index)
      }
    }
  }
}
