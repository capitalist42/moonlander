"""Compile and flash decisions. qmk and zapp are never invoked."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from script_loader import load

flash = load("flash_under_test", "flash.py")

EMPTY_DRAFT = json.dumps({"layers": [{"title": "Base", "keys": [{} for _ in range(72)]}]})


class IsolatedQmk:
    def __init__(self, with_makefile=False, with_quantum=False, with_qmk_json=False, draft=EMPTY_DRAFT):
        self.with_makefile = with_makefile
        self.with_quantum = with_quantum
        self.with_qmk_json = with_qmk_json
        self.draft_text = draft
        self.stack = ExitStack()

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        qmk = root / "qmk"
        qmk.mkdir()
        keymap = root / "keymap"
        if self.with_makefile:
            (qmk / "Makefile").write_text("all:\n")
        if self.with_quantum:
            (qmk / "quantum").mkdir()
        if self.with_qmk_json:
            (qmk / "qmk.json").write_text("{}\n")
        draft = root / "draft.json"
        draft.write_text(self.draft_text)
        self.stack.enter_context(patch.object(flash, "QMK_HOME", qmk))
        self.stack.enter_context(patch.object(flash, "KEYMAP", keymap))
        return SimpleNamespace(root=root, qmk=qmk, keymap=keymap, draft=draft)

    def __exit__(self, *exc):
        self.stack.close()
        self.tmp.cleanup()


class FlashTest(unittest.TestCase):
    def test_run_passes_the_command_through(self):
        """A successful command is printed with the working directory and environment it was given."""
        seen = {}

        def fake_run(cmd, cwd=None, env=None):
            seen["cmd"] = cmd
            seen["cwd"] = cwd
            seen["env"] = env
            return subprocess.CompletedProcess(cmd, 0)

        with patch.object(flash.subprocess, "run", side_effect=fake_run):
            with redirect_stdout(io.StringIO()) as stdout:
                flash.run(["qmk", "compile"], cwd="/tmp/qmk", env={"QMK_HOME": "/tmp/qmk"})
        self.assertEqual(seen["cmd"], ["qmk", "compile"])
        self.assertEqual(seen["cwd"], "/tmp/qmk")
        self.assertEqual(seen["env"]["QMK_HOME"], "/tmp/qmk")
        self.assertIn("qmk compile", stdout.getvalue())

    def test_run_stops_when_the_command_fails(self):
        """A failing command stops the flasher with that command's exit code."""
        with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 4)):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    flash.run(["qmk", "compile"])
        self.assertEqual(caught.exception.code, 4)

    def test_qmk_env_points_at_the_tree(self):
        """The compile environment points QMK_HOME at this tree and keeps the current PATH."""
        with patch.object(flash, "QMK_HOME", Path("/tmp/qmk-tree")):
            env = flash.qmk_env()
        self.assertEqual(env["QMK_HOME"], "/tmp/qmk-tree")
        self.assertEqual(env["PATH"], os.environ["PATH"])

    def test_missing_qmk_tree(self):
        """Compile refuses when the QMK checkout is not on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(flash, "QMK_HOME", Path(tmp) / "qmk"):
                with self.assertRaises(SystemExit) as caught:
                    flash.compile_draft(Path(tmp) / "draft.json")
        self.assertIn("QMK tree is missing", str(caught.exception))

    def test_quantum_directory_is_enough_to_try_compiling(self):
        """A quantum directory is enough to recognize the QMK tree, and compile still requires the qmk tool."""
        with IsolatedQmk(with_quantum=True) as tree:
            with patch.object(flash.shutil, "which", return_value=None):
                with self.assertRaises(SystemExit) as caught:
                    flash.compile_draft(tree.draft)
        self.assertIn("qmk is not installed", str(caught.exception))

    def test_makefile_without_qmk_installed(self):
        """The keymap is written before compile reports that qmk is not installed."""
        with IsolatedQmk(with_makefile=True) as tree:
            with patch.object(flash.shutil, "which", return_value=None):
                with self.assertRaises(SystemExit) as caught:
                    flash.compile_draft(tree.draft)
            self.assertIn("qmk is not installed", str(caught.exception))
            self.assertTrue((tree.keymap / "keymap.c").is_file())

    def test_qmk_json_without_qmk_installed(self):
        """A qmk.json file is enough to recognize the tree, and compile still requires the qmk tool."""
        with IsolatedQmk(with_qmk_json=True) as tree:
            with patch.object(flash.shutil, "which", return_value=None):
                with self.assertRaises(SystemExit) as caught:
                    flash.compile_draft(tree.draft)
        self.assertIn("qmk is not installed", str(caught.exception))

    def test_compile_returns_this_keymaps_firmware_not_a_newer_bin(self):
        """Compile returns this keymap's firmware even when a newer unrelated .bin sits beside it."""
        with IsolatedQmk(with_makefile=True) as tree:
            decoy = tree.qmk / "newer.bin"
            firmware = tree.qmk / flash.FIRMWARE_BIN
            decoy.write_bytes(b"other")
            firmware.write_bytes(b"moonlander")
            os.utime(firmware, (1_000, 1_000))
            os.utime(decoy, (2_000, 2_000))
            with patch.object(flash.shutil, "which", return_value="/usr/bin/qmk"):
                with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                    with redirect_stdout(io.StringIO()) as stdout:
                        found = flash.compile_draft(tree.draft)
        self.assertEqual(found, firmware)
        self.assertIn(f"firmware {firmware}", stdout.getvalue())

    def test_compile_uses_the_build_directory_when_the_root_has_no_bin(self):
        """When this keymap's firmware exists only under .build, that file is the one to flash."""
        with IsolatedQmk(with_makefile=True) as tree:
            decoy = tree.qmk / "newer.bin"
            decoy.write_bytes(b"other")
            build = tree.qmk / ".build"
            build.mkdir()
            firmware = build / flash.FIRMWARE_BIN
            firmware.write_bytes(b"fw")
            with patch.object(flash.shutil, "which", return_value="/usr/bin/qmk"):
                with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                    with redirect_stdout(io.StringIO()):
                        found = flash.compile_draft(tree.draft)
        self.assertEqual(found, firmware)

    def test_compile_fails_when_qmk_returns_an_error(self):
        """A non-zero qmk compile is reported as that exit code."""
        with IsolatedQmk(with_makefile=True) as tree:
            with patch.object(flash.shutil, "which", return_value="/usr/bin/qmk"):
                with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 2)):
                    with redirect_stdout(io.StringIO()):
                        with self.assertRaises(SystemExit) as caught:
                            flash.compile_draft(tree.draft)
        self.assertEqual(caught.exception.code, 2)

    def test_compile_fails_when_no_firmware_is_produced(self):
        """A qmk run that does not produce this keymap's firmware is a failure, even if some other .bin exists."""
        with IsolatedQmk(with_makefile=True) as tree:
            (tree.qmk / "other.bin").write_bytes(b"stale")
            with patch.object(flash.shutil, "which", return_value="/usr/bin/qmk"):
                with patch.object(flash.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
                    with redirect_stdout(io.StringIO()):
                        with self.assertRaises(SystemExit) as caught:
                            flash.compile_draft(tree.draft)
        self.assertIn(flash.FIRMWARE_BIN, str(caught.exception))

    def test_flash_requires_zapp(self):
        """Flashing refuses when zapp is not installed."""
        with patch.object(flash.shutil, "which", return_value=None):
            with self.assertRaises(SystemExit) as caught:
                flash.flash_bin(Path("/tmp/firmware.bin"))
        self.assertIn("zapp is not installed", str(caught.exception))

    def test_flash_requires_the_firmware_file(self):
        """Flashing refuses when the firmware file is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.bin"
            with patch.object(flash.shutil, "which", return_value="/usr/bin/zapp"):
                with self.assertRaises(SystemExit) as caught:
                    flash.flash_bin(missing)
        self.assertIn("firmware not found", str(caught.exception))

    def test_flash_invokes_zapp_without_running_it(self):
        """Flash asks zapp to write the firmware and tells you to press the reset pinhole."""
        with tempfile.TemporaryDirectory() as tmp:
            firmware = Path(tmp) / "firmware.bin"
            firmware.write_bytes(b"bin")
            with patch.object(flash.shutil, "which", return_value="/usr/bin/zapp"):
                with patch.object(flash, "run") as run:
                    with redirect_stdout(io.StringIO()) as stdout:
                        flash.flash_bin(firmware)
        run.assert_called_once_with(["/usr/bin/zapp", "flash", str(firmware)])
        self.assertIn("reset pinhole", stdout.getvalue())

    def test_compile_command(self):
        """The compile subcommand builds the draft you named."""
        with patch.object(sys, "argv", ["flash.py", "compile", "--draft", "layout.json"]):
            with patch.object(flash, "compile_draft") as compile_draft:
                flash.main()
        compile_draft.assert_called_once_with(Path("layout.json"))

    def test_flash_command_refuses_without_yes(self):
        """Flash does not compile or write the keyboard unless --yes is passed."""
        with patch.object(sys, "argv", ["flash.py", "flash", "--draft", "layout.json"]):
            with patch.object(flash, "compile_draft") as compile_draft:
                with self.assertRaises(SystemExit) as caught:
                    flash.main()
        self.assertIn("refusing to flash", str(caught.exception))
        compile_draft.assert_not_called()

    def test_flash_command_compiles_then_asks_zapp(self):
        """Flash --yes compiles the draft and then hands that firmware to zapp."""
        firmware = Path("/tmp/moonlander-test.bin")
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "layout.json"
            draft.write_text(EMPTY_DRAFT)
            with patch.object(sys, "argv", ["flash.py", "flash", "--draft", str(draft), "--yes"]):
                with patch.object(flash, "compile_draft", return_value=firmware) as compile_draft:
                    with patch.object(flash, "flash_bin") as flash_bin:
                        flash.main()
        compile_draft.assert_called_once_with(draft)
        flash_bin.assert_called_once_with(firmware)

    def test_restore_command_refuses_without_yes(self):
        """Restore does not write the keyboard unless --yes is passed."""
        with patch.object(sys, "argv", ["flash.py", "restore"]):
            with patch.object(flash, "flash_bin") as flash_bin:
                with self.assertRaises(SystemExit) as caught:
                    flash.main()
        self.assertIn("refusing to flash", str(caught.exception))
        flash_bin.assert_not_called()

    def test_flash_command_records_the_layer_hash(self):
        """A successful flash stores the layer hash and marks the draft as what is on the keyboard."""
        layers = [{"title": "Base", "keys": [{} for _ in range(72)]}]
        doc = {"layers": layers, "flashedHash": "old", "layoutId": "DqKqE", "revisionId": "Jal4PQ"}
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "layout.json"
            draft.write_text(json.dumps(doc))
            with patch.object(sys, "argv", ["flash.py", "flash", "--draft", str(draft), "--yes"]):
                with patch.object(flash, "compile_draft", return_value=Path("/tmp/moonlander.bin")):
                    with patch.object(flash, "flash_bin"):
                        with redirect_stdout(io.StringIO()) as stdout:
                            flash.main()
            saved = json.loads(draft.read_text())
        expected = flash.generate_keymap.draft_hash({"layers": layers})
        self.assertEqual(saved["flashedHash"], expected)
        self.assertTrue(saved["matchesKeyboard"])
        self.assertIn(f"flashedHash {expected}", stdout.getvalue())
        self.assertEqual(saved["layoutId"], "DqKqE")

    def test_failed_flash_does_not_record_the_hash(self):
        """A failed flash leaves the previous flashed hash in the draft."""
        doc = {"layers": [{"title": "Base", "keys": [{} for _ in range(72)]}], "flashedHash": "old"}
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "layout.json"
            draft.write_text(json.dumps(doc))
            with patch.object(sys, "argv", ["flash.py", "flash", "--draft", str(draft), "--yes"]):
                with patch.object(flash, "compile_draft", return_value=Path("/tmp/moonlander.bin")):
                    with patch.object(flash, "flash_bin", side_effect=SystemExit(1)):
                        with self.assertRaises(SystemExit):
                            flash.main()
            saved = json.loads(draft.read_text())
        self.assertEqual(saved["flashedHash"], "old")

    def test_restore_command_flashes_the_saved_image(self):
        """Restore flashes the pinned Jal4PQ image."""
        with patch.object(sys, "argv", ["flash.py", "restore", "--yes"]):
            with patch.object(flash, "flash_bin") as flash_bin:
                flash.main()
        flash_bin.assert_called_once_with(flash.RESTORE)


if __name__ == "__main__":
    unittest.main()
