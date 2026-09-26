"""Slash Higher or Lower against Aetherion. Odds-priced ladder + Aether Coins."""
from __future__ import annotations

import asyncio
import io
import logging

import discord

from . import ai_coins
from .higher_lower import (
    HIGHER,
    HL_DEFAULT_BET,
    HL_MAX_BET,
    HL_MIN_BET,
    LOWER,
    MAX_STEPS,
    HighLowRound,
    draw_rank,
)
from .higher_lower_art import render_table
from .slash_blackjack import has_live_hand

logger = logging.getLogger("aetherion.slash_highlow")

_games: dict[int, HighLowRound] = {}
_last_bet: dict[int, int] = {}
_busy: set[int] = set()

EMBED_PLAY = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
EMBED_PUSH = 0x8A8F98
IMAGE_NAME = "highlow.png"


def has_live_highlow(user_id: int) -> bool:
    game = _games.get(user_id)
    return game is not None and not game.finished


def has_live_hand_safe(user_id: int) -> bool:
    try:
        return bool(has_live_hand(user_id))
    except Exception:
        return False


def _set_disabled(view: discord.ui.View, disabled: bool) -> None:
    for child in view.children:
        if isinstance(child, discord.ui.Button):
            child.disabled = disabled


def _png(raw: bytes) -> discord.File:
    return discord.File(io.BytesIO(raw), filename=IMAGE_NAME)


def _fmt_multi(multi: float) -> str:
    if multi <= 0:
        return "\u2014"
    text = f"{multi:.2f}".rstrip("0").rstrip(".")
    return f"{text}x"


def _body(game: HighLowRound) -> str:
    trail = " \u2192 ".join(f"**{rank}**" for rank in game.history[-6:])
    if game.finished and game.outcome in ("lose", "same"):
        if game.outcome == "same":
            line = f"Same rank. **{game.last_drawn}** misses."
        else:
            way = "Higher" if game.last_side == HIGHER else "Lower"
            line = f"**{game.last_drawn}** was not {way.lower()} than **{game.history[-2]}**."
        return f"{line}\n{trail}"
    if game.finished and game.outcome == "max":
        return f"Six clean calls. Ladder is done.\n{trail}"
    if game.finished and game.outcome == "cash":
        return f"Cashed out after **{game.step}** call{'s' if game.step != 1 else ''}.\n{trail}"
    if game.finished and game.outcome == "push":
        return "Walked before a call. Stake returned."
    hi = _fmt_multi(game.higher_multi())
    lo = _fmt_multi(game.lower_multi())
    return (
        f"This card is **{game.card}**. Same rank misses.\n"
        f"Higher pays **{hi}** \u00b7 Lower pays **{lo}**\n"
        f"{trail}"
    )


def _embed(game: HighLowRound, *, pocket: int, color: int) -> discord.Embed:
    if game.finished:
        if game.outcome in ("cash", "max"):
            title = f"\u2726 Higher or Lower \u00b7 {ai_coins.won_line(game.net())}"
        elif game.outcome == "push":
            title = "\u2726 Higher or Lower \u00b7 Push"
        else:
            title = f"\u2726 Higher or Lower \u00b7 {ai_coins.won_line(game.net())}"
    else:
        title = f"\u2726 Higher or Lower \u00b7 step {game.step + 1}/{MAX_STEPS}"
    desc = (
        f"**Pocket** \u00b7 {ai_coins.coins(f'**{pocket:,}**')}\n"
        f"**On the table** \u00b7 {ai_coins.coins(f'**{game.pot:,}**')}\n"
        f"**Stake** \u00b7 {ai_coins.coins(f'**{game.bet:,}**')}\n\n"
        f"{_body(game)}"
    )
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_footer(text="Odds follow the card. Cash out or climb. Same rank misses.")
    embed.set_image(url=f"attachment://{IMAGE_NAME}")
    return embed


async def _publish(
    interaction: discord.Interaction,
    *,
    embed: discord.Embed,
    view: discord.ui.View | None,
    image: discord.File | None,
    as_edit: bool,
) -> discord.Message | None:
    kwargs: dict = {"embed": embed, "view": view}
    if not interaction.response.is_done():
        if as_edit:
            if image is not None:
                kwargs["attachments"] = [image]
            await interaction.response.edit_message(**kwargs)
        else:
            if image is not None:
                kwargs["file"] = image
            await interaction.response.send_message(**kwargs)
        try:
            return await interaction.original_response()
        except Exception:
            return None
    if image is not None:
        kwargs["attachments"] = [image]
    await interaction.edit_original_response(**kwargs)
    try:
        return await interaction.original_response()
    except Exception:
        return None


class BetModal(discord.ui.Modal, title="Change bet"):
    amount = discord.ui.TextInput(
        label="Aether Coins",
        placeholder=f"{HL_MIN_BET}\u2013{HL_MAX_BET}",
        required=True,
        max_length=6,
    )

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.amount.value or "").replace(",", "").strip()
        try:
            bet = int(raw)
        except ValueError:
            await interaction.response.send_message("Bet has to be a whole number.", ephemeral=True)
            return
        err = ai_coins.amount_error(bet, HL_MIN_BET, HL_MAX_BET)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        _last_bet[self.user_id] = bet
        await interaction.response.send_message(
            f"Next ladder is {ai_coins.coins(f'**{bet:,}**')}.", ephemeral=True
        )


class ReplayView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your ladder.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = int(_last_bet.get(self.user_id) or HL_DEFAULT_BET)
        await _start_round(interaction, user_id=self.user_id, bet=bet, edit=True)

    @discord.ui.button(label="Change Bet", style=discord.ButtonStyle.secondary)
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal(self.user_id))


class HighLowView(discord.ui.View):
    def __init__(self, user_id: int, game: HighLowRound):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.message: discord.Message | None = None
        self._sync(game)

    def _sync(self, game: HighLowRound) -> None:
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "hl_higher":
                child.label = f"Higher \u00b7 {_fmt_multi(game.higher_multi())}"
                child.disabled = not game.can_higher()
            elif child.custom_id == "hl_lower":
                child.label = f"Lower \u00b7 {_fmt_multi(game.lower_multi())}"
                child.disabled = not game.can_lower()
            elif child.custom_id == "hl_cash":
                child.disabled = game.step <= 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your ladder.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        game = _games.get(self.user_id)
        if game is None or game.finished:
            return
        try:
            if game.step:
                game.cash()
                credit = game.credit()
            else:
                game.finished = True
                game.outcome = "push"
                credit = game.bet
            balance = ai_coins.settle_hand(self.user_id, credit)
            _last_bet[self.user_id] = game.bet
            _games.pop(self.user_id, None)
            if self.message is None:
                return
            color = EMBED_WIN if game.net() > 0 else EMBED_PUSH
            embed = _embed(game, pocket=balance, color=color)
            table = _png(render_table(game.card))
            await self.message.edit(
                content="Ladder timed out.",
                embed=embed,
                view=ReplayView(self.user_id),
                attachments=[table],
            )
        except Exception:
            logger.exception("highlow timeout settle failed user=%s", self.user_id)
            _games.pop(self.user_id, None)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.primary, custom_id="hl_higher")
    async def higher(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _call(interaction, self, HIGHER)

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.primary, custom_id="hl_lower")
    async def lower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _call(interaction, self, LOWER)

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.success, custom_id="hl_cash")
    async def cash(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _cash_out(interaction, self)


async def _call(interaction: discord.Interaction, view: HighLowView, side: str) -> None:
    user_id = view.user_id
    game = _games.get(user_id)
    if game is None or game.finished:
        await interaction.response.send_message("That ladder is already over.", ephemeral=True)
        return
    if user_id in _busy:
        await interaction.response.send_message("The next card is already coming.", ephemeral=True)
        return
    if side == HIGHER and not game.can_higher():
        await interaction.response.send_message("Nothing ranks above an Ace.", ephemeral=True)
        return
    if side == LOWER and not game.can_lower():
        await interaction.response.send_message("Nothing ranks below a 2.", ephemeral=True)
        return

    _busy.add(user_id)
    _set_disabled(view, True)
    try:
        pocket = ai_coins.get_balance(user_id)
        flip = _embed(game, pocket=pocket, color=EMBED_PLAY)
        await _publish(
            interaction,
            embed=flip,
            view=view,
            image=_png(render_table(game.card, flipping=True)),
            as_edit=True,
        )
        await asyncio.sleep(0.45)
        drawn = draw_rank()
        result = game.resolve(side, drawn)
        if result in ("lose", "same"):
            balance = ai_coins.settle_hand(user_id, 0)
            _last_bet[user_id] = game.bet
            _games.pop(user_id, None)
            view.stop()
            embed = _embed(game, pocket=balance, color=EMBED_LOSE)
            await _publish(
                interaction,
                embed=embed,
                view=ReplayView(user_id),
                image=_png(render_table(game.history[-2], game.card)),
                as_edit=True,
            )
            return
        if result == "max":
            balance = ai_coins.settle_hand(user_id, game.credit())
            _last_bet[user_id] = game.bet
            _games.pop(user_id, None)
            view.stop()
            embed = _embed(game, pocket=balance, color=EMBED_WIN)
            await _publish(
                interaction,
                embed=embed,
                view=ReplayView(user_id),
                image=_png(render_table(game.history[-2], game.card)),
                as_edit=True,
            )
            return
        pocket = ai_coins.get_balance(user_id)
        view._sync(game)
        _set_disabled(view, False)
        view._sync(game)
        embed = _embed(game, pocket=pocket, color=EMBED_WIN)
        message = await _publish(
            interaction,
            embed=embed,
            view=view,
            image=_png(render_table(game.history[-2], game.card)),
            as_edit=True,
        )
        if message is not None:
            view.message = message
    except Exception:
        logger.exception("highlow call failed user=%s", user_id)
        try:
            _set_disabled(view, False)
            await interaction.edit_original_response(view=view)
        except Exception:
            pass
    finally:
        _busy.discard(user_id)


async def _cash_out(interaction: discord.Interaction, view: HighLowView) -> None:
    user_id = view.user_id
    game = _games.get(user_id)
    if game is None or game.finished:
        await interaction.response.send_message("That ladder is already over.", ephemeral=True)
        return
    if game.step <= 0:
        await interaction.response.send_message("Call once before you cash out.", ephemeral=True)
        return
    game.cash()
    balance = ai_coins.settle_hand(user_id, game.credit())
    _last_bet[user_id] = game.bet
    _games.pop(user_id, None)
    view.stop()
    color = EMBED_WIN if game.net() > 0 else EMBED_PUSH
    embed = _embed(game, pocket=balance, color=color)
    await _publish(
        interaction,
        embed=embed,
        view=ReplayView(user_id),
        image=_png(render_table(game.card)),
        as_edit=True,
    )


async def _start_round(
    interaction: discord.Interaction,
    *,
    user_id: int,
    bet: int,
    edit: bool,
) -> None:
    if has_live_highlow(user_id):
        msg = "Finish the ladder already on the table first."
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

    _games.pop(user_id, None)
    ai_coins.refund_stale_pending(user_id)
    err = ai_coins.amount_error(bet, HL_MIN_BET, HL_MAX_BET)
    if err:
        if interaction.response.is_done():
            await interaction.followup.send(err, ephemeral=True)
        else:
            await interaction.response.send_message(err, ephemeral=True)
        return
    ok, _remaining, hold_err = ai_coins.hold_bet(user_id, bet, max_bet=HL_MAX_BET)
    if not ok:
        if interaction.response.is_done():
            await interaction.followup.send(hold_err, ephemeral=True)
        else:
            await interaction.response.send_message(hold_err, ephemeral=True)
        return

    _last_bet[user_id] = int(bet)
    game = HighLowRound(user_id=user_id, bet=int(bet), card=draw_rank())
    _games[user_id] = game
    pocket = ai_coins.get_balance(user_id)
    view = HighLowView(user_id, game)
    embed = _embed(game, pocket=pocket, color=EMBED_PLAY)
    message = await _publish(
        interaction,
        embed=embed,
        view=view,
        image=_png(render_table(game.card)),
        as_edit=edit,
    )
    view.message = message


def register_highlow(tree, is_guild_allowed) -> None:
    @tree.command(name="highlow", description="Higher or Lower. Odds follow the card. Cash out or climb.")
    @discord.app_commands.describe(bet=f"Wager in Aether Coins ({HL_MIN_BET}\u2013{HL_MAX_BET})")
    async def highlow_slash(
        interaction: discord.Interaction,
        bet: int = HL_DEFAULT_BET,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        user_id = interaction.user.id
        if bet == HL_DEFAULT_BET and user_id in _last_bet:
            bet = int(_last_bet[user_id])
        await _start_round(interaction, user_id=user_id, bet=int(bet), edit=False)
