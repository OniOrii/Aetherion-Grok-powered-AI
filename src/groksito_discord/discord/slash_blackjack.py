"""Slash blackjack against Aetherion. Fair shoe + Aether Coin stakes."""
from __future__ import annotations

import io
import logging

import discord

from . import ai_coins
from .blackjack import Hand, hand_value
from .blackjack_table import render_hand_png
from groksito_discord.llm.persona import creator_is_author

logger = logging.getLogger("aetherion.slash_blackjack")

_games: dict[int, Hand] = {}

EMBED_PLAY = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
EMBED_PUSH = 0x8A8F98
TABLE_NAME = "blackjack.png"


def _can_double(hand: Hand, pocket: int) -> bool:
    return (
        not hand.finished
        and not hand.doubled
        and len(hand.player) == 2
        and pocket >= hand.bet
    )


def _embed_for(hand: Hand, *, balance: int, reveal: bool) -> discord.Embed:
    hide = not reveal and not hand.finished
    player_total = hand_value(hand.player)
    dealer_total_text = (
        f"{hand_value(hand.dealer[:1])}+" if hide else str(hand_value(hand.dealer))
    )

    if hand.finished:
        if hand.outcome in ("player_bj", "win"):
            color = EMBED_WIN
            title = "Blackjack \u2014 you take it"
        elif hand.outcome in ("push", "both_bj"):
            color = EMBED_PUSH
            title = "Blackjack \u2014 push"
        else:
            color = EMBED_LOSE
            title = "Blackjack \u2014 dealer table"
        footer = hand.result_line()
    else:
        color = EMBED_PLAY
        title = "Blackjack"
        footer = "Hit, stand, or double. Only you can press the buttons."

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="You", value=str(player_total), inline=True)
    embed.add_field(name="Aetherion", value=dealer_total_text, inline=True)
    embed.add_field(name="Bet", value=f"{hand.bet} Aether Coins", inline=True)
    embed.add_field(name="Wallet", value=f"{balance} Aether Coins", inline=True)
    embed.set_footer(text=footer)
    return embed


def _table_file(hand: Hand, *, reveal: bool) -> discord.File | None:
    try:
        raw = render_hand_png(hand, reveal=reveal)
        return discord.File(io.BytesIO(raw), filename=TABLE_NAME)
    except Exception:
        logger.exception("blackjack table render failed")
        return None


def _attach_image(embed: discord.Embed, table: discord.File | None) -> discord.Embed:
    if table is not None:
        embed.set_image(url=f"attachment://{TABLE_NAME}")
    return embed


class BlackjackView(discord.ui.View):
    def __init__(self, user_id: int, can_double: bool):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.message: discord.Message | None = None
        if not can_double:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == "bj_double":
                    item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This is not your hand.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        hand = _games.get(self.user_id)
        if hand is None or hand.finished:
            return
        try:
            hand.stand()
            balance = ai_coins.settle_hand(self.user_id, hand.credit())
            _games.pop(self.user_id, None)
            if self.message is not None:
                table = _table_file(hand, reveal=True)
                embed = _attach_image(_embed_for(hand, balance=balance, reveal=True), table)
                kwargs = {
                    "embed": embed,
                    "view": None,
                    "content": "Hand timed out. Stood automatically.",
                }
                if table is not None:
                    kwargs["attachments"] = [table]
                await self.message.edit(**kwargs)
        except Exception:
            logger.exception("blackjack timeout settle failed user=%s", self.user_id)
            _games.pop(self.user_id, None)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="bj_hit")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _act(interaction, self, "hit")

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="bj_stand")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _act(interaction, self, "stand")

    @discord.ui.button(label="Double", style=discord.ButtonStyle.success, custom_id="bj_double")
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _act(interaction, self, "double")


async def _act(interaction: discord.Interaction, view: BlackjackView, action: str) -> None:
    hand = _games.get(view.user_id)
    if hand is None or hand.finished:
        await interaction.response.send_message("That hand is already over.", ephemeral=True)
        return

    if action == "double":
        extra = hand.bet
        ok, _bal, err = ai_coins.add_to_pending(view.user_id, extra)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        hand.double()
    elif action == "hit":
        hand.hit()
    else:
        hand.stand()

    reveal = hand.finished
    if hand.finished:
        balance = ai_coins.settle_hand(view.user_id, hand.credit())
        _games.pop(view.user_id, None)
        view.stop()
        view_to_send = None
    else:
        balance = ai_coins.get_balance(view.user_id)
        for item in view.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == "bj_double":
                item.disabled = True
        view_to_send = view

    table = _table_file(hand, reveal=reveal)
    embed = _attach_image(_embed_for(hand, balance=balance, reveal=reveal), table)
    kwargs = {"embed": embed, "view": view_to_send}
    if table is not None:
        kwargs["attachments"] = [table]
    await interaction.response.edit_message(**kwargs)


def register_blackjack(tree, is_guild_allowed) -> None:
    @tree.command(name="blackjack", description="Play blackjack against Aetherion for Aether Coins")
    @discord.app_commands.describe(bet=f"Wager in Aether Coins ({ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}, default {ai_coins.DEFAULT_BET})")
    async def blackjack_slash(
        interaction: discord.Interaction,
        bet: int = ai_coins.DEFAULT_BET,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return

        user_id = interaction.user.id
        if user_id in _games and not _games[user_id].finished:
            await interaction.response.send_message(
                "Finish the hand already on the table first.", ephemeral=True
            )
            return
        _games.pop(user_id, None)
        refunded = ai_coins.refund_stale_pending(user_id)

        ok, _remaining, err = ai_coins.hold_bet(user_id, bet)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return

        hand = Hand(user_id=user_id, bet=int(bet))
        hand.deal_opening()
        pocket = ai_coins.get_balance(user_id)
        note = (
            f"Returned {refunded} Aether Coins from a hand that died in a restart."
            if refunded
            else None
        )

        if hand.finished:
            pocket = ai_coins.settle_hand(user_id, hand.credit())
            table = _table_file(hand, reveal=True)
            embed = _attach_image(_embed_for(hand, balance=pocket, reveal=True), table)
            kwargs = {"content": note, "embed": embed}
            if table is not None:
                kwargs["file"] = table
            await interaction.response.send_message(**kwargs)
            return

        _games[user_id] = hand
        view = BlackjackView(user_id, can_double=_can_double(hand, pocket))
        table = _table_file(hand, reveal=False)
        embed = _attach_image(_embed_for(hand, balance=pocket, reveal=False), table)
        kwargs = {"content": note, "embed": embed, "view": view}
        if table is not None:
            kwargs["file"] = table
        await interaction.response.send_message(**kwargs)
        try:
            view.message = await interaction.original_response()
        except Exception:
            logger.exception("blackjack failed to capture table message user=%s", user_id)

    @tree.command(name="balance", description="See your Aether Coin wallet")
    async def balance_slash(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        live = _games.get(interaction.user.id)
        refunded = 0
        if live is None or live.finished:
            refunded = ai_coins.refund_stale_pending(interaction.user.id)
        bal = ai_coins.get_balance(interaction.user.id)
        extra = f" Returned {refunded} from a dead hand." if refunded else ""
        await interaction.response.send_message(
            f"You have **{bal} Aether Coins**.{extra} New players start at {ai_coins.STARTING_BALANCE}.",
            ephemeral=True,
        )

    @tree.command(name="daily", description="Claim today's free Aether Coins")
    async def daily_slash(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        live = _games.get(interaction.user.id)
        if live is None or live.finished:
            ai_coins.refund_stale_pending(interaction.user.id)
        bal, granted, already = ai_coins.claim_daily(interaction.user.id)
        if already:
            await interaction.response.send_message(
                f"Already claimed today. Wallet: **{bal} Aether Coins**. Next drip after midnight Eastern.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"Claimed **{granted} Aether Coins**. Wallet: **{bal}**.",
            ephemeral=True,
        )

    @tree.command(name="leaderboard", description="Aether Coin standings on this server")
    async def leaderboard_slash(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Leaderboard only works in a server.", ephemeral=True
            )
            return
        await interaction.response.defer(thinking=True)
        rows = ai_coins.snapshot_wallets()
        ranked: list[tuple[int, int, str]] = []
        for uid, bal, pending in rows:
            member = guild.get_member(uid)
            if member is None:
                try:
                    member = await guild.fetch_member(uid)
                except Exception:
                    member = None
            if member is None:
                continue
            wealth = bal + pending
            ranked.append((wealth, uid, member.display_name))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        top = ranked[:10]
        embed = discord.Embed(
            title=f"Aether Coin leaderboard \u00b7 {guild.name}",
            color=EMBED_PLAY,
        )
        if not top:
            embed.description = "Nobody on this server has a wallet yet. Play `/blackjack` to start."
        else:
            medals = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}
            lines = []
            for i, (wealth, uid, name) in enumerate(top, start=1):
                mark = medals.get(i, f"`{i}.`")
                you = " \u2190 you" if uid == interaction.user.id else ""
                lines.append(f"{mark} **{name}** \u2014 {wealth} Aether Coins{you}")
            embed.description = "\n".join(lines)
            yours = next((i for i, row in enumerate(ranked, start=1) if row[1] == interaction.user.id), None)
            if yours and yours > 10:
                embed.set_footer(text=f"You are #{yours} of {len(ranked)} on this server.")
            else:
                embed.set_footer(text=f"{len(ranked)} wallets on this server. Mid-hand bets count.")
        await interaction.followup.send(embed=embed)

    @tree.command(name="givecoins", description="Ori only: grant Aether Coins to a member")
    @discord.app_commands.describe(
        member="Who receives the coins",
        amount=f"How many coins ({ai_coins.MIN_GRANT}\u2013{ai_coins.MAX_GRANT})",
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def givecoins_slash(
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if not creator_is_author(interaction.user.id):
            await interaction.response.send_message(
                "Only Ori can grant Aether Coins.", ephemeral=True
            )
            return
        ok, bal, err = ai_coins.grant_coins(member.id, amount)
        if not ok:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message(
            f"Granted **{amount} Aether Coins** to {member.mention}. Their wallet is now **{bal}**.",
            ephemeral=True,
        )
