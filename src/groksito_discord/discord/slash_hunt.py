"""Ori-only WIP slash commands for Aetherion Hunt Test 1."""
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


async def _suggest_animals(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    if not _is_ori(interaction):
        return []
    needle = (current or "").strip().lower()
    out: list[discord.app_commands.Choice[str]] = []
    for aid, name, emoji, rarity in hunt.ANIMALS:
        hay = f"{aid} {name} {rarity}"
        if needle and needle not in hay.lower() and needle not in name.lower():
            continue
        out.append(
            discord.app_commands.Choice(
                name=f"{emoji} {name} ({hunt.RARITY_LABEL[rarity]})",
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
        aid = result["animal_id"]
        rarity = hunt.RARITY_LABEL[hunt.rarity_of(aid)]
        first = " New to the menagerie." if result.get("new") else ""
        pocket = ai_coins.coins(f"**{int(result['balance']):,}**")
        body = (
            f"You found **{hunt.animal_label(aid)}** · {rarity}.{first}\n"
            f"Owned: **{result['count']}**\n"
            f"Pocket · {pocket}\n"
            f"Hunt cost {ai_coins.coins(hunt.HUNT_COST)}."
        )
        await interaction.response.send_message(embed=_embed("\u2726 Hunt", body))

    @tree.command(name="zoo", description="WIP Ori only. Show hunted animals.")
    @discord.app_commands.default_permissions(administrator=True)
    async def zoo_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        snap = hunt.snapshot(interaction.user.id)
        lines = hunt.zoo_lines(snap["zoo"], snap["xp"])
        total = sum(int(n) for n in snap["zoo"].values())
        kinds = len(snap["zoo"])
        header = f"{kinds} kinds · {total} animals\n\n"
        body = header + "\n".join(lines)
        if len(body) > 3900:
            body = body[:3890] + "\n\u2026"
        await interaction.response.send_message(embed=_embed("\u2726 Menagerie", body))

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
            f"Pocket · {pocket}"
        )
        await interaction.response.send_message(embed=_embed("\u2726 Sold", body))

    @sell_slash.autocomplete("animal")
    async def sell_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_animals(interaction, current)

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
        body = "\n".join(hunt.team_lines(snap["team"], snap["xp"], snap["zoo"]))
        await interaction.response.send_message(embed=_embed("\u2726 Team", body))

    @team_slash.autocomplete("animal")
    async def team_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_animals(interaction, current)

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
        you = " · ".join(hunt.fighter_line(pet) for pet in result["player"])
        foe = " · ".join(hunt.fighter_line(pet) for pet in result["enemy"])
        log = "\n".join(result["log"]) or "No blows landed."
        if result["payout"]:
            pay = ai_coins.won_line(int(result["payout"]))
        elif outcome == "draw":
            pay = "Push"
        else:
            pay = "No coin payout"
        pocket = ai_coins.coins(f"**{int(result['balance']):,}**")
        body = (
            f"**You** {you}\n"
            f"**Wild** {foe}\n\n"
            f"{log}\n\n"
            f"Team XP +{result['xp_gain']} · {pay}\n"
            f"Pocket · {pocket}"
        )
        await interaction.response.send_message(
            embed=_embed(f"\u2726 Battle · {headline}", body, color)
        )
