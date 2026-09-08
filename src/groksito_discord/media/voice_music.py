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
_INVIDIOUS = (
    "https://yewtu.be",
    "https://inv.nadeko.net",
    "https://invidious.fdn.fr",
)
_MATCH_MIN = 58


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
    extract_flat: bool = False,
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
    if extract_flat:
        opts["extract_flat"] = True
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


def _usable_audio_url(url: str, fmt: dict[str, Any] | None = None) -> bool:
    if not url.startswith("http"):
        return False
    low = url.lower()
    path = low.split("?", 1)[0]
    if any(h in low for h in ("ytimg.com", "ggpht.com")):
        return False
    if "storyboard" in low:
        return False
    if path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return False
    if fmt is not None:
        fid = str(fmt.get("format_id") or "").lower()
        note = str(fmt.get("format_note") or "").lower()
        if fid.startswith("sb") or "storyboard" in fid or "storyboard" in note:
            return False
        acodec = str(fmt.get("acodec") or "none")
        vcodec = str(fmt.get("vcodec") or "none")
        if acodec == "none" and vcodec in ("none", "images"):
            return False
    return True


def _pick_stream(info: dict[str, Any]) -> str:
    candidates: list[tuple[float, str]] = []
    for fmt in info.get("formats") or []:
        url = str(fmt.get("url") or "")
        if not _usable_audio_url(url, fmt):
            continue
        proto = str(fmt.get("protocol") or "")
        if "dash" in proto or "sabr" in proto:
            continue
        score = float(fmt.get("abr") or fmt.get("tbr") or 0)
        if "googlevideo.com" in url:
            score += 1000
        if (fmt.get("acodec") or "none") != "none":
            score += 100
        candidates.append((score, url))
    if candidates:
        candidates.sort(key=lambda row: row[0], reverse=True)
        return candidates[0][1]
    top = str(info.get("url") or "")
    if _usable_audio_url(top):
        return top
    return ""


def _unwrap_info(info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not info:
        return None
    if "entries" in info:
        entries = [e for e in (info.get("entries") or []) if e]
        return entries[0] if entries else None
    return info


def _title_score(wanted: str, got: str) -> int:
    try:
        from rapidfuzz import fuzz
    except Exception:
        a = set(re.findall(r"[a-z0-9]+", (wanted or "").lower()))
        b = set(re.findall(r"[a-z0-9]+", (got or "").lower()))
        if not a or not b:
            return 0
        return int(100 * len(a & b) / len(a))
    return int(fuzz.token_set_ratio(wanted or "", got or ""))


def _clean_search_title(title: str) -> str:
    text = re.sub(r"\[[^\]]*\]", " ", title or "")
    text = re.sub(r"\([^\)]*official[^\)]*\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text[:120]


def _source_queries(query: str) -> list[tuple[str, str, str | None]]:
    q = (query or "").strip()
    if not q:
        return []
    if _URL_RE.match(q):
        low = q.lower()
        if "soundcloud.com" in low:
            return [("soundcloud", q, None)]
        if "youtu.be" in low or "youtube.com" in low:
            return [("youtube", q, None)]
        if "mixcloud.com" in low:
            return [("mixcloud", q, None)]
        if "audiomack.com" in low:
            return [("audiomack", q, None)]
        return [("url", q, None)]
    return [("youtube", q, "ytsearch1")]


def _youtube_attempts() -> list[tuple[bool, tuple[str, ...]]]:
    rows: list[tuple[bool, tuple[str, ...]]] = [(False, c) for c in _ANON_CLIENTS]
    if cookiefile_path():
        rows.extend((True, c) for c in _COOKIE_CLIENTS)
    return rows


def _run_ydl(
    ytdlp_query: str,
    *,
    use_cookies: bool,
    clients: tuple[str, ...] | None,
    default_search: str | None,
    extract_flat: bool = False,
) -> dict[str, Any] | None:
    import yt_dlp

    opts = _ydl_opts(
        clients,
        use_cookies=use_cookies,
        default_search=default_search,
        extract_flat=extract_flat,
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(ytdlp_query, download=False)


def _invidious_audio(video_id: str) -> str:
    try:
        import httpx
    except Exception:
        return ""
    for base in _INVIDIOUS:
        try:
            resp = httpx.get(
                f"{base}/api/v1/videos/{video_id}",
                timeout=8.0,
                follow_redirects=True,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            streams = list(data.get("adaptiveFormats") or []) + list(
                data.get("formatStreams") or []
            )
            best = ""
            best_score = -1
            for item in streams:
                url = str(item.get("url") or "")
                if not _usable_audio_url(url):
                    continue
                kind = str(item.get("type") or "")
                if "audio" not in kind and not item.get("audioQuality"):
                    continue
                score = int(item.get("bitrate") or 0)
                if score >= best_score:
                    best_score = score
                    best = url
            if best:
                logger.info("invidious audio ok host=%s id=%s", base, video_id)
                return best
        except Exception:
            logger.warning("invidious miss host=%s id=%s", base, video_id)
            continue
    return ""


def _extract_one(
    ytdlp_query: str,
    *,
    use_cookies: bool,
    clients: tuple[str, ...] | None,
    default_search: str | None,
    source: str,
    wanted: str = "",
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    global last_error
    try:
        raw = _run_ydl(
            ytdlp_query,
            use_cookies=use_cookies,
            clients=clients,
            default_search=default_search,
        )
        info = _unwrap_info(raw)
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
        return None, None
    if not info:
        return None, None
    title = (info.get("title") or ytdlp_query).strip()
    if wanted:
        score = _title_score(wanted, title)
        if score < _MATCH_MIN:
            logger.warning(
                "reject weak match source=%s score=%s title=%s wanted=%s",
                source,
                score,
                title[:80],
                wanted[:80],
            )
            last_error = "weak_match"
            return None, info
    url = _pick_stream(info)
    if not url:
        last_error = "no_format"
        logger.warning(
            "no stream url source=%s cookies=%s clients=%s title=%s",
            source,
            use_cookies,
            ",".join(clients or ()),
            title[:80],
        )
        return None, info
    logger.info(
        "extract ok source=%s cookies=%s clients=%s title=%s",
        source,
        use_cookies,
        ",".join(clients or ()),
        title[:80],
    )
    return {"url": url, "title": title[:120], "source": source}, info


def _best_search_hit(search_q: str, wanted: str) -> dict[str, Any] | None:
    try:
        raw = _run_ydl(
            search_q,
            use_cookies=False,
            clients=None,
            default_search=None,
            extract_flat=True,
        )
    except Exception as e:
        logger.warning("search failed q=%s err=%s", search_q[:80], type(e).__name__)
        return None
    entries = []
    if raw:
        if raw.get("entries"):
            entries = [e for e in raw["entries"] if e]
        else:
            entries = [raw]
    best = None
    best_score = -1
    for entry in entries[:8]:
        title = str(entry.get("title") or "")
        score = _title_score(wanted, title)
        if score > best_score:
            best_score = score
            best = entry
    if not best or best_score < _MATCH_MIN:
        logger.warning(
            "no strong search hit q=%s best=%s score=%s",
            search_q[:80],
            (best or {}).get("title", "")[:80],
            best_score,
        )
        return None
    return best


def _fallback_sources(search_text: str) -> list[tuple[str, str]]:
    q = search_text.strip()
    return [
        ("soundcloud", f"scsearch5:{q}"),
        ("mixcloud", f"https://www.mixcloud.com/search/?q={q}"),
        ("audiomack", f"https://audiomack.com/search?q={q}"),
    ]


def _extract_track(query: str) -> dict[str, str] | None:
    global last_error
    last_error = None
    try:
        import yt_dlp  # noqa: F401
    except Exception:
        logger.warning("yt-dlp is not installed")
        last_error = "yt_dlp_missing"
        return None

    yt_info: dict[str, Any] | None = None
    for source, ytdlp_query, default_search in _source_queries(query):
        if source != "youtube" and not _URL_RE.match(query):
            break
        if source == "youtube":
            for use_cookies, clients in _youtube_attempts():
                track, info = _extract_one(
                    ytdlp_query,
                    use_cookies=use_cookies,
                    clients=clients,
                    default_search=default_search,
                    source=source,
                    wanted="",
                )
                if info and info.get("id"):
                    yt_info = info
                if track:
                    return track
            continue
        track, _info = _extract_one(
            ytdlp_query,
            use_cookies=False,
            clients=None,
            default_search=default_search,
            source=source,
            wanted=query,
        )
        if track:
            return track

    if yt_info and yt_info.get("id"):
        audio = _invidious_audio(str(yt_info["id"]))
        if audio:
            title = (yt_info.get("title") or query).strip()
            return {"url": audio, "title": title[:120], "source": "youtube"}

    wanted = _clean_search_title(str((yt_info or {}).get("title") or query))
    for source, search_q in _fallback_sources(wanted):
        logger.info("music fallback source=%s query=%s", source, search_q[:80])
        hit = _best_search_hit(search_q, wanted)
        if not hit:
            continue
        page = str(hit.get("webpage_url") or hit.get("url") or "")
        if not page:
            continue
        track, _info = _extract_one(
            page,
            use_cookies=False,
            clients=None,
            default_search=None,
            source=source,
            wanted=wanted,
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
    if last_error == "weak_match":
        return "I found other tracks, but not that song."
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
    if source == "youtube":
        speak = f"Playing {track['title']}."
    else:
        speak = f"Playing {track['title']} from {source}."
    return {
        "speak": speak,
        "url": track["url"],
        "title": track["title"],
    }
