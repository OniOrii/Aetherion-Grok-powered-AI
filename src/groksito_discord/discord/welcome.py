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
    from PIL import Image, ImageDraw, ImageFont

    count = member.guild.member_count or 0
    avatar_url = member.display_avatar.replace(size=256).url
    bg_url = await _imagine_background(member)
    if not bg_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            bg_r = await client.get(bg_url)
            av_r = await client.get(avatar_url)
        if bg_r.status_code >= 400 or av_r.status_code >= 400:
            return None
        bg = Image.open(io.BytesIO(bg_r.content)).convert("RGBA").resize((1200, 500))
        av = Image.open(io.BytesIO(av_r.content)).convert("RGBA").resize((220, 220))
        mask = Image.new("L", (220, 220), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 219, 219), fill=255)
        bg.paste(av, (490, 70), mask)
        draw = ImageDraw.Draw(bg)
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        except Exception:
            title_font = ImageFont.load_default()
            small_font = title_font
        lines = [
            ("Welcome", title_font, 320),
            (member.display_name[:24], small_font, 390),
            (f"to {member.guild.name}  ·  {_ordinal(count)} member", small_font, 430),
        ]
        for text, font, y in lines:
            draw.text(
                (600, y),
                text,
                font=font,
                fill="white",
                anchor="mt",
                stroke_width=3,
                stroke_fill="black",
            )
        out = io.BytesIO()
        bg.convert("RGB").save(out, format="PNG")
        out.seek(0)
        return discord.File(out, filename="welcome.png")
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
