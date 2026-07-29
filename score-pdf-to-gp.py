#!/usr/bin/env python3
"""Launcher. Keeps the package importable without an install step."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
