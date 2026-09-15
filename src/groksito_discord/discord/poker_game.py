"""Poker Discord views. Logic lives in poker_logic."""
from __future__ import annotations

import asyncio
import io
import logging

import discord

from . import ai_coins
from .poker_table import render_hole_png, render_table_png
from .poker_logic import (
    BOT_ID, BOT_NAME, MAX_SEATS, TABLE_NAME, HOLE_NAME, THINK_SLEEP,
    EMBED_WAIT, EMBED_PLAY, EMBED_WIN, EMBED_DEAD, DEFAULT_BUYIN,
    _tables, _last_bet, _new_id, _card_label, _hold_seat, _refund_seat, _finish,
    _deal_holes, _raise_bounds, _apply_action, _bot_action, _after_action,
    _needs_board_run, _player_busy, _bind, Seat, Table, _showdown, _advance_street,
)

logger = logging.getLogger("aetherion.slash_poker")

def _embed(table, *, waiting=False):
    if waiting or table.street == "lobby":
        color, title, status = EMBED_WAIT, "Poker \u00b7 table", table.reason or "Join a seat, then Deal when 2-4 people are ready."
    elif table.finished:
        color, title, status = (EMBED_WIN if table.winner_ids else EMBED_DEAD), "Poker \u00b7 hand over", table.reason or "Pot awarded."
    else:
        color, title = EMBED_PLAY, "Poker \u00b7 Texas Hold'em"
        actor = table.seats[table.actor] if table.seats else None
        if actor:
            to_call = max(0, table.current_bet - actor.bet)
            status = f"{actor.name} to act \u00b7 {table.street} \u00b7 call {to_call} or raise \u00b7 My cards" if to_call else f"{actor.name} to act \u00b7 {table.street} \u00b7 check or raise \u00b7 My cards"
        else:
            status = table.street
    embed = discord.Embed(title=title, color=color)
    if table.finished and status:
        embed.description = status
    names = "\n".join(f"{'\u00b7 ' if (not table.finished and i == table.actor and table.street != 'lobby') else ''}{s.name} \u2014 {ai_coins.coins(s.stack)}" for i, s in enumerate(table.seats)) or "Empty"
    embed.add_field(name=f"Seats {len(table.seats)}/{MAX_SEATS}", value=names, inline=True)
    embed.add_field(name="Buy-in", value=ai_coins.coins(f"**{table.buyin:,}**"), inline=True)
    embed.add_field(name="Pot", value=ai_coins.coins(f"**{table.pot:,}**"), inline=True)
    embed.set_image(url=f"attachment://{TABLE_NAME}")
    embed.set_footer(text=status)
    return embed

def _table_file(table, subtitle=""):
    try:
        actor_id = None
        if not table.finished and table.street not in ("lobby", "showdown") and table.seats:
            actor_id = table.seats[table.actor].user_id
        raw = render_table_png([s.snapshot() for s in table.seats], table.board, pot=table.pot, street=table.street, subtitle=subtitle or table.reason, actor_id=actor_id, reveal=table.finished)
        return discord.File(io.BytesIO(raw), filename=TABLE_NAME)
    except Exception:
        logger.exception("poker table render failed")
        return None

async def _ack(interaction):
    if interaction is None or interaction.response.is_done():
        return
    try:
        await interaction.response.defer()
    except Exception:
        pass

async def _publish(interaction, *, embed, view, table=None, edit=True, ephemeral=False):
    kwargs = {"embed": embed, "view": view}
    if table is not None:
        if edit:
            kwargs["attachments"] = [table]
        else:
            kwargs["file"] = table
    message = getattr(view, "message", None) if view is not None else None
    if edit and message is not None:
        try:
            await message.edit(embed=embed, view=view, attachments=[table] if table is not None else [])
            await _ack(interaction)
            return message
        except Exception:
            logger.exception("poker table message edit failed")
    try:
        if interaction is None:
            return message
        if not interaction.response.is_done():
            if edit:
                await interaction.response.edit_message(**{k: v for k, v in kwargs.items() if k != "file"})
            else:
                await interaction.response.send_message(**kwargs, ephemeral=ephemeral)
        else:
            await interaction.edit_original_response(embed=embed, view=view, attachments=[table] if table is not None else [])
        try:
            return await interaction.original_response()
        except Exception:
            return message
    except Exception:
        logger.exception("poker publish failed")
        await _ack(interaction)
        return message

async def _reveal_runout(interaction, table, view):
    while _needs_board_run(table):
        await asyncio.sleep(1.2)
        if table.street == "river":
            _showdown(table)
            break
        _advance_street(table)
        if table.finished:
            break
        await _publish(interaction, embed=_embed(table), view=view, table=_table_file(table), edit=True)
    if table.street == "river" and _needs_board_run(table):
        _showdown(table)

async def _run_bots(interaction, table, view):
    guard = 0
    while not table.finished and table.street != "lobby" and table.seats and table.seats[table.actor].is_bot and guard < 16:
        guard += 1
        seat = table.seats[table.actor]
        await asyncio.sleep(THINK_SLEEP)
        line = _apply_action(table, seat, _bot_action(table, seat))
        _after_action(table)
        if not table.finished:
            table.reason = line
        await _publish(interaction, embed=_embed(table), view=view, table=_table_file(table), edit=True)

class RaiseModal(discord.ui.Modal, title="Raise"):
    def __init__(self, view, min_to, max_to):
        super().__init__()
        self.play = view
        self.min_to = min_to
        self.max_to = max_to
        self.amount = discord.ui.TextInput(label=f"Raise to ({min_to}-{max_to})", placeholder=str(min_to), default=str(min_to), required=True, max_length=6)
        self.add_item(self.amount)
    async def on_submit(self, interaction):
        raw = str(self.amount.value).replace(",", "").strip()
        try:
            value = int(raw)
        except ValueError:
            await interaction.response.send_message("Type a number in tens.", ephemeral=True)
            return
        value = max(self.min_to, min(self.max_to, max(10, (value // 10) * 10)))
        await self.play._act(interaction, "raise", raise_to=value)

class LobbyView(discord.ui.View):
    def __init__(self, table_id):
        super().__init__(timeout=180)
        self.table_id = table_id
        self.message = None
    def _table(self):
        return _tables.get(self.table_id)
    async def interaction_check(self, interaction):
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("That table is gone.", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join(self, interaction, button):
        table = self._table()
        if table is None:
            await interaction.response.send_message("That table is gone.", ephemeral=True)
            return
        uid = interaction.user.id
        if _player_busy(uid) and table.seat_of(uid) is None:
            await interaction.response.send_message("You already have a hand in progress.", ephemeral=True)
            return
        if not table.can_join(uid):
            await interaction.response.send_message("You cannot join this table.", ephemeral=True)
            return
        seat = Seat(uid, interaction.user.display_name, table.buyin)
        err = _hold_seat(seat, table.buyin)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        table.seats.append(seat)
        _bind(table)
        await _publish(interaction, embed=_embed(table, waiting=True), view=self, table=_table_file(table, "Waiting for Deal."), edit=True)
    @discord.ui.button(label="Seat Aetherion", style=discord.ButtonStyle.primary)
    async def seat_bot(self, interaction, button):
        table = self._table()
        if table is None:
            return
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can seat Aetherion.", ephemeral=True)
            return
        if table.seat_of(BOT_ID) is not None:
            await interaction.response.send_message("Aetherion is already seated.", ephemeral=True)
            return
        if len(table.seats) >= MAX_SEATS:
            await interaction.response.send_message("The table is full.", ephemeral=True)
            return
        table.seats.append(Seat(BOT_ID, BOT_NAME, table.buyin, is_bot=True, held=True))
        await _publish(interaction, embed=_embed(table, waiting=True), view=self, table=_table_file(table, "Aetherion sits."), edit=True)
    @discord.ui.button(label="Deal", style=discord.ButtonStyle.primary)
    async def deal(self, interaction, button):
        table = self._table()
        if table is None:
            return
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can deal.", ephemeral=True)
            return
        if len(table.seats) < 2:
            await interaction.response.send_message("Need at least two seats.", ephemeral=True)
            return
        _deal_holes(table)
        play = PlayView(table.id)
        play.message = self.message
        await _publish(interaction, embed=_embed(table), view=play, table=_table_file(table, "Tap My cards for your hand."), edit=True)
        try:
            play.message = await interaction.original_response() or play.message
        except Exception:
            pass
        await _run_bots(interaction, table, play)
        if not table.finished:
            await _reveal_runout(interaction, table, play)
        if table.finished:
            replay = ReplayView(table.host_id)
            replay.message = play.message
            await _publish(interaction, embed=_embed(table), view=replay, table=_table_file(table), edit=True)
        else:
            await _publish(interaction, embed=_embed(table), view=play, table=_table_file(table), edit=True)
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        table = self._table()
        if table is None:
            return
        if interaction.user.id != table.host_id:
            await interaction.response.send_message("Only the host can cancel.", ephemeral=True)
            return
        for seat in list(table.seats):
            _refund_seat(seat)
        _finish(table, "Table cancelled. Buy-ins returned.")
        self.stop()
        await _publish(interaction, embed=_embed(table), view=None, table=_table_file(table, "Cancelled."), edit=True)
    async def on_timeout(self):
        table = self._table()
        if table is None or table.finished or table.street != "lobby":
            return
        for seat in list(table.seats):
            _refund_seat(seat)
        _finish(table, "Lobby timed out. Buy-ins returned.")
        if self.message is not None:
            try:
                file = _table_file(table)
                kwargs = {"embed": _embed(table), "view": None}
                if file is not None:
                    kwargs["attachments"] = [file]
                await self.message.edit(**kwargs)
            except Exception:
                logger.exception("poker lobby timeout failed")

class ReplayView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.message = None
    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This table is not yours.", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction, button):
        bet = int(_last_bet.get(self.user_id) or DEFAULT_BUYIN)
        await _open_table(interaction, user_id=self.user_id, name=interaction.user.display_name, bet=bet, seat_bot=True, edit=True)

class PlayView(discord.ui.View):
    def __init__(self, table_id):
        super().__init__(timeout=180)
        self.table_id = table_id
        self.message = None
    def _table(self):
        return _tables.get(self.table_id)
    async def interaction_check(self, interaction):
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return False
        if table.seat_of(interaction.user.id) is None:
            await interaction.response.send_message("You are not seated.", ephemeral=True)
            return False
        return True
    async def _act(self, interaction, action, raise_to=None):
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return
        if table.busy:
            await interaction.response.send_message("Wait a second.", ephemeral=True)
            return
        seat = table.seat_of(interaction.user.id)
        if seat is None or seat.folded:
            await interaction.response.send_message("You cannot act.", ephemeral=True)
            return
        if seat.all_in:
            await interaction.response.send_message("You are already all-in. Wait for the board.", ephemeral=True)
            return
        if table.seats[table.actor].user_id != interaction.user.id:
            await interaction.response.send_message("Wait for your turn.", ephemeral=True)
            return
        table.busy = True
        try:
            await _ack(interaction)
            table.reason = _apply_action(table, seat, action, raise_to=raise_to)
            _after_action(table)
            view = self
            if table.finished:
                self.stop()
                replay = ReplayView(table.host_id)
                replay.message = self.message
                view = replay
            await _publish(interaction, embed=_embed(table), view=view, table=_table_file(table), edit=True)
            if table.finished:
                return
            await _run_bots(interaction, table, self)
            if _needs_board_run(table):
                await _reveal_runout(interaction, table, self)
            view = self
            if table.finished:
                self.stop()
                replay = ReplayView(table.host_id)
                replay.message = self.message
                view = replay
            await _publish(interaction, embed=_embed(table), view=view, table=_table_file(table), edit=True)
        except Exception:
            logger.exception("poker act failed action=%s user=%s", action, interaction.user.id)
        finally:
            table.busy = False
    @discord.ui.button(label="Fold", style=discord.ButtonStyle.danger, row=0)
    async def fold(self, interaction, button):
        await self._act(interaction, "fold")
    @discord.ui.button(label="Check / Call", style=discord.ButtonStyle.secondary, row=0)
    async def check_call(self, interaction, button):
        await self._act(interaction, "check")
    @discord.ui.button(label="Raise", style=discord.ButtonStyle.primary, row=0)
    async def raise_bet(self, interaction, button):
        table = self._table()
        if table is None or table.finished:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return
        seat = table.seat_of(interaction.user.id)
        if seat is None or table.seats[table.actor].user_id != interaction.user.id:
            await interaction.response.send_message("Wait for your turn.", ephemeral=True)
            return
        min_to, max_to = _raise_bounds(table, seat)
        if max_to <= table.current_bet or seat.stack <= 0:
            await self._act(interaction, "allin")
            return
        await interaction.response.send_modal(RaiseModal(self, min_to, max_to))
    @discord.ui.button(label="All-in", style=discord.ButtonStyle.primary, row=0)
    async def allin(self, interaction, button):
        await self._act(interaction, "allin")
    @discord.ui.button(label="My cards", style=discord.ButtonStyle.secondary, row=1)
    async def my_cards(self, interaction, button):
        table = self._table()
        if table is None:
            await interaction.response.send_message("This hand is over.", ephemeral=True)
            return
        seat = table.seat_of(interaction.user.id)
        if seat is None or not seat.hole:
            await interaction.response.send_message("No hole cards yet.", ephemeral=True)
            return
        raw = render_hole_png(seat.hole)
        file = discord.File(io.BytesIO(raw), filename=HOLE_NAME)
        embed = discord.Embed(title="Your hole cards", description="  ".join(_card_label(c) for c in seat.hole), color=EMBED_PLAY)
        embed.set_image(url=f"attachment://{HOLE_NAME}")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    async def on_timeout(self):
        table = self._table()
        if table is None or table.finished or table.street == "lobby":
            return
        actor = table.seats[table.actor]
        if actor.is_bot:
            return
        table.reason = _apply_action(table, actor, "fold")
        _after_action(table)
        if self.message is not None:
            try:
                view = ReplayView(table.host_id) if table.finished else self
                file = _table_file(table)
                kwargs = {"embed": _embed(table), "view": view}
                if file is not None:
                    kwargs["attachments"] = [file]
                await self.message.edit(**kwargs)
            except Exception:
                logger.exception("poker turn timeout failed")

async def _open_table(interaction, *, user_id, name, bet, seat_bot, edit):
    err = ai_coins.amount_error(bet, ai_coins.MIN_BET, ai_coins.MAX_GRANT)
    if err:
        if not interaction.response.is_done():
            await interaction.response.send_message(err, ephemeral=True)
        else:
            await interaction.followup.send(err, ephemeral=True)
        return
    if _player_busy(user_id):
        msg = "You already have a hand in progress."
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
        return
    table = Table(id=_new_id(), guild_id=interaction.guild.id if interaction.guild else 0, channel_id=interaction.channel.id if interaction.channel else 0, host_id=user_id, buyin=bet)
    host = Seat(user_id, name, bet)
    hold_err = _hold_seat(host, bet)
    if hold_err:
        if not interaction.response.is_done():
            await interaction.response.send_message(hold_err, ephemeral=True)
        else:
            await interaction.followup.send(hold_err, ephemeral=True)
        return
    table.seats.append(host)
    if seat_bot:
        table.seats.append(Seat(BOT_ID, BOT_NAME, bet, is_bot=True, held=True))
    _bind(table)
    view = LobbyView(table.id)
    await _publish(interaction, embed=_embed(table, waiting=True), view=view, table=_table_file(table, "Lobby open."), edit=edit)
    try:
        view.message = await interaction.original_response()
    except Exception:
        view.message = None

def register_poker(tree, is_guild_allowed):
    @tree.command(name="poker", description="Texas Hold'em, 2-4 seats. Friends and/or Aetherion. Aether Coins.")
    @discord.app_commands.describe(bet="Buy-in the host sets for every seat (10-10000, tens). Default 200.", vs_aetherion="Seat Aetherion now. Friends can still join.")
    async def poker_slash(interaction, bet: int = DEFAULT_BUYIN, vs_aetherion: bool = False):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        await _open_table(interaction, user_id=interaction.user.id, name=interaction.user.display_name, bet=int(bet), seat_bot=bool(vs_aetherion), edit=False)
