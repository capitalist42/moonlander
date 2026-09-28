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

test("jal4pq legends and the board index map", () => {
  const layers = doc.layers
  assert.equal(layers.length, 3)
  assert.equal(layers[0].keys.length, 72)

  const esc = Model.legend(layers[0].keys[0])
  assert.equal(esc.main, "Esc")

  const a = Model.legend(layers[0].keys[15])
  assert.equal(a.main, "A")
  assert.ok(a.sub.includes("Super"))
  assert.ok(a.sub.includes("Shift"))

  const grave = Model.legend(layers[0].keys[27])
  assert.equal(grave.main, "`")
  assert.ok(grave.sub.includes("MO1"))
  assert.ok(grave.sub.includes("~"))

  const seen = {}
  Model.ROWS.forEach((row) => {
    row.left.concat(row.right).forEach((index) => {
      seen[index] = true
    })
  })
  assert.equal(Object.keys(seen).length, 72)
  assert.equal(Model.ROWS[4].right[0], 68)
  assert.equal(Model.MAX_LAYERS, 8)
})

test("catalog lists letters, function keys, and digits", () => {
  const list = Model.catalog()
  assert.equal(list.length, 109)
  assert.ok(list.includes("KC_ESCAPE"))
  assert.ok(list.includes("KC_A"))
  assert.ok(list.includes("KC_Z"))
  assert.ok(list.includes("KC_F1"))
  assert.ok(list.includes("KC_F12"))
  assert.ok(list.includes("KC_0"))
  assert.ok(list.includes("KC_9"))
  assert.equal(list.indexOf("KC_F"), list.indexOf("KC_A") + 5)
})

test("short names", () => {
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

test("legends promote hold and double tap when the tap is empty", () => {
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

test("empty layers and labels", () => {
  const key = Model.emptyKey()
  assert.deepEqual(key, { tap: null, hold: null, doubleTap: null })

  const blank = Model.blankLayer("Lower")
  assert.equal(blank.title, "Lower")
  assert.equal(blank.position, 0)
  assert.equal(blank.keys.length, 72)
  blank.keys[0].tap = { code: "KC_A" }
  assert.equal(blank.keys[1].tap, null)

  assert.equal(Model.layerLabel({ title: "Base" }, 0), "Base")
  assert.equal(Model.layerLabel({ title: "Layer" }, 1), "Layer 1")
  assert.equal(Model.layerLabel({ title: "" }, 2), "Layer 2")
  assert.equal(Model.layerLabel(null, 3), "Layer 3")

  const original = { layers: [{ keys: [{ tap: { code: "KC_A" } }] }] }
  const copied = Model.clone(original)
  copied.layers[0].keys[0].tap.code = "KC_B"
  assert.equal(original.layers[0].keys[0].tap.code, "KC_A")
})
