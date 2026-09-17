"""Hunt lootbox, crate, gem, equip, salvage helpers and buttons."""
from __future__ import annotations

import discord

from . import aether_gear as gear
from . import aether_hunt as hunt
from .slash_hunt_ops import _display_name, _embed, _gear_call
from .slash_hunt_acts import _checklist_embed


async def _reply_lootbox(interaction: discord.Interaction) -> None:
    result = _gear_call("open_lootbox", interaction.user.id)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "No lootbox.", ephemeral=True
        )
        return
    rar = hunt.RARITY_LABEL[result["rarity"]]
    kind = gear.GEM_BY_KIND[result["kind"]][1]
    line = (
        f"\U0001f48e | **{_display_name(interaction)}** opens a lootbox\n"
        f"\U0001f4e6 | and finds a **{rar} {kind}**!"
    )
    await interaction.response.send_message(line)


async def _reply_crate(interaction: discord.Interaction) -> None:
    result = _gear_call("open_crate", interaction.user.id)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "No crate.", ephemeral=True
        )
        return
    rar = hunt.RARITY_LABEL[result["rarity"]]
    line = (
        f"{result['emoji']} | **{rar} {result['name']}** Q{result['quality']} "
        f"+{result['atk']} ATK (id `{result['wid']}`)"
    )
    embed = _embed(
        f"\U0001fab5 {_display_name(interaction)} opens a weapon crate",
        line,
    )
    if hasattr(gear, "weapon_icon_png"):
        icon = gear.weapon_icon_png(result["kind"], result["rarity"])
        fname = f"{result['kind']}.png"
        embed.set_thumbnail(url=f"attachment://{fname}")
        await interaction.response.send_message(
            embed=embed, file=discord.File(icon, filename=fname)
        )
        return
    await interaction.response.send_message(embed=embed)


async def _reply_use(
    interaction: discord.Interaction, gem: str, rarity: str | None
) -> None:
    rar = None
    if rarity:
        key = rarity.strip().lower()
        rar = key if key in gear.RARITY_LABEL else None
    result = _gear_call("use_gem", interaction.user.id, gem, rar)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not use that gem.", ephemeral=True
        )
        return
    tier = gear.RARITY_LABEL.get(result["rarity"], result["rarity"])
    left = int(result["left"])
    await interaction.response.send_message(
        f"{gear.GEM_BY_KIND[result['kind']][2]} | Activated "
        f"**{tier} {result['label']}** "
        f"`[{left}/{left}]` charges (role-based spend per hunt)."
    )


async def _reply_equip(interaction: discord.Interaction, weapon: str, animal: str) -> None:
    snap0 = hunt.snapshot(interaction.user.id)
    team_ids = [aid for aid in (snap0.get("team") or []) if aid]
    if not team_ids:
        await interaction.response.send_message(
            "Your battle team is empty. Set animals with `/team` first.",
            ephemeral=True,
        )
        return
    animal_id = hunt.resolve_animal(animal)
    if animal_id is None:
        await interaction.response.send_message(
            "I do not know that animal. Check `/team`.",
            ephemeral=True,
        )
        return
    if animal_id not in team_ids:
        await interaction.response.send_message(
            "Equip only works on your battle team. Use `/team` to set slots.",
            ephemeral=True,
        )
        return
    if hasattr(hunt, "equip_weapon"):
        result = hunt.equip_weapon(interaction.user.id, weapon, animal)
    else:
        with hunt._lock:
            store = hunt._load_store()
            row = hunt._ensure_user(store, interaction.user.id)
            pack = gear.ensure_gear(row)
            wid = gear.resolve_weapon(pack, weapon)
            if not wid:
                result = {"ok": False, "error": "No matching weapon. Use the id from `/inv`."}
            else:
                result = gear.equip_weapon(pack, wid, animal_id)
                if result.get("ok"):
                    result["animal_id"] = animal_id
                    result["label"] = gear.weapon_line(gear.equipped_weapon(pack, animal_id))
            hunt._save_store(store)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not equip.", ephemeral=True
        )
        return
    pack = hunt.snapshot(interaction.user.id).get("gear") or {}
    if not pack:
        with hunt._lock:
            store = hunt._load_store()
            pack = gear.ensure_gear(hunt._ensure_user(store, interaction.user.id))
    wep = gear.equipped_weapon(pack, result["animal_id"])
    body = f"Equipped {result['label']} on {hunt.animal_label(result['animal_id'])}."
    if wep and hasattr(gear, "weapon_icon_png"):
        embed = _embed("\u2726 Equip", body)
        icon = gear.weapon_icon_png(wep["kind"], wep.get("rarity"))
        fname = f"{wep['kind']}.png"
        embed.set_thumbnail(url=f"attachment://{fname}")
        await interaction.response.send_message(
            embed=embed, file=discord.File(icon, filename=fname)
        )
        return
    await interaction.response.send_message(body)


async def _reply_salvage(interaction: discord.Interaction, weapon: str) -> None:
    result = hunt.salvage(interaction.user.id, weapon)
    if not result.get("ok"):
        await interaction.response.send_message(
            result.get("error") or "Could not salvage.", ephemeral=True
        )
        return
    rar = result.get("rarity") or hunt.COMMON
    mark = hunt.rarity_mark(rar) if rar else rar
    body = (
        f"Salvaged `{result['wid']}` {result['emoji']} **{result['name']}** {mark}.\n"
        f"Shards gained **{result['gained']}** \u00b7 total **{result['shards']}**"
    )
    color = hunt.RARITY_EMBED.get(rar, hunt.EMBED_GOLD)
    await interaction.response.send_message(embed=_embed("\u2726 Salvage", body, color=color))


class ZooMenuView(discord.ui.View):
    def __init__(self, actor_id: int):
        super().__init__(timeout=180)
        self.actor_id = actor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "This zoo is not yours. Run `/zoo`.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Checklist", style=discord.ButtonStyle.secondary)
    async def checklist_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(embed=_checklist_embed(interaction))


class InvOpenView(discord.ui.View):
    def __init__(self, actor_id: int):
        super().__init__(timeout=180)
        self.actor_id = actor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "This inventory is not yours. Run `/inv`.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Lootbox", style=discord.ButtonStyle.primary)
    async def lootbox_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await _reply_lootbox(interaction)

    @discord.ui.button(label="Crate", style=discord.ButtonStyle.primary)
    async def crate_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await _reply_crate(interaction)
