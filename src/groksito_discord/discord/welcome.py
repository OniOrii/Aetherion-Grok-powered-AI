"""Post text + a welcome banner when someone joins."""

from __future__ import annotations

import io
import logging
from urllib.parse import quote

import discord
import httpx

from ..config import settings

logger = logging.getLogger("groksito.welcome")

DEFAULT_BG = (
    "https://images.unsplash.com/photo-1508184964240-ee96bb9677a7"
    "?auto=format&fit=crop&w=1200&h=500"
)


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


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


def _fill(template: str, member: discord.Member) -> str:
    count = member.guild.member_count or 0
    text = template or (
        "Welcome {{User.Mention}} to **{{Guild.Name}}**! You are the {{Ordinal}} member!"
    )
    return (
        text.replace("{{User.Mention}}", member.mention)
        .replace("{{User.Name}}", member.display_name)
        .replace("{{Guild.Name}}", member.guild.name)
        .replace("{{Guild.Members}}", str(count))
        .replace("{{Ordinal}}", _ordinal(count))
        .replace("{user}", member.mention)
        .replace("{server}", member.guild.name)
    )

async def _imagine_background(member: discord.Member) -> str | None:
    key = settings.xai_api_key
    if not key:
        logger.warning("welcome imagine: no xai_api_key")
        return None
    prompt = (
        "Wide cinematic 16:9 welcome banner. Brand new scene, not a portrait. "
        "Use a soft purple, lilac, and gray color palette like a pale cat photo. "
        "Moody lighting, fabric and shadow atmosphere. No readable text, "
        "no watermark, no UI, no copied face."
    )
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.x.ai/v1/images/generations",
                headers=headers,
                json={
                    "model": "grok-imagine-image-quality",
                    "prompt": prompt,
                    "response_format": "url",
                    "aspect_ratio": "16:9",
                },
            )
            if r.status_code >= 400:
                logger.warning("welcome generate failed: %s %s", r.status_code, r.text[:240])
                return None
            rows = (r.json().get("data") or [])
            if rows and isinstance(rows[0], dict):
                return rows[0].get("url")
    except Exception:
        logger.exception("welcome imagine error")
    return None


async def _banner(member: discord.Member) -> discord.File | None:
    count = member.guild.member_count or 0
    avatar = member.display_avatar.replace(size=256).url
    bg = await _imagine_background(member)
    if not bg:
        bg = avatar
    url = (
        "https://api.popcat.xyz/welcomecard"
        f"?background={quote(bg, safe='')}"
        f"&avatar={quote(avatar, safe='')}"
        f"&text1={quote('Welcome')}"
        f"&text2={quote(member.display_name[:32])}"
        f"&text3={quote('to ' + member.guild.name + '  ·  ' + _ordinal(count) + ' member')}"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url)
        if r.status_code >= 400 or not r.content:
            logger.warning("welcome banner failed: %s", r.status_code)
            return None
        return discord.File(io.BytesIO(r.content), filename="welcome.png")
    except Exception:
        logger.exception("welcome banner error")
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
        logger.warning("welcome: no channel in guild %s", member.guild.id)
        return
    text = _fill(getattr(settings, "welcome_message", None) or "", member)
    banner = await _banner(member)
    try:
        if banner:
            await channel.send(content=text, file=banner)
        else:
            await channel.send(content=text)
    except Exception:
        logger.exception("welcome send failed")


async def on_member_join(member: discord.Member) -> None:
    await send_welcome(member)


async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    if getattr(before, "pending", False) and not getattr(after, "pending", False):
        await send_welcome(after)
