import QtQuick

// One layout for every monitor. The bar is built once per screen, and each
// screen would otherwise keep its own copy of the draft.
QtObject {
  property var doc: ({})
  property var layers: []
  property int layerIndex: 0
  property int targetLayer: 0
  property int selectedIndex: -1
  property string slotName: "tap"
  property string status: ""
  property string logText: ""
  property bool busy: false
  property bool matchesKeyboard: true
  property string keyboardSnapshot: ""
  property bool loadArmed: false
  property bool flashArmed: false
  property bool restoreArmed: false
  property int nameRevision: 0
  property bool draftSaveFailed: false
  property string layoutTitle: ""
  property bool unflashed: false
  property bool connected: false
}
