"""Public /help. Explains Aetherion commands without touching game or voice logic."""
from __future__ import annotations

import logging

import discord

from . import ai_coins

logger = logging.getLogger("aetherion.slash_help")

HELP_COLOR = 0xC9A227
PAGES = ("overview", "chat", "voice", "games", "coins", "hunt", "server")


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
            f"`/connect4` \u2014 challenge a member, or leave opponent empty to play Aetherion. "
            f"Same bet each ({ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}). Winner takes the pot.\n\n"
            f"`/poker` \u2014 Texas Hold'em, 2\u20134 seats. Friends Join, or Seat Aetherion. "
            f"Buy-in {ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET} (default 200). **My cards** is private. **Hands** is a rank chart only."
        )
        return embed

    if key == "coins":
        embed.title = "\u2726 Aetherion \u00b7 Aether Coins"
        embed.description = (
            "Play-money. No cash-out. Bets and grants move in tens.\n\n"
            f"New players start with **{ai_coins.STARTING_BALANCE}** Aether Coins.\n"
            f"`/daily` \u2014 claim **{ai_coins.DAILY_DRIP}** once per Eastern day.\n"
            "`/balance` \u2014 your wallet.\n"
            "`/leaderboard` \u2014 top wallets on this server, including Aetherion's house wallet.\n\n"
            f"Blackjack, Connect Four, and Poker bets: {ai_coins.MIN_BET}\u2013{ai_coins.MAX_BET}.\n"
            "Slots bets: 100\u201310,000.\n"
            "Coin toss bets: 10\u201310,000.\n"
            "Ori only: `/givecoins`."
        )
        return embed

    if key == "hunt":
        embed.title = "\u2726 Aetherion \u00b7 Hunt"
        embed.description = (
            "**Ori only WIP.** Everyone else is rejected. Expedition and autohunt are still on hold.\n\n"
            "50 original animals (10 each C/U/R/E/M). 42 weapons. Level cap 50.\n"
            "Manual hunt costs **10** Aether Coins with a **15s** cooldown.\n\n"
            "`/hunt` — catch. `/zoo` — grid and Zoo Points.\n"
            "`/team` `/sell` `/sacrifice` `/rename` `/checklist`\n"
            "`/battle` — 3v3 board. Phys ATK/PR, weapon MAG/MR, WP spend.\n"
            "`/raid` — pick Easy/Hard/Nightmare rift (Ember/Void/Crown); spend tickets; epic clears on Hard+. Craft: 30 shards → 1 ticket. `/bestiary` (`/dex`) — animal card.\n\n"
            "`/inv` `/lootbox` `/crate` `/use` `/equip` `/weapons` `/weapon` `/salvage`\n"
            "`/use hunting|lucky|empower|prism` activates gems onto hunts, not pets. "
            "Tiers go through Fabled. `/weapons` is the zoo-style armory; `/weapon id` opens the detail card.\n\n"
            "Custom icons (optional): upload `assets/hunt_icons/` + `hunt_portraits/` as Discord emojis, "
            "set `HUNT_EMOJI_HP` / `HUNT_EMOJI_ANIMAL_<id>` / etc. in `.env` — unicode fallbacks until then."
        )
        return embed

    if key == "server":
        embed.title = "\u2726 Aetherion \u00b7 Server tools"
        embed.description = (
            "Administrators:\n"
            "`/reactionrole colors` — post the color-role panel.\n"
            "`/reactionrole post` `add` `remove` `list` — custom panels.\n"
            "People can keep **one** color from a panel at a time.\n"
            "`/welcome` — channel for new-member banners.\n"
            "`/datechannel` — voice channel that shows today's date at midnight Eastern.\n"
            "`/purge` — delete up to 100 recent messages in this channel.\n\n"
            "Ori only: `/givecoins`, `/edit`, `/status`.\n"
            "Hunt commands live on the **Hunt** help page."
        )
        return embed

    embed.title = "\u2726 Aetherion \u00b7 Help"
    embed.description = (
        "Grok in Discord — chat, vision, live voice, SoundCloud, Aether Coin games, and Hunt.\n"
        "Mention **@Aetherion** or reply to it. Use the menu for a topic."
    )
    embed.add_field(
        name="\U0001F399\ufe0f  Talk & voice",
        value=(
            "`/join` `/leave` — voice chat\n"
            "`/play` `/pause` `/stop` — SoundCloud\n"
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
        name="\U0001F3AF  Hunt",
        value=(
            "Ori only WIP\n"
            "`/hunt` `/zoo` `/team` `/battle` `/inv`"
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


class HelpView(discord.ui.View):
    def __init__(self, user_id: int, page: str):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.page = page if page in PAGES else "overview"
        self._sync_select()

    def _sync_select(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                child.placeholder = f"Topic \u00b7 {self.page}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This help menu is not yours. Run `/help`.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.select(
        placeholder="Topic \u00b7 overview",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Overview", value="overview", description="Command list"),
            discord.SelectOption(label="Chat", value="chat", description="Mentions, images, /audio"),
            discord.SelectOption(label="Voice & music", value="voice", description="/join and SoundCloud"),
            discord.SelectOption(label="Games", value="games", description="Blackjack, slots, coin toss, Connect Four, poker"),
            discord.SelectOption(label="Aether Coins", value="coins", description="Wallet, daily, bets"),
            discord.SelectOption(label="Hunt", value="hunt", description="Ori-only animals, battle, gems"),
            discord.SelectOption(label="Server tools", value="server", description="Roles, welcome, date dock"),
        ],
    )
    async def pick_topic(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.page = str(select.values[0])
        self._sync_select()
        await interaction.response.edit_message(embed=_embed(self.page), view=self)


def register_help(tree, is_guild_allowed) -> None:
    @tree.command(name="help", description="How Aetherion works, and every command.")
    @discord.app_commands.describe(topic="Jump straight to a help page")
    @discord.app_commands.choices(
        topic=[
            discord.app_commands.Choice(name="Overview", value="overview"),
            discord.app_commands.Choice(name="Chat", value="chat"),
            discord.app_commands.Choice(name="Voice & music", value="voice"),
            discord.app_commands.Choice(name="Games", value="games"),
            discord.app_commands.Choice(name="Aether Coins", value="coins"),
            discord.app_commands.Choice(name="Hunt", value="hunt"),
            discord.app_commands.Choice(name="Server tools", value="server"),
        ]
    )
    async def help_slash(
        interaction: discord.Interaction,
        topic: discord.app_commands.Choice[str] | None = None,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        page = topic.value if topic else "overview"
        view = HelpView(interaction.user.id, page)
        await interaction.response.send_message(embed=_embed(page), view=view)
