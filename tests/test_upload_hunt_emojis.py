"""Unit tests for scripts/upload_hunt_emojis.py (mapping + env format; no Discord)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "upload_hunt_emojis.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("upload_hunt_emojis", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["upload_hunt_emojis"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def upe():
    return _load_script()


class TestHuntEmojiMapping:
    def test_exactly_thirteen_assets(self, upe):
        assert len(upe.HUNT_EMOJI_ASSETS) == 13

    def test_phys_png_not_included(self, upe):
        paths = [a.rel_path for a in upe.HUNT_EMOJI_ASSETS]
        assert not any(p.endswith("phys.png") for p in paths)

    def test_hud_and_rank_env_keys(self, upe):
        keys = {a.env_key for a in upe.HUNT_EMOJI_ASSETS}
        assert keys == {
            "HUNT_EMOJI_HP",
            "HUNT_EMOJI_WP",
            "HUNT_EMOJI_ATK",
            "HUNT_EMOJI_MAG",
            "HUNT_EMOJI_PR",
            "HUNT_EMOJI_MR",
            "HUNT_RANK_EMOJI_COMMON",
            "HUNT_RANK_EMOJI_UNCOMMON",
            "HUNT_RANK_EMOJI_RARE",
            "HUNT_RANK_EMOJI_EPIC",
            "HUNT_RANK_EMOJI_MYTHIC",
            "HUNT_RANK_EMOJI_ASTRAL",
            "HUNT_RANK_EMOJI_PRIMORDIAL",
        }

    def test_emoji_names_match_spec(self, upe):
        by_key = {a.env_key: a.emoji_name for a in upe.HUNT_EMOJI_ASSETS}
        assert by_key["HUNT_EMOJI_HP"] == "hunt_hp"
        assert by_key["HUNT_EMOJI_ATK"] == "hunt_atk"
        assert by_key["HUNT_RANK_EMOJI_COMMON"] == "aether_c"
        assert by_key["HUNT_RANK_EMOJI_PRIMORDIAL"] == "aether_p"

    def test_asset_files_exist_on_disk(self, upe):
        for asset in upe.HUNT_EMOJI_ASSETS:
            path = REPO_ROOT / asset.rel_path
            assert path.is_file(), f"missing {path}"
            assert path.stat().st_size > 0


class TestEnvLineFormat:
    def test_format_env_line(self, upe):
        line = upe.format_env_line("HUNT_EMOJI_HP", "hunt_hp", "123456789012345678")
        assert line == "HUNT_EMOJI_HP=<:hunt_hp:123456789012345678>"

    def test_format_env_block_order(self, upe):
        pairs = [(upe.HUNT_EMOJI_ASSETS[0], "111"), (upe.HUNT_EMOJI_ASSETS[1], "222")]
        block = upe.format_env_block(pairs)
        assert block == (
            "HUNT_EMOJI_HP=<:hunt_hp:111>\n"
            "HUNT_EMOJI_WP=<:hunt_wp:222>\n"
        )

    def test_update_env_keys_preserves_others(self, upe, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DISCORD_TOKEN=secret\nHUNT_EMOJI_HP=<:old:1>\nFOO=bar\n", encoding="utf-8")
        upe.update_env_keys(
            env,
            {
                "HUNT_EMOJI_HP": "<:hunt_hp:999>",
                "HUNT_EMOJI_WP": "<:hunt_wp:888>",
            },
        )
        text = env.read_text(encoding="utf-8")
        assert "DISCORD_TOKEN=secret" in text
        assert "FOO=bar" in text
        assert "HUNT_EMOJI_HP=<:hunt_hp:999>" in text
        assert "HUNT_EMOJI_WP=<:hunt_wp:888>" in text
        assert "<:old:1>" not in text

    def test_dry_run_main_exits_zero(self, upe, capsys):
        rc = upe.main(["--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "HUNT_EMOJI_HP=" in out
        assert "HUNT_RANK_EMOJI_PRIMORDIAL=" in out
        assert "[dry-run]" in out
