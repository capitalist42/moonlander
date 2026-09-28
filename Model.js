// Legends and geometry for the Moonlander board. No Qt dependencies.

var ROWS = [
  { left: [0, 1, 2, 3, 4, 5, 6], right: [36, 37, 38, 39, 40, 41, 42] },
  { left: [7, 8, 9, 10, 11, 12, 13], right: [43, 44, 45, 46, 47, 48, 49] },
  { left: [14, 15, 16, 17, 18, 19, 20], right: [50, 51, 52, 53, 54, 55, 56] },
  { left: [21, 22, 23, 24, 25, 26], right: [57, 58, 59, 60, 61, 62] },
  { left: [27, 28, 29, 30, 31, 32], right: [68, 63, 64, 65, 66, 67] },
  { left: [33, 34, 35], right: [69, 70, 71] }
]

var MAX_LAYERS = 8

var SHORT = {
  KC_ESCAPE: "Esc",
  KC_DELETE: "Del",
  KC_BSPC: "Bspc",
  KC_TAB: "Tab",
  KC_ENTER: "Enter",
  KC_SPACE: "Spc",
  KC_CAPS: "Caps",
  KC_LEFT_SHIFT: "Shift",
  KC_RIGHT_SHIFT: "Shift",
  KC_LEFT_CTRL: "Ctrl",
  KC_RIGHT_CTRL: "Ctrl",
  KC_LEFT_ALT: "Alt",
  KC_RIGHT_ALT: "Alt",
  KC_LEFT_GUI: "Super",
  KC_RIGHT_GUI: "Super",
  KC_APPLICATION: "Menu",
  KC_GRAVE: "`",
  KC_TILD: "~",
  KC_MINUS: "-",
  KC_EQUAL: "=",
  KC_BSLS: "\\",
  KC_LBRC: "[",
  KC_RBRC: "]",
  KC_SCLN: ";",
  KC_QUOTE: "'",
  KC_COMMA: ",",
  KC_DOT: ".",
  KC_SLASH: "/",
  KC_QUES: "?",
  KC_COLN: ":",
  KC_LABK: "<",
  KC_RABK: ">",
  KC_LEFT: "←",
  KC_RIGHT: "→",
  KC_UP: "↑",
  KC_DOWN: "↓",
  KC_EXLM: "!",
  KC_AT: "@",
  KC_HASH: "#",
  KC_DLR: "$",
  KC_PERC: "%",
  KC_CIRC: "^",
  KC_AMPR: "&",
  KC_ASTR: "*",
  KC_LPRN: "(",
  KC_RPRN: ")",
  KC_LCBR: "{",
  KC_RCBR: "}",
  KC_PIPE: "|",
  KC_PLUS: "+",
  KC_KP_PLUS: "Num+",
  KC_TRANSPARENT: "",
  KC_NO: "",
  KC_MS_UP: "Ms↑",
  KC_MS_DOWN: "Ms↓",
  KC_MS_LEFT: "Ms←",
  KC_MS_RIGHT: "Ms→",
  KC_MS_BTN1: "Ms1",
  KC_MS_BTN2: "Ms2",
  KC_MEDIA_PLAY_PAUSE: "Play",
  KC_MEDIA_PREV_TRACK: "Prev",
  KC_MEDIA_NEXT_TRACK: "Next",
  KC_AUDIO_VOL_UP: "Vol+",
  KC_AUDIO_VOL_DOWN: "Vol-",
  KC_AUDIO_MUTE: "Mute",
  QK_BOOT: "Reset",
  AU_TOGG: "Audio",
  MU_TOGG: "Music",
  MU_NEXT: "Mus+",
  RGB_MODE_FORWARD: "RGB+",
  RGB_VAD: "Bri-",
  RGB_VAI: "Bri+",
  RGB_HUD: "Hue-",
  RGB_HUI: "Hue+",
  RGB_SLD: "Solid",
  RGB_TOG: "RGB",
  TOGGLE_LAYER_COLOR: "LyCol"
}

var MOD_LABELS = [
  ["leftCtrl", "Ctrl"],
  ["rightCtrl", "RCtrl"],
  ["leftShift", "Shift"],
  ["rightShift", "RShift"],
  ["leftAlt", "Alt"],
  ["rightAlt", "RAlt"],
  ["leftGui", "Super"],
  ["rightGui", "RSuper"]
]

var CATALOG = [
  "KC_TRANSPARENT", "KC_NO", "KC_ESCAPE", "KC_TAB", "KC_ENTER", "KC_SPACE", "KC_BSPC", "KC_DELETE",
  "KC_LEFT_SHIFT", "KC_RIGHT_SHIFT", "KC_LEFT_CTRL", "KC_RIGHT_CTRL", "KC_LEFT_ALT", "KC_RIGHT_ALT",
  "KC_LEFT_GUI", "KC_RIGHT_GUI", "KC_APPLICATION", "KC_CAPS",
  "KC_GRAVE", "KC_MINUS", "KC_EQUAL", "KC_LBRC", "KC_RBRC", "KC_BSLS", "KC_SCLN", "KC_QUOTE",
  "KC_COMMA", "KC_DOT", "KC_SLASH",
  "KC_LEFT", "KC_RIGHT", "KC_UP", "KC_DOWN", "KC_HOME", "KC_END", "KC_PGUP", "KC_PGDN",
  "QK_BOOT",
  "KC_MS_UP", "KC_MS_DOWN", "KC_MS_LEFT", "KC_MS_RIGHT", "KC_MS_BTN1", "KC_MS_BTN2",
  "KC_MEDIA_PLAY_PAUSE", "KC_MEDIA_PREV_TRACK", "KC_MEDIA_NEXT_TRACK",
  "KC_AUDIO_VOL_UP", "KC_AUDIO_VOL_DOWN", "KC_AUDIO_MUTE",
  "AU_TOGG", "MU_TOGG", "MU_NEXT",
  "RGB_TOG", "RGB_MODE_FORWARD", "RGB_VAD", "RGB_VAI", "RGB_HUD", "RGB_HUI", "RGB_SLD", "TOGGLE_LAYER_COLOR"
]

function catalog() {
  var list = CATALOG.slice()
  var letter
  for (letter = 0; letter < 26; letter++) list.push("KC_" + String.fromCharCode(65 + letter))
  var digit
  for (digit = 1; digit <= 12; digit++) list.push("KC_F" + digit)
  for (digit = 0; digit <= 9; digit++) list.push("KC_" + String(digit === 0 ? 0 : digit))
  return list
}

function shortCode(code) {
  if (!code) return ""
  if (SHORT[code] !== undefined) return SHORT[code]
  if (code.indexOf("KC_") === 0) {
    var rest = code.substring(3)
    if (rest.length === 1) return rest
    if (rest.charAt(0) === "F" && rest.length <= 3) return rest
    return rest
  }
  return code
}

function modifierText(action) {
  var flags = action && action.modifiers
  if (!flags) return ""
  var names = []
  var i
  for (i = 0; i < MOD_LABELS.length; i++) {
    if (flags[MOD_LABELS[i][0]]) names.push(MOD_LABELS[i][1])
  }
  return names.join("+")
}

function slotText(action) {
  if (!action) return ""
  var code = action.code || ""
  if (code === "KC_TRANSPARENT" || code === "KC_NO" || code === "") {
    if (action.layer === null || action.layer === undefined) return ""
  }
  if (code === "MO" || code === "TG" || code === "TO" || code === "TT" || code === "OSL" || code === "LT") {
    return code + (action.layer === null || action.layer === undefined ? "" : String(action.layer))
  }
  if (code === "RGB" && action.color) return action.color
  var base = shortCode(code)
  var mods = modifierText(action)
  if (mods && base) return mods + "+" + base
  return mods || base
}

function present(action) {
  return slotText(action) !== ""
}

function legend(key) {
  var tap = key && key.tap
  var hold = key && key.hold
  var doubleTap = key && key.doubleTap
  var main = slotText(tap)
  var notes = []
  if (present(hold)) notes.push(slotText(hold))
  if (present(doubleTap)) notes.push("2×" + slotText(doubleTap))
  if (!main) {
    main = notes.length ? notes.shift() : ""
  }
  return { main: main, sub: notes.join(" ") }
}

function emptyKey() {
  return { tap: null, hold: null, doubleTap: null }
}

function blankLayer(title) {
  var keys = []
  var i
  for (i = 0; i < 72; i++) keys.push(emptyKey())
  return { title: title, position: 0, keys: keys }
}

function layerLabel(layer, index) {
  var title = layer && layer.title ? String(layer.title) : ""
  if (!title || title === "Layer") return "Layer " + index
  return title
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

var LAYER_OPS = { MO: true, TG: true, TO: true, TT: true, OSL: true, LT: true }

function layerTarget(slot) {
  if (!slot || slot.layer === null || slot.layer === undefined || slot.layer === "") return null
  if (typeof slot.layer === "boolean") return null
  var layer = Number(slot.layer)
  if (layer !== layer || layer < 0) return null
  return layer
}

function retargetSlot(slot, removed) {
  if (!slot || !LAYER_OPS[slot.code]) return slot
  var layer = layerTarget(slot)
  if (layer === null) return slot
  if (layer === removed) return null
  if (layer > removed) {
    var next = clone(slot)
    next.layer = layer - 1
    return next
  }
  return slot
}

// Drop one layer and keep the rest pointing at the layers that remain.
// Layer 0 is the base map and is not removed.
function removeLayer(layers, index) {
  if (!layers || index <= 0 || index >= layers.length) return layers
  var next = []
  var i
  for (i = 0; i < layers.length; i++) {
    if (i === index) continue
    var layer = clone(layers[i])
    layer.position = next.length
    var keys = layer.keys || []
    var k
    for (k = 0; k < keys.length; k++) {
      var key = keys[k]
      if (!key) continue
      key.tap = retargetSlot(key.tap, index)
      key.hold = retargetSlot(key.hold, index)
      key.doubleTap = retargetSlot(key.doubleTap, index)
    }
    next.push(layer)
  }
  return next
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    ROWS: ROWS,
    MAX_LAYERS: MAX_LAYERS,
    catalog: catalog,
    legend: legend,
    slotText: slotText,
    emptyKey: emptyKey,
    blankLayer: blankLayer,
    layerLabel: layerLabel,
    clone: clone,
    removeLayer: removeLayer
  }
}
