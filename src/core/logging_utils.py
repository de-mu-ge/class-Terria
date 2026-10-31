"""日志初始化。"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO", quiet_libs: bool = True) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    numeric = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(numeric)
    root.addHandler(handler)
    if quiet_libs:
        logging.getLogger("pygame").setLevel(logging.WARNING)
    _CONFIGURED = True
