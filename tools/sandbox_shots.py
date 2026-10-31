"""沙盒画面取样：玩法 / 挖掘 / 背包 / 合成 四张图 + 帧率测量。

用法：python tools/sandbox_shots.py
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


def main() -> int:
    OUT.mkdir(exist_ok=True)
    app = Application(AppOptions(scene="sandbox", headless=True, no_audio=True))
    app.stack.flush()
    scene = app.stack.top
    world = scene._world
    player = scene._player

    def frames(count: int) -> None:
        for _ in range(count):
            app._update(STEP)

    def shot(name: str) -> None:
        app.renderer.begin_frame()
        scene.draw()
        path = OUT / name
        app.renderer.capture(path)
        print(f"[截图] {path.relative_to(ROOT)}")

    frames(40)
    shot("sandbox_play.png")

    # 挖一个向下的竖井（按住左键）
    ts = world.tile_size
    ptx, pty = player.tile_center()
    for depth in range(1, 5):
        tx, ty = ptx, pty + depth
        scene.ctx.mouse.pos = (int(tx * ts + ts / 2 - scene._camera[0]),
                               int(ty * ts + ts / 2 - scene._camera[1]))
        scene.ctx.mouse.left = True
        frames(70)
        scene.ctx.mouse.left = False
        frames(10)
    shot("sandbox_dig.png")

    # 背包
    scene.handle_event(InputEvent(InputKind.KEY, key="e"))
    scene.ctx.mouse.pos = (int(scene._ui.inventory_rect(2).centerx),
                           int(scene._ui.inventory_rect(2).centery))
    frames(4)
    shot("sandbox_inventory.png")

    # 合成
    scene.handle_event(InputEvent(InputKind.KEY, key="e"))
    scene.handle_event(InputEvent(InputKind.KEY, key="c"))
    scene.ctx.mouse.pos = (int(scene._ui.recipe_rect(1).centerx),
                           int(scene._ui.recipe_rect(1).centery))
    frames(4)
    shot("sandbox_crafting.png")
    scene.handle_event(InputEvent(InputKind.KEY, key="c"))

    # 帧率
    start = time.perf_counter()
    count = 180
    for _ in range(count):
        app._update(STEP)
        app.renderer.begin_frame()
        scene.draw()
    elapsed = time.perf_counter() - start
    print(f"[帧率] {count} 帧 {elapsed:.2f}s → {count / elapsed:.0f} FPS（无窗口绘制吞吐）")

    app._shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
