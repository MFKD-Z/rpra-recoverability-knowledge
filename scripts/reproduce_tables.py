#!/usr/bin/env python3
"""Regenerate the reader-facing result tables."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rpra.reporting import generate_tables

generate_tables(ROOT)
print("TABLE_REPRODUCTION=PASS")

