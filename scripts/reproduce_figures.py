#!/usr/bin/env python3
"""Regenerate the reader-facing figures."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rpra.reporting import generate_figures

generate_figures(ROOT)
print("FIGURE_REPRODUCTION=PASS")

