"""grace_hw: read-only hardware detection for GraceOS.

The heavy lifting lives in :mod:`grace_hw.parsers` (pure functions over
saved command output) and :mod:`grace_hw.collector` (live I/O that never
lets one missing source crash the whole report).
"""

from __future__ import annotations

__version__ = "0.1.0"

from grace_hw.collector import collect

__all__ = ["__version__", "collect"]
