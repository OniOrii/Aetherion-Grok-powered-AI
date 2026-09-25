"""Public /top. Lifetime activity ranks for this server."""
from __future__ import annotations

import logging

import discord

from . import activity
from .brand import GOLD, stamp

logger = logging.getLogger("aetherion.slash_top")

SORT_LABELS = {
    "messages": "messages",
    "voice": "voice time",
    "level": "level",
}


def _who(guild: discord.Guild, user_id: int) -> str:
    member = guild.get_member(user_id)
    if member is not None:
        return member.mention
    return f"`{user_id}`"


def _score(row: dict, sort: str) -> str:
    if sort == "voice":
        return activity.format_voice(int(row.get("voice_seconds") or 0))
    if sort == "level":
        return f"Lv {int(row.get('level') or 0)}"
    return f"{int(row.get('messages') or 0):,}"


def top_embed(guild: discord.Guild, board: dict, bot_user=None) -> discord.Embed:
    sort = board.get("sort") or "messages"
    label = SORT_LABELS.get(sort, "messages")
    rows = board.get("rows") or []
    total = int(board.get("total") or 0)
    viewer_rank = board.get("viewer_rank")
    embed = discord.Embed(
        title=f"\u2726 {guild.name} \u00b7 Top",
        description=f"Lifetime \u00b7 sorted by **{label}** \u00b7 {total} tracked",
        color=GOLD,
    )
    if not rows:
        embed.add_field(
            name="Board",
            value="No activity yet. Chat or sit in voice and it starts counting.",
            inline=False,
        )
    else:
        medals = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}
        lines = []
        for i, row in enumerate(rows, start=1):
            mark = medals.get(i, f"`{i}.`")
            lines.append(f"{mark} {_who(guild, int(row['user_id']))} \u00b7 **{_score(row, sort)}**")
        embed.add_field(name="Top 10", value="\n".join(lines)[:1024], inline=False)
    if viewer_rank:
        embed.add_field(name="You", value=f"#{viewer_rank} of {total}", inline=True)
    elif total:
        embed.add_field(name="You", value="Unranked \u00b7 no tracked activity yet", inline=True)
    return stamp(embed, bot_user, extra="activity \u00b7 lifetime \u00b7 this server")


def register_top(tree, is_guild_allowed) -> None:
    @tree.command(name="top", description="Activity ranks on this server. Messages, voice, or level.")
    @discord.app_commands.describe(sort="How to rank people")
    @discord.app_commands.choices(
        sort=[
            discord.app_commands.Choice(name="Messages", value="messages"),
            discord.app_commands.Choice(name="Voice time", value="voice"),
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
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        key = sort.value if sort else "messages"
        board = activity.leaderboard(
            interaction.guild.id,
            sort=key,
            limit=10,
            viewer_id=interaction.user.id,
        )
        bot_user = getattr(interaction.client, "user", None)
        await interaction.response.send_message(embed=top_embed(interaction.guild, board, bot_user))
