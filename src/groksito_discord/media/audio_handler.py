9"""
Centralized, modern audio / TTS (Text-to-Speech) handler for Groksito.

This module is the single source of truth for generating spoken audio from text.

Follows the exact same architectural style as `image_handler.py` and `video_handler.py`:
- Dedicated always-on text preparation / enhancement (cleaning + speech-friendly tweaks, Spanish-aware).
- Centralized auth, HTTP, retry, error handling.
- Direct delivery via image_delivery (register + consume + reply) as a playable audio attachment.
  The spoken text is surfaced in the reply (when short enough) + the audio is attached.
  When possible we deliver as real Discord voice message (Opus + waveform + voice flag) so it renders the nice bubble UI instead of a plain attachment.
  Unified UX for all audio requests (no more special "tts" vs "generate audio" branching).
- Explicit intent guard (lazy call back to media_tools).
- **extra_params for future voice params (speed, emotion, pitch, etc.).
- Graceful handling of long text (truncate + note; basic split support possible in future).
- Clean natural Spanish user feedback.
- Fully compatible with normal chat, tool dispatch, and DIRECT_DELIVERY_PERFORMED sentinel.

No breaking changes to image/video flows.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from io import BytesIO
from typing import Any, Optional

import httpx
import discord  # core dep; needed for voice message File subclass + MessageFlags

# For reliable voice message delivery (flag + attachment metadata).
# High-level reply(..., flags=...) is not always available / consistent even on 2.7.x
# (as seen in container), so we prefer the low-level path using handle_message_parameters.
try:
    from discord.http import handle_message_parameters
    from discord import AllowedMentions
except Exception:
    handle_message_parameters = None
    AllowedMentions = None  # type: ignore[assignment]


# pydub + ffmpeg are used for proper voice message support (transcode xAI MP3 -> Opus OGG
# + generate waveform + duration). If ffmpeg is missing we fall back to a regular MP3
# attachment (no waveform bubble UI). On Windows you need ffmpeg in PATH for the bubble.
try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None  # type: ignore


from ..utils.correlation import cid_prefix
from ..config import settings
from .delivery import consume_image_request, register_image_request

# Bearer resolution (OAuth preferred)
try:
    from ..core.grok_oauth import get_grok_bearer
except Exception:
    get_grok_bearer = None  # type: ignore

logger = logging.getLogger("groksito.media.audio_handler")


# =============================================================================
# Voice message helper (for Discord bubble UI)
# =============================================================================

class _VoiceMessageFile(discord.File):
    """
    Subclass of discord.File that injects the fields Discord requires
    for a real voice message (the waveform "bubble" UI with player/scrubber).

    discord.py no longer accepts duration/waveform in the File constructor
    (that API was removed). The default to_dict() also doesn't emit them.
    We override to_dict() so the attachments payload sent to Discord includes
    duration_secs + waveform when we use the voice message flag.
    """

    def __init__(self, *args, duration: float = 0.0, waveform: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._voice_duration = float(duration) if duration else 0.0
        self._voice_waveform = waveform or ""

    def to_dict(self, index: int) -> dict[str, Any]:
        d = super().to_dict(index)
        if self._voice_duration > 0:
            d["duration_secs"] = round(self._voice_duration, 3)
        if self._voice_waveform:
            d["waveform"] = self._voice_waveform
        return d


# =============================================================================
# Common Helpers
# =============================================================================

def _resolve_api_key() -> str | None:
    """Resolve credential preferring fresh OAuth token."""
    if get_grok_bearer:
        try:
            tok = get_grok_bearer()
            if tok:
                return tok
        except Exception:
            pass
    return (
        os.getenv("XAI_API_KEY")
        or getattr(settings, "xai_api_key", None)
    )


# --- Text preparation / enhancement for TTS (cleaning + Spanish-friendly) ---

def _clean_text_for_tts(text: str) -> str:
    """
    Prepare text for TTS:
    - Remove code blocks, markdown artifacts, excessive punctuation.
    - Replace URLs and long technical strings with readable placeholders.
    - Normalize whitespace.
    - Truncate very long inputs with a note (TTS APIs have practical limits ~4k chars).
    - Keep natural Spanish flow.
    """
    if not text:
        return ""

    t = text.strip()

    # Remove fenced code blocks entirely (they sound terrible in TTS)
    t = re.sub(r'```[\s\S]*?```', ' [código omitido] ', t, flags=re.MULTILINE)

    # Remove inline code
    t = re.sub(r'`([^`]+)`', r'\1', t)

    # Replace URLs with placeholder (saying "https colon slash..." is useless)
    t = re.sub(r'https?://\S+', ' [enlace] ', t)
    t = re.sub(r'www\.\S+', ' [sitio web] ', t)

    # Strip common markdown / discord formatting that pollutes speech.
    # CRITICAL: do NOT strip [ ] < > | because xAI TTS supports speech tags: [pause], <whisper>text</whisper>, etc.
    t = re.sub(r'[*_~#`]', ' ', t)
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)  # markdown links -> text
    # Also strip bold/italic markers that sometimes leak as ** or __ (already covered) and lone > for quotes
    t = re.sub(r'\s+', ' ', t)  # re-collapse early after strip

    # Collapse whitespace
    t = ' '.join(t.split())

    # Truncate for TTS safety (many engines ~4096 char limit; we are conservative)
    MAX_TTS_CHARS = 3200
    if len(t) > MAX_TTS_CHARS:
        # Try to cut at sentence boundary
        cut = t[:MAX_TTS_CHARS]
        last_period = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'), cut.rfind('\n'))
        if last_period > MAX_TTS_CHARS * 0.7:
            t = cut[:last_period + 1]
        else:
            t = cut
        t = t.rstrip() + " ... (texto truncado para audio)"

    return t.strip()


def _enhance_text_for_tts(text: str) -> str:
    """
    Light enhancement for natural speech (runs after cleaning).
    - Adds subtle pauses for long sentences if helpful (SSML not used here for simplicity).
    - Keeps Spanish pronunciation in mind (API should handle "ñ", accents, etc. well).
    - This is "enhancement", not rewriting the meaning.
    """
    if not text:
        return text

    t = text

    # Very light: ensure ends with punctuation for better prosody
    if t and t[-1] not in '.!?':
        t += '.'

    # Normalize common Spanish speech things (optional, non-destructive)
    # e.g. keep numbers as words? No, modern TTS handles "2026" fine.

    return t


def _prepare_text_for_tts(raw_text: str) -> str:
    """Full preparation pipeline for TTS."""
    cleaned = _clean_text_for_tts(raw_text)
    enhanced = _enhance_text_for_tts(cleaned)
    return enhanced


def _generate_waveform(segment: "AudioSegment", num_points: int = 256) -> str:
    """
    Generate a real waveform from the audio segment for Discord voice message UI.
    This makes the attachment render with the nice waveform bar + scrubber
    (exactly like user-recorded voice messages or how Hermes delivered TTS audio).
    """
    if AudioSegment is None or len(segment) == 0 or num_points <= 0:
        # Fallback flat-ish waveform
        return base64.b64encode(b"\x80" * num_points).decode("ascii")

    try:
        # Work with mono for simplicity
        mono = segment.set_channels(1)
        # Get raw samples (signed 16-bit usually)
        samples = mono.get_array_of_samples()
        if not samples:
            return base64.b64encode(b"\x80" * num_points).decode("ascii")

        chunk_size = max(1, len(samples) // num_points)
        waveform_bytes = bytearray()

        for i in range(num_points):
            start = i * chunk_size
            end = min(start + chunk_size, len(samples))
            chunk = samples[start:end]
            if chunk:
                # Peak absolute amplitude in this window
                peak = max(abs(int(s)) for s in chunk)
                # Normalize (AudioSegment 16-bit -> ~32768 max)
                normalized = int((peak / 32768.0) * 255)
                waveform_bytes.append(max(0, min(255, normalized)))
            else:
                waveform_bytes.append(128)

        return base64.b64encode(bytes(waveform_bytes)).decode("ascii")
    except Exception:
        # Any decoding issue -> safe fallback
        return base64.b64encode(b"\x80" * num_points).decode("ascii")


# =============================================================================
# Audio Schema
# =============================================================================

def _generate_audio_schema() -> dict:
    """Generate the TTS tool schema. Defaults are documented; runtime resolution
    in the handler pulls tts_default_* from settings (web-configurable)."""
    # Pull configured defaults for better schema (LLM sees the active defaults)
    try:
        from ..config import settings as _s
        _voice_def = getattr(_s, "tts_default_voice", "eve") or "eve"
        _lang_def = getattr(_s, "tts_default_language", "es") or "es"
    except Exception:
        _voice_def, _lang_def = "eve", "es"

    return {
        "type": "function",
        "name": "generate_audio",
        "description": (
            "Generates spoken audio (TTS / text-to-speech) from input text using the official xAI TTS API. "
            "Useful for explicit user requests to read content aloud, produce voice output, TTS, 'léelo en voz alta', 'dilo', 'genera audio', etc. "
            "Supports multiple voices (eve energetic default, ara warm, rex professional, sal balanced, leo authoritative) and languages via BCP-47 codes. "
            "Language parameter is required by the API."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "El texto que se debe convertir en audio / voz. Puede ser un párrafo o mensaje completo. Soporta speech tags como [pause] o <whisper>texto</whisper>."
                },
                "voice": {
                    "type": "string",
                    "description": "ID de voz (eve, ara, rex, sal, leo). Por defecto el configurado (eve recomendado para español).",
                    "default": _voice_def
                },
                "language": {
                    "type": "string",
                    "description": "Código BCP-47 del idioma (ej: 'es', 'es-ES', 'es-MX', 'en', 'auto' para detección). Requerido por la API de xAI. Por defecto 'es'.",
                    "default": _lang_def
                },
                "speed": {
                    "type": "number",
                    "description": "Velocidad de habla (0.7 a 1.5). 1.0 = normal.",
                    "default": 1.0
                }
            },
            "required": ["prompt"]
        }
    }


# =============================================================================
# Core Audio Tool
# =============================================================================

async def _tool_generate_audio(
    text: str,
    voice: str = "eve",
    language: str = "es",
    speed: float = 1.0,
    request_id: Optional[str] = None,
    **extra_params: Any,
) -> str:
    """
    Genera audio a partir de texto usando el endpoint oficial de TTS de xAI (/v1/tts).

    - Limpia y prepara el texto (quita código, urls, markdown, trunca si es muy largo; preserva speech tags).
    - Usa parámetros correctos: text, voice_id, language (obligatorio), speed (0.7-1.5), output_format.
    - Direct delivery as a playable audio attachment (reusing the media request tracker).
    - Unified delivery for all audio requests (whether the user said "tts", "genera audio", etc.).
      The spoken text is surfaced in the reply when practical + the custom voice file is attached.
    - Robust error handling + retries. Spanish user messages.
    """
    api_key = _resolve_api_key()
    if not api_key:
        return "No hay credencial de xAI configurada para generar audio (usa --login-oauth o XAI_API_KEY)."

    prepared_text = _prepare_text_for_tts(text)
    if not prepared_text:
        return "No hay texto válido para convertir a audio."

    # Resolver defaults desde config si el caller no pasó valores (fallback defensivo)
    if not voice:
        voice = "eve"
    if not language:
        language = "es"

    payload: dict[str, Any] = {
        "text": prepared_text,
        "voice_id": voice,
        "language": language,
    }
    if speed and abs(float(speed) - 1.0) > 0.001:
        clamped = max(0.7, min(1.5, float(speed)))
        payload["speed"] = clamped

    # Always request MP3 from xAI for reliable bytes.
    # We will transcode to proper OGG/Opus + real waveform client-side using pydub/ffmpeg
    # so it renders as a native Discord voice message (waveform bar) like Hermes used to do.
    payload["output_format"] = {"codec": "mp3", "sample_rate": 24000, "bit_rate": 128000}

    # Pasar params avanzados/futuros soportados por la API (sin sobrescribir los principales)
    for k in ("optimize_streaming_latency", "text_normalization"):
        if k in extra_params and extra_params[k] is not None:
            payload[k] = extra_params[k]

    max_attempts = getattr(settings, "api_max_retries", 3)

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=getattr(settings, "api_timeout_seconds", 60.0)) as http_client:
                response = await http_client.post(
                    "https://api.x.ai/v1/tts",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code != 200:
                    # Error handling
                    err_msg = "desconocido"
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            err_obj = data.get("error", {}) or {}
                            if isinstance(err_obj, dict):
                                err_msg = str(err_obj.get("message", "") or data.get("message", ""))[:300]
                            else:
                                err_msg = str(err_obj)[:300]
                    except Exception:
                        err_msg = (response.text or "")[:300]

                    is_transient = response.status_code in (429, 500, 502, 503, 504)
                    if is_transient and attempt < max_attempts - 1:
                        delay = 0.5 * (2 ** attempt)
                        logger.info(f"{cid_prefix()}[Audio] Transient error (status {response.status_code}), retrying in {delay:.1f}s")
                        await asyncio.sleep(delay)
                        continue

                    # Non-retryable or final
                    if "rate" in err_msg.lower() or response.status_code == 429:
                        return "Se ha alcanzado el límite de generación de audio por ahora. Intenta más tarde."
                    return f"No se pudo generar el audio: {err_msg or 'error del servicio'}"

                # Success: audio bytes directly (raw MP3 etc.)
                audio_bytes = response.content
                if not audio_bytes or len(audio_bytes) < 100:
                    return "El servicio devolvió audio vacío. Intenta con un texto más corto."

                logger.info(f"{cid_prefix()}[Audio] TTS generation successful, size={len(audio_bytes)} bytes")

                # === Direct delivery with attachment (preferred path) ===
                if request_id:
                    info = await consume_image_request(request_id)
                    if info:
                        orig_msg = info.get("original_message")
                        if orig_msg:
                            try:
                                voiced_text = prepared_text

                                # Deliver the spoken text + a proper voice message attachment so Discord
                                # shows the waveform bubble UI (like user voice messages) instead of a
                                # regular playable file attachment. We convert xAI's MP3 to Opus OGG
                                # (required for voice messages) + compute waveform + set the voice flag.
                                delivery_text = voiced_text

                                if len(voiced_text) > 400:
                                    delivery_text = voiced_text[:400].rsplit(" ", 1)[0] + "…"
                                    if "truncado" in voiced_text.lower():
                                        delivery_text += " (texto truncado)"

                                # === Voice message delivery (bubble UI) ===
                                # We force MP3 from xAI, then transcode via pydub/ffmpeg to OGG/Opus.
                                # We also generate a real waveform and set the IS_VOICE_MESSAGE flag.
                                # This is what produces the nice waveform bar + player (instead of attachment).
                                # We ALWAYS prefer this path over plain MP3 when conversion succeeds.
                                ogg_data = None
                                duration = 0.0
                                waveform = ""
                                if AudioSegment is not None:
                                    try:
                                        seg = AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
                                        duration = len(seg) / 1000.0

                                        ogg_bio = BytesIO()
                                        seg.export(ogg_bio, format="ogg", codec="libopus", bitrate="128k")
                                        ogg_data = ogg_bio.getvalue()

                                        waveform = _generate_waveform(seg)
                                    except Exception as conv_err:
                                        # Most common cause on Windows: ffmpeg not installed or not in PATH.
                                        # pydub needs the ffmpeg binary to transcode to libopus.
                                        # In Docker it's pre-installed; on dev machines you usually need:
                                        #   winget install ffmpeg   (Windows)
                                        #   or https://www.gyan.dev/ffmpeg/builds/  (add bin/ to PATH)
                                        logger.warning(
                                            f"{cid_prefix()}[AudioDelivery] Opus/OGG conversion failed (ffmpeg/pydub issue?), will fallback to MP3 attachment: {conv_err}"
                                        )

                                audio_attached = False
                                if ogg_data is not None:
                                    # Send as .ogg (Opus) + voice message flag + attachment metadata.
                                    # This is what makes Discord render the native waveform "bubble" UI
                                    # (inline player with scrubber, like real voice messages) instead of
                                    # a boring file attachment download.
                                    f = _VoiceMessageFile(
                                        BytesIO(ogg_data),
                                        filename="voice-message.ogg",
                                        duration=duration,
                                        waveform=waveform,
                                    )

                                    flags = discord.MessageFlags(voice=True)

                                    # Strong diagnostic logging so we can see in container logs
                                    # exactly what is being sent to Discord for the voice message.
                                    try:
                                        att = f.to_dict(0)
                                        logger.info(
                                            f"{cid_prefix()}[AudioDelivery] Preparing voice message | "
                                            f"flag=0x{flags.value:x} (voice={bool(flags.voice)}) | "
                                            f"attachment_keys={list(att.keys())} | "
                                            f"duration_secs={att.get('duration_secs')} | "
                                            f"has_waveform={'waveform' in att}"
                                        )
                                    except Exception as log_err:
                                        logger.debug(f"{cid_prefix()}[AudioDelivery] payload log failed: {log_err}")

                                    # Use low-level path as primary for voice messages (reliable way to set the flag).
                                    # Even on discord.py 2.7.1 in the container, high-level reply(..., flags=...) 
                                    # was raising "unexpected keyword argument 'flags'".
                                    # Low-level (handle_message_parameters + direct http) is what actually works
                                    # for proper voice message bubbles.
                                    voice_sent = False
                                    send_method = "none"

                                    channel = getattr(orig_msg, "channel", None)
                                    is_interaction = isinstance(orig_msg, discord.Interaction)

                                    if handle_message_parameters is not None and channel is not None:
                                        try:
                                            message_reference: dict[str, str] | None = None
                                            ch_id = getattr(channel, "id", None)
                                            if not is_interaction and ch_id:
                                                # Only real messages get a reply reference (threads the voice bubble under request).
                                                # For slash /audio (Interaction), we send top-level in channel (appears after command use).
                                                message_reference = {
                                                    "message_id": str(getattr(orig_msg, "id", "")),
                                                    "channel_id": str(ch_id),
                                                }
                                                if getattr(orig_msg, "guild", None) and orig_msg.guild is not None:
                                                    message_reference["guild_id"] = str(orig_msg.guild.id)

                                            am = AllowedMentions(replied_user=False) if AllowedMentions else None

                                            # IMPORTANT: For real Discord voice messages (the waveform bubble),
                                            # you MUST NOT include any text content when the voice flag is set.
                                            # Including content triggers Discord error 50159:
                                            # "Voice messages do not support additional content"
                                            # We send a pure voice message (just the attachment + flag).
                                            # The spoken text context lives in the parent message (the user's request).
                                            params = handle_message_parameters(
                                                content=None,
                                                file=f,
                                                flags=flags,
                                                message_reference=message_reference,
                                                allowed_mentions=am,
                                            )

                                            await channel._state.http.send_message(
                                                channel_id=ch_id,
                                                params=params,
                                            )
                                            voice_sent = True
                                            send_method = "lowlevel"
                                        except Exception as low_err:
                                            logger.warning(
                                                f"{cid_prefix()}[AudioDelivery] Low-level voice message send failed: {low_err}. "
                                                "Falling back to channel send."
                                            )

                                    if not voice_sent and channel is not None:
                                        try:
                                            # Re-create File for fallback (previous may have been read/consumed)
                                            f2 = _VoiceMessageFile(
                                                BytesIO(ogg_data),
                                                filename="voice-message.ogg",
                                                duration=duration,
                                                waveform=waveform,
                                            )
                                            # Interaction (slash) or message: public channel.send so voice appears in channel.
                                            # (lowlevel path already handled reply-ref for real messages when possible)
                                            await channel.send(file=f2)
                                            voice_sent = True
                                            send_method = "channel-send" if is_interaction else "highlevel-no-flags"
                                        except Exception as fb_err:
                                            logger.warning(
                                                f"{cid_prefix()}[AudioDelivery] Channel send fallback also failed: {fb_err}"
                                            )

                                    if voice_sent:
                                        logger.info(
                                            f"{cid_prefix()}[AudioDelivery] Sent as voice-message.ogg "
                                            f"(duration={duration:.1f}s, has_waveform={bool(waveform)}, method={send_method})"
                                        )
                                        audio_attached = True
                                    else:
                                        # Last resort: send the text so the user knows something happened.
                                        try:
                                            if channel:
                                                await channel.send(delivery_text)
                                            else:
                                                await orig_msg.reply(delivery_text, mention_author=False)
                                        except Exception:
                                            pass
                                        logger.warning(
                                            f"{cid_prefix()}[AudioDelivery] Could not attach audio at all for request {request_id}"
                                        )
                                else:
                                    # Absolute last resort only if we couldn't produce OGG at all.
                                    bio = BytesIO(audio_bytes)
                                    bio.name = "audio.mp3"
                                    channel = getattr(orig_msg, "channel", None)
                                    is_interaction = isinstance(orig_msg, discord.Interaction)
                                    if channel and (is_interaction or not hasattr(orig_msg, "reply")):
                                        await channel.send(
                                            delivery_text,
                                            file=discord.File(bio, filename="audio.mp3")
                                        )
                                    else:
                                        await orig_msg.reply(
                                            delivery_text,
                                            mention_author=False,
                                            file=discord.File(bio, filename="audio.mp3")
                                        )
                                    logger.info(f"{cid_prefix()}[AudioDelivery] Sent as audio.mp3 (no OGG conversion available)")
                                    audio_attached = True

                                # Log to channel context (same pattern as other media)
                                try:
                                    ch = getattr(orig_msg, "channel", None)
                                    ch_id = getattr(ch, "id", None) if ch else None
                                    if ch_id:
                                        from .. import context as ctx
                                        ctx.update_from_message(
                                            channel_id=ch_id,
                                            user_id=0,
                                            author_name="Groksito",
                                            content=voiced_text,
                                            is_bot=True,
                                        )
                                except Exception:
                                    pass

                                # Only claim direct delivery success (which suppresses the LLM's final text reply
                                # and prevents duplicate messages) when we actually attached audio.
                                if audio_attached:
                                    logger.info(f"{cid_prefix()}[AudioDelivery] Direct audio delivery successful for request {request_id}")
                                    # Local/lazy import (not top-level) to break the startup circular import:
                                    # discord/client.py (eager for /audio) → audio_handler → llm.prompt_builder
                                    # → llm chain → media_tools → back to audio_handler (schema).
                                    # Mirrors defensive local imports already used in this file + conversation.py.
                                    from ..llm.prompt_builder import DIRECT_DELIVERY_SUCCESS_AUDIO
                                    return DIRECT_DELIVERY_SUCCESS_AUDIO

                                # If we only managed to send a text note (very rare), fall through so the
                                # generic fallback string is returned and the model can respond naturally.

                            except Exception as send_err:
                                logger.warning(f"{cid_prefix()}[AudioDelivery] Failed direct audio reply for {request_id}: {send_err}")
                                # Try one last time with just the text (no file) so the user at least gets
                                # a reply instead of total silence on the audio request.
                                try:
                                    channel = getattr(orig_msg, "channel", None)
                                    if channel and isinstance(orig_msg, discord.Interaction):
                                        await channel.send(delivery_text)
                                    else:
                                        await orig_msg.reply(delivery_text, mention_author=False)
                                except Exception:
                                    pass
                                # fall through to fallback return below

                # Fallback (rare): return a message the model can use.
                # The LLM will usually turn this into a friendly note.
                # We prefer the model to say something natural rather than us forcing a second message.
                return "Audio generado correctamente. (No se pudo adjuntar directamente en esta ocasión. Intenta de nuevo si quieres otra toma.)"

        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as net_err:
            if attempt < max_attempts - 1:
                delay = 0.6 * (2 ** attempt)
                logger.info(f"{cid_prefix()}[Audio] Transient network error on attempt {attempt+1}: {type(net_err).__name__} — retry in {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            return f"Error generando audio por problema de red después de reintentos: {type(net_err).__name__}."

        except Exception as e:
            logger.exception(f"{cid_prefix()}[Audio] Unexpected error during TTS generation")
            return f"Error generando el audio: {str(e)}"

    return "No se pudo generar el audio después de varios intentos. Intenta de nuevo más tarde."


# (Audio delivery is now unified — no more separate "tts utterance" vs "generate audio" branching.
# All generate_audio calls use the same clean media-style delivery with the spoken text surfaced
# when reasonable + the custom voice audio attached.)


# =============================================================================
# Dispatch Handler (stable API for tools.py)
# =============================================================================

async def _handle_generate_audio(args: dict, original_message: Any) -> str:
    """
    Public handler called from execute_hybrid_tool.

    Registers the request for direct delivery (with audio attachment) and
    delegates to the core tool.
    Resolves voice/language from args (LLM-provided) or falls back to
    tts_default_* settings loaded from .env (configurable via web dashboard).

    Audio delivery is now unified: always the same nice generated-audio UX
    (spoken text surfaced in the message when practical + custom voice MP3 attached).
    """
    from ..config import settings as _settings  # local import to avoid any edge cycles

    text = args.get("prompt", "") or args.get("text", "")
    # Resolver defaults configurables (web dashboard) con fallbacks seguros
    voice = args.get("voice") or getattr(_settings, "tts_default_voice", "eve") or "eve"
    language = args.get("language") or getattr(_settings, "tts_default_language", "es") or "es"
    speed = float(args.get("speed", 1.0))

    request_id = None
    if original_message:
        try:
            uid = getattr(getattr(original_message, "author", None), "id", 0)
            mid = getattr(original_message, "id", 0)
            request_id = await register_image_request(
                user_id=uid,
                channel_id=getattr(getattr(original_message, "channel", None), "id", 0) or 0,
                message_id=mid,
                operation_type="audio",
                original_message=original_message,
            )
        except Exception as reg_err:
            logger.warning(f"{cid_prefix()}[Audio] Failed to register audio request: {reg_err}")

    return await _tool_generate_audio(
        text,
        voice=voice,
        language=language,
        speed=speed,
        request_id=request_id,
        **{k: v for k, v in args.items() if k not in ("prompt", "text", "voice", "language", "speed")}
    )


# =============================================================================
# Slash Command Support (reuses 100% of core TTS + delivery logic)
# =============================================================================

XAI_TTS_DOCS_URL = "https://docs.x.ai/developers/model-capabilities/audio/text-to-speech"

# xAI wrapping speech tags exposed as the optional /audio `estilo` slash parameter.
AUDIO_WRAPPING_TAGS: tuple[tuple[str, str], ...] = (
    ("Whisper", "whisper"),
("Soft", "soft"),
("Loud", "loud"),
("More intensity", "build-intensity"),
("Less intensity", "decrease-intensity"),
("Higher pitch", "higher-pitch"),
("Lower pitch", "lower-pitch"),
("Slow", "slow"),
("Fast", "fast"),
("Singing", "singing"),
("Sing-song", "sing-song"),
("Laugh while speaking", "laugh-speak"),
("Emphasis", "emphasis"),
)


def apply_wrapping_speech_tag(text: str, tag: str | None) -> str:
    """Wrap prepared text with an xAI wrapping speech tag when `estilo` is selected."""
    if not tag or not text.strip():
        return text
    clean_tag = tag.strip().strip("<>/")
    if not clean_tag:
        return text
    return f"<{clean_tag}>{text}</{clean_tag}>"


def build_audio_speech_tags_embed() -> discord.Embed:
    """Brief /audio usage help when invoked without text or a replied message."""
    embed = discord.Embed(
        title="🔊 /audio — Text-to-Speech",
        url=XAI_TTS_DOCS_URL,
        description=(
            "Escribe el **texto** a leer o **responde a un mensaje** y ejecuta `/audio`.\n\n"
            "• **Inline tags** van dentro del texto (ver descripción del parámetro `texto`).\n"
            "• **Estilo envolvente** se elige en el parámetro `estilo` (whisper, soft, slow, etc.).\n"
            "• **Voz** opcional: eve, ara, rex, sal, leo."
        ),
        color=0x5865F2,
    )
    embed.set_footer(text="Documentación xAI TTS · Speech Tags")
    return embed


async def prepare_text_from_interaction(
    interaction: discord.Interaction, provided_text: str = ""
) -> str:
    """
    Build final text for the /audio slash command, with reply-to-message support.

    - If no provided_text and the invocation carries a message reference (user
      replied to a message then ran the slash), fetch and use the replied content.
    - If both text and reply: combine naturally as "<text> [reading the message] <replied>".
    - Returns stripped text (core _prepare_text_for_tts will still clean markdown/tags
      and enforce length).
    - Never raises; falls back gracefully so slash stays robust.
    """
    final_text = (provided_text or "").strip()

    replied_message = None
    try:
        msg_ref = None
        if getattr(interaction, "message", None) and getattr(interaction.message, "reference", None):
            msg_ref = interaction.message.reference
        if msg_ref and getattr(msg_ref, "message_id", None):
            ch = getattr(interaction, "channel", None)
            if ch and hasattr(ch, "fetch_message"):
                replied_message = await ch.fetch_message(msg_ref.message_id)
    except Exception:
        replied_message = None

    if replied_message and getattr(replied_message, "content", None):
        replied_content = (replied_message.content or "").strip()
        if replied_content:
            if not final_text:
                final_text = replied_content
            else:
                final_text = f"{final_text} [reading the message] {replied_content}"

    return final_text


# Lazy module-level re-export via __getattr__.
# This lets tests (e.g. test_guidance_centralization) and direct attribute access
# like `audio_handler.DIRECT_DELIVERY_SUCCESS_AUDIO` continue to work *without*
# a top-level `from ..llm.prompt_builder import ...` that would trigger the
# circular import during early loading of discord/client.py (for /audio slash).
# The actual constant lives in prompt_builder; we fetch it only on first access
# (after full module initialization).
def __getattr__(name: str):
    if name == "DIRECT_DELIVERY_SUCCESS_AUDIO":
        from ..llm.prompt_builder import DIRECT_DELIVERY_SUCCESS_AUDIO
        return DIRECT_DELIVERY_SUCCESS_AUDIO
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
