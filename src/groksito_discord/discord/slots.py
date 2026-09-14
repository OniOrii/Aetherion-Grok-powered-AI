"""Fair Aetherion slots. Reels are weighted RNG in this file, never Grok."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import secrets
from typing import Mapping

AETHER = "\u2726"

SYMBOLS: dict[str, str] = {
    "comet": "\u2604\ufe0f",
    "void": "\U0001F30C",
    "shard": "\U0001F9FF",
    "moon": "\U0001F319",
    "star": "\u2728",
    "coin": "\U0001F52E",
}

LABELS: dict[str, str] = {
    "comet": "Comet",
    "void": "Rift",
    "shard": "Ward",
    "moon": "Moon",
    "star": "Stardust",
    "coin": "Aether Core",
}

SPIN_GLYPH = "\u2728"
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
    glyphs: Mapping[str, str]


NEBULA = Machine(
    key="nebula",
    name="Nebula",
    blurb="Soft lights. Hits often, pays small.",
    emoji="\U0001F52E",
    color=0x6B5B95,
    weights={"comet": 22, "void": 20, "shard": 18, "moon": 16, "star": 14, "coin": 10},
    pays={
        "comet": (8.0, 2.8),
        "void": (10.0, 3.0),
        "shard": (14.0, 3.2),
        "moon": (18.0, 3.6),
        "star": (24.0, 4.0),
        "coin": (32.0, 4.8),
    },
    glyphs={
        "comet": "\U0001F386",
        "void": "\U0001F30C",
        "shard": "\U0001F48E",
        "moon": "\U0001F52E",
        "star": "\U0001F49C",
        "coin": "\U0001F9FF",
    },
)

COSMOS = Machine(
    key="cosmos",
    name="Cosmos Wheel",
    blurb="The house wheel. Balanced spin.",
    emoji="\U0001FA90",
    color=0xC9A227,
    weights={"comet": 22, "void": 19, "shard": 17, "moon": 16, "star": 15, "coin": 11},
    pays={
        "comet": (10.0, 2.4),
        "void": (12.0, 2.6),
        "shard": (16.0, 3.0),
        "moon": (20.0, 3.4),
        "star": (28.0, 4.0),
        "coin": (44.0, 5.0),
    },
    glyphs={
        "comet": "\u2604\ufe0f",
        "void": "\U0001FA90",
        "shard": "\U0001F31F",
        "moon": "\U0001F315",
        "star": "\u2728",
        "coin": "\U0001FA99",
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
        "comet": (10.0, 1.6),
        "void": (14.0, 1.8),
        "shard": (20.0, 2.2),
        "moon": (32.0, 2.8),
        "star": (56.0, 4.0),
        "coin": (140.0, 6.0),
    },
    glyphs={
        "comet": "\u26A1",
        "void": "\U0001F573\ufe0f",
        "shard": "\u26AB",
        "moon": "\U0001F311",
        "star": "\U0001F608",
        "coin": "\U0001F300",
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


def blur_grid(machine: Machine) -> list[list[str]]:
    return [[_pick(machine.weights) for _ in range(3)] for _ in range(3)]


def coins(amount: int | str) -> str:
    return f"{AETHER} {amount}"


def format_cells(
    grid: list[list[str]],
    *,
    tag: str,
    spinning: bool = False,
    glyphs: Mapping[str, str] | None = None,
) -> str:
    table = glyphs or SYMBOLS
    rows = []
    for i, row in enumerate(grid):
        marks = [SPIN_GLYPH if spinning else table.get(s, SYMBOLS.get(s, "?")) for s in row]
        body = "[  {}    {}    {}  ]".format(*marks)
        if i == 1:
            rows.append(f"{body}   `{tag}`")
        else:
            rows.append(body)
    return "\n\n".join(rows)


def format_grid(result: SpinResult) -> str:
    tag = f"{result.multiplier:g}x" if result.multiplier > 0 else "0x"
    return format_cells(result.grid, tag=tag, glyphs=result.machine.glyphs)


def spinning_cells() -> str:
    dummy = [["coin"] * 3 for _ in range(3)]
    return format_cells(dummy, tag="\u2026", spinning=True)


def payouts_text(machine: Machine) -> str:
    table = machine.glyphs or SYMBOLS
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
        three, _pair = machine.pays[key]
        g = table.get(key, SYMBOLS[key])
        lines.append(f"{g} {g} {g}  \u2014  {three:g}x  ({LABELS[key]})")
    lines.append("")
    lines.append("**Any pair** on the middle line")
    for key in order:
        _three, pair = machine.pays[key]
        g = table.get(key, SYMBOLS[key])
        lines.append(f"{g} {g} \u00b7  \u2014  {pair:g}x")
    return "\n".join(lines)
