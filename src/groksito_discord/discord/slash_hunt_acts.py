"""Hunt slash action helpers and inventory/zoo buttons."""
from __future__ import annotations

import discord

from . import ai_coins
from . import aether_gear as gear
from . import aether_hunt as hunt
from .slash_hunt_ops import (
    _display_name,
    _embed,
    _gear_call,
    _is_ori,
)

async def _suggest_caught(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    if not _is_ori(interaction):
        return []
    snap = hunt.snapshot(interaction.user.id)
    caught = snap.get("caught") or {}
    zoo = snap.get("zoo") or {}
    needle = (current or "").strip().lower()
    out: list[discord.app_commands.Choice[str]] = []
    for aid, name, emoji, rarity in hunt.ANIMALS:
        if int(caught.get(aid) or 0) < 1 and int(zoo.get(aid) or 0) < 1:
            continue
        hay = f"{aid} {name} {rarity}"
        if needle and needle not in hay.lower() and needle not in name.lower():
            continue
        out.append(discord.app_commands.Choice(name=f"{emoji} {name}", value=name))
        if len(out) >= 25:
            break
    return out


async def _suggest_weapons(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    if not _is_ori(interaction):
        return []
    snap = hunt.snapshot(interaction.user.id)
    needle = (current or "").strip().lower()
    out: list[discord.app_commands.Choice[str]] = []
    for wid, label, name in gear.owned_weapons(snap.get("gear") or {}):
        if needle and needle not in label.lower() and needle not in wid:
            continue
        out.append(discord.app_commands.Choice(name=f"#{wid} {label}", value=wid))
        if len(out) >= 25:
            break
    return out


def _armory_pack(user_id: int, snap: dict):
    pack = snap.get("gear")
    if isinstance(pack, dict):
        return pack
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        hunt._save_store(store)
    return pack


def _zoo_board_text(interaction: discord.Interaction) -> str:
    snap = hunt.snapshot(interaction.user.id)
    board_txt = hunt.zoo_board(
        _display_name(interaction),
        snap["zoo"],
        snap.get("caught") or snap["zoo"],
    )
    if len(board_txt) > 1900:
        board_txt = board_txt[:1890] + "\n\u2026"
    return board_txt


def _checklist_embed(interaction: discord.Interaction) -> discord.Embed:
    snap = hunt.snapshot(interaction.user.id)
    body = hunt.checklist_board(
        _display_name(interaction),
        snap.get("caught") or snap["zoo"],
    )
    if len(body) > 3900:
        body = body[:3890] + "\n\u2026"
    return _embed("\u2726 Field guide", body)


async def _reply_sell(interaction: discord.Interaction, animal: str, count: int) -> None:
    result = hunt.sell(interaction.user.id, animal, count)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not sell.", ephemeral=True
        )
        return
    pocket = ai_coins.coins(f"**{int(result['balance']):,}**")
    body = (
        f"Sold **{result['sold']}\u00d7 {hunt.animal_label(result['animal_id'])}** "
        f"for {ai_coins.coins(result['payout'])}.\n"
        f"Left: **{result['left']}**\n"
        f"Pocket \u00b7 {pocket}"
    )
    rar = hunt.rarity_of(result["animal_id"])
    color = hunt.RARITY_EMBED.get(rar, hunt.EMBED_GOLD)
    await interaction.response.send_message(embed=_embed("\u2726 Sold", body, color=color))


async def _reply_sacrifice(interaction: discord.Interaction, animal: str, count: int) -> None:
    result = hunt.sacrifice(interaction.user.id, animal, count)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not sacrifice.", ephemeral=True
        )
        return
    body = (
        f"Offered **{result['sacrificed']}\u00d7 {hunt.animal_label(result['animal_id'])}** "
        f"to the aether.\n"
        f"Essence gained **{result['gained']}** \u00b7 total **{result['essence']}**\n"
        f"Left in the zoo: **{result['left']}**"
    )
    rar = hunt.rarity_of(result["animal_id"])
    color = hunt.RARITY_EMBED.get(rar, hunt.EMBED_GOLD)
    await interaction.response.send_message(embed=_embed("\u2726 Sacrifice", body, color=color))


async def _reply_rename(
    interaction: discord.Interaction, animal: str, nickname: str | None
) -> None:
    result = hunt.rename_animal(interaction.user.id, animal, nickname)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not rename.", ephemeral=True
        )
        return
    label = hunt.animal_label(result["animal_id"])
    if result.get("cleared"):
        body = f"Cleared the nickname on {label}."
    else:
        nick = result["nickname"]
        pocket = ai_coins.coins(f"{int(result['balance']):,}")
        body = (
            f'{label} is now **"{nick}"**\n'
            f"Paid {ai_coins.coins(result['fee'])} \u00b7 pocket {pocket}"
        )
    await interaction.response.send_message(embed=_embed("\u2726 Rename", body))


async def _reply_bestiary(interaction: discord.Interaction, animal: str) -> None:
    result = hunt.bestiary(interaction.user.id, animal, _display_name(interaction))
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not open bestiary.", ephemeral=True
        )
        return
    body = result["body"]
    if len(body) > 3900:
        body = body[:3890] + "\n\u2026"
    rar = result.get("rarity") or hunt.COMMON
    color = hunt.RARITY_EMBED.get(rar, hunt.EMBED_GOLD)
    await interaction.response.send_message(embed=_embed("\u2726 Bestiary", body, color=color))
