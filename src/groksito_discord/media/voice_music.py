"""Play/stop music on the same VoiceClient Aetherion already uses for TTS."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import discord

logger = logging.getLogger("groksito.voice_music")

_PLAY_RE = re.compile(
    r"(?:^|[\s\-]+|(?:please|can you|could you)\s+)(?:play|put on|queue)\s+(.+)$",
    re.IGNORECASE,
)
_STOP_RE = re.compile(
    r"\b(?:stop|pause|halt)(?:\s+(?:the\s+)?(?:music|song|track))?\b",
    re.IGNORECASE,
)
_SKIP_RE = re.compile(
    r"\b(?:skip|next)(?:\s+(?:the\s+)?(?:song|track|music))?\b",
    re.IGNORECASE,
)


def parse_music_command(prompt: str) -> tuple[str, str] | None:
    text = (prompt or "").strip().strip(".!?")
    text = re.sub(r"^[\s\-\u2013\u2014:]+", "", text).strip()
    if not text:
        return None
    low = text.lower()
    if _STOP_RE.search(text) and "play" not in low:
        return ("stop", "")
    if _SKIP_RE.search(text) and "play" not in low:
        return ("stop", "")
    m = _PLAY_RE.search(text)
    if m:
        query = m.group(1).strip().strip(".!?")
        query = re.sub(r"^(the\s+song\s+)", "", query, flags=re.IGNORECASE).strip()
        if query:
            logger.info("music play query: %s", query[:120])
            return ("play", query)
    return None


def _extract_track(query: str) -> dict[str, str] | None:
    try:
        import yt_dlp
    except Exception:
        logger.warning("yt-dlp is not installed")
        return None
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "default_search": "ytsearch1",
        "skip_download": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
    except Exception:
        logger.exception("yt-dlp extract failed for %s", query[:80])
        return None
    if not info:
        return None
    if "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        info = entries[0] if entries else None
    if not info:
        return None
    url = info.get("url") or ""
    title = (info.get("title") or query).strip()
    if not url:
        return None
    return {"url": url, "title": title[:120]}


async def resolve_track(query: str) -> dict[str, str] | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _extract_track, query)


def start_playback(vc: discord.VoiceClient, url: str) -> None:
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    vc.play(
        discord.FFmpegPCMAudio(
            url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn",
        )
    )
    logger.info("ffmpeg started music stream")


async def handle_music(vc: discord.VoiceClient | None, prompt: str) -> dict[str, Any] | None:
    parsed = parse_music_command(prompt)
    if parsed is None:
        return None
    action, query = parsed
    if vc is None or not getattr(vc, "is_connected", lambda: False)():
        return {"speak": "I am not in a voice channel."}
    if action == "stop":
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            return {"speak": "Stopped."}
        return {"speak": "Nothing is playing."}
    track = await resolve_track(query)
    if not track:
        return {"speak": "I could not find that song."}
    return {
        "speak": f"Playing {track['title']}.",
        "url": track["url"],
        "title": track["title"],
    }
