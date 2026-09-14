"""Fair Aether coin toss. Heads, tails, or a rare side landing."""
from __future__ import annotations

from dataclasses import dataclass
import secrets

AETHER = "\u2726"

HEADS = "heads"
TAILS = "tails"
SIDE = "side"

WIN_MULTI = 2.0
SIDE_MULTI = 2.5

TOSS_MIN_BET = 10
TOSS_DEFAULT_BET = 100
TOSS_MAX_BET = 10_000

FACE_LABEL = {HEADS: "Heads", TAILS: "Tails", SIDE: "its Side"}

# Exactly 48% heads, 48% tails, 2% side.
_BAG = [SIDE] * 2 + [HEADS] * 48 + [TAILS] * 48


@dataclass
class TossResult:
    pick: str
    landed: str
    bet: int
    multiplier: float
    winnings: int
    net: int
    won: bool


def flip(pick: str, bet: int) -> TossResult:
    pick = pick if pick in (HEADS, TAILS) else HEADS
    bet = int(bet)
    landed = secrets.choice(_BAG)
    if landed == SIDE:
        multi = SIDE_MULTI
        won = True
    elif landed == pick:
        multi = WIN_MULTI
        won = True
    else:
        multi = 0.0
        won = False
    winnings = int(bet * multi) if multi else 0
    return TossResult(
        pick=pick,
        landed=landed,
        bet=bet,
        multiplier=multi,
        winnings=winnings,
        net=winnings - bet,
        won=won,
    )


def coins(amount: int | str) -> str:
    return f"{AETHER} {amount}"


def result_line(result: TossResult) -> str:
    pick = FACE_LABEL[result.pick]
    land = FACE_LABEL[result.landed]
    if result.landed == SIDE:
        mark = "\u2726"
    elif result.won:
        mark = "\u2705"
    else:
        mark = "\u274c"
    return f"You picked **{pick}**, it landed on **{land}** {mark}"
