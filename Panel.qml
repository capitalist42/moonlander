import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model
import "Session.js" as Session

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

  property var session: Session.store()

  // These read the shared session. Writes go to session so the other screen
  // sees them; assigning here would keep a private copy.
  readonly property var doc: session ? session.doc : ({})
  readonly property var layers: session ? session.layers : []
  readonly property int layerIndex: session ? session.layerIndex : 0
  readonly property int targetLayer: session ? session.targetLayer : 0
  readonly property int selectedIndex: session ? session.selectedIndex : -1
  readonly property string slotName: session ? session.slotName : "tap"
  readonly property string status: session ? session.status : ""
  readonly property string logText: session ? session.logText : ""
  readonly property bool busy: session ? session.busy : false
  readonly property bool matchesKeyboard: session ? session.matchesKeyboard : true
  readonly property string keyboardSnapshot: session ? session.keyboardSnapshot : ""
  readonly property bool loadArmed: session ? session.loadArmed : false
  readonly property bool flashArmed: session ? session.flashArmed : false
  readonly property bool restoreArmed: session ? session.restoreArmed : false
  readonly property int nameRevision: session ? session.nameRevision : 0
  readonly property bool draftSaveFailed: session ? session.draftSaveFailed : false

  readonly property bool unflashed: keyboardSnapshot === "" ? !matchesKeyboard : JSON.stringify(layers) !== keyboardSnapshot
  readonly property var characterOptions: Model.pickerOptions("Character")
  readonly property var numberOptions: Model.pickerOptions("Number")
  readonly property var symbolOptions: Model.pickerOptions("Symbol")
  readonly property var keyOptions: Model.pickerOptions("Key")
  readonly property var selectedKey: {
    var layer = layers && layerIndex >= 0 && layerIndex < layers.length ? layers[layerIndex] : null
    if (!layer || !layer.keys || selectedIndex < 0 || selectedIndex >= layer.keys.length) return null
    return layer.keys[selectedIndex]
  }

  onUnflashedChanged: {
    if (session) session.unflashed = unflashed
  }

  Connections {
    target: root.session
    function onDocChanged() { root.syncNameFields() }
    function onLayerIndexChanged() { root.syncNameFields() }
    function onNameRevisionChanged() { root.syncNameFields() }
  }

  onSelectedIndexChanged: root.syncPickers()
  onSlotNameChanged: root.syncPickers()
  onLayerIndexChanged: root.syncPickers()

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
      session.status = "Could not read the layout."
      return
    }
    session.doc = parsed
    session.layers = parsed.layers ? Model.clone(parsed.layers) : []
    session.layerIndex = 0
    session.targetLayer = session.layers.length > 1 ? 1 : 0
    session.selectedIndex = -1
    session.matchesKeyboard = parsed.matchesKeyboard !== false
    session.keyboardSnapshot = session.matchesKeyboard ? JSON.stringify(session.layers) : ""
    session.loadArmed = false
    var title = parsed.title || "Moonlander"
    session.layoutTitle = title
    session.connected = !!parsed.connected
    root.syncNameFields()
    if (parsed.error) session.status = parsed.error
    else if (parsed.liveError && !parsed.matchesKeyboard) session.status = parsed.liveError
    else session.status = (parsed.title || "Layout") + "  " + (parsed.layoutId || "") + "/" + (parsed.revisionId || "")
    root.syncPickers()
  }

  function collapsePickers(keep) {
    if (characterPicker !== keep) characterPicker.expanded = false
    if (numberPicker !== keep) numberPicker.expanded = false
    if (symbolPicker !== keep) symbolPicker.expanded = false
    if (keyPicker !== keep) keyPicker.expanded = false
  }

  function syncPickers() {
    if (!characterPicker) return
    var layer = root.layers && root.layerIndex >= 0 && root.layerIndex < root.layers.length ? root.layers[root.layerIndex] : null
    var key = layer && layer.keys && root.selectedIndex >= 0 && root.selectedIndex < layer.keys.length ? layer.keys[root.selectedIndex] : null
    var slot = key ? key[root.slotName] : null
    var code = slot && slot.code ? String(slot.code) : ""
    var group = Model.groupOf(code)
    characterPicker.value = group === "Character" ? code : ""
    numberPicker.value = group === "Number" ? code : ""
    symbolPicker.value = group === "Symbol" ? code : ""
    keyPicker.value = group === "Key" ? code : ""
  }

  function touch() {
    session.layers = Model.clone(root.layers)
    session.loadArmed = false
    session.flashArmed = false
  }

  function modOn(name) {
    var key = root.selectedKey
    if (!key || !key[root.slotName] || !key[root.slotName].modifiers) return false
    return !!key[root.slotName].modifiers[name]
  }

  function writeSlot(patch) {
    if (!session || root.selectedIndex < 0) return false
    var next = Model.assignSlot(root.layers, root.layerIndex, root.selectedIndex, root.slotName, patch)
    if (next === root.layers) return false
    session.layers = next
    session.loadArmed = false
    session.flashArmed = false
    return true
  }

  function assignCode(code) {
    var patch = { code: code }
    if (code !== "MO" && code !== "TG" && code !== "TO" && code !== "TT" && code !== "OSL" && code !== "LT") patch.layer = null
    if (!writeSlot(patch)) return
    root.syncPickers()
  }

  function assignLayerOp(op) {
    var layerNumber = session ? session.targetLayer : 0
    if (layerNumber < 0 || layerNumber >= root.layers.length) {
      session.status = "Choose a target layer first."
      return
    }
    if (!writeSlot({ code: op, layer: layerNumber })) return
    root.syncPickers()
  }

  function toggleMod(name) {
    var key = root.selectedKey
    var slot = key && key[root.slotName]
    var flags = {}
    flags[name] = !(slot && slot.modifiers && slot.modifiers[name])
    writeSlot({ modifiers: flags })
  }

  function clearSlot() {
    if (root.selectedIndex < 0) return
    session.layers = Model.clearKey(root.layers, root.layerIndex, root.selectedIndex)
    touch()
    root.syncPickers()
  }

  function writeDraft() {
    if (!hostWidget) return false
    var next = Model.clone(root.doc || {})
    next.layers = Model.clone(root.layers)
    next.matchesKeyboard = JSON.stringify(root.layers) === root.keyboardSnapshot && root.keyboardSnapshot !== ""
    // A failed write leaves the new text in FileView's cache, and setText
    // then skips the write. Clear the path so the retry is a real save.
    if (root.draftSaveFailed) draftFile.path = ""
    session.draftSaveFailed = false
    draftFile.path = hostWidget.draftPath
    draftFile.setText(JSON.stringify(next, null, 2) + "\n")
    draftFile.waitForJob()
    if (root.draftSaveFailed) return false
    session.doc = next
    return true
  }

  function saveDraft() {
    if (!writeDraft()) {
      if (hostWidget) session.status = "Could not save the draft."
      return
    }
    session.status = "Saved. The keyboard is unchanged until you flash."
  }

  function runTool(proc, args) {
    if (!hostWidget || root.busy) return
    session.busy = true
    session.logText = ""
    proc.command = ["python3", hostWidget.script("flash.py")].concat(args)
    proc.running = true
  }

  function compile() {
    if (!hostWidget || root.busy) return
    if (!writeDraft()) {
      session.status = "Could not save the draft."
      return
    }
    session.status = "Compiling. The first build takes several minutes."
    runTool(compileProc, ["compile", "--draft", hostWidget.draftPath])
  }

  function requestFlash() {
    if (!root.flashArmed) {
      session.flashArmed = true
      session.restoreArmed = false
      session.status = "Flash overwrites the keyboard. Press Flash again, then the reset pinhole or the Reset key on layer 2."
      return
    }
    session.flashArmed = false
    if (!writeDraft()) {
      session.status = "Could not save the draft."
      return
    }
    session.status = "Waiting for the bootloader. Press the reset pinhole and leave the cable in."
    runTool(flashProc, ["flash", "--draft", hostWidget.draftPath, "--yes"])
  }

  function requestRestore() {
    if (!root.restoreArmed) {
      session.restoreArmed = true
      session.flashArmed = false
      session.status = "Restore puts revision Jal4PQ back on the board. Press Restore again, then the reset pinhole."
      return
    }
    session.restoreArmed = false
    session.status = "Waiting for the bootloader to restore Jal4PQ."
    runTool(restoreProc, ["restore", "--yes"])
  }

  function requestLoad() {
    if (!hostWidget) return
    if (root.unflashed && !root.loadArmed) {
      session.loadArmed = true
      session.status = "Load from keyboard discards unflashed edits. Press Load again."
      return
    }
    session.loadArmed = false
    loadProc.command = ["python3", hostWidget.script("read-layout.py"), "--draft", hostWidget.draftPath, "--force"]
    loadProc.running = true
  }

  function addLayer() {
    if (root.layers.length >= Model.MAX_LAYERS) {
      session.status = "Eight layers is the maximum for this firmware."
      return
    }
    var next = Model.clone(root.layers)
    var created = Model.blankLayer("Layer " + next.length)
    created.position = next.length
    next.push(created)
    session.layers = next
    session.layerIndex = next.length - 1
    root.syncNameFields()
  }

  function deleteLayer() {
    if (root.layerIndex <= 0) {
      session.status = "Layer 0 stays."
      return
    }
    var removed = root.layerIndex
    var next = Model.removeLayer(root.layers, removed)
    session.layers = next
    session.layerIndex = Math.max(0, removed - 1)
    if (session.targetLayer === removed) session.targetLayer = Math.max(0, next.length - 1)
    else if (root.targetLayer > removed) session.targetLayer = root.targetLayer - 1
    session.selectedIndex = -1
    session.loadArmed = false
    session.flashArmed = false
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
    var layers = Model.clone(root.layers)
    layers[root.layerIndex].title = name
    session.layers = layers
    session.nameRevision = root.nameRevision + 1
    session.loadArmed = false
    session.flashArmed = false
    root.saveDraft()
  }

  function commitLayoutName(text) {
    var name = String(text || "").replace(/^\s+|\s+$/g, "")
    if (name === "") name = "Moonlander"
    var current = root.doc && root.doc.title ? String(root.doc.title) : ""
    layoutNameEdit.text = name
    if (name === current) return
    var next = Model.clone(root.doc || {})
    next.title = name
    session.doc = next
    session.layoutTitle = name
    session.loadArmed = false
    session.flashArmed = false
    root.saveDraft()
  }

  FileView {
    id: draftFile
    path: hostWidget ? hostWidget.draftPath : ""
    watchChanges: false
    atomicWrites: true
    printErrors: false
    onSaveFailed: function() { session.draftSaveFailed = true }
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
      session.busy = false
      session.logText = ((compileProc.stdout.text || "") + (compileProc.stderr.text || "")).trim()
      session.status = code === 0 ? "Compile finished. Flash when you are ready." : "Compile failed."
    }
  }

  Process {
    id: flashProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      session.busy = false
      session.logText = ((flashProc.stdout.text || "") + (flashProc.stderr.text || "")).trim()
      if (code === 0) {
        var hashed = /flashedHash ([0-9a-f]{8})/.exec(root.logText)
        if (hashed) {
          var next = Model.clone(root.doc || {})
          next.flashedHash = hashed[1]
          next.matchesKeyboard = true
          session.doc = next
        }
        session.matchesKeyboard = true
        session.keyboardSnapshot = JSON.stringify(root.layers)
        session.unflashed = false
        session.status = "Flashed. The draft is now the record of what is on the keyboard."
      } else {
        session.status = "Flash failed."
      }
    }
  }

  Process {
    id: restoreProc
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      session.busy = false
      session.logText = ((restoreProc.stdout.text || "") + (restoreProc.stderr.text || "")).trim()
      session.status = code === 0 ? "Restored Jal4PQ. Load from keyboard to pick up the Oryx layout." : "Restore failed."
    }
  }

  function start() {
    if (!hostWidget) return
    root.syncNameFields()
    if (loadProc.running || !Session.claimLoad()) return
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
      blocked: characterPicker.editing || numberPicker.editing || symbolPicker.editing || keyPicker.editing

      Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: body.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        Column {
          id: body
          width: scroller.width
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
                active: session.layerIndex === index
                onClicked: {
                  session.layerIndex = index
                  session.selectedIndex = -1
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
            layers: root.session.layers
            layerIndex: root.session.layerIndex
            selectedIndex: root.session.selectedIndex
            foreground: root.contentForeground
            accent: Color.accent
            fontFamily: root.contentFontFamily
            onKeyClicked: function(index) { session.selectedIndex = index }
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
                  active: session.slotName === modelData
                  onClicked: session.slotName = modelData
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
                  active: session.targetLayer === index
                  onClicked: session.targetLayer = index
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
                  text: modelData[1] + " " + root.session.targetLayer
                  fontSize: Style.font.caption
                  foreground: root.contentForeground
                  fontFamily: root.contentFontFamily
                  bordered: true
                  onClicked: root.assignLayerOp(modelData[0])
                }
              }
            }

            Row {
              spacing: Style.space(8)

              KeyPicker {
                id: characterPicker
                width: Style.space(180)
                label: "Character"
                placeholderText: "A–Z"
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
                accent: Color.accent
                options: root.characterOptions
                onChanged: function(code) { root.assignCode(code) }
                onExpandedChanged: if (expanded) root.collapsePickers(characterPicker)
              }

              KeyPicker {
                id: numberPicker
                width: Style.space(140)
                label: "Number"
                placeholderText: "0–9"
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
                accent: Color.accent
                options: root.numberOptions
                onChanged: function(code) { root.assignCode(code) }
                onExpandedChanged: if (expanded) root.collapsePickers(numberPicker)
              }

              KeyPicker {
                id: symbolPicker
                width: Style.space(160)
                label: "Symbol"
                placeholderText: "!@#"
                foreground: root.contentForeground
                fontFamily: root.contentFontFamily
                accent: Color.accent
                options: root.symbolOptions
                onChanged: function(code) { root.assignCode(code) }
                onExpandedChanged: if (expanded) root.collapsePickers(symbolPicker)
              }
            }

            KeyPicker {
              id: keyPicker
              width: Style.spacing.searchableDropdownWidth
              label: "Key"
              placeholderText: "Choose a key"
              foreground: root.contentForeground
              fontFamily: root.contentFontFamily
              accent: Color.accent
              options: root.keyOptions
              onChanged: function(code) { root.assignCode(code) }
              onExpandedChanged: if (expanded) root.collapsePickers(keyPicker)
            }

            Flow {
              width: parent.width
              spacing: Style.space(4)
              Repeater {
                model: [
                  ["leftCtrl", "Ctrl"], ["rightCtrl", "RCtrl"],
                  ["leftShift", "Shift"], ["rightShift", "RShift"],
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
