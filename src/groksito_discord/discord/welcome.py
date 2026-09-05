"""Post text + a welcome banner when someone joins."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import discord
import httpx

from ..config import settings

logger = logging.getLogger("groksito.welcome")

DEFAULT_BG = (
    "https://images.unsplash.com/photo-1508184964240-ee96bb9677a7"
    "?auto=format&fit=crop&w=1200&h=500"
)


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "welcome_channels.json"


def _load_store() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("welcome store read failed")
        return {}


def _save_store(data: dict) -> None:
    path = _store_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_guild_welcome_channel_id(guild_id: int) -> int:
    store = _load_store()
    raw = store.get(str(guild_id)) or store.get(guild_id)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def set_guild_welcome_channel(guild_id: int, channel_id: int) -> None:
    store = _load_store()
    store[str(guild_id)] = int(channel_id)
    _save_store(store)
    try:
        settings.welcome_channel_id = int(channel_id)
        settings.welcome_enabled = True
    except Exception:
        pass


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _channel(guild: discord.Guild):
    cid = get_guild_welcome_channel_id(guild.id)
    if not cid:
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


def _avatar_url(member: discord.Member) -> str:
    return str(member.display_avatar.replace(size=512).url)


def _imagine_prompt(member: discord.Member, scene: str | None = None) -> str:
    scene_bit = (scene or "").strip()
    extra = f" Scene cues from this member's profile picture: {scene_bit}." if scene_bit else ""
    return (
        "Wide cinematic 16:9 welcome banner environment only. "
        "Expand the attached profile picture into a brand-new matching background: "
        "same colors, lighting, objects, and mood, but as a room or landscape, "
        "not a close-up portrait. Keep the center relatively uncluttered so a "
        "circular avatar can sit on top. No readable text, no watermark, no UI, "
        "do not copy the face into the background. Unique composition for this "
        f"user ({member.id}).{extra}"
    )


async def _describe_avatar(client: httpx.AsyncClient, headers: dict, avatar_url: str) -> str | None:
    model = getattr(settings, "model", None) or "grok-4-fast-non-reasoning"
    try:
        r = await client.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "temperature": 0.4,
                "max_tokens": 180,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": avatar_url, "detail": "low"},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Describe this Discord profile picture in one short sentence "
                                    "for an image prompt: subject, colors, objects, setting, mood. "
                                    "No names. No quotes."
                                ),
                            },
                        ],
                    }
                ],
            },
        )
        if r.status_code >= 400:
            logger.warning("welcome vision failed: %s %s", r.status_code, r.text[:240])
            return None
        choices = r.json().get("choices") or []
        if not choices:
            return None
        text = ((choices[0].get("message") or {}).get("content") or "").strip()
        return text[:280] or None
    except Exception:
        logger.exception("welcome vision error")
        return None


async def _post_image(
    client: httpx.AsyncClient,
    headers: dict,
    path: str,
    payload: dict,
) -> str | None:
    r = await client.post(f"https://api.x.ai/v1{path}", headers=headers, json=payload)
    if r.status_code >= 400:
        logger.warning("welcome %s failed: %s %s", path, r.status_code, r.text[:240])
        return None
    rows = (r.json().get("data") or [])
    if rows and isinstance(rows[0], dict):
        return rows[0].get("url")
    return None


async def _imagine_background(member: discord.Member) -> str | None:
    key = settings.xai_api_key
    if not key:
        logger.warning("welcome imagine: no xai_api_key")
        return None
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    avatar_url = _avatar_url(member)
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            scene = await _describe_avatar(client, headers, avatar_url)
            prompt = _imagine_prompt(member, scene)
            payload = {
                "model": "grok-imagine-image-quality",
                "prompt": prompt,
                "response_format": "url",
                "aspect_ratio": "16:9",
                "image": {"url": avatar_url, "type": "image_url"},
            }
            url = await _post_image(client, headers, "/images/edits", payload)
            if url:
                return url
            url = await _post_image(client, headers, "/images/generations", payload)
            if url:
                return url
            gen_only = {
                "model": "grok-imagine-image-quality",
                "prompt": prompt,
                "response_format": "url",
                "aspect_ratio": "16:9",
            }
            return await _post_image(client, headers, "/images/generations", gen_only)
    except Exception:
        logger.exception("welcome imagine error")
    return None


async def _banner(member: discord.Member) -> discord.File | None:
    import unicodedata
    from PIL import Image, ImageDraw, ImageFont

    def plain(s: str) -> str:
        s = unicodedata.normalize("NFKC", s or "")
        return "".join(ch if ord(ch) < 128 else " " for ch in s).strip()

    avatar_url = _avatar_url(member)
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
        size = 280
        ring = 10
        av = Image.open(io.BytesIO(av_r.content)).convert("RGBA").resize((size, size))
        ring_img = Image.new("RGBA", (size + ring * 2, size + ring * 2), (0, 0, 0, 0))
        ImageDraw.Draw(ring_img).ellipse(
            (0, 0, size + ring * 2 - 1, size + ring * 2 - 1),
            fill="white",
        )
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        ring_img.paste(av, (ring, ring), mask)
        x = (1200 - (size + ring * 2)) // 2
        bg.paste(ring_img, (x, 40), ring_img)

        draw = ImageDraw.Draw(bg)
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
            name_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        except Exception:
            title_font = ImageFont.load_default()
            name_font = title_font

        lines = [
            ("Welcome", title_font, 348),
            (plain(member.display_name)[:24], name_font, 420),
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
    if not getattr(settings, "welcome_enabled", False) and not get_guild_welcome_channel_id(member.guild.id):
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
