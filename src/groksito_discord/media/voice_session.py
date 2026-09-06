"""Live Discord voice listen + Grok reply.

Does NOT forward Discord UDP/Opus packets to Grok.
Each speaker's PCM is decoded, buffered until ~0.8s of silence, then sent
as one audio clip to xAI STT. Grok replies in text, TTS plays back in VC.

Only the member who ran /join is listened to (avoids the whole channel
being mashed into one request).
"""

from __future__ import annotations

import audioop
import asyncio
import io
import logging
import os
import tempfile
import wave
from typing import Any

import discord
import httpx

from ..config import settings

logger = logging.getLogger("groksito.voice_session")

DISCORD_RATE = 48000
STT_RATE = 16000
SILENCE_MS = 800
MIN_SPEECH_MS = 350
MAX_SPEECH_MS = 20_000
RMS_THRESHOLD = 250

try:
    from discord.ext import voice_recv
except Exception:  # pragma: no cover
    voice_recv = None  # type: ignore


def _pcm48_to_16_mono(pcm: bytes) -> bytes:
    if not pcm:
        return b""
    sample_width = 2
    # discord-ext-voice-recv typically gives 48k stereo s16le
    if len(pcm) % 4 == 0:
        mono, _ = audioop.tomono(pcm, sample_width, 1, 1)
    else:
        mono = pcm
    down, _ = audioop.ratecv(mono, sample_width, 1, DISCORD_RATE, STT_RATE, None)
    return down


def _wav_bytes(pcm16_mono: bytes, rate: int = STT_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm16_mono)
    return buf.getvalue()


def _api_key() -> str | None:
    return getattr(settings, "xai_api_key", None) or os.environ.get("XAI_API_KEY")


class _PcmFifoSource(discord.AudioSource):
    FRAME = 3840  # 20ms 48k stereo s16le

    def __init__(self) -> None:
        self._buf = bytearray()
        self._closed = False

    def feed(self, pcm48_stereo: bytes) -> None:
        if pcm48_stereo:
            self._buf.extend(pcm48_stereo)

    def close_source(self) -> None:
        self._closed = True

    def is_opus(self) -> bool:
        return False

    def read(self) -> bytes:
        if len(self._buf) >= self.FRAME:
            chunk = bytes(self._buf[: self.FRAME])
            del self._buf[: self.FRAME]
            return chunk
        if self._closed:
            return b""
        return b"\x00" * self.FRAME


class _UserSink(voice_recv.AudioSink if voice_recv else object):
    def __init__(self, session: "VoiceSession") -> None:
        if voice_recv:
            super().__init__()
        self.session = session

    def wants_opus(self) -> bool:
        return False

    def write(self, user: discord.abc.User | None, data: Any) -> None:
        pcm = getattr(data, "pcm", None)
        if not pcm:
            return
        uid = getattr(user, "id", None)
        if uid is None:
            uid = getattr(getattr(data, "user", None), "id", None)
        self.session.on_pcm(uid, pcm)

    def cleanup(self) -> None:
        return


class VoiceSession:
    def __init__(self, guild_id: int, user_id: int, voice_name: str = "eve") -> None:
        self.guild_id = guild_id
        self.user_id = user_id
        self.voice_name = voice_name
        self._buf = bytearray()
        self._last_voice_ms = 0.0
        self._speeching = False
        self._busy = False
        self._stop = asyncio.Event()
        self._vc: discord.VoiceProtocol | None = None
        self._loop = asyncio.get_event_loop()

    def on_pcm(self, user_id: int | None, pcm: bytes) -> None:
        if self._busy or self._stop.is_set():
            return
        if user_id is not None and user_id != self.user_id:
            return
        mono16 = _pcm48_to_16_mono(pcm)
        if not mono16:
            return
        rms = audioop.rms(mono16, 2)
        now = self._loop.time() * 1000
        if rms >= RMS_THRESHOLD:
            self._speeching = True
            self._last_voice_ms = now
            self._buf.extend(mono16)
            max_bytes = int(STT_RATE * 2 * (MAX_SPEECH_MS / 1000))
            if len(self._buf) > max_bytes:
                held = bytes(self._buf)
                self._buf.clear()
                self._speeching = False
                self._busy = True
                self._loop.create_task(self._reply(held))
        elif self._speeching:
            self._buf.extend(mono16)
            if now - self._last_voice_ms >= SILENCE_MS and not self._busy:
                held = bytes(self._buf)
                self._buf.clear()
                self._speeching = False
                duration_ms = (len(held) / 2) / STT_RATE * 1000
                if duration_ms >= MIN_SPEECH_MS:
                    self._busy = True
                    self._loop.create_task(self._reply(held))
                else:
                    self._buf.clear()

    async def _reply(self, pcm16: bytes) -> None:
        try:
            text = await self._transcribe(pcm16)
            if not text:
                logger.info("empty transcript, skipping")
                return
            logger.info("heard (%s): %s", self.user_id, text[:200])
            reply = await self._grok_text(text)
            if not reply:
                return
            logger.info("say: %s", reply[:200])
            audio = await self._tts(reply)
            if audio:
                await self._play_mp3(audio)
        except Exception:
            logger.exception("voice reply failed")
        finally:
            self._busy = False

    async def _transcribe(self, pcm16: bytes) -> str:
        key = _api_key()
        if not key:
            raise RuntimeError("No XAI_API_KEY")
        wav = _wav_bytes(pcm16)
        async with httpx.AsyncClient(timeout=60) as client:
            for url in ("https://api.x.ai/v1/stt", "https://api.x.ai/v1/audio/transcriptions"):
                files = {"file": ("speech.wav", wav, "audio/wav")}
                data = {"model": "grok-stt"}
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                    files=files,
                    data=data,
                )
                if resp.status_code >= 400:
                    logger.warning("STT %s %s %s", url, resp.status_code, resp.text[:300])
                    continue
                payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                text = (payload.get("text") or payload.get("transcript") or "").strip()
                if text:
                    return text
        return ""

    async def _grok_text(self, heard: str) -> str:
        key = _api_key()
        if not key:
            raise RuntimeError("No XAI_API_KEY")
        model = getattr(settings, "grok_model", None) or "grok-4.3"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Aetherion in a Discord voice channel. "
                        "Reply in one or two short spoken sentences. No markdown."
                    ),
                },
                {"role": "user", "content": heard},
            ],
            "temperature": 0.8,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        msg = (choices[0].get("message") or {}).get("content") if choices else ""
        return (msg or "").strip()

    async def _tts(self, text: str) -> bytes | None:
        key = _api_key()
        if not key:
            return None
        payload = {
            "text": text,
            "voice_id": self.voice_name or "eve",
            "language": getattr(settings, "tts_default_language", None) or "en",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.x.ai/v1/tts",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code >= 400:
                logger.warning("TTS failed %s %s", resp.status_code, resp.text[:300])
                return None
            return resp.content

    async def _play_mp3(self, audio: bytes) -> None:
        vc = self._vc
        if vc is None or not getattr(vc, "is_connected", lambda: False)():
            return
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(audio)
        tmp.close()
        try:
            if vc.is_playing():
                vc.stop()
            vc.play(discord.FFmpegPCMAudio(tmp.name))
        except Exception:
            logger.exception("VC playback failed")

    def stop(self) -> None:
        self._stop.set()
        self._buf.clear()


_sessions: dict[int, VoiceSession] = {}


def get_recv_cls():
    if voice_recv is None:
        return None
    return getattr(voice_recv, "VoiceRecvClient", None)


async def start_session(
    guild: discord.Guild,
    voice_client: discord.VoiceProtocol,
    user_id: int,
    voice_name: str = "eve",
) -> str:
    if voice_recv is None:
        return "Voice receive package is not installed (discord-ext-voice-recv)."
    old = _sessions.pop(guild.id, None)
    if old:
        old.stop()
    session = VoiceSession(guild.id, user_id, voice_name=voice_name)
    session._vc = voice_client
    _sessions[guild.id] = session
    sink = _UserSink(session)
    listen = getattr(voice_client, "listen", None)
    if listen is None:
        return "This voice connection cannot hear users. /leave then /join again."
    try:
        listen(sink)
    except Exception as e:
        return f"Could not start listening: {e}"
    return (
        "Listening only to you. Talk, pause about a second, and I will answer out loud. "
        "Use /leave when done."
    )


def stop_session(guild_id: int) -> None:
    session = _sessions.pop(guild_id, None)
    if session:
        session.stop()


