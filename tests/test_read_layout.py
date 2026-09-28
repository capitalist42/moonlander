"""Behavior of the Oryx layout reader. USB and HTTP are faked."""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from script_loader import load

read_layout = load("read_layout_under_test", "read-layout.py")
generate_keymap = load("generate_keymap_for_hash", "generate-keymap.py")


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def usb(root):
    real_path = Path

    def routed(value, *args, **kwargs):
        if not args and not kwargs and str(value) == "/sys/bus/usb/devices":
            return root
        return real_path(value, *args, **kwargs)

    return patch.object(read_layout, "Path", side_effect=routed)


class ReadLayoutTest(unittest.TestCase):
    def test_draft_hash_matches_the_generator(self):
        doc = {"title": "ignored", "layers": [{"keys": [{"tap": {"code": "KC_A"}}]}]}
        self.assertEqual(read_layout.draft_hash(doc), generate_keymap.draft_hash(doc))

    def test_split_serial(self):
        self.assertEqual(read_layout.split_serial("DqKqE/Jal4PQ"), ("DqKqE", "Jal4PQ"))
        self.assertEqual(read_layout.split_serial("layout/rev/extra"), ("layout", "rev/extra"))
        for serial in ("", None, "noid", "layout/", "/revision"):
            self.assertEqual(read_layout.split_serial(serial), (None, None))

    def test_missing_usb_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "absent"
            with usb(missing):
                self.assertIsNone(read_layout.find_keyboard())

    def test_usb_file_is_not_a_device_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            sysfs = Path(tmp) / "devices"
            sysfs.write_text("nope")
            with usb(sysfs):
                self.assertIsNone(read_layout.find_keyboard())

    def test_ignores_other_usb_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "1-1"
            device.mkdir()
            (device / "idVendor").write_text("1234\n")
            (device / "idProduct").write_text("1969\n")
            with usb(Path(tmp)):
                self.assertIsNone(read_layout.find_keyboard())

    def test_reads_a_moonlander(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "1-0"
            other.mkdir()
            (other / "idVendor").write_text("0000\n")
            device = Path(tmp) / "1-1"
            device.mkdir()
            (device / "idVendor").write_text("3297\n")
            (device / "idProduct").write_text("1969\n")
            (device / "product").write_text("Moonlander Mark I\n")
            (device / "serial").write_text("DqKqE/Jal4PQ\n")
            with usb(Path(tmp)):
                found = read_layout.find_keyboard()
        self.assertEqual(found["serial"], "DqKqE/Jal4PQ")
        self.assertEqual(found["product"], "Moonlander Mark I")
        self.assertEqual(found["vendor"], "3297")
        self.assertEqual(found["productId"], "1969")

    def test_missing_product_string_uses_the_board_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "1-1"
            device.mkdir()
            (device / "idVendor").write_text("3297\n")
            (device / "idProduct").write_text("1969\n")
            with usb(Path(tmp)):
                found = read_layout.find_keyboard()
        self.assertEqual(found["product"], "Moonlander Mark I")
        self.assertEqual(found["serial"], "")

    def test_fetch_posts_the_layout_query(self):
        captured = {}
        payload = {
            "data": {
                "layout": {
                    "hashId": "DqKqE",
                    "title": "Mine",
                    "geometry": "moonlander",
                    "revision": {
                        "hashId": "Jal4PQ",
                        "title": "note",
                        "qmkVersion": "firmware25",
                        "zipUrl": "https://example.test/firmware.zip",
                        "layers": [{"title": "Base", "keys": []}],
                    },
                }
            }
        }

        def fake_urlopen(request, timeout=0):
            captured["timeout"] = timeout
            captured["url"] = request.full_url
            captured["type"] = request.get_header("Content-type")
            captured["body"] = json.loads(request.data.decode())
            return Response(json.dumps(payload).encode())

        with patch.object(read_layout.urllib.request, "urlopen", side_effect=fake_urlopen):
            doc = read_layout.fetch_oryx("DqKqE", "Jal4PQ")
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(captured["url"], read_layout.GRAPHQL)
        self.assertEqual(captured["type"], "application/json")
        self.assertEqual(captured["body"]["variables"]["geometry"], "moonlander")
        self.assertEqual(doc["layoutId"], "DqKqE")
        self.assertEqual(doc["revisionId"], "Jal4PQ")
        self.assertEqual(doc["title"], "Mine")
        self.assertEqual(doc["note"], "note")
        self.assertEqual(doc["firmware"], "firmware25")
        self.assertEqual(doc["zipUrl"], "https://example.test/firmware.zip")
        self.assertEqual(doc["source"], "oryx")
        self.assertIn("/DqKqE/Jal4PQ/0", doc["oryxUrl"])
        self.assertEqual(doc["layers"], [{"title": "Base", "keys": []}])

    def test_fetch_fills_missing_oryx_fields(self):
        payload = {"data": {"layout": {"revision": {"title": None}}}}

        def fake_urlopen(request, timeout=0):
            return Response(json.dumps(payload).encode())

        with patch.object(read_layout.urllib.request, "urlopen", side_effect=fake_urlopen):
            doc = read_layout.fetch_oryx("abc", "rev")
        self.assertEqual(doc["layoutId"], "abc")
        self.assertEqual(doc["revisionId"], "rev")
        self.assertEqual(doc["title"], "")
        self.assertEqual(doc["layers"], [])
        self.assertEqual(doc["geometry"], "moonlander")

    def test_fetch_reports_graphql_errors(self):
        def fake_urlopen(request, timeout=0):
            return Response(json.dumps({"errors": [{"message": "gone"}]}).encode())

        with patch.object(read_layout.urllib.request, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError) as caught:
                read_layout.fetch_oryx("abc", "rev")
        self.assertIn("gone", str(caught.exception))

    def test_fetch_reports_an_empty_graphql_error(self):
        def fake_urlopen(request, timeout=0):
            return Response(json.dumps({"errors": [{}]}).encode())

        with patch.object(read_layout.urllib.request, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError) as caught:
                read_layout.fetch_oryx("abc", "rev")
        self.assertIn("Oryx query failed", str(caught.exception))

    def test_fetch_rejects_a_missing_layout(self):
        def fake_urlopen(request, timeout=0):
            return Response(json.dumps({"data": {"layout": None}}).encode())

        with patch.object(read_layout.urllib.request, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError) as caught:
                read_layout.fetch_oryx("abc", "rev")
        self.assertIn("did not return a layout", str(caught.exception))

    def test_live_document_without_a_keyboard(self):
        with patch.object(read_layout, "find_keyboard", return_value=None):
            doc = read_layout.live_document()
        self.assertFalse(doc["connected"])
        self.assertIn("not connected", doc["error"])

    def test_live_document_without_an_oryx_serial(self):
        keyboard = {"product": "Moonlander Mark I", "serial": "local-build"}
        with patch.object(read_layout, "find_keyboard", return_value=keyboard):
            doc = read_layout.live_document()
        self.assertTrue(doc["connected"])
        self.assertIn("no Oryx layout id", doc["error"])

    def test_live_document_records_a_fetched_layout(self):
        keyboard = {"product": "Moonlander Mark I", "serial": "DqKqE/Jal4PQ"}
        fetched = {"layoutId": "DqKqE", "revisionId": "Jal4PQ", "layers": [{"keys": []}], "title": "Mine"}
        with patch.object(read_layout, "find_keyboard", return_value=keyboard):
            with patch.object(read_layout, "fetch_oryx", return_value=fetched):
                doc = read_layout.live_document()
        self.assertEqual(doc["title"], "Mine")
        self.assertEqual(doc["originHash"], read_layout.draft_hash(doc))
        self.assertEqual(doc["flashedHash"], doc["originHash"])
        self.assertEqual(doc["error"], "")

    def test_live_document_keeps_fetch_failures(self):
        keyboard = {"product": "Moonlander Mark I", "serial": "DqKqE/Jal4PQ"}
        failures = [
            urllib.error.URLError("offline"),
            RuntimeError("gone"),
            TimeoutError("slow"),
            json.JSONDecodeError("bad", "", 0),
        ]
        for failure in failures:
            with patch.object(read_layout, "find_keyboard", return_value=keyboard):
                with patch.object(read_layout, "fetch_oryx", side_effect=failure):
                    doc = read_layout.live_document()
            self.assertTrue(doc["connected"])
            self.assertTrue(doc["error"])
            self.assertNotIn("layers", doc)

    def test_emit_status_follows_the_error(self):
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(read_layout.emit({"ok": True}), 0)
        self.assertTrue(stdout.getvalue().endswith("\n"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(read_layout.emit({"error": "nope"}), 1)

    def _run_main(self, argv):
        with patch.object(sys, "argv", argv):
            with redirect_stdout(io.StringIO()) as stdout:
                code = read_layout.main()
        return code, stdout.getvalue()

    def test_main_prints_the_live_document(self):
        live = {"connected": False, "error": "Moonlander is not connected"}
        with patch.object(read_layout, "live_document", return_value=live):
            code, text = self._run_main(["read-layout.py"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(text)["error"], live["error"])

    def test_main_keeps_an_existing_draft(self):
        layers = [{"keys": [{"tap": {"code": "KC_A"}}]}]
        draft = {"title": "Mine", "product": "Custom", "layers": layers}
        live = {
            "connected": True,
            "serial": "DqKqE/Jal4PQ",
            "error": "",
            "product": "Moonlander Mark I",
            "layers": layers,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text(json.dumps(draft))
            with patch.object(read_layout, "live_document", return_value=live):
                code, text = self._run_main(["read-layout.py", "--draft", str(path)])
        body = json.loads(text)
        self.assertEqual(code, 0)
        self.assertEqual(body["product"], "Custom")
        self.assertEqual(body["liveSerial"], "DqKqE/Jal4PQ")
        self.assertTrue(body["matchesKeyboard"])

    def test_main_reports_a_corrupt_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text("{")
            with patch.object(read_layout, "live_document", return_value={"connected": False, "error": ""}):
                code, text = self._run_main(["read-layout.py", "--draft", str(path)])
        body = json.loads(text)
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", body["error"])

    def test_flashed_hash_wins_over_the_live_layout(self):
        layers = [{"keys": []}]
        draft = {"layers": layers, "flashedHash": "deadbeef"}
        live = {"connected": True, "serial": "a/b", "error": "", "product": "Moonlander Mark I", "layers": layers}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text(json.dumps(draft))
            with patch.object(read_layout, "live_document", return_value=live):
                code, text = self._run_main(["read-layout.py", "--draft", str(path)])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(text)["matchesKeyboard"])

    def test_matching_flashed_hash(self):
        draft = {"layers": [{"keys": [{"tap": {"code": "KC_B"}}]}]}
        draft["flashedHash"] = read_layout.draft_hash(draft)
        live = {"connected": False, "serial": "", "error": "Moonlander is not connected", "layers": []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text(json.dumps(draft))
            with patch.object(read_layout, "live_document", return_value=live):
                _code, text = self._run_main(["read-layout.py", "--draft", str(path)])
        body = json.loads(text)
        self.assertTrue(body["matchesKeyboard"])
        self.assertEqual(body["product"], "")

    def test_draft_without_layers_or_a_flash_hash_does_not_match(self):
        live = {"connected": True, "serial": "", "error": "", "product": "Moonlander Mark I"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text(json.dumps({"title": "Empty"}))
            with patch.object(read_layout, "live_document", return_value=live):
                _code, text = self._run_main(["read-layout.py", "--draft", str(path)])
        body = json.loads(text)
        self.assertFalse(body["matchesKeyboard"])
        self.assertEqual(body["product"], "Moonlander Mark I")

    def test_force_writes_a_fetched_layout(self):
        fetched = {"connected": True, "error": "", "layers": [], "title": "Fetched"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "layout.json"
            with patch.object(read_layout, "live_document", return_value=fetched):
                code, text = self._run_main(["read-layout.py", "--draft", str(path), "--force"])
            saved = json.loads(path.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(saved["title"], "Fetched")
        self.assertEqual(json.loads(text)["title"], "Fetched")

    def test_force_does_not_overwrite_when_the_keyboard_cannot_be_read(self):
        failure = {"connected": False, "error": "Moonlander is not connected"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text('{"title": "keep"}\n')
            with patch.object(read_layout, "live_document", return_value=failure):
                code, _text = self._run_main(["read-layout.py", "--draft", str(path), "--force"])
            self.assertEqual(path.read_text(), '{"title": "keep"}\n')
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
