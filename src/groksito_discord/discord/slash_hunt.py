"""Ori-only WIP slash commands for Aetherion Hunt Test 2."""
from __future__ import annotations

import asyncio
import logging

import discord

from ..llm.persona import creator_is_author
from . import ai_coins
from . import aether_battle as board
from . import aether_gear as gear
from . import aether_hunt as hunt

logger = logging.getLogger("aetherion.slash_hunt")

ORIONLY = "Hunt is a WIP. Only Ori can use these commands."


def _is_ori(interaction: discord.Interaction) -> bool:
    return creator_is_author(getattr(interaction.user, "id", None))


async def _gate(interaction: discord.Interaction, is_guild_allowed) -> bool:
    if not _is_ori(interaction):
        await interaction.response.send_message(ORIONLY, ephemeral=True)
        return False
    if interaction.guild and not is_guild_allowed(interaction.guild.id):
        await interaction.response.send_message(
            "Aetherion is not available on this server.", ephemeral=True
        )
        return False
    return True


def _embed(title: str, body: str, color: int = hunt.EMBED_GOLD) -> discord.Embed:
    embed = discord.Embed(title=title, description=body, color=color)
    embed.set_footer(text=hunt.WIP_FOOTER)
    return embed


def _display_name(interaction: discord.Interaction) -> str:
    user = interaction.user
    return getattr(user, "display_name", None) or getattr(user, "name", "Hunter")


def _gear_call(name: str, user_id: int, *args):
    fn = getattr(hunt, name, None)
    if callable(fn):
        return fn(user_id, *args)
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        if name == "open_lootbox":
            out = gear.open_lootbox(pack)
        elif name == "open_crate":
            out = gear.open_crate(pack)
        elif name == "use_gem":
            out = gear.use_gem(pack, args[0], args[1] if len(args) > 1 else None)
        else:
            out = {"ok": False, "error": "Hunt gear is still updating."}
        hunt._save_store(store)
        return out


def _avatar_url(interaction: discord.Interaction) -> str | None:
    avatar = getattr(interaction.user, "display_avatar", None)
    return str(avatar.url) if avatar is not None else None


def _battle_total(result: dict) -> int:
    return max(1, int(result.get("rounds") or 1))


def _battle_embed(
    name: str,
    result: dict,
    frame: dict,
    *,
    final: bool,
    icon_url: str | None = None,
) -> discord.Embed:
    outcome = result.get("result") or "draw"
    if outcome == "win":
        color = hunt.EMBED_WIN
    elif outcome == "lose":
        color = hunt.EMBED_LOSE
    else:
        color = hunt.EMBED_GOLD
    desc = None if final else ("\n".join((frame.get("lines") or [])[-2:]) or None)
    embed = discord.Embed(color=color, description=desc)
    author = {"name": f"{name} goes into battle!"}
    if icon_url:
        author["icon_url"] = icon_url
    embed.set_author(**author)
    embed.add_field(name=f"{name}'s Team", value=board.roster_field(frame.get("player") or []), inline=True)
    embed.add_field(name="Enemy Team", value=board.roster_field(frame.get("enemy") or []), inline=True)
    total = _battle_total(result)
    turn = int(frame.get("turn") or 1)
    if final:
        footer = board.result_caption(result) + f"\n{hunt.WIP_FOOTER}"
    else:
        footer = f"Turn {turn}/{total}"
    embed.set_footer(text=footer)
    embed.set_image(url="attachment://battle.png")
    return embed


def _battle_file(frame: dict, total: int) -> discord.File:
    png = board.render_battle_png(
        frame.get("player") or [],
        frame.get("enemy") or [],
        turn=int(frame.get("turn") or 1),
        max_turns=max(1, int(total or 1)),
        lines=frame.get("lines") or None,
    )
    return discord.File(png, filename="battle.png")


def _playable_frames(frames: list[dict]) -> list[dict]:
    if len(frames) <= 18:
        return frames
    first, last = frames[0], frames[-1]
    mid = frames[1:-1]
    step = max(1, len(mid) // 16)
    picked = [first] + mid[::step][:16]
    if picked[-1] is not last:
        picked.append(last)
    return picked


async def _suggest_owned(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    if not _is_ori(interaction):
        return []
    snap = hunt.snapshot(interaction.user.id)
    owned = hunt.owned_catalog(snap["zoo"])
    needle = (current or "").strip().lower()
    out: list[discord.app_commands.Choice[str]] = []
    for aid, name, emoji, rarity in owned:
        hay = f"{aid} {name} {rarity}"
        if needle and needle not in hay.lower() and needle not in name.lower():
            continue
        have = int(snap["zoo"].get(aid) or 0)
        out.append(
            discord.app_commands.Choice(
                name=f"{emoji} {name} \u00d7{have}",
                value=name,
            )
        )
        if len(out) >= 25:
            break
    return out


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
        try:
            line = hunt.hunt_catch_line(
                _display_name(interaction),
                result["animal_id"],
                extras,
                bool(result.get("lootbox")),
            )
        except TypeError:
            line = hunt.hunt_catch_line(_display_name(interaction), result["animal_id"])
        await interaction.response.send_message(line)

    @tree.command(name="zoo", description="WIP Ori only. Show hunted animals.")
    @discord.app_commands.default_permissions(administrator=True)
    async def zoo_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        snap = hunt.snapshot(interaction.user.id)
        board_txt = hunt.zoo_board(
            _display_name(interaction),
            snap["zoo"],
            snap.get("caught") or snap["zoo"],
        )
        if len(board_txt) > 1900:
            board_txt = board_txt[:1890] + "\n\u2026"
        await interaction.response.send_message(board_txt)

    @tree.command(name="sell", description="WIP Ori only. Sell extra animals for Aether Coins.")
    @discord.app_commands.describe(animal="Animal name", count="How many to sell")
    @discord.app_commands.default_permissions(administrator=True)
    async def sell_slash(interaction: discord.Interaction, animal: str, count: int = 1):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = hunt.sell(interaction.user.id, animal, count)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not sell.", ephemeral=True
            )
            return
        pocket = ai_coins.coins(f"**{int(result['balance']):,}**")
        body = (
            f"Sold **{result['sold']}\u00d7 {hunt.animal_label(result['animal_id'])}** "
            f"for {ai_coins.coins(result['payout'])}.\n"
            f"Left: **{result['left']}**\n"
            f"Pocket \u00b7 {pocket}"
        )
        await interaction.response.send_message(embed=_embed("\u2726 Sold", body))

    @sell_slash.autocomplete("animal")
    async def sell_animal_ac(interaction: discord.Interaction, current: str):
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
        snap = hunt.snapshot(interaction.user.id)
        try:
            body = "\n".join(
                hunt.team_lines(snap["team"], snap["xp"], snap["zoo"], snap.get("gear"))
            )
        except TypeError:
            body = "\n".join(hunt.team_lines(snap["team"], snap["xp"], snap["zoo"]))
        owned = hunt.owned_catalog(snap["zoo"])
        if owned:
            picks = ", ".join(f"{emoji} {name}" for _aid, name, emoji, _rar in owned)
            body += f"\n\n**Owned** {picks}"
        else:
            body += "\n\nHunt something before you set a team."
        await interaction.response.send_message(embed=_embed("\u2726 Team", body))

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

    @tree.command(name="inv", description="WIP Ori only. Lootboxes, crates, gems, weapons.")
    @discord.app_commands.default_permissions(administrator=True)
    async def inv_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        snap = hunt.snapshot(interaction.user.id)
        pack = snap.get("gear")
        if not isinstance(pack, dict):
            with hunt._lock:
                store = hunt._load_store()
                row = hunt._ensure_user(store, interaction.user.id)
                pack = gear.ensure_gear(row)
                hunt._save_store(store)
        text = gear.inventory_text(_display_name(interaction), pack)
        sheet = gear.inventory_sheet_png(pack) if hasattr(gear, "inventory_sheet_png") else None
        if sheet:
            embed = _embed("\u2726 Inventory", text)
            embed.set_thumbnail(url="attachment://inventory_weapons.png")
            await interaction.response.send_message(
                embed=embed,
                file=discord.File(sheet, filename="inventory_weapons.png"),
            )
            return
        await interaction.response.send_message(text)

    @tree.command(name="lootbox", description="WIP Ori only. Open a lootbox for a hunt gem.")
    @discord.app_commands.default_permissions(administrator=True)
    async def lootbox_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = _gear_call("open_lootbox", interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "No lootbox.", ephemeral=True
            )
            return
        rar = hunt.RARITY_LABEL[result["rarity"]]
        kind = gear.GEM_BY_KIND[result["kind"]][1]
        line = (
            f"\U0001f48e | **{_display_name(interaction)}** opens a lootbox\n"
            f"\U0001f4e6 | and finds a **{rar} {kind}**!"
        )
        await interaction.response.send_message(line)

    @tree.command(name="crate", description="WIP Ori only. Open a weapon crate.")
    @discord.app_commands.default_permissions(administrator=True)
    async def crate_slash(interaction: discord.Interaction):
        if not await _gate(interaction, is_guild_allowed):
            return
        result = _gear_call("open_crate", interaction.user.id)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "No crate.", ephemeral=True
            )
            return
        rar = hunt.RARITY_LABEL[result["rarity"]]
        line = (
            f"{result['emoji']} | **{rar} {result['name']}** Q{result['quality']} "
            f"+{result['atk']} ATK (id `{result['wid']}`)"
        )
        embed = _embed(
            f"\U0001fab5 {_display_name(interaction)} opens a weapon crate",
            line,
        )
        if hasattr(gear, "weapon_icon_png"):
            icon = gear.weapon_icon_png(result["kind"], result["rarity"])
            fname = f"{result['kind']}.png"
            embed.set_thumbnail(url=f"attachment://{fname}")
            await interaction.response.send_message(
                embed=embed, file=discord.File(icon, filename=fname)
            )
            return
        await interaction.response.send_message(embed=embed)

    @tree.command(name="use", description="WIP Ori only. Activate a hunting, lucky, or empower gem.")
    @discord.app_commands.describe(gem="hunting, lucky, or empower", rarity="optional gem tier")
    @discord.app_commands.choices(
        gem=[
            discord.app_commands.Choice(name="Hunting", value="hunting"),
            discord.app_commands.Choice(name="Lucky", value="lucky"),
            discord.app_commands.Choice(name="Empowering", value="empower"),
        ]
    )
    @discord.app_commands.default_permissions(administrator=True)
    async def use_slash(
        interaction: discord.Interaction,
        gem: discord.app_commands.Choice[str],
        rarity: str | None = None,
    ):
        if not await _gate(interaction, is_guild_allowed):
            return
        rar = None
        if rarity:
            key = rarity.strip().lower()
            rar = key if key in hunt.RARITY_LABEL else None
        result = _gear_call("use_gem", interaction.user.id, gem.value, rar)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not use that gem.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{gear.GEM_BY_KIND[result['kind']][2]} | Activated "
            f"**{hunt.RARITY_LABEL[result['rarity']]} {result['label']}** "
            f"for **{result['left']}** hunts."
        )

    @tree.command(name="equip", description="WIP Ori only. Put a crate weapon on a team animal.")
    @discord.app_commands.describe(weapon="Weapon id or name from /inv", animal="Owned animal")
    @discord.app_commands.default_permissions(administrator=True)
    async def equip_slash(interaction: discord.Interaction, weapon: str, animal: str):
        if not await _gate(interaction, is_guild_allowed):
            return
        if hasattr(hunt, "equip_weapon"):
            result = hunt.equip_weapon(interaction.user.id, weapon, animal)
        else:
            animal_id = hunt.resolve_animal(animal)
            if animal_id is None:
                result = {"ok": False, "error": "I do not know that animal. Check /zoo."}
            else:
                with hunt._lock:
                    store = hunt._load_store()
                    row = hunt._ensure_user(store, interaction.user.id)
                    pack = gear.ensure_gear(row)
                    wid = gear.resolve_weapon(pack, weapon)
                    if not wid:
                        result = {"ok": False, "error": "No matching weapon. Use the id from /inv."}
                    else:
                        result = gear.equip_weapon(pack, wid, animal_id)
                        if result.get("ok"):
                            result["animal_id"] = animal_id
                            result["label"] = gear.weapon_line(gear.equipped_weapon(pack, animal_id))
                    hunt._save_store(store)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not equip.", ephemeral=True
            )
            return
        pack = hunt.snapshot(interaction.user.id).get("gear") or {}
        if not pack:
            with hunt._lock:
                store = hunt._load_store()
                pack = gear.ensure_gear(hunt._ensure_user(store, interaction.user.id))
        wep = gear.equipped_weapon(pack, result["animal_id"])
        body = f"Equipped {result['label']} on {hunt.animal_label(result['animal_id'])}."
        if wep and hasattr(gear, "weapon_icon_png"):
            embed = _embed("\u2726 Equip", body)
            icon = gear.weapon_icon_png(wep["kind"], wep.get("rarity"))
            fname = f"{wep['kind']}.png"
            embed.set_thumbnail(url=f"attachment://{fname}")
            await interaction.response.send_message(
                embed=embed, file=discord.File(icon, filename=fname)
            )
            return
        await interaction.response.send_message(body)

    @equip_slash.autocomplete("animal")
    async def equip_animal_ac(interaction: discord.Interaction, current: str):
        return await _suggest_owned(interaction, current)

    @equip_slash.autocomplete("weapon")
    async def equip_weapon_ac(interaction: discord.Interaction, current: str):
        if not _is_ori(interaction):
            return []
        snap = hunt.snapshot(interaction.user.id)
        needle = (current or "").strip().lower()
        out: list[discord.app_commands.Choice[str]] = []
        for wid, label, name in gear.owned_weapons(snap.get("gear") or {}):
            if needle and needle not in label.lower() and needle not in wid:
                continue
            out.append(discord.app_commands.Choice(name=f"#{wid} {label}", value=wid))
            if len(out) >= 25:
                break
        return out
