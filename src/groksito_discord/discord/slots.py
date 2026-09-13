"""Fair Aetherion slots. Reels are weighted RNG in this file, never Grok."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import secrets
from typing import Mapping

SYMBOLS: dict[str, str] = {
    "comet": "\u2604\ufe0f",
    "void": "\U0001F311",
    "shard": "\U0001F6E1",
    "moon": "\U0001F319",
    "star": "\u2B50",
    "coin": "\U0001FA99",
}

LABELS: dict[str, str] = {
    "comet": "Comet",
    "void": "Void",
    "shard": "Shard",
    "moon": "Moon",
    "star": "Star",
    "coin": "Aether Coin",
}

Paytable = dict[str, tuple[float, float]]


@dataclass(frozen=True)
class Machine:
    key: str
    name: str
    blurb: str
    emoji: str
    color: int
    weights: Mapping[str, int]
    pays: Paytable


NEBULA = Machine(
    key="nebula",
    name="Nebula",
    blurb="Soft lights. Hits often, pays small.",
    emoji="\U0001F49C",
    color=0x6B5B95,
    weights={"comet": 22, "void": 20, "shard": 18, "moon": 16, "star": 14, "coin": 10},
    pays={
        "comet": (4.0, 1.4),
        "void": (5.0, 1.5),
        "shard": (7.0, 1.6),
        "moon": (9.0, 1.8),
        "star": (12.0, 2.0),
        "coin": (16.0, 2.4),
    },
)

COSMOS = Machine(
    key="cosmos",
    name="Cosmos Wheel",
    blurb="The house wheel. Balanced spin.",
    emoji="\U0001F30C",
    color=0xC9A227,
    weights={"comet": 22, "void": 19, "shard": 17, "moon": 16, "star": 15, "coin": 11},
    pays={
        "comet": (5.0, 1.2),
        "void": (6.0, 1.3),
        "shard": (8.0, 1.5),
        "moon": (10.0, 1.7),
        "star": (14.0, 2.0),
        "coin": (22.0, 2.5),
    },
)

HORIZON = Machine(
    key="horizon",
    name="Event Horizon",
    blurb="Mostly dark. When it hits, it hits.",
    emoji="\U0001F573\ufe0f",
    color=0x3B1F4A,
    weights={"comet": 32, "void": 24, "shard": 18, "moon": 12, "star": 9, "coin": 5},
    pays={
        "comet": (5.0, 0.8),
        "void": (7.0, 0.9),
        "shard": (10.0, 1.1),
        "moon": (16.0, 1.4),
        "star": (28.0, 2.0),
        "coin": (70.0, 3.0),
    },
)

MACHINES: dict[str, Machine] = {
    NEBULA.key: NEBULA,
    COSMOS.key: COSMOS,
    HORIZON.key: HORIZON,
}
DEFAULT_MACHINE = COSMOS.key

SLOTS_MIN_BET = 100
SLOTS_DEFAULT_BET = 100
SLOTS_MAX_BET = 10_000


@dataclass
class SpinResult:
    machine: Machine
    grid: list[list[str]]
    line: tuple[str, str, str]
    multiplier: float
    bet: int
    winnings: int
    net: int


def _pick(weights: Mapping[str, int]) -> str:
    bag: list[str] = []
    for key, w in weights.items():
        bag.extend([key] * int(w))
    return secrets.choice(bag)


def _line_multiplier(machine: Machine, a: str, b: str, c: str) -> float:
    counts = Counter((a, b, c))
    if len(counts) == 1:
        return float(machine.pays[a][0])
    for symbol, n in counts.items():
        if n == 2:
            return float(machine.pays[symbol][1])
    return 0.0


def spin(machine: Machine, bet: int) -> SpinResult:
    bet = int(bet)
    grid = [[_pick(machine.weights) for _ in range(3)] for _ in range(3)]
    line = (grid[1][0], grid[1][1], grid[1][2])
    multi = _line_multiplier(machine, *line)
    winnings = int(bet * multi) if multi > 0 else 0
    return SpinResult(
        machine=machine,
        grid=grid,
        line=line,
        multiplier=multi,
        bet=bet,
        winnings=winnings,
        net=winnings - bet,
    )


def format_grid(result: SpinResult) -> str:
    rows = []
    for i, row in enumerate(result.grid):
        cells = " ".join(f"[ {SYMBOLS[s]} ]" for s in row)
        if i == 1:
            tag = f"  **{result.multiplier:g}x**" if result.multiplier > 0 else "  \u2014"
            rows.append(f"**\u00bb** {cells}{tag}")
        else:
            rows.append(f"    {cells}")
    return "\n".join(rows)


def payouts_text(machine: Machine) -> str:
    lines = [
        f"{machine.emoji} **{machine.name}**",
        machine.blurb,
        "",
        "Pays the middle line. Three of a kind, or any two matching.",
        "",
        "**Three of a kind**",
    ]
    order = ["coin", "star", "moon", "shard", "void", "comet"]
    for key in order:
        three, pair = machine.pays[key]
        lines.append(f"{SYMBOLS[key]} {SYMBOLS[key]} {SYMBOLS[key]}  \u2014  {three:g}x  ({LABELS[key]})")
    lines.append("")
    lines.append("**Any pair** on the middle line")
    for key in order:
        _three, pair = machine.pays[key]
        lines.append(f"{SYMBOLS[key]} {SYMBOLS[key]} \u00b7  \u2014  {pair:g}x")
    return "\n".join(lines)
