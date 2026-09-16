"""Slash slots against Aetherion. Fair reels + Aether Coin stakes."""
from __future__ import annotations

import asyncio
import io
import logging

import discord

from . import ai_coins
from .slash_blackjack import has_live_hand
from .slots import (
    COSMOS,
    DEFAULT_MACHINE,
    MACHINES,
    SLOTS_DEFAULT_BET,
    SLOTS_MAX_BET,
    SLOTS_MIN_BET,
    blur_grid,
    coins,
    format_cells,
    format_grid,
    payouts_text,
    spin,
    spinning_cells,
)
from .slots_art import cabinet_png

logger = logging.getLogger("aetherion.slash_slots")

_sessions: dict[int, dict[str, object]] = {}
_busy: set[int] = set()

EMBED_SPIN = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
EMBED_PUSH = 0x8A8F98
THUMB_NAME = "cabinet.png"


def has_live_hand_safe(user_id: int) -> bool:
    try:
        return bool(has_live_hand(user_id))
    except Exception:
        return False


def _set_disabled(view: discord.ui.View, disabled: bool) -> None:
    for child in view.children:
        if isinstance(child, (discord.ui.Button, discord.ui.Select)):
            child.disabled = disabled


def _cabinet_file(machine_key: str) -> discord.File | None:
    try:
        raw = cabinet_png(machine_key)
    except Exception:
        logger.exception("cabinet render failed key=%s", machine_key)
        return None
    if not raw:
        return None
    return discord.File(io.BytesIO(raw), filename=THUMB_NAME)


class BetModal(discord.ui.Modal, title="Change bet"):
    amount = discord.ui.TextInput(
        label="Aether Coins",
        placeholder=f"{SLOTS_MIN_BET}\u2013{SLOTS_MAX_BET}",
        required=True,
        max_length=6,
    )

    def __init__(self, view: "SlotsView"):
        super().__init__()
        self.slots_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.amount.value or "").replace(",", "").strip()
        try:
            bet = int(raw)
        except ValueError:
            await interaction.response.send_message("Bet has to be a whole number.", ephemeral=True)
            return
        if bet < SLOTS_MIN_BET or bet > SLOTS_MAX_BET:
            await interaction.response.send_message(
                f"Bet must be {SLOTS_MIN_BET}\u2013{SLOTS_MAX_BET} Aether Coins.",
                ephemeral=True,
            )
            return
        session = _sessions.setdefault(
            self.slots_view.user_id,
            {"bet": SLOTS_DEFAULT_BET, "machine": DEFAULT_MACHINE},
        )
        session["bet"] = bet
        await interaction.response.send_message(
            f"Next spin is **{coins(bet)}**.", ephemeral=True
        )


class SlotsView(discord.ui.View):
    def __init__(self, user_id: int, machine_key: str):
        super().__init__(timeout=180)
        self.user_id = user_id
        self._sync_select(machine_key)

    def _sync_select(self, machine_key: str) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                for option in child.options:
                    option.default = option.value == machine_key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your machine.", ephemeral=True)
            return False
        return True

    @discord.ui.select(
        placeholder="Choose a machine",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Cosmos Wheel", value="cosmos", emoji="\U0001FA90", description="Balanced house wheel"),
            discord.SelectOption(label="Nebula", value="nebula", emoji="\U0001F52E", description="Hits often, pays small"),
            discord.SelectOption(label="Event Horizon", value="horizon", emoji="\U0001F573\ufe0f", description="Rare. Huge when it lands"),
        ],
    )
    async def machine_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        key = select.values[0]
        session = _sessions.setdefault(self.user_id, {"bet": SLOTS_DEFAULT_BET, "machine": DEFAULT_MACHINE})
        session["machine"] = key
        session.pop("thumb", None)
        self._sync_select(key)
        machine = MACHINES[key]
        await interaction.response.send_message(
            f"Machine set to {machine.emoji} **{machine.name}**. Spin Again when ready.",
            ephemeral=True,
        )

    @discord.ui.button(label="Spin Again", style=discord.ButtonStyle.primary)
    async def spin_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = _sessions.get(self.user_id) or {"bet": SLOTS_DEFAULT_BET, "machine": DEFAULT_MACHINE}
        await _run_spin(
            interaction,
            user_id=self.user_id,
            machine_key=str(session.get("machine") or DEFAULT_MACHINE),
            bet=int(session.get("bet") or SLOTS_DEFAULT_BET),
            edit=True,
            view=self,
        )

    @discord.ui.button(label="Change Bet", style=discord.ButtonStyle.secondary)
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal(self))

    @discord.ui.button(label="See Payouts", style=discord.ButtonStyle.secondary)
    async def see_payouts(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = _sessions.get(self.user_id) or {"machine": DEFAULT_MACHINE}
        machine = MACHINES.get(str(session.get("machine") or DEFAULT_MACHINE), COSMOS)
        embed = discord.Embed(title=f"\u2726 {machine.name} \u00b7 Payouts", description=payouts_text(machine), color=machine.color)
        embed.set_footer(text=f"Bet {coins(SLOTS_MIN_BET)} \u2013 {coins(SLOTS_MAX_BET)}")
        thumb = _cabinet_file(machine.key)
        if thumb:
            embed.set_thumbnail(url=f"attachment://{THUMB_NAME}")
            await interaction.response.send_message(embed=embed, file=thumb, ephemeral=True)
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)


def _cabinet_embed(*, machine, pocket: int, winnings_text: str, net_text: str, grid: str, bet: int, color: int) -> discord.Embed:
    body = (
        f"**Pocket** \u00b7 {coins(f'**{pocket:,}**')}\n"
        f"**Winnings** \u00b7 {coins(f'**{winnings_text}**')}\n"
        f"**Net** \u00b7 {coins(f'**{net_text}**')}\n\n"
        f"{grid}"
    )
    embed = discord.Embed(title=f"\u2726 {machine.name}", description=body, color=color)
    embed.set_footer(text=f"Bet: {coins(f'{bet:,}')}  |  Min: {coins(f'{SLOTS_MIN_BET:,}')}  |  Max: {coins(f'{SLOTS_MAX_BET:,}')}")
    embed.set_thumbnail(url=f"attachment://{THUMB_NAME}")
    return embed


def _final_embed(result, *, balance: int) -> discord.Embed:
    if result.net > 0:
        color = EMBED_WIN
    elif result.net < 0:
        color = EMBED_LOSE
    else:
        color = EMBED_PUSH
    net = f"+{result.net:,}" if result.net > 0 else f"{result.net:,}"
    return _cabinet_embed(
        machine=result.machine,
        pocket=balance,
        winnings_text=f"{result.winnings:,}",
        net_text=net,
        grid=format_grid(result),
        bet=result.bet,
        color=color,
    )


async def _publish(interaction: discord.Interaction, *, embed, view, as_edit: bool, thumb: discord.File | None) -> None:
    if not interaction.response.is_done():
        if as_edit:
            kwargs = {"embed": embed, "view": view}
            if thumb is not None:
                kwargs["attachments"] = [thumb]
            await interaction.response.edit_message(**kwargs)
        else:
            kwargs = {"embed": embed, "view": view}
            if thumb is not None:
                kwargs["file"] = thumb
            await interaction.response.send_message(**kwargs)
        return
    kwargs = {"embed": embed, "view": view}
    if thumb is not None:
        kwargs["attachments"] = [thumb]
    await interaction.edit_original_response(**kwargs)


async def _run_spin(interaction: discord.Interaction, *, user_id: int, machine_key: str, bet: int, edit: bool, view: SlotsView | None) -> None:
    if user_id in _busy:
        msg = "Reels are already spinning."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    if has_live_hand_safe(user_id):
        msg = "Finish the blackjack hand on the table first."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    ai_coins.refund_stale_pending(user_id)
    if bet < SLOTS_MIN_BET or bet > SLOTS_MAX_BET:
        msg = f"Bet must be {SLOTS_MIN_BET}\u2013{SLOTS_MAX_BET} Aether Coins."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    pocket = ai_coins.get_balance(user_id)
    if bet > pocket:
        msg = f"You only have {coins(pocket)}."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    machine = MACHINES.get(machine_key, COSMOS)
    send_view = view or SlotsView(user_id, machine.key)
    send_view._sync_select(machine.key)
    _set_disabled(send_view, True)
    _busy.add(user_id)
    session = _sessions.setdefault(user_id, {"bet": bet, "machine": machine.key})
    try:
        ticks = [spinning_cells()] + [format_cells(blur_grid(machine), tag="\u2026", glyphs=machine.glyphs) for _ in range(3)]
        first = True
        thumb = _cabinet_file(machine.key)
        for grid in ticks:
            frame = _cabinet_embed(
                machine=machine,
                pocket=pocket,
                winnings_text="Spinning\u2026",
                net_text=f"-{bet:,}",
                grid=grid,
                bet=bet,
                color=EMBED_SPIN,
            )
            await _publish(
                interaction,
                embed=frame,
                view=send_view,
                as_edit=edit if first else True,
                thumb=thumb if first else None,
            )
            first = False
            await asyncio.sleep(0.55)
        result = spin(machine, bet)
        ok, balance, err = ai_coins.resolve_wager(
            user_id, result.bet, result.winnings, min_bet=SLOTS_MIN_BET, max_bet=SLOTS_MAX_BET,
        )
        if not ok:
            _set_disabled(send_view, False)
            await interaction.edit_original_response(view=send_view)
            await interaction.followup.send(err, ephemeral=True)
            return
        session["bet"] = result.bet
        session["machine"] = machine.key
        session["thumb"] = machine.key
        _set_disabled(send_view, False)
        final = _final_embed(result, balance=balance)
        await _publish(interaction, embed=final, view=send_view, as_edit=True, thumb=None)
    except Exception:
        logger.exception("slots spin failed user=%s", user_id)
        try:
            _set_disabled(send_view, False)
            await interaction.edit_original_response(view=send_view)
        except Exception:
            pass
    finally:
        _busy.discard(user_id)


def register_slots(tree, is_guild_allowed) -> None:
    @tree.command(name="slots", description="Spin Aetherion slots for Aether Coins.")
    @discord.app_commands.describe(
        bet=f"Wager in Aether Coins ({SLOTS_MIN_BET}\u2013{SLOTS_MAX_BET})",
        machine="Which cabinet to sit at",
    )
    @discord.app_commands.choices(
        machine=[
            discord.app_commands.Choice(name="Cosmos Wheel", value="cosmos"),
            discord.app_commands.Choice(name="Nebula", value="nebula"),
            discord.app_commands.Choice(name="Event Horizon", value="horizon"),
        ]
    )
    async def slots_slash(
        interaction: discord.Interaction,
        bet: int = SLOTS_DEFAULT_BET,
        machine: discord.app_commands.Choice[str] | None = None,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        key = machine.value if machine is not None else DEFAULT_MACHINE
        session = _sessions.get(interaction.user.id) or {}
        if machine is None and session.get("machine"):
            key = str(session["machine"])
        if bet == SLOTS_DEFAULT_BET and interaction.user.id in _sessions and session.get("bet"):
            bet = int(session["bet"])
        await _run_spin(interaction, user_id=interaction.user.id, machine_key=key, bet=int(bet), edit=False, view=None)
