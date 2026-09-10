"""Administrator /purge command (Dyno-style bulk delete)."""
from __future__ import annotations

import logging
from typing import Optional

import discord

logger = logging.getLogger("aetherion.slash_purge")

MIN_PURGE = 1
MAX_PURGE = 100
CONFIRM_TIMEOUT = 30


def clamp_purge_amount(amount: int) -> int:
    try:
        n = int(amount)
    except (TypeError, ValueError):
        return MIN_PURGE
    return max(MIN_PURGE, min(MAX_PURGE, n))


def is_administrator(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


def skip_pinned(message: discord.Message) -> bool:
    return not bool(getattr(message, "pinned", False))


class PurgeConfirmView(discord.ui.View):
    def __init__(self, *, actor_id: int, channel, amount: int, reason: str):
        super().__init__(timeout=CONFIRM_TIMEOUT)
        self.actor_id = actor_id
        self.channel = channel
        self.amount = amount
        self.reason = reason
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "Only the administrator who ran /purge can confirm this.",
                ephemeral=True,
            )
            return False
        return True

    def _disable(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def on_timeout(self) -> None:
        self._disable()
        if self.message is None:
            return
        try:
            await self.message.edit(content="Purge timed out. Nothing was deleted.", view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Confirm purge", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._disable()
        await interaction.response.edit_message(
            content=f"Purging up to **{self.amount}** messages…",
            view=self,
        )
        self.stop()
        try:
            deleted = await self.channel.purge(
                limit=self.amount,
                check=skip_pinned,
                reason=self.reason,
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                content="Discord blocked the purge. I need **Manage Messages** and **Read Message History** here.",
                view=self,
            )
            return
        except discord.HTTPException:
            logger.exception("purge failed")
            await interaction.edit_original_response(
                content="Could not purge those messages. Messages older than 14 days cannot be bulk-deleted. Try a smaller number.",
                view=self,
            )
            return

        n = len(deleted)
        await interaction.edit_original_response(
            content=(
                f"Deleted **{n}** message{'s' if n != 1 else ''}. "
                "Pinned messages were kept."
            ),
            view=self,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._disable()
        self.stop()
        await interaction.response.edit_message(content="Purge cancelled.", view=self)


def register_purge(tree, is_guild_allowed) -> None:
    @tree.command(
        name="purge",
        description="Delete up to 100 recent messages in this channel. Administrators only.",
    )
    @discord.app_commands.describe(amount="How many messages to delete (1-100)")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.guild_only()
    async def purge_slash(interaction: discord.Interaction, amount: int = 10):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use /purge in a server channel.", ephemeral=True
            )
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if not is_administrator(interaction):
            await interaction.response.send_message(
                "Only Discord Administrators can use /purge.", ephemeral=True
            )
            return

        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "I can only purge text channels.", ephemeral=True
            )
            return

        me = interaction.guild.me
        bot_perms = channel.permissions_for(me) if me is not None else None
        if bot_perms is None or not bot_perms.manage_messages:
            await interaction.response.send_message(
                "I need **Manage Messages** in this channel to purge.",
                ephemeral=True,
            )
            return
        if not bot_perms.read_message_history:
            await interaction.response.send_message(
                "I need **Read Message History** in this channel to purge.",
                ephemeral=True,
            )
            return

        count = clamp_purge_amount(amount)
        view = PurgeConfirmView(
            actor_id=interaction.user.id,
            channel=channel,
            amount=count,
            reason=f"Aetherion /purge by {interaction.user}",
        )
        await interaction.response.send_message(
            (
                f"Delete up to **{count}** recent message{'s' if count != 1 else ''} "
                "in this channel?\n"
                "Pinned messages are kept. This cannot be undone."
            ),
            view=view,
            ephemeral=True,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = None
