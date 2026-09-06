"""YouTube cookie wiring for music resolve."""
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


def test_ydl_opts_omits_cookiefile_by_default(monkeypatch):
    monkeypatch.setattr(vm, "cookiefile_path", lambda: None)
    opts = vm._ydl_opts()
    assert "cookiefile" not in opts
    assert opts["default_search"] == "ytsearch1"


def test_ydl_opts_adds_cookiefile_when_present(monkeypatch):
    monkeypatch.setattr(vm, "cookiefile_path", lambda: "/tmp/youtube_cookies.txt")
    opts = vm._ydl_opts()
    assert opts["cookiefile"] == "/tmp/youtube_cookies.txt"
