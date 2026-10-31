"""资源路径解析（只读，不写）。

规则：素材一律从项目根 assets/ 下取；缺失时不抛异常，由 ResourceManager 换成占位图。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetPaths:
    project_root: Path

    @property
    def assets_root(self) -> Path:
        return self.project_root / "assets"

    @property
    def data_root(self) -> Path:
        return self.project_root / "data"

    # --- 具体资产 -----------------------------------------------------
    def background(self, name: str) -> Path:
        return self.assets_root / "backgrounds" / "prologue" / name

    def paper_doll(self, relative: str) -> Path:
        return self.assets_root / "characters" / "paper_dolls" / relative

    def sprite(self, relative: str) -> Path:
        return self.assets_root / "characters" / "sprites" / relative

    def ui(self, name: str) -> Path:
        return self.assets_root / "ui" / name

    def audio(self, name: str) -> Path:
        return self.assets_root / "audio" / name

    def font(self, name: str) -> Path:
        return self.assets_root / "fonts" / name

    def resolve(self, value: str | Path) -> Path:
        """相对路径按项目根解析；绝对路径原样返回。"""
        path = Path(value)
        return path if path.is_absolute() else (self.project_root / path)

    def exists(self, path: Path) -> bool:
        return path.is_file()

    def ensure_layout(self) -> None:
        """启动时检查目录，只提示不创建（资产只读）。"""
        for sub in ("backgrounds", "characters", "audio", "fonts", "ui"):
            path = self.assets_root / sub
            if not path.exists():
                log.info("资产目录不存在（相关资源将使用占位）：%s", path)
