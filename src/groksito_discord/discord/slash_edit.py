"""Ori-only commands to edit messages Aetherion already posted."""
from __future__ import annotations

import logging
import re
from typing import Optional

import discord

from ..llm.persona import creator_is_author

logger = logging.getLogger("aetherion.slash_edit")

MAX_EDIT = 2000
_LINK_RE = re.compile(
    r"(?:https?://)?(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+|@me)/(\d+)/(\d+)",
    re.IGNORECASE,
)


def parse_message_ref(raw: str | None) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse a Discord message link or bare ID.

    Returns (guild_id_or_none, channel_id_or_none, message_id_or_none).
    """
    if raw is None:
        return None, None, None
    text = raw.strip()
    if not text:
        return None, None, None
    match = _LINK_RE.search(text)
    if match:
        guild_raw, channel_raw, message_raw = match.groups()
        guild_id = None if guild_raw == "@me" else int(guild_raw)
        return guild_id, int(channel_raw), int(message_raw)
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    try:
        return None, None, int(text)
    except ValueError:
        return None, None, None


def clamp_edit_text(text: str | None) -> str:
    return (text or "").strip()[:MAX_EDIT]


def is_ori(interaction: discord.Interaction) -> bool:
    return creator_is_author(getattr(interaction.user, "id", None))


def is_bot_message(message: discord.Message, client: discord.Client) -> bool:
    author = getattr(message, "author", None)
    me = getattr(client, "user", None)
    if author is None or me is None:
        return False
    return int(author.id) == int(me.id)


async def resolve_target_message(
    interaction: discord.Interaction, raw: str
) -> Optional[discord.Message]:
    _guild_id, channel_id, message_id = parse_message_ref(raw)
    if message_id is None:
        return None
    channel = None
    client = interaction.client
    if channel_id is not None:
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except discord.HTTPException:
                channel = None
    if channel is None:
        channel = interaction.channel
    if channel is None or not hasattr(channel, "fetch_message"):
        return None
    try:
        return await channel.fetch_message(message_id)
    except discord.HTTPException:
        return None


async def apply_edit(message: discord.Message, new_text: str) -> str | None:
    try:
        await message.edit(content=new_text)
    except discord.Forbidden:
        return "Discord blocked the edit. I can only change messages I posted."
    except discord.HTTPException:
        logger.exception("edit message failed")
        return "Could not edit that message."
    return None


class EditAetherionModal(discord.ui.Modal, title="Edit Aetherion text"):
    def __init__(self, target: discord.Message):
        super().__init__()
        self.target = target
        current = (target.content or "")[:MAX_EDIT]
        self.body = discord.ui.TextInput(
            label="New text",
            style=discord.TextStyle.paragraph,
            default=current,
            max_length=MAX_EDIT,
            required=True,
        )
        self.add_item(self.body)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not is_ori(interaction):
            await interaction.response.send_message("Only Ori can edit Aetherion text.", ephemeral=True)
            return
        if not is_bot_message(self.target, interaction.client):
            await interaction.response.send_message(
                "I can only edit messages Aetherion posted.", ephemeral=True
            )
            return
        new_text = clamp_edit_text(str(self.body.value))
        if not new_text:
            await interaction.response.send_message("Give me the replacement text.", ephemeral=True)
            return
        err = await apply_edit(self.target, new_text)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message(
            f"Updated {self.target.jump_url}", ephemeral=True
        )


def register_edit(tree, is_guild_allowed) -> None:
    async def _gate(interaction: discord.Interaction) -> bool:
        if not is_ori(interaction):
            await interaction.response.send_message(
                "Only Ori can edit Aetherion text.", ephemeral=True
            )
            return False
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return False
        return True

    @tree.command(
        name="edit",
        description="Ori only. Edit text Aetherion already posted.",
    )
    @discord.app_commands.describe(
        message="Message link or ID of the Aetherion message",
        text="Replacement text. Leave empty to open an editor with the current text.",
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def edit_slash(
        interaction: discord.Interaction,
        message: str,
        text: Optional[str] = None,
    ):
        if not await _gate(interaction):
            return
        target = await resolve_target_message(interaction, message)
        if target is None:
            await interaction.response.send_message(
                "I could not find that message. Use the message link, or run this in the same channel as the message ID.",
                ephemeral=True,
            )
            return
        if not is_bot_message(target, interaction.client):
            await interaction.response.send_message(
                "That is not one of my messages. I can only edit text Aetherion posted.",
                ephemeral=True,
            )
            return
        replacement = clamp_edit_text(text)
        if not replacement:
            await interaction.response.send_modal(EditAetherionModal(target))
            return
        err = await apply_edit(target, replacement)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        await interaction.response.send_message(f"Updated {target.jump_url}", ephemeral=True)

    @tree.context_menu(name="Edit Aetherion text")
    @discord.app_commands.default_permissions(administrator=True)
    async def edit_context(interaction: discord.Interaction, message: discord.Message):
        if not await _gate(interaction):
            return
        if not is_bot_message(message, interaction.client):
            await interaction.response.send_message(
                "That is not one of my messages. I can only edit text Aetherion posted.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(EditAetherionModal(message))
