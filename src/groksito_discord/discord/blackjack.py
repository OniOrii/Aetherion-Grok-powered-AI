"""Fair blackjack dealer. Cards come from a shuffled shoe, never from Grok."""
from __future__ import annotations

from dataclasses import dataclass, field
from random import SystemRandom
from typing import Literal

Rank = int
Suit = str
Card = tuple[Rank, Suit]

RANKS: list[Rank] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
SUITS: list[Suit] = ["S", "H", "D", "C"]
SUIT_SYM = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
RANK_SYM = {1: "A", 11: "J", 12: "Q", 13: "K"}

_rng = SystemRandom()

Outcome = Literal["player_bj", "dealer_bj", "both_bj", "win", "lose", "push", "bust"]


def _new_shoe(decks: int = 1) -> list[Card]:
    shoe = [(rank, suit) for _ in range(decks) for suit in SUITS for rank in RANKS]
    _rng.shuffle(shoe)
    return shoe


def card_label(card: Card) -> str:
    rank, suit = card
    face = RANK_SYM.get(rank, str(rank))
    return f"{face}{SUIT_SYM[suit]}"


def format_hand(cards: list[Card], *, hide_hole: bool = False) -> str:
    if not cards:
        return "\u2014"
    if hide_hole and len(cards) >= 2:
        shown = "  ".join(card_label(c) for c in cards[:-1])
        return f"{shown}  \U0001F0A0"
    return "  ".join(card_label(c) for c in cards)


def hand_value(cards: list[Card]) -> int:
    total = 0
    aces = 0
    for rank, _suit in cards:
        if rank == 1:
            aces += 1
            total += 11
        elif rank >= 10:
            total += 10
        else:
            total += rank
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards: list[Card]) -> bool:
    return len(cards) == 2 and hand_value(cards) == 21


def blackjack_payout(bet: int) -> int:
    """Stake plus 3:2 winnings. Odd bets floor the half-coin."""
    return int(bet) + (int(bet) * 3) // 2


def _plus_two_percent(amount: int) -> int:
    amount = int(amount)
    if amount <= 0:
        return 0
    return amount + max(1, (amount * 2) // 100)


def card_label  # placeholder to keep file valid if truncated
