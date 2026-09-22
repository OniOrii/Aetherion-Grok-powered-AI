"""Owner-only /status. Hidden from non-admins. Locked to Ori's Discord ID."""
from __future__ import annotations

import logging

import discord

from .presence import (
    DEFAULT_ROTATION,
    ROTATION_SECONDS,
    apply_presence,
    enable_rotation,
    is_status_owner,
    load_presence,
    pin_presence,
)

logger = logging.getLogger("aetherion.slash_status")


def register_status(tree, is_guild_allowed) -> None:
    @tree.command(name="status", description="Set or rotate Aetherion's status bubble. Ori only.")
    @discord.app_commands.describe(
        text="Status text. Leave empty to see the current status or to resume rotation.",
        kind="How the status is shown",
        rotate="On = cycle the default bubbles. Off = pin this text.",
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
        text: str | None = None,
        kind: discord.app_commands.Choice[str] | None = None,
        rotate: bool | None = None,
    ):
        if not is_status_owner(getattr(interaction.user, "id", None)):
            await interaction.response.send_message("Only Ori can change Aetherion's status.", ephemeral=True)
            return
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return

        body = (text or "").strip()
        selected = kind.value if kind else "custom"

        if rotate is True:
            stored = enable_rotation(0)
            try:
                stored = await apply_presence(interaction.client, stored["kind"], stored["text"])
            except Exception:
                logger.exception("status rotate apply failed")
                await interaction.response.send_message("Rotation is on, but Discord rejected the presence update.", ephemeral=True)
                return
            await interaction.response.send_message(
                f"Rotating **{len(DEFAULT_ROTATION)}** custom bubbles every **{ROTATION_SECONDS}s**. Now **{stored['text']}**.",
                ephemeral=True,
            )
            return

        if body:
            stored = pin_presence(selected, body)
            try:
                stored = await apply_presence(interaction.client, stored["kind"], stored["text"])
            except Exception:
                logger.exception("status apply failed")
                await interaction.response.send_message("Saved, but Discord rejected the presence update.", ephemeral=True)
                return
            label = stored["kind"]
            shown = stored["text"]
            if label == "custom":
                note = f"Pinned custom bubble to **{shown}**. Rotation is off."
            else:
                note = f"Pinned status to **{label} {shown}**. Rotation is off."
            await interaction.response.send_message(note, ephemeral=True)
            return

        current = load_presence()
        mode = "rotating" if current.get("rotate", True) else "pinned"
        shown = current["text"]
        await interaction.response.send_message(
            f"Current status is **{mode}**: **{shown}**.",
            ephemeral=True,
        )
