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


@dataclass
class Hand:
    user_id: int
    bet: int
    shoe: list[Card] = field(default_factory=_new_shoe)
    player: list[Card] = field(default_factory=list)
    dealer: list[Card] = field(default_factory=list)
    doubled: bool = False
    finished: bool = False
    outcome: Outcome | None = None

    def deal_opening(self) -> None:
        self.player.append(self.shoe.pop())
        self.dealer.append(self.shoe.pop())
        self.player.append(self.shoe.pop())
        self.dealer.append(self.shoe.pop())
        self._resolve_naturals()

    def _resolve_naturals(self) -> None:
        p_bj = is_blackjack(self.player)
        d_bj = is_blackjack(self.dealer)
        # Only a player natural ends the hand on the deal.
        # Dealer blackjack stays hole-card-down until the player acts.
        if p_bj and d_bj:
            self.finished = True
            self.outcome = "both_bj"
        elif p_bj:
            self.finished = True
            self.outcome = "player_bj"

    def hit(self) -> None:
        if self.finished:
            return
        self.player.append(self.shoe.pop())
        if hand_value(self.player) > 21:
            self.finished = True
            self.outcome = "bust"

    def stand(self) -> None:
        if self.finished:
            return
        self._dealer_play()
        self._compare()

    def double(self) -> None:
        if self.finished or self.doubled or len(self.player) != 2:
            return
        self.doubled = True
        self.bet *= 2
        self.player.append(self.shoe.pop())
        if hand_value(self.player) > 21:
            self.finished = True
            self.outcome = "bust"
            return
        self._dealer_play()
        self._compare()

    def _dealer_play(self) -> None:
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.shoe.pop())

    def _compare(self) -> None:
        self.finished = True
        p = hand_value(self.player)
        d = hand_value(self.dealer)
        if p > 21:
            self.outcome = "bust"
        elif is_blackjack(self.dealer) and not is_blackjack(self.player):
            self.outcome = "dealer_bj"
        elif d > 21 or p > d:
            self.outcome = "win"
        elif p < d:
            self.outcome = "lose"
        else:
            self.outcome = "push"

    def credit(self) -> int:
        if self.outcome in ("player_bj",):
            return _plus_two_percent(blackjack_payout(self.bet))
        if self.outcome in ("win",):
            return _plus_two_percent(self.bet * 2)
        if self.outcome in ("push", "both_bj"):
            return self.bet
        return 0

    def result_line(self) -> str:
        labels = {
            "player_bj": "Blackjack. You win 3:2.",
            "dealer_bj": "Dealer blackjack. You lose.",
            "both_bj": "Both blackjack. Push.",
            "win": "You win.",
            "lose": "Dealer wins.",
            "push": "Push.",
            "bust": "Bust.",
        }
        return labels.get(self.outcome or "", "Hand over.")
