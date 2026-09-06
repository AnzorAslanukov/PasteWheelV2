"""Shared pytest fixtures/config for the whole test suite.

Ensures GUI tests run headless by default (SPEC §10: "All GUI tests must
pass with QT_QPA_PLATFORM=offscreen set"). Honors an already-set env var
so CI/dev can still override it explicitly.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
