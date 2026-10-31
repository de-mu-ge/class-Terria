"""海岸世界取样：海滩 / 水线 / 浅海 / 礁石 / 深水 / 洞穴 / 黄昏 / 夜晚 / 营地。

用法：python tools/coast_shots.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.app import Application, AppOptions  # noqa: E402
from src.core.events import InputEvent, InputKind  # noqa: E402

STEP = 1.0 / 60.0
OUT = ROOT / "out"


def teleport(scene, tile_x: int, tile_y: float | None = None) -> None:
    world = scene._world
    player = scene._player
    ts = world.tile_size
    if tile_y is None:
        tile_y = world.surface_y(tile_x) - 1
    player.x = (tile_x + 0.5) * ts
    player.y = tile_y * ts
    player.vx = player.vy = 0.0
    player.in_water = tile_y > world.sea_level
    scene._snap_camera()


def main() -> int:
    OUT.mkdir(exist_ok=True)
    app = Application(AppOptions(scene="coast", headless=True, no_audio=True))
    app.stack.flush()
    scene = app.stack.top
    world = scene._world

    def frames(count: int) -> None:
        for _ in range(count):
            app._update(STEP)

    def shot(name: str, seconds: float = 1.2) -> None:
        frames(int(seconds / STEP))
        app.renderer.begin_frame()
        scene.draw()
        path = OUT / name
        app.renderer.capture(path)
        print(f"[截图] {path.relative_to(ROOT)}")

    # 海滩（清晨，出生点附近）
    scene._cycle.time = 0.30
    teleport(scene, 138)
    shot("coast_01_beach.png")

    # 水线 / 潮间带
    teleport(scene, 168)
    scene._cycle.time = 0.36
    shot("coast_02_waterline.png")

    # 浅海（水下）
    teleport(scene, 205, world.sea_level + 5)
    shot("coast_03_shallow.png")

    # 礁石区
    teleport(scene, 222, world.sea_level + 9)
    shot("coast_04_reef.png")

    # 深水
    teleport(scene, 292, world.sea_level + 16)
    shot("coast_05_deep.png")

    # 洞穴（口部）
    cave_cfg = scene._defs.world.get("cave", {})
    teleport(scene, int(cave_cfg.get("mouth_x", 32)) + 7, int(cave_cfg.get("mouth_y", 88)) + 2)
    scene._cycle.time = 0.55
    shot("coast_06_cave.png")

    # 黄昏
    teleport(scene, 158)
    scene._cycle.time = 0.84
    shot("coast_07_dusk.png", 0.6)

    # 夜晚
    scene._cycle.time = 0.95
    shot("coast_08_night.png", 0.6)

    # 营地：篝火 + 储物箱（夜里更有氛围）
    teleport(scene, 150)
    scene._cycle.time = 0.93
    scene._inventory.add("campfire", 1)
    scene._inventory.add("chest", 1)
    for item_id in ("campfire", "chest"):
        slot = scene._inventory.first_slot_of(item_id)
        if slot is None:
            continue
        scene._ui.selected = slot
        scene.handle_event(InputEvent(InputKind.KEY, key="f"))
        frames(3)
        scene._player.x += 34
        scene._snap_camera()
    shot("coast_09_camp.png", 1.4)

    # 绘制吞吐
    start = time.perf_counter()
    count = 120
    for _ in range(count):
        app._update(STEP)
        app.renderer.begin_frame()
        scene.draw()
    elapsed = time.perf_counter() - start
    print(f"[帧率] {count} 帧 {elapsed:.2f}s → {count / elapsed:.0f} FPS（headless 绘制吞吐）")

    app._shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
