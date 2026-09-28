import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Moonlander chip. Click opens the layout editor.
BarWidget {
  id: root
  moduleName: "capitalist42.moonlander"

  property string layoutTitle: ""
  property bool unflashed: false
  property bool connected: false

  readonly property string draftPath: Quickshell.env("HOME") + "/.config/omarchy/moonlander/layout.json"

  function script(name) {
    var url = Qt.resolvedUrl(name).toString()
    if (url.indexOf("file://") === 0) url = url.substring(7)
    return decodeURIComponent(url)
  }

  function togglePanel() {
    if (panelLoader.item) panelLoader.item.toggle()
  }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
      if (panelLoader.item && panelLoader.item.start) panelLoader.item.start()
    }
  }

  IpcHandler {
    target: "capitalist42.moonlander"

    function open(): void { if (panelLoader.item) panelLoader.item.open() }
    function close(): void { if (panelLoader.item) panelLoader.item.close() }
    function toggle(): void { root.togglePanel() }
    function show(): void { if (panelLoader.item) panelLoader.item.open() }
    function hide(): void { if (panelLoader.item) panelLoader.item.close() }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.layoutTitle !== "" ? root.layoutTitle : "Moonlander"
    tooltipText: root.connected
      ? (root.unflashed ? "Moonlander layout has unflashed edits" : "Moonlander layout")
      : "Moonlander is not connected"
    onPressed: function(b) { root.togglePanel() }

    Rectangle {
      visible: root.unflashed
      width: Style.space(6)
      height: Style.space(6)
      radius: width / 2
      color: root.bar ? root.bar.foreground : Color.foreground
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: Style.space(3)
    }
  }
}
