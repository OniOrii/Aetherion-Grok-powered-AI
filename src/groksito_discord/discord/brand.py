"""Shared gold embed stamp so public Aetherion replies look like one bot."""
from __future__ import annotations

import discord

GOLD = 0xC9A227
FOOTER = "\u2726 Aetherion"


def stamp(embed: discord.Embed, bot_user=None, extra: str | None = None) -> discord.Embed:
    embed.color = GOLD
    embed.set_footer(text=f"{FOOTER} \u00b7 {extra}" if extra else FOOTER)
    if bot_user is None:
        return embed
    name = getattr(bot_user, "display_name", None) or getattr(bot_user, "name", None) or "Aetherion"
    avatar = getattr(getattr(bot_user, "display_avatar", None), "url", None)
    if avatar:
        embed.set_author(name=name, icon_url=str(avatar))
        if embed.thumbnail is None or not getattr(embed.thumbnail, "url", None):
            embed.set_thumbnail(url=str(avatar))
    else:
        embed.set_author(name=name)
    return embed
