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

async def emit(guild, key, embed, source_channel_id=None):
    if guild is None or key not in EVENTS:
        return
    cfg = get_guild_cfg(guild.id)
    if not cfg["channel_id"] or not cfg["events"].get(key):
        return
    if source_channel_id and int(source_channel_id) == int(cfg["channel_id"]) and key in {"message_delete","message_edit","message_purge","invite"}:
        return
    ch = guild.get_channel(int(cfg["channel_id"]))
    if ch is None or not hasattr(ch, "send"):
        return
    me = getattr(guild, "me", None)
    perms = ch.permissions_for(me) if me is not None else None
    if perms is not None and not perms.send_messages:
        return
    try:
        await ch.send(embed=embed)
    except Exception:
        logger.exception("server log send failed in guild %s", guild.id)

def _status_embed(guild, cfg):
    cid = cfg.get("channel_id") or 0
    e = _embed("Server logs", f"Log channel: {('<#'+str(cid)+'>') if cid else '*not set*'}")
    on = [EVENTS[k][0] for k,v in cfg["events"].items() if v]
    off = [EVENTS[k][0] for k,v in cfg["events"].items() if not v]
    e.add_field(name="On", value=", ".join(on) or "*none*", inline=False)
    e.add_field(name="Off", value=", ".join(off) or "*none*", inline=False)
    e.add_field(name="How to edit", value="`/logs channel:#logs`\n`/logs event:leave enabled:True`\nOr use the menus.", inline=False)
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
        self.add_item(b1); self.add_item(b2)
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
        await interaction.response.send_message(content=note or None, embed=_status_embed(interaction.guild, cfg), view=LogSetupView(interaction.user.id, interaction.guild.id), ephemeral=True)

async def on_member_join(member):
    if member.bot: return
    e = _embed("Member joined", _who(member))
    e.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    if member.guild.member_count:
        e.add_field(name="Members", value=str(member.guild.member_count), inline=True)
    await emit(member.guild, "join", e)

async def on_member_remove(member):
    if getattr(member, "bot", False): return
    kicker = await _actor(member.guild, getattr(discord.AuditLogAction, "kick", None), getattr(member, "id", None))
    if kicker:
        e = _embed("Member kicked", _who(member)); e.add_field(name="By", value=_who(kicker), inline=True)
        await emit(member.guild, "kick", e); return
    e = _embed("Member left", _who(member))
    if getattr(member.guild, "member_count", None):
        e.add_field(name="Members", value=str(member.guild.member_count), inline=True)
    await emit(member.guild, "leave", e)

async def on_member_update(before, after):
    if after.bot: return
    g = after.guild
    if before.nick != after.nick:
        e = _embed("Nickname changed", _who(after))
        e.add_field(name="Before", value=_clip(before.nick or before.name), inline=True)
        e.add_field(name="After", value=_clip(after.nick or after.name), inline=True)
        await emit(g, "nickname", e)
    old_r = {r.id for r in before.roles if not r.is_default()}
    new_r = {r.id for r in after.roles if not r.is_default()}
    added, removed = new_r - old_r, old_r - new_r
    if added or removed:
        e = _embed("Roles updated", _who(after))
        if added: e.add_field(name="Added", value=" ".join(f"<@&{i}>" for i in added)[:900], inline=False)
        if removed: e.add_field(name="Removed", value=" ".join(f"<@&{i}>" for i in removed)[:900], inline=False)
        actor = await _actor(g, getattr(discord.AuditLogAction, "member_role_update", None), after.id)
        if actor: e.add_field(name="By", value=_who(actor), inline=True)
        await emit(g, "roles", e)
    if getattr(before, "timed_out_until", None) != getattr(after, "timed_out_until", None):
        if after.timed_out_until:
            e = _embed("Timeout given", _who(after)); e.add_field(name="Until", value=discord.utils.format_dt(after.timed_out_until, "F"), inline=True)
        else:
            e = _embed("Timeout removed", _who(after))
        await emit(g, "timeout", e)
    bav = str(getattr(getattr(before, "display_avatar", None), "url", "") or "")
    aav = str(getattr(getattr(after, "display_avatar", None), "url", "") or "")
    if bav and aav and bav != aav:
        e = _embed("Avatar changed", _who(after)); e.set_thumbnail(url=aav)
        await emit(g, "avatar", e)

async def on_user_update(before, after):
    if after.bot: return
    name_ch = before.name != after.name or getattr(before, "global_name", None) != getattr(after, "global_name", None)
    av_ch = str(before.display_avatar.url) != str(after.display_avatar.url)
    if not name_ch and not av_ch: return
    client = after._state._get_client() if hasattr(after, "_state") else None
    for guild in list(getattr(client, "guilds", []) or []):
        if guild.get_member(after.id) is None: continue
        if name_ch:
            e = _embed("Username changed", _who(after))
            e.add_field(name="Before", value=_clip(before.name), inline=True)
            e.add_field(name="After", value=_clip(after.name), inline=True)
            await emit(guild, "nickname", e)
        if av_ch:
            e = _embed("Avatar changed", _who(after)); e.set_thumbnail(url=str(after.display_avatar.url))
            await emit(guild, "avatar", e)

async def on_member_ban(guild, user):
    e = _embed("Member banned", _who(user))
    actor = await _actor(guild, getattr(discord.AuditLogAction, "ban", None), getattr(user, "id", None))
    if actor: e.add_field(name="By", value=_who(actor), inline=True)
    await emit(guild, "ban", e)

async def on_member_unban(guild, user):
    e = _embed("Member unbanned", _who(user))
    actor = await _actor(guild, getattr(discord.AuditLogAction, "unban", None), getattr(user, "id", None))
    if actor: e.add_field(name="By", value=_who(actor), inline=True)
    await emit(guild, "unban", e)

async def on_voice_state_update(member, before, after):
    if member.bot: return
    old, new = before.channel, after.channel
    oid, nid = getattr(old, "id", None), getattr(new, "id", None)
    if oid is None and nid is not None:
        e = _embed("Joined voice", _who(member)); e.add_field(name="Channel", value=new.mention, inline=True)
        await emit(member.guild, "voicejoin", e)
    elif oid is not None and nid is None:
        e = _embed("Left voice", _who(member)); e.add_field(name="Channel", value=old.mention, inline=True)
        actor = await _actor(member.guild, getattr(discord.AuditLogAction, "member_disconnect", None), member.id, 6)
        if actor: e.add_field(name="Disconnected by", value=_who(actor), inline=True)
        await emit(member.guild, "voiceleave", e)
    elif oid and nid and oid != nid:
        e = _embed("Moved voice", _who(member))
        e.add_field(name="From", value=old.mention, inline=True); e.add_field(name="To", value=new.mention, inline=True)
        actor = await _actor(member.guild, getattr(discord.AuditLogAction, "member_move", None), member.id, 6)
        if actor: e.add_field(name="Moved by", value=_who(actor), inline=True)
        await emit(member.guild, "voicemove", e)
    bits = []
    for attr, label in (("self_mute","Self mute"),("self_deaf","Self deaf"),("mute","Server mute"),("deaf","Server deaf"),("self_stream","Stream"),("self_video","Camera")):
        if getattr(before, attr, None) != getattr(after, attr, None):
            bits.append(f"{label}: {'on' if getattr(after, attr, False) else 'off'}")
    if bits and (oid or nid):
        e = _embed("Voice flags", _who(member)); e.add_field(name="Changed", value="\n".join(bits), inline=False)
        loc = new or old
        if loc: e.add_field(name="Channel", value=loc.mention, inline=True)
        await emit(member.guild, "voicemute", e)

async def on_message(message):
    if message.guild is None or message.author.bot: return
    if not INVITE_RE.search(message.content or ""): return
    e = _embed("Invite posted", _who(message.author))
    e.add_field(name="Channel", value=getattr(message.channel, "mention", "?"), inline=True)
    e.add_field(name="Invite", value=_clip(", ".join(INVITE_RE.findall(message.content)[:5]), 300), inline=False)
    await emit(message.guild, "invite", e, getattr(message.channel, "id", None))

async def on_raw_message_delete(payload):
    if not payload.guild_id: return
    client = payload._state._get_client() if hasattr(payload, "_state") else None
    guild = client.get_guild(payload.guild_id) if client else None
    if guild is None: return
    cached = payload.cached_message
    author = getattr(cached, "author", None)
    if author is not None and guild.me and author.id == guild.me.id: return
    e = _embed("Message deleted")
    if author: e.add_field(name="Author", value=_who(author), inline=False)
    ch = guild.get_channel(payload.channel_id)
    if ch: e.add_field(name="Channel", value=ch.mention, inline=True)
    e.add_field(name="Content", value=_clip(cached.content) if cached else "Not in cache (bot did not see the original).", inline=False)
    actor = await _actor(guild, getattr(discord.AuditLogAction, "message_delete", None), getattr(author, "id", None), 6)
    if actor: e.add_field(name="Deleted by", value=_who(actor), inline=True)
    await emit(guild, "message_delete", e, payload.channel_id)

async def on_raw_message_edit(payload):
    if not payload.guild_id: return
    data = payload.data or {}
    if "content" not in data: return
    client = payload._state._get_client() if hasattr(payload, "_state") else None
    guild = client.get_guild(int(payload.guild_id)) if client else None
    if guild is None: return
    cached = payload.cached_message
    before = getattr(cached, "content", None) if cached else None
    after = data.get("content")
    if before is not None and before == after: return
    author = getattr(cached, "author", None)
    if author is None and isinstance(data.get("author"), dict) and data["author"].get("id"):
        author = guild.get_member(int(data["author"]["id"]))
    if author is not None and author.bot: return
    e = _embed("Message edited", _who(author) if author else None)
    ch = guild.get_channel(int(payload.channel_id))
    if ch:
        e.add_field(name="Channel", value=ch.mention, inline=True)
        e.add_field(name="Jump", value=f"[Open](https://discord.com/channels/{guild.id}/{payload.channel_id}/{payload.message_id})", inline=True)
    e.add_field(name="Before", value=_clip(before if before is not None else "*not cached*"), inline=False)
    e.add_field(name="After", value=_clip(after), inline=False)
    await emit(guild, "message_edit", e, int(payload.channel_id))

async def on_raw_bulk_message_delete(payload):
    if not payload.guild_id: return
    client = payload._state._get_client() if hasattr(payload, "_state") else None
    guild = client.get_guild(payload.guild_id) if client else None
    if guild is None: return
    e = _embed("Messages purged", f"**{len(payload.message_ids)}** messages removed.")
    ch = guild.get_channel(payload.channel_id)
    if ch: e.add_field(name="Channel", value=ch.mention, inline=True)
    await emit(guild, "message_purge", e, payload.channel_id)

def _ch_label(ch):
    return f"{ch.mention} ({type(ch).__name__.replace('Channel','')})" if getattr(ch, "mention", None) else f"**#{getattr(ch,'name','unknown')}**"

async def on_guild_channel_create(channel):
    e = _embed("Channel created", _ch_label(channel))
    actor = await _actor(channel.guild, getattr(discord.AuditLogAction, "channel_create", None), channel.id)
    if actor: e.add_field(name="By", value=_who(actor), inline=True)
    await emit(channel.guild, "channel_create", e)

async def on_guild_channel_delete(channel):
    e = _embed("Channel deleted", f"**#{getattr(channel,'name','unknown')}**")
    actor = await _actor(channel.guild, getattr(discord.AuditLogAction, "channel_delete", None), channel.id)
    if actor: e.add_field(name="By", value=_who(actor), inline=True)
    await emit(channel.guild, "channel_delete", e)

async def on_guild_channel_update(before, after):
    bits = []
    if before.name != after.name: bits.append(f"Name: `#{before.name}` → `#{after.name}`")
    if getattr(before, "topic", None) != getattr(after, "topic", None): bits.append("Topic changed")
    if getattr(before, "nsfw", None) != getattr(after, "nsfw", None): bits.append(f"NSFW: {getattr(after, 'nsfw', False)}")
    if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None): bits.append(f"Slowmode: {getattr(after, 'slowmode_delay', 0)}s")
    if not bits: return
    e = _embed("Channel updated", _ch_label(after)); e.add_field(name="Changes", value="\n".join(bits)[:900], inline=False)
    await emit(after.guild, "channel_update", e)

async def on_guild_role_create(role):
    e = _embed("Role created", role.mention)
    actor = await _actor(role.guild, getattr(discord.AuditLogAction, "role_create", None), role.id)
    if actor: e.add_field(name="By", value=_who(actor), inline=True)
    await emit(role.guild, "role_create", e)

async def on_guild_role_delete(role):
    e = _embed("Role deleted", f"**{role.name}**")
    actor = await _actor(role.guild, getattr(discord.AuditLogAction, "role_delete", None), role.id)
    if actor: e.add_field(name="By", value=_who(actor), inline=True)
    await emit(role.guild, "role_delete", e)

async def on_guild_role_update(before, after):
    bits = []
    if before.name != after.name: bits.append(f"Name: `{before.name}` → `{after.name}`")
    if before.color != after.color: bits.append("Color changed")
    if before.permissions != after.permissions: bits.append("Permissions changed")
    if not bits: return
    e = _embed("Role updated", after.mention); e.add_field(name="Changes", value="\n".join(bits), inline=False)
    await emit(after.guild, "role_update", e)

async def on_guild_emojis_update(guild, before, after):
    b, a = {e.id: e for e in before}, {e.id: e for e in after}
    added = [e for i,e in a.items() if i not in b]
    removed = [e for i,e in b.items() if i not in a]
    if not added and not removed: return
    lines = [f"Added {e} `{e.name}`" for e in added] + [f"Removed `{e.name}`" for e in removed]
    await emit(guild, "emoji", _embed("Emojis updated", "\n".join(lines)[:900]))

async def on_guild_update(before, after):
    bits = []
    if before.name != after.name: bits.append(f"Name: `{before.name}` → `{after.name}`")
    if before.icon != after.icon: bits.append("Icon changed")
    if before.owner_id != after.owner_id: bits.append("Owner changed")
    if not bits: return
    await emit(after, "server", _embed("Server updated", "\n".join(bits)))

def attach_listeners(client):
    for name, fn in (("on_member_join", on_member_join),("on_member_update", on_member_update),("on_member_remove", on_member_remove),("on_user_update", on_user_update),("on_member_ban", on_member_ban),("on_member_unban", on_member_unban),("on_voice_state_update", on_voice_state_update),("on_message", on_message),("on_raw_message_delete", on_raw_message_delete),("on_raw_message_edit", on_raw_message_edit),("on_raw_bulk_message_delete", on_raw_bulk_message_delete),("on_guild_channel_create", on_guild_channel_create),("on_guild_channel_delete", on_guild_channel_delete),("on_guild_channel_update", on_guild_channel_update),("on_guild_role_create", on_guild_role_create),("on_guild_role_delete", on_guild_role_delete),("on_guild_role_update", on_guild_role_update),("on_guild_emojis_update", on_guild_emojis_update),("on_guild_update", on_guild_update)):
        client.add_listener(fn, name)
