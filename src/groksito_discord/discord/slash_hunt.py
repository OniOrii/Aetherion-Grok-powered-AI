"""Ori-only WIP slash commands for Aetherion Hunt Test 2."""
from __future__ import annotations

import logging

import discord

from ..llm.persona import creator_is_author
from . import ai_coins
from . import aether_hunt as hunt

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
                name=f"{emoji} {name} \u00d7{have}",
                value=name,
            )
        )
        if len(out) >= 25:
            break
    return out


def register_hunt(tree, is_guild_allowed) -> None:
    @tree.command(name="hunt", description="WIP Ori only. Hunt one Aetherion animal.")
    @discord.app_commands.default_permissions(administrator=True)
    async def hunt_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.hunt(interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Hunt failed.", ephemeral=True
            )
            return
        extras = [aid for aid in result.get("animals") or [] if aid != result["animal_id"]]
        line = hunt.hunt_catch_line(
            _display_name(interaction),
            result["animal_id"],
            extras,
            bool(result.get("lootbox")),
        )
        await interaction.response.send_message(line)

    @tree.command(name="zoo", description="WIP Ori only. Show hunted animals.")
    @discord.app_commands.default_permissions(administrator=True)
    async def zoo_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        snap = hunt.snapshot(interaction.user.id)
        board = hunt.zoo_board(
            _display_name(interaction),
            snap["zoo"],
            snap.get("caught") or snap["zoo"],
        )
        if len(board) > 1900:
            board = board[:1890] + "\n\u2026"
        await interaction.response.send_message(board)

    @tree.command(name="sell", description="WIP Ori only. Sell extra animals for Aether Coins.")
    @discord.app_commands.describe(animal="Animal name", count="How many to sell")
    @discord.app_commands.default_permissions(administrator=True)
    async def sell_slash(interaction: discord.Interaction, animal: str, count: int = 1):
        if not await _gate(interaction, is_guild_allowed):
            return
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
        await interaction.response.send_message(embed=_embed("\u2726 Sold", body))

    @sell_slash.autocomplete("animal")
    async def sell_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_owned(interaction, current)

    @tree.command(name="team", description="WIP Ori only. Set the three-animal battle team.")
    @discord.app_commands.describe(
        action="show, set, or clear",
        animal="Animal to put in the slot",
        slot="Team slot 1-3",
    )
    @discord.app_commands.choices(
        action=[
            discord.app_commands.Choice(name="Show", value="show"),
            discord.app_commands.Choice(name="Set", value="set"),
            discord.app_commands.Choice(name="Clear", value="clear"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def team_slash(
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str] | None = None,
        animal: str | None = None,
        slot: int = 1,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        verb = action.value if action else ("set" if animal else "show")
        if verb == "set":
            if not animal:
                await interaction.response.send_message(
                    "Name the animal to put on the team.", ephemeral=True
                )
                return
            result = hunt.set_team_slot(interaction.user.id, slot, animal)
            if not result.get("ok"):
                await interaction.response.send_message(
                    result.get("error") or "Could not update the team.", ephemeral=True
                )
                return
        elif verb == "clear":
            result = hunt.set_team_slot(interaction.user.id, slot, None)
            if not result.get("ok"):
                await interaction.response.send_message(
                    result.get("error") or "Could not clear that slot.", ephemeral=True
                )
                return
        snap = hunt.snapshot(interaction.user.id)
        body = "\n".join(
            hunt.team_lines(snap["team"], snap["xp"], snap["zoo"], snap.get("gear"))
        )
        owned = hunt.owned_catalog(snap["zoo"])
        if owned:
            picks = ", ".join(f"{emoji} {name}" for _aid, name, emoji, _rar in owned)
            body += f"\n\n**Owned** {picks}"
        else:
            body += "\n\nHunt something before you set a team."
        await interaction.response.send_message(embed=_embed("\u2726 Team", body))

    @team_slash.autocomplete("animal")
    async def team_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_owned(interaction, current)

    @tree.command(name="battle", description="WIP Ori only. Fight a wild team with your animals.")
    @discord.app_commands.default_permissions(administrator=True)
    async def battle_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.battle(interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Battle failed.", ephemeral=True
            )
            return
        outcome = result["result"]
        if outcome == "win":
            color = hunt.EMBED_WIN
            headline = "Win"
        elif outcome == "lose":
            color = hunt.EMBED_LOSE
            headline = "Loss"
        else:
            color = hunt.EMBED_GOLD
            headline = "Draw"
        if result["payout"]:
            pay = ai_coins.won_line(int(result["payout"]))
        elif outcome == "draw":
            pay = "Push"
        else:
            pay = "No coin payout"
        pocket = ai_coins.coins(f"**{int(result['balance']):,}**")
        body = hunt.battle_card(_display_name(interaction), result)
        body += f"\n{pay}\nPocket \u00b7 {pocket}"
        await interaction.response.send_message(
            embed=_embed(f"\u2726 Battle \u00b7 {headline}", body, color)
        )

    @tree.command(name="inv", description="WIP Ori only. Lootboxes, crates, gems, weapons.")
    @discord.app_commands.default_permissions(administrator=True)
    async def inv_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        snap = hunt.snapshot(interaction.user.id)
        text = hunt.gear.inventory_text(_display_name(interaction), snap.get("gear") or {})
        await interaction.response.send_message(text)

    @tree.command(name="lootbox", description="WIP Ori only. Open a lootbox for a hunt gem.")
    @discord.app_commands.default_permissions(administrator=True)
    async def lootbox_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.open_lootbox(interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "No lootbox.", ephemeral=True
            )
            return
        rar = hunt.RARITY_LABEL[result["rarity"]]
        kind = hunt.gear.GEM_BY_KIND[result["kind"]][1]
        line = (
            f"\U0001f48e | **{_display_name(interaction)}** opens a lootbox\n"
            f"\U0001f4e6 | and finds a **{rar} {kind}**!"
        )
        await interaction.response.send_message(line)

    @tree.command(name="crate", description="WIP Ori only. Open a weapon crate.")
    @discord.app_commands.default_permissions(administrator=True)
    async def crate_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.open_crate(interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "No crate.", ephemeral=True
            )
            return
        rar = hunt.RARITY_LABEL[result["rarity"]]
        line = (
            f"\U0001fab5 | **{_display_name(interaction)}** opens a weapon crate\n"
            f"{result['emoji']} | **{rar} {result['name']}** Q{result['quality']} +{result['atk']} ATK "
            f"(id `{result['wid']}`)"
        )
        await interaction.response.send_message(line)

    @tree.command(name="use", description="WIP Ori only. Activate a hunting, lucky, or empower gem.")
    @discord.app_commands.describe(gem="hunting, lucky, or empower", rarity="optional gem tier")
    @discord.app_commands.choices(
        gem=[
            discord.app_commands.Choice(name="Hunting", value="hunting"),
            discord.app_commands.Choice(name="Lucky", value="lucky"),
            discord.app_commands.Choice(name="Empowering", value="empower"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def use_slash(
        interaction: discord.Interaction,
        gem: discord.app_commands.Choice[str],
        rarity: str | None = None,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        rar = None
        if rarity:
            key = rarity.strip().lower()
            rar = key if key in hunt.RARITY_LABEL else None
        result = hunt.use_gem(interaction.user.id, gem.value, rar)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not use that gem.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{hunt.gear.GEM_BY_KIND[result['kind']][2]} | Activated "
            f"**{hunt.RARITY_LABEL[result['rarity']]} {result['label']}** "
            f"for **{result['left']}** hunts."
        )

    @tree.command(name="equip", description="WIP Ori only. Put a crate weapon on a team animal.")
    @discord.app_commands.describe(weapon="Weapon id or name from /inv", animal="Owned animal")
    @discord.app_commands.default_permissions(administrator=True)
    async def equip_slash(interaction: discord.Interaction, weapon: str, animal: str):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.equip_weapon(interaction.user.id, weapon, animal)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not equip.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"Equipped {result['label']} on {hunt.animal_label(result['animal_id'])}."
        )

    @equip_slash.autocomplete("animal")
    async def equip_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_owned(interaction, current)

    @equip_slash.autocomplete("weapon")
    async def equip_weapon_ac(interaction: discord.Interaction, current: str):
        if not _is_ori(interaction):
            return []
        snap = hunt.snapshot(interaction.user.id)
        needle = (current or "").strip().lower()
        out: list[discord.app_commands.Choice[str]] = []
        for wid, label, name in hunt.gear.owned_weapons(snap.get("gear") or {}):
            if needle and needle not in label.lower() and needle not in wid:
                continue
            out.append(discord.app_commands.Choice(name=f"#{wid} {label}", value=wid))
            if len(out) >= 25:
                break
        return out
