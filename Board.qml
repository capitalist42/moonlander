import QtQuick
import qs.Commons
import "Model.js" as Model

// Moonlander shape: a columnar keywell, and a turned thumb cluster on each
// half with a wide red key over three tall piano keys. Click a key to select it.
Item {
  id: root

  property var layers: []
  property int layerIndex: 0
  property int selectedIndex: -1
  property color foreground: Color.foreground
  property color accent: Color.accent
  property string fontFamily: Style.font.family

  signal keyClicked(int index)

  readonly property real unit: width > 0 ? width / Model.BOARD_WIDTH : 0
  readonly property real keyGap: Math.max(1, unit * 0.08)

  width: parent ? parent.width : 0
  implicitHeight: unit * Model.BOARD_HEIGHT

  readonly property var layerKeys: {
    var layer = layers && layers.length > layerIndex ? layers[layerIndex] : null
    return layer && layer.keys ? layer.keys : []
  }

  Repeater {
    model: Model.KEYS

    delegate: Item {
      id: key
      required property var modelData

      x: modelData.x * root.unit
      y: modelData.y * root.unit
      width: modelData.w * root.unit
      height: modelData.h * root.unit

      transform: Rotation {
        angle: modelData.r || 0
        origin.x: (modelData.ox - modelData.x) * root.unit
        origin.y: (modelData.oy - modelData.y) * root.unit
      }

      readonly property int index: modelData.index
      readonly property bool launch: modelData.shape === "launch"
      readonly property bool selected: index === root.selectedIndex
      readonly property color fill: selected
        ? Style.selectionFillFor(root.foreground, root.accent)
        : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.08)
      readonly property color stroke: Qt.rgba(
        root.foreground.r, root.foreground.g, root.foreground.b,
        selected ? 0.9 : 0.25)
      readonly property var legend: {
        var keys = root.layerKeys
        if (!keys || index < 0 || index >= keys.length) return { main: "", sub: "" }
        return Model.legend(keys[index])
      }

      Rectangle {
        visible: !key.launch
        anchors.fill: parent
        anchors.margins: root.keyGap / 2
        radius: Math.min(Style.space(4), height / 4)
        color: key.fill
        border.width: 1
        border.color: key.stroke
      }

      Canvas {
        id: house
        visible: key.launch
        anchors.fill: parent
        anchors.margins: root.keyGap / 2
        onPaint: {
          var ctx = getContext("2d")
          ctx.clearRect(0, 0, width, height)
          var w = width
          var h = height
          if (w < 2 || h < 2) return
          ctx.beginPath()
          ctx.moveTo(w * 0.5, h * 0.04)
          ctx.lineTo(w * 0.96, h * 0.34)
          ctx.lineTo(w * 0.96, h * 0.9)
          ctx.quadraticCurveTo(w * 0.96, h * 0.98, w * 0.88, h * 0.98)
          ctx.lineTo(w * 0.12, h * 0.98)
          ctx.quadraticCurveTo(w * 0.04, h * 0.98, w * 0.04, h * 0.9)
          ctx.lineTo(w * 0.04, h * 0.34)
          ctx.closePath()
          ctx.fillStyle = key.fill
          ctx.strokeStyle = key.stroke
          ctx.lineWidth = 1
          ctx.fill()
          ctx.stroke()
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onVisibleChanged: requestPaint()
        Connections {
          target: key
          function onFillChanged() { house.requestPaint() }
          function onStrokeChanged() { house.requestPaint() }
        }
      }

      Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: key.launch ? parent.height * 0.12 : 0
        width: parent.width - root.keyGap
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
