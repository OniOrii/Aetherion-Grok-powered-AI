"""Public /profile and /server. Discord facts plus Aether Coins. Activity is this server only."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from ..config import settings
from . import activity
from . import activity_card
from . import ai_coins
from .brand import GOLD, stamp
from .slash_autorole import get_guild_autorole_id
from .slash_logs import get_guild_cfg
from .welcome import get_guild_welcome_channel_id
from .date_dock import get_guild_date_channel_id

logger = logging.getLogger("aetherion.slash_profile")
EASTERN = ZoneInfo("America/Detroit")


def _dt(value) -> str:
    if value is None:
        return "Unknown"
    return f"{discord.utils.format_dt(value, 'D')} ({discord.utils.format_dt(value, 'R')})"


def _tenure(joined) -> str:
    if joined is None:
        return "Unknown"
    now = discord.utils.utcnow()
    if joined.tzinfo is None:
        joined = joined.replace(tzinfo=now.tzinfo)
    days = max(0, (now - joined).days)
    if days < 1:
        return "Joined today"
    if days < 31:
        return f"{days} day" + ("" if days == 1 else "s")
    years, rem = divmod(days, 365)
    months = rem // 30
    if years:
        return f"{years}y {months}mo" if months else f"{years}y"
    return f"{months} mo"


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


def _accent(member: discord.Member) -> int:
    colored = [
        r
        for r in member.roles
        if not r.is_default() and getattr(r.color, "value", 0)
    ]
    if not colored:
        return GOLD
    colored.sort(key=lambda r: r.position, reverse=True)
    return int(colored[0].color.value)


def _last_daily(user_id: int) -> str | None:
    try:
        path = Path(getattr(settings, "data_dir", Path("./data"))) / "ai_coins.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        row = (data.get("users") or {}).get(str(int(user_id)))
        if isinstance(row, dict):
            raw = row.get("last_daily")
            return str(raw) if raw else None
    except Exception:
        logger.exception("daily peek failed")
    return None


def _daily_line(user_id: int, *, house: bool) -> str:
    if house:
        return "House \u00b7 no daily"
    today = datetime.now(EASTERN).date().isoformat()
    last = _last_daily(user_id)
    if last == today:
        return "Claimed today"
    return f"Open \u00b7 {ai_coins.coins(f'{ai_coins.DAILY_DRIP:,}')} via `/daily`"


def _wallet_lines(user_id: int, *, house: bool) -> tuple[str, str]:
    lookup = ai_coins.HOUSE_ID if house else int(user_id)
    rows = ai_coins.snapshot_wallets()
    people = list(rows)
    people.sort(key=lambda row: row[1] + row[2], reverse=True)
    match = next((row for row in people if row[0] == lookup), None)
    if match is None:
        return "No wallet yet", "Play a game or claim `/daily`."
    coins = ai_coins.coins(f"{match[1]:,}")
    rank = next(i for i, row in enumerate(people, start=1) if row[0] == lookup)
    label = f"House \u00b7 #{rank} of {len(people)}" if house else f"#{rank} of {len(people)}"
    return coins, label


def profile_embed(member: discord.Member, bot_user=None) -> discord.Embed:
    house = bool(bot_user and member.id == getattr(bot_user, "id", 0))
    embed = discord.Embed(
        title=f"\u2726 {member.display_name}",
        description=f"{member.mention} \u00b7 `{member.id}`",
        color=_accent(member),
    )
    av = getattr(member, "display_avatar", None)
    if av is not None:
        embed.set_thumbnail(url=str(av.url))
    embed.add_field(name="Account", value=_dt(getattr(member, "created_at", None)), inline=True)
    embed.add_field(name="Joined", value=_dt(getattr(member, "joined_at", None)), inline=True)
    embed.add_field(name="In server", value=_tenure(getattr(member, "joined_at", None)), inline=True)
    boost = getattr(member, "premium_since", None)
    embed.add_field(name="Boost", value=_dt(boost) if boost else "No", inline=True)
    timeout = getattr(member, "timed_out_until", None)
    if timeout:
        embed.add_field(name="Timeout", value=_dt(timeout), inline=True)
    voice = getattr(getattr(member, "voice", None), "channel", None)
    if voice is not None:
        embed.add_field(name="Voice", value=voice.mention, inline=True)
    coins, rank = _wallet_lines(member.id, house=house)
    embed.add_field(name="Aether Coins", value=coins, inline=True)
    embed.add_field(name="Wallet rank", value=rank, inline=True)
    embed.add_field(name="Daily", value=_daily_line(member.id, house=house), inline=True)
    embed.add_field(name="Roles", value=_roles_line(member), inline=False)
    extra = "house wallet" if house else (
        "bot account" if getattr(member, "bot", False) else "card \u00b7 this server"
    )
    return stamp(embed, bot_user, extra=extra)


async def _avatar_bytes(member: discord.Member) -> bytes | None:
    av = getattr(member, "display_avatar", None)
    if av is None:
        return None
    try:
        return await av.read()
    except Exception:
        logger.exception("avatar fetch failed")
        return None


def activity_embed(member: discord.Member, bot_user=None, snap=None) -> discord.Embed:
    guild = member.guild
    if snap is None:
        snap = activity.snapshot(guild.id, member.id, guild) if guild is not None else {
            "started": "\u2014",
            "messages": 0,
            "voice_seconds": 0,
            "xp": 0,
            "level": 0,
            "into": 0,
            "need": activity.xp_need(0),
            "msg_rank": None,
            "voice_rank": None,
            "top_channels": [],
        }
    embed = discord.Embed(
        title=f"\u2726 {member.display_name} \u00b7 Activity",
        description="Lifetime on this server.",
        color=_accent(member),
    )
    embed.set_image(url="attachment://activity.png")
    return stamp(embed, bot_user, extra="activity \u00b7 lifetime \u00b7 this server")


async def activity_payload(member: discord.Member, bot_user=None):
    guild = member.guild
    snap = activity.snapshot(guild.id, member.id, guild) if guild is not None else {
        "started": "\u2014",
        "messages": 0,
        "voice_seconds": 0,
        "xp": 0,
        "level": 0,
        "into": 0,
        "need": activity.xp_need(0),
        "msg_rank": None,
        "voice_rank": None,
        "top_channels": [],
    }
    raw = await _avatar_bytes(member)
    try:
        buf = activity_card.render_activity_card(member, snap, raw)
        image = discord.File(buf, filename="activity.png")
        return activity_embed(member, bot_user, snap), image
    except Exception:
        logger.exception("activity card render failed")
        embed = discord.Embed(
            title=f"\u2726 {member.display_name} \u00b7 Activity",
            description=f"{member.mention} \u00b7 this server only \u00b7 lifetime",
            color=_accent(member),
        )
        embed.add_field(name="Level", value=str(snap.get("level") or 0), inline=True)
        embed.add_field(name="Messages", value=f"{int(snap.get('messages') or 0):,}", inline=True)
        embed.add_field(name="Voice", value=activity.format_voice(int(snap.get("voice_seconds") or 0)), inline=True)
        return stamp(embed, bot_user, extra="activity \u00b7 lifetime \u00b7 this server"), None


class ProfileView(discord.ui.View):
    def __init__(self, actor_id: int, member: discord.Member, bot_user=None, page: str = "card"):
        super().__init__(timeout=180)
        self.actor_id = actor_id
        self.member = member
        self.bot_user = bot_user
        self.page = page
        self._sync()

    def _sync(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = child.custom_id == self.page

    def embed(self) -> discord.Embed:
        return profile_embed(self.member, self.bot_user)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message("This profile menu is not yours. Run `/profile`.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Card", style=discord.ButtonStyle.primary, custom_id="card")
    async def card_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "card"
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), attachments=[], view=self)

    @discord.ui.button(label="Activity", style=discord.ButtonStyle.secondary, custom_id="activity")
    async def activity_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = "activity"
        self._sync()
        embed, image = await activity_payload(self.member, self.bot_user)
        files = [image] if image is not None else []
        await interaction.response.edit_message(embed=embed, attachments=files, view=self)


def _richest_line(guild: discord.Guild, snap: list) -> str:
    players = [row for row in snap if row[0] != ai_coins.HOUSE_ID]
    if not players:
        return "No player wallets yet"
    top = max(players, key=lambda row: row[1])
    who = guild.get_member(top[0])
    name = who.mention if who is not None else f"`{top[0]}`"
    return f"{name} \u00b7 {ai_coins.coins(f'{top[1]:,}')}"


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
    embed.add_field(
        name="Members",
        value=f"{guild.member_count or humans + bots} \u00b7 {humans} people \u00b7 {bots} bots",
        inline=False,
    )
    embed.add_field(name="Boosts", value=f"Tier {tier} \u00b7 {boosts}", inline=True)
    embed.add_field(
        name="Channels",
        value=f"{text_n} text \u00b7 {voice_n} voice" + (f" \u00b7 {forum_n} forum" if forum_n else ""),
        inline=True,
    )
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
        value=(
            f"{len(wallets)} wallets \u00b7 house {ai_coins.coins(f'{house_bal:,}')}\n"
            f"Richest {_richest_line(guild, snap)}"
        ),
        inline=False,
    )
    return stamp(embed, bot_user, extra="snapshot of this server")


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
        view = ProfileView(interaction.user.id, target, bot_user)
        await interaction.response.send_message(embed=view.embed(), view=view)

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
