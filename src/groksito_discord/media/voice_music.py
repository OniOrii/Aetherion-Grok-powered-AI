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
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

last_error: str | None = None
_cookies_logged = False

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
    default_search: str | None = "ytsearch1",
) -> dict[str, Any]:
    global _cookies_logged
    opts: dict[str, Any] = {
        "noplaylist": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "ignore_no_formats_error": True,
        "format": "bestaudio/best/best*",
    }
    if default_search:
        opts["default_search"] = default_search
    if player_clients:
        opts["extractor_args"] = {"youtube": {"player_client": list(player_clients)}}
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
        if "dash" in proto or "sabr" in proto:
            continue
        if (fmt.get("acodec") or "none") == "none" and (fmt.get("vcodec") or "none") != "none":
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


def _unwrap_info(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not info:
        return None
    if "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        return entries[0] if entries else None
    return info


def _source_queries(query: str) -> list[tuple[str, str, str | None]]:
    """(source, ytdlp_query, default_search)."""
    q = (query or "").strip()
    if not q:
        return []
    if _URL_RE.match(q):
        low = q.lower()
        if "soundcloud.com" in low:
            return [("soundcloud", q, None)]
        if "youtu.be" in low or "youtube.com" in low:
            return [("youtube", q, None)]
        return [("url", q, None)]
    return [
        ("youtube", q, "ytsearch1"),
        ("soundcloud", f"scsearch1:{q}", None),
    ]


def _youtube_attempts() -> list[tuple[bool, tuple[str, ...]]]:
    rows: list[tuple[bool, tuple[str, ...]]] = [(False, c) for c in _ANON_CLIENTS]
    if cookiefile_path():
        rows.extend((True, c) for c in _COOKIE_CLIENTS)
    return rows


def _extract_one(
    ytdlp_query: str,
    *,
    use_cookies: bool,
    clients: tuple[str, ...] | None,
    default_search: str | None,
    source: str,
) -> dict[str, str] | None:
    global last_error
    import yt_dlp

    opts = _ydl_opts(clients, use_cookies=use_cookies, default_search=default_search)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = _unwrap_info(ydl.extract_info(ytdlp_query, download=False))
    except Exception as e:
        last_error = _classify_extract_error(e)
        logger.warning(
            "yt-dlp %s source=%s cookies=%s clients=%s query=%s",
            last_error,
            source,
            use_cookies,
            ",".join(clients or ()),
            ytdlp_query[:80],
        )
        return None
    if not info:
        return None
    url = _pick_stream(info)
    title = (info.get("title") or ytdlp_query).strip()
    if not url:
        last_error = "no_format"
        logger.warning(
            "no stream url source=%s cookies=%s clients=%s title=%s",
            source,
            use_cookies,
            ",".join(clients or ()),
            title[:80],
        )
        return None
    logger.info(
        "extract ok source=%s cookies=%s clients=%s title=%s",
        source,
        use_cookies,
        ",".join(clients or ()),
        title[:80],
    )
    return {"url": url, "title": title[:120], "source": source}


def _extract_track(query: str) -> dict[str, str] | None:
    global last_error
    last_error = None
    try:
        import yt_dlp  # noqa: F401
    except Exception:
        logger.warning("yt-dlp is not installed")
        last_error = "yt_dlp_missing"
        return None

    for source, ytdlp_query, default_search in _source_queries(query):
        if source == "youtube":
            for use_cookies, clients in _youtube_attempts():
                track = _extract_one(
                    ytdlp_query,
                    use_cookies=use_cookies,
                    clients=clients,
                    default_search=default_search,
                    source=source,
                )
                if track:
                    return track
            continue
        logger.info("music fallback source=%s query=%s", source, ytdlp_query[:80])
        track = _extract_one(
            ytdlp_query,
            use_cookies=False,
            clients=None,
            default_search=default_search,
            source=source,
        )
        if track:
            return track
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
        return "I could not start that song. Try another name or a link."
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
    source = track.get("source") or "youtube"
    if source == "soundcloud":
        speak = f"Playing {track['title']} from SoundCloud."
    else:
        speak = f"Playing {track['title']}."
    return {
        "speak": speak,
        "url": track["url"],
        "title": track["title"],
    }
