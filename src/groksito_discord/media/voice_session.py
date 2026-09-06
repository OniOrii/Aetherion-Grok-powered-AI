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
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

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
DEFAULT_VOICE = "ara"

_WAKE_RE = re.compile(
    r"\b(aetherion|aetherian|atherion|atheerion|etherion|ethereon|aetherium|aethereon|aetheron|atheron|atheon|atheorian|atheorion|theorion|athena|thea|iryan)\b|a\s+theory(?:\s+on)?",
    re.IGNORECASE,
)
