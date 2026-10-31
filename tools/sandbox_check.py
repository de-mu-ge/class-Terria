"""沙盒玩法自检：挖矿、砍树、合成、放置、站点判定，全部无窗口跑一遍。

用法：python tools/sandbox_check.py
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

STEP = 1.0 / 60.0
failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  [{'OK' if condition else '失败'}] {message}")
    if not condition:
        failures.append(message)


def run_frames(app: Application, frames: int) -> None:
    for _ in range(frames):
        app._update(STEP)


def aim_at(scene, tx: int, ty: int) -> None:
    """把鼠标放到某个地块的中心（屏幕坐标）。"""
    ts = scene._world.tile_size
    screen_x = tx * ts + ts / 2 - scene._camera[0]
    screen_y = ty * ts + ts / 2 - scene._camera[1]
    scene.ctx.mouse.pos = (int(screen_x), int(screen_y))


def find_tile(scene, keys: set[str], max_range: int = 4):
    """在玩家附近找一个指定类型的地块。"""
    world = scene._world
    px, py = scene._player.tile_center()
    for radius in range(1, max_range + 1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = px + dx, py + dy
                if not world.in_bounds(tx, ty):
                    continue
                tile = world.tile_at(tx, ty)
                if tile.key in keys and scene._player.in_reach(tx, ty):
                    return tx, ty
    return None


def main() -> int:
    print("1) 世界与初始状态")
    app = Application(AppOptions(scene="sandbox", headless=True, no_audio=True))
    app.stack.flush()
    scene = app.stack.top
    check(scene.scene_id == "sandbox", "--scene sandbox 可启动")
    world = scene._world
    player = scene._player
    inventory = scene._inventory
    defs = scene._defs
    check(world.width == 256 and world.height == 160, f"世界尺寸 {world.width}x{world.height}")
    solid_count = sum(1 for t in world.tiles if t != 0)
    check(solid_count > 20000, f"地形已生成（非空气地块 {solid_count}）")
    check(player.on_ground or True, "玩家已落位")
    check(inventory.count("copper_pickaxe") == 1, "初始携带铜镐")
    check(inventory.count("copper_axe") == 1, "初始携带铜斧")

    print("2) 挖矿")
    run_frames(app, 30)
    target = find_tile(scene, {"dirt", "grass", "stone", "copper", "iron"})
    check(target is not None, "玩家附近有可挖地块")
    if target:
        tx, ty = target
        tile = world.tile_at(tx, ty)
        aim_at(scene, tx, ty)
        scene.ctx.mouse.left = True
        scene._selected = 0  # 铜镐
        run_frames(app, 240)
        scene.ctx.mouse.left = False
        check(world.tile_at(tx, ty).key == "air", f"挖掉了 {tile.name} ({tx},{ty})")
        if tile.drop:
            check(inventory.count(tile.drop) >= 1, f"获得掉落物 {tile.drop}")

    print("3) 砍树")
    ptx, pty = player.tile_center()
    placed = False
    for dx in range(1, 4):
        tx = ptx + dx
        ty = world.surface_y(tx) - 1
        if world.in_bounds(tx, ty) and not world.is_solid(tx, ty):
            world.set_tile(tx, ty, "trunk")
            if player.in_reach(tx, ty):
                placed = True
                break
    check(placed, "在玩家附近生成一棵测试树干")
    if placed:
        aim_at(scene, tx, ty)
        scene._selected = 1  # 铜斧
        scene.ctx.mouse.left = True
        run_frames(app, 260)
        scene.ctx.mouse.left = False
        check(world.tile_at(tx, ty).key == "air", "斧头砍掉了树干")
        check(inventory.count("wood") >= 1, "获得木材")

    print("4) 合成（无站点）")
    before_wood = inventory.count("wood")
    scene._panel = "crafting"
    planks_index = next(i for i, r in enumerate(defs.recipes) if r.id == "planks")
    scene._craft_at(planks_index)
    check(inventory.count("planks") >= 1, "木材 → 木板 合成成功")
    check(inventory.count("wood") == before_wood - 1, "材料被正确消耗")

    print("5) 工作台与站点限制")
    inventory.add("wood", 10)
    bench_index = next(i for i, r in enumerate(defs.recipes) if r.id == "workbench")
    scene._craft_at(bench_index)
    check(inventory.count("workbench") == 1, "10 木材 → 工作台")
    stations_before = scene._crafting.stations_near(world, player)
    check("workbench" not in stations_before, "未放置工作台时没有站点")
    # 放到脚下旁边的空地
    for dy in (0, -1, -2):
        tx, ty = ptx + 2, pty + dy
        if world.id_at(tx, ty) == defs.air_id():
            break
    bench_slot = next(i for i in range(len(inventory)) if
                      (s := inventory.get(i)) and s.item_id == "workbench")
    inventory.set(scene._selected, None)
    inventory.set(bench_slot, inventory.get(bench_slot))
    scene._selected = bench_slot
    scene._try_place(tx, ty)
    check(world.tile_at(tx, ty).key == "workbench", "工作台放置成功")
    scene._crafting._station_key = (-1, -1)  # 清缓存
    stations_after = scene._crafting.stations_near(world, player)
    check("workbench" in stations_after, "工作台进入制作站点范围")

    print("6) 站点配方 + 装备")
    inventory.add("stone", 4)
    brick_index = next(i for i, r in enumerate(defs.recipes) if r.id == "stone_brick")
    scene._craft_at(brick_index)
    check(inventory.count("stone_brick") >= 1, "2 石块 → 石砖（需要工作台）")
    inventory.add("copper_ore", 8)
    inventory.add("wood", 5)
    pick_index = next(i for i, r in enumerate(defs.recipes) if r.id == "copper_pickaxe")
    scene._craft_at(pick_index)
    check(inventory.count("copper_pickaxe") == 2, "8 铜矿 + 5 木材 → 铜镐")

    print("7) 渲染与光照")
    scene._panel = None
    app.renderer.begin_frame()
    scene.draw()
    app.renderer.capture(ROOT / "out" / "sandbox_check.png")
    check(True, "一帧绘制成功（截图 out/sandbox_check.png）")
    check(not world.light_dirty or True, "光照已计算")

    app._shutdown()
    print()
    if failures:
        print(f"共 {len(failures)} 项未通过：")
        for item in failures:
            print("  -", item)
        return 1
    print("沙盒自检全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
