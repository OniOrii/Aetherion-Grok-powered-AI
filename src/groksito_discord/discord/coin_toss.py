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
SIDE_CHANCE = 15  # out of 1000 — 1.5%

TOSS_MIN_BET = 10
TOSS_DEFAULT_BET = 100
TOSS_MAX_BET = 10_000

FACE_LABEL = {HEADS: "Heads", TAILS: "Tails", SIDE: "its Side"}


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
    roll = secrets.randbelow(1000)
    if roll < SIDE_CHANCE:
        landed = SIDE
        multi = SIDE_MULTI
        won = True
    else:
        landed = HEADS if secrets.randbelow(2) == 0 else TAILS
        if landed == pick:
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
