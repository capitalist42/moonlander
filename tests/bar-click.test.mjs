import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const LEFT = 1

// The shell delivers a bar click to the widget root, then dismisses an open
// panel by calling close() on that same root. KeyboardPanel.close does not
// reach the layout unless the root itself implements close.
function mountBarWidget(source, panel) {
  const members = rootMembers(source)
  const callPanel = (body, method) => {
    if (!body || !panel) return false
    if (!/panelLoader\.item/.test(body)) return false
    if (!new RegExp("\\." + method + "\\s*\\(").test(body)) return false
    panel[method]()
    return true
  }
  return {
    get opened() {
      const decl = members.opened || ""
      if (!/panelLoader\.item/.test(decl) || !/\.opened/.test(decl) || !/\?/.test(decl)) return undefined
      return panel ? panel.opened === true : false
    },
    open() { return callPanel(members.open, "open") },
    close() { return callPanel(members.close, "close") },
    press(button) {
      if (button !== LEFT) return false
      const handler = buttonPress(source)
      if (!/togglePanel\s*\(/.test(handler)) return false
      return callPanel(members.togglePanel, "toggle")
    },
  }
}

function rootMembers(source) {
  const start = source.indexOf("\nBarWidget {")
  if (start < 0) throw new Error("BarWidget root missing")
  const lines = source.slice(start + 1).split("\n")
  let depth = 0
  const members = {}
  let name = null
  let buf = []
  for (const line of lines) {
    const opens = (line.match(/\{/g) || []).length
    const closes = (line.match(/\}/g) || []).length
    if (depth === 1) {
      const fn = line.match(/^  function (\w+)\(/)
      const prop = line.match(/^  (?:readonly )?property \w+ (\w+)\s*:/)
      if (fn) {
        name = fn[1]
        buf = [line]
      } else if (prop && !line.includes("{")) {
        members[prop[1]] = line.trim()
      }
    } else if (name) {
      buf.push(line)
    }
    const next = depth + opens - closes
    if (name && depth > 1 && next === 1) {
      members[name] = buf.join("\n")
      name = null
      buf = []
    }
    depth = next
    if (depth === 0 && line.includes("}")) break
  }
  return members
}

function buttonPress(source) {
  const match = source.match(/onPressed:\s*function\s*\([^)]*\)\s*\{([^{}]*)\}/)
  return match ? match[1] : ""
}

function layoutPanel() {
  return {
    opened: false,
    open() { this.opened = true },
    close() { this.opened = false },
    toggle() { this.opened ? this.close() : this.open() },
  }
}

// Shell overlay: KeyboardPanel.close calls owner.close when the bar widget has it.
function dismiss(widget) {
  if (widget.close()) return
  widget.windowOpen = false
}

test("a left click on the bar chip opens the layout panel, and the shell can close it", () => {
  const source = readFileSync(join(root, "BarWidget.qml"), "utf8")
  const panel = layoutPanel()
  const widget = mountBarWidget(source, panel)

  assert.equal(widget.opened, false, "the chip starts closed")
  assert.equal(widget.press(LEFT), true, "a left click is handled")
  assert.equal(widget.opened, true, "the chip reports the panel open")
  assert.equal(panel.opened, true, "the layout panel is open")

  dismiss(widget)
  assert.equal(panel.opened, false, "the shell closes the panel through the chip")
  assert.equal(widget.opened, false, "the chip reports the panel closed")

  assert.equal(widget.press(LEFT), true, "the next left click is handled")
  assert.equal(widget.opened, true, "the next left click opens the panel again")
})
