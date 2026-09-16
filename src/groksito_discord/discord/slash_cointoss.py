"""Slash coin toss against Aetherion. Fair flip + Aether Coin stakes."""
from __future__ import annotations

import asyncio
import io
import logging

import discord

from . import ai_coins
from .coin_art import FLIP_BEATS, FLIP_SLEEP, render_flip_frame, render_result, render_thumb
from .coin_toss import (
    HEADS,
    SIDE_MULTI,
    TAILS,
    TOSS_DEFAULT_BET,
    TOSS_MAX_BET,
    TOSS_MIN_BET,
    WIN_MULTI,
    coins,
    flip,
    result_line,
)
from .slash_blackjack import has_live_hand

logger = logging.getLogger("aetherion.slash_cointoss")

_sessions: dict[int, dict[str, object]] = {}
_busy: set[int] = set()

EMBED_FLIP = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
EMBED_SIDE = 0xC9A227
IMAGE_NAME = "coin.png"
THUMB_NAME = "coin_thumb.png"


def has_live_hand_safe(user_id: int) -> bool:
    try:
        return bool(has_live_hand(user_id))
    except Exception:
        return False


def _set_disabled(view: discord.ui.View, disabled: bool) -> None:
    for child in view.children:
        if isinstance(child, (discord.ui.Button,)):
            child.disabled = disabled


def _png(name: str, raw: bytes) -> discord.File:
    return discord.File(io.BytesIO(raw), filename=name)


class BetModal(discord.ui.Modal, title="Change bet"):
    amount = discord.ui.TextInput(
        label="Aether Coins",
        placeholder=f"{TOSS_MIN_BET}\u2013{TOSS_MAX_BET}",
        required=True,
        max_length=6,
    )

    def __init__(self, view: "TossView"):
        super().__init__()
        self.toss_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.amount.value or "").replace(",", "").strip()
        try:
            bet = int(raw)
        except ValueError:
            await interaction.response.send_message("Bet has to be a whole number.", ephemeral=True)
            return
        if bet < TOSS_MIN_BET or bet > TOSS_MAX_BET:
            await interaction.response.send_message(
                f"Bet must be {TOSS_MIN_BET}\u2013{TOSS_MAX_BET} Aether Coins.",
                ephemeral=True,
            )
            return
        session = _sessions.setdefault(
            self.toss_view.user_id, {"bet": TOSS_DEFAULT_BET}
        )
        session["bet"] = bet
        await interaction.response.send_message(f"Next toss is **{coins(bet)}**.", ephemeral=True)


class TossView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your toss.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Heads", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _run_toss(interaction, user_id=self.user_id, pick=HEADS, edit=True, view=self)

    @discord.ui.button(label="Tails", style=discord.ButtonStyle.primary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _run_toss(interaction, user_id=self.user_id, pick=TAILS, edit=True, view=self)

    @discord.ui.button(label="Change Bet", style=discord.ButtonStyle.secondary)
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal(self))


def _toss_embed(* , pocket: int, winnings_text: str, body: str, bet: int, color: int) -> discord.Embed:
    desc = (
        f"**Pocket** \u00b7 {coins(f'**{pocket:,}**')}\n"
        f"**Winnings** \u00b7 {coins(f'**{winnings_text}**')}\n\n"
        f"{body}"
    )
    embed = discord.Embed(title="\u2726 Coin Toss", description=desc, color=color)
    embed.set_footer(
        text=(
            f"Bet: {coins(f'{bet:,}')}  |  Correct: {WIN_MULTI:g}x  |  Side: {SIDE_MULTI:g}x"
        )
    )
    return embed


async def _publish(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View,
    as_edit: bool,
    image: discord.File | None,
    thumb: discord.File | None,
) -> None:
    files: list[discord.File] = []
    if image is not None:
        embed.set_image(url=f"attachment://{IMAGE_NAME}")
        files.append(image)
    if thumb is not None:
        embed.set_thumbnail(url=f"attachment://{THUMB_NAME}")
        files.append(thumb)
    if not interaction.response.is_done():
        if as_edit:
            kwargs = {"embed": embed, "view": view}
            if files:
                kwargs["attachments"] = files
            await interaction.response.edit_message(**kwargs)
        else:
            kwargs = {"embed": embed, "view": view}
            if files:
                kwargs["files"] = files
            await interaction.response.send_message(**kwargs)
        return
    kwargs = {"embed": embed, "view": view}
    if files:
        kwargs["attachments"] = files
    await interaction.edit_original_response(**kwargs)


async def _run_toss(
    interaction: discord.Interaction,
    *,
    user_id: int,
    pick: str,
    edit: bool,
    view: TossView | None,
) -> None:
    if user_id in _busy:
        msg = "The coin is still in the air."
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
    session = _sessions.setdefault(user_id, {"bet": TOSS_DEFAULT_BET})
    bet = int(session.get("bet") or TOSS_DEFAULT_BET)
    ai_coins.refund_stale_pending(user_id)
    if bet < TOSS_MIN_BET or bet > TOSS_MAX_BET:
        msg = f"Bet must be {TOSS_MIN_BET}\u2013{TOSS_MAX_BET} Aether Coins."
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

    send_view = view or TossView(user_id)
    _set_disabled(send_view, True)
    _busy.add(user_id)
    try:
        result = flip(pick, bet)
        first = True
        for tilt, y_frac in FLIP_BEATS:
            frame = _toss_embed(
                pocket=pocket,
                winnings_text="Flipping\u2026",
                body="The Aether coin is in the air.",
                bet=bet,
                color=EMBED_FLIP,
            )
            await _publish(
                interaction,
                embed=frame,
                view=send_view,
                as_edit=edit if first else True,
                image=_png(IMAGE_NAME, render_flip_frame(tilt, y_frac)),
                thumb=None,
            )
            first = False
            await asyncio.sleep(FLIP_SLEEP)
        land_body = "It lands on its side." if result.landed == "side" else "The Aether coin lands."
        land = _toss_embed(
            pocket=pocket,
            winnings_text="Flipping\u2026",
            body=land_body,
            bet=bet,
            color=EMBED_FLIP,
        )
        await _publish(
            interaction,
            embed=land,
            view=send_view,
            as_edit=True,
            image=_png(IMAGE_NAME, render_result(result.landed)),
            thumb=None,
        )
        await asyncio.sleep(0.35)
        ok, balance, err = ai_coins.resolve_wager(
            user_id, result.bet, result.winnings, min_bet=TOSS_MIN_BET, max_bet=TOSS_MAX_BET
        )
        if not ok:
            _set_disabled(send_view, False)
            await interaction.edit_original_response(view=send_view)
            await interaction.followup.send(err, ephemeral=True)
            return
        _sessions[user_id] = {"bet": result.bet}
        if result.landed == "side":
            color = EMBED_SIDE
        elif result.won:
            color = EMBED_WIN
        else:
            color = EMBED_LOSE
        net = f"+{result.net:,}" if result.net > 0 else f"{result.net:,}"
        final = _toss_embed(
            pocket=balance,
            winnings_text=net,
            body=result_line(result),
            bet=result.bet,
            color=color,
        )
        _set_disabled(send_view, False)
        await _publish(
            interaction,
            embed=final,
            view=send_view,
            as_edit=True,
            image=_png(IMAGE_NAME, render_result(result.landed)),
            thumb=_png(THUMB_NAME, render_thumb(result.landed)),
        )
    except Exception:
        logger.exception("cointoss failed user=%s", user_id)
        try:
            _set_disabled(send_view, False)
            await interaction.edit_original_response(view=send_view)
        except Exception:
            pass
    finally:
        _busy.discard(user_id)


def register_cointoss(tree, is_guild_allowed) -> None:
    @tree.command(name="cointoss", description="Flip an Aether coin for Aether Coins.")
    @discord.app_commands.describe(
        bet=f"Wager in Aether Coins ({TOSS_MIN_BET}\u2013{TOSS_MAX_BET})",
        side="Call heads or tails",
    )
    @discord.app_commands.choices(
        side=[
            discord.app_commands.Choice(name="Heads", value=HEADS),
            discord.app_commands.Choice(name="Tails", value=TAILS),
        ]
    )
    async def cointoss_slash(
        interaction: discord.Interaction,
        bet: int = TOSS_DEFAULT_BET,
        side: discord.app_commands.Choice[str] | None = None,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        session = _sessions.setdefault(interaction.user.id, {"bet": TOSS_DEFAULT_BET})
        if bet == TOSS_DEFAULT_BET and session.get("bet"):
            bet = int(session["bet"])
        else:
            session["bet"] = int(bet)
        pick = side.value if side is not None else None
        if pick is None:
            pocket = ai_coins.get_balance(interaction.user.id)
            embed = _toss_embed(
                pocket=pocket,
                winnings_text="0",
                body="Call **Heads** or **Tails**. A rare side landing pays 2.5x.",
                bet=int(session["bet"]),
                color=EMBED_FLIP,
            )
            view = TossView(interaction.user.id)
            await _publish(
                interaction,
                embed=embed,
                view=view,
                as_edit=False,
                image=_png(IMAGE_NAME, render_result("heads")),
                thumb=_png(THUMB_NAME, render_thumb("heads")),
            )
            return
        await _run_toss(
            interaction,
            user_id=interaction.user.id,
            pick=pick,
            edit=False,
            view=None,
        )
