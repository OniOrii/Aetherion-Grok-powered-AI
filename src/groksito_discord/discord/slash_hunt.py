"""Ori-only WIP slash commands for Aetherion Hunt.

Root slashes stay short: /hunt /zoo /team /battle /raid /inv /weapon.
Bag and zoo verbs live as options or inventory buttons.
"""
from __future__ import annotations

import asyncio
import logging

import discord

from . import aether_battle as board
from . import aether_gear as gear
from . import aether_hunt as hunt
from . import team_settings_views as team_ui
from .slash_hunt_ops import (
    _avatar_url,
    _battle_embed,
    _battle_file,
    _battle_total,
    _display_name,
    _embed,
    _gate,
    _playable_frames,
    _suggest_owned,
    _suggest_team,
)
from .slash_hunt_acts import (
    _armory_pack,
    _checklist_embed,
    _reply_bestiary,
    _reply_rename,
    _reply_sacrifice,
    _reply_sell,
    _suggest_caught,
    _suggest_weapons,
    _zoo_board_text,
)
from .slash_hunt_open import ZooMenuView
from .slash_hunt_bags import register_hunt_bags

logger = logging.getLogger("aetherion.slash_hunt")

def register_hunt(tree, is_guild_allowed) -> None:
    @tree.command(name="hunt", description="WIP Ori only. Hunt one Aetherion animal.")
    @discord.app_commands.default_permissions(administrator=True)
    async def hunt_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.hunt(interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Hunt failed.", ephemeral=True
            )
            return
        extras = [aid for aid in result.get("animals") or [] if aid != result["animal_id"]]
        team_xp = None
        xp_gain = int(result.get("xp_gain") or 0)
        if xp_gain > 0:
            snap = hunt.snapshot(interaction.user.id)
            bits = []
            for aid in snap.get("team") or []:
                if not aid:
                    continue
                row = hunt.ANIMAL_BY_ID.get(aid)
                if row:
                    bits.append((row[2], xp_gain))
            if bits:
                team_xp = bits
        try:
            line = hunt.hunt_catch_line(
                _display_name(interaction),
                result["animal_id"],
                extras,
                bool(result.get("lootbox")),
                team_xp,
                gems_hud=result.get("gems_hud") or None,
                lootbox_count=int(result.get("lootbox_count") or 0) or None,
            )
        except TypeError:
            line = hunt.hunt_catch_line(_display_name(interaction), result["animal_id"])
        for aw in result.get("ticket_awards") or []:
            amt = int(aw.get("amount") or 1)
            reason = aw.get("reason") or "raid ticket"
            line += f"\n+{amt} raid ticket ({reason}) · {int(aw.get('tickets') or 0)} left"
        await interaction.response.send_message(line)

    @tree.command(name="zoo", description="WIP Ori only. Zoo grid, sell, sacrifice, rename, checklist, bestiary.")
    @discord.app_commands.describe(
        action="show, checklist, sell, sacrifice, rename, or bestiary",
        animal="Animal name (sell / sacrifice / rename / bestiary)",
        count="How many extras to sell or sacrifice",
        nickname="New nickname, or empty to clear",
    )
    @discord.app_commands.choices(
        action=[
            discord.app_commands.Choice(name="Show", value="show"),
            discord.app_commands.Choice(name="Checklist", value="checklist"),
            discord.app_commands.Choice(name="Sell", value="sell"),
            discord.app_commands.Choice(name="Sacrifice", value="sacrifice"),
            discord.app_commands.Choice(name="Rename", value="rename"),
            discord.app_commands.Choice(name="Bestiary", value="bestiary"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def zoo_slash(
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str] | None = None,
        animal: str | None = None,
        count: int = 1,
        nickname: str | None = None,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        verb = action.value if action else "show"
        if verb == "checklist":
            await interaction.response.send_message(embed=_checklist_embed(interaction))
            return
        if verb in {"sell", "sacrifice", "rename", "bestiary"} and not animal:
            await interaction.response.send_message(
                f"Name the animal for `/zoo {verb}`.", ephemeral=True
            )
            return
        if verb == "sell":
            await _reply_sell(interaction, animal or "", count)
            return
        if verb == "sacrifice":
            await _reply_sacrifice(interaction, animal or "", count)
            return
        if verb == "rename":
            await _reply_rename(interaction, animal or "", nickname)
            return
        if verb == "bestiary":
            await _reply_bestiary(interaction, animal or "")
            return
        view = ZooMenuView(interaction.user.id)
        await interaction.response.send_message(_zoo_board_text(interaction), view=view)

    @zoo_slash.autocomplete("animal")
    async def zoo_animal_ac(interaction: discord.Interaction, current: str):
        action = None
        try:
            action = interaction.namespace.action
        except AttributeError:
            action = None
        if str(action or "") == "bestiary":
            return await _suggest_caught(interaction, current)
        return await _suggest_owned(interaction, current)

    @tree.command(name="team", description="WIP Ori only. Set the three-animal battle team.")
    @discord.app_commands.describe(
        action="show, set, or clear",
        animal="Animal to put in the slot",
        slot="Team slot 1-3",
    )
    @discord.app_commands.choices(
        action=[
            discord.app_commands.Choice(name="Show", value="show"),
            discord.app_commands.Choice(name="Set", value="set"),
            discord.app_commands.Choice(name="Clear", value="clear"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def team_slash(
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str] | None = None,
        animal: str | None = None,
        slot: int = 1,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        verb = action.value if action else ("set" if animal else "show")
        if verb == "set":
            if not animal:
                await interaction.response.send_message(
                    "Name the animal to put on the team.", ephemeral=True
                )
                return
            result = hunt.set_team_slot(interaction.user.id, slot, animal)
            if not result.get("ok"):
                await interaction.response.send_message(
                    result.get("error") or "Could not update the team.", ephemeral=True
                )
                return
        elif verb == "clear":
            result = hunt.set_team_slot(interaction.user.id, slot, None)
            if not result.get("ok"):
                await interaction.response.send_message(
                    result.get("error") or "Could not clear that slot.", ephemeral=True
                )
                return
        view = team_ui.TeamMainView(
            actor_id=interaction.user.id,
            display_name=_display_name(interaction),
        )
        await interaction.response.send_message(
            embed=team_ui.build_team_embed(interaction.user.id),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass

    @team_slash.autocomplete("animal")
    async def team_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_owned(interaction, current)

    @tree.command(name="battle", description="WIP Ori only. Fight a wild team with your animals.")
    @discord.app_commands.default_permissions(administrator=True)
    async def battle_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        await interaction.response.defer()
        result = hunt.battle(interaction.user.id)
        if not result.get("ok"):
            await interaction.followup.send(result.get("error") or "Battle failed.", ephemeral=True)
            return
        name = _display_name(interaction)
        icon_url = _avatar_url(interaction)
        total = _battle_total(result)
        frames = _playable_frames(list(result.get("frames") or []))
        if not frames:
            frames = [{
                "turn": total,
                "player": result.get("player") or [],
                "enemy": result.get("enemy") or [],
                "lines": result.get("log") or [],
            }]
        try:
            first = frames[0]
            msg = await interaction.followup.send(
                embed=_battle_embed(name, result, first, final=len(frames) == 1, icon_url=icon_url),
                file=_battle_file(first, total),
                wait=True,
            )
            for index, frame in enumerate(frames[1:], start=1):
                await asyncio.sleep(0.9)
                final = index == len(frames) - 1
                await msg.edit(
                    embed=_battle_embed(name, result, frame, final=final, icon_url=icon_url),
                    attachments=[_battle_file(frame, total)],
                )
        except Exception:
            logger.exception("battle animation failed")
            if hasattr(hunt, "battle_card"):
                body = hunt.battle_card(name, result)
            else:
                body = "\n".join(result.get("log") or ["Battle finished."])
            body += f"\n{board.result_caption(result)}"
            try:
                await interaction.edit_original_response(content=None, embed=_embed("Battle", body), attachments=[])
            except Exception:
                await interaction.followup.send(embed=_embed("Battle", body))

    register_hunt_bags(tree, is_guild_allowed)
