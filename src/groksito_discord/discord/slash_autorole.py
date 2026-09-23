"""Administrator /autorole — give a role as soon as someone joins."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import discord

from ..config import settings
from .brand import GOLD, stamp

logger = logging.getLogger("aetherion.slash_autorole")


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "autoroles.json"


def _load_store() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("autorole store read failed")
        return {}


def _save_store(data: dict) -> None:
    _store_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_guild_autorole_id(guild_id: int) -> int:
    store = _load_store()
    raw = store.get(str(guild_id)) or store.get(guild_id)
    if isinstance(raw, dict):
        raw = raw.get("role_id")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def set_guild_autorole(guild_id: int, role_id: int) -> None:
    store = _load_store()
    store[str(guild_id)] = int(role_id)
    _save_store(store)


def clear_guild_autorole(guild_id: int) -> None:
    store = _load_store()
    store.pop(str(guild_id), None)
    store.pop(guild_id, None)
    _save_store(store)


def is_administrator(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


def _bot_member(guild: discord.Guild) -> discord.Member | None:
    me = getattr(guild, "me", None)
    if me is not None:
        return me
    state_user = getattr(getattr(guild, "_state", None), "user", None)
    uid = getattr(state_user, "id", None)
    if uid:
        return guild.get_member(uid)
    return None


def explain_role_block(guild: discord.Guild, role: discord.Role) -> str | None:
    if role.is_default():
        return "@everyone is already given. Pick a real role."
    if role.managed:
        return f"{role.mention} is managed by an integration. Discord will not let Aetherion assign it."
    if role.permissions.administrator:
        return f"{role.mention} has Administrator. Auto-role will not hand that out."
    me = _bot_member(guild)
    if me is None:
        return "Aetherion is not in this server cache yet. Try again in a moment."
    if not me.guild_permissions.manage_roles:
        return "Aetherion needs **Manage Roles** to assign a join role."
    if role >= me.top_role:
        return (
            f"Move Aetherion's role **above** {role.mention} in Server Settings → Roles, "
            "then run `/autorole` again."
        )
    return None


async def assign_join_role(member: discord.Member) -> None:
    if member is None or getattr(member, "bot", False):
        return
    guild = member.guild
    if guild is None:
        return
    if getattr(member, "pending", False):
        return
    role_id = get_guild_autorole_id(guild.id)
    if not role_id:
        return
    role = guild.get_role(role_id)
    if role is None:
        logger.warning("autorole: saved role %s missing in guild %s", role_id, guild.id)
        return
    if role in getattr(member, "roles", []):
        return
    blocked = explain_role_block(guild, role)
    if blocked:
        logger.warning("autorole skipped in guild %s: %s", guild.id, blocked)
        return
    try:
        await member.add_roles(role, reason="Aetherion auto-role on join")
    except discord.Forbidden:
        logger.warning("autorole forbidden for %s in guild %s", member.id, guild.id)
    except Exception:
        logger.exception("autorole assign failed for %s in guild %s", member.id, guild.id)


async def on_member_join(member: discord.Member) -> None:
    await assign_join_role(member)


async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    if getattr(before, "pending", False) and not getattr(after, "pending", False):
        await assign_join_role(after)


def _status_embed(guild: discord.Guild) -> discord.Embed:
    role_id = get_guild_autorole_id(guild.id)
    role = guild.get_role(role_id) if role_id else None
    if role is not None:
        body = f"New members get {role.mention} as soon as they join."
    elif role_id:
        body = (
            f"Saved role `{role_id}` is gone. Pick a new one with `/autorole role:@Name`."
        )
    else:
        body = "No join role is set. `/autorole role:@Member` turns it on."
    embed = discord.Embed(title="\u2726 Auto-role", description=body, color=GOLD)
    return stamp(embed, extra="Administrators \u00b7 /autorole off:True clears it")


def register_autorole(tree, is_guild_allowed) -> None:
    @tree.command(
        name="autorole",
        description="Give a role to people as soon as they join. Administrators only.",
    )
    @discord.app_commands.describe(
        role="Role new members receive on join",
        off="Turn auto-role off for this server",
    )
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def autorole_slash(
        interaction: discord.Interaction,
        role: discord.Role | None = None,
        off: bool | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use /autorole in a server.", ephemeral=True
            )
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if not is_administrator(interaction):
            await interaction.response.send_message(
                "Only Discord Administrators can use /autorole.", ephemeral=True
            )
            return

        note = ""
        if off:
            clear_guild_autorole(interaction.guild.id)
            note = "Auto-role is off. New joins will not get a role from Aetherion."
        elif role is not None:
            blocked = explain_role_block(interaction.guild, role)
            if blocked:
                await interaction.response.send_message(blocked, ephemeral=True)
                return
            set_guild_autorole(interaction.guild.id, role.id)
            note = f"New members will get {role.mention} when they join."

        await interaction.response.send_message(
            content=note or None,
            embed=_status_embed(interaction.guild),
            ephemeral=True,
        )
