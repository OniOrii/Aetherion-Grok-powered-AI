"""Public /help. Explains Aetherion commands without touching game or voice logic."""
from __future__ import annotations

import logging

import discord

from . import ai_coins

logger = logging.getLogger("aetherion.slash_help")

HELP_COLOR = 0xC9A227
PAGES = ("overview", "chat", "voice", "games", "coins", "server")


def _embed(page: str) -> discord.Embed:
    key = page if page in PAGES else "overview"
    embed = discord.Embed(color=HELP_COLOR)
    embed.set_footer(text="\u2726 Aetherion \u00b7 pick a topic below, or run /help topic:")

    if key == "chat":
        embed.title = "\u2726 Aetherion \u00b7 Chat"
        embed.description = (
            "Aetherion is Grok in Discord. Mention **@Aetherion** or reply to it.\n\n"
            "It can read pictures you attach, search the web, and generate or edit images. "
            "Video generation is available when that setting is on.\n\n"
            f"`/audio` \u2014 speak text in this channel. Default voice is **Zagan**.\n"
            "Right-click a message \u2192 Apps \u2192 **Leer en voz alta** to hear that message.\n"
            "`/ping` \u2014 check that the bot is awake."
        )
        return embed

    if key == "voice":
        embed.title = "\u2726 Aetherion \u00b7 Voice & music"
        embed.description = (
            "Join a voice channel first, then run `/join`. `/leave` disconnects.\n\n"
            "Aetherion listens to the person who last used `/join`. "
            "Say **Aetherion**, then the question, then pause.\n\n"
            "Music is **SoundCloud only** on that same connection.\n"
            "`/play` `query:` song name or a soundcloud.com link\n"
            "`/pause` \u00b7 `/stop`\n\n"
            "You can also say **Aetherion play \u2026**, **Aetherion pause**, or **Aetherion stop**.\n"
            "YouTube links are rejected on purpose."
        )
        return embed

    if key == "games":
        embed.title = "\u2726 Aetherion \u00b7 Games"
        embed.description = (
            "Play-money only. Same **Aether Coins** wallet for every game.\n\n"
            f"`/blackjack` \u2014 fair dealer. Hit, Stand, Double. Bet {ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}.\n"
            "After the hand: **Play Again** or **Change Bet**.\n\n"
            "`/slots` \u2014 Cosmos Wheel, Nebula, or Event Horizon. Bet 100\u201310,000.\n"
            "**Spin Again** and **Change Bet** stay on the machine.\n\n"
            "`/cointoss` \u2014 call Heads or Tails. Bet 10\u201310,000.\n"
            "Odds are 48% / 48% / 2% side. Side pays 2.5x.\n\n"
            f"`/connect4` \u2014 challenge a member. Same bet each ({ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}). Winner takes the pot.\n\n"
            f"`/poker` \u2014 Texas Hold'em, 2\u20134 seats. Friends Join, or Seat Aetherion. Buy-in {ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}."
        )
        return embed

    if key == "coins":
        embed.title = "\u2726 Aetherion \u00b7 Aether Coins"
        embed.description = (
            "Play-money. No cash-out. Bets and grants move in tens.\n\n"
            f"New players start with **{ai_coins.STARTING_BALANCE}** Aether Coins.\n"
            f"`/daily` \u2014 claim **{ai_coins.DAILY_DRIP}** once per Eastern day.\n"
            "`/balance` \u2014 your wallet.\n"
            "`/leaderboard` \u2014 top wallets on this server.\n\n"
            f"Blackjack, Connect Four, and Poker bets: {ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}.\n"
            "Slots bets: 100\u201310,000.\n"
            "Coin toss bets: 10\u201310,000."
        )
        return embed

    if key == "server":
        embed.title = "\u2726 Aetherion \u00b7 Server tools"
        embed.description = (
            "Administrators:\n"
            "`/reactionrole colors` \u2014 post the color-role panel.\n"
            "`/reactionrole post` `add` `remove` `list` \u2014 custom panels.\n"
            "People can keep **one** color from a panel at a time.\n"
            "`/welcome` \u2014 channel for new-member banners.\n"
            "`/datechannel` \u2014 voice channel that shows today's date at midnight Eastern.\n"
            "`/purge` \u2014 delete up to 100 recent messages in this channel.\n\n"
            "Ori only: `/givecoins`, `/edit`, `/status`.\n"
            "Ori only WIP: `/hunt` `/zoo` `/sell` `/team` `/battle` `/inv` `/lootbox` `/crate` `/use` `/equip` `/weapon` `/sacrifice` `/rename` `/checklist`.\nGems from `/lootbox` activate with `/use hunting|lucky|empower`. They are not equipped on animals."
        )
        return embed

    embed.title = "\u2726 Aetherion \u00b7 Help"
    embed.description = (
        "Grok in Discord \u2014 chat, vision, live voice, SoundCloud, and Aether Coin games.\n"
        "Mention **@Aetherion** or reply to it. Use the menu for a topic."
    )
    embed.add_field(
        name="\U0001F399\ufe0f  Talk & voice",
        value=(
            "`/join` `/leave` \u2014 voice chat\n"
            "`/play` `/pause` `/stop` \u2014 SoundCloud\n"
            "`/audio` `/ping` `/help`"
        ),
        inline=True,
    )
    embed.add_field(
        name="\u2726  Games & coins",
        value=(
            "`/blackjack` `/slots` `/cointoss` `/connect4` `/poker`\n"
            "`/balance` `/daily` `/leaderboard`"
        ),
        inline=True,
    )
    embed.add_field(
        name="\U0001F6E1\ufe0f  Server",
        value=(
            "`/reactionrole` color roles\n"
            "`/welcome` `/datechannel` `/purge`"
        ),
        inline=True,
    )
    return embed
