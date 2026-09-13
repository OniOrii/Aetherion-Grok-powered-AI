"""Administrator /reactionrole commands."""
from __future__ import annotations

import logging

import discord

from .reaction_roles import (
    get_panel,
    latest_panel_id,
    list_panels,
    parse_emoji_input,
    remove_mapping,
    set_mapping,
    upsert_panel,
)

logger = logging.getLogger("aetherion.slash_reactionrole")


def is_administrator(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, "guild_permissions", None)
    return bool(perms and perms.administrator)


def _parse_message_id(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if "/channels/" in text:
        text = text.rsplit("/", 1)[-1]
    try:
        return int(text)
    except ValueError:
        return None


async def _fetch_message(guild: discord.Guild, message_id: int, preferred_channel=None):
    if preferred_channel is not None:
        try:
            return await preferred_channel.fetch_message(message_id)
        except discord.HTTPException:
            pass
    panel = get_panel(guild.id, message_id)
    if panel:
        channel = guild.get_channel(int(panel.get("channel_id") or 0))
        if channel is not None:
            try:
                return await channel.fetch_message(message_id)
            except discord.HTTPException:
                pass
    for channel in list(guild.text_channels)[:40]:
        try:
            return await channel.fetch_message(message_id)
        except discord.HTTPException:
            continue
    return None


def register_reactionrole(tree, is_guild_allowed) -> None:
    group = discord.app_commands.Group(
        name="reactionrole",
        description="Set up reaction roles. Administrators only.",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    async def _gate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return False
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return False
        if not is_administrator(interaction):
            await interaction.response.send_message(
                "Only Discord Administrators can set up reaction roles.", ephemeral=True
            )
            return False
        return True

    @group.command(name="post", description="Post a reaction-role message in this channel.")
    @discord.app_commands.describe(text="Text on the message people will react to")
    async def post_cmd(interaction: discord.Interaction, text: str = "React to pick a color"):
        if not await _gate(interaction):
            return
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message("Use this in a text channel.", ephemeral=True)
            return
        me = interaction.guild.me
        perms = channel.permissions_for(me) if me else None
        if perms is None or not perms.send_messages or not perms.add_reactions:
            await interaction.response.send_message(
                "I need **Send Messages** and **Add Reactions** here.",
                ephemeral=True,
            )
            return
        body = (text or "React to pick a color").strip()
        message = await channel.send(body)
        upsert_panel(interaction.guild.id, message.id, channel.id, unique=True)
        await interaction.response.send_message(
            (
                f"Posted {message.jump_url}\n"
                "Now run `/reactionrole add` for each color. "
                "People can only keep one color from this message."
            ),
            ephemeral=True,
        )

    @group.command(name="add", description="Tie an emoji on a message to a role.")
    @discord.app_commands.describe(
        emoji="Emoji people should click",
        role="Role they get",
        message="Message ID or link. Leave empty to use the last posted panel.",
    )
    async def add_cmd(
        interaction: discord.Interaction,
        emoji: str,
        role: discord.Role,
        message: str | None = None,
    ):
        if not await _gate(interaction):
            return
        guild = interaction.guild
        parsed = parse_emoji_input(emoji)
        if parsed is None:
            await interaction.response.send_message("That emoji is not valid.", ephemeral=True)
            return
        emoji_key, react_with = parsed
        mid = _parse_message_id(message) or latest_panel_id(guild.id)
        if mid is None:
            await interaction.response.send_message(
                "Post a panel first with `/reactionrole post`.", ephemeral=True
            )
            return
        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "Pick a normal server role, not @everyone or a bot role.", ephemeral=True
            )
            return
        me = guild.me
        if me is None or not me.guild_permissions.manage_roles:
            await interaction.response.send_message("I need **Manage Roles**.", ephemeral=True)
            return
        if me.top_role <= role:
            await interaction.response.send_message(
                f"Move my role above **{role.name}** so I can assign it.",
                ephemeral=True,
            )
            return
        target = await _fetch_message(guild, mid, interaction.channel)
        if target is None:
            await interaction.response.send_message(
                "I could not find that message. Use the message ID or link.",
                ephemeral=True,
            )
            return
        try:
            await target.add_reaction(react_with)
        except discord.HTTPException:
            await interaction.response.send_message(
                "I could not add that emoji. Use a unicode emoji or a server emoji I can see.",
                ephemeral=True,
            )
            return
        set_mapping(guild.id, target.id, target.channel.id, emoji_key, role.id)
        await interaction.response.send_message(
            (
                f"React {emoji} on {target.jump_url} to get {role.mention}.\n"
                "Only one color from that message at a time."
            ),
            ephemeral=True,
        )

    @group.command(name="remove", description="Stop an emoji from giving a role.")
    @discord.app_commands.describe(
        emoji="Emoji to unlink",
        message="Message ID or link. Leave empty to use the last posted panel.",
    )
    async def remove_cmd(
        interaction: discord.Interaction,
        emoji: str,
        message: str | None = None,
    ):
        if not await _gate(interaction):
            return
        parsed = parse_emoji_input(emoji)
        if parsed is None:
            await interaction.response.send_message("That emoji is not valid.", ephemeral=True)
            return
        emoji_key, _react_with = parsed
        mid = _parse_message_id(message) or latest_panel_id(interaction.guild.id)
        if mid is None:
            await interaction.response.send_message("No reaction-role panel found.", ephemeral=True)
            return
        if not remove_mapping(interaction.guild.id, mid, emoji_key):
            await interaction.response.send_message("That emoji was not set on that message.", ephemeral=True)
            return
        await interaction.response.send_message("Removed that reaction role.", ephemeral=True)

    @group.command(name="list", description="Show reaction roles on this server.")
    async def list_cmd(interaction: discord.Interaction):
        if not await _gate(interaction):
            return
        panels = list_panels(interaction.guild.id)
        if not panels:
            await interaction.response.send_message("No reaction roles set up yet.", ephemeral=True)
            return
        lines = []
        for mid, panel in panels.items():
            mapping = (panel or {}).get("map") or {}
            if not mapping:
                continue
            pairs = []
            for key, rid in mapping.items():
                role = interaction.guild.get_role(int(rid))
                label = role.mention if role else f"`{rid}`"
                pairs.append(f"{key} → {label}")
            lines.append(f"`{mid}`: " + ", ".join(pairs))
        await interaction.response.send_message(
            "\n".join(lines)[:1900] or "No reaction roles set up yet.",
            ephemeral=True,
        )

    tree.add_command(group)
