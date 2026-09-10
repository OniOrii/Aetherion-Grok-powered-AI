"""Music resolve matching and SoundCloud-only filters."""
from __future__ import annotations

from groksito_discord.media import voice_impl
from groksito_discord.media import voice_music as vm


def test_parse_play_still_works():
    assert vm.parse_music_command("play Astronaut in the Ocean") == (
        "play",
        "Astronaut in the Ocean",
    )


def test_title_score_rejects_unrelated():
    wanted = "Hippie Sabotage Your Soul"
    wrong = "random cooking podcast episode 12"
    right = "Hippie Sabotage Your Soul"
    assert vm._title_score(wanted, wrong) < vm._MATCH_MIN
    assert vm._title_score(wanted, right) >= vm._MATCH_MIN


def test_pick_stream_skips_storyboard_and_prefers_soundcloud():
    info = {
        "url": "https://i.ytimg.com/sb/abc/storyboard3_L2/M$M.jpg?sqp=1",
        "formats": [
            {
                "format_id": "sb0",
                "url": "https://i.ytimg.com/sb/abc/storyboard3_L2/M$M.jpg",
                "acodec": "none",
                "vcodec": "none",
            },
            {
                "format_id": "http_mp3_128",
                "url": "https://cf-media.sndcdn.com/example.mp3",
                "acodec": "mp3",
                "vcodec": "none",
                "abr": 128,
                "protocol": "https",
            },
        ],
    }
    assert "sndcdn.com" in vm._pick_stream(info)


def test_youtube_and_other_hosts_are_rejected():
    assert vm._unsupported_url("https://youtu.be/dQw4w9WgXcQ")
    assert vm._unsupported_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert vm._unsupported_url("https://www.mixcloud.com/foo/bar")
    assert vm._unsupported_url("https://audiomack.com/foo/song/bar")
    assert not vm._unsupported_url("https://soundcloud.com/foo/bar")


def test_extract_track_rejects_youtube_without_network():
    vm.last_error = None
    assert vm._extract_track("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is None
    assert vm.last_error == "unsupported_source"


def test_wake_words_include_ethereum_and_iberian():
    assert voice_impl._wake_and_prompt("Ethereum play some lofi") == "play some lofi"
    assert voice_impl._wake_and_prompt("Iberian what time is it") == "what time is it"
    assert voice_impl._wake_and_prompt("Aetherion hello") == "hello"
    assert voice_impl._wake_and_prompt("just talking in vc") is None
