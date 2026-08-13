#!/usr/bin/env python3
"""Run the quick or full public reproduction workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rpra.reproduction import full_reproduction, quick_reproduction


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("quick", "full"))
    args = parser.parse_args()
    try:
        if args.mode == "quick":
            quick_reproduction(ROOT)
        else:
            full_reproduction(ROOT)
        return 0
    except Exception as error:
        print(f"{args.mode.upper()}_REPRODUCTION=FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

