import test from "node:test"
import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const require = createRequire(import.meta.url)
const root = dirname(dirname(fileURLToPath(import.meta.url)))
const Model = require(join(root, "Model.js"))
const doc = JSON.parse(readFileSync(join(root, "fixtures", "jal4pq.json"), "utf8"))

test("Jal4PQ key legends match the board, and every key index is drawn once", () => {
  const layers = doc.layers
  assert.equal(layers.length, 3, "Jal4PQ has three layers")
  assert.equal(layers[0].keys.length, 72, "each layer has one entry per key")

  const esc = Model.legend(layers[0].keys[0])
  assert.equal(esc.main, "Esc", "the top-left key is Escape")

  const a = Model.legend(layers[0].keys[15])
  assert.equal(a.main, "A", "the A key shows its letter")
  assert.ok(a.sub.includes("Super"), "the A key's hold shows Super")
  assert.ok(a.sub.includes("Shift"), "the A key's hold shows Shift")

  const grave = Model.legend(layers[0].keys[27])
  assert.equal(grave.main, "`", "the grave key shows the backtick")
  assert.ok(grave.sub.includes("MO1"), "the grave key holds layer 1")
  assert.ok(grave.sub.includes("~"), "the grave key's shifted legend is tilde")

  const seen = {}
  Model.ROWS.forEach((row) => {
    row.left.concat(row.right).forEach((index) => {
      seen[index] = true
    })
  })
  assert.equal(Object.keys(seen).length, 72, "the drawn rows cover all 72 keys")
  assert.equal(Model.ROWS[4].right[0], 68, "the right thumb cluster starts at key 68")
  assert.equal(Model.MAX_LAYERS, 8, "the editor allows the same eight layers as the firmware")
})

test("the key catalog offers letters, function keys, and digits in typing order", () => {
  const list = Model.catalog()
  assert.equal(list.length, 109, "the catalog is the fixed keycode list")
  assert.ok(list.includes("KC_ESCAPE"), "Escape is offered")
  assert.ok(list.includes("KC_A"), "letters are offered")
  assert.ok(list.includes("KC_Z"), "the alphabet runs through Z")
  assert.ok(list.includes("KC_F1"), "function keys are offered")
  assert.ok(list.includes("KC_F12"), "function keys run through F12")
  assert.ok(list.includes("KC_0"), "digits are offered")
  assert.ok(list.includes("KC_9"), "digits run through 9")
  assert.equal(list.indexOf("KC_F"), list.indexOf("KC_A") + 5, "letters stay in alphabetical order")
})

test("a key legend uses the short name, including layer ops and modifiers", () => {
  assert.equal(Model.slotText(null), "")
  assert.equal(Model.slotText({ code: "" }), "")
  assert.equal(Model.slotText({ code: "KC_NO" }), "")
  assert.equal(Model.slotText({ code: "KC_TRANSPARENT" }), "")
  assert.equal(Model.slotText({ code: "KC_A" }), "A")
  assert.equal(Model.slotText({ code: "KC_F12" }), "F12")
  assert.equal(Model.slotText({ code: "KC_HOME" }), "HOME")
  assert.equal(Model.slotText({ code: "KC_F100" }), "F100")
  assert.equal(Model.slotText({ code: "CUSTOM" }), "CUSTOM")
  assert.equal(Model.slotText({ code: "MO" }), "MO")
  assert.equal(Model.slotText({ code: "MO", layer: 0 }), "MO0")
  assert.equal(Model.slotText({ code: "TG", layer: 2 }), "TG2")
  assert.equal(Model.slotText({ code: "TO", layer: 3 }), "TO3")
  assert.equal(Model.slotText({ code: "TT", layer: 4 }), "TT4")
  assert.equal(Model.slotText({ code: "OSL", layer: 5 }), "OSL5")
  assert.equal(Model.slotText({ code: "LT", layer: 1 }), "LT1")
  assert.equal(Model.slotText({ code: "RGB", color: "#ff00aa" }), "#ff00aa")
  assert.equal(Model.slotText({ code: "RGB" }), "RGB")
  assert.equal(
    Model.slotText({ code: "KC_SPACE", modifiers: { leftGui: true, rightShift: true } }),
    "RShift+Super+Spc"
  )
  assert.equal(Model.slotText({ modifiers: { leftAlt: true } }), "")
})

test("a key with no tap shows its hold, and a double-tap is marked 2×", () => {
  assert.deepEqual(Model.legend(null), { main: "", sub: "" })
  assert.deepEqual(Model.legend({}), { main: "", sub: "" })
  assert.deepEqual(Model.legend({ hold: { code: "KC_LEFT_SHIFT" } }), { main: "Shift", sub: "" })
  assert.deepEqual(
    Model.legend({ tap: { code: "KC_A" }, doubleTap: { code: "KC_B" } }),
    { main: "A", sub: "2×B" }
  )
  assert.deepEqual(
    Model.legend({
      hold: { code: "KC_LEFT_CTRL" },
      doubleTap: { code: "KC_TAB" }
    }),
    { main: "Ctrl", sub: "2×Tab" }
  )
})

test("a new layer is 72 blank keys, and a default title shows the layer number", () => {
  const key = Model.emptyKey()
  assert.deepEqual(key, { tap: null, hold: null, doubleTap: null }, "a blank key has no tap, hold, or double-tap")

  const blank = Model.blankLayer("Lower")
  assert.equal(blank.title, "Lower", "the layer keeps the title it was given")
  assert.equal(blank.position, 0, "a new layer starts at position 0")
  assert.equal(blank.keys.length, 72, "a new layer has one slot per key")
  blank.keys[0].tap = { code: "KC_A" }
  assert.equal(blank.keys[1].tap, null, "editing one key does not fill the next key")

  assert.equal(Model.layerLabel({ title: "Base" }, 0), "Base", "a real title is shown as written")
  assert.equal(Model.layerLabel({ title: "Layer" }, 1), "Layer 1", "the placeholder title shows the layer number")
  assert.equal(Model.layerLabel({ title: "" }, 2), "Layer 2", "a blank title shows the layer number")
  assert.equal(Model.layerLabel(null, 3), "Layer 3", "a missing layer shows the layer number")
})

test("deleting a layer retargets keys that pointed at it and leaves layer 0 in place", () => {
  const base = Model.blankLayer("Base")
  base.keys[0].tap = { code: "MO", layer: 1 }
  base.keys[1].hold = { code: "LT", layer: 2 }
  base.keys[2].tap = { code: "TG", layer: 2 }
  base.keys[3].tap = { code: "KC_A", layer: 2 }
  const mid = Model.blankLayer("Mid")
  mid.position = 1
  mid.keys[0].tap = { code: "TO", layer: 2 }
  const top = Model.blankLayer("Top")
  top.position = 2
  top.keys[0].doubleTap = { code: "OSL", layer: 1 }
  top.keys[1].tap = { code: "TT", layer: 0 }

  const kept = Model.removeLayer([base, mid, top], 0)
  assert.equal(kept.length, 3, "layer 0 is the base map and is not removed")
  assert.equal(kept[0].keys[0].tap.layer, 1, "a key that holds layer 1 is unchanged when layer 0 stays")

  const next = Model.removeLayer([base, mid, top], 1)
  assert.equal(next.length, 2, "deleting the middle layer leaves the other two")
  assert.equal(next[0].title, "Base", "the base layer stays first")
  assert.equal(next[0].position, 0, "the base layer's position stays 0")
  assert.equal(next[0].keys[0].tap, null, "a momentary hold of the deleted layer is cleared")
  assert.equal(next[0].keys[1].hold.code, "LT", "a layer-tap of a later layer is kept")
  assert.equal(next[0].keys[1].hold.layer, 1, "that layer-tap now aims at the layer's new index")
  assert.equal(next[0].keys[2].tap.layer, 1, "a toggle of a later layer follows the layer to its new index")
  assert.equal(next[0].keys[3].tap.code, "KC_A", "a normal key is not treated as a layer action")
  assert.equal(next[0].keys[3].tap.layer, 2, "a normal key keeps an unrelated layer field")
  assert.equal(next[1].title, "Top", "the layer after the deleted one moves up")
  assert.equal(next[1].position, 1, "the moved layer's position matches its new index")
  assert.equal(next[1].keys[0].doubleTap, null, "a double-tap of the deleted layer is cleared")
  assert.equal(next[1].keys[1].tap.layer, 0, "an action aimed at layer 0 still aims at layer 0")
  assert.equal(base.keys[0].tap.layer, 1, "the layers you passed in are left unchanged")
})

test("cloning a layout does not share keys with the original", () => {
  const original = { layers: [{ keys: [{ tap: { code: "KC_A" } }] }] }
  const copied = Model.clone(original)
  copied.layers[0].keys[0].tap.code = "KC_B"
  assert.equal(original.layers[0].keys[0].tap.code, "KC_A", "editing the copy leaves the original key")
})
