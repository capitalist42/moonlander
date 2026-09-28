#!/usr/bin/env python3
"""Run the unit tests and require 80% combined coverage.

The rate is coverage.py statement coverage for flash.py, generate-keymap.py,
and read-layout.py, plus node line coverage for Model.js. Those are the
programs this runner executes. The QML files are the Quickshell UI and are
not instrumented here.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_DIR = ROOT / "coverage"
LCOV = COVERAGE_DIR / "js.lcov"
THRESHOLD = 0.80


def python_statements():
    report = COVERAGE_DIR / "python.json"
    completed = subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", str(report)],
        cwd=ROOT,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    totals = json.loads(report.read_text())["totals"]
    return totals["covered_lines"], totals["num_statements"]


def javascript_lines():
    measured = None
    source = None
    covered = total = None
    for line in LCOV.read_text().splitlines():
        if line.startswith("SF:"):
            source = line[3:]
            covered = total = None
        elif line.startswith("LH:"):
            covered = int(line[3:])
        elif line.startswith("LF:"):
            total = int(line[3:])
        elif line == "end_of_record" and source and source.endswith("Model.js") and total:
            measured = (covered or 0, total)
    if measured is None:
        raise SystemExit("node coverage did not report Model.js")
    return measured


def main():
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    python = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
        ],
        cwd=ROOT,
    )
    if python.returncode != 0:
        return python.returncode
    subprocess.run([sys.executable, "-m", "coverage", "report", "-m"], cwd=ROOT)

    node_tests = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("*.test.mjs"))
    node = subprocess.run(
        [
            "node",
            "--experimental-test-coverage",
            "--test-coverage-include=Model.js",
            "--test-reporter=spec",
            "--test-reporter=lcov",
            "--test-reporter-destination=stdout",
            "--test-reporter-destination=" + str(LCOV),
            "--test",
            *node_tests,
        ],
        cwd=ROOT,
    )
    if node.returncode != 0:
        return node.returncode

    py_covered, py_total = python_statements()
    js_covered, js_total = javascript_lines()
    covered = py_covered + js_covered
    total = py_total + js_total
    rate = covered / total if total else 0
    print(
        f"python {py_covered}/{py_total}  "
        f"javascript {js_covered}/{js_total}  "
        f"coverage {rate:.2%}"
    )
    if rate < THRESHOLD:
        print(f"coverage {rate:.2%} is below {THRESHOLD:.0%}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        import coverage  # noqa: F401
    except ImportError:
        print("coverage is not installed. pip install -r requirements-dev.txt", file=sys.stderr)
        sys.exit(1)
    sys.exit(main())
