"""Slash blackjack against Aetherion. Fair shoe + Aether Coin stakes."""
from __future__ import annotations

import io
import logging

import discord

from . import ai_coins
from . import aether_hunt as hunt
from . import aether_hunt_ext  # noqa: F401
from .blackjack import Hand, hand_value
from .blackjack_table import render_hand_png
from groksito_discord.llm.persona import creator_is_author

logger = logging.getLogger("aetherion.slash_blackjack")

_games: dict[int, Hand] = {}
_last_bet: dict[int, int] = {}


def has_live_hand(user_id: int) -> bool:
    hand = _games.get(user_id)
    return hand is not None and not hand.finished


EMBED_PLAY = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
EMBED_PUSH = 0x8A8F98
TABLE_NAME = "blackjack.png"
