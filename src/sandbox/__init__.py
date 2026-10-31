"""沙盒玩法：地块定义、物品定义、合成配方、世界、物理、背包。

与序章部分解耦：这里只依赖 core 的渲染/输入抽象和 data 里的 JSON。
"""

from .defs import Defs, ItemDef, Recipe, TileDef
from .inventory import Inventory, Stack
from .world import World

__all__ = ["Defs", "TileDef", "ItemDef", "Recipe", "World", "Inventory", "Stack"]
