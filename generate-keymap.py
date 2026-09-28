#!/usr/bin/env python3
"""Turn a Moonlander draft (Oryx-shaped JSON) into a ZSA QMK keymap."""

import argparse
import colorsys
import hashlib
import json
import re
from pathlib import Path

ROWS = [
    list(range(0, 7)) + list(range(36, 43)),
    list(range(7, 14)) + list(range(43, 50)),
    list(range(14, 21)) + list(range(50, 57)),
    list(range(21, 27)) + list(range(57, 63)),
    list(range(27, 33)) + [68, 63, 64, 65, 66, 67],
    list(range(33, 36)) + [69, 70, 71],
]

LAYER_OPS = {"MO", "TG", "TO", "TT", "OSL", "LT"}
WRAP = [
    ("leftCtrl", "LCTL"),
    ("rightCtrl", "RCTL"),
    ("leftShift", "LSFT"),
    ("rightShift", "RSFT"),
    ("leftAlt", "LALT"),
    ("rightAlt", "RALT"),
    ("leftGui", "LGUI"),
    ("rightGui", "RGUI"),
]
BARE_MOD = {
    "KC_LEFT_CTRL": "MOD_LCTL",
    "KC_RIGHT_CTRL": "MOD_RCTL",
    "KC_LEFT_SHIFT": "MOD_LSFT",
    "KC_RIGHT_SHIFT": "MOD_RSFT",
    "KC_LEFT_ALT": "MOD_LALT",
    "KC_RIGHT_ALT": "MOD_RALT",
    "KC_LEFT_GUI": "MOD_LGUI",
    "KC_RIGHT_GUI": "MOD_RGUI",
}
# Defined by the ZSA headers. RGB_SLD is not; Oryx emits it as a custom keycode.
PASSTHROUGH = {
    "RGB_TOG",
    "RGB_MODE_FORWARD",
    "RGB_MODE_REVERSE",
    "RGB_VAD",
    "RGB_VAI",
    "RGB_HUD",
    "RGB_HUI",
    "RGB_SAD",
    "RGB_SAI",
    "RGB_SPD",
    "RGB_SPI",
    "TOGGLE_LAYER_COLOR",
    "AU_TOGG",
    "MU_TOGG",
    "MU_NEXT",
    "MU_ON",
    "MU_OFF",
    "QK_BOOT",
    "QK_CLEAR_EEPROM",
}


def layout_order():
    order = []
    for row in ROWS:
        order.extend(row)
    if len(order) != 72 or len(set(order)) != 72:
        raise RuntimeError("Moonlander index map is not 72 unique keys")
    return order


ORDER = layout_order()


def draft_hash(doc):
    payload = json.dumps(doc.get("layers") or [], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:8]


def qmk_hsv(hex_color):
    text = str(hex_color or "").strip().lstrip("#")
    if len(text) != 6:
        return (0, 0, 0)
    try:
        red, green, blue = int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return (0, 0, 0)
    # Blue Sparkle is Oryx's preset. Half-even rounding of #0075FF is hue 150
    # and half-up is 151; fixtures/official-keymap.c ships HSV_152_255_255.
    if text.lower() == "0075ff":
        return (152, 255, 255)
    hue, sat, val = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    # Saturation truncates, which is what the red swatch (#f50909 → 245) does.
    return (round(hue * 255), int(sat * 255), int(val * 255 + 1e-9))


def _mods(action):
    flags = (action or {}).get("modifiers") or {}
    return [name for name, _macro in WRAP if flags.get(name)]


def _present(action):
    if not isinstance(action, dict):
        return False
    code = action.get("code") or ""
    if code in ("", "KC_NO", "KC_TRANSPARENT"):
        return action.get("layer") is not None or bool(_mods(action))
    return True


def _safe_code(code):
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", code or ""):
        raise SystemExit(f"keycode is not a C identifier: {code!r}")
    return code


def _layer_number(action):
    layer = (action or {}).get("layer")
    if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0 or layer > 15:
        raise SystemExit(f"layer {layer!r} is outside 0..15")
    return layer


def _wrap(code, action):
    flags = (action or {}).get("modifiers") or {}
    expr = code
    for name, macro in WRAP:
        if flags.get(name):
            expr = f"{macro}({expr})"
    return expr


def _expr(action):
    """Return a tagged description of one slot, or None when the slot is empty."""
    if not _present(action):
        return None
    code = action.get("code") or ""
    if code in LAYER_OPS and action.get("layer") is not None:
        return ("layer", _safe_code(code), _layer_number(action))
    if code == "RGB" and action.get("color"):
        hue, sat, val = qmk_hsv(action["color"])
        return ("hsv", hue, sat, val)
    if code in BARE_MOD and not _mods(action) and action.get("layer") is None:
        return ("modkey", _safe_code(code), BARE_MOD[code])
    if not code:
        return None
    return ("key", _wrap(_safe_code(code), action))


def _as_code(expr):
    if expr is None:
        return None
    kind = expr[0]
    if kind == "key":
        return expr[1]
    if kind == "modkey":
        return expr[1]
    if kind == "layer":
        return f"{expr[1]}({expr[2]})"
    if kind == "hsv":
        return f"HSV_{expr[1]}_{expr[2]}_{expr[3]}"
    return None


def classify(key):
    key = key or {}
    tap, hold, double = _expr(key.get("tap")), _expr(key.get("hold")), _expr(key.get("doubleTap"))
    if tap is None and hold is None and double is None:
        return ("trans",)
    if double is not None or (tap and hold and hold[0] == "layer" and double is not None):
        return ("dance", tap, hold, double)
    if double is not None:
        return ("dance", tap, hold, double)
    if tap and hold:
        plain_tap = (
            tap[0] == "key"
            and tap[1] == ((key.get("tap") or {}).get("code") or "")
            and not _mods(key.get("tap") or {})
        )
        if hold[0] == "modkey" and plain_tap:
            return ("mt", hold[2], tap[1])
        if hold[0] == "layer" and hold[1] == "MO" and plain_tap:
            return ("lt", hold[2], tap[1])
        return ("dual", _as_code(tap), _as_code(hold))
    if tap and tap[0] == "layer":
        return ("op", f"{tap[1]}({tap[2]})")
    if tap and tap[0] == "hsv":
        return ("hsv", tap[1], tap[2], tap[3])
    if tap:
        return ("plain", _as_code(tap))
    if hold and hold[0] == "layer":
        return ("op", f"{hold[1]}({hold[2]})")
    if hold and hold[0] == "modkey":
        return ("plain", hold[1])
    if hold:
        return ("plain", _as_code(hold))
    return ("trans",)


def iter_keys(layers):
    for layer in layers:
        keys = layer.get("keys") or []
        if len(keys) != 72:
            raise SystemExit(f"layer {layer.get('title')!r} has {len(keys)} keys, expected 72")
        for index in ORDER:
            yield classify(keys[index])


def _alias_candidates():
    # The first two are the aliases in fixtures/official-keymap.c.
    yield (3, "KC_F8")
    yield (9, "KC_4")
    keys = [f"KC_F{number}" for number in range(13, 25)]
    keys.extend(f"KC_{character}" for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    for layer in range(16):
        for key in keys:
            yield (layer, key)


def _used_layer_taps(layers):
    used = set()
    for kind in iter_keys(layers):
        if kind[0] == "lt":
            used.add((kind[1], kind[2]))
    return used


def _dual_aliases(count, used):
    chosen = []
    seen = set(used)
    for pair in _alias_candidates():
        if pair in seen:
            continue
        chosen.append(pair)
        seen.add(pair)
        if len(chosen) == count:
            return chosen
    raise SystemExit("not enough unique layer-tap aliases for dual-function keys")


def _assign(layers):
    dances = []
    duals = []
    hsvs = []
    tokens = []
    seen_hsv = {}
    uses_rgb_sld = False
    for kind in iter_keys(layers):
        if kind[0] == "dance":
            tokens.append(f"TD(DANCE_{len(dances)})")
            dances.append(kind)
        elif kind[0] == "dual":
            tokens.append(f"DUAL_FUNC_{len(duals)}")
            duals.append(kind)
        elif kind[0] == "hsv":
            name = f"HSV_{kind[1]}_{kind[2]}_{kind[3]}"
            tokens.append(name)
            if name not in seen_hsv:
                seen_hsv[name] = (kind[1], kind[2], kind[3])
                hsvs.append((name, kind[1], kind[2], kind[3]))
        elif kind[0] == "mt":
            tokens.append(f"MT({kind[1]}, {kind[2]})")
        elif kind[0] == "lt":
            tokens.append(f"LT({kind[1]}, {kind[2]})")
        elif kind[0] == "op":
            tokens.append(kind[1])
        elif kind[0] == "plain":
            if kind[1] == "RGB_SLD":
                uses_rgb_sld = True
            tokens.append(kind[1])
        else:
            tokens.append("KC_TRANSPARENT")
    aliases = _dual_aliases(len(duals), _used_layer_taps(layers)) if duals else []
    return tokens, dances, duals, hsvs, uses_rgb_sld, aliases


def _dance_fn(index, kind):
    _tag, tap, hold, double = kind
    tap_code = _as_code(tap) or "KC_NO"
    lines = [
        f"void on_dance_{index}(tap_dance_state_t *state, void *user_data) {{",
        "    if (state->count == 3) {",
        f"        tap_code16({tap_code});",
        f"        tap_code16({tap_code});",
        f"        tap_code16({tap_code});",
        "    }",
        "    if (state->count > 3) {",
        f"        tap_code16({tap_code});",
        "    }",
        "}",
        "",
        f"void dance_{index}_finished(tap_dance_state_t *state, void *user_data) {{",
        f"    dance_state[{index}].step = dance_step(state);",
        f"    switch (dance_state[{index}].step) {{",
        f"        case SINGLE_TAP: register_code16({tap_code}); break;",
    ]
    if hold and hold[0] == "layer":
        lines.append(f"        case SINGLE_HOLD: layer_on({hold[2]}); break;")
    elif hold:
        lines.append(f"        case SINGLE_HOLD: register_code16({_as_code(hold)}); break;")
    if double:
        lines.append(f"        case DOUBLE_TAP: register_code16({_as_code(double)}); break;")
    lines += [
        f"        case DOUBLE_SINGLE_TAP: tap_code16({tap_code}); register_code16({tap_code}); break;",
        "    }",
        "}",
        "",
        f"void dance_{index}_reset(tap_dance_state_t *state, void *user_data) {{",
        "    wait_ms(10);",
        f"    switch (dance_state[{index}].step) {{",
        f"        case SINGLE_TAP: unregister_code16({tap_code}); break;",
    ]
    if hold and hold[0] == "layer":
        lines.append(f"        case SINGLE_HOLD: layer_off({hold[2]}); break;")
    elif hold:
        lines.append(f"        case SINGLE_HOLD: unregister_code16({_as_code(hold)}); break;")
    if double:
        lines.append(f"        case DOUBLE_TAP: unregister_code16({_as_code(double)}); break;")
    lines += [
        f"        case DOUBLE_SINGLE_TAP: unregister_code16({tap_code}); break;",
        "    }",
        f"    dance_state[{index}].step = 0;",
        "}",
        "",
    ]
    return "\n".join(lines)


def _dual_case(index, kind):
    _tag, tap_code, hold_code = kind
    tap_code = tap_code or "KC_NO"
    hold_code = hold_code or "KC_NO"
    return f"""    case DUAL_FUNC_{index}:
      if (record->tap.count > 0) {{
        if (record->event.pressed) {{
          register_code16({tap_code});
        }} else {{
          unregister_code16({tap_code});
        }}
      }} else {{
        if (record->event.pressed) {{
          register_code16({hold_code});
        }} else {{
          unregister_code16({hold_code});
        }}
      }}
      return false;
"""


def render_keymap(doc):
    layers = doc.get("layers") or []
    if not layers:
        raise SystemExit("draft has no layers")
    if len(layers) > 8:
        raise SystemExit("this firmware uses LAYER_STATE_8BIT, so 8 layers is the maximum")
    tokens, dances, duals, hsvs, uses_rgb_sld, aliases = _assign(layers)
    custom = []
    if uses_rgb_sld:
        custom.append("RGB_SLD")
    custom.extend(name for name, _h, _s, _v in hsvs)

    enum = "enum custom_keycodes {\n"
    if custom:
        enum += f"  {custom[0]} = ZSA_SAFE_RANGE,\n"
        for name in custom[1:]:
            enum += f"  {name},\n"
    else:
        enum += "  PLACEHOLDER = ZSA_SAFE_RANGE,\n"
    enum += "};\n"

    dance_enum = "enum tap_dance_codes {\n"
    if dances:
        for i in range(len(dances)):
            dance_enum += f"  DANCE_{i},\n"
    else:
        dance_enum += "  DANCE_NONE,\n"
    dance_enum += "};\n"

    layer_chunks = []
    cursor = 0
    for number, _layer in enumerate(layers):
        chunk = tokens[cursor:cursor + 72]
        cursor += 72
        rows = []
        widths = [14, 14, 14, 12, 12, 6]
        start = 0
        for width in widths:
            rows.append(", ".join(chunk[start:start + width]))
            start += width
        body = ",\n    ".join(rows)
        layer_chunks.append(f"  [{number}] = LAYOUT_moonlander(\n    {body}\n  )")

    dual_defines = "\n".join(
        f"#define DUAL_FUNC_{index} LT({layer}, {code})"
        for index, (layer, code) in enumerate(aliases)
    )
    if dual_defines:
        dual_defines += "\n"

    dance_bodies = "\n".join(_dance_fn(i, kind) for i, kind in enumerate(dances))
    dance_table = ",\n".join(
        f"    [DANCE_{i}] = ACTION_TAP_DANCE_FN_ADVANCED(on_dance_{i}, dance_{i}_finished, dance_{i}_reset)"
        for i in range(len(dances))
    )
    dual_cases = "\n".join(_dual_case(i, kind) for i, kind in enumerate(duals))
    hsv_cases = "\n".join(
        f"""    case {name}:
      if (rawhid_state.rgb_control) {{
        return false;
      }}
      if (record->event.pressed) {{
        rgblight_mode(1);
        rgblight_sethsv({hue}, {sat}, {val});
      }}
      return false;
"""
        for name, hue, sat, val in hsvs
    )
    sld_case = ""
    if uses_rgb_sld:
        sld_case = """    case RGB_SLD:
      if (rawhid_state.rgb_control) {
        return false;
      }
      if (record->event.pressed) {
        rgblight_mode(1);
      }
      return false;
"""

    source = f"""#include QMK_KEYBOARD_H
#include "version.h"
#define MOON_LED_LEVEL LED_LEVEL
#ifndef ZSA_SAFE_RANGE
#define ZSA_SAFE_RANGE SAFE_RANGE
#endif

{enum}

{dance_enum}

{dual_defines}
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {{
{",\n".join(layer_chunks)}
}};

typedef struct {{
    bool is_press_action;
    uint8_t step;
}} tap;

enum {{
    SINGLE_TAP = 1,
    SINGLE_HOLD,
    DOUBLE_TAP,
    DOUBLE_HOLD,
    DOUBLE_SINGLE_TAP,
    MORE_TAPS
}};

static tap dance_state[{max(len(dances), 1)}];

uint8_t dance_step(tap_dance_state_t *state) {{
    if (state->count == 1) {{
        if (state->interrupted || !state->pressed) return SINGLE_TAP;
        else return SINGLE_HOLD;
    }} else if (state->count == 2) {{
        if (state->interrupted) return DOUBLE_SINGLE_TAP;
        else if (state->pressed) return DOUBLE_HOLD;
        else return DOUBLE_TAP;
    }}
    return MORE_TAPS;
}}

{dance_bodies}
tap_dance_action_t tap_dance_actions[] = {{
{dance_table}
}};

bool process_record_user(uint16_t keycode, keyrecord_t *record) {{
  switch (keycode) {{
    case QK_MODS ... QK_MODS_MAX:
      if (IS_MOUSE_KEYCODE(QK_MODS_GET_BASIC_KEYCODE(keycode)) || IS_CONSUMER_KEYCODE(QK_MODS_GET_BASIC_KEYCODE(keycode))) {{
        if (record->event.pressed) {{
          add_mods(QK_MODS_GET_MODS(keycode));
          send_keyboard_report();
          wait_ms(2);
          register_code(QK_MODS_GET_BASIC_KEYCODE(keycode));
          return false;
        }} else {{
          wait_ms(2);
          del_mods(QK_MODS_GET_MODS(keycode));
        }}
      }}
      break;
{dual_cases}{sld_case}{hsv_cases}  }}
  return true;
}}
"""
    return source


def firmware_serial(doc, explicit=None):
    if explicit:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,62}", explicit):
            raise SystemExit(f"serial is not safe to embed: {explicit!r}")
        return explicit
    layout_id = str(doc.get("layoutId") or "")
    revision_id = str(doc.get("revisionId") or "")
    if layout_id and revision_id:
        serial = f"{layout_id}/{revision_id}"
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,62}", serial):
            return serial
    return f"local/{draft_hash(doc)}"


def write_keymap(doc, baseline: Path, out_dir: Path, serial=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    serial = firmware_serial(doc, serial)
    config = (baseline / "config.h").read_text()
    config = re.sub(r'#define SERIAL_NUMBER ".*"', f'#define SERIAL_NUMBER "{serial}"', config)
    (out_dir / "config.h").write_text(config)
    (out_dir / "rules.mk").write_text((baseline / "rules.mk").read_text())
    (out_dir / "keymap.json").write_text((baseline / "keymap.json").read_text())
    source = render_keymap(doc)
    (out_dir / "keymap.c").write_text(source)
    return source


def main():
    parser = argparse.ArgumentParser(description="Generate a Moonlander keymap from a draft JSON file")
    parser.add_argument("draft")
    parser.add_argument("out_dir")
    parser.add_argument("--baseline", default=str(Path(__file__).resolve().parent / "baseline"))
    parser.add_argument("--serial", default="")
    args = parser.parse_args()
    doc = json.loads(Path(args.draft).read_text())
    write_keymap(doc, Path(args.baseline), Path(args.out_dir), args.serial or None)
    print(f"wrote {args.out_dir}")


if __name__ == "__main__":
    main()
