"""Fail CI if core slashes disappear from source the way they did on 2026-09-16."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISCORD = ROOT / "src" / "groksito_discord" / "discord"

REQUIRED = (
    "help",
    "logs",
    "autorole",
    "play",
    "pause",
    "stop",
    "purge",
    "reactionrole",
    "status",
    "edit",
    "blackjack",
    "balance",
    "daily",
    "leaderboard",
    "givecoins",
    "slots",
    "cointoss",
    "highlow",
    "connect4",
    "poker",
    "ping",
    "welcome",
    "datechannel",
    "audio",
    "join",
    "leave",
    "profile",
    "server",
    "top",
)
REMOVED_HUNT = (
    "hunt",
    "zoo",
    "team",
    "battle",
    "raid",
    "inv",
    "weapon",
    "givesupply",
)
NAME_RE = re.compile(
    r"(?:tree|group)\.command\(\s*name\s*=\s*[\"']([a-z0-9]+)[\"']",
    re.I,
)
INLINE_HANDLERS = (
    "def welcome_slash",
    "def datechannel_slash",
    "def audio_slash",
    "def join_slash",
    "def leave_slash",
    "def read_aloud_context",
    'name="Read aloud"',
)


def _slash_source() -> str:
    chunks = []
    for path in sorted(DISCORD.glob("slash*.py")):
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _declared_names() -> set[str]:
    return set(NAME_RE.findall(_slash_source()))


def test_required_slashes_are_still_declared():
    names = _declared_names()
    missing = [name for name in REQUIRED if name not in names]
    assert not missing, f"slash registry lost: {missing}"


def test_inline_voice_welcome_audio_handlers_were_not_truncated():
    text = (DISCORD / "slash_commands.py").read_text(encoding="utf-8")
    missing = [mark for mark in INLINE_HANDLERS if mark not in text]
    assert not missing, f"slash_commands.py was truncated again: {missing}"


def test_help_still_lists_the_required_slashes():
    help_text = (DISCORD / "slash_help.py").read_text(encoding="utf-8")
    missing = [name for name in REQUIRED if f"/{name}" not in help_text]
    assert not missing, f"/help is missing: {missing}"


def test_hunt_slashes_stay_unregistered():
    names = _declared_names()
    present = [name for name in REMOVED_HUNT if name in names]
    assert not present, f"Hunt slashes came back: {present}"
