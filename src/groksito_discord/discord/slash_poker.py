"""Texas Hold'em for 2-4 seats. Friends and/or Aetherion. Aether Coin buy-in."""
from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, field
from itertools import combinations
from random import SystemRandom

import discord

from . import ai_coins
from .poker_table import render_hole_png, render_table_png

logger = logging.getLogger("aetherion.slash_poker")

_rng = SystemRandom()

BOT_ID = 0
BOT_NAME = "Aetherion"
MAX_SEATS = 4
TABLE_NAME = "poker.png"
HOLE_NAME = "hole.png"
THINK_SLEEP = 0.7

EMBED_WAIT = 0xC9A227
EMBED_PLAY = 0x3D6B9B
EMBED_WIN = 0x3D9B64
EMBED_DEAD = 0xC45C4A

RANKS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
SUITS = ["S", "H", "D", "C"]
RANK_SYM = {11: "J", 12: "Q", 13: "K", 14: "A"}
SUIT_SYM = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}

HAND_NAMES = (
    "High card",
    "Pair",
    "Two pair",
    "Three of a kind",
    "Straight",
    "Flush",
    "Full house",
    "Four of a kind",
    "Straight flush",
)

_tables: dict[int, "Table"] = {}
_by_user: dict[int, int] = {}
_next_id = 1
_last_bet: dict[int, int] = {}


def _new_id() -> int:
    global _next_id
    gid = _next_id
    _next_id += 1
    return gid


def _card_label(card) -> str:
    rank, suit = card
    return f"{RANK_SYM.get(rank, str(rank))}{SUIT_SYM[suit]}"


def _hole_text(seat: "Seat") -> str:
    return " ".join(_card_label(c) for c in seat.hole) if seat.hole else "-"


def _new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    _rng.shuffle(deck)
    return deck


def _hand_score(cards) -> tuple:
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    straight = False
    top = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight = True
            top = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight = True
            top = 5
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    groups = sorted(((n, r) for r, n in counts.items()), reverse=True)
    kick = tuple(
        r
        for n, r in sorted(((n, r) for r, n in counts.items()), key=lambda x: (x[0], x[1]), reverse=True)
        for _ in range(n)
    )
    if straight and flush:
        return (8, top)
    if groups[0][0] == 4:
        return (7, groups[0][1], groups[1][1])
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *ranks)
    if straight:
        return (4, top)
    if groups[0][0] == 3:
        return (3, groups[0][1], *kick)
    if groups[0][0] == 2 and groups[1][0] == 2:
        high_p = max(groups[0][1], groups[1][1])
        low_p = min(groups[0][1], groups[1][1])
        kicker = groups[2][1]
        return (2, high_p, low_p, kicker)
    if groups[0][0] == 2:
        return (1, groups[0][1], *kick)
    return (0, *ranks)


def best_hand(hole, board) -> tuple:
    pool = list(hole) + list(board)
    if len(pool) < 5:
        return _hand_score((pool + [(0, "S")] * 5)[:5])
    return max(_hand_score(combo) for combo in combinations(pool, 5))


def _strength(hole, board) -> float:
    if not hole:
        return 0.0
    if len(board) < 3:
        a, b = hole[0][0], hole[1][0]
        hi, lo = max(a, b), min(a, b)
        pair = 0.62 if a == b else 0.0
        suited = 0.08 if hole[0][1] == hole[1][1] else 0.0
        connected = 0.06 if abs(a - b) in (1, 2) else 0.0
        high = (hi - 2) / 12 * 0.38
        return min(0.96, pair + suited + connected + high + (0.04 if lo >= 10 else 0))
    score = best_hand(hole, board)
    return min(0.99, 0.08 + score[0] / 8 * 0.82 + (score[1] if len(score) > 1 else 0) / 140)


def _blinds(buyin: int) -> tuple[int, int]:
    if buyin < 40:
        return 0, 0
    return 10, 20


def _raise_step(buyin: int) -> int:
    _sb, bb = _blinds(buyin)
    return bb if bb else 10
