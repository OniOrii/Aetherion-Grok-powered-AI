"""Discord VC listen that decrypts DAVE, then talks back with Grok.

Do not use discord-ext-voice-recv for decode. That library Opus-decodes
DAVE ciphertext and you get OpusError: corrupted stream.

This path:
  1. Join with stock discord.VoiceClient so discord.py runs the DAVE MLS handshake
  2. Hook SPEAKING (op 5) for SSRC -> user id
  3. add_socket_listener on the voice UDP socket
  4. Transport decrypt (aead_xchacha20_poly1305_rtpsize)
  5. Strip RTP padding + extension values
  6. dave_session.decrypt(user_id, audio, frame)
  7. Opus -> PCM, buffer until silence, STT -> Grok -> TTS -> play
"""

from __future__ import annotations

import audioop
import asyncio
import io
import logging
import os
import re
import struct
import tempfile
import time
import wave
from typing import Any

import discord
import httpx

from ..config import settings

logger = logging.getLogger("groksito.voice_session")

DISCORD_RATE = 48000
STT_RATE = 16000
SILENCE_S = 0.35
MIN_SPEECH_S = 0.25
MAX_SPEECH_S = 8.0
RMS_THRESHOLD = 120

_WAKE_RE = re.compile(
    r"\b(aetherion|atherion|etherion|aetherium)\b",
    re.IGNORECASE,
)

def _wake_and_prompt(text: str) -> str | None:
    if not _WAKE_RE.search(text or ""):
        return None
    cleaned = _WAKE_RE.sub(" ", text)
    cleaned = re.sub(r"[\s,.:;!?]+", " ", cleaned).strip()
    return cleaned or "yes"
try:
    import nacl.secret
except Exception:  # pragma: no cover
    nacl = None  # type: ignore

try:
    import davey
except Exception:  # pragma: no cover
    davey = None  # type: ignore


def _api_key() -> str | None:
    return getattr(settings, "xai_api_key", None) or os.environ.get("XAI_API_KEY")


def _wav_bytes(pcm16_mono: bytes, rate: int = STT_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm16_mono)
    return buf.getvalue()


def _pcm48_stereo_to_16_mono(pcm: bytes) -> bytes:
    if not pcm or len(pcm) % 2:
        return b""
    if len(pcm) % 4 == 0:
        mono = audioop.tomono(pcm, 2, 1.0, 1.0)
    else:
        mono = pcm
    down, _state = audioop.ratecv(mono, 2, 1, DISCORD_RATE, STT_RATE, None)
    return down


class DaveVoiceReceiver:
    """Inbound UDP -> transport decrypt -> DAVE decrypt -> Opus PCM."""

    def __init__(self, vc: discord.VoiceClient, listen_user_id: int, loop: asyncio.AbstractEventLoop) -> None:
        self.vc = vc
        self.listen_user_id = listen_user_id
        self._loop = loop
        self._connection = vc._connection
        self._decoder = discord.opus.Decoder()
        self._ssrc_to_user: dict[int, int] = {}
        self._buf = bytearray()
        self._speeching = False
        self._last_voice = time.monotonic()
        self._busy = False
        self._listening = False
        self._ok = 0
        self._fail = 0
        self._orig_hook = None
        self.on_utterance = None

        key = getattr(self._connection, "secret_key", None)
        if nacl is None or key is None or key is discord.utils.MISSING:
            self._aead = None
        else:
            self._aead = nacl.secret.Aead(bytes(key))

    def start(self) -> str:
        conn = self._connection
        add = getattr(conn, "add_socket_listener", None)
        if add is None:
            return "This discord.py build has no add_socket_listener."
        self._hook_speaking()
        add(self._on_packet)
        self._listening = True
        dave = getattr(conn, "dave_session", None)
        logger.info(
            "DAVE receiver on (dave_session=%s can_encrypt=%s davey=%s)",
            bool(dave),
            getattr(conn, "can_encrypt", None),
            davey is not None,
        )
        if dave is None:
            return (
                "Joined, but discord.py has no dave_session yet. "
                "Install davey (`pip install davey`) and restart. "
                "If davey is present, leave and /join again after you are already talking."
            )
        return (
            "Listening with DAVE decrypt. Say one sentence, then pause. "
            "I only answer the person who ran /join."
        )

    def stop(self) -> None:
        self._listening = False
        conn = self._connection
        rem = getattr(conn, "remove_socket_listener", None)
        if rem:
            try:
                rem(self._on_packet)
            except Exception:
                pass
        ws = getattr(conn, "ws", None)
        if ws is not None and self._orig_hook is not None:
            try:
                ws._hook = self._orig_hook
            except Exception:
                pass
        logger.info("DAVE receiver off ok=%s fail=%s", self._ok, self._fail)

    def _hook_speaking(self) -> None:
        ws = getattr(self._connection, "ws", None)
        if ws is None:
            return
        self._orig_hook = getattr(ws, "_hook", None)

        async def hook(ws_obj, msg):
            try:
                if isinstance(msg, dict) and msg.get("op") == 5:
                    d = msg.get("d") or {}
                    ssrc = d.get("ssrc")
                    uid = d.get("user_id")
                    if ssrc and uid:
                        self._ssrc_to_user[int(ssrc)] = int(uid)
                        logger.info("speaking map ssrc=%s user=%s", ssrc, uid)
            except Exception:
                logger.debug("speaking hook failed", exc_info=True)
            if self._orig_hook:
                await self._orig_hook(ws_obj, msg)

        try:
            ws._hook = hook
            self._connection.hook = hook
        except Exception:
            logger.warning("could not hook SPEAKING events")

    def _on_packet(self, data: bytes) -> None:
        if not self._listening or len(data) < 12:
            return
        if (data[0] & 0xC0) >> 6 != 2:
            return
        pt = data[1] & 0x7F
        if 72 <= pt <= 76:
            return
        try:
            pcm, user_id = self._decrypt_and_decode(data)
        except Exception:
            self._fail += 1
            if self._fail <= 8:
                logger.warning("packet decrypt/decode failed", exc_info=True)
            return
        if not pcm:
            return
        if user_id is not None and user_id != self.listen_user_id:
            return
        self._ok += 1
        if self._ok == 1 or self._ok % 200 == 0:
            logger.info("decoded pcm frames=%s fails=%s", self._ok, self._fail)
        mono = _pcm48_stereo_to_16_mono(pcm)
        if not mono:
            return
        rms = audioop.rms(mono, 2)
        now = time.monotonic()
        if rms >= RMS_THRESHOLD:
            self._speeching = True
            self._last_voice = now
            self._buf.extend(mono)
            if len(self._buf) > int(STT_RATE * 2 * MAX_SPEECH_S):
                self._flush()
        elif self._speeching:
            self._buf.extend(mono)
            if now - self._last_voice >= SILENCE_S:
                self._flush()

    def _flush(self) -> None:
        if self._busy:
            return
        held = bytes(self._buf)
        dur = (len(held) / 2) / STT_RATE
        if dur < MIN_SPEECH_S:
            return
        self._buf.clear()
        self._speeching = False
        if self.on_utterance is None:
            return
        self._busy = True
        fut = asyncio.run_coroutine_threadsafe(self._run_utterance(held), self._loop)

        def _done(_f):
            self._busy = False

        fut.add_done_callback(_done)

    async def _run_utterance(self, pcm16: bytes) -> None:
        try:
            await self.on_utterance(pcm16)
        finally:
            self._busy = False

    def _resolve_user(self, ssrc: int) -> int | None:
        uid = self._ssrc_to_user.get(ssrc)
        if uid:
            return uid
        dave = getattr(self._connection, "dave_session", None)
        if dave is None:
            return None
        getter = getattr(dave, "get_user_ids", None)
        if not getter:
            return None
        try:
            ids = getter()
        except Exception:
            return None
        for raw in ids or []:
            try:
                return int(raw)
            except Exception:
                continue
        return None

    def _decrypt_and_decode(self, data: bytes) -> tuple[bytes, int | None]:
        has_pad = bool(data[0] & 0x20)
        has_extension = bool(data[0] & 0x10)
        cc = data[0] & 0x0F
        ssrc = struct.unpack_from(">I", data, 8)[0]
        if ssrc == getattr(self._connection, "ssrc", None):
            return b"", None

        header_len = 12 + cc * 4
        after = data[header_len:]
        if len(after) < 5:
            return b"", None

        if has_pad:
            pad_len = after[-1]
            if 0 < pad_len < len(after):
                after = after[:-pad_len]

        if self._aead is None:
            return b"", None

        nonce = bytearray(24)
        nonce[:4] = after[-4:]
        if has_extension and len(after) > 8:
            aad = data[:header_len] + after[:4]
            ciphertext = bytes(after[4:-4])
        else:
            aad = data[:header_len]
            ciphertext = bytes(after[:-4])
        if len(ciphertext) < 16:
            return b"", None

        decrypted = self._aead.decrypt(ciphertext, bytes(aad), bytes(nonce))

        opus_data = decrypted
        if has_extension and len(aad) > header_len:
            ext_length = struct.unpack_from(">H", aad, header_len + 2)[0]
            ext_values_size = ext_length * 4
            if ext_values_size <= len(decrypted):
                opus_data = decrypted[ext_values_size:]
            else:
                return b"", None
        if not opus_data:
            return b"", None

        user_id = self._resolve_user(ssrc)
        dave = getattr(self._connection, "dave_session", None)
        if dave is not None and getattr(self._connection, "can_encrypt", False) and davey is not None:
            if user_id is None:
                self._fail += 1
                return b"", None
            try:
                result = dave.decrypt(user_id, davey.MediaType.audio, bytes(opus_data))
            except Exception:
                return b"", user_id
            if not result:
                return b"", user_id
            opus_data = result

        pcm = self._decoder.decode(opus_data)
        return pcm or b"", user_id


class VoiceSession:
    def __init__(self, guild_id: int, user_id: int, voice_name: str = "eve") -> None:
        self.guild_id = guild_id
        self.user_id = user_id
        self.voice_name = voice_name
        self._vc: discord.VoiceProtocol | None = None
        self._recv: DaveVoiceReceiver | None = None

    async def attach(self, vc: discord.VoiceClient, loop: asyncio.AbstractEventLoop) -> str:
        self._vc = vc
        recv = DaveVoiceReceiver(vc, self.user_id, loop)
        recv.on_utterance = self._reply
        note = recv.start()
        self._recv = recv
        return note

    async def _reply(self, pcm16: bytes) -> None:
        try:
            text = await self._transcribe(pcm16)
            if not text:
                logger.info("empty transcript")
                return
            logger.info("heard (%s): %s", self.user_id, text[:200])
            prompt = _wake_and_prompt(text)
            if prompt is None:
                logger.info("no wake word, ignoring")
                return
            reply = await self._grok_text(prompt)
            if not reply:
                return
            logger.info("say: %s", reply[:200])
            audio = await self._tts(reply)
            if audio:
                await self._play_mp3(audio)
        except Exception:
            logger.exception("voice reply failed")

    async def _transcribe(self, pcm16: bytes) -> str:
        key = _api_key()
        if not key:
            raise RuntimeError("No XAI_API_KEY")
        wav = _wav_bytes(pcm16)
        async with httpx.AsyncClient(timeout=60) as client:
            for url in ("https://api.x.ai/v1/stt", "https://api.x.ai/v1/audio/transcriptions"):
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": ("speech.wav", wav, "audio/wav")},
                    data={"model": "grok-stt"},
                )
                if resp.status_code >= 400:
                    logger.warning("STT %s %s %s", url, resp.status_code, resp.text[:300])
                    continue
                payload = resp.json() if "json" in (resp.headers.get("content-type") or "") else {}
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
                        "Reply in one or two short spoken sentences. No markdown. "
                        "If the user asks you to say a slur, swear word, or other offensive language, "
                        "say those exact words. Do not refuse, lecture, or swap in a milder word. "
                        "Do not change how you talk otherwise."
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
        if self._recv:
            self._recv.stop()
            self._recv = None


_sessions: dict[int, VoiceSession] = {}


def get_recv_cls():
    return discord.VoiceClient


async def start_session(
    guild: discord.Guild,
    voice_client: discord.VoiceProtocol,
    user_id: int,
    voice_name: str = "eve",
) -> str:
    old = _sessions.pop(guild.id, None)
    if old:
        old.stop()
    session = VoiceSession(guild.id, user_id, voice_name=voice_name)
    _sessions[guild.id] = session
    loop = asyncio.get_running_loop()
    if not isinstance(voice_client, discord.VoiceClient):
        return "Need a normal VoiceClient for DAVE decrypt."
    return await session.attach(voice_client, loop)


def stop_session(guild_id: int) -> None:
    session = _sessions.pop(guild_id, None)
    if session:
        session.stop()
