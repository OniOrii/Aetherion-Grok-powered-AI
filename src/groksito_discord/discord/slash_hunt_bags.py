"""Hunt /inv /weapon /raid slash registration."""
from __future__ import annotations

import asyncio
import logging

import discord

from . import aether_gear as gear
from . import aether_hunt as hunt
from .slash_hunt_ops import (
    _avatar_url,
    _battle_embed,
    _battle_file,
    _battle_total,
    _display_name,
    _embed,
    _gate,
    _playable_frames,
    _suggest_team,
)
from .slash_hunt_acts import _armory_pack, _suggest_weapons
from .slash_hunt_open import (
    InvOpenView,
    _reply_crate,
    _reply_equip,
    _reply_lootbox,
    _reply_salvage,
    _reply_use,
)

logger = logging.getLogger("aetherion.slash_hunt")


def register_hunt_bags(tree, is_guild_allowed) -> None:
    @tree.command(name="inv", description="WIP Ori only. Bags, gems, open lootbox/crate, use, equip, salvage.")
    @discord.app_commands.describe(
        action="show, lootbox, crate, use, equip, or salvage",
        gem="hunting, lucky, empower, or prism",
        rarity="optional gem tier (common…fabled)",
        weapon="Weapon id or name from /inv",
        animal="Team animal (one of your 3 battle slots)",
    )
    @discord.app_commands.choices(
        action=[
            discord.app_commands.Choice(name="Show", value="show"),
            discord.app_commands.Choice(name="Lootbox", value="lootbox"),
            discord.app_commands.Choice(name="Crate", value="crate"),
            discord.app_commands.Choice(name="Use gem", value="use"),
            discord.app_commands.Choice(name="Equip", value="equip"),
            discord.app_commands.Choice(name="Salvage", value="salvage"),
        ],
        gem=[
            discord.app_commands.Choice(name="Hunting", value="hunting"),
            discord.app_commands.Choice(name="Lucky", value="lucky"),
            discord.app_commands.Choice(name="Empowering", value="empower"),
            discord.app_commands.Choice(name="Prism", value="prism"),
        ],
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def inv_slash(
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str] | None = None,
        gem: discord.app_commands.Choice[str] | None = None,
        rarity: str | None = None,
        weapon: str | None = None,
        animal: str | None = None,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        verb = action.value if action else "show"
        if verb == "lootbox":
            await _reply_lootbox(interaction)
            return
        if verb == "crate":
            await _reply_crate(interaction)
            return
        if verb == "use":
            if gem is None:
                await interaction.response.send_message(
                    "Pick a gem for `/inv use`.", ephemeral=True
                )
                return
            await _reply_use(interaction, gem.value, rarity)
            return
        if verb == "equip":
            if not weapon or not animal:
                await interaction.response.send_message(
                    "Name the weapon and team animal for `/inv equip`.", ephemeral=True
                )
                return
            await _reply_equip(interaction, weapon, animal)
            return
        if verb == "salvage":
            if not weapon:
                await interaction.response.send_message(
                    "Name the weapon for `/inv salvage`.", ephemeral=True
                )
                return
            await _reply_salvage(interaction, weapon)
            return
        snap = hunt.snapshot(interaction.user.id)
        pack = _armory_pack(interaction.user.id, snap)
        text = gear.inventory_text(_display_name(interaction), pack)
        await interaction.response.send_message(
            embed=_embed("\u2726 Inventory", text),
            view=InvOpenView(interaction.user.id),
        )

    @inv_slash.autocomplete("animal")
    async def inv_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_team(interaction, current)

    @inv_slash.autocomplete("weapon")
    async def inv_weapon_ac(interaction: discord.Interaction, current: str):
        return await _suggest_weapons(interaction, current)

    @tree.command(name="weapon", description="WIP Ori only. Armory board, or inspect a crate weapon by id.")
    @discord.app_commands.describe(id="Weapon inventory id — omit for the armory list")
    @discord.app_commands.default_permissions(administrator=True)
    async def weapon_slash(interaction: discord.Interaction, id: str | None = None):
        if not await _gate(interaction, is_guild_allowed):
            return
        snap = hunt.snapshot(interaction.user.id)
        pack = _armory_pack(interaction.user.id, snap)
        name = _display_name(interaction)
        if id:
            result = hunt.weapon_detail(interaction.user.id, id, name)
            if not result.get("ok"):
                await interaction.response.send_message(
                    result.get("error") or "Could not open that weapon.", ephemeral=True
                )
                return
            body = result["body"]
            if len(body) > 3900:
                body = body[:3890] + "\n\u2026"
            title = f"{result.get('emoji', '')} {name}'s {result.get('name', 'weapon')}".strip()
            embed = _embed(title, body)
            wep = result.get("wep") or {}
            if wep.get("kind") and hasattr(gear, "weapon_icon_png"):
                icon = gear.weapon_icon_png(str(wep["kind"]), wep.get("rarity"))
                fname = f"{wep['kind']}.png"
                embed.set_thumbnail(url=f"attachment://{fname}")
                await interaction.response.send_message(
                    embed=embed, file=discord.File(icon, filename=fname)
                )
                return
            await interaction.response.send_message(embed=embed)
            return
        rowish = {"nicks": snap.get("nicks") or {}}
        body = hunt.weapon_board(name, pack, rowish)
        if len(body) > 3900:
            body = body[:3890] + "\n\u2026"
        await interaction.response.send_message(embed=_embed("\u2726 Armory", body))

    @weapon_slash.autocomplete("id")
    async def weapon_id_ac(interaction: discord.Interaction, current: str):
        return await _suggest_weapons(interaction, current)

    @tree.command(name="raid", description="WIP Ori only. Spend tickets for Ember/Void/Crown Rift PvE.")
    @discord.app_commands.describe(
        tier="Easy Ember / Hard Void / Nightmare Crown",
        craft="Spend 30 shards for 1 raid ticket instead of fighting",
    )
    @discord.app_commands.choices(
        tier=[
            discord.app_commands.Choice(name="Easy · Ember Rift (1 ticket)", value="easy"),
            discord.app_commands.Choice(name="Hard · Void Rift (2 tickets)", value="hard"),
            discord.app_commands.Choice(name="Nightmare · Crown Rift (3 tickets)", value="nightmare"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def raid_slash(
        interaction: discord.Interaction,
        tier: str = "easy",
        craft: bool = False,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        if craft:
            result = hunt.craft_raid_ticket(interaction.user.id)
            if not result.get("ok"):
                await interaction.response.send_message(
                    result.get("error") or "Could not craft ticket.", ephemeral=True
                )
                return
            body = (
                f"Crafted **1** raid ticket for **{result['spent']}** shards.\n"
                f"Tickets **{result['tickets']}** · shards **{result['shards']}**"
            )
            await interaction.response.send_message(embed=_embed("\u2726 Raid ticket", body))
            return
        await interaction.response.defer()
        result = hunt.raid(interaction.user.id, tier=tier)
        if not result.get("ok"):
            await interaction.followup.send(result.get("error") or "Raid failed.", ephemeral=True)
            return
        name = _display_name(interaction)
        icon_url = _avatar_url(interaction)
        total = _battle_total(result)
        frames = _playable_frames(list(result.get("frames") or []))
        if not frames:
            frames = [{
                "turn": total,
                "player": result.get("player") or [],
                "enemy": result.get("enemy") or [],
                "lines": result.get("log") or [],
            }]
        spent = int(result.get("tickets_spent") or 1)
        left = int(result.get("tickets_left") or 0)
        label = result.get("tier_label") or "Easy"
        rift = result.get("rift") or "Ember Rift"
        ticket_note = f"{label} · {spent} ticket{'s' if spent != 1 else ''} spent · {left} left"
        author = {"name": f"{name} raids the {rift}!"}
        if icon_url:
            author["icon_url"] = icon_url

        def _raid_footer(res: dict) -> str:
            outcome = res.get("result") or "draw"
            rounds = max(1, int(res.get("rounds") or 1))
            turns = f"{rounds} turn" if rounds == 1 else f"{rounds} turns"
            rift_name = res.get("rift") or "rift"
            if outcome == "win":
                base = int(res.get("xp_base") or res.get("xp_gain") or 0)
                line = f"{rift_name} cleared in {turns}! Team gained {base}xp"
                if int(res.get("xp_bonus") or 0) > 0:
                    line += f" + {int(res['xp_bonus'])} bonus xp"
                if int(res.get("shard_bonus") or 0) > 0:
                    line += f" · +{int(res['shard_bonus'])} shards"
                for note in res.get("reward_notes") or []:
                    if note.startswith("+") and "shard" in note:
                        continue
                    line += f" | {note}"
                return line + f"\n{hunt.WIP_FOOTER}"
            if outcome == "lose":
                line = f"The rift held · {turns}"
            else:
                line = f"The rift stilled · {turns}"
            if int(res.get("shard_bonus") or 0) > 0:
                line += f" · +{int(res['shard_bonus'])} shards"
            return line + f"\n{hunt.WIP_FOOTER}"

        try:
            first = dict(frames[0])
            first["lines"] = [ticket_note] + list(first.get("lines") or [])
            embed0 = _battle_embed(name, result, first, final=len(frames) == 1, icon_url=icon_url)
            embed0.set_author(**author)
            if len(frames) == 1:
                embed0.set_footer(text=_raid_footer(result))
            msg = await interaction.followup.send(
                embed=embed0,
                file=_battle_file(first, total),
                wait=True,
            )
            for index, frame in enumerate(frames[1:], start=1):
                await asyncio.sleep(0.9)
                final = index == len(frames) - 1
                embed = _battle_embed(name, result, frame, final=final, icon_url=icon_url)
                embed.set_author(**author)
                if final:
                    embed.set_footer(text=_raid_footer(result))
                await msg.edit(embed=embed, attachments=[_battle_file(frame, total)])
        except Exception:
            logger.exception("raid animation failed")
            if hasattr(hunt, "battle_card"):
                body = hunt.battle_card(name, result)
            else:
                body = "\n".join(result.get("log") or ["Raid finished."])
            body += f"\n{_raid_footer(result)}"
            try:
                await interaction.edit_original_response(
                    content=None, embed=_embed("Raid", body), attachments=[]
                )
            except Exception:
                await interaction.followup.send(embed=_embed("Raid", body))
