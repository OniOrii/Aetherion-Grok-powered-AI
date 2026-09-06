"""Play/stop music on the same VoiceClient Aetherion already uses for TTS."""
from __future__ import annotations

import asyncio
import base64
import logging
import re
from pathlib import Path
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

last_error: str | None = None
_cookies_logged = False

# Anonymous clients first. Cookies often force SABR / tv_downgraded with no URL.
_ANON_CLIENTS: tuple[tuple[str, ...], ...] = (
    ("tv", "android_vr"),
    ("ios", "android"),
)
_COOKIE_CLIENTS: tuple[tuple[str, ...], ...] = (
    ("web_embedded", "android"),
    ("tv", "web_safari"),
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


def _normalize_netscape(text: str) -> str:
    out: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.strip() or line.lstrip().startswith("#") or "\t" in line:
            out.append(line)
            continue
        parts = re.split(r" {2,}", line.strip())
        if len(parts) >= 7:
            out.append("\t".join(parts))
        else:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"


def cookiefile_path() -> str | None:
    try:
        from ..config.settings import settings
    except Exception:
        return None
    dest = Path(getattr(settings, "data_dir", Path("./data"))) / "youtube_cookies.txt"
    raw = (getattr(settings, "youtube_cookies", None) or "").strip()
    b64 = (getattr(settings, "youtube_cookies_b64", None) or "").strip()
    try:
        if raw:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(_normalize_netscape(raw), encoding="utf-8")
            return str(dest)
        if b64:
            dest.parent.mkdir(parents=True, exist_ok=True)
            decoded = base64.b64decode(b64)
            try:
                dest.write_text(_normalize_netscape(decoded.decode("utf-8")), encoding="utf-8")
            except UnicodeDecodeError:
                dest.write_bytes(decoded)
            return str(dest)
    except Exception:
        logger.exception("failed to materialize YouTube cookies")
        return None
    path = getattr(settings, "youtube_cookies_file", None)
    if path:
        p = Path(path)
        if p.is_file():
            return str(p)
        logger.warning("YOUTUBE_COOKIES_FILE is set but missing: %s", p)
    return None


def _ydl_opts(
    player_clients: tuple[str, ...] | None = None,
    use_cookies: bool = True,
) -> dict[str, Any]:
    global _cookies_logged
    clients = list(player_clients or _ANON_CLIENTS[0])
    opts: dict[str, Any] = {
        "noplaylist": True,
        "default_search": "ytsearch1",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": clients}},
    }
    cookiefile = cookiefile_path() if use_cookies else None
    if cookiefile:
        opts["cookiefile"] = cookiefile
        if not _cookies_logged:
            logger.info("youtube cookies enabled")
            _cookies_logged = True
    elif not _cookies_logged and use_cookies:
        logger.info("youtube cookies not set; Railway IPs may get a bot check")
        _cookies_logged = True
    return opts


def _classify_extract_error(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "sign in to confirm" in msg or "not a bot" in msg:
        return "bot_check"
    if "page needs to be reloaded" in msg:
        return "reload_needed"
    if "requested format is not available" in msg:
        return "no_format"
    return "extract_failed"


def _pick_stream(info: dict[str, Any]) -> str:
    if info.get("url"):
        return str(info["url"])
    best = ""
    best_score = -1.0
    for fmt in info.get("formats") or []:
        url = fmt.get("url") or ""
        if not url:
            continue
        proto = str(fmt.get("protocol") or "")
        if "dash" in proto or "sabr" in proto or proto == "m3u8_native":
            continue
        if (fmt.get("acodec") or "none") == "none":
            continue
        score = float(fmt.get("abr") or fmt.get("tbr") or 0)
        if score >= best_score:
            best_score = score
            best = str(url)
    if best:
        return best
    for fmt in info.get("formats") or []:
        url = fmt.get("url") or ""
        if url:
            return str(url)
    return ""


def _attempts() -> list[tuple[bool, tuple[str, ...]]]:
    rows: list[tuple[bool, tuple[str, ...]]] = [(False, clients) for clients in _ANON_CLIENTS]
    if cookiefile_path():
        rows.extend((True, clients) for clients in _COOKIE_CLIENTS)
    return rows


def _extract_track(query: str) -> dict[str, str] | None:
    global last_error
    last_error = None
    try:
        import yt_dlp
    except Exception:
        logger.warning("yt-dlp is not installed")
        last_error = "yt_dlp_missing"
        return None

    last_exc: BaseException | None = None
    for use_cookies, clients in _attempts():
        try:
            with yt_dlp.YoutubeDL(_ydl_opts(clients, use_cookies=use_cookies)) as ydl:
                info = ydl.extract_info(query, download=False)
        except Exception as e:
            last_exc = e
            logger.warning(
                "yt-dlp %s cookies=%s clients=%s query=%s",
                _classify_extract_error(e),
                use_cookies,
                ",".join(clients),
                query[:80],
            )
            continue
        if not info:
            continue
        if "entries" in info:
            entries = [e for e in (info.get("entries") or []) if e]
            info = entries[0] if entries else None
        if not info:
            continue
        url = _pick_stream(info)
        title = (info.get("title") or query).strip()
        if not url:
            last_error = "no_format"
            logger.warning(
                "youtube had no stream url cookies=%s clients=%s title=%s",
                use_cookies,
                ",".join(clients),
                title[:80],
            )
            continue
        logger.info(
            "youtube extract ok cookies=%s clients=%s title=%s",
            use_cookies,
            ",".join(clients),
            title[:80],
        )
        return {"url": url, "title": title[:120]}
    if last_exc is not None and last_error is None:
        last_error = _classify_extract_error(last_exc)
    return None


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


def _play_fail_speech() -> str:
    if last_error == "bot_check":
        if cookiefile_path():
            return "YouTube still blocked that video."
        return "YouTube blocked this server. Add YouTube cookies and restart."
    if last_error in ("reload_needed", "no_format"):
        return "YouTube would not start that video. Try another link."
    return "I could not find that song."


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
        return {"speak": _play_fail_speech()}
    return {
        "speak": f"Playing {track['title']}.",
        "url": track["url"],
        "title": track["title"],
    }
