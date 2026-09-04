"""Voice-note talk-back.

Discord live VC listen is broken (Opus/SSRC). This path uses a Discord
voice message (the mic button) instead:

1. Download the ogg/mp3 clip
2. Transcribe with xAI STT
3. Ask Grok for a short spoken reply
4. Speak it with existing TTS (channel bubble) and play in the VC if joined
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Any

import discord

from ..config import settings

logger = logging.getLogger("groksito.voice_reply")

STT_URLS = (
    "https://api.x.ai/v1/audio/transcriptions",
    "https://api.x.ai/v1/stt",
)
CHAT_URL = "https://api.x.ai/v1/chat/completions"


def _api_key() -> str | None:
    return settings.xai_api_key or os.environ.get("XAI_API_KEY")


def is_voice_note(message: discord.Message) -> bool:
    atts = getattr(message, "attachments", None) or []
    if not atts:
        return False
    flags = getattr(message, "flags", None)
    if flags is not None and getattr(flags, "voice", False):
        return True
    for att in atts:
        name = (getattr(att, "filename", "") or "").lower()
        ct = (getattr(att, "content_type", "") or "").lower()
        if "voice-message" in name or name.endswith((".ogg", ".opus", ".mp3", ".wav", ".m4a", ".webm")):
            return True
        if ct.startswith("audio/"):
            return True
    return False


async def _transcribe(audio_bytes: bytes, filename: str) -> str:
    import aiohttp

    key = _api_key()
    if not key:
        raise RuntimeError("No XAI_API_KEY")
    last_err = "stt failed"
    for url in STT_URLS:
        form = aiohttp.FormData()
        form.add_field("model", "grok-stt")
        form.add_field("file", audio_bytes, filename=filename or "voice.ogg", content_type="application/octet-stream")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                data=form,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    last_err = f"{url} {resp.status} {body[:300]}"
                    logger.warning("STT failed: %s", last_err)
                    continue
                try:
                    data = await resp.json()
                except Exception:
                    data = {"text": body}
                text = (data.get("text") or data.get("transcript") or "").strip()
                if text:
                    return text
                last_err = f"empty transcript: {body[:200]}"
    raise RuntimeError(last_err)


async def _grok_reply(user_text: str) -> str:
    import aiohttp

    key = _api_key()
    if not key:
        raise RuntimeError("No XAI_API_KEY")
    payload = {
        "model": "grok-3",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Aetherion, a Grok-powered assistant speaking in a Discord voice chat. "
                    "Reply in one or two short spoken sentences. No markdown."
                ),
            },
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.8,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            CHAT_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                raise RuntimeError(f"chat {resp.status} {data}")
    choices = data.get("choices") or []
    msg = (choices[0].get("message") or {}).get("content") if choices else None
    text = (msg or "").strip()
    if not text:
        raise RuntimeError(f"empty grok reply: {data}")
    return text


async def _play_in_vc(guild: discord.Guild | None, audio_bytes: bytes) -> None:
    if guild is None:
        return
    vc = guild.voice_client
    if vc is None or not getattr(vc, "is_connected", lambda: False)():
        return
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.write(audio_bytes)
    tmp.close()
    try:
        if vc.is_playing():
            vc.stop()
        vc.play(discord.FFmpegPCMAudio(tmp.name))
    except Exception:
        logger.exception("VC playback failed")


async def _tts_bytes(text: str) -> bytes | None:
    """Best-effort: call xAI TTS the same way /audio does."""
    import aiohttp

    key = _api_key()
    if not key:
        return None
    voice = getattr(settings, "tts_default_voice", None) or "eve"
    payload = {
        "text": text,
        "voice_id": voice,
        "language": getattr(settings, "tts_default_language", None) or "en",
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.x.ai/v1/tts",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status >= 400:
                logger.warning("TTS failed %s %s", resp.status, await resp.text())
                return None
            return await resp.read()


async def maybe_handle_voice_note(message: discord.Message) -> bool:
    """Return True if this message was a voice note we handled (caller should stop)."""
    if message.author.bot:
        return False
    if not is_voice_note(message):
        return False

    att = (message.attachments or [None])[0]
    if att is None:
        return False

    logger.info("voice note from %s file=%s", message.author.id, getattr(att, "filename", "?"))
    await message.channel.typing()
    try:
        raw = await att.read()
        heard = await _transcribe(raw, getattr(att, "filename", "voice.ogg"))
        logger.info("transcript: %s", heard[:200])
        reply = await _grok_reply(heard)
        logger.info("reply: %s", reply[:200])
        audio = await _tts_bytes(reply)
        if audio:
            await _play_in_vc(message.guild, audio)
            await message.reply(
                f"**You said:** {heard}\n**Aetherion:** {reply}",
                mention_author=False,
                file=discord.File(io.BytesIO(audio), filename="aetherion.mp3"),
            )
        else:
            await message.reply(
                f"**You said:** {heard}\n**Aetherion:** {reply}",
                mention_author=False,
            )
    except Exception as e:
        logger.exception("voice note failed")
        try:
            await message.reply(f"Could not answer that voice note: {e}", mention_author=False)
        except Exception:
            pass
    return True
