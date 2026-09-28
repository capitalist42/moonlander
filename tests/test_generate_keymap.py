"""Behavior of the Moonlander keymap generator."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from script_loader import ROOT, load

generate_keymap = load("generate_keymap_under_test", "generate-keymap.py")


def layer(keys, title="Base"):
    return {"title": title, "keys": keys}


def filled(**slots):
    keys = [{} for _ in range(72)]
    keys[0] = slots
    return layer(keys)


def source_for(*layers):
    return generate_keymap.render_keymap({"layers": list(layers)})


class GenerateKeymapTest(unittest.TestCase):
    def test_layout_order_is_72_unique_indexes(self):
        """The firmware matrix lists each of the 72 Moonlander keys once."""
        order = generate_keymap.layout_order()
        self.assertEqual(len(order), 72)
        self.assertEqual(len(set(order)), 72)

    def test_layout_order_rejects_a_short_map(self):
        """A geometry that is not 72 keys cannot be compiled."""
        with patch.object(generate_keymap, "ROWS", [[0, 1]]):
            with self.assertRaises(RuntimeError):
                generate_keymap.layout_order()

    def test_draft_hash_tracks_layers_only(self):
        """Renaming the layout keeps the flash hash; changing a key does not."""
        first = {"title": "One", "layers": [{"keys": [{"tap": {"code": "KC_A"}}]}]}
        renamed = {"title": "Two", "layers": first["layers"]}
        changed = {"layers": [{"keys": [{"tap": {"code": "KC_B"}}]}]}
        self.assertEqual(generate_keymap.draft_hash(first), generate_keymap.draft_hash(renamed))
        self.assertNotEqual(generate_keymap.draft_hash(first), generate_keymap.draft_hash(changed))
        self.assertEqual(len(generate_keymap.draft_hash(first)), 8)
        self.assertEqual(generate_keymap.draft_hash({}), generate_keymap.draft_hash({"layers": []}))

    def test_qmk_hsv_matches_the_oryx_swatches(self):
        """Oryx swatch colors become the HSV values shipped in the official keymap, and a bad color is black."""
        self.assertEqual(generate_keymap.qmk_hsv("#f50909"), (0, 245, 245))
        self.assertEqual(generate_keymap.qmk_hsv("#37ce00"), (74, 255, 206))
        # fixtures/official-keymap.c ships Blue Sparkle as HSV_152_255_255.
        self.assertEqual(generate_keymap.qmk_hsv("#0075FF"), (152, 255, 255))
        self.assertEqual(generate_keymap.qmk_hsv("  #0000ff"), (170, 255, 255))
        self.assertEqual(generate_keymap.qmk_hsv("#ffffff"), (0, 0, 255))
        self.assertEqual(generate_keymap.qmk_hsv("#00ff00"), (85, 255, 255))
        for bad in ("", None, "#fff", "12345", "blue", "#00gg00"):
            self.assertEqual(generate_keymap.qmk_hsv(bad), (0, 0, 0))

    def test_empty_draft_is_rejected(self):
        """A draft with no layers is refused."""
        with self.assertRaises(SystemExit) as caught:
            generate_keymap.render_keymap({})
        self.assertIn("no layers", str(caught.exception))

    def test_ninth_layer_is_rejected(self):
        """Nine layers exceed the firmware cap of eight."""
        layers = [layer([{} for _ in range(72)], title=str(index)) for index in range(9)]
        with self.assertRaises(SystemExit) as caught:
            generate_keymap.render_keymap({"layers": layers})
        self.assertIn("8 layers", str(caught.exception))

    def test_eight_layers_are_accepted(self):
        """Eight layers compile, including layer 7."""
        layers = [layer([{} for _ in range(72)]) for _ in range(8)]
        source = generate_keymap.render_keymap({"layers": layers})
        self.assertIn("[7] = LAYOUT_moonlander(", source)

    def test_short_layer_is_rejected(self):
        """A layer that is not 72 keys is refused, and the error names that layer."""
        with self.assertRaises(SystemExit) as caught:
            generate_keymap.render_keymap({"layers": [layer([{}], title="Broken")]})
        self.assertIn("Broken", str(caught.exception))
        self.assertIn("1 keys", str(caught.exception))

    def test_blank_layer_uses_placeholders(self):
        """An empty layer compiles as transparent keys and creates no tap dance."""
        source = source_for(layer([{} for _ in range(72)]))
        self.assertIn("PLACEHOLDER = ZSA_SAFE_RANGE", source)
        self.assertIn("DANCE_NONE", source)
        self.assertIn("KC_TRANSPARENT", source)
        self.assertNotIn("TD(DANCE_", source)

    def test_plain_modifier_wrap_nests_in_wrap_order(self):
        """Ctrl+Shift+A nests as shift around ctrl, in QMK wrap order."""
        source = source_for(filled(tap={"code": "KC_A", "modifiers": {"leftCtrl": True, "leftShift": True}}))
        self.assertIn("LSFT(LCTL(KC_A))", source)

    def test_bare_mod_plus_plain_tap_is_a_mod_tap(self):
        """A plain tap plus a bare modifier hold becomes a mod-tap, not a dual-function key."""
        source = source_for(filled(
            tap={"code": "KC_A"},
            hold={"code": "KC_LEFT_CTRL"},
        ))
        self.assertIn("MT(MOD_LCTL, KC_A)", source)
        self.assertNotIn("DUAL_FUNC_", source)

    def test_plain_tap_plus_momentary_layer_is_layer_tap(self):
        """A plain tap plus a momentary layer hold becomes a layer-tap."""
        source = source_for(filled(
            tap={"code": "KC_A"},
            hold={"code": "MO", "layer": 1},
        ))
        self.assertIn("LT(1, KC_A)", source)
        self.assertNotIn("TD(DANCE_", source)

    def test_modified_tap_plus_other_key_is_a_dual_function(self):
        """A modified tap plus another hold uses a layer-tap alias so the key can tell a tap from a hold."""
        source = source_for(filled(
            tap={"code": "KC_A", "modifiers": {"leftShift": True}},
            hold={"code": "KC_TAB"},
        ))
        self.assertIn("#define DUAL_FUNC_0 LT(3, KC_F8)", source)
        enum = source.split("enum custom_keycodes", 1)[1].split("};", 1)[0]
        self.assertNotIn("DUAL_FUNC_0", enum)
        self.assertIn("case DUAL_FUNC_0:", source)
        self.assertIn("register_code16(LSFT(KC_A));", source)
        self.assertIn("register_code16(KC_TAB);", source)

    def test_two_duals_get_separate_indexes(self):
        """Each dual-function key gets its own alias, and the second does not reuse the first."""
        keys = [{} for _ in range(72)]
        keys[0] = {"tap": {"code": "KC_A"}, "hold": {"code": "KC_B"}}
        keys[1] = {"tap": {"code": "KC_C"}, "hold": {"code": "KC_D"}}
        source = source_for(layer(keys))
        self.assertIn("#define DUAL_FUNC_0 LT(3, KC_F8)", source)
        self.assertIn("#define DUAL_FUNC_1 LT(9, KC_4)", source)

    def test_layer_op_and_color_and_boot_key(self):
        """Toggle-layer, a repeated swatch, and the boot key compile, and the boot key stays a built-in code."""
        keys = [{} for _ in range(72)]
        keys[0] = {"tap": {"code": "TG", "layer": 0}}
        keys[1] = {"tap": {"code": "RGB", "color": "#f50909"}}
        keys[2] = {"tap": {"code": "RGB", "color": "#f50909"}}
        keys[3] = {"tap": {"code": "QK_BOOT"}}
        keys[4] = {"tap": {"code": "RGB_SLD"}}
        keys[5] = {"tap": {"code": "RGB"}}
        source = source_for(layer(keys))
        self.assertIn("TG(0)", source)
        self.assertIn("HSV_0_245_245", source)
        self.assertEqual(source.count("case HSV_0_245_245:"), 1)
        self.assertIn("QK_BOOT", source)
        self.assertNotIn("QK_BOOT = ZSA_SAFE_RANGE", source)
        self.assertIn("RGB_SLD = ZSA_SAFE_RANGE", source)
        self.assertIn("case RGB_SLD:", source)
        self.assertIn("RGB,", source)

    def test_dual_alias_skips_a_real_layer_tap(self):
        """A dual-function alias does not reuse a layer-tap the layout already uses."""
        keys = [{} for _ in range(72)]
        keys[0] = {"tap": {"code": "KC_F8"}, "hold": {"code": "MO", "layer": 3}}
        keys[1] = {"tap": {"code": "KC_A"}, "hold": {"code": "KC_B"}}
        source = source_for(layer(keys))
        self.assertIn("LT(3, KC_F8)", source)
        self.assertIn("#define DUAL_FUNC_0 LT(9, KC_4)", source)
        self.assertNotIn("#define DUAL_FUNC_0 LT(3, KC_F8)", source)

    def test_keycode_that_is_not_an_identifier_is_rejected(self):
        """A keycode that is not a C identifier is refused before it is pasted into the keymap."""
        with self.assertRaises(SystemExit) as caught:
            source_for(filled(tap={"code": "KC_A); return"}))
        self.assertIn("identifier", str(caught.exception))

    def test_layer_outside_the_firmware_range_is_rejected(self):
        """A layer number outside 0..15 is refused."""
        with self.assertRaises(SystemExit) as caught:
            source_for(filled(tap={"code": "MO", "layer": 16}))
        self.assertIn("layer", str(caught.exception))

    def test_hold_only_slots(self):
        """A hold with no tap still compiles as that hold action."""
        keys = [{} for _ in range(72)]
        keys[0] = {"hold": {"code": "OSL", "layer": 3}}
        keys[1] = {"hold": {"code": "KC_LEFT_SHIFT"}}
        keys[2] = {"hold": {"code": "KC_B"}}
        source = source_for(layer(keys))
        self.assertIn("OSL(3)", source)
        self.assertIn("KC_LEFT_SHIFT", source)
        self.assertIn("KC_B", source)

    def test_empty_code_is_transparent_even_with_a_modifier(self):
        """A modifier flag with no keycode does not emit a chord."""
        source = source_for(filled(tap={"modifiers": {"leftCtrl": True}, "layer": 1}))
        self.assertNotIn("LCTL", source)

    def test_shifted_mod_key_is_wrapped_instead_of_a_bare_mod(self):
        """Shift plus a modifier key is a wrapped key, not a mod-tap."""
        source = source_for(filled(tap={"code": "KC_LEFT_CTRL", "modifiers": {"leftShift": True}}))
        self.assertIn("LSFT(KC_LEFT_CTRL)", source)
        self.assertNotIn("MT(", source)

    def test_tap_and_double_without_hold(self):
        """Tap plus double-tap is a dance with no hold action."""
        source = source_for(filled(
            tap={"code": "KC_A"},
            doubleTap={"code": "KC_B"},
        ))
        self.assertIn("TD(DANCE_0)", source)
        self.assertIn("case SINGLE_TAP: register_code16(KC_A); break;", source)
        self.assertIn("case DOUBLE_TAP: register_code16(KC_B); break;", source)
        finished = source.split("void dance_0_finished", 1)[1].split("void dance_0_reset", 1)[0]
        self.assertNotIn("SINGLE_HOLD", finished)
        self.assertNotIn("DANCE_NONE", source)

    def test_dance_with_a_layer_hold_and_a_double_tap(self):
        """Tap, a momentary layer, and a double-tap become one dance that turns that layer on and off."""
        source = source_for(filled(
            tap={"code": "KC_A"},
            hold={"code": "MO", "layer": 2},
            doubleTap={"code": "KC_C"},
        ))
        self.assertIn("case SINGLE_HOLD: layer_on(2); break;", source)
        self.assertIn("case SINGLE_HOLD: layer_off(2); break;", source)
        self.assertIn("register_code16(KC_C);", source)
        self.assertNotIn("LT(", source)

    def test_dance_with_a_key_hold(self):
        """Tap, a key hold, and a double-tap register that hold key and release it."""
        source = source_for(filled(
            tap={"code": "KC_A"},
            hold={"code": "KC_LSFT"},
            doubleTap={"code": "KC_D"},
        ))
        self.assertIn("case SINGLE_HOLD: register_code16(KC_LSFT); break;", source)
        self.assertIn("case SINGLE_HOLD: unregister_code16(KC_LSFT); break;", source)

    def test_double_tap_without_a_tap_uses_kc_no(self):
        """A double-tap with no single tap uses KC_NO for the single press."""
        source = source_for(filled(doubleTap={"code": "KC_A"}))
        self.assertIn("register_code16(KC_NO);", source)
        self.assertIn("register_code16(KC_A);", source)

    def test_write_keymap_copies_baseline_and_stamps_the_serial(self):
        """The keymap keeps the baseline files, stamps an explicit serial, keeps a safe Oryx id, and otherwise uses local/<hash>."""
        doc = {"layers": [layer([{} for _ in range(72)])]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "keymap"
            generate_keymap.write_keymap(doc, ROOT / "baseline", out, serial="abc/def")
            config = (out / "config.h").read_text()
            self.assertIn('#define SERIAL_NUMBER "abc/def"', config)
            self.assertNotIn("Jal4PQ", config)
            self.assertEqual((out / "rules.mk").read_text(), (ROOT / "baseline" / "rules.mk").read_text())
            self.assertEqual((out / "keymap.json").read_text(), (ROOT / "baseline" / "keymap.json").read_text())
            self.assertIn("PLACEHOLDER = ZSA_SAFE_RANGE", (out / "keymap.c").read_text())

            generate_keymap.write_keymap(doc, ROOT / "baseline", out, serial=None)
            stamped = (out / "config.h").read_text()
            self.assertIn(f'#define SERIAL_NUMBER "local/{generate_keymap.draft_hash(doc)}"', stamped)

            named = {"layoutId": "DqKqE", "revisionId": "Jal4PQ", "layers": doc["layers"]}
            generate_keymap.write_keymap(named, ROOT / "baseline", out, serial=None)
            self.assertIn('#define SERIAL_NUMBER "DqKqE/Jal4PQ"', (out / "config.h").read_text())

    def test_write_keymap_rejects_a_serial_that_breaks_c(self):
        """A serial that would break a C string is refused."""
        doc = {"layers": [layer([{} for _ in range(72)])]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "keymap"
            with self.assertRaises(SystemExit) as caught:
                generate_keymap.write_keymap(doc, ROOT / "baseline", out, serial='ab"c')
        self.assertIn("serial", str(caught.exception))

    def test_unsafe_layout_id_falls_back_to_the_local_serial(self):
        """A layout id that would break a C string falls back to the local hash serial."""
        doc = {
            "layoutId": 'a"b',
            "revisionId": "Jal4PQ",
            "layers": [layer([{} for _ in range(72)])],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "keymap"
            generate_keymap.write_keymap(doc, ROOT / "baseline", out, serial=None)
            stamped = (out / "config.h").read_text()
        self.assertIn(f'#define SERIAL_NUMBER "local/{generate_keymap.draft_hash(doc)}"', stamped)
        self.assertNotIn('a"b', stamped)

    def test_main_writes_the_out_dir(self):
        """The command writes the keymap directory and prints that path."""
        doc = {"layers": [layer([{} for _ in range(72)])]}
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.json"
            out = Path(tmp) / "out"
            draft.write_text(json.dumps(doc))
            argv = ["generate-keymap.py", str(draft), str(out), "--serial", "board/rev"]
            with patch.object(sys, "argv", argv):
                with redirect_stdout(io.StringIO()) as stdout:
                    generate_keymap.main()
            self.assertIn(str(out), stdout.getvalue())
            self.assertIn('#define SERIAL_NUMBER "board/rev"', (out / "config.h").read_text())


if __name__ == "__main__":
    unittest.main()
