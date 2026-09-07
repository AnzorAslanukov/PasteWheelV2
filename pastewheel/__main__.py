"""Entry point for ``python -m pastewheel`` (SPEC §11)."""

from __future__ import annotations

import sys

from pastewheel.main import main

if __name__ == "__main__":
    sys.exit(main())
