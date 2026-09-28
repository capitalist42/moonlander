#!/usr/bin/env python3
"""Compile a Moonlander draft, or flash a compiled firmware with Zapp."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import importlib.util

spec = importlib.util.spec_from_file_location("generate_keymap", ROOT / "generate-keymap.py")
generate_keymap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate_keymap)

SHARE = Path.home() / ".local" / "share" / "omarchy-moonlander"
QMK_HOME = SHARE / "qmk"
KEYMAP = QMK_HOME / "keyboards" / "zsa" / "moonlander" / "keymaps" / "omarchy"
RESTORE = SHARE / "restore" / "Jal4PQ.bin"
KEYBOARD = "zsa/moonlander/reva"
FIRMWARE_BIN = "zsa_moonlander_reva_omarchy.bin"


def run(cmd, cwd=None, env=None):
    print("+", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=cwd, env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def qmk_env():
    env = os.environ.copy()
    env["QMK_HOME"] = str(QMK_HOME)
    return env


def compile_draft(draft_path: Path):
    if not (QMK_HOME / "Makefile").is_file() and not (QMK_HOME / "qmk.json").is_file():
        # A qmk tree always has a Makefile at the root once setup finishes.
        if not (QMK_HOME / "quantum").is_dir():
            raise SystemExit(
                f"QMK tree is missing at {QMK_HOME}. Run scripts/setup-toolchain.sh first."
            )
    doc = json.loads(draft_path.read_text())
    generate_keymap.write_keymap(doc, ROOT / "baseline", KEYMAP)
    qmk = shutil.which("qmk")
    if not qmk:
        raise SystemExit("qmk is not installed. Run scripts/setup-toolchain.sh first.")
    run([qmk, "compile", "-kb", KEYBOARD, "-km", "omarchy"], cwd=QMK_HOME, env=qmk_env())
    for directory in (QMK_HOME, QMK_HOME / ".build"):
        firmware = directory / FIRMWARE_BIN
        if firmware.is_file():
            print(f"firmware {firmware}", flush=True)
            return firmware
    raise SystemExit(f"compile finished but {FIRMWARE_BIN} was not produced")


def remember_flash(draft_path: Path):
    doc = json.loads(draft_path.read_text())
    doc["flashedHash"] = generate_keymap.draft_hash(doc)
    doc["matchesKeyboard"] = True
    temporary = draft_path.with_suffix(draft_path.suffix + ".tmp")
    temporary.write_text(json.dumps(doc, indent=2) + "\n")
    temporary.replace(draft_path)
    print(f"flashedHash {doc['flashedHash']}", flush=True)


def flash_bin(path: Path):
    zapp = shutil.which("zapp")
    if not zapp:
        raise SystemExit("zapp is not installed. Run scripts/setup-toolchain.sh first.")
    if not path.is_file():
        raise SystemExit(f"firmware not found: {path}")
    print("Press the Moonlander reset pinhole, or the Reset key on layer 2. Leave the cable in.", flush=True)
    run([zapp, "flash", str(path)])


def main():
    parser = argparse.ArgumentParser(description="Compile or flash a Moonlander draft")
    sub = parser.add_subparsers(dest="cmd", required=True)

    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--draft", required=True)

    flash_cmd = sub.add_parser("flash")
    flash_cmd.add_argument("--draft", required=True)
    flash_cmd.add_argument("--yes", action="store_true")

    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("--yes", action="store_true")

    args = parser.parse_args()
    if args.cmd == "compile":
        compile_draft(Path(args.draft))
        return
    if args.cmd == "flash":
        if not args.yes:
            raise SystemExit("refusing to flash without --yes")
        firmware = compile_draft(Path(args.draft))
        flash_bin(firmware)
        remember_flash(Path(args.draft))
        return
    if args.cmd == "restore":
        if not args.yes:
            raise SystemExit("refusing to flash without --yes")
        flash_bin(RESTORE)


if __name__ == "__main__":
    main()
