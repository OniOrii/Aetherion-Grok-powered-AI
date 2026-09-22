"""Carl-style server logs. No Grok calls. Administrators pick a channel and events."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import discord

from ..config import settings

logger = logging.getLogger("aetherion.slash_logs")

LOG_COLOR = 0xC9A227
INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[A-Za-z0-9-]+",
    re.IGNORECASE,
)

EVENTS: dict[str, tuple[str, str]] = {
    "join": ("Join", "Member joined the server"),
    "leave": ("Leave", "Member left the server"),
    "kick": ("Kick", "Member was kicked"),
    "ban": ("Ban", "Member was banned"),
    "unban": ("Unban", "Member was unbanned"),
    "timeout": ("Timeout", "Timeout given or removed"),
    "nickname": ("Nickname", "Nick or username changed"),
    "roles": ("Roles", "Roles added or removed"),
    "avatar": ("Avatar", "Avatar changed"),
    "voicejoin": ("Voice join", "Joined a voice channel"),
    "voicemove": ("Voice move", "Moved between voice channels"),
    "voiceleave": ("Voice leave", "Left a voice channel"),
    "voicemute": ("Voice mute", "Mute, deafen, or server mute"),
    "message_delete": ("Message delete", "A message was deleted"),
    "message_edit": ("Message edit", "A message was edited"),
    "message_purge": ("Message purge", "Bulk messages deleted"),
    "invite": ("Invite posted", "A Discord invite was posted"),
    "channel_create": ("Channel create", "A channel was created"),
    "channel_update": ("Channel update", "A channel was edited"),
    "channel_delete": ("Channel delete", "A channel was deleted"),
    "role_create": ("Role create", "A role was created"),
    "role_update": ("Role update", "A role was edited"),
    "role_delete": ("Role delete", "A role was deleted"),
    "emoji": ("Emoji", "Emoji created, updated, or removed"),
    "server": ("Server", "Server name, icon, or settings"),
}

DEFAULT_ON = {
    "join", "leave", "kick", "ban", "unban", "timeout", "nickname", "roles",
    "voicejoin", "voicemove", "voiceleave", "message_delete", "message_edit",
    "message_purge", "channel_create", "channel_update", "channel_delete",
    "role_create", "role_update", "role_delete",
}


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "server_logs.json"


def _load_store() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("server log store read failed")
        return {}


def _save_store(data: dict) -> None:
    _store_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _empty_events(on: bool = False) -> dict[str, bool]:
    enabled = set(EVENTS) if on else set(DEFAULT_ON)
    return {key: key in enabled for key in EVENTS}


def get_guild_cfg(guild_id: int) -> dict:
    store = _load_store()
    raw = store.get(str(guild_id)) or {}
    if not isinstance(raw, dict):
        raw = {}
    events = _empty_events(False)
    saved = raw.get("events") if isinstance(raw.get("events"), dict) else {}
    for key in EVENTS:
        if key in saved:
            events[key] = bool(saved[key])
    try:
        channel_id = int(raw.get("channel_id") or 0)
    except (TypeError, ValueError):
        channel_id = 0
    return {"channel_id": channel_id, "events": events}


def save_guild_cfg(guild_id: int, cfg: dict) -> dict:
    store = _load_store()
    events = _empty_events(False)
    incoming = cfg.get("events") if isinstance(cfg.get("events"), dict) else {}
    for key in EVENTS:
        if key in incoming:
            events[key] = bool(incoming[key])
    try:
        channel_id = int(cfg.get("channel_id") or 0)
    except (TypeError, ValueError):
        channel_id = 0
    row = {"channel_id": channel_id, "events": events}
    store[str(guild_id)] = row
    _save_store(store)
    return row


def set_log_channel(guild_id: int, channel_id: int) -> dict:
    cfg = get_guild_cfg(guild_id)
    first = not cfg["channel_id"]
    cfg["channel_id"] = int(channel_id)
    if first:
        cfg["events"] = _empty_events(False)
    return save_guild_cfg(guild_id, cfg)


def set_event(guild_id: int, event_key: str, enabled: bool) -> dict:
    cfg = get_guild_cfg(guild_id)
    if event_key in EVENTS:
        cfg["events"][event_key] = bool(enabled)
    return save_guild_cfg(guild_id, cfg)


def set_all_events(guild_id: int, enabled: bool) -> dict:
    cfg = get_guild_cfg(guild_id)
    cfg["events"] = {key: bool(enabled) for key in EVENTS}
    return save_guild_cfg(guild_id, cfg)


def is_administrator(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


def _clip(text: str | None, limit: int = 900) -> str:
    body = (text or "").strip()
    if not body:
        return "*empty*"
    if len(body) <= limit:
        return body
    return body[: limit - 1] + "…"


def _user_line(user) -> str:
    if user is None:
        return "Unknown"
    mention = getattr(user, "mention", None)
    name = getattr(user, "display_name", None) or getattr(user, "name", "Unknown")
    uid = getattr(user, "id", "?")
    if mention:
        return f"{mention} (`{name}` · `{uid}`)"
    return f"**{name}** (`{uid}`)"


def _embed(title: str, description: str | None = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description or None, color=LOG_COLOR, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="Aetherion logs")
    return embed


async def _actor(guild: discord.Guild, action, target_id: int | None = None, seconds: float = 8.0):
    if guild is None:
        return None
    try:
        async for entry in guild.audit_logs(limit=8, action=action):
            created = getattr(entry, "created_at", None)
            if created is not None:
                age = (datetime.now(timezone.utc) - created).total_seconds()
                if age > seconds:
                    continue
            target = getattr(entry, "target", None)
            tid = getattr(target, "id", None)
            if target_id and tid and int(tid) != int(target_id):
                continue
            return getattr(entry, "user", None)
    except Exception:
        return None
    return None


async def emit(guild: discord.Guild | None, event_key: str, embed: discord.Embed, *, source_channel_id: int | None = None) -> None:
    if guild is None or event_key not in EVENTS:
        return
    cfg = get_guild_cfg(guild.id)
    if not cfg["channel_id"] or not cfg["events"].get(event_key):
        return
    if source_channel_id and int(source_channel_id) == int(cfg["channel_id"]):
        if event_key in {"message_delete", "message_edit", "message_purge", "invite"}:
            return
    channel = guild.get_channel(int(cfg["channel_id"]))
    if channel is None or not hasattr(channel, "send"):
        return
    me = getattr(guild, "me", None)
    perms = channel.permissions_for(me) if me is not None else None
    if perms is not None and not perms.send_messages:
        return
    try:
        await channel.send(embed=embed)
    except Exception:
        logger.exception("server log send failed in guild %s", guild.id)


def _status_embed(guild: discord.Guild, cfg: dict) -> discord.Embed:
    channel_id = cfg.get("channel_id") or 0
    channel_txt = f"<#{channel_id}>" if channel_id else "*not set*"
    on = [EVENTS[k][0] for k, v in cfg["events"].items() if v]
    off = [EVENTS[k][0] for k, v in cfg["events"].items() if not v]
    embed = _embed("Server logs", f"Log channel: {channel_txt}")
    embed.add_field(name="On", value=", ".join(on) if on else "*none*", inline=False)
    embed.add_field(name="Off", value=", ".join(off) if off else "*none*", inline=False)
    embed.add_field(name="How to edit", value="`/logs channel:#logs` sets the channel.\n`/logs event:leave enabled:True` toggles one event.\nOr use the menus on this message.", inline=False)
    return embed


def _event_options(cfg: dict) -> list:
    options = []
    for key, (label, desc) in EVENTS.items():
        options.append(discord.SelectOption(label=label, value=key, description=desc[:100], default=bool(cfg["events"].get(key))))
    return options


class LogSetupView(discord.ui.View):
    def __init__(self, *, actor_id: int, guild_id: int):
        super().__init__(timeout=180)
        self.actor_id = actor_id
        self.guild_id = guild_id
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear_items()
        cfg = get_guild_cfg(self.guild_id)
        select = discord.ui.Select(placeholder="Events that stay on", min_values=0, max_values=len(EVENTS), options=_event_options(cfg), custom_id="aetherion_logs_events")
        select.callback = self._on_select
        self.add_item(select)
        all_on = discord.ui.Button(label="Enable all", style=discord.ButtonStyle.success)
        all_on.callback = self._enable_all
        self.add_item(all_on)
        all_off = discord.ui.Button(label="Disable all", style=discord.ButtonStyle.secondary)
        all_off.callback = self._disable_all
        self.add_item(all_off)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message("This log menu is not yours. Run `/logs`.", ephemeral=True)
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction) -> None:
        self._rebuild()
        cfg = get_guild_cfg(self.guild_id)
        guild = interaction.guild
        embed = _status_embed(guild, cfg) if guild else _embed("Server logs")
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        selected = set(interaction.data.get("values") or [])
        cfg = get_guild_cfg(self.guild_id)
        cfg["events"] = {key: key in selected for key in EVENTS}
        save_guild_cfg(self.guild_id, cfg)
        await self._refresh(interaction)

    async def _enable_all(self, interaction: discord.Interaction) -> None:
        set_all_events(self.guild_id, True)
        await self._refresh(interaction)

    async def _disable_all(self, interaction: discord.Interaction) -> None:
        set_all_events(self.guild_id, False)
        await self._refresh(interaction)


def register_logs(tree, is_guild_allowed) -> None:
    choices = [discord.app_commands.Choice(name=label, value=key) for key, (label, _) in EVENTS.items()]

    @tree.command(name="logs", description="Set the server log channel and pick which events Aetherion posts.")
    @discord.app_commands.describe(channel="Channel that receives log embeds", event="One event to turn on or off", enabled="On or off for that event")
    @discord.app_commands.choices(event=choices)
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def logs_slash(interaction: discord.Interaction, channel: discord.TextChannel | None = None, event: discord.app_commands.Choice[str] | None = None, enabled: bool | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Use /logs in a server.", ephemeral=True)
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        if not is_administrator(interaction):
            await interaction.response.send_message("Only Discord Administrators can use /logs.", ephemeral=True)
            return
        guild = interaction.guild
        changed = False
        if channel is not None:
            set_log_channel(guild.id, channel.id)
            changed = True
        if event is not None:
            set_event(guild.id, event.value, True if enabled is None else bool(enabled))
            changed = True
        elif enabled is not None and channel is None:
            await interaction.response.send_message("Pick an `event:` when using `enabled:`.", ephemeral=True)
            return
        cfg = get_guild_cfg(guild.id)
        view = LogSetupView(actor_id=interaction.user.id, guild_id=guild.id)
        note = "Updated. " if changed else ""
        if not cfg["channel_id"]:
            note += "Pick a log channel with `/logs channel:#logs`."
        await interaction.response.send_message(content=note or None, embed=_status_embed(guild, cfg), view=view, ephemeral=True)


async def on_member_join(member: discord.Member) -> None:
    if getattr(member, "bot", False):
        return
    embed = _embed("Member joined", _user_line(member))
    embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    count = getattr(member.guild, "member_count", None)
    if count:
        embed.add_field(name="Members", value=str(count), inline=True)
    await emit(member.guild, "join", embed)


async def on_member_remove(member: discord.Member) -> None:
    if getattr(member, "bot", False):
        return
    action = getattr(discord.AuditLogAction, "kick", None)
    kicker = await _actor(member.guild, action, getattr(member, "id", None)) if action else None
    if kicker is not None:
        embed = _embed("Member kicked", _user_line(member))
        embed.add_field(name="By", value=_user_line(kicker), inline=True)
        await emit(member.guild, "kick", embed)
        return
    embed = _embed("Member left", _user_line(member))
    count = getattr(member.guild, "member_count", None)
    if count:
        embed.add_field(name="Members", value=str(count), inline=True)
    await emit(member.guild, "leave", embed)


async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    if after.bot:
        return
    guild = after.guild
    if before.nick != after.nick:
        embed = _embed("Nickname changed", _user_line(after))
        embed.add_field(name="Before", value=_clip(before.nick or before.name), inline=True)
        embed.add_field(name="After", value=_clip(after.nick or after.name), inline=True)
        await emit(guild, "nickname", embed)
    before_roles = {r.id for r in getattr(before, "roles", []) if not r.is_default()}
    after_roles = {r.id for r in getattr(after, "roles", []) if not r.is_default()}
    added = after_roles - before_roles
    removed = before_roles - after_roles
    if added or removed:
        embed = _embed("Roles updated", _user_line(after))
        if added:
            embed.add_field(name="Added", value=" ".join(f"<@&{rid}>" for rid in added)[:900], inline=False)
        if removed:
            embed.add_field(name="Removed", value=" ".join(f"<@&{rid}>" for rid in removed)[:900], inline=False)
        action = getattr(discord.AuditLogAction, "member_role_update", None)
        actor = await _actor(guild, action, after.id) if action else None
        if actor:
            embed.add_field(name="By", value=_user_line(actor), inline=True)
        await emit(guild, "roles", embed)
    before_to = getattr(before, "timed_out_until", None)
    after_to = getattr(after, "timed_out_until", None)
    if before_to != after_to:
        if after_to:
            embed = _embed("Timeout given", _user_line(after))
            embed.add_field(name="Until", value=discord.utils.format_dt(after_to, "F"), inline=True)
        else:
            embed = _embed("Timeout removed", _user_line(after))
        await emit(guild, "timeout", embed)
    before_av = str(getattr(getattr(before, "display_avatar", None), "url", "") or "")
    after_av = str(getattr(getattr(after, "display_avatar", None), "url", "") or "")
    if before_av and after_av and before_av != after_av:
        embed = _embed("Avatar changed", _user_line(after))
        embed.set_thumbnail(url=after_av)
        await emit(guild, "avatar", embed)


async def on_user_update(before: discord.User, after: discord.User) -> None:
    if after.bot:
        return
    name_changed = (before.name != after.name) or (getattr(before, "global_name", None) != getattr(after, "global_name", None))
    av_changed = str(before.display_avatar.url) != str(after.display_avatar.url)
    if not name_changed and not av_changed:
        return
    client = after._state._get_client() if hasattr(after, "_state") else None
    guilds = list(getattr(client, "guilds", []) or [])
    for guild in guilds:
        member = guild.get_member(after.id)
        if member is None:
            continue
        if name_changed:
            embed = _embed("Username changed", _user_line(after))
            embed.add_field(name="Before", value=_clip(before.name), inline=True)
            embed.add_field(name="After", value=_clip(after.name), inline=True)
            await emit(guild, "nickname", embed)
        if av_changed:
            embed = _embed("Avatar changed", _user_line(after))
            embed.set_thumbnail(url=str(after.display_avatar.url))
            await emit(guild, "avatar", embed)


async def on_member_ban(guild: discord.Guild, user) -> None:
    action = getattr(discord.AuditLogAction, "ban", None)
    actor = await _actor(guild, action, getattr(user, "id", None)) if action else None
    embed = _embed("Member banned", _user_line(user))
    if actor:
        embed.add_field(name="By", value=_user_line(actor), inline=True)
    await emit(guild, "ban", embed)


async def on_member_unban(guild: discord.Guild, user) -> None:
    action = getattr(discord.AuditLogAction, "unban", None)
    actor = await _actor(guild, action, getattr(user, "id", None)) if action else None
    embed = _embed("Member unbanned", _user_line(user))
    if actor:
        embed.add_field(name="By", value=_user_line(actor), inline=True)
    await emit(guild, "unban", embed)


async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    if member.bot:
        return
    old_ch = getattr(before, "channel", None)
    new_ch = getattr(after, "channel", None)
    old_id = getattr(old_ch, "id", None)
    new_id = getattr(new_ch, "id", None)
    if old_id is None and new_id is not None:
        embed = _embed("Joined voice", _user_line(member))
        embed.add_field(name="Channel", value=new_ch.mention, inline=True)
        await emit(member.guild, "voicejoin", embed)
    elif old_id is not None and new_id is None:
        embed = _embed("Left voice", _user_line(member))
        embed.add_field(name="Channel", value=old_ch.mention, inline=True)
        action = getattr(discord.AuditLogAction, "member_disconnect", None)
        actor = await _actor(member.guild, action, member.id, seconds=6) if action else None
        if actor:
            embed.add_field(name="Disconnected by", value=_user_line(actor), inline=True)
        await emit(member.guild, "voiceleave", embed)
    elif old_id is not None and new_id is not None and old_id != new_id:
        embed = _embed("Moved voice", _user_line(member))
        embed.add_field(name="From", value=old_ch.mention, inline=True)
        embed.add_field(name="To", value=new_ch.mention, inline=True)
        action = getattr(discord.AuditLogAction, "member_move", None)
        actor = await _actor(member.guild, action, member.id, seconds=6) if action else None
        if actor:
            embed.add_field(name="Moved by", value=_user_line(actor), inline=True)
        await emit(member.guild, "voicemove", embed)
    mute_bits = (("self_mute", "Self mute"), ("self_deaf", "Self deaf"), ("mute", "Server mute"), ("deaf", "Server deaf"), ("self_stream", "Stream"), ("self_video", "Camera"))
    changes = []
    for attr, label in mute_bits:
        if getattr(before, attr, None) != getattr(after, attr, None):
            now = bool(getattr(after, attr, False))
            changes.append(f"{label}: {'on' if now else 'off'}")
    if changes and (old_id or new_id):
        embed = _embed("Voice flags", _user_line(member))
        embed.add_field(name="Changed", value="\n".join(changes), inline=False)
        loc = new_ch or old_ch
        if loc:
            embed.add_field(name="Channel", value=loc.mention, inline=True)
        await emit(member.guild, "voicemute", embed)


async def on_message(message: discord.Message) -> None:
    if message.guild is None or getattr(message.author, "bot", False):
        return
    content = message.content or ""
    if not INVITE_RE.search(content):
        return
    found = ", ".join(INVITE_RE.findall(content)[:5])
    embed = _embed("Invite posted", _user_line(message.author))
    embed.add_field(name="Channel", value=getattr(message.channel, "mention", "?"), inline=True)
    embed.add_field(name="Invite", value=_clip(found, 300), inline=False)
    await emit(message.guild, "invite", embed, source_channel_id=getattr(message.channel, "id", None))


async def on_raw_message_delete(payload: discord.RawMessageDeleteEvent) -> None:
    guild_id = getattr(payload, "guild_id", None)
    if not guild_id:
        return
    client = payload._state._get_client() if hasattr(payload, "_state") else None
    guild = client.get_guild(guild_id) if client else None
    if guild is None:
        return
    cached = getattr(payload, "cached_message", None)
    author = getattr(cached, "author", None)
    if author is not None and getattr(author, "id", None) == getattr(getattr(guild, "me", None), "id", None):
        return
    embed = _embed("Message deleted")
    if author is not None:
        embed.add_field(name="Author", value=_user_line(author), inline=False)
    ch = guild.get_channel(payload.channel_id)
    if ch is not None:
        embed.add_field(name="Channel", value=ch.mention, inline=True)
    if cached is not None:
        embed.add_field(name="Content", value=_clip(cached.content), inline=False)
    else:
        embed.add_field(name="Content", value="Not in cache (bot did not see the original).", inline=False)
    action = getattr(discord.AuditLogAction, "message_delete", None)
    actor = await _actor(guild, action, getattr(author, "id", None), seconds=6) if action else None
    if actor:
        embed.add_field(name="Deleted by", value=_user_line(actor), inline=True)
    await emit(guild, "message_delete", embed, source_channel_id=payload.channel_id)


async def on_raw_message_edit(payload: discord.RawMessageUpdateEvent) -> None:
    guild_id = getattr(payload, "guild_id", None)
    if not guild_id:
        return
    data = getattr(payload, "data", {}) or {}
    if "content" not in data:
        return
    client = payload._state._get_client() if hasattr(payload, "_state") else None
    guild = client.get_guild(int(guild_id)) if client else None
    if guild is None:
        return
    cached = getattr(payload, "cached_message", None)
    before = getattr(cached, "content", None) if cached is not None else None
    after = data.get("content")
    if before is not None and before == after:
        return
    author = getattr(cached, "author", None)
    if author is None:
        author_id = data.get("author", {}).get("id") if isinstance(data.get("author"), dict) else None
        if author_id:
            author = guild.get_member(int(author_id))
    if author is not None and getattr(author, "bot", False):
        return
    embed = _embed("Message edited", _user_line(author) if author else None)
    ch = guild.get_channel(int(payload.channel_id))
    if ch is not None:
        embed.add_field(name="Channel", value=ch.mention, inline=True)
        jump = f"https://discord.com/channels/{guild.id}/{payload.channel_id}/{payload.message_id}"
        embed.add_field(name="Jump", value=f"[Open]({jump})", inline=True)
    embed.add_field(name="Before", value=_clip(before if before is not None else "*not cached*"), inline=False)
    embed.add_field(name="After", value=_clip(after), inline=False)
    await emit(guild, "message_edit", embed, source_channel_id=int(payload.channel_id))


async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent) -> None:
    guild_id = getattr(payload, "guild_id", None)
    if not guild_id:
        return
    client = payload._state._get_client() if hasattr(payload, "_state") else None
    guild = client.get_guild(guild_id) if client else None
    if guild is None:
        return
    embed = _embed("Messages purged", f"**{len(payload.message_ids)}** messages removed.")
    ch = guild.get_channel(payload.channel_id)
    if ch is not None:
        embed.add_field(name="Channel", value=ch.mention, inline=True)
    await emit(guild, "message_purge", embed, source_channel_id=payload.channel_id)


def _channel_label(channel) -> str:
    mention = getattr(channel, "mention", None)
    name = getattr(channel, "name", "unknown")
    ctype = type(channel).__name__.replace("Channel", "")
    if mention:
        return f"{mention} ({ctype})"
    return f"**#{name}** ({ctype})"


async def on_guild_channel_create(channel) -> None:
    guild = getattr(channel, "guild", None)
    embed = _embed("Channel created", _channel_label(channel))
    action = getattr(discord.AuditLogAction, "channel_create", None)
    actor = await _actor(guild, action, getattr(channel, "id", None)) if action else None
    if actor:
        embed.add_field(name="By", value=_user_line(actor), inline=True)
    await emit(guild, "channel_create", embed)


async def on_guild_channel_delete(channel) -> None:
    guild = getattr(channel, "guild", None)
    embed = _embed("Channel deleted", f"**#{getattr(channel, 'name', 'unknown')}**")
    action = getattr(discord.AuditLogAction, "channel_delete", None)
    actor = await _actor(guild, action, getattr(channel, "id", None)) if action else None
    if actor:
        embed.add_field(name="By", value=_user_line(actor), inline=True)
    await emit(guild, "channel_delete", embed)


async def on_guild_channel_update(before, after) -> None:
    guild = getattr(after, "guild", None)
    bits = []
    if before.name != after.name:
        bits.append(f"Name: `#{before.name}` → `#{after.name}`")
    if getattr(before, "topic", None) != getattr(after, "topic", None):
        bits.append("Topic changed")
    if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
        bits.append(f"NSFW: {getattr(after, 'nsfw', False)}")
    if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None):
        bits.append(f"Slowmode: {getattr(after, 'slowmode_delay', 0)}s")
    if getattr(before, "bitrate", None) != getattr(after, "bitrate", None):
        bits.append(f"Bitrate: {getattr(after, 'bitrate', '?')}")
    if getattr(before, "user_limit", None) != getattr(after, "user_limit", None):
        bits.append(f"User limit: {getattr(after, 'user_limit', '?')}")
    if not bits:
        return
    embed = _embed("Channel updated", _channel_label(after))
    embed.add_field(name="Changes", value="\n".join(bits)[:900], inline=False)
    await emit(guild, "channel_update", embed)


async def on_guild_role_create(role: discord.Role) -> None:
    embed = _embed("Role created", role.mention)
    action = getattr(discord.AuditLogAction, "role_create", None)
    actor = await _actor(role.guild, action, role.id) if action else None
    if actor:
        embed.add_field(name="By", value=_user_line(actor), inline=True)
    await emit(role.guild, "role_create", embed)


async def on_guild_role_delete(role: discord.Role) -> None:
    embed = _embed("Role deleted", f"**{role.name}**")
    action = getattr(discord.AuditLogAction, "role_delete", None)
    actor = await _actor(role.guild, action, role.id) if action else None
    if actor:
        embed.add_field(name="By", value=_user_line(actor), inline=True)
    await emit(role.guild, "role_delete", embed)


async def on_guild_role_update(before: discord.Role, after: discord.Role) -> None:
    bits = []
    if before.name != after.name:
        bits.append(f"Name: `{before.name}` → `{after.name}`")
    if before.color != after.color:
        bits.append("Color changed")
    if before.hoist != after.hoist:
        bits.append(f"Hoist: {after.hoist}")
    if before.mentionable != after.mentionable:
        bits.append(f"Mentionable: {after.mentionable}")
    if before.permissions != after.permissions:
        bits.append("Permissions changed")
    if not bits:
        return
    embed = _embed("Role updated", after.mention)
    embed.add_field(name="Changes", value="\n".join(bits), inline=False)
    await emit(after.guild, "role_update", embed)


async def on_guild_emojis_update(guild: discord.Guild, before, after) -> None:
    before_ids = {e.id: e for e in before}
    after_ids = {e.id: e for e in after}
    added = [e for i, e in after_ids.items() if i not in before_ids]
    removed = [e for i, e in before_ids.items() if i not in after_ids]
    if not added and not removed:
        return
    lines = [f"Added {e} `{e.name}`" for e in added] + [f"Removed `{e.name}`" for e in removed]
    embed = _embed("Emojis updated", "\n".join(lines)[:900])
    await emit(guild, "emoji", embed)


async def on_guild_update(before: discord.Guild, after: discord.Guild) -> None:
    bits = []
    if before.name != after.name:
        bits.append(f"Name: `{before.name}` → `{after.name}`")
    if before.icon != after.icon:
        bits.append("Icon changed")
    if before.owner_id != after.owner_id:
        bits.append("Owner changed")
    if getattr(before, "afk_channel", None) != getattr(after, "afk_channel", None):
        bits.append("AFK channel changed")
    if getattr(before, "verification_level", None) != getattr(after, "verification_level", None):
        bits.append(f"Verification: {after.verification_level}")
    if not bits:
        return
    embed = _embed("Server updated", "\n".join(bits))
    await emit(after, "server", embed)
