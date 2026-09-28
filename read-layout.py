#!/usr/bin/env python3
"""Read the Moonlander layout id from USB and the keymap from Oryx."""

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


def draft_hash(doc):
    payload = json.dumps(doc.get("layers") or [], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:8]

VENDOR = "3297"
PRODUCT = "1969"
GRAPHQL = "https://oryx.zsa.io/graphql"
QUERY = """
query ($hashId: String!, $revisionId: String!, $geometry: String) {
  layout(hashId: $hashId, revisionId: $revisionId, geometry: $geometry) {
    hashId
    title
    geometry
    revision {
      hashId
      title
      qmkVersion
      zipUrl
      layers { title position keys }
    }
  }
}
"""


def find_keyboard():
    root = Path("/sys/bus/usb/devices")
    if not root.is_dir():
        return None
    for device in root.iterdir():
        vendor = _read(device / "idVendor")
        product = _read(device / "idProduct")
        if vendor.lower() == VENDOR and product.lower() == PRODUCT:
            return {
                "product": _read(device / "product") or "Moonlander Mark I",
                "serial": _read(device / "serial"),
                "vendor": vendor,
                "productId": product,
            }
    return None


def _read(path: Path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def split_serial(serial):
    if not serial or "/" not in serial:
        return None, None
    layout_id, revision_id = serial.split("/", 1)
    if not layout_id or not revision_id:
        return None, None
    return layout_id, revision_id


def fetch_oryx(layout_id, revision_id):
    payload = json.dumps({
        "query": QUERY,
        "variables": {
            "hashId": layout_id,
            "revisionId": revision_id,
            "geometry": "moonlander",
        },
    }).encode()
    request = urllib.request.Request(
        GRAPHQL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("errors"):
        raise RuntimeError(body["errors"][0].get("message") or "Oryx query failed")
    layout = (body.get("data") or {}).get("layout")
    if not layout or not layout.get("revision"):
        raise RuntimeError("Oryx did not return a layout for this serial")
    revision = layout["revision"]
    return {
        "layoutId": layout.get("hashId") or layout_id,
        "revisionId": revision.get("hashId") or revision_id,
        "title": layout.get("title") or "",
        "note": revision.get("title") or "",
        "firmware": revision.get("qmkVersion") or "",
        "geometry": layout.get("geometry") or "moonlander",
        "zipUrl": revision.get("zipUrl") or "",
        "oryxUrl": f"https://configure.zsa.io/moonlander/layouts/{layout_id}/{revision_id}/0",
        "layers": revision.get("layers") or [],
        "source": "oryx",
    }


def live_document():
    keyboard = find_keyboard()
    doc = {
        "connected": keyboard is not None,
        "product": (keyboard or {}).get("product") or "",
        "serial": (keyboard or {}).get("serial") or "",
        "error": "",
    }
    if keyboard is None:
        doc["error"] = "Moonlander is not connected"
        return doc
    layout_id, revision_id = split_serial(doc["serial"])
    if layout_id is None:
        doc["error"] = "Firmware serial has no Oryx layout id. Load the saved draft, or restore the Oryx firmware."
        return doc
    try:
        fetched = fetch_oryx(layout_id, revision_id)
    except (urllib.error.URLError, RuntimeError, TimeoutError, json.JSONDecodeError) as exc:
        doc["error"] = str(exc)
        return doc
    doc.update(fetched)
    doc["originHash"] = draft_hash(doc)
    doc["flashedHash"] = doc["originHash"]
    return doc


def emit(doc):
    json.dump(doc, sys.stdout)
    sys.stdout.write("\n")
    return 0 if not doc.get("error") else 1


def main():
    parser = argparse.ArgumentParser(description="Read the connected Moonlander layout from Oryx")
    parser.add_argument("--draft", default="", help="Draft JSON path. Created from the keyboard when missing.")
    parser.add_argument("--force", action="store_true", help="Replace an existing draft with the keyboard layout")
    args = parser.parse_args()

    if not args.draft:
        return emit(live_document())

    path = Path(args.draft)
    if path.is_file() and not args.force:
        try:
            draft = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            draft = {"error": f"draft is not valid JSON: {exc}", "layers": []}
        live = live_document()
        draft["connected"] = live.get("connected", False)
        draft["liveSerial"] = live.get("serial") or ""
        draft["liveError"] = live.get("error") or ""
        if not draft.get("product"):
            draft["product"] = live.get("product") or ""
        current = draft_hash(draft)
        flashed = draft.get("flashedHash") or ""
        if flashed:
            draft["matchesKeyboard"] = current == flashed
        elif live.get("layers"):
            draft["matchesKeyboard"] = current == draft_hash(live)
        else:
            draft["matchesKeyboard"] = False
        return emit(draft)

    doc = live_document()
    if doc.get("error"):
        return emit(doc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")
    return emit(doc)


if __name__ == "__main__":
    sys.exit(main())
