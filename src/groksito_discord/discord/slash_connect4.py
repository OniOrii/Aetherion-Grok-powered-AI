"""Connect Four: challenge a member or play Aetherion. Aether Coin stakes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .connect4_board import (
    COLS,
    EMPTY,
    P1,
    P2,
    ROWS,
    choose_column,
)

logger = logging.getLogger("aetherion.slash_connect4")

DISC = {EMPTY: "\u26ab", P1: "\U0001f534", P2: "\U0001f7e1"}
TABLE_NAME = "connect4.gif"
THINK_SLEEP = 0.65

EMBED_WAIT = 0xC9A227
EMBED_PLAY = 0x3D6B9B
EMBED_WIN = 0x3D9B64
EMBED_DRAW = 0x8A8F98
EMBED_DEAD = 0xC45C4A

_games: dict[int, "Match"] = {}
_by_user: dict[int, int] = {}
_next_id = 1
_last_bet: dict[int, int] = {}


def _new_id() -> int:
    global _next_id
    gid = _next_id
    _next_id += 1
    return gid


def _player_busy(user_id: int) -> bool:
    gid = _by_user.get(user_id)
    if gid is None:
        return False
    match = _games.get(gid)
    return match is not None and not match.finished


@dataclass
class Match:
    id: int
    guild_id: int
    channel_id: int
    p1: int
    p2: int
    p1_name: str
    p2_name: str
    bet: int
    vs_bot: bool = False
    busy: bool = False
    held: bool = False
    turn: int = P1
    board: list[list[int]] = field(default_factory=lambda: [[EMPTY] * COLS for _ in range(ROWS)])
    finished: bool = False
    winner: int = 0
    reason: str = ""
    last_col: int = -1
    last_row: int = -1

    def piece_of(self, user_id: int) -> int:
        if user_id == self.p1:
            return P1
        if not self.vs_bot and user_id == self.p2:
            return P2
        return EMPTY

    def name_of(self, piece: int) -> str:
        if piece == P1:
            return self.p1_name
        if piece == P2:
            return self.p2_name
        return "\u2014"

    def column_open(self, col: int) -> bool:
        return 0 <= col < COLS and self.board[ROWS - 1][col] == EMPTY

    def drop(self, col: int, piece: int) -> int | None:
        if not self.column_open(col):
            return None
        for row in range(ROWS):
            if self.board[row][col] == EMPTY:
                self.board[row][col] = piece
                self.last_col = col
                self.last_row = row
                return row
        return None

    def is_full(self) -> bool:
        return all(self.board[ROWS - 1][c] != EMPTY for c in range(COLS))

    def has_win(self, piece: int) -> bool:
        b = self.board
        for r in range(ROWS):
            for c in range(COLS):
                if b[r][c] != piece:
                    continue
                if c + 3 < COLS and all(b[r][c + i] == piece for i in range(4)):
                    return True
                if r + 3 < ROWS and all(b[r + i][c] == piece for i in range(4)):
                    return True
                if r + 3 < ROWS and c + 3 < COLS and all(b[r + i][c + i] == piece for i in range(4)):
                    return True
                if r + 3 < ROWS and c - 3 >= 0 and all(b[r + i][c - i] == piece for i in range(4)):
                    return True
        return False


from .slash_connect4_flow import (  # noqa: E402
    _after_drop,
    _animate_fall,
    _bind,
    _bot_move,
    _embed,
    _finish,
    _hold_start,
    _publish,
    _settle,
    _subtitle,
    _table_file,
    _unbind,
)
from .slash_connect4_views import PlayView, ReplayView  # noqa: E402
from .slash_connect4_reg import register_connect4  # noqa: E402

__all__ = [
    "Match",
    "PlayView",
    "ReplayView",
    "register_connect4",
    "choose_column",
]
