"""Aetherion Hunt WIP — original animals, zoo, team, and PvE battles.

Runtime save: data/aether_hunt.json. Play-money spends go through ai_coins.
Crates, huntbot, and public access are not in this slice.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from pathlib import Path
from typing import Any

from ..config import settings
from . import ai_coins

logger = logging.getLogger("aetherion.hunt")

HUNT_COST = 10
HUNT_COOLDOWN = 10
TEAM_SIZE = 3
LEVEL_CAP = 20
XP_PER_LEVEL = 25
WIN_PAYOUT = 20
DRAW_PAYOUT = 10
EMBED_GOLD = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
WIP_FOOTER = "WIP \u00b7 Test 1 \u00b7 Ori only \u00b7 crates later"

COMMON = "common"
UNCOMMON = "uncommon"
RARE = "rare"
EPIC = "epic"
MYTHIC = "mythic"

RARITY_ORDER = (COMMON, UNCOMMON, RARE, EPIC, MYTHIC)
RARITY_LABEL = {
    COMMON: "Common",
    UNCOMMON: "Uncommon",
    RARE: "Rare",
    EPIC: "Epic",
    MYTHIC: "Mythic",
}
RARITY_WEIGHT = {
    COMMON: 550,
    UNCOMMON: 270,
    RARE: 120,
    EPIC: 45,
    MYTHIC: 15,
}
RARITY_SELL = {
    COMMON: 10,
    UNCOMMON: 20,
    RARE: 40,
    EPIC: 80,
    MYTHIC: 150,
}
RARITY_BASE = {
    COMMON: (40, 8),
    UNCOMMON: (52, 11),
    RARE: (68, 15),
    EPIC: (88, 20),
    MYTHIC: (110, 26),
}

RARITY_LETTER = {
    COMMON: ("C", "\U0001f7e5"),
    UNCOMMON: ("U", "\U0001f7e9"),
    RARE: ("R", "\U0001f7e8"),
    EPIC: ("E", "\U0001f7e6"),
    MYTHIC: ("M", "\U0001f7ea"),
}
RARITY_POINTS = {
    COMMON: 1,
    UNCOMMON: 5,
    RARE: 20,
    EPIC: 250,
    MYTHIC: 3000,
}
ZOO_COLS = 5
