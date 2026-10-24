"""Check every tile map in python/levels.py. Run from arcade/: python3 scripts/test_levels.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from levels import LEVELS, parse, validate  # noqa: E402

validate(LEVELS)
for level in LEVELS:
    _, start = parse(level["map"])
    print(f"ok  {level['name']}  start={start}")
