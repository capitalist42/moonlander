import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Session.js" as Session

// Moonlander chip. Click opens the layout editor.
BarWidget {
  id: root
  moduleName: "capitalist42.moonlander"

  property var session: Session.store()
  property string layoutTitle: session ? session.layoutTitle : ""
  property bool unflashed: session ? session.unflashed : false
  property bool connected: session ? session.connected : false

  readonly property string draftPath: Quickshell.env("HOME") + "/.config/omarchy/moonlander/layout.json"

  function script(name) {
    var url = Qt.resolvedUrl(name).toString()
    if (url.indexOf("file://") === 0) url = url.substring(7)
    return decodeURIComponent(url)
  }

  // The shell routes a bar click through this root. findPanelWidget ignores a
  // widget with no open/close/opened, and KeyboardPanel.close only reaches
  // the layout when the root itself implements close.
  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item) panelLoader.item.close()
  }

  function togglePanel() {
    if (panelLoader.item) panelLoader.item.toggle()
  }

  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
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

    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.togglePanel() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
  }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.layoutTitle !== "" ? root.layoutTitle : "Moonlander"
    tooltipText: root.connected
      ? (root.unflashed ? "Moonlander layout has unflashed edits" : "Moonlander layout")
      : "Moonlander is not connected"
    onPressed: function(b) {
      if (b === Qt.LeftButton) root.togglePanel()
    }

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
