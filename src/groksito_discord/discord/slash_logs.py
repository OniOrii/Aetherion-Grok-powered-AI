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
INVITE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[A-Za-z0-9-]+", re.I)
EVENTS = {
    "join": ("Join", "Member joined"),
    "leave": ("Leave", "Member left"),
    "kick": ("Kick", "Member kicked"),
    "ban": ("Ban", "Member banned"),
    "unban": ("Unban", "Member unbanned"),
    "timeout": ("Timeout", "Timeout given or lifted"),
    "nickname": ("Nickname", "Nick or username"),
    "roles": ("Roles", "Roles added or removed"),
    "avatar": ("Avatar", "Avatar changed"),
    "voicejoin": ("Voice join", "Joined voice"),
    "voicemove": ("Voice move", "Moved voice channels"),
    "voiceleave": ("Voice leave", "Left voice"),
    "voicemute": ("Voice mute", "Mute / deaf / stream"),
    "message_delete": ("Message delete", "Message deleted"),
    "message_edit": ("Message edit", "Message edited"),
    "message_purge": ("Message purge", "Bulk delete"),
    "invite": ("Invite posted", "Discord invite posted"),
    "channel_create": ("Channel create", "Channel created"),
    "channel_update": ("Channel update", "Channel edited"),
    "channel_delete": ("Channel delete", "Channel deleted"),
    "role_create": ("Role create", "Role created"),
    "role_update": ("Role update", "Role edited"),
    "role_delete": ("Role delete", "Role deleted"),
    "emoji": ("Emoji", "Emoji changed"),
    "server": ("Server", "Server settings"),
}
DEFAULT_ON = {"join","leave","kick","ban","unban","timeout","nickname","roles","voicejoin","voicemove","voiceleave","message_delete","message_edit","message_purge","channel_create","channel_update","channel_delete","role_create","role_update","role_delete"}

def _path():
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "server_logs.json"

def _load():
    p = _path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("server log store read failed")
        return {}

def _save(data):
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")

def _empty(all_on=False):
    on = set(EVENTS) if all_on else set(DEFAULT_ON)
    return {k: k in on for k in EVENTS}

def get_guild_cfg(gid):
    raw = _load().get(str(gid)) or {}
    if not isinstance(raw, dict):
        raw = {}
    events = _empty(False)
    saved = raw.get("events") if isinstance(raw.get("events"), dict) else {}
    for k in EVENTS:
        if k in saved:
            events[k] = bool(saved[k])
    try:
        cid = int(raw.get("channel_id") or 0)
    except (TypeError, ValueError):
        cid = 0
    return {"channel_id": cid, "events": events}

def save_guild_cfg(gid, cfg):
    events = _empty(False)
    incoming = cfg.get("events") if isinstance(cfg.get("events"), dict) else {}
    for k in EVENTS:
        if k in incoming:
            events[k] = bool(incoming[k])
    try:
        cid = int(cfg.get("channel_id") or 0)
    except (TypeError, ValueError):
        cid = 0
    row = {"channel_id": cid, "events": events}
    store = _load()
    store[str(gid)] = row
    _save(store)
    return row

def set_log_channel(gid, channel_id):
    cfg = get_guild_cfg(gid)
    first = not cfg["channel_id"]
    cfg["channel_id"] = int(channel_id)
    if first:
        cfg["events"] = _empty(False)
    return save_guild_cfg(gid, cfg)

def set_event(gid, key, enabled):
    cfg = get_guild_cfg(gid)
    if key in EVENTS:
        cfg["events"][key] = bool(enabled)
    return save_guild_cfg(gid, cfg)

def set_all_events(gid, enabled):
    cfg = get_guild_cfg(gid)
    cfg["events"] = {k: bool(enabled) for k in EVENTS}
    return save_guild_cfg(gid, cfg)

def is_administrator(interaction):
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)

def _clip(text, n=900):
    body = (text or "").strip()
    if not body:
        return "*empty*"
    return body if len(body) <= n else body[:n-1] + "…"

def _who(user):
    if user is None:
        return "Unknown"
    mention = getattr(user, "mention", None)
    name = getattr(user, "display_name", None) or getattr(user, "name", "Unknown")
    uid = getattr(user, "id", "?")
    return f"{mention} (`{name}` · `{uid}`)" if mention else f"**{name}** (`{uid}`)"

def _embed(title, desc=None):
    e = discord.Embed(title=title, description=desc or None, color=LOG_COLOR, timestamp=datetime.now(timezone.utc))
    e.set_footer(text="Aetherion logs")
    return e

async def _actor(guild, action, target_id=None, seconds=8.0):
    if guild is None or action is None:
        return None
    try:
        async for entry in guild.audit_logs(limit=8, action=action):
            created = getattr(entry, "created_at", None)
            if created is not None and (datetime.now(timezone.utc) - created).total_seconds() > seconds:
                continue
            tid = getattr(getattr(entry, "target", None), "id", None)
            if target_id and tid and int(tid) != int(target_id):
                continue
            return getattr(entry, "user", None)
    except Exception:
        return None
    return None

_SEND_HINT = {
    "no-channel": "No log channel is set. Run `/logs channel:#logs`.",
    "event-off": "That event is turned off.",
    "missing-channel": "Aetherion cannot see the log channel. Check the channel still exists.",
    "bad-channel": "That log channel cannot receive messages.",
    "no-view": "Aetherion needs View Channel in the log channel.",
    "no-send": "Aetherion needs Send Messages in the log channel.",
    "no-embed": "Aetherion needs Embed Links in the log channel.",
    "send-failed": "Discord rejected the log message. Check channel permissions.",
}

async def emit(guild, key, embed, source_channel_id=None, force=False):
    if guild is None:
        return "bad-event"
    if not force and key not in EVENTS:
        return "bad-event"
    cfg = get_guild_cfg(guild.id)
    if not cfg["channel_id"]:
        return "no-channel"
    if not force and not cfg["events"].get(key):
        return "event-off"
    cid = int(cfg["channel_id"])
    ch = guild.get_channel(cid)
    if ch is None:
        try:
            ch = await guild.fetch_channel(cid)
        except Exception:
            logger.exception("server log channel fetch failed in guild %s", guild.id)
            return "missing-channel"
    if ch is None or not hasattr(ch, "send"):
        return "bad-channel"
    me = getattr(guild, "me", None)
    if me is None:
        state_user = getattr(getattr(guild, "_state", None), "user", None)
        uid = getattr(state_user, "id", None)
        if uid:
            me = guild.get_member(uid)
    perms = ch.permissions_for(me) if me is not None else None
    if perms is not None:
        if not getattr(perms, "view_channel", True):
            return "no-view"
        if not perms.send_messages:
            return "no-send"
        if not getattr(perms, "embed_links", True):
            return "no-embed"
    try:
        await ch.send(embed=embed)
        return "ok"
    except Exception:
        logger.exception("server log send failed in guild %s", guild.id)
        return "send-failed"

async def emit_test(guild):
    e = _embed("Logs are live", "Aetherion can post here. Joins, leaves, deletes, and the other enabled events will show up in this channel.")
    return await emit(guild, "join", e, force=True)

def _status_embed(guild, cfg):
    cid = cfg.get("channel_id") or 0
    e = _embed("Server logs", f"Log channel: {('<#'+str(cid)+'>') if cid else '*not set*'}")
    on = [EVENTS[k][0] for k,v in cfg["events"].items() if v]
    off = [EVENTS[k][0] for k,v in cfg["events"].items() if not v]
    e.add_field(name="On", value=", ".join(on) or "*none*", inline=False)
    e.add_field(name="Off", value=", ".join(off) or "*none*", inline=False)
    e.add_field(name="How to edit", value="`/logs channel:#logs`\n`/logs event:leave enabled:True`\nOr use the menus. Tap **Send test** if the channel looks empty.", inline=False)
    return e

class LogSetupView(discord.ui.View):
    def __init__(self, actor_id, guild_id):
        super().__init__(timeout=180)
        self.actor_id = actor_id
        self.guild_id = guild_id
        self._rebuild()
    def _rebuild(self):
        self.clear_items()
        cfg = get_guild_cfg(self.guild_id)
        sel = discord.ui.Select(placeholder="Events that stay on", min_values=0, max_values=len(EVENTS), options=[discord.SelectOption(label=EVENTS[k][0], value=k, description=EVENTS[k][1][:100], default=bool(cfg["events"].get(k))) for k in EVENTS])
        sel.callback = self._on_select
        self.add_item(sel)
        b1 = discord.ui.Button(label="Enable all", style=discord.ButtonStyle.success)
        b1.callback = self._all_on
        b2 = discord.ui.Button(label="Disable all", style=discord.ButtonStyle.secondary)
        b2.callback = self._all_off
        b3 = discord.ui.Button(label="Send test", style=discord.ButtonStyle.primary)
        b3.callback = self._test
        self.add_item(b1); self.add_item(b2); self.add_item(b3)
    async def interaction_check(self, interaction):
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message("This log menu is not yours. Run `/logs`.", ephemeral=True)
            return False
        return True
    async def _refresh(self, interaction):
        self._rebuild()
        await interaction.response.edit_message(embed=_status_embed(interaction.guild, get_guild_cfg(self.guild_id)), view=self)
    async def _on_select(self, interaction):
        selected = set(interaction.data.get("values") or [])
        cfg = get_guild_cfg(self.guild_id)
        cfg["events"] = {k: k in selected for k in EVENTS}
        save_guild_cfg(self.guild_id, cfg)
        await self._refresh(interaction)
    async def _all_on(self, interaction):
        set_all_events(self.guild_id, True); await self._refresh(interaction)
    async def _all_off(self, interaction):
        set_all_events(self.guild_id, False); await self._refresh(interaction)
    async def _test(self, interaction):
        result = await emit_test(interaction.guild)
        if result == "ok":
            await interaction.response.send_message("Posted a test log in the log channel.", ephemeral=True)
        else:
            await interaction.response.send_message(_SEND_HINT.get(result, "Could not post a test log."), ephemeral=True)

def register_logs(tree, is_guild_allowed):
    choices = [discord.app_commands.Choice(name=EVENTS[k][0], value=k) for k in EVENTS]
    @tree.command(name="logs", description="Set the server log channel and pick which events Aetherion posts.")
    @discord.app_commands.describe(channel="Channel that receives log embeds", event="One event to turn on or off", enabled="On or off for that event")
    @discord.app_commands.choices(event=choices)
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def logs_slash(interaction, channel: discord.TextChannel | None = None, event: discord.app_commands.Choice[str] | None = None, enabled: bool | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("Use /logs in a server.", ephemeral=True); return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True); return
        if not is_administrator(interaction):
            await interaction.response.send_message("Only Discord Administrators can use /logs.", ephemeral=True); return
        changed = False
        if channel is not None:
            set_log_channel(interaction.guild.id, channel.id); changed = True
        if event is not None:
            set_event(interaction.guild.id, event.value, True if enabled is None else bool(enabled)); changed = True
        elif enabled is not None and channel is None:
            await interaction.response.send_message("Pick an `event:` when using `enabled:`.", ephemeral=True); return
        cfg = get_guild_cfg(interaction.guild.id)
        note = "Updated. " if changed else ""
        if not cfg["channel_id"]:
            note += "Pick a log channel with `/logs channel:#logs`."
        elif channel is not None:
            probe = await emit_test(interaction.guild)
            if probe == "ok":
                note += "Posted a test log in that channel."
            else:
                note += _SEND_HINT.get(probe, "Could not post in that channel.")
        await interaction.response.send_message(content=note or None, embed=_status_embed(interaction.guild, cfg), view=LogSetupView(interaction.user.id, interaction.guild.id), ephemeral=True)
