"""流程自检：不依赖窗口，直接驱动场景栈验证关键交互。

覆盖：
1. 开始界面 → Scene 01
2. 按住 Ctrl 快进整段台词（对话不卡死）
3. Esc → 二次确认 → 回开始界面
4. 「继续」置灰不可选
5. 单独启动 Scene 07 → 交接 → 生存占位画面
6. 退出后重建应用，状态干净

用法：python tools/flow_check.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.app import Application, AppOptions  # noqa: E402
from src.core.events import InputEvent, InputKind  # noqa: E402

STEP = 1.0 / 60.0
failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  [OK] {message}")
    else:
        print(f"  [失败] {message}")
        failures.append(message)


def pump(app: Application, seconds: float) -> None:
    for _ in range(int(seconds / STEP)):
        app._update(STEP)


def new_app(scene: str | None = None) -> Application:
    app = Application(AppOptions(scene=scene, headless=True, no_audio=True, max_seconds=600))
    app.stack.flush()
    return app


def main() -> int:
    print("1) 开始界面 → Scene 01")
    app = new_app()
    check(app.stack.top is not None and app.stack.top.scene_id == "title", "启动后停在开始界面")
    before = len(app.state.read_lines)
    app.stack.handle_event(InputEvent(InputKind.CONFIRM))
    app.stack.update(STEP)
    check(app.stack.top.scene_id == "s01", "确认后进入 Scene 01")

    print("2) 按住 Ctrl 快进")
    app.stack.handle_event(InputEvent(InputKind.FAST_FORWARD_START))
    for _ in range(int(40 / STEP)):
        app._update(STEP)
        if app.stack.top.scene_id != "s01":
            break
    app.stack.handle_event(InputEvent(InputKind.FAST_FORWARD_END))
    check(len(app.state.read_lines) > before, "快进期间已读记录在增长（对话在推进）")

    print("3) Esc → 二次确认 → 回开始界面")
    app.stack.handle_event(InputEvent(InputKind.CANCEL))
    scene = app.stack.top
    check(getattr(scene, "_confirm", None) is not None, "Esc 弹出二次确认")
    app.stack.handle_event(InputEvent(InputKind.MENU_RIGHT))   # 选中「是」
    app.stack.handle_event(InputEvent(InputKind.CONFIRM))
    app.stack.update(STEP)
    check(app.stack.top.scene_id == "title", "确认后回到开始界面")
    check(len(app.state.read_lines) == 0, "回开始界面后已读记录清空（状态干净）")

    print("4) 「继续」置灰")
    menu = app.stack.top._menu
    ids = [item["id"] for item in menu._items if item.get("enabled", True)]
    check("continue" not in ids, "继续项本轮禁用")
    check("start" in ids and "settings" in ids and "quit" in ids, "开始 / 设置 / 退出可用")

    print("5) 单独启动 Scene 07 → 交接 → 生存占位")
    app.stack.handle_event(InputEvent(InputKind.CANCEL))  # 关闭确认框（若有）
    app.shutdown_quietly() if hasattr(app, "shutdown_quietly") else app._shutdown()
    app2 = new_app("07")
    check(app2.stack.top.scene_id == "s07", "--scene 07 单独启动成功")
    app2.state.flags["autoplay"] = True
    scene = app2.stack.top
    if hasattr(scene, "director") and scene.director is not None:
        scene.director.autoplay = True
    for _ in range(int(120 / STEP)):
        app2._update(STEP)
        if app2.stack.top.scene_id == "sandbox":
            break
    check(app2.stack.top.scene_id == "sandbox", "Scene 07 结束后进入沙盒玩法场景")
    top = app2.stack.top
    check(getattr(top, "_world", None) is not None, "沙盒世界已生成")
    check(getattr(top, "_inventory", None) is not None
          and top._inventory.count("copper_pickaxe") == 1, "沙盒初始装备就位")
    app2._shutdown()

    print("6) 退出后重建")
    app3 = new_app()
    check(app3.state.current_scene_id == "title", "重新启动回到开始界面")
    check(app3.state.read_lines == set(), "重新启动没有残留已读记录")
    app3._shutdown()

    print()
    if failures:
        print(f"共 {len(failures)} 项未通过：")
        for item in failures:
            print("  -", item)
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
