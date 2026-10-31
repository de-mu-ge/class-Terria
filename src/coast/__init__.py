"""海岸世界（Coastal World V0.1）。"""

from .daycycle import DayCycle
from .defs import CoastDefs
from .entities import Bird, Crab, FishSchool, Prop, PropWorld
from .inventory import CoastInventory, Stack
from .player import CoastPhysics, CoastPlayer
from .textures import ItemIcons, TileTextures
from .world import CoastWorld

__all__ = [
    "Bird",
    "CoastDefs",
    "CoastInventory",
    "CoastPhysics",
    "CoastPlayer",
    "CoastWorld",
    "Crab",
    "DayCycle",
    "FishSchool",
    "ItemIcons",
    "Prop",
    "PropWorld",
    "Stack",
    "TileTextures",
]
