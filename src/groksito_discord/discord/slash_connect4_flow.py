"""Connect Four settle / embed / animation helpers."""
from __future__ import annotations

import asyncio
import io

import discord

from . import ai_coins
from .connect4_board import render_fall_gif, render_still_gif
from . import slash_connect4 as c4


def _unbind(match) -> None:
    c4._games.pop(match.id, None)
    c4._by_user.pop(match.p1, None)
    if not match.vs_bot:
        c4._by_user.pop(match.p2, None)


def _bind(match) -> None:
    c4._games[match.id] = match
    c4._by_user[match.p1] = match.id
    if not match.vs_bot:
        c4._by_user[match.p2] = match.id


def _hold_start(match) -> str:
    ok1, _bal1, err1 = ai_coins.hold_bet(match.p1, match.bet)
    if not ok1:
        return f"{match.p1_name}: {err1}"
    if match.vs_bot:
        match.held = True
        return ""
    ok2, _bal2, err2 = ai_coins.hold_bet(match.p2, match.bet)
    if not ok2:
        ai_coins.settle_hand(match.p1, match.bet)
        return f"{match.p2_name}: {err2}"
    match.held = True
    return ""


def _settle(match) -> None:
    if not match.held:
        return
    if match.vs_bot:
        if match.winner == c4.P1:
            ai_coins.settle_hand(match.p1, match.bet * 2)
        elif match.winner == c4.P2:
            ai_coins.settle_hand(match.p1, 0)
        else:
            ai_coins.settle_hand(match.p1, match.bet)
        match.held = False
        return
    if match.winner == c4.P1:
        ai_coins.settle_hand(match.p1, match.bet * 2)
        ai_coins.settle_hand(match.p2, 0)
    elif match.winner == c4.P2:
        ai_coins.settle_hand(match.p2, match.bet * 2)
        ai_coins.settle_hand(match.p1, 0)
    else:
        ai_coins.settle_hand(match.p1, match.bet)
        ai_coins.settle_hand(match.p2, match.bet)
    match.held = False


def _finish(match, *, winner: int = 0, reason: str = "") -> None:
    match.finished = True
    match.winner = winner
    match.reason = reason
    _settle(match)
    c4._last_bet[match.p1] = match.bet
    _unbind(match)


def _after_drop(match, piece: int) -> None:
    if match.has_win(piece):
        _finish(
            match,
            winner=piece,
            reason=f"{match.name_of(piece)} connects four and takes {ai_coins.coins(match.bet * 2)}.",
        )
    elif match.is_full():
        _finish(match, winner=0, reason="Draw. Stakes returned.")
    else:
        match.turn = c4.P2 if match.turn == c4.P1 else c4.P1


def _bot_move(match) -> None:
    if match.finished or not match.vs_bot or match.turn != c4.P2:
        return
    col = c4.choose_column(match.board, c4.P2)
    if match.drop(col, c4.P2) is None:
        _finish(match, winner=c4.P1, reason="Aetherion could not move. Stake returned.")
        return
    _after_drop(match, c4.P2)


def _embed(match, *, waiting: bool = False, balance: int | None = None) -> discord.Embed:
    pot = match.bet if match.vs_bot else match.bet * 2
    if waiting:
        color = c4.EMBED_WAIT
        title = "Connect Four \u00b7 challenge"
        status = f"{match.p2_name} \u2014 Accept or Decline."
    elif match.finished:
        if match.winner:
            color = c4.EMBED_WIN if match.winner == c4.P1 else c4.EMBED_DEAD
            title = "Connect Four \u00b7 four in a row"
        elif match.reason and "Draw" not in match.reason:
            color = c4.EMBED_DEAD
            title = "Connect Four \u00b7 over"
        else:
            color = c4.EMBED_DRAW
            title = "Connect Four \u00b7 draw"
        status = match.reason
    else:
        color = c4.EMBED_PLAY
        title = "Connect Four"
        status = f"{c4.DISC[match.turn]} {match.name_of(match.turn)} to drop."
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name=f"{c4.DISC[c4.P1]} Red", value=match.p1_name, inline=True)
    embed.add_field(name=f"{c4.DISC[c4.P2]} Gold", value=match.p2_name, inline=True)
    embed.add_field(name="Pot" if not match.vs_bot else "Stake", value=ai_coins.coins(f"**{pot:,}**"), inline=True)
    if balance is not None:
        embed.add_field(name="Wallet", value=ai_coins.coins(f"**{balance:,}**"), inline=True)
    embed.set_image(url=f"attachment://{c4.TABLE_NAME}")
    embed.set_footer(text=status)
    return embed


def _subtitle(match, extra: str = "") -> str:
    if extra:
        return extra
    if match.finished:
        return match.reason or ""
    if match.turn == c4.P1:
        return "Your move."
    return f"{match.p2_name} is choosing a column..."


def _table_file(match, *, falling=None, subtitle=None):
    try:
        last = None
        if falling is None and match.last_row >= 0:
            last = (match.last_row, match.last_col)
        raw = render_still_gif(
            match.board,
            subtitle=_subtitle(match) if subtitle is None else subtitle,
            last=last,
            winner=match.winner if match.finished else 0,
        )
        return discord.File(io.BytesIO(raw), filename=c4.TABLE_NAME)
    except Exception:
        c4.logger.exception("connect4 board render failed")
        return None


async def _animate_fall(interaction, match, view, *, piece, col, landing_row, caption) -> None:
    parked = match.board[landing_row][col]
    match.board[landing_row][col] = c4.EMPTY
    try:
        raw, seconds = render_fall_gif(
            match.board,
            piece=piece,
            col=col,
            landing_row=landing_row,
            subtitle=caption,
        )
        table = discord.File(io.BytesIO(raw), filename=c4.TABLE_NAME)
        embed = _embed(match, balance=ai_coins.get_balance(match.p1))
        embed.set_footer(text=caption)
        embed.set_image(url=f"attachment://{c4.TABLE_NAME}")
        await _publish(interaction, embed=embed, view=view, table=table, edit=True)
        await asyncio.sleep(max(0.35, seconds))
    finally:
        match.board[landing_row][col] = parked


async def _publish(interaction, *, embed, view, table, edit, content=None):
    kwargs = {"embed": embed, "view": view, "content": content}
    if not interaction.response.is_done():
        if edit:
            if table is not None:
                kwargs["attachments"] = [table]
            await interaction.response.edit_message(**kwargs)
        else:
            if table is not None:
                kwargs["file"] = table
            await interaction.response.send_message(**kwargs)
        try:
            return await interaction.original_response()
        except Exception:
            return None
    if table is not None:
        kwargs["attachments"] = [table]
    await interaction.edit_original_response(**kwargs)
    try:
        return await interaction.original_response()
    except Exception:
        return None
