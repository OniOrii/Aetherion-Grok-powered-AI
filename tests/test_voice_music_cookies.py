"""Music resolve matching and stream filters."""
from __future__ import annotations

from groksito_discord.media import voice_music as vm


def test_parse_play_still_works():
    assert vm.parse_music_command("play Astronaut in the Ocean") == (
        "play",
        "Astronaut in the Ocean",
    )


def test_title_score_rejects_unrelated():
    wanted = 'Hippie Sabotage - "Your Soul" [Official Audio]'
    wrong = "parsg - heal your soul (prod. by Fujishen)"
    right = "Hippie Sabotage Your Soul"
    assert vm._title_score(wanted, wrong) < vm._MATCH_MIN
    assert vm._title_score(wanted, right) >= vm._MATCH_MIN


def test_pick_stream_skips_storyboard():
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
                "format_id": "251",
                "url": "https://rr1---sn-abc.googlevideo.com/videoplayback?id=1",
                "acodec": "opus",
                "vcodec": "none",
                "abr": 160,
                "protocol": "https",
            },
        ],
    }
    assert "googlevideo.com" in vm._pick_stream(info)
