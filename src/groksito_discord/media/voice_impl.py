from __future__ import annotations
import audioop, asyncio, io, logging, os, re, struct, tempfile, time, wave
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import discord
import httpx
from ..config import settings
from .voice_music import handle_music, start_playback
logger = logging.getLogger('groksito.voice_session')
DISCORD_RATE = 48000
STT_RATE = 16000
SILENCE_S = 0.35
MIN_SPEECH_S = 0.25
MAX_SPEECH_S = 8.0
RMS_THRESHOLD = 120
DEFAULT_VOICE = 'ara'
_WAKE_RE = re.compile(r'\b(aetherion|aetherian|atherion|atherian|atheerion|etherion|ethereon|aetherium|aethereon|aetheron|atheron|atheon|atheorian|atheorion|theorion|athena|thea|iryan)\b|a\s+theory(?:\s+on)?', re.IGNORECASE)
_CITE_RE = re.compile(r'https?://\S+|www\.\S+|\[\s*\d+\s*\]\s*\([^)]*\)|\[\s*\d+\s*\]', re.IGNORECASE)

def _wake_and_prompt(text: str):
    if not _WAKE_RE.search(text or ''):
        return None
    cleaned = _WAKE_RE.sub(' ', text)
    cleaned = re.sub(r'[\s,.:;!?]+', ' ', cleaned).strip()
    return cleaned or 'yes'

def _speakable(text: str) -> str:
    cleaned = _CITE_RE.sub(' ', text or '')
    return re.sub(r'\s+', ' ', cleaned).strip(' \t\n.,;:-[]()')

try:
    import nacl.secret
except Exception:
    nacl = None
try:
    import davey
except Exception:
    davey = None

def _api_key():
    return getattr(settings, 'xai_api_key', None) or os.environ.get('XAI_API_KEY')

def _now_detroit() -> str:
    return datetime.now(ZoneInfo('America/Detroit')).strftime('%A, %B %d, %Y, %I:%M %p %Z')

def _extract_response_text(data: dict[str, Any]) -> str:
    chunks = []
    for item in data.get('output') or []:
        if not isinstance(item, dict):
            continue
        if item.get('type') == 'message':
            for part in item.get('content') or []:
                if isinstance(part, dict) and part.get('type') in ('output_text', 'text'):
                    t = (part.get('text') or '').strip()
                    if t:
                        chunks.append(t)
        elif item.get('type') == 'output_text':
            t = (item.get('text') or '').strip()
            if t:
                chunks.append(t)
    return ' '.join(chunks).strip() or (data.get('output_text') or '').strip()

def _wav_bytes(pcm16_mono: bytes, rate: int = STT_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate); wf.writeframes(pcm16_mono)
    return buf.getvalue()

def _pcm48_stereo_to_16_mono(pcm: bytes) -> bytes:
    if not pcm or len(pcm) % 2:
        return b''
    mono = audioop.tomono(pcm, 2, 1.0, 1.0) if len(pcm) % 4 == 0 else pcm
    down, _state = audioop.ratecv(mono, 2, 1, DISCORD_RATE, STT_RATE, None)
    return down
