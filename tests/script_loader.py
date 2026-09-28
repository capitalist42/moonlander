"""Load the hyphenated command scripts as modules."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
