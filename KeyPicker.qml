import QtQuick
import qs.Commons
import qs.Ui

// A labeled picker whose list opens in the panel. The shell dropdown's popup
// does not show inside this layer-shell surface, so the choices scroll here.
Column {
  id: root

  property string label: ""
  property string value: ""
  property string placeholderText: ""
  property var options: []
  property color foreground: Color.foreground
  property color accent: Color.accent
  property string fontFamily: Style.font.family
  property bool expanded: false
  property string filter: ""

  readonly property bool editing: filterField.activeFocus
  readonly property string shownLabel: {
    var i
    for (i = 0; i < options.length; i++) {
      if (optionValue(options[i]) === value) return optionLabel(options[i])
    }
    return ""
  }
  readonly property var filteredOptions: {
    var query = filter.toLowerCase()
    var out = []
    var i
    for (i = 0; i < options.length; i++) {
      var option = options[i]
      var label = optionLabel(option).toLowerCase()
      var description = option && option.description ? String(option.description).toLowerCase() : ""
      if (query === "" || label.indexOf(query) >= 0 || description.indexOf(query) >= 0) out.push(option)
    }
    return out
  }

  signal changed(string value)

  function optionValue(option) {
    return (option && typeof option === "object") ? String(option.value) : String(option)
  }

  function optionLabel(option) {
    return (option && typeof option === "object") ? String(option.label) : String(option)
  }

  spacing: Style.space(4)
  width: Style.space(180)

  Text {
    text: root.label
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
  }

  Button {
    width: parent.width
    text: root.shownLabel !== "" ? root.shownLabel : root.placeholderText
    fontSize: Style.font.caption
    foreground: root.foreground
    fontFamily: root.fontFamily
    bordered: true
    active: root.expanded
    onClicked: root.expanded = !root.expanded
  }

  Column {
    width: parent.width
    visible: root.expanded
    spacing: Style.space(4)

    TextField {
      id: filterField
      width: parent.width
      visible: root.options.length > 8
      placeholderText: "Filter"
      foreground: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      onTextChanged: root.filter = text
    }

    Flickable {
      id: scroller
      width: parent.width
      height: Math.min(list.implicitHeight, Style.space(220))
      contentWidth: width
      contentHeight: list.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      interactive: contentHeight > height

      Column {
        id: list
        width: scroller.width
        spacing: Style.space(2)

        Repeater {
          model: root.filteredOptions
          Button {
            required property var modelData
            width: list.width
            text: root.optionLabel(modelData)
            fontSize: Style.font.caption
            foreground: root.foreground
            fontFamily: root.fontFamily
            bordered: true
            active: root.optionValue(modelData) === root.value
            onClicked: {
              var code = root.optionValue(modelData)
              root.value = code
              root.changed(code)
              root.expanded = false
              root.filter = ""
              filterField.text = ""
            }
          }
        }
      }
    }
  }

  onExpandedChanged: {
    if (!expanded) {
      filter = ""
      filterField.text = ""
    }
  }
}
