"""Ori-only supply grant for Hunt Test 3."""
from __future__ import annotations

import discord

from ..llm.persona import creator_is_author
from . import aether_hunt as hunt
from . import aether_hunt_ext  # noqa: F401

ORIONLY = "Hunt is a WIP. Only Ori can use these commands."


def register_supply(tree, is_guild_allowed) -> None:
    @tree.command(name="givesupply", description="WIP Ori only. Grant lootboxes or weapon crates to yourself.")
    @discord.app_commands.describe(item="lootbox or crate", amount="How many to grant (1-100)")
    @discord.app_commands.choices(
        item=[
            discord.app_commands.Choice(name="Lootbox", value="lootbox"),
            discord.app_commands.Choice(name="Weapon crate", value="crate"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def givesupply_slash(
        interaction: discord.Interaction,
        item: discord.app_commands.Choice[str],
        amount: int = 1,
    ):
        if not creator_is_author(getattr(interaction.user, "id", None)):
            await interaction.response.send_message(ORIONLY, ephemeral=True)
            return
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        result = hunt.grant_supplies(interaction.user.id, item.value, amount)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not grant that.", ephemeral=True
            )
            return
        mark = "\U0001f4e6" if result["kind"] == "lootbox" else "\U0001fab5"
        word = result["label"] + ("" if result["amount"] == 1 else "s")
        await interaction.response.send_message(
            f"{mark} Granted **{result['amount']}** {word}. You now have **{result['left']}**."
        )
