"""Odds math for /highlow. No Discord."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from groksito_discord.discord.higher_lower import (  # noqa: E402
    HOUSE,
    RANK_COUNT,
    HighLowRound,
    multiplier,
    next_pot,
    side_wins,
)


def test_edges_have_no_impossible_side():
    assert multiplier("A", "higher") == 0.0
    assert multiplier("2", "lower") == 0.0
    assert side_wins("A", "higher") == 0
    assert side_wins("2", "lower") == 0


def test_mid_card_is_near_even_money():
    hi = multiplier("8", "higher")
    lo = multiplier("8", "lower")
    assert hi == lo
    assert 1.9 <= hi <= 2.0


def test_hard_call_pays_more_than_safe_call():
    assert multiplier("K", "higher") > multiplier("3", "higher")
    assert multiplier("3", "lower") > multiplier("K", "lower")


def test_each_priced_side_has_house_edge():
    for rank in ("2", "3", "8", "Q", "K", "A"):
        for side in ("higher", "lower"):
            wins = side_wins(rank, side)
            multi = multiplier(rank, side)
            if wins <= 0:
                assert multi == 0.0
                continue
            ev = (wins / RANK_COUNT) * multi
            assert abs(ev - HOUSE) < 0.02


def test_resolve_same_rank_misses():
    game = HighLowRound(user_id=1, bet=100, card="8")
    game.resolve("higher", "8")
    assert game.finished
    assert game.outcome == "same"
    assert game.credit() == 0


def test_resolve_win_then_cash():
    game = HighLowRound(user_id=1, bet=100, card="8")
    game.resolve("higher", "K")
    assert game.outcome == "win"
    assert game.pot == next_pot(100, multiplier("8", "higher"))
    game.cash()
    assert game.outcome == "cash"
    assert game.credit() == game.pot
