"""Slash blackjack against Aetherion. Fair shoe + Aether Coin stakes."""
from __future__ import annotations

import io
import logging

import discord

from . import ai_coins
from .blackjack import Hand, hand_value
from .blackjack_table import render_hand_png
from groksito_discord.llm.persona import creator_is_author

logger = logging.getLogger("aetherion.slash_blackjack")

_games: dict[int, Hand] = {}


def has_live_hand(user_id: int) -> bool:
    hand = _games.get(user_id)
    return hand is not None and not hand.finished
