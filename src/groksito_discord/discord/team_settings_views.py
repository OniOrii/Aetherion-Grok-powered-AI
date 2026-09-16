"""OwO-feel Team Settings UI for Aetherion Hunt (Ori-only WIP)."""
from __future__ import annotations

import logging
from typing import Any

import discord

from . import aether_hunt as hunt

logger = logging.getLogger("aetherion.team_settings")

VIEW_TIMEOUT = 180
_SELECT_CAP = 24  # Discord max 25; reserve one for Clear

# Display-only toggle stubs (persistence deferred). Defaults: OFF except Show Stats ON.
TOGGLE_DEFAULTS: dict[str, bool] = {
    "auto_rename": False,
    "auto_team": False,
    "auto_battle": False,
    "show_stats": True,
    "level_up_ping": False,
}

TOGGLE_LABELS: tuple[tuple[str, str], ...] = (
    ("auto_rename", "Auto Rename"),
    ("auto_team", "Auto Team"),
    ("auto_battle", "Auto Battle"),
    ("show_stats", "Show Stats"),
    ("level_up_ping", "Level-up Ping"),
)


def _btn_label(text: str, *, chevron: bool = True) -> str:
    base = (text or "empty").strip() or "empty"
    if chevron:
        base = f"{base} ›"
    return base[:80]


def _slot_button_label(aid: str | None, xp: dict[str, int]) -> str:
    return _btn_label(hunt.settings_slot_display(aid, xp))


def settings_embed(display_name: str, team: list[str | None], xp: dict[str, int]) -> discord.Embed:
    title = f"{display_name}'s team settings" if display_name else "Team Settings"
    embed = discord.Embed(
        title=title,
        description=hunt.team_settings_description(team, xp),
        color=hunt.EMBED_GOLD,
    )
    embed.set_footer(text=hunt.WIP_FOOTER)
    return embed


def toggles_embed(display_name: str) -> discord.Embed:
    lines = ["`Team options`", ""]
    for key, label in TOGGLE_LABELS:
        on = TOGGLE_DEFAULTS.get(key, False)
        mark = "ON" if on else "OFF"
        lines.append(f"`{label}`")
        lines.append(f"{mark}  _(not saved yet)_")
        lines.append("")
    body = "\n".join(lines).rstrip()
    title = f"{display_name}'s team options" if display_name else "Team Options"
    embed = discord.Embed(title=title, description=body, color=hunt.EMBED_GOLD)
    embed.set_footer(text=hunt.WIP_FOOTER + " · toggles display-only")
    return embed


def build_team_embed(user_id: int) -> discord.Embed:
    snap = hunt.snapshot(user_id)
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
    embed = discord.Embed(title="\u2726 Team", description=body, color=hunt.EMBED_GOLD)
    embed.set_footer(text=hunt.WIP_FOOTER)
    return embed


def _owned_select_options(
    zoo: dict[str, int],
    xp: dict[str, int],
    team: list[str | None],
    slot_index: int,
) -> list[discord.SelectOption]:
    current = team[slot_index] if slot_index < len(team) else None
    taken = {aid for i, aid in enumerate(team) if aid and i != slot_index}
    options: list[discord.SelectOption] = [
        discord.SelectOption(
            label="Clear slot",
            value="__clear__",
            description="Leave this slot empty",
            emoji="\u274c",
            default=current is None,
        )
    ]
    owned = hunt.owned_catalog(zoo)
    for aid, name, emoji, _rar in owned:
        if aid in taken:
            continue
        if len(options) >= _SELECT_CAP + 1:
            break
        lvl = hunt.level_of(int(xp.get(aid) or 0))
        label = f"[Lvl {lvl}] {name}"[:100]
        opt_kw: dict[str, Any] = {
            "label": label,
            "value": aid,
            "description": f"Put {name} in slot {slot_index + 1}"[:100],
            "default": aid == current,
        }
        if emoji:
            opt_kw["emoji"] = emoji
        options.append(discord.SelectOption(**opt_kw))
    return options


class _TeamActorView(discord.ui.View):
    def __init__(self, *, actor_id: int, display_name: str):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.actor_id = int(actor_id)
        self.display_name = display_name or "Hunter"
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "Only the hunter who opened this team can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message is None:
            return
        try:
            await self.message.edit(view=self)
        except discord.HTTPException:
            pass


class TeamMainView(_TeamActorView):
    """Main /team embed controls — cog opens Team Settings."""

    @discord.ui.button(emoji="\u2699\ufe0f", style=discord.ButtonStyle.secondary, custom_id="hunt:team:cog")
    async def open_settings(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        snap = hunt.snapshot(self.actor_id)
        view = TeamSettingsView(actor_id=self.actor_id, display_name=self.display_name, page=1)
        view._refresh_slot_labels(snap["team"], snap["xp"])
        await interaction.response.edit_message(
            embed=settings_embed(self.display_name, snap["team"], snap["xp"]),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = interaction.message


class TeamSettingsView(_TeamActorView):
    """Page 1: Active team + slot rows. Page 2: display-only toggles stub."""

    def __init__(self, *, actor_id: int, display_name: str, page: int = 1):
        super().__init__(actor_id=actor_id, display_name=display_name)
        self.page = 1 if page < 1 else min(2, page)
        self.clear_items()
        if self.page == 1:
            self._build_page1()
        else:
            self._build_page2()

    def _build_page1(self) -> None:
        team_btn = discord.ui.Button(
            label=_btn_label("Team 1"),
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=0,
            custom_id="hunt:team:active",
        )
        self.add_item(team_btn)
        for slot in range(1, hunt.TEAM_SIZE + 1):
            btn = discord.ui.Button(
                label=_btn_label("empty"),
                style=discord.ButtonStyle.secondary,
                row=slot,  # rows 1-3
                custom_id=f"hunt:team:slot:{slot}",
            )
            btn.callback = self._make_slot_callback(slot)
            self.add_item(btn)
        self._add_nav(row=4)

    def _build_page2(self) -> None:
        for i, (key, label) in enumerate(TOGGLE_LABELS):
            on = TOGGLE_DEFAULTS.get(key, False)
            mark = "ON" if on else "OFF"
            btn = discord.ui.Button(
                label=f"{label}: {mark}"[:80],
                style=discord.ButtonStyle.success if on else discord.ButtonStyle.secondary,
                disabled=True,
                row=i // 3,
                custom_id=f"hunt:team:toggle:{key}",
            )
            self.add_item(btn)
        self._add_nav(row=4)

    def _add_nav(self, *, row: int) -> None:
        prev_btn = discord.ui.Button(
            emoji="\u25c0\ufe0f",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="hunt:team:prev",
            disabled=self.page <= 1,
        )
        prev_btn.callback = self._go_prev
        self.add_item(prev_btn)

        page_btn = discord.ui.Button(
            label=f"{self.page}/2",
            style=discord.ButtonStyle.secondary,
            row=row,
            disabled=True,
            custom_id="hunt:team:page",
        )
        self.add_item(page_btn)

        next_btn = discord.ui.Button(
            emoji="\u25b6\ufe0f",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="hunt:team:next",
            disabled=self.page >= 2,
        )
        next_btn.callback = self._go_next
        self.add_item(next_btn)

        back = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.primary,
            row=row,
            custom_id="hunt:team:back",
        )
        back.callback = self._go_back
        self.add_item(back)

    def _refresh_slot_labels(self, team: list[str | None], xp: dict[str, int]) -> None:
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            cid = item.custom_id or ""
            if cid.startswith("hunt:team:slot:"):
                try:
                    slot = int(cid.rsplit(":", 1)[-1])
                except ValueError:
                    continue
                aid = team[slot - 1] if 0 < slot <= len(team) else None
                item.label = _slot_button_label(aid, xp)

    def _make_slot_callback(self, slot: int):
        async def _callback(interaction: discord.Interaction) -> None:
            snap = hunt.snapshot(self.actor_id)
            view = SlotPickView(
                actor_id=self.actor_id,
                display_name=self.display_name,
                slot=slot,
                zoo=snap["zoo"],
                xp=snap["xp"],
                team=list(snap["team"]),
            )
            embed = discord.Embed(
                title=f"Slot {slot}",
                description=(
                    f"Pick an owned animal for **slot {slot}**, or clear it.\n"
                    f"Current: **{hunt.settings_slot_display(snap['team'][slot - 1] if slot <= len(snap['team']) else None, snap['xp'])}**"
                ),
                color=hunt.EMBED_GOLD,
            )
            embed.set_footer(text=hunt.WIP_FOOTER)
            await interaction.response.edit_message(embed=embed, view=view)
            try:
                view.message = await interaction.original_response()
            except discord.HTTPException:
                view.message = interaction.message

        return _callback

    async def _go_prev(self, interaction: discord.Interaction) -> None:
        await self._switch_page(interaction, self.page - 1)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        await self._switch_page(interaction, self.page + 1)

    async def _switch_page(self, interaction: discord.Interaction, page: int) -> None:
        page = 1 if page < 1 else min(2, page)
        snap = hunt.snapshot(self.actor_id)
        view = TeamSettingsView(
            actor_id=self.actor_id, display_name=self.display_name, page=page
        )
        if page == 1:
            view._refresh_slot_labels(snap["team"], snap["xp"])
            embed = settings_embed(self.display_name, snap["team"], snap["xp"])
        else:
            embed = toggles_embed(self.display_name)
        await interaction.response.edit_message(embed=embed, view=view)
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = interaction.message

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = TeamMainView(actor_id=self.actor_id, display_name=self.display_name)
        await interaction.response.edit_message(
            embed=build_team_embed(self.actor_id),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = interaction.message


class SlotPickView(_TeamActorView):
    """Select menu to set or clear one team slot."""

    def __init__(
        self,
        *,
        actor_id: int,
        display_name: str,
        slot: int,
        zoo: dict[str, int],
        xp: dict[str, int],
        team: list[str | None],
    ):
        super().__init__(actor_id=actor_id, display_name=display_name)
        self.slot = max(1, min(hunt.TEAM_SIZE, int(slot)))
        options = _owned_select_options(zoo, xp, team, self.slot - 1)
        select = discord.ui.Select(
            placeholder=f"Animal for slot {self.slot}",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
            custom_id=f"hunt:team:pick:{self.slot}",
        )
        select.callback = self._on_pick
        self.add_item(select)
        back = discord.ui.Button(
            label="Back to settings",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id="hunt:team:pick:back",
        )
        back.callback = self._back_settings
        self.add_item(back)

    async def _on_pick(self, interaction: discord.Interaction) -> None:
        select = next(
            (c for c in self.children if isinstance(c, discord.ui.Select)),
            None,
        )
        if select is None or not select.values:
            await interaction.response.send_message("Nothing selected.", ephemeral=True)
            return
        value = select.values[0]
        query: str | None = None if value == "__clear__" else value
        result = hunt.set_team_slot(self.actor_id, self.slot, query)
        if not result.get("ok"):
            await interaction.response.send_message(
                result.get("error") or "Could not update that slot.",
                ephemeral=True,
            )
            return
        snap = hunt.snapshot(self.actor_id)
        view = TeamSettingsView(
            actor_id=self.actor_id, display_name=self.display_name, page=1
        )
        view._refresh_slot_labels(snap["team"], snap["xp"])
        await interaction.response.edit_message(
            embed=settings_embed(self.display_name, snap["team"], snap["xp"]),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = interaction.message

    async def _back_settings(self, interaction: discord.Interaction) -> None:
        snap = hunt.snapshot(self.actor_id)
        view = TeamSettingsView(
            actor_id=self.actor_id, display_name=self.display_name, page=1
        )
        view._refresh_slot_labels(snap["team"], snap["xp"])
        await interaction.response.edit_message(
            embed=settings_embed(self.display_name, snap["team"], snap["xp"]),
            view=view,
        )
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            view.message = interaction.message
