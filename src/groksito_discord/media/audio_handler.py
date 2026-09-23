from __future__ import annotations
import asyncio, base64, logging, os, re
from io import BytesIO
from typing import Any, Optional
import httpx
import discord
try:
    from discord.http import handle_message_parameters
    from discord import AllowedMentions
except Exception:
    handle_message_parameters = None
    AllowedMentions = None
try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None
from ..utils.correlation import cid_prefix
from ..config import settings
from .delivery import consume_image_request, register_image_request
try:
    from ..core.grok_oauth import get_grok_bearer
except Exception:
    get_grok_bearer = None
logger = logging.getLogger("groksito.media.audio_handler")

class _VoiceMessageFile(discord.File):
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

def _resolve_api_key() -> str | None:
    if get_grok_bearer:
        try:
            tok = get_grok_bearer()
            if tok:
                return tok
        except Exception:
            pass
    return os.getenv("XAI_API_KEY") or getattr(settings, "xai_api_key", None)

def _clean_text_for_tts(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r'```[\s\S]*?```', ' [code omitted] ', t, flags=re.MULTILINE)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    t = re.sub(r'https?://\S+', ' [link] ', t)
    t = re.sub(r'www\.\S+', ' [website] ', t)
    t = re.sub(r'[*_~#`]', ' ', t)
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)
    t = ' '.join(t.split())
    MAX_TTS_CHARS = 3200
    if len(t) > MAX_TTS_CHARS:
        cut = t[:MAX_TTS_CHARS]
        last_period = max(cut.rfind('.'), cut.rfind('!'), cut.rfind('?'), cut.rfind('\n'))
        t = cut[:last_period + 1] if last_period > MAX_TTS_CHARS * 0.7 else cut
        t = t.rstrip() + " ... (text truncated for audio)"
    return t.strip()

def _enhance_text_for_tts(text: str) -> str:
    if not text:
        return text
    t = text
    if t and t[-1] not in '.!?':
        t += '.'
    return t

def _prepare_text_for_tts(raw_text: str) -> str:
    return _enhance_text_for_tts(_clean_text_for_tts(raw_text))

def _generate_waveform(segment, num_points: int = 256) -> str:
    if AudioSegment is None or len(segment) == 0 or num_points <= 0:
        return base64.b64encode(b"\x80" * num_points).decode("ascii")
    try:
        mono = segment.set_channels(1)
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
                peak = max(abs(int(s)) for s in chunk)
                waveform_bytes.append(max(0, min(255, int((peak / 32768.0) * 255))))
            else:
                waveform_bytes.append(128)
        return base64.b64encode(bytes(waveform_bytes)).decode("ascii")
    except Exception:
        return base64.b64encode(b"\x80" * num_points).decode("ascii")

def _generate_audio_schema() -> dict:
    try:
        from ..config import settings as _s
        _voice_def = getattr(_s, "tts_default_voice", "eve") or "eve"
        _lang_def = getattr(_s, "tts_default_language", "en") or "en"
    except Exception:
        _voice_def, _lang_def = "eve", "en"
    return {
        "type": "function",
        "name": "generate_audio",
        "description": "Generates spoken audio (TTS) from input text using the official xAI TTS API.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The text to convert into spoken audio."},
                "voice": {"type": "string", "description": "Voice id (eve, ara, rex, sal, leo).", "default": _voice_def},
                "language": {"type": "string", "description": "BCP-47 language code. Default en.", "default": _lang_def},
                "speed": {"type": "number", "description": "Speech speed 0.7 to 1.5.", "default": 1.0},
            },
            "required": ["prompt"],
        },
    }

async def _tool_generate_audio(text: str, voice: str = "eve", language: str = "en", speed: float = 1.0, request_id: Optional[str] = None, **extra_params: Any) -> str:
    api_key = _resolve_api_key()
    if not api_key:
        return "No xAI credential is configured for audio (use --login-oauth or XAI_API_KEY)."
    prepared_text = _prepare_text_for_tts(text)
    if not prepared_text:
        return "There is no valid text to convert to audio."
    if not voice:
        voice = "eve"
    if not language:
        language = "en"
    payload: dict[str, Any] = {"text": prepared_text, "voice_id": voice, "language": language}
    if speed and abs(float(speed) - 1.0) > 0.001:
        payload["speed"] = max(0.7, min(1.5, float(speed)))
    payload["output_format"] = {"codec": "mp3", "sample_rate": 24000, "bit_rate": 128000}
    for k in ("optimize_streaming_latency", "text_normalization"):
        if extra_params.get(k) is not None:
            payload[k] = extra_params[k]
    max_attempts = getattr(settings, "api_max_retries", 3)
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=getattr(settings, "api_timeout_seconds", 60.0)) as http_client:
                response = await http_client.post("https://api.x.ai/v1/tts", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload)
                if response.status_code != 200:
                    err_msg = "unknown"
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            err_obj = data.get("error", {}) or {}
                            err_msg = str((err_obj.get("message") if isinstance(err_obj, dict) else err_obj) or data.get("message") or "")[:300]
                    except Exception:
                        err_msg = (response.text or "")[:300]
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    if "rate" in err_msg.lower() or response.status_code == 429:
                        return "Audio generation is rate limited right now. Try again later."
                    return f"Could not generate the audio: {err_msg or 'service error'}"
                audio_bytes = response.content
                if not audio_bytes or len(audio_bytes) < 100:
                    return "The service returned empty audio. Try a shorter text."
                if request_id:
                    info = await consume_image_request(request_id)
                    if info:
                        orig_msg = info.get("original_message")
                        if orig_msg:
                            try:
                                voiced_text = prepared_text
                                delivery_text = voiced_text[:400].rsplit(" ", 1)[0] + "\u2026" if len(voiced_text) > 400 else voiced_text
                                if "truncat" in voiced_text.lower():
                                    delivery_text += " (text truncated)"
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
                                        logger.warning(f"{cid_prefix()}[AudioDelivery] Opus/OGG conversion failed: {conv_err}")
                                audio_attached = False
                                channel = getattr(orig_msg, "channel", None)
                                is_interaction = isinstance(orig_msg, discord.Interaction)
                                if ogg_data is not None:
                                    f = _VoiceMessageFile(BytesIO(ogg_data), filename="voice-message.ogg", duration=duration, waveform=waveform)
                                    flags = discord.MessageFlags(voice=True)
                                    voice_sent = False
                                    if handle_message_parameters is not None and channel is not None:
                                        try:
                                            message_reference = None
                                            ch_id = getattr(channel, "id", None)
                                            if not is_interaction and ch_id:
                                                message_reference = {"message_id": str(getattr(orig_msg, "id", "")), "channel_id": str(ch_id)}
                                                if getattr(orig_msg, "guild", None):
                                                    message_reference["guild_id"] = str(orig_msg.guild.id)
                                            am = AllowedMentions(replied_user=False) if AllowedMentions else None
                                            params = handle_message_parameters(content=None, file=f, flags=flags, message_reference=message_reference, allowed_mentions=am)
                                            await channel._state.http.send_message(channel_id=ch_id, params=params)
                                            voice_sent = True
                                        except Exception as low_err:
                                            logger.warning(f"{cid_prefix()}[AudioDelivery] Low-level voice send failed: {low_err}")
                                    if not voice_sent and channel is not None:
                                        try:
                                            f2 = _VoiceMessageFile(BytesIO(ogg_data), filename="voice-message.ogg", duration=duration, waveform=waveform)
                                            await channel.send(file=f2)
                                            voice_sent = True
                                        except Exception as fb_err:
                                            logger.warning(f"{cid_prefix()}[AudioDelivery] Channel send failed: {fb_err}")
                                    audio_attached = voice_sent
                                else:
                                    bio = BytesIO(audio_bytes)
                                    bio.name = "audio.mp3"
                                    if channel and (is_interaction or not hasattr(orig_msg, "reply")):
                                        await channel.send(delivery_text, file=discord.File(bio, filename="audio.mp3"))
                                    else:
                                        await orig_msg.reply(delivery_text, mention_author=False, file=discord.File(bio, filename="audio.mp3"))
                                    audio_attached = True
                                if audio_attached:
                                    from ..llm.prompt_builder import DIRECT_DELIVERY_SUCCESS_AUDIO
                                    return DIRECT_DELIVERY_SUCCESS_AUDIO
                            except Exception as send_err:
                                logger.warning(f"{cid_prefix()}[AudioDelivery] Failed: {send_err}")
                return "Audio generated. (Could not attach it directly this time. Try again if you want another take.)"
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as net_err:
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.6 * (2 ** attempt))
                continue
            return f"Network error generating audio after retries: {type(net_err).__name__}."
        except Exception as e:
            logger.exception(f"{cid_prefix()}[Audio] Unexpected error during TTS generation")
            return f"Error generating audio: {str(e)}"
    return "Could not generate the audio after several tries. Try again later."

async def _handle_generate_audio(args: dict, original_message: Any) -> str:
    from ..config import settings as _settings
    text = args.get("prompt", "") or args.get("text", "")
    voice = args.get("voice") or getattr(_settings, "tts_default_voice", "eve") or "eve"
    language = args.get("language") or getattr(_settings, "tts_default_language", "en") or "en"
    speed = float(args.get("speed", 1.0))
    request_id = None
    if original_message:
        try:
            uid = getattr(getattr(original_message, "author", None), "id", 0)
            mid = getattr(original_message, "id", 0)
            request_id = await register_image_request(user_id=uid, channel_id=getattr(getattr(original_message, "channel", None), "id", 0) or 0, message_id=mid, operation_type="audio", original_message=original_message)
        except Exception as reg_err:
            logger.warning(f"{cid_prefix()}[Audio] Failed to register audio request: {reg_err}")
    return await _tool_generate_audio(text, voice=voice, language=language, speed=speed, request_id=request_id, **{k: v for k, v in args.items() if k not in ("prompt", "text", "voice", "language", "speed")})

XAI_TTS_DOCS_URL = "https://docs.x.ai/developers/model-capabilities/audio/text-to-speech"
AUDIO_WRAPPING_TAGS = (("Whisper", "whisper"), ("Soft", "soft"), ("Loud", "loud"), ("More intensity", "build-intensity"), ("Less intensity", "decrease-intensity"), ("Higher pitch", "higher-pitch"), ("Lower pitch", "lower-pitch"), ("Slow", "slow"), ("Fast", "fast"), ("Singing", "singing"), ("Sing-song", "sing-song"), ("Laugh while speaking", "laugh-speak"), ("Emphasis", "emphasis"))

def apply_wrapping_speech_tag(text: str, tag: str | None) -> str:
    if not tag or not text.strip():
        return text
    clean_tag = tag.strip().strip("<>/")
    if not clean_tag:
        return text
    return f"<{clean_tag}>{text}</{clean_tag}>"

def build_audio_speech_tags_embed() -> discord.Embed:
    embed = discord.Embed(title="\U0001F50A /audio \u2014 Text-to-Speech", url=XAI_TTS_DOCS_URL, description=("Type the **text** to speak, or **reply to a message** and run `/audio`.\n\n" "\u2022 **Inline tags** go in the text (`[pause]`, `[laugh]`, `[sigh]`, etc.).\n" "\u2022 **Wrapping style** is the optional `style` option (whisper, soft, slow, etc.).\n" "\u2022 **Voice** is optional: zagan, eve, ara, rex, sal, leo."), color=0x5865F2)
    embed.set_footer(text="xAI TTS docs \u00b7 Speech tags")
    return embed

async def prepare_text_from_interaction(interaction: discord.Interaction, provided_text: str = "") -> str:
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
            final_text = replied_content if not final_text else f"{final_text} [reading the message] {replied_content}"
    return final_text

def __getattr__(name: str):
    if name == "DIRECT_DELIVERY_SUCCESS_AUDIO":
        from ..llm.prompt_builder import DIRECT_DELIVERY_SUCCESS_AUDIO
        return DIRECT_DELIVERY_SUCCESS_AUDIO
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
