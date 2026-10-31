"""海岸世界自检：地形、移动、游泳、采集、放置、制作、储物、昼夜。

用法：python tools/coast_check.py
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
    print(f"  [{'OK' if condition else '失败'}] {message}")
    if not condition:
        failures.append(message)


def frames(app, count: int) -> None:
    for _ in range(count):
        app._update(STEP)


def main() -> int:
    app = Application(AppOptions(scene="coast", headless=True, no_audio=True))
    app.stack.flush()
    scene = app.stack.top
    world = scene._world
    player = scene._player
    inventory = scene._inventory
    defs = scene._defs

    print("1) 世界结构")
    check(scene.scene_id == "coast", "--scene coast 可启动")
    check(world.width == 320 and world.height == 180, f"世界 {world.width}x{world.height}")
    solid = sum(1 for t in world.tiles if t != 0)
    check(solid > 20000, f"地形已生成（实心格 {solid}）")
    check(len(world.cave_air) > 200, f"洞穴空腔 {len(world.cave_air)} 格")
    zones = {"beach": 0, "intertidal": 0, "shallow": 0, "seabed": 0, "reef": 0,
             "deep": 0, "cave": 0}
    for tx in range(2, world.width - 2, 3):
        surface = world.surface_y(tx)
        if surface > 1:
            zone = world.zone_at(tx, surface - 1)
            if zone in zones:
                zones[zone] += 1
    print("     分区抽样:", {k: v for k, v in zones.items() if v})
    check(zones["beach"] > 0 and zones["intertidal"] > 0 and zones["shallow"] > 0,
          "海滩 / 潮间带 / 浅海 三类区域都存在")
    check(zones["reef"] > 0 and zones["deep"] > 0, "礁石区与深水区存在")
    check(len(scene._props.props) > 60, f"生态对象 {len(scene._props.props)} 个")
    check(len(scene._fish) >= 5 and len(scene._birds) >= 3, "鱼群与海鸟已生成")

    print("2) 陆地移动与跳跃")
    start_x = player.x
    app.keys.press("left")
    frames(app, 40)
    app.keys.release("left")
    check(player.x < start_x - 20, f"向左走了 {start_x - player.x:.0f}px")
    frames(app, 20)
    check(player.on_ground, "落地后 on_ground=True")
    ground_y = player.y
    app.keys.press("jump")
    frames(app, 12)
    app.keys.release("jump")
    check(player.y < ground_y - 10, "空格起跳有效")
    frames(app, 90)
    check(abs(player.y - ground_y) < 40, "跳跃后落回地面")

    print("3) 下水与游泳")
    swim_x = None
    for tx in range(int(world.beach_cfg.get("end", 132)) + 20, world.width - 20):
        if world.surface_y(tx) - world.sea_level >= 14:
            swim_x = tx
            break
    if swim_x is None:
        swim_x = int(world.width * 0.85)
    player.spawn(swim_x, int(world.sea_level) + 3)
    frames(app, 40)
    check(player.in_water, "进入水体后 in_water=True")
    depth_before = player.y
    app.keys.press("jump")
    frames(app, 45)
    app.keys.release("jump")
    check(player.y < depth_before - 10, f"上浮有效（{depth_before - player.y:.0f}px）")
    depth_mid = player.y
    app.keys.press("down")
    frames(app, 45)
    app.keys.release("down")
    check(player.y > depth_mid + 5, "下潜有效")
    check(abs(player.vy) <= 200, "水下速度被限制（阻力/浮力生效）")

    print("4) 采集")
    inventory.slots = [None] * len(inventory.slots)
    prop = next(p for p in scene._props.props
                if not p.harvested and defs.obj(p.obj_id).kind == "harvestable")
    obj = defs.obj(prop.obj_id)
    player.x = prop.x
    player.y = world.surface_y(int(prop.x // world.tile_size)) * world.tile_size
    frames(app, 6)
    check(scene._focus is prop, f"靠近后锁定目标：{obj.name}")
    scene.handle_event(InputEvent(InputKind.KEY, key="e"))
    check(prop.harvested, "按 E 完成采集")
    gained = inventory.count(obj.harvest.item)
    check(gained >= obj.harvest.count, f"获得 {obj.harvest.item} ×{gained}")

    print("5) 放置营地设施")
    inventory.add("campfire", 1)
    slot = inventory.first_slot_of("campfire")
    scene._ui.selected = slot
    before = len(scene._props.props)
    scene.handle_event(InputEvent(InputKind.KEY, key="f"))
    check(len(scene._props.props) == before + 1, "按 F 放置了篝火")
    placed = scene._props.props[-1]
    check(placed.obj_id == "campfire", "放置物类型正确")
    check(placed.lit, "篝火默认点燃")
    check(len(scene._props.lights()) > 0, "篝火进入光源列表")
    scene._focus = placed
    scene.handle_event(InputEvent(InputKind.KEY, key="e"))
    check(not placed.lit, "按 E 可以熄灭篝火")

    print("6) 制作")
    inventory.add("wood", 6)
    inventory.add("fiber", 2)
    before_torch = inventory.count("torch")
    torch_index = next(i for i, r in enumerate(defs.recipes) if r.id == "torch")
    scene._craft(torch_index)
    check(inventory.count("torch") == before_torch + 2, "2 木材 + 1 纤维 → 火把 ×2")

    print("7) 储物箱")
    inventory.add("chest", 1)
    slot = inventory.first_slot_of("chest")
    scene._ui.selected = slot
    scene.handle_event(InputEvent(InputKind.KEY, key="f"))
    chest = scene._props.props[-1]
    check(chest.obj_id == "chest", "放置了储物箱")
    scene._focus = chest
    scene.handle_event(InputEvent(InputKind.KEY, key="e"))
    check(scene._panel == "chest", "按 E 打开了储物箱")
    inventory.add("shell", 3)
    shell_slot = inventory.first_slot_of("shell")
    scene._chest_deposit(shell_slot)
    check(any(slot and slot.item_id == "shell" for slot in chest.storage), "贝壳已存入")
    scene._chest_click(0)
    check(inventory.count("shell") == 3, "从箱子取回贝壳")
    scene.handle_event(InputEvent(InputKind.KEY, key="i"))
    check(scene._panel == "inventory", "I 打开行囊")
    scene.handle_event(InputEvent(InputKind.CANCEL))
    check(scene._panel is None, "Esc 关闭面板")

    print("8) 昼夜与潮汐")
    t0 = scene._cycle.time
    frames(app, 120)
    check(scene._cycle.time > t0, "时间在推进")
    levels = []
    for step in range(4):
        scene._elapsed += 40.0
        world.update_tide(scene._elapsed)
        levels.append(round(world.sea_level, 2))
    check(max(levels) - min(levels) > 0.3, f"潮汐有涨落：{levels}")

    print("9) 渲染")
    app.renderer.begin_frame()
    scene.draw()
    app.renderer.capture(ROOT / "out" / "coast_check.png")
    check(True, "一帧绘制成功（out/coast_check.png）")

    app._shutdown()
    print()
    if failures:
        print(f"共 {len(failures)} 项未通过：")
        for item in failures:
            print("  -", item)
        return 1
    print("海岸世界自检全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
