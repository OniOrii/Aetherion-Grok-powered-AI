"""Owner-only /status. Hidden from non-admins. Locked to Ori's Discord ID."""
from __future__ import annotations

import logging

import discord

from .presence import apply_presence, is_status_owner, save_presence

logger = logging.getLogger("aetherion.slash_status")


def register_status(tree, is_guild_allowed) -> None:
    @tree.command(name="status", description="Set Aetherion's status bubble. Ori only.")
    @discord.app_commands.describe(
        text="Status text shown on Aetherion's profile",
        kind="How the status is shown",
    )
    @discord.app_commands.choices(
        kind=[
            discord.app_commands.Choice(name="Custom bubble (like Meh)", value="custom"),
            discord.app_commands.Choice(name="Watching", value="watching"),
            discord.app_commands.Choice(name="Playing", value="playing"),
            discord.app_commands.Choice(name="Listening", value="listening"),
            discord.app_commands.Choice(name="Competing", value="competing"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def status_slash(
        interaction: discord.Interaction,
        text: str,
        kind: discord.app_commands.Choice[str] | None = None,
    ):
        if not is_status_owner(getattr(interaction.user, "id", None)):
            await interaction.response.send_message("Only Ori can change Aetherion's status.", ephemeral=True)
            return
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        body = (text or "").strip()
        if not body:
            await interaction.response.send_message("Give me the status text.", ephemeral=True)
            return
        selected = (kind.value if kind else "custom")
        save_presence(selected, body)
        try:
            stored = await apply_presence(interaction.client, selected, body)
        except Exception:
            logger.exception("status apply failed")
            await interaction.response.send_message("Saved, but Discord rejected the presence update.", ephemeral=True)
            return
        label = stored["kind"]
        shown = stored["text"]
        if label == "custom":
            note = f"Custom bubble set to **{shown}**."
        else:
            note = f"Status set to **{label} {shown}**."
        await interaction.response.send_message(note, ephemeral=True)
