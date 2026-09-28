import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

// Layout currently on the Moonlander, plus the draft you are editing.
Panel {
  id: root
  moduleName: "capitalist42.moonlander"
  ipcTarget: ""
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null

  readonly property var barIdentity: hostWidget || root
  readonly property color contentForeground: bar ? bar.foreground : Color.foreground
  readonly property string contentFontFamily: bar ? bar.fontFamily : Style.font.family

  property var doc: ({})
  property var layers: []
  property int layerIndex: 0
  property int targetLayer: 0
  property int selectedIndex: -1
  property string slotName: "tap"
  property string filterText: ""
  property string status: ""
  property string logText: ""
  property bool busy: false
  property bool matchesKeyboard: true
  property string keyboardSnapshot: ""
  property bool loadArmed: false
  property bool flashArmed: false
  property bool restoreArmed: false
  property int nameRevision: 0

  readonly property bool unflashed: keyboardSnapshot === "" ? !matchesKeyboard : JSON.stringify(layers) !== keyboardSnapshot
  readonly property var filteredCodes: {
    var all = Model.catalog()
    var query = filterText.toLowerCase()
    var out = []
    var i
    for (i = 0; i < all.length && out.length < 16; i++) {
      if (query === "" || all[i].toLowerCase().indexOf(query) >= 0) out.push(all[i])
    }
    return out
  }
  readonly property var selectedKey: {
    var layer = layers && layerIndex >= 0 && layerIndex < layers.length ? layers[layerIndex] : null
    if (!layer || !layer.keys || selectedIndex < 0 || selectedIndex >= layer.keys.length) return null
    return layer.keys[selectedIndex]
  }

  onUnflashedChanged: {
    if (hostWidget) hostWidget.unflashed = unflashed
  }

  function open() {
    root.syncNameFields()
    root.controller.show()
  }

  function close() {
    root.controller.hide()
  }

  function toggle() {
    if (root.opened) root.close()
    else root.open()
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }

  function applyDocument(text) {
    var parsed
    try { parsed = JSON.parse(text) } catch (e) {
      root.status = "Could not read the layout."
      return
    }
    root.doc = parsed
    root.layers = parsed.layers ? Model.clone(parsed.layers) : []
    root.layerIndex = 0
    root.targetLayer = root.layers.length > 1 ? 1 : 0
    root.selectedIndex = -1
    root.matchesKeyboard = parsed.matchesKeyboard !== false
    root.keyboardSnapshot = root.matchesKeyboard ? JSON.stringify(root.layers) : ""
    root.loadArmed = false
    root.syncNameFields()
    if (hostWidget) {
      hostWidget.layoutTitle = parsed.title || "Moonlander"
      hostWidget.connected = !!parsed.connected
      hostWidget.unflashed = !root.matchesKeyboard
    }
    if (parsed.error) root.status = parsed.error
    else if (parsed.liveError && !parsed.matchesKeyboard) root.status = parsed.liveError
    else root.status = (parsed.title || "Layout") + "  " + (parsed.layoutId || "") + "/" + (parsed.revisionId || "")
  }

  function touch() {
    root.layers = Model.clone(root.layers)
    root.loadArmed = false
    root.flashArmed = false
  }

  function currentSlot() {
    var key = root.selectedKey
    if (!key) return null
    if (!key[root.slotName]) key[root.slotName] = { code: "", modifiers: {} }
    if (!key[root.slotName].modifiers) key[root.slotName].modifiers = {}
    return key[root.slotName]
  }

  function modOn(name) {
    var key = root.selectedKey
    if (!key || !key[root.slotName] || !key[root.slotName].modifiers) return false
    return !!key[root.slotName].modifiers[name]
  }

  function assignCode(code) {
    var slot = currentSlot()
    if (!slot) return
    slot.code = code
    if (code !== "MO" && code !== "TG" && code !== "TO" && code !== "TT" && code !== "OSL" && code !== "LT") slot.layer = null
    touch()
  }

  function assignLayerOp(op) {
    var slot = currentSlot()
    if (!slot) return
    if (root.targetLayer < 0 || root.targetLayer >= root.layers.length) {
      root.status = "Choose a target layer first."
      return
    }
    slot.code = op
    slot.layer = root.targetLayer
    touch()
  }

  function toggleMod(name) {
    var slot = currentSlot()
    if (!slot) return
    if (!slot.modifiers) slot.modifiers = {}
    slot.modifiers[name] = !slot.modifiers[name]
    touch()
  }

  function clearSlot() {
    var key = root.selectedKey
    if (!key) return
    key[root.slotName] = null
    touch()
  }

  function saveDraft() {
    if (!hostWidget) return
    var next = Model.clone(root.doc || {})
    next.layers = Model.clone(root.layers)
    next.matchesKeyboard = JSON.stringify(root.layers) === root.keyboardSnapshot && root.keyboardSnapshot !== ""
    draftFile.path = hostWidget.draftPath
    draftFile.setText(JSON.stringify(next, null, 2) + "\n")
    root.doc = next
    root.status = "Saved. The keyboard is unchanged until you flash."
  }

  function runTool(proc, args) {
    if (!hostWidget || root.busy) return
    root.busy = true
    root.logText = ""
    proc.command = ["python3", hostWidget.script("flash.py")].concat(args)
    proc.running = true
  }

  function compile() {
    saveDraft()
    root.status = "Compiling. The first build takes several minutes."
    runTool(compileProc, ["compile", "--draft", hostWidget.draftPath])
  }

  function requestFlash() {
    if (!root.flashArmed) {
      root.flashArmed = true
      root.restoreArmed = false
      root.status = "Flash overwrites the keyboard. Press Flash again, then the reset pinhole or the Reset key on layer 2."
      return
    }
    root.flashArmed = false
    saveDraft()
    root.status = "Waiting for the bootloader. Press the reset pinhole and leave the cable in."
    runTool(flashProc, ["flash", "--draft", hostWidget.draftPath, "--yes"])
  }

  function requestRestore() {
    if (!root.restoreArmed) {
      root.restoreArmed = true
      root.flashArmed = false
      root.status = "Restore puts revision Jal4PQ back on the board. Press Restore again, then the reset pinhole."
      return
    }
    root.restoreArmed = false
    root.status = "Waiting for the bootloader to restore Jal4PQ."
    runTool(restoreProc, ["restore", "--yes"])
  }

  function requestLoad() {
    if (!hostWidget) return
    if (root.unflashed && !root.loadArmed) {
      root.loadArmed = true
      root.status = "Load from keyboard discards unflashed edits. Press Load again."
      return
    }
    root.loadArmed = false
    loadProc.command = ["python3", hostWidget.script("read-layout.py"), "--draft", hostWidget.draftPath, "--force"]
    loadProc.running = true
  }

  function addLayer() {
    if (root.layers.length >= Model.MAX_LAYERS) {
      root.status = "Eight layers is the maximum for this firmware."
      return
    }
    var next = Model.clone(root.layers)
    var created = Model.blankLayer("Layer " + next.length)
    created.position = next.length
    next.push(created)
    root.layers = next
    root.layerIndex = next.length - 1
    root.syncNameFields()
  }

  function deleteLayer() {
    if (root.layerIndex <= 0) {
      root.status = "Layer 0 stays."
      return
    }
    var next = Model.clone(root.layers)
    next.splice(root.layerIndex, 1)
    root.layers = next
    root.layerIndex = Math.max(0, root.layerIndex - 1)
    if (root.targetLayer >= next.length) root.targetLayer = Math.max(0, next.length - 1)
    root.selectedIndex = -1
    root.syncNameFields()
  }

  function layerTitleAt(index) {
    var layer = root.layers && index >= 0 && index < root.layers.length ? root.layers[index] : null
    return layer && layer.title ? String(layer.title) : ""
  }

  function layerButtonLabel(index) {
    var unused = root.nameRevision
    return Model.layerLabel(root.layers[index], index)
  }

  // Copy names into the fields without a text binding. A binding that writes
  // back on editingFinished rebuilds the layer list, the field loses focus,
  // and editingFinished fires again.
  function syncNameFields() {
    if (!layoutNameEdit || !layerNameEdit) return
    layoutNameEdit.text = root.doc && root.doc.title ? String(root.doc.title) : ""
    layerNameEdit.text = layerTitleAt(root.layerIndex)
  }

  function commitLayerName(text) {
    if (root.layerIndex < 0 || root.layerIndex >= root.layers.length) return
    var name = String(text || "")
    if (layerTitleAt(root.layerIndex) === name) return
    root.layers[root.layerIndex].title = name
    root.nameRevision = root.nameRevision + 1
    root.loadArmed = false
    root.flashArmed = false
  }

  function commitLayoutName(text) {
    var name = String(text || "").replace(/^\s+|\s+$/g, "")
    if (name === "") name = "Moonlander"
    var current = root.doc && root.doc.title ? String(root.doc.title) : ""
    layoutNameEdit.text = name
    if (name === current) return
    var next = Model.clone(root.doc || {})
    next.title = name
    root.doc = next
    if (hostWidget) hostWidget.layoutTitle = name
    root.loadArmed = false
    root.flashArmed = false
    root.saveDraft()
  }

  FileView {
    id: draftFile
    path: hostWidget ? hostWidget.draftPath : ""
    watchChanges: false
    atomicWrites: true
    printErrors: false
  }

  Process {
    id: loadProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      root.applyDocument(loadProc.stdout.text || "")
    }
  }

  Process {
    id: compileProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      root.busy = false
      root.logText = ((compileProc.stdout.text || "") + (compileProc.stderr.text || "")).trim()
      root.status = code === 0 ? "Compile finished. Flash when you are ready." : "Compile failed."
    }
  }

  Process {
    id: flashProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      root.busy = false
      root.logText = ((flashProc.stdout.text || "") + (flashProc.stderr.text || "")).trim()
      if (code === 0) {
        var hashed = /flashedHash ([0-9a-f]{8})/.exec(root.logText)
        if (hashed) {
          var next = Model.clone(root.doc || {})
          next.flashedHash = hashed[1]
          next.matchesKeyboard = true
          root.doc = next
        }
        root.matchesKeyboard = true
        root.keyboardSnapshot = JSON.stringify(root.layers)
        if (hostWidget) hostWidget.unflashed = false
        root.status = "Flashed. The draft is now the record of what is on the keyboard."
      } else {
        root.status = "Flash failed."
      }
    }
  }

  Process {
    id: restoreProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      root.busy = false
      root.logText = ((restoreProc.stdout.text || "") + (restoreProc.stderr.text || "")).trim()
      root.status = code === 0 ? "Restored Jal4PQ. Load from keyboard to pick up the Oryx layout." : "Restore failed."
    }
  }

  function start() {
    if (!hostWidget || loadProc.running) return
    loadProc.command = ["python3", hostWidget.script("read-layout.py"), "--draft", hostWidget.draftPath]
    loadProc.running = true
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(780)
    contentHeight: panel.fittedContentHeight(Math.min(body.implicitHeight + Style.space(8), 720))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        anchors.fill: parent
        contentWidth: body.width
        contentHeight: body.implicitHeight
        clip: true

        Column {
          id: body
          width: panel.contentWidth - Style.space(16)
          x: Style.space(8)
          spacing: Style.space(8)

          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: root.status
            color: root.contentForeground
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.bodySmall
          }

          Row {
            spacing: Style.space(8)

            Text {
              text: "Layout name"
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
            }

            TextField {
              id: layoutNameEdit
              width: Style.space(220)
              placeholderText: "Layout name"
              foreground: root.contentForeground
              font.pixelSize: Style.font.caption
              onEditingFinished: root.commitLayoutName(text)
            }
          }

          Row {
            spacing: Style.space(4)
            Repeater {
              model: root.layers
              Button {
                required property var modelData
                required property int index
                text: root.layerButtonLabel(index)
                fontSize: Style.font.caption
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
                bordered: true
                active: root.layerIndex === index
                onClicked: {
                  root.layerIndex = index
                  root.selectedIndex = -1
                  root.syncNameFields()
                }
              }
            }
          }

          Row {
            spacing: Style.space(6)
            Button {
              text: "Add layer"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy
              onClicked: root.addLayer()
            }
            Button {
              text: "Delete layer"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy && root.layerIndex > 0
              onClicked: root.deleteLayer()
            }
            TextField {
              id: layerNameEdit
              width: Style.space(160)
              placeholderText: "Layer name"
              foreground: root.contentForeground
              font.pixelSize: Style.font.caption
              onEditingFinished: root.commitLayerName(text)
            }
          }

          Board {
            layers: root.layers
            layerIndex: root.layerIndex
            selectedIndex: root.selectedIndex
            foreground: root.contentForeground
            accent: Color.accent
            fontFamily: root.contentFontFamily
            onKeyClicked: function(index) { root.selectedIndex = index }
          }

          Column {
            visible: root.selectedKey !== null
            width: parent.width
            spacing: Style.space(4)

            Text {
              text: "Key " + root.selectedIndex + "  ·  editing " + root.slotName
              color: root.contentForeground
              font.family: root.contentFontFamily
              font.pixelSize: Style.font.caption
            }

            Row {
              spacing: Style.space(4)
              Repeater {
                model: ["tap", "hold", "doubleTap"]
                Button {
                  required property var modelData
                  text: modelData === "doubleTap" ? "double" : modelData
                  fontSize: Style.font.caption
                  foreground: root.contentForeground
                  fontFamily: root.contentFontFamily
                  bordered: true
                  active: root.slotName === modelData
                  onClicked: root.slotName = modelData
                }
              }
              Button {
                text: "Clear slot"
                fontSize: Style.font.caption
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
                bordered: true
                onClicked: root.clearSlot()
              }
            }

            Row {
              spacing: Style.space(4)

              Text {
                text: "To layer"
                color: root.contentForeground
                font.family: root.contentFontFamily
                font.pixelSize: Style.font.caption
                anchors.verticalCenter: parent.verticalCenter
              }

              Repeater {
                model: root.layers
                Button {
                  required property int index
                  text: String(index)
                  fontSize: Style.font.caption
                  foreground: root.contentForeground
                  fontFamily: root.contentFontFamily
                  bordered: true
                  active: root.targetLayer === index
                  onClicked: root.targetLayer = index
                }
              }
            }

            Flow {
              width: parent.width
              spacing: Style.space(4)
              Repeater {
                model: [
                  ["MO", "Hold"],
                  ["TG", "Toggle"],
                  ["TO", "Switch"],
                  ["TT", "Tap toggle"],
                  ["OSL", "One shot"],
                  ["LT", "Layer tap"]
                ]
                Button {
                  required property var modelData
                  text: modelData[1] + " " + root.targetLayer
                  fontSize: Style.font.caption
                  foreground: root.contentForeground
                  fontFamily: root.contentFontFamily
                  bordered: true
                  onClicked: root.assignLayerOp(modelData[0])
                }
              }
            }

            TextField {
              id: filterField
              width: Style.space(220)
              placeholderText: "Filter keycodes"
              foreground: root.contentForeground
              font.pixelSize: Style.font.caption
              onTextChanged: root.filterText = text
            }

            Flow {
              width: parent.width
              spacing: Style.space(4)
              Repeater {
                model: root.filteredCodes
                Button {
                  required property var modelData
                  text: Model.slotText({ code: modelData }) || modelData
                  fontSize: Style.font.caption
                  foreground: root.contentForeground
                  fontFamily: root.contentFontFamily
                  bordered: true
                  onClicked: root.assignCode(modelData)
                }
              }
            }

            Flow {
              width: parent.width
              spacing: Style.space(4)
              Repeater {
                model: [
                  ["leftCtrl", "Ctrl"], ["rightCtrl", "RCtrl"],
                  ["leftShift", "Shift"], ["rightShift", "RShift"],
                  ["leftAlt", "Alt"], ["rightAlt", "RAlt"],
                  ["leftGui", "Super"], ["rightGui", "RSuper"]
                ]
                Button {
                  required property var modelData
                  text: modelData[1]
                  fontSize: Style.font.caption
                  foreground: root.contentForeground
                  fontFamily: root.contentFontFamily
                  bordered: true
                  active: root.modOn(modelData[0])
                  onClicked: root.toggleMod(modelData[0])
                }
              }
            }
          }

          Row {
            spacing: Style.space(6)
            Button {
              text: root.loadArmed ? "Load anyway" : "Load from keyboard"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy
              onClicked: root.requestLoad()
            }
            Button {
              text: "Save"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy
              onClicked: root.saveDraft()
            }
            Button {
              text: root.busy ? "Working" : "Compile"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy
              onClicked: root.compile()
            }
            Button {
              text: root.flashArmed ? "Flash now" : "Flash"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy
              onClicked: root.requestFlash()
            }
            Button {
              text: root.restoreArmed ? "Restore now" : "Restore Jal4PQ"
              fontSize: Style.font.caption
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              bordered: true
              enabled: !root.busy
              onClicked: root.requestRestore()
            }
          }

          Text {
            width: parent.width
            visible: root.logText !== ""
            wrapMode: Text.Wrap
            maximumLineCount: 12
            elide: Text.ElideRight
            text: root.logText
            color: Qt.rgba(root.contentForeground.r, root.contentForeground.g, root.contentForeground.b, 0.75)
            font.family: root.contentFontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }
}
