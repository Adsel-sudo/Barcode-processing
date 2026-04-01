#!/usr/bin/env python3
"""Compatibility wrapper for barcode label export CLI."""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "experiments" / "pdf_text" / "export_barcode_labels.py"
    runpy.run_path(str(target), run_name="__main__")
