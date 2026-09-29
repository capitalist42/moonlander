.pragma library

// Shared across every Moonlander bar. A .pragma library keeps one copy for
// the whole shell, so the laptop screen and the external screen edit the
// same draft.

var object = null
var loadClaimed = false

function store(component) {
  if (object) return object
  var source = component
  if (!source) {
    source = Qt.createComponent(Qt.resolvedUrl("Session.qml"))
  }
  if (!source || source.status === 2) return null
  if (source.status !== 1) {
    console.log("Moonlander session: " + source.errorString())
    return null
  }
  object = source.createObject(null)
  return object
}

function claimLoad() {
  if (loadClaimed) return false
  loadClaimed = true
  return true
}
