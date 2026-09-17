"""Shared Hunt slash helpers and button views. Used by slash_hunt.register_hunt."""
from __future__ import annotations

import asyncio
import logging

import discord

from ..llm.persona import creator_is_author
from . import ai_coins
from . import aether_battle as board
from . import aether_gear as gear
from . import aether_hunt as hunt
from . import team_settings_views as team_ui

logger = logging.getLogger("aetherion.slash_hunt")

ORIONLY = "Hunt is a WIP. Only Ori can use these commands."


def _is_ori(interaction: discord.Interaction) -> bool:
    return creator_is_author(getattr(interaction.user, "id", None))


async def _gate(interaction: discord.Interaction, is_guild_allowed) -> bool:
    if not _is_ori(interaction):
        await interaction.response.send_message(ORIONLY, ephemeral=True)
        return False
    if interaction.guild and not is_guild_allowed(interaction.guild.id):
        await interaction.response.send_message(
            "Aetherion is not available on this server.", ephemeral=True
        )
        return False
    return True


def _embed(title: str, body: str, color: int = hunt.EMBED_GOLD) -> discord.Embed:
    embed = discord.Embed(title=title, description=body, color=color)
    embed.set_footer(text=hunt.WIP_FOOTER)
    return embed


def _display_name(interaction: discord.Interaction) -> str:
    user = interaction.user
    return getattr(user, "display_name", None) or getattr(user, "name", "Hunter")


def _gear_call(name: str, user_id: int, *args):
    fn = getattr(hunt, name, None)
    if callable(fn):
        return fn(user_id, *args)
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        if name == "open_lootbox":
            out = gear.open_lootbox(pack)
        elif name == "open_crate":
            out = gear.open_crate(pack)
        elif name == "use_gem":
            out = gear.use_gem(pack, args[0], args[1] if len(args) > 1 else None)
        else:
            out = {"ok": False, "error": "Hunt gear is still updating."}
        hunt._save_store(store)
        return out


def _avatar_url(interaction: discord.Interaction) -> str | None:
    avatar = getattr(interaction.user, "display_avatar", None)
    return str(avatar.url) if avatar is not None else None


def _battle_total(result: dict) -> int:
    return max(1, int(result.get("rounds") or 1))


def _battle_embed(
    name: str,
    result: dict,
    frame: dict,
    *,
    final: bool,
    icon_url: str | None = None,
) -> discord.Embed:
    outcome = result.get("result") or "draw"
    if outcome == "win":
        color = hunt.EMBED_WIN
    elif outcome == "lose":
        color = hunt.EMBED_LOSE
    else:
        color = hunt.EMBED_GOLD
    desc = None if final else ("\n".join((frame.get("lines") or [])[-2:]) or None)
    embed = discord.Embed(color=color, description=desc)
    author = {"name": f"{name} goes into battle!"}
    if icon_url:
        author["icon_url"] = icon_url
    embed.set_author(**author)
    embed.add_field(name=f"{name}'s Team", value=board.roster_field(frame.get("player") or []), inline=True)
    embed.add_field(name="Enemy Team", value=board.roster_field(frame.get("enemy") or []), inline=True)
    total = _battle_total(result)
    turn = int(frame.get("turn") or 1)
    if final:
        footer = board.result_caption(result) + f"\n{hunt.WIP_FOOTER}"
    else:
        footer = f"Turn {turn}/{total}"
    embed.set_footer(text=footer)
    embed.set_image(url="attachment://battle.png")
    return embed


def _battle_file(frame: dict, total: int) -> discord.File:
    png = board.render_battle_png(
        frame.get("player") or [],
        frame.get("enemy") or [],
        turn=int(frame.get("turn") or 1),
        max_turns=max(1, int(total or 1)),
        lines=frame.get("lines") or None,
    )
    return discord.File(png, filename="battle.png")


def _playable_frames(frames: list[dict]) -> list[dict]:
    if len(frames) <= 18:
        return frames
    first, last = frames[0], frames[-1]
    mid = frames[1:-1]
    step = max(1, len(mid) // 16)
    picked = [first] + mid[::step][:16]
    if picked[-1] is not last:
        picked.append(last)
    return picked


def _team_animal_choice_rows(
    team: list, zoo: dict, current: str
) -> list[tuple[str, str]]:
    """Pure helper: (choice_label, value_name) for animals in the 3 battle slots only."""
    needle = (current or "").strip().lower()
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for aid in team or []:
        if not aid or aid in seen:
            continue
        seen.add(aid)
        row = hunt.ANIMAL_BY_ID.get(aid)
        if not row:
            continue
        _aid, name, emoji, rarity = row
        hay = f"{aid} {name} {rarity}"
        if needle and needle not in hay.lower() and needle not in name.lower():
            continue
        have = int((zoo or {}).get(aid) or 0)
        label = f"{emoji} {name}"
        if have:
            label = f"{emoji} {name} ×{have}"
        out.append((label, name))
        if len(out) >= 25:
            break
    return out


async def _suggest_owned(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    if not _is_ori(interaction):
        return []
    snap = hunt.snapshot(interaction.user.id)
    owned = hunt.owned_catalog(snap["zoo"])
    needle = (current or "").strip().lower()
    out: list[discord.app_commands.Choice[str]] = []
    for aid, name, emoji, rarity in owned:
        hay = f"{aid} {name} {rarity}"
        if needle and needle not in hay.lower() and needle not in name.lower():
            continue
        have = int(snap["zoo"].get(aid) or 0)
        out.append(
            discord.app_commands.Choice(
                name=f"{emoji} {name} ×{have}",
                value=name,
            )
        )
        if len(out) >= 25:
            break
    return out


async def _suggest_team(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    """Autocomplete for /equip animal — battle-team slots only."""
    if not _is_ori(interaction):
        return []
    snap = hunt.snapshot(interaction.user.id)
    rows = _team_animal_choice_rows(snap.get("team") or [], snap.get("zoo") or {}, current)
    return [discord.app_commands.Choice(name=label, value=value) for label, value in rows]
