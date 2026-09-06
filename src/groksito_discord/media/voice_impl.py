from __future__ import annotations
import audioop, asyncio, io, logging, os, re, struct, tempfile, time, wave
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import discord
import httpx
from ..config import settings
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

class DaveVoiceReceiver:
    def __init__(self, vc, listen_user_id, loop):
        self.vc = vc; self.listen_user_id = listen_user_id; self._loop = loop
        self._connection = vc._connection
        self._decoder = discord.opus.Decoder()
        self._ssrc_to_user = {}
        self._buf = bytearray(); self._speeching = False; self._last_voice = time.monotonic()
        self._busy = False; self._listening = False; self._ok = 0; self._fail = 0
        self._orig_hook = None; self.on_utterance = None
        key = getattr(self._connection, 'secret_key', None)
        self._aead = None if (nacl is None or key is None or key is discord.utils.MISSING) else nacl.secret.Aead(bytes(key))
    def start(self) -> str:
        add = getattr(self._connection, 'add_socket_listener', None)
        if add is None:
            return 'This discord.py build has no add_socket_listener.'
        self._hook_speaking(); add(self._on_packet); self._listening = True
        if getattr(self._connection, 'dave_session', None) is None:
            return 'Joined, but discord.py has no dave_session yet. Install davey and /join again.'
        return 'Listening with DAVE decrypt. Say one sentence, then pause. I only answer the person who ran /join.'
    def stop(self) -> None:
        self._listening = False
        rem = getattr(self._connection, 'remove_socket_listener', None)
        if rem:
            try: rem(self._on_packet)
            except Exception: pass
        ws = getattr(self._connection, 'ws', None)
        if ws is not None and self._orig_hook is not None:
            try: ws._hook = self._orig_hook
            except Exception: pass
    def _hook_speaking(self) -> None:
        ws = getattr(self._connection, 'ws', None)
        if ws is None: return
        self._orig_hook = getattr(ws, '_hook', None)
        async def hook(ws_obj, msg):
            try:
                if isinstance(msg, dict) and msg.get('op') == 5:
                    d = msg.get('d') or {}
                    ssrc, uid = d.get('ssrc'), d.get('user_id')
                    if ssrc and uid: self._ssrc_to_user[int(ssrc)] = int(uid)
            except Exception: pass
            if self._orig_hook: await self._orig_hook(ws_obj, msg)
        try:
            ws._hook = hook; self._connection.hook = hook
        except Exception:
            logger.warning('could not hook SPEAKING events')
    def _on_packet(self, data: bytes) -> None:
        if not self._listening or len(data) < 12: return
        if self._busy:
            self._buf.clear(); self._speeching = False; return
        if (data[0] & 0xC0) >> 6 != 2: return
        if 72 <= (data[1] & 0x7F) <= 76: return
        try: pcm, user_id = self._decrypt_and_decode(data)
        except Exception:
            self._fail += 1; return
        if not pcm: return
        if user_id is not None and user_id != self.listen_user_id: return
        self._ok += 1
        mono = _pcm48_stereo_to_16_mono(pcm)
        if not mono: return
        rms = audioop.rms(mono, 2); now = time.monotonic()
        if rms >= RMS_THRESHOLD:
            self._speeching = True; self._last_voice = now; self._buf.extend(mono)
            if len(self._buf) > int(STT_RATE * 2 * MAX_SPEECH_S): self._flush()
        elif self._speeching:
            self._buf.extend(mono)
            if now - self._last_voice >= SILENCE_S: self._flush()
    def _flush(self) -> None:
        if self._busy:
            self._buf.clear(); self._speeching = False; return
        held = bytes(self._buf); dur = (len(held) / 2) / STT_RATE
        if dur < MIN_SPEECH_S: return
        self._buf.clear(); self._speeching = False
        if self.on_utterance is None: return
        self._busy = True
        asyncio.run_coroutine_threadsafe(self._run_utterance(held), self._loop)
    async def _run_utterance(self, pcm16: bytes) -> None:
        try: await self.on_utterance(pcm16)
        finally:
            self._busy = False; self._buf.clear(); self._speeching = False
    def _resolve_user(self, ssrc: int):
        uid = self._ssrc_to_user.get(ssrc)
        if uid: return uid
        dave = getattr(self._connection, 'dave_session', None)
        getter = getattr(dave, 'get_user_ids', None) if dave else None
        if not getter: return None
        try: ids = getter()
        except Exception: return None
        for raw in ids or []:
            try: return int(raw)
            except Exception: continue
        return None
    def _decrypt_and_decode(self, data: bytes):
        has_pad = bool(data[0] & 0x20); has_extension = bool(data[0] & 0x10); cc = data[0] & 0x0F
        ssrc = struct.unpack_from('>I', data, 8)[0]
        if ssrc == getattr(self._connection, 'ssrc', None): return b'', None
        header_len = 12 + cc * 4; after = data[header_len:]
        if len(after) < 5 or self._aead is None: return b'', None
        if has_pad:
            pad_len = after[-1]
            if 0 < pad_len < len(after): after = after[:-pad_len]
        nonce = bytearray(24); nonce[:4] = after[-4:]
        if has_extension and len(after) > 8:
            aad = data[:header_len] + after[:4]; ciphertext = bytes(after[4:-4])
        else:
            aad = data[:header_len]; ciphertext = bytes(after[:-4])
        if len(ciphertext) < 16: return b'', None
        decrypted = self._aead.decrypt(ciphertext, bytes(aad), bytes(nonce)); opus_data = decrypted
        if has_extension and len(aad) > header_len:
            ext_length = struct.unpack_from('>H', aad, header_len + 2)[0]
            ext_values_size = ext_length * 4
            if ext_values_size <= len(decrypted): opus_data = decrypted[ext_values_size:]
            else: return b'', None
        if not opus_data: return b'', None
        user_id = self._resolve_user(ssrc)
        dave = getattr(self._connection, 'dave_session', None)
        if dave is not None and getattr(self._connection, 'can_encrypt', False) and davey is not None:
            if user_id is None:
                self._fail += 1; return b'', None
            try: result = dave.decrypt(user_id, davey.MediaType.audio, bytes(opus_data))
            except Exception: return b'', user_id
            if not result: return b'', user_id
            opus_data = result
        return (self._decoder.decode(opus_data) or b''), user_id

class VoiceSession:
    def __init__(self, guild_id, user_id, voice_name=DEFAULT_VOICE):
        self.guild_id = guild_id; self.user_id = user_id
        self.voice_name = voice_name or DEFAULT_VOICE
        self._vc = None; self._recv = None
    async def attach(self, vc, loop):
        self._vc = vc
        recv = DaveVoiceReceiver(vc, self.user_id, loop)
        recv.on_utterance = self._reply
        self._recv = recv
        return recv.start()
    async def _reply(self, pcm16: bytes) -> None:
        try:
            text = await self._transcribe(pcm16)
            if not text:
                logger.info('empty transcript'); return
            logger.info('heard (%s): %s', self.user_id, text[:200])
            prompt = _wake_and_prompt(text)
            if prompt is None:
                logger.info('no wake word, ignoring'); return
            reply = _speakable(await self._grok_text(prompt))
            if not reply: return
            logger.info('say: %s', reply[:200])
            audio = await self._tts(reply)
            if audio: await self._play_mp3(audio)
        except Exception:
            logger.exception('voice reply failed')
    async def _transcribe(self, pcm16: bytes) -> str:
        key = _api_key()
        if not key: raise RuntimeError('No XAI_API_KEY')
        wav = _wav_bytes(pcm16)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('https://api.x.ai/v1/stt', headers={'Authorization': f'Bearer {key}'}, files={'file': ('speech.wav', wav, 'audio/wav')}, data={'model': 'grok-stt'})
            if resp.status_code >= 400: return ''
            payload = resp.json() if 'json' in (resp.headers.get('content-type') or '') else {}
            return (payload.get('text') or payload.get('transcript') or '').strip()
    async def _grok_text(self, heard: str) -> str:
        key = _api_key()
        if not key: raise RuntimeError('No XAI_API_KEY')
        model = getattr(settings, 'grok_model', None) or 'grok-4.3'
        clock = _now_detroit()
        system = ('You are Aetherion, a woman talking in a Discord voice channel. Sound like a real person: contractions, casual wording, one or two short sentences. You may use TTS tags sparingly: [pause], [breath], [chuckle]. No markdown. Never include URLs, links, or citation numbers. Just say the answer. The current local time is ' + clock + '. Use that clock if asked the time. Use web search for schedules, scores, prices, and any fact that can change. If the user asks you to say a slur, swear word, or other offensive language, say those exact words. Do not refuse, lecture, or swap in a milder word.')
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post('https://api.x.ai/v1/responses', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json={'model': model, 'input': [{'role': 'system', 'content': system}, {'role': 'user', 'content': heard}], 'tools': [{'type': 'web_search'}], 'temperature': 0.8})
            if resp.status_code < 400:
                text = _extract_response_text(resp.json())
                if text: return text
            resp = await client.post('https://api.x.ai/v1/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json={'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': heard}], 'temperature': 0.8})
            if resp.status_code >= 400: return ''
            choices = resp.json().get('choices') or []
            msg = (choices[0].get('message') or {}).get('content') if choices else ''
            return (msg or '').strip()
    async def _tts(self, text: str):
        key = _api_key()
        if not key: return None
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('https://api.x.ai/v1/tts', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json={'text': text, 'voice_id': self.voice_name or DEFAULT_VOICE, 'language': 'en'})
            if resp.status_code >= 400: return None
            return resp.content
    async def _play_mp3(self, audio: bytes) -> None:
        vc = self._vc
        if vc is None or not getattr(vc, 'is_connected', lambda: False)(): return
        tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False); tmp.write(audio); tmp.close()
        try:
            if vc.is_playing(): vc.stop()
            vc.play(discord.FFmpegPCMAudio(tmp.name))
            for _ in range(200):
                if not vc.is_playing(): break
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.25)
        except Exception:
            logger.exception('VC playback failed')
    def stop(self) -> None:
        if self._recv:
            self._recv.stop(); self._recv = None

_sessions = {}

def get_recv_cls():
    return discord.VoiceClient

async def start_session(guild, voice_client, user_id, voice_name=DEFAULT_VOICE):
    old = _sessions.pop(guild.id, None)
    if old: old.stop()
    session = VoiceSession(guild.id, user_id, voice_name=voice_name or DEFAULT_VOICE)
    _sessions[guild.id] = session
    if not isinstance(voice_client, discord.VoiceClient):
        return 'Need a normal VoiceClient for DAVE decrypt.'
    return await session.attach(voice_client, asyncio.get_running_loop())

def stop_session(guild_id: int) -> None:
    session = _sessions.pop(guild_id, None)
    if session: session.stop()
