"""Post in #welcome when someone joins."""

from __future__ import annotations

import logging

import discord

from ..config import settings

logger = logging.getLogger("groksito.welcome")


def _channel(guild: discord.Guild):
    cid = int(getattr(settings, "welcome_channel_id", 0) or 0)
    if cid:
        ch = guild.get_channel(cid)
        if ch is not None:
            return ch
    name = (getattr(settings, "welcome_channel_name", None) or "welcome").lower().lstrip("#")
    for ch in guild.text_channels:
        if ch.name.lower() == name:
            return ch
    return None


async def send_welcome(member: discord.Member) -> None:
    if not getattr(settings, "welcome_enabled", False):
        return
    if member.bot:
        return
    if getattr(member, "pending", False):
        return
    channel = _channel(member.guild)
    if channel is None:
        logger.warning("welcome: no channel found in guild %s", member.guild.id)
        return
    text = getattr(settings, "welcome_message", None) or (
        f"Welcome {member.mention} to **{member.guild.name}**."
    )
    text = (
        text.replace("{{User.Mention}}", member.mention)
        .replace("{{User.Name}}", member.display_name)
        .replace("{{Guild.Name}}", member.guild.name)
        .replace("{user}", member.mention)
        .replace("{server}", member.guild.name)
    )
    try:
        await channel.send(text)
    except Exception:
        logger.exception("welcome send failed")


async def on_member_join(member: discord.Member) -> None:
    await send_welcome(member)


async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    if getattr(before, "pending", False) and not getattr(after, "pending", False):
        await send_welcome(after)
