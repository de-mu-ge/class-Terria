"""资源管理：纹理与字体的统一入口。

原则：
- 任何资源缺失都不抛异常，换成占位纹理并记录一条警告（验收清单：缺图不崩溃）。
- 路径只从 AssetPaths 取，代码里不出现具体素材路径。
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..assets.paths import AssetPaths
from ..data.models import GameConfig, SceneSpec
from ..render.renderer import Font, Renderer, Texture

log = logging.getLogger(__name__)


class ResourceManager:
    def __init__(self, renderer: Renderer, paths: AssetPaths, config: GameConfig) -> None:
        self._renderer = renderer
        self._paths = paths
        self._config = config
        self._textures: dict[str, Texture] = {}
        self._fonts: dict[str, Font] = {}
        self._font_paths: dict[str, str] = {}
        self.missing: list[str] = []

    # --- 纹理 ---------------------------------------------------------
    def texture(self, path: Path | str, key: str | None = None) -> Texture:
        path = Path(path)
        cache_key = key or str(path)
        cached = self._textures.get(cache_key)
        if cached is not None:
            return cached

        if not path.is_file():
            log.warning("缺少素材：%s（使用占位图）", path)
            self.missing.append(str(path))
            placeholder = self._placeholder(path.stem or "missing")
            self._textures[cache_key] = placeholder
            return placeholder

        try:
            texture = self._renderer.load_texture(path)
        except Exception:
            log.exception("素材加载失败：%s（使用占位图）", path)
            self.missing.append(str(path))
            texture = self._placeholder(path.stem or "broken")
        self._textures[cache_key] = texture
        return texture

    def has_asset(self, path: Path | str) -> bool:
        return Path(path).is_file()

    def _placeholder(self, label: str) -> Texture:
        """占位纹理：暗底 + 中性色，尺寸取逻辑画布，避免比例错乱。"""
        width, height = self._renderer.size
        return self._renderer.create_solid(width, height, "#26364A")

    # --- 字体 ---------------------------------------------------------
    def font(self, role: str) -> Font:
        cached = self._fonts.get(role)
        if cached is not None:
            return cached
        spec = self._config.value("fonts", "roles", role, default=None)
        if spec is None:
            log.warning("未知字体角色 %s，退回 dialogue", role)
            spec = self._config.value("fonts", "roles", "dialogue", default={"family": "galgame", "size": 18})
        family = spec.get("family", "galgame")
        size = int(spec.get("size", 18))
        candidates = self._config.value("fonts", "candidates", family, default=[]) or []
        chosen = ""
        for candidate in candidates:
            path = self._paths.resolve(candidate)
            if path.is_file():
                chosen = str(path)
                break
        if not chosen:
            # 全部缺失时仍交给渲染器尝试最后一条（渲染器内部会退回默认字体）
            log.warning("字体家族 %s 候选路径都不存在（角色 %s）", family, role)
            chosen = candidates[-1] if candidates else "default"
            self.missing.append(f"font:{family}")
        font = self._renderer.load_font(chosen, size)
        self._fonts[role] = font
        self._font_paths[role] = chosen
        return font

    @property
    def font_paths(self) -> dict[str, str]:
        return dict(self._font_paths)

    # --- 场景预载 -----------------------------------------------------
    def preload_scene(self, scene: SceneSpec, doll_paths: list[Path]) -> None:
        """预载背景与纸片，避免演出中卡顿。"""
        for bg in scene.backgrounds.values():
            if bg.file:
                self.texture(self._paths.background(bg.file))
        for path in doll_paths:
            self.texture(path)

    def texture_or_none(self, path: Path) -> Texture | None:
        """存在才载入（纸片缺失时要走占位纸片绘制，而不是占位大图）。"""
        if not Path(path).is_file():
            return None
        return self.texture(path)

    def stats(self) -> dict[str, int]:
        return {"textures": len(self._textures), "fonts": len(self._fonts),
                "missing": len(self.missing)}
