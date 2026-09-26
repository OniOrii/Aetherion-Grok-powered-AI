"""Slash easy trivia against Aetherion for Aether Coins."""
from __future__ import annotations

import logging

import discord

from . import ai_coins
from .slash_blackjack import has_live_hand
from .trivia import (
    TRIVIA_DEFAULT_BET,
    TRIVIA_MAX_BET,
    TRIVIA_MIN_BET,
    WIN_MULTI,
    TriviaQuestion,
    fetch_question,
)

logger = logging.getLogger("aetherion.slash_trivia")

_games: dict[int, dict] = {}
_last_bet: dict[int, int] = {}

EMBED_PLAY = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
EMBED_PUSH = 0x8A8F98
LETTERS = ("A", "B", "C", "D")


def has_live_trivia(user_id: int) -> bool:
    game = _games.get(user_id)
    return bool(game) and not game.get("finished")


def has_live_hand_safe(user_id: int) -> bool:
    try:
        return bool(has_live_hand(user_id))
    except Exception:
        return False


def _clip(text: str, limit: int = 72) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


def _choices(question: TriviaQuestion) -> str:
    lines = []
    for i, answer in enumerate(question.answers):
        lines.append(f"**{LETTERS[i]}.** {answer}")
    return "\n".join(lines)


def _embed(question: TriviaQuestion, *, pocket: int, bet: int, color: int, result: str | None = None) -> discord.Embed:
    if result == "win":
        title = f"\u2726 Trivia \u00b7 {ai_coins.won_line(int(bet * WIN_MULTI) - bet)}"
        body = f"Correct. **{question.correct}**"
    elif result == "lose":
        title = f"\u2726 Trivia \u00b7 {ai_coins.won_line(-bet)}"
        body = f"The answer was **{question.correct}**."
    elif result == "push":
        title = "\u2726 Trivia \u00b7 Push"
        body = "No answer. Stake returned."
    else:
        title = "\u2726 Trivia"
        body = f"{question.prompt}\n\n{_choices(question)}"
    desc = (
        f"**Pocket** \u00b7 {ai_coins.coins(f'**{pocket:,}**')}\n"
        f"**Stake** \u00b7 {ai_coins.coins(f'**{bet:,}**')}\n"
        f"**Pays** \u00b7 **{WIN_MULTI:g}x** if you are right\n\n"
        f"{body}"
    )
    embed = discord.Embed(title=title, description=desc, color=color)
    extra = question.category or "General"
    embed.set_footer(text=f"Easy general knowledge \u00b7 {extra}")
    return embed


class BetModal(discord.ui.Modal, title="Change bet"):
    amount = discord.ui.TextInput(
        label="Aether Coins",
        placeholder=f"{TRIVIA_MIN_BET}\u2013{TRIVIA_MAX_BET}",
        required=True,
        max_length=6,
    )

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.amount.value or "").replace(",", "").strip()
        try:
            bet = int(raw)
        except ValueError:
            await interaction.response.send_message("Bet has to be a whole number.", ephemeral=True)
            return
        err = ai_coins.amount_error(bet, TRIVIA_MIN_BET, TRIVIA_MAX_BET)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return
        _last_bet[self.user_id] = bet
        await interaction.response.send_message(
            f"Next question is {ai_coins.coins(f'**{bet:,}**')}.", ephemeral=True
        )


class ReplayView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your question.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.primary)
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = int(_last_bet.get(self.user_id) or TRIVIA_DEFAULT_BET)
        await _start_round(interaction, user_id=self.user_id, bet=bet, edit=True)

    @discord.ui.button(label="Change Bet", style=discord.ButtonStyle.secondary)
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal(self.user_id))


class TriviaView(discord.ui.View):
    def __init__(self, user_id: int, question: TriviaQuestion):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.message: discord.Message | None = None
        for index, answer in enumerate(question.answers):
            self.add_item(_AnswerButton(index, answer))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your question.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        game = _games.get(self.user_id)
        if game is None or game.get("finished"):
            return
        try:
            question: TriviaQuestion = game["question"]
            bet = int(game["bet"])
            game["finished"] = True
            balance = ai_coins.settle_hand(self.user_id, bet)
            _last_bet[self.user_id] = bet
            _games.pop(self.user_id, None)
            if self.message is None:
                return
            embed = _embed(question, pocket=balance, bet=bet, color=EMBED_PUSH, result="push")
            await self.message.edit(content="Question timed out.", embed=embed, view=ReplayView(self.user_id))
        except Exception:
            logger.exception("trivia timeout settle failed user=%s", self.user_id)
            _games.pop(self.user_id, None)


class _AnswerButton(discord.ui.Button):
    def __init__(self, index: int, answer: str):
        super().__init__(
            label=f"{LETTERS[index]}. {_clip(answer)}",
            style=discord.ButtonStyle.primary,
            custom_id=f"tv_{index}",
            row=index // 2,
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, TriviaView):
            return
        await _answer(interaction, view, self.index)


async def _answer(interaction: discord.Interaction, view: TriviaView, pick: int) -> None:
    user_id = view.user_id
    game = _games.get(user_id)
    if game is None or game.get("finished"):
        await interaction.response.send_message("That question is already over.", ephemeral=True)
        return
    question: TriviaQuestion = game["question"]
    bet = int(game["bet"])
    game["finished"] = True
    won = pick == question.correct_index
    credit = int(bet * WIN_MULTI) if won else 0
    balance = ai_coins.settle_hand(user_id, credit)
    _last_bet[user_id] = bet
    _games.pop(user_id, None)
    view.stop()
    embed = _embed(
        question,
        pocket=balance,
        bet=bet,
        color=EMBED_WIN if won else EMBED_LOSE,
        result="win" if won else "lose",
    )
    if not interaction.response.is_done():
        await interaction.response.edit_message(embed=embed, view=ReplayView(user_id))
        return
    await interaction.edit_original_response(embed=embed, view=ReplayView(user_id))


async def _start_round(
    interaction: discord.Interaction,
    *,
    user_id: int,
    bet: int,
    edit: bool,
) -> None:
    if has_live_trivia(user_id):
        msg = "Finish the question already on the table first."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return
    if has_live_hand_safe(user_id):
        msg = "Finish the blackjack hand on the table first."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    err = ai_coins.amount_error(bet, TRIVIA_MIN_BET, TRIVIA_MAX_BET)
    if err:
        if interaction.response.is_done():
            await interaction.followup.send(err, ephemeral=True)
        else:
            await interaction.response.send_message(err, ephemeral=True)
        return

    if not interaction.response.is_done():
        await interaction.response.defer()

    _games.pop(user_id, None)
    ai_coins.refund_stale_pending(user_id)
    ok, pocket, hold_err = ai_coins.hold_bet(user_id, bet, max_bet=TRIVIA_MAX_BET)
    if not ok:
        await interaction.followup.send(hold_err, ephemeral=True)
        return

    try:
        question = await fetch_question()
    except Exception:
        logger.exception("trivia fetch failed user=%s", user_id)
        ai_coins.settle_hand(user_id, bet)
        await interaction.followup.send("Could not load a question. Stake returned.", ephemeral=True)
        return

    _last_bet[user_id] = int(bet)
    _games[user_id] = {"question": question, "bet": int(bet), "finished": False}
    view = TriviaView(user_id, question)
    embed = _embed(question, pocket=pocket, bet=int(bet), color=EMBED_PLAY)
    message = await interaction.edit_original_response(embed=embed, view=view)
    view.message = message


def register_trivia(tree, is_guild_allowed) -> None:
    @tree.command(name="trivia", description="Easy general knowledge. Four answers. Pays 3x.")
    @discord.app_commands.describe(bet=f"Wager in Aether Coins ({TRIVIA_MIN_BET}\u2013{TRIVIA_MAX_BET})")
    async def trivia_slash(
        interaction: discord.Interaction,
        bet: int = TRIVIA_DEFAULT_BET,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available on this server.", ephemeral=True)
            return
        user_id = interaction.user.id
        if bet == TRIVIA_DEFAULT_BET and user_id in _last_bet:
            bet = int(_last_bet[user_id])
        await _start_round(interaction, user_id=user_id, bet=int(bet), edit=False)
