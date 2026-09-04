"""Live Discord voice <-> xAI Grok Voice (v1).

One speaker per guild: the member who ran /join.
Discord PCM is 48 kHz stereo s16le. xAI realtime expects 24 kHz mono PCM16.
"""

from __future__ import annotations

import audioop
import asyncio
import base64
import json
import logging
import os
from typing import Any

import discord

from ..config import settings

logger = logging.getLogger("groksito.voice_session")

XAI_REALTIME_URL = "wss://api.x.ai/v1/realtime?model=grok-voice-latest"
DISCORD_RATE = 48000
XAI_RATE = 24000
SILENCE_MS = 900
MIN_SPEECH_MS = 400
RMS_THRESHOLD = 280

try:
    from discord.ext import voice_recv
except Exception:  # pragma: no cover
    voice_recv = None  # type: ignore


def _pcm48_stereo_to_24_mono(pcm: bytes) -> bytes:
    if not pcm:
        return b""
    mono, _ = audioop.tomono(pcm, 2, 1, 1)
    down, _ = audioop.ratecv(mono, 2, 1, DISCORD_RATE, XAI_RATE, None)
    return down


def _pcm24_mono_to_48_stereo(pcm: bytes) -> bytes:
    if not pcm:
        return b""
    up, _ = audioop.ratecv(pcm, 2, 1, XAI_RATE, DISCORD_RATE, None)
    return audioop.tostereo(up, 2, 1, 1)


class _PcmFifoSource(discord.AudioSource):
    """20 ms chunks of 48 kHz stereo s16le for VoiceClient.play."""

    FRAME = 3840  # 48000 * 2ch * 2bytes * 0.02s

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
    """Minimal sink compatible with discord-ext-voice-recv."""

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
        self._ws = None
        self._player: _PcmFifoSource | None = None
        self._vc: discord.VoiceProtocol | None = None
        self._loop = asyncio.get_event_loop()

    def on_pcm(self, user_id: int | None, pcm: bytes) -> None:
        if self._busy or user_id != self.user_id:
            return
        mono24 = _pcm48_stereo_to_24_mono(pcm)
        if not mono24:
            return
        rms = audioop.rms(mono24, 2)
        now = self._loop.time() * 1000
        if rms >= RMS_THRESHOLD:
            self._speeching = True
            self._last_voice_ms = now
            self._buf.extend(mono24)
        elif self._speeching:
            self._buf.extend(mono24)
            if now - self._last_voice_ms >= SILENCE_MS and not self._busy:
                held = bytes(self._buf)
                self._buf.clear()
                self._speeching = False
                duration_ms = (len(held) / 2) / XAI_RATE * 1000
                if duration_ms >= MIN_SPEECH_MS:
                    self._busy = True
                    self._loop.create_task(self._reply(held))

    async def _reply(self, pcm24: bytes) -> None:
        try:
            await self._stream_grok(pcm24)
        except Exception:
            logger.exception("voice reply failed")
        finally:
            self._busy = False

    async def _stream_grok(self, pcm24: bytes) -> None:
        import websockets

        api_key = settings.xai_api_key or os.environ.get("XAI_API_KEY")
        if not api_key:
            logger.error("No XAI_API_KEY — cannot talk")
            return

        headers = {"Authorization": f"Bearer {api_key}"}
        async with websockets.connect(
            XAI_REALTIME_URL,
            additional_headers=headers,
            max_size=8_000_000,
        ) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "session.update",
                        "session": {
                            "voice": self.voice_name,
                            "instructions": (
                                "You are Aetherion, a Grok-powered assistant in a Discord voice channel. "
                                "Speak briefly and naturally."
                            ),
                            "turn_detection": {"type": "server_vad"},
                            "modalities": ["audio", "text"],
                        },
                    }
                )
            )
            await ws.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(pcm24).decode("ascii"),
                    }
                )
            )
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await ws.send(json.dumps({"type": "response.create"}))

            player = _PcmFifoSource()
            self._player = player
            vc = self._vc
            if vc is None:
                return
            if vc.is_playing():
                vc.stop()
            vc.play(player)

            try:
                async for raw in ws:
                    if self._stop.is_set():
                        break
                    try:
                        ev = json.loads(raw)
                    except Exception:
                        continue
                    kind = ev.get("type") or ""
                    if kind in (
                        "response.output_audio.delta",
                        "response.audio.delta",
                    ):
                        delta = ev.get("delta") or ""
                        if delta:
                            player.feed(_pcm24_mono_to_48_stereo(base64.b64decode(delta)))
                    elif kind in (
                        "response.output_audio.done",
                        "response.audio.done",
                        "response.done",
                    ):
                        break
                    elif kind == "error":
                        logger.error("xAI voice error: %s", ev)
                        break
            finally:
                player.close_source()

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
        return "Voice receive package is not installed."
    old = _sessions.pop(guild.id, None)
    if old:
        old.stop()
    session = VoiceSession(guild.id, user_id, voice_name=voice_name)
    session._vc = voice_client
    _sessions[guild.id] = session
    sink = _UserSink(session)
    listen = getattr(voice_client, "listen", None)
    if listen is None:
        return "This voice connection cannot hear users. Reconnect with /leave then /join."
    try:
        listen(sink)
    except Exception as e:
        return f"Could not start listening: {e}"
    return "Listening. Talk after a short pause and I will answer out loud."


def stop_session(guild_id: int) -> None:
    session = _sessions.pop(guild_id, None)
    if session:
        session.stop()
