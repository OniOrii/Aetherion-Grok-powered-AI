"""Persistent exclusive reaction roles (Carl-style color panels)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import discord

from ..config import settings

logger = logging.getLogger("aetherion.reaction_roles")

_CUSTOM_EMOJI_RE = re.compile(r"^<(a?):([A-Za-z0-9_]+):(\d+)>$" )
_ID_EMOJI_RE = re.compile(r"^([A-Za-z0-9_]+):(\d+)$")
_PAIR_RE = re.compile(r"(?P<left><(?:a)?:[A-Za-z0-9_]+:\d+>|\S+)\s+<@&(?P<rid>\d+)>")
RR_EMBED_TITLE = "Aetherion reaction roles"


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "reaction_roles.json"


def load_store() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("reaction role store read failed")
        return {}


def save_store(data: dict) -> None:
    _store_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def emoji_key_from_partial(emoji) -> str:
    eid = getattr(emoji, "id", None)
    name = getattr(emoji, "name", None) or str(emoji)
    if eid:
        return f"{name}:{eid}"
    return str(emoji)


def parse_emoji_input(raw: str) -> tuple[str, discord.PartialEmoji | str] | None:
    text = (raw or "").strip()
    if not text:
        return None
    match = _CUSTOM_EMOJI_RE.match(text)
    if match:
        name, eid = match.group(2), int(match.group(3))
        return f"{name}:{eid}", discord.PartialEmoji(name=name, id=eid, animated=match.group(1) == "a")
    match = _ID_EMOJI_RE.match(text)
    if match:
        name, eid = match.group(1), int(match.group(2))
        return f"{name}:{eid}", discord.PartialEmoji(name=name, id=eid)
    return text, text


def parse_panel_text(content: str, extra_blobs: list[str] | None = None) -> dict[str, int]:
    """Read emoji to role id pairs from a panel message body or stamped embed."""
    mapping: dict[str, int] = {}
    blobs = [content or ""]
    if extra_blobs:
        blobs.extend(extra_blobs)
    for blob in blobs:
        for match in _PAIR_RE.finditer(blob or ""):
            parsed = parse_emoji_input(match.group("left"))
            if parsed is None:
                continue
            mapping[parsed[0]] = int(match.group("rid"))
        for line in (blob or "").splitlines():
            line = line.strip()
            if "=" not in line or "<@&" in line:
                continue
            left, _, right = line.partition("=")
            parsed = parse_emoji_input(left.strip())
            if parsed is None:
                continue
            try:
                mapping[parsed[0]] = int(right.strip())
            except ValueError:
                continue
    return mapping


def get_panel(guild_id: int, message_id: int) -> dict | None:
    store = load_store()
    guild = store.get(str(guild_id)) or {}
    panel = guild.get(str(message_id))
    return panel if isinstance(panel, dict) else None


def upsert_panel(guild_id: int, message_id: int, channel_id: int, unique: bool = True) -> dict:
    store = load_store()
    guild = store.setdefault(str(guild_id), {})
    panel = guild.get(str(message_id))
    if not isinstance(panel, dict):
        panel = {"channel_id": int(channel_id), "unique": bool(unique), "map": {}}
    else:
        panel["channel_id"] = int(channel_id)
        panel["unique"] = bool(unique) if "unique" not in panel else bool(panel.get("unique", True))
        panel.setdefault("map", {})
    guild[str(message_id)] = panel
    save_store(store)
    return panel


def set_mapping(guild_id: int, message_id: int, channel_id: int, emoji_key: str, role_id: int) -> dict:
    store = load_store()
    guild = store.setdefault(str(guild_id), {})
    panel = guild.get(str(message_id))
    if not isinstance(panel, dict):
        panel = {"channel_id": int(channel_id), "unique": True, "map": {}}
    panel["channel_id"] = int(channel_id)
    panel.setdefault("unique", True)
    mapping = panel.setdefault("map", {})
    mapping[emoji_key] = int(role_id)
    guild[str(message_id)] = panel
    save_store(store)
    return panel


def restore_panel(guild_id: int, message_id: int, channel_id: int, mapping: dict[str, int], unique: bool = True) -> dict | None:
    if not mapping:
        return None
    upsert_panel(guild_id, message_id, channel_id, unique=unique)
    panel = None
    for key, role_id in mapping.items():
        panel = set_mapping(guild_id, message_id, channel_id, key, int(role_id))
    return panel


def remove_mapping(guild_id: int, message_id: int, emoji_key: str) -> bool:
    store = load_store()
    guild = store.get(str(guild_id)) or {}
    panel = guild.get(str(message_id))
    if not isinstance(panel, dict):
        return False
    mapping = panel.get("map") or {}
    if emoji_key not in mapping:
        return False
    mapping.pop(emoji_key, None)
    panel["map"] = mapping
    if mapping:
        guild[str(message_id)] = panel
    else:
        guild.pop(str(message_id), None)
    if guild:
        store[str(guild_id)] = guild
    else:
        store.pop(str(guild_id), None)
    save_store(store)
    return True


def latest_panel_id(guild_id: int) -> int | None:
    store = load_store()
    guild = store.get(str(guild_id)) or {}
    if not guild:
        return None
    try:
        return max(int(mid) for mid in guild.keys())
    except (TypeError, ValueError):
        return None


def list_panels(guild_id: int) -> dict:
    store = load_store()
    guild = store.get(str(guild_id)) or {}
    return guild if isinstance(guild, dict) else {}


def lookup_role_id(guild_id: int, message_id: int, emoji_key: str) -> int | None:
    panel = get_panel(guild_id, message_id)
    if not panel:
        return None
    raw = (panel.get("map") or {}).get(emoji_key)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def sibling_role_ids(guild_id: int, message_id: int, except_emoji: str | None = None) -> list[int]:
    panel = get_panel(guild_id, message_id)
    if not panel:
        return []
    out = []
    for key, role_id in (panel.get("map") or {}).items():
        if except_emoji is not None and key == except_emoji:
            continue
        try:
            out.append(int(role_id))
        except (TypeError, ValueError):
            continue
    return out


def panel_is_unique(guild_id: int, message_id: int) -> bool:
    panel = get_panel(guild_id, message_id)
    if not panel:
        return True
    return bool(panel.get("unique", True))


def panel_embed(panel: dict) -> discord.Embed:
    mapping = (panel or {}).get("map") or {}
    lines = [f"{key} <@&{rid}>" for key, rid in mapping.items()]
    embed = discord.Embed(
        title=RR_EMBED_TITLE,
        description="\n".join(lines)[:4000] or "No roles bound yet.",
        color=0x2B2D31,
    )
    return embed


async def stamp_panel_embed(message: discord.Message, guild_id: int, message_id: int) -> None:
    panel = get_panel(guild_id, message_id)
    if panel is None:
        return
    kept = [embed for embed in (message.embeds or []) if (embed.title or "") != RR_EMBED_TITLE]
    kept.append(panel_embed(panel))
    try:
        await message.edit(embeds=kept[:10])
    except discord.HTTPException:
        logger.exception("could not stamp reaction role embed on %s", message_id)


async def _fetch_payload_message(client, payload: discord.RawReactionActionEvent):
    if client is None or payload.channel_id is None:
        return None
    channel = client.get_channel(payload.channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(payload.channel_id)
        except discord.HTTPException:
            return None
    if channel is None or not hasattr(channel, "fetch_message"):
        return None
    try:
        return await channel.fetch_message(payload.message_id)
    except discord.HTTPException:
        return None


async def ensure_panel_from_message(client, payload: discord.RawReactionActionEvent) -> None:
    """If the on-disk store was wiped, rebuild it from the Discord panel message."""
    if payload.guild_id is None:
        return
    existing = get_panel(payload.guild_id, payload.message_id)
    if existing and (existing.get("map") or {}):
        return
    message = await _fetch_payload_message(client, payload)
    if message is None:
        return
    blobs = [embed.description or "" for embed in (message.embeds or [])]
    mapping = parse_panel_text(message.content or "", blobs)
    if not mapping:
        return
    restore_panel(payload.guild_id, payload.message_id, payload.channel_id, mapping)
    logger.info("restored reaction role panel %s from Discord message", payload.message_id)


async def _guild_and_member(client, payload: discord.RawReactionActionEvent):
    if payload.guild_id is None or payload.user_id is None:
        return None, None
    guild = client.get_guild(payload.guild_id) if client is not None else None
    if guild is None and payload.member is not None:
        guild = payload.member.guild
    if guild is None:
        return None, None
    if payload.member is not None:
        return guild, payload.member
    member = guild.get_member(payload.user_id)
    if member is not None:
        return guild, member
    try:
        return guild, await guild.fetch_member(payload.user_id)
    except discord.HTTPException:
        return guild, None


def _can_assign(guild: discord.Guild, role: discord.Role) -> str | None:
    me = guild.me
    if me is None:
        return "I am not in this server."
    if not me.guild_permissions.manage_roles:
        return "I need **Manage Roles**."
    if role.is_default() or role.managed:
        return f"I cannot assign {role.mention}."
    if me.top_role <= role:
        return f"Move my role above **{role.name}** so I can assign it."
    return None


async def _clear_other_reactions(
    channel,
    message_id: int,
    member: discord.Member,
    keep_emoji_key: str,
    panel: dict,
) -> None:
    try:
        message = await channel.fetch_message(message_id)
    except discord.HTTPException:
        return
    for key in (panel.get("map") or {}).keys():
        if key == keep_emoji_key:
            continue
        emoji: discord.PartialEmoji | str
        if ":" in key:
            name, _, eid = key.rpartition(":")
            try:
                emoji = discord.PartialEmoji(name=name, id=int(eid))
            except ValueError:
                continue
        else:
            emoji = key
        try:
            await message.remove_reaction(emoji, member)
        except discord.HTTPException:
            continue


async def handle_reaction_add(client, payload: discord.RawReactionActionEvent) -> None:
    if payload.guild_id is None or payload.user_id is None:
        return
    await ensure_panel_from_message(client, payload)
    emoji_key = emoji_key_from_partial(payload.emoji)
    role_id = lookup_role_id(payload.guild_id, payload.message_id, emoji_key)
    if role_id is None:
        return
    guild, member = await _guild_and_member(client, payload)
    if member is None or member.bot or guild is None:
        return
    role = guild.get_role(role_id)
    if role is None:
        logger.warning("reaction role missing role %s in guild %s", role_id, guild.id)
        return
    problem = _can_assign(guild, role)
    if problem:
        logger.warning("reaction role assign blocked: %s", problem)
        return
    if panel_is_unique(guild.id, payload.message_id):
        extras = [
            guild.get_role(rid)
            for rid in sibling_role_ids(guild.id, payload.message_id, except_emoji=emoji_key)
        ]
        extras = [r for r in extras if r is not None and r in member.roles]
        if extras:
            try:
                await member.remove_roles(*extras, reason="Aetherion exclusive color role")
            except discord.HTTPException:
                logger.exception("could not remove old color roles")
        panel = get_panel(guild.id, payload.message_id) or {}
        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(payload.channel_id)
            except discord.HTTPException:
                channel = None
        if channel is not None:
            await _clear_other_reactions(channel, payload.message_id, member, emoji_key, panel)
    if role not in member.roles:
        try:
            await member.add_roles(role, reason="Aetherion reaction role")
        except discord.HTTPException:
            logger.exception("could not add reaction role")


async def handle_reaction_remove(client, payload: discord.RawReactionActionEvent) -> None:
    if payload.guild_id is None or payload.user_id is None:
        return
    await ensure_panel_from_message(client, payload)
    emoji_key = emoji_key_from_partial(payload.emoji)
    role_id = lookup_role_id(payload.guild_id, payload.message_id, emoji_key)
    if role_id is None:
        return
    guild, member = await _guild_and_member(client, payload)
    if guild is None or member is None or member.bot:
        return
    if guild.me is not None and payload.user_id == guild.me.id:
        return
    role = guild.get_role(role_id)
    if role is None or role not in member.roles:
        return
    try:
        await member.remove_roles(role, reason="Aetherion reaction role removed")
    except discord.HTTPException:
        logger.exception("could not remove reaction role")
