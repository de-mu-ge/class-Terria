"""兼容入口：`python src/main.py` 等同于 `python -m src`。"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())