"""Public /top. Lifetime activity ranks for this server."""
from __future__ import annotations

import discord

from . import activity
from .brand import GOLD, stamp


def _who(guild: discord.Guild, user_id: int) -> str:
    member = guild.get_member(int(user_id))
    if member is not None:
        return member.mention
    return f"`{user_id}`"


def _score(sort: str, row: dict) -> str:
    if sort == "voice":
        return activity.format_voice(int(row.get("voice_seconds") or 0))
    if sort == "level":
        return f"Lv {int(row.get('level') or 0)} \u00b7 {int(row.get('xp') or 0):,} XP"
    return f"{int(row.get('messages') or 0):,} msg"


def top_embed(guild: discord.Guild, sort: str, bot_user=None, viewer_id: int | None = None) -> discord.Embed:
    board = activity.leaderboard(guild.id, sort=sort, limit=10, viewer_id=viewer_id)
    label = {"messages": "Messages", "voice": "Voice", "level": "Level"}.get(board["sort"], "Messages")
    embed = discord.Embed(
        title=f"\u2726 {guild.name} \u00b7 Top {label}",
        description="Lifetime on this server.",
        color=GOLD,
    )
    rows = list(board.get("rows") or [])
    if not rows:
        embed.add_field(name="Board", value="No activity tracked yet.", inline=False)
        return stamp(embed, bot_user, extra="activity \u00b7 this server")
    lines = []
    for index, row in enumerate(rows, start=1):
        lines.append(f"**{index}.** {_who(guild, row['user_id'])} \u00b7 {_score(board['sort'], row)}")
    embed.add_field(name=f"Top {len(rows)}", value="\n".join(lines)[:1024], inline=False)
    rank = board.get("viewer_rank")
    total = int(board.get("total") or 0)
    if viewer_id and rank:
        embed.add_field(name="You", value=f"#{rank} of {total}", inline=True)
    started = board.get("started")
    if started:
        embed.add_field(name="Tracked since", value=str(started), inline=True)
    return stamp(embed, bot_user, extra="activity \u00b7 this server")


def register_top(tree, is_guild_allowed) -> None:
    @tree.command(name="top", description="Activity ranks on this server. Messages, voice, or level.")
    @discord.app_commands.describe(sort="What to rank by. Default is messages.")
    @discord.app_commands.choices(
        sort=[
            discord.app_commands.Choice(name="Messages", value="messages"),
            discord.app_commands.Choice(name="Voice", value="voice"),
            discord.app_commands.Choice(name="Level", value="level"),
        ]
    )
    @discord.app_commands.guild_only()
    async def top_slash(
        interaction: discord.Interaction,
        sort: discord.app_commands.Choice[str] | None = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Use /top in a server.", ephemeral=True)
            return
        if not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        key = sort.value if sort else "messages"
        bot_user = getattr(interaction.client, "user", None)
        embed = top_embed(interaction.guild, key, bot_user, viewer_id=interaction.user.id)
        await interaction.response.send_message(embed=embed)
