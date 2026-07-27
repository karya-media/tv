"""Shared pytest fixtures.

Populated starting Phase 2 (parser tests need sample .m3u fixtures).
Kept here now so `pytest` runs cleanly from Phase 1 onward, proving the
project skeleton and import paths (src/ layout) are wired correctly.
"""

import sys
from pathlib import Path

# Ensure `src/` is importable without an editable install, so
# `pytest` works immediately after clone + `pip install -r requirements`.
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
