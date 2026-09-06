"""YouTube cookie wiring and music source fallback."""
from __future__ import annotations

from groksito_discord.media import voice_music as vm


def test_parse_play_still_works():
    assert vm.parse_music_command("play Astronaut in the Ocean") == (
        "play",
        "Astronaut in the Ocean",
    )


def test_classify_bot_check():
    err = Exception("ERROR: [youtube] abc: Sign in to confirm you're not a bot.")
    assert vm._classify_extract_error(err) == "bot_check"


def test_source_queries_add_soundcloud_fallback():
    q = vm._source_queries("Your Soul by Hippie Sabotage")
    assert q[0][0] == "youtube"
    assert q[1][0] == "soundcloud"
    assert q[1][1].startswith("scsearch1:")


def test_source_queries_keep_direct_links():
    yt = vm._source_queries("https://youtu.be/dQw4w9WgXcQ")
    assert yt == [("youtube", "https://youtu.be/dQw4w9WgXcQ", None)]
    sc = vm._source_queries("https://soundcloud.com/artist/track")
    assert sc[0][0] == "soundcloud"


def test_ydl_opts_ignores_missing_formats(monkeypatch):
    monkeypatch.setattr(vm, "cookiefile_path", lambda: None)
    opts = vm._ydl_opts(use_cookies=True)
    assert opts["ignore_no_formats_error"] is True
    assert "cookiefile" not in opts
