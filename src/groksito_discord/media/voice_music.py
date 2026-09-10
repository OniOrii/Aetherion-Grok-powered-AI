"""Play/stop SoundCloud music on the same VoiceClient Aetherion already uses for TTS."""
from __future__ import annotations

import asyncio
import logging
import re
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
_NOISE = {
    "official",
    "visualizer",
    "audio",
    "video",
    "lyrics",
    "lyric",
    "hd",
    "hq",
    "mv",
    "feat",
    "ft",
    "prod",
    "the",
    "and",
}

last_error: str | None = None
_MATCH_MIN = 50


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


def _ydl_opts(*, default_search: str | None = None, extract_flat: bool = False) -> dict[str, Any]:
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
    return opts


def _classify_extract_error(exc: BaseException) -> str:
    msg = str(exc).lower()
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
        if "soundcloud" in url or "sndcdn.com" in url:
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


def _clean_search_title(title: str) -> str:
    text = re.sub(r"\[[^\]]*\]", " ", title or "")
    text = re.sub(r"\([^\)]*\)", " ", text)
    text = re.sub(r"\b(official|visualizer|audio|video|lyrics|lyric)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text[:120]


def _title_score(wanted: str, got: str) -> int:
    wanted = wanted or ""
    got = got or ""
    try:
        from rapidfuzz import fuzz

        raw = int(fuzz.token_set_ratio(wanted, got))
        clean = int(fuzz.token_set_ratio(_clean_search_title(wanted), _clean_search_title(got)))
        partial = int(fuzz.partial_ratio(_clean_search_title(wanted), _clean_search_title(got)))
        return max(raw, clean, partial)
    except Exception:
        a = {w for w in re.findall(r"[a-z0-9]+", wanted.lower()) if w not in _NOISE}
        b = {w for w in re.findall(r"[a-z0-9]+", got.lower()) if w not in _NOISE}
        if not a or not b:
            return 0
        return int(100 * len(a & b) / max(len(a), 1))


def _unsupported_url(query: str) -> bool:
    low = query.lower()
    return any(
        host in low
        for host in (
            "youtube.com",
            "youtu.be",
            "music.youtube.com",
            "mixcloud.com",
            "audiomack.com",
        )
    )


def _run_ydl(
    ytdlp_query: str,
    *,
    default_search: str | None,
    extract_flat: bool = False,
) -> dict[str, Any] | None:
    import yt_dlp

    opts = _ydl_opts(default_search=default_search, extract_flat=extract_flat)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(ytdlp_query, download=False)


def _extract_one(
    ytdlp_query: str,
    *,
    default_search: str | None,
    wanted: str = "",
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    global last_error
    try:
        raw = _run_ydl(
            ytdlp_query,
            default_search=default_search,
        )
        info = _unwrap_info(raw)
    except Exception as e:
        last_error = _classify_extract_error(e)
        logger.warning(
            "yt-dlp %s source=soundcloud query=%s",
            last_error,
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
                "reject weak match source=soundcloud score=%s title=%s wanted=%s",
                score,
                title[:80],
                wanted[:80],
            )
            last_error = "weak_match"
            return None, info
    url = _pick_stream(info)
    if not url:
        last_error = "no_format"
        logger.warning("no stream url source=soundcloud title=%s", title[:80])
        return None, info
    logger.info("extract ok source=soundcloud title=%s", title[:80])
    return {"url": url, "title": title[:120], "source": "soundcloud"}, info


def _best_search_hit(search_q: str, wanted: str) -> dict[str, Any] | None:
    try:
        raw = _run_ydl(
            search_q,
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
    logger.info(
        "search hit source=soundcloud score=%s title=%s",
        best_score,
        str(best.get("title"))[:80],
    )
    return best


def _extract_track(query: str) -> dict[str, str] | None:
    global last_error
    last_error = None
    q = (query or "").strip()
    if not q:
        last_error = "extract_failed"
        return None
    if _URL_RE.match(q) and _unsupported_url(q):
        last_error = "unsupported_source"
        logger.info("rejected non-soundcloud url query=%s", q[:80])
        return None
    try:
        import yt_dlp  # noqa: F401
    except Exception:
        logger.warning("yt-dlp is not installed")
        last_error = "yt_dlp_missing"
        return None

    if _URL_RE.match(q) and "soundcloud.com" in q.lower():
        track, _info = _extract_one(q, default_search=None, wanted="")
        return track

    wanted = _clean_search_title(q)
    logger.info("music source=soundcloud query=%s", q[:80])
    hit = _best_search_hit(f"scsearch5:{q}", wanted)
    if hit:
        page = str(hit.get("webpage_url") or hit.get("url") or "")
        if page:
            track, _info = _extract_one(page, default_search=None, wanted=wanted)
            if track:
                return track
    track, _info = _extract_one(f"scsearch1:{q}", default_search=None, wanted=wanted)
    return track


async def resolve_track(query: str) -> dict[str, str] | None:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _extract_track, query)


def _ffmpeg_before_options() -> str:
    return "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin"


def start_playback(vc: discord.VoiceClient, url: str) -> None:
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    vc.play(
        discord.FFmpegPCMAudio(
            url,
            before_options=_ffmpeg_before_options(),
            options="-vn",
        )
    )
    logger.info("ffmpeg started music stream")


def _play_fail_speech() -> str:
    if last_error == "unsupported_source":
        return "I only play SoundCloud now. Say a song name or paste a SoundCloud link."
    if last_error == "weak_match":
        return "I found other tracks, but not that song."
    if last_error in ("reload_needed", "no_format"):
        return "I could not start that song. Try another name or a SoundCloud link."
    if last_error == "yt_dlp_missing":
        return "Music is not installed on this host."
    return "I could not find that song on SoundCloud."


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
