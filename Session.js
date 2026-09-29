.pragma library

// Shared across every Moonlander bar. A .pragma library keeps one copy for
// the whole shell, so the laptop screen and the external screen edit the
// same draft.

var object = null
var loadClaimed = false

function store() {
  if (object) return object
  var component = Qt.createComponent(Qt.resolvedUrl("Session.qml"))
  if (component.status !== 1) {
    console.log("Moonlander session: " + component.errorString())
    return null
  }
  object = component.createObject(null)
  return object
}

function claimLoad() {
  if (loadClaimed) return false
  loadClaimed = true
  return true
}
