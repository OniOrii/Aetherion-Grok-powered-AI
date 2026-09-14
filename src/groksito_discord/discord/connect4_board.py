"""Painted Connect Four board + house mover. Matches blackjack cosmos felt."""
from __future__ import annotations

import io
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROWS = 6
COLS = 7
EMPTY = 0
P1 = 1
P2 = 2

VOID = (6, 8, 16)
GOLD = (212, 176, 72)
GOLD_DIM = (148, 118, 42)
CREAM = (248, 244, 234)
FRAME = (18, 28, 52)
GRID = (22, 38, 72)
HOLE = (8, 10, 18)
RED = (196, 48, 52)
RED_HI = (240, 120, 110)
GOLD_DISC = (214, 168, 48)
GOLD_HI = (255, 226, 140)
NEBULA_TEAL = (40, 90, 110, 70)
NEBULA_VIOLET = (70, 40, 110, 65)

CELL = 78
HOLE_R = 28
PAD_X = 36
PAD_Y = 22
HEADER = 56
FOOTER = 40

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _space_field(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), VOID)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.ellipse((-width // 4, -height // 5, width // 2 + 40, height // 2 + 40), fill=NEBULA_VIOLET)
    d.ellipse((width // 3, height // 4, width + 80, height + 40), fill=NEBULA_TEAL)
    overlay = overlay.filter(ImageFilter.GaussianBlur(28))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    stars = ImageDraw.Draw(img)
    rng = Random(width * 17 + height)
    for _ in range(max(80, width * height // 2800)):
        x = rng.randint(8, width - 8)
        y = rng.randint(8, height - 8)
        r = rng.choice((0, 0, 1, 1, 2))
        c = rng.randint(160, 240)
        stars.ellipse((x, y, x + r, y + r), fill=(c, c - 8, min(255, c + 10)))
    return img.convert("RGB")


def _winning_cells(board: list[list[int]], piece: int) -> set[tuple[int, int]]:
    hits: set[tuple[int, int]] = set()
    dirs = ((1, 0), (0, 1), (1, 1), (1, -1))
    for r in range(ROWS):
        for c in range(COLS):
            if board[r][c] != piece:
                continue
            for dr, dc in dirs:
                cells = []
                rr, cc = r, c
                for _ in range(4):
                    if not (0 <= rr < ROWS and 0 <= cc < COLS) or board[rr][cc] != piece:
                        cells = []
                        break
                    cells.append((rr, cc))
                    rr += dr
                    cc += dc
                if len(cells) == 4:
                    hits.update(cells)
    return hits


def fall_path(landing_row: int) -> list[int]:
    """Board rows a disc travels through, top to landing."""
    if landing_row < 0:
        return []
    return list(range(ROWS - 1, landing_row - 1, -1))


def render_board_png(
    board: list[list[int]],
    *,
    subtitle: str = "",
    last: tuple[int, int] | None = None,
    winner: int = 0,
    falling: tuple[int, int, int] | None = None,
) -> bytes:
    grid_w = COLS * CELL
    grid_h = ROWS * CELL
    width = PAD_X * 2 + grid_w
    height = PAD_Y + HEADER + grid_h + FOOTER
    img = _space_field(width, height)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, width - 11, height - 11), radius=28, outline=GOLD_DIM, width=2)
    d.rounded_rectangle((16, 16, width - 17, height - 17), radius=24, outline=(80, 70, 40), width=1)
    d.text((width // 2, 34), "AETHERION  \u00b7  CONNECT FOUR", font=_font(20), fill=GOLD, anchor="mm")

    gx0 = PAD_X
    gy0 = PAD_Y + HEADER
    d.rounded_rectangle((gx0 - 8, gy0 - 8, gx0 + grid_w + 8, gy0 + grid_h + 8), radius=18, fill=FRAME, outline=GOLD_DIM, width=2)

    glow = _winning_cells(board, winner) if winner else set()
    last_cell = last

    for col in range(COLS):
        cx = gx0 + col * CELL + CELL // 2
        d.text((cx, gy0 - 16), str(col + 1), font=_font(16), fill=CREAM, anchor="mm")
        for row_from_top in range(ROWS):
            board_row = ROWS - 1 - row_from_top
            cy = gy0 + row_from_top * CELL + CELL // 2
            piece = board[board_row][col]
            if falling and falling[1] == col and falling[2] == board_row:
                piece = falling[0]
            d.ellipse((cx - HOLE_R - 2, cy - HOLE_R - 2, cx + HOLE_R + 2, cy + HOLE_R + 2), fill=HOLE)
            if piece == EMPTY:
                d.ellipse((cx - HOLE_R + 4, cy - HOLE_R + 4, cx + HOLE_R - 4, cy + HOLE_R - 4), fill=(12, 14, 24))
                continue
            fill = RED if piece == P1 else GOLD_DISC
            hi = RED_HI if piece == P1 else GOLD_HI
            d.ellipse((cx - HOLE_R + 1, cy - HOLE_R + 1, cx + HOLE_R - 1, cy + HOLE_R - 1), fill=fill)
            d.ellipse((cx - 12, cy - 16, cx + 4, cy - 2), fill=hi)
            if last_cell == (board_row, col) or (board_row, col) in glow:
                d.ellipse(
                    (cx - HOLE_R - 4, cy - HOLE_R - 4, cx + HOLE_R + 4, cy + HOLE_R + 4),
                    outline=GOLD,
                    width=3,
                )

    if subtitle:
        d.text((width // 2, height - 22), subtitle[:64], font=_font(15), fill=GOLD, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


FRAME_MS = 110
HOLD_MS = 450


def render_fall_gif(
    board: list[list[int]],
    *,
    piece: int,
    col: int,
    landing_row: int,
    subtitle: str = "",
) -> tuple[bytes, float]:
    """One GIF for a drop so Discord does not reload a new PNG every hole."""
    path = fall_path(landing_row) or [landing_row]
    raw_frames: list[Image.Image] = []
    for hover in path:
        raw = render_board_png(board, subtitle=subtitle, falling=(piece, col, hover))
        raw_frames.append(Image.open(io.BytesIO(raw)).convert("RGB"))
    landed = [row[:] for row in board]
    landed[landing_row][col] = piece
    raw = render_board_png(landed, subtitle=subtitle, last=(landing_row, col))
    raw_frames.append(Image.open(io.BytesIO(raw)).convert("RGB"))

    try:
        method = Image.Quantize.MEDIANCUT
        dither = Image.Dither.NONE
    except AttributeError:
        method = 0
        dither = 0
    base = raw_frames[0].quantize(colors=48, method=method)
    frames = [base] + [f.quantize(palette=base, dither=dither) for f in raw_frames[1:]]
    durations = [FRAME_MS] * (len(frames) - 1) + [HOLD_MS]
    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    return buf.getvalue(), sum(durations) / 1000.0


def _copy(board: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in board]


def column_open(board: list[list[int]], col: int) -> bool:
    return 0 <= col < COLS and board[ROWS - 1][col] == EMPTY


def drop_copy(board: list[list[int]], col: int, piece: int) -> list[list[int]] | None:
    if not column_open(board, col):
        return None
    nxt = _copy(board)
    for row in range(ROWS):
        if nxt[row][col] == EMPTY:
            nxt[row][col] = piece
            return nxt
    return None


def winner_of(board: list[list[int]]) -> int:
    for piece in (P1, P2):
        if _winning_cells(board, piece):
            return piece
    return EMPTY


def board_full(board: list[list[int]]) -> bool:
    return all(board[ROWS - 1][c] != EMPTY for c in range(COLS))


def _score_window(window: list[int], piece: int) -> int:
    opp = P1 if piece == P2 else P2
    if window.count(piece) == 4:
        return 10000
    if window.count(opp) == 4:
        return -10000
    score = 0
    if window.count(piece) == 3 and window.count(EMPTY) == 1:
        score += 80
    elif window.count(piece) == 2 and window.count(EMPTY) == 2:
        score += 8
    if window.count(opp) == 3 and window.count(EMPTY) == 1:
        score -= 90
    elif window.count(opp) == 2 and window.count(EMPTY) == 2:
        score -= 6
    return score


def evaluate(board: list[list[int]], piece: int) -> int:
    score = 0
    center = [board[r][COLS // 2] for r in range(ROWS)]
    score += center.count(piece) * 6
    for r in range(ROWS):
        row = board[r]
        for c in range(COLS - 3):
            score += _score_window(row[c : c + 4], piece)
    for c in range(COLS):
        col = [board[r][c] for r in range(ROWS)]
        for r in range(ROWS - 3):
            score += _score_window(col[r : r + 4], piece)
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            score += _score_window([board[r + i][c + i] for i in range(4)], piece)
        for c in range(3, COLS):
            score += _score_window([board[r + i][c - i] for i in range(4)], piece)
    return score


def _minimax(board: list[list[int]], depth: int, alpha: int, beta: int, maximizing: bool, piece: int) -> int:
    opp = P1 if piece == P2 else P2
    win = winner_of(board)
    if win == piece:
        return 100000 + depth
    if win == opp:
        return -100000 - depth
    if board_full(board) or depth == 0:
        return evaluate(board, piece)
    actor = piece if maximizing else opp
    if maximizing:
        best = -10**9
        for col in (3, 2, 4, 1, 5, 0, 6):
            nxt = drop_copy(board, col, actor)
            if nxt is None:
                continue
            best = max(best, _minimax(nxt, depth - 1, alpha, beta, False, piece))
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best
    best = 10**9
    for col in (3, 2, 4, 1, 5, 0, 6):
        nxt = drop_copy(board, col, actor)
        if nxt is None:
            continue
        best = min(best, _minimax(nxt, depth - 1, alpha, beta, True, piece))
        beta = min(beta, best)
        if beta <= alpha:
            break
    return best


def choose_column(board: list[list[int]], piece: int, *, depth: int = 4) -> int:
    open_cols = [c for c in range(COLS) if column_open(board, c)]
    if not open_cols:
        return 3
    for col in open_cols:
        nxt = drop_copy(board, col, piece)
        if nxt is not None and winner_of(nxt) == piece:
            return col
    opp = P1 if piece == P2 else P2
    for col in open_cols:
        nxt = drop_copy(board, col, opp)
        if nxt is not None and winner_of(nxt) == opp:
            return col
    best_col = open_cols[0]
    best_score = -10**9
    for col in (3, 2, 4, 1, 5, 0, 6):
        nxt = drop_copy(board, col, piece)
        if nxt is None:
            continue
        score = _minimax(nxt, depth - 1, -10**9, 10**9, False, piece)
        if score > best_score:
            best_score = score
            best_col = col
    return best_col
