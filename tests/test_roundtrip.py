#!/usr/bin/env python3
"""The generated keymap must place the same actions as Oryx's keymap.c."""

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("generate_keymap", ROOT / "generate-keymap.py")
generate_keymap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_keymap)


def split_args(body):
    args = []
    buf = []
    depth = 0
    for char in body:
        if char == "(":
            depth += 1
            buf.append(char)
        elif char == ")":
            depth -= 1
            buf.append(char)
        elif char == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    return args


def layout_layers(source):
    layers = []
    cursor = 0
    needle = "LAYOUT_moonlander("
    while True:
        start = source.find(needle, cursor)
        if start < 0:
            break
        index = start + len(needle)
        depth = 1
        buf = []
        while index < len(source) and depth:
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            if depth:
                buf.append(char)
            index += 1
        layers.append(split_args("".join(buf)))
        cursor = index
    return layers


def dance_semantics(source):
    found = {}
    for match in re.finditer(r"void dance_(\d+)_finished\(.*?\{(.*?)\n\}", source, re.S):
        body = match.group(2)
        tap = re.search(r"SINGLE_TAP:\s*register_code16\((.*?)\);", body)
        hold_key = re.search(r"SINGLE_HOLD:\s*register_code16\((.*?)\);", body)
        hold_layer = re.search(r"SINGLE_HOLD:\s*layer_on\((\d+)\);", body)
        double = re.search(r"DOUBLE_TAP:\s*register_code16\((.*?)\);", body)
        parts = ["td"]
        if tap:
            parts.append("tap=" + tap.group(1).replace(" ", ""))
        if hold_layer:
            parts.append("hold=layer" + hold_layer.group(1))
        elif hold_key:
            parts.append("hold=" + hold_key.group(1).replace(" ", ""))
        if double:
            parts.append("double=" + double.group(1).replace(" ", ""))
        found[f"TD(DANCE_{match.group(1)})"] = ":".join(parts)
    return found


def dual_semantics(source):
    found = {}
    for match in re.finditer(r"case DUAL_FUNC_(\d+):(.*?)(?=\n    case |\Z)", source, re.S):
        regs = re.findall(r"(?<![A-Za-z_])register_code16\((.*?)\);", match.group(2))
        tap = regs[0].replace(" ", "") if regs else "?"
        hold = regs[1].replace(" ", "") if len(regs) > 1 else "?"
        found[f"DUAL_FUNC_{match.group(1)}"] = f"dual:tap={tap}:hold={hold}"
    return found


def semantics(source):
    dances = dance_semantics(source)
    duals = dual_semantics(source)
    layers = []
    for args in layout_layers(source):
        row = []
        for token in args:
            compact = re.sub(r"\s+", "", token)
            if compact in dances:
                row.append(dances[compact])
            elif compact in duals:
                row.append(duals[compact])
            elif compact.startswith("HSV_"):
                row.append(compact)
            else:
                row.append(compact)
        layers.append(row)
    return layers


def main():
    doc = json.loads((ROOT / "fixtures" / "jal4pq.json").read_text())
    official = (ROOT / "fixtures" / "official-keymap.c").read_text()
    generated = generate_keymap.render_keymap(doc)
    left = semantics(official)
    right = semantics(generated)
    if len(left) != len(right):
        raise SystemExit(f"layer count {len(left)} != {len(right)}")
    problems = []
    for layer_index, (expect, got) in enumerate(zip(left, right)):
        if len(expect) != 72 or len(got) != 72:
            problems.append(f"layer {layer_index} width {len(expect)} vs {len(got)}")
            continue
        for key_index, (want, have) in enumerate(zip(expect, got)):
            if want != have:
                problems.append(f"L{layer_index}[{key_index}] {want} != {have}")
    if problems:
        print("\n".join(problems[:40]))
        raise SystemExit(f"{len(problems)} key mismatches")
    flat = [key for layer in right for key in layer]
    grave = next((key for key in flat if "KC_GRAVE" in key and "KC_TILD" in key), "")
    if "layer1" not in grave:
        raise SystemExit(f"grave key is {grave}")
    dual = next((key for key in flat if key.startswith("dual:tap=RGUI(KC_SPACE)")), "")
    if dual != "dual:tap=RGUI(KC_SPACE):hold=KC_RIGHT_CTRL":
        raise SystemExit(f"right super-space is {dual}")
    letter = next((key for key in flat if "LSFT(KC_A)" in key), "")
    if "KC_A" not in letter:
        raise SystemExit(f"A is {letter}")
    # Right upper thumb is arguments 60-65: dual, up, down, two dances, layer.
    if right[0][60] != dual or right[0][61] != "KC_UP" or not right[0][64].startswith("td") or right[0][65] != "MO(1)":
        raise SystemExit(f"right thumb row is {right[0][60:66]}")
    print("round-trip ok", len(right), "layers")


class OfficialKeymapRoundTripTest(unittest.TestCase):
    def test_generated_keymap_matches_oryx_semantics(self):
        main()


if __name__ == "__main__":
    main()
