"""Public /profile and /server. Discord facts plus Aether Coins. No XP."""
from __future__ import annotations

import logging

import discord

from . import ai_coins
from .brand import GOLD, stamp
from .slash_autorole import get_guild_autorole_id
from .slash_logs import get_guild_cfg
from .welcome import get_guild_welcome_channel_id
from .date_dock import get_guild_date_channel_id

logger = logging.getLogger("aetherion.slash_profile")


def _dt(value) -> str:
    if value is None:
        return "Unknown"
    return f"{discord.utils.format_dt(value, 'D')} ({discord.utils.format_dt(value, 'R')})"


def _roles_line(member: discord.Member) -> str:
    roles = [r for r in member.roles if not r.is_default()]
    roles.sort(key=lambda r: r.position, reverse=True)
    if not roles:
        return "*none*"
    shown = roles[:12]
    text = " ".join(r.mention for r in shown)
    extra = len(roles) - len(shown)
    if extra:
        text += f" +{extra}"
    return text[:1024]


def _wallet_lines(user_id: int) -> tuple[str, str]:
    rows = ai_coins.snapshot_wallets()
    people = [(uid, bal, pending) for uid, bal, pending in rows]
    people.sort(key=lambda row: row[1] + row[2], reverse=True)
    match = next((row for row in people if row[0] == int(user_id)), None)
    if match is None:
        return "No wallet yet", "Play a game or claim `/daily`."
    bal, pending = match[1], match[2]
    rank = next(i for i, row in enumerate(people, start=1) if row[0] == int(user_id))
    coins = ai_coins.coins(f"{bal:,}")
    if pending:
        coins += f" \u00b7 held {ai_coins.coins(f'{pending:,}')}"
    return coins, f"#{rank} of {len(people)}"


def profile_embed(member: discord.Member, bot_user=None) -> discord.Embed:
    embed = discord.Embed(
        title=f"\u2726 {member.display_name}",
        description=f"{member.mention} \u00b7 `{member.id}`",
        color=GOLD,
    )
    av = getattr(member, "display_avatar", None)
    if av is not None:
        embed.set_thumbnail(url=str(av.url))
    embed.add_field(name="Account", value=_dt(getattr(member, "created_at", None)), inline=True)
    embed.add_field(name="Joined", value=_dt(getattr(member, "joined_at", None)), inline=True)
    boost = getattr(member, "premium_since", None)
    embed.add_field(name="Boost", value=_dt(boost) if boost else "No", inline=True)
    timeout = getattr(member, "timed_out_until", None)
    if timeout:
        embed.add_field(name="Timeout", value=_dt(timeout), inline=True)
    voice = getattr(getattr(member, "voice", None), "channel", None)
    if voice is not None:
        embed.add_field(name="Voice", value=voice.mention, inline=True)
    coins, rank = _wallet_lines(member.id)
    embed.add_field(name="Aether Coins", value=coins, inline=True)
    embed.add_field(name="Wallet rank", value=rank, inline=True)
    embed.add_field(name="Roles", value=_roles_line(member), inline=False)
    extra = "bot account" if getattr(member, "bot", False) else "no levels \u00b7 coins + Discord facts"
    return stamp(embed, bot_user, extra=extra)


def server_embed(guild: discord.Guild, bot_user=None) -> discord.Embed:
    humans = sum(1 for m in guild.members if not m.bot)
    bots = sum(1 for m in guild.members if m.bot)
    text_n = len(guild.text_channels)
    voice_n = len(guild.voice_channels)
    forum_n = len(getattr(guild, "forums", []) or [])
    owner = getattr(guild, "owner", None)
    owner_line = owner.mention if owner is not None else (f"<@{guild.owner_id}>" if guild.owner_id else "Unknown")
    boosts = int(getattr(guild, "premium_subscription_count", 0) or 0)
    tier = int(getattr(guild, "premium_tier", 0) or 0)
    verify = str(getattr(guild, "verification_level", "unknown")).replace("_", " ").title()

    embed = discord.Embed(
        title=f"\u2726 {guild.name}",
        description=guild.description or None,
        color=GOLD,
    )
    icon = getattr(guild, "icon", None)
    if icon is not None:
        embed.set_thumbnail(url=str(icon.url))
    embed.add_field(name="Owner", value=owner_line, inline=True)
    embed.add_field(name="Created", value=_dt(getattr(guild, "created_at", None)), inline=True)
    embed.add_field(name="Members", value=f"{guild.member_count or humans + bots} \u00b7 {humans} people \u00b7 {bots} bots", inline=False)
    embed.add_field(name="Boosts", value=f"Tier {tier} \u00b7 {boosts}", inline=True)
    embed.add_field(name="Channels", value=f"{text_n} text \u00b7 {voice_n} voice" + (f" \u00b7 {forum_n} forum" if forum_n else ""), inline=True)
    embed.add_field(name="Roles / emoji", value=f"{len(guild.roles)} \u00b7 {len(guild.emojis)}", inline=True)
    embed.add_field(name="Verification", value=verify, inline=True)

    welcome_id = get_guild_welcome_channel_id(guild.id)
    date_id = get_guild_date_channel_id(guild.id)
    auto_id = get_guild_autorole_id(guild.id)
    logs = get_guild_cfg(guild.id)
    log_id = int(logs.get("channel_id") or 0)
    log_on = sum(1 for v in (logs.get("events") or {}).values() if v)

    def ch(cid: int) -> str:
        return f"<#{cid}>" if cid else "*not set*"

    role = guild.get_role(auto_id) if auto_id else None
    auto_line = role.mention if role is not None else ("*missing role*" if auto_id else "*not set*")
    embed.add_field(
        name="Aetherion setup",
        value=(
            f"Welcome {ch(welcome_id)}\n"
            f"Logs {ch(log_id)} \u00b7 {log_on} events on\n"
            f"Date dock {ch(date_id)}\n"
            f"Auto-role {auto_line}"
        ),
        inline=False,
    )

    snap = ai_coins.snapshot_wallets()
    wallets = [row for row in snap if row[0] != ai_coins.HOUSE_ID]
    house = next((row for row in snap if row[0] == ai_coins.HOUSE_ID), None)
    house_bal = house[1] if house else ai_coins.HOUSE_START
    embed.add_field(
        name="Aether Coins",
        value=f"{len(wallets)} wallets \u00b7 house {ai_coins.coins(f'{house_bal:,}')}",
        inline=False,
    )
    return stamp(embed, bot_user, extra="no levels \u00b7 snapshot of this server")


def register_profile(tree, is_guild_allowed) -> None:
    @tree.command(name="profile", description="Show a member's Discord facts and Aether Coin wallet.")
    @discord.app_commands.describe(member="Who to look up. Leave empty for yourself.")
    @discord.app_commands.guild_only()
    async def profile_slash(interaction: discord.Interaction, member: discord.Member | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Use /profile in a server.", ephemeral=True)
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        target = member or interaction.guild.get_member(interaction.user.id) or interaction.user
        if not isinstance(target, discord.Member):
            fetched = interaction.guild.get_member(getattr(target, "id", 0))
            if fetched is None:
                await interaction.response.send_message("That person is not in this server.", ephemeral=True)
                return
            target = fetched
        bot_user = getattr(interaction.client, "user", None)
        await interaction.response.send_message(embed=profile_embed(target, bot_user))

    @tree.command(name="server", description="Show this server's stats and Aetherion setup.")
    @discord.app_commands.guild_only()
    async def server_slash(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Use /server in a server.", ephemeral=True)
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        bot_user = getattr(interaction.client, "user", None)
        await interaction.response.send_message(embed=server_embed(interaction.guild, bot_user))
