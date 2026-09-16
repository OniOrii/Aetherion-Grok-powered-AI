"""OwO-style PvE battle board and auto turn animation frames."""
from __future__ import annotations

import hashlib
import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .aether_gear import COMMON, WEAPON_BY_ID
from .weapon_art import weapon_icon_png

MAX_TURNS = 5
BOARD_W = 920
ROW_H = 168
PAD = 10
NAME_H = 36

BG = (18, 20, 28)
PANEL = (32, 36, 48)
PANEL_EDGE = (58, 64, 82)
INK = (236, 230, 220)
MUTED = (168, 172, 184)
HP_RED = (196, 64, 72)
HP_BACK = (72, 28, 32)
WP_BLUE = (56, 128, 214)
WP_BACK = (28, 44, 78)
STR_C = (214, 96, 88)
MAG_C = (88, 168, 214)
RES_C = (72, 186, 118)

_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

RARITY_TINT = {
    "common": (196, 72, 72),
    "uncommon": (56, 158, 88),
    "rare": (214, 176, 48),
    "epic": (72, 128, 214),
    "mythic": (156, 88, 214),
}


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _FONT_BOLD if bold else _FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _tint(animal_id: str) -> tuple[int, int, int]:
    digest = hashlib.md5((animal_id or "pet").encode()).hexdigest()
    return (
        40 + int(digest[0:2], 16) % 180,
        36 + int(digest[2:4], 16) % 170,
        50 + int(digest[4:6], 16) % 170,
    )


def _snap_side(side: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for pet in side:
        copy = dict(pet)
        wep = pet.get("weapon")
        copy["weapon"] = dict(wep) if isinstance(wep, dict) else None
        out.append(copy)
    return out


def _bar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, cur: int, mx: int, fill, back) -> None:
    mx = max(1, int(mx or 1))
    cur = max(0, int(cur or 0))
    draw.rounded_rectangle((x, y, x + w, y + h), radius=4, fill=back)
    frac = min(1.0, cur / mx)
    if frac > 0:
        draw.rounded_rectangle((x, y, x + max(6, int(w * frac)), y + h), radius=4, fill=fill)


def _portrait(pet: dict[str, Any], size: int = 118) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rar = pet.get("rarity") or COMMON
    rim = RARITY_TINT.get(rar, (140, 140, 140))
    fill = _tint(str(pet.get("id") or ""))
    draw.rounded_rectangle((1, 1, size - 2, size - 2), radius=16, fill=fill + (255,), outline=rim + (255,), width=4)
    inner = (max(20, fill[0] // 3), max(20, fill[1] // 3), max(24, fill[2] // 3), 255)
    draw.ellipse((18, 22, size - 19, size - 17), fill=inner)
    initials = "".join(ch[0] for ch in str(pet.get("name") or pet.get("id") or "?").split()[:2]).upper()
    draw.text((size / 2, size / 2 - 4), initials or "?", font=_font(28, True), fill=INK + (255,), anchor="mm")
    wep = pet.get("weapon")
    if isinstance(wep, dict) and wep.get("kind"):
        icon = Image.open(weapon_icon_png(str(wep["kind"]), wep.get("rarity"), size=36)).convert("RGBA")
        img.alpha_composite(icon, (size - 40, size - 40))
    return img


def _stats_block(draw: ImageDraw.ImageDraw, x: int, y: int, pet: dict[str, Any]) -> None:
    hp = max(0, int(pet.get("hp") or 0))
    mx = max(1, int(pet.get("max_hp") or 1))
    wp = max(0, int(pet.get("wp") or 0))
    wpx = max(1, int(pet.get("max_wp") or 1))
    _bar(draw, x, y, 220, 16, hp, mx, HP_RED, HP_BACK)
    draw.text((x + 226, y + 7), f"{hp}/{mx}", font=_font(13, True), fill=INK, anchor="lm")
    _bar(draw, x, y + 24, 220, 16, wp, wpx, WP_BLUE, WP_BACK)
    draw.text((x + 226, y + 31), f"{wp}/{wpx}", font=_font(13, True), fill=INK, anchor="lm")
    rows = (
        (int(pet.get("atk") or 0), STR_C),
        (int(pet.get("mag") or 0), MAG_C),
        (f"{int(pet.get('pr') or 0)}%", RES_C),
    )
    sy = y + 50
    for val, color in rows:
        draw.rounded_rectangle((x, sy, x + 14, sy + 14), radius=3, fill=color)
        draw.text((x + 20, sy + 6), str(val), font=_font(13, True), fill=INK, anchor="lm")
        sy += 18


def render_battle_png(
    player: list[dict[str, Any]],
    enemy: list[dict[str, Any]],
    *,
    turn: int,
    max_turns: int = MAX_TURNS,
) -> io.BytesIO:
    rows = max(len(player), len(enemy), 1)
    height = NAME_H + rows * ROW_H + 28
    img = Image.new("RGB", (BOARD_W, height), BG)
    draw = ImageDraw.Draw(img)
    mid = BOARD_W // 2
    draw.line((mid, NAME_H, mid, height - 24), fill=PANEL_EDGE, width=2)
    draw.text((PAD + 8, 10), "Your team", font=_font(16, True), fill=INK)
    draw.text((BOARD_W - PAD - 8, 10), "Enemy team", font=_font(16, True), fill=INK, anchor="ra")

    for i in range(rows):
        top = NAME_H + i * ROW_H
        draw.rounded_rectangle((PAD, top + 4, mid - 8, top + ROW_H - 6), radius=12, fill=PANEL, outline=PANEL_EDGE)
        draw.rounded_rectangle((mid + 8, top + 4, BOARD_W - PAD, top + ROW_H - 6), radius=12, fill=PANEL, outline=PANEL_EDGE)
        if i < len(player):
            pet = player[i]
            port = _portrait(pet)
            img.paste(port, (PAD + 10, top + 18), port)
            label = f"L. {pet.get('level', 1)}  {pet.get('name') or pet.get('id')}"
            if pet.get("hp", 1) <= 0:
                label += "  KO"
            draw.text((PAD + 140, top + 16), label, font=_font(15, True), fill=INK)
            wep = pet.get("weapon")
            gear = f"{wep['emoji']} {wep['name']}" if isinstance(wep, dict) else "no weapon"
            draw.text((PAD + 140, top + 36), gear, font=_font(12), fill=MUTED)
            _stats_block(draw, PAD + 140, top + 58, pet)
        if i < len(enemy):
            pet = enemy[i]
            port = _portrait(pet)
            img.paste(port, (BOARD_W - PAD - 128, top + 18), port)
            label = f"L. {pet.get('level', 1)}  {pet.get('name') or pet.get('id')}"
            if pet.get("hp", 1) <= 0:
                label += "  KO"
            draw.text((mid + 20, top + 16), label, font=_font(15, True), fill=INK)
            wep = pet.get("weapon")
            gear = f"{wep['emoji']} {wep['name']}" if isinstance(wep, dict) else "no weapon"
            draw.text((mid + 20, top + 36), gear, font=_font(12), fill=MUTED)
            _stats_block(draw, mid + 20, top + 58, pet)

    draw.text((mid, height - 14), f"Turn {turn} / {max_turns}", font=_font(14, True), fill=MUTED, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "battle.png"
    return buf


def apply_action(attacker: dict[str, Any], allies: list[dict[str, Any]], foes: list[dict[str, Any]], rng) -> str:
    from .aether_hunt import animal_label

    living = [p for p in foes if p["hp"] > 0]
    if not living:
        return ""
    wep = attacker.get("weapon") if isinstance(attacker.get("weapon"), dict) else None
    style = (wep or {}).get("style") or "strike"
    cost = {"strike": 8, "cleave": 12, "mend": 10}.get(style, 8)
    used_weapon = bool(wep) and attacker["wp"] >= cost
    if used_weapon:
        attacker["wp"] -= cost
    name = animal_label(attacker["id"])
    if used_weapon and style == "mend":
        wounded = [p for p in allies if p["hp"] > 0]
        if not wounded:
            return f"{name} has no ally to mend."
        target = min(wounded, key=lambda p: p["hp"] / max(1, p["max_hp"]))
        heal = max(6, int(attacker["mag"] * 0.55) + rng.randint(-2, 3))
        target["hp"] = min(target["max_hp"], target["hp"] + heal)
        return f"{name} mends {animal_label(target['id'])} for {heal} HP."
    if used_weapon and style == "cleave":
        bits = []
        dmg = max(1, int(attacker["atk"] * 0.7) + rng.randint(-2, 2))
        for target in list(living):
            taken = max(1, int(dmg * (100 - int(target.get("pr") or 0)) / 100))
            target["hp"] = max(0, target["hp"] - taken)
            mark = "KO" if target["hp"] <= 0 else f"{target['hp']} HP"
            bits.append(f"{animal_label(target['id'])} {taken} ({mark})")
        return f"{name} cleaves " + ", ".join(bits) + "."
    target = rng.choice(living)
    raw = attacker["atk"] if not used_weapon else attacker["atk"] + int((wep or {}).get("atk") or 0) // 2
    resist = int(target.get("pr") or 0) if not used_weapon else int(target.get("mr") or 0)
    dmg = max(1, int(raw * (100 - resist) / 100) + rng.randint(-2, 2))
    target["hp"] = max(0, target["hp"] - dmg)
    mark = "KO" if target["hp"] <= 0 else f"{target['hp']} HP"
    verb = "uses a weapon on" if used_weapon else "hits"
    return f"{name} {verb} {animal_label(target['id'])} for {dmg}. {mark}."


def play_turns(player: list[dict[str, Any]], enemy: list[dict[str, Any]], rng) -> dict[str, Any]:
    frames = [{"turn": 1, "player": _snap_side(player), "enemy": _snap_side(enemy), "lines": []}]
    log: list[str] = []
    rounds = 0
    while any(p["hp"] > 0 for p in player) and any(p["hp"] > 0 for p in enemy) and rounds < MAX_TURNS:
        rounds += 1
        lines: list[str] = []
        order: list[tuple[str, dict[str, Any]]] = []
        for i in range(max(len(player), len(enemy))):
            if i < len(player) and player[i]["hp"] > 0:
                order.append(("you", player[i]))
            if i < len(enemy) and enemy[i]["hp"] > 0:
                order.append(("foe", enemy[i]))
        for side, attacker in order:
            if attacker["hp"] <= 0:
                continue
            allies = player if side == "you" else enemy
            foes = enemy if side == "you" else player
            if not any(p["hp"] > 0 for p in foes):
                break
            line = apply_action(attacker, allies, foes, rng)
            if line:
                lines.append(line)
                log.append(line)
        frames.append({"turn": min(MAX_TURNS, rounds + 1), "player": _snap_side(player), "enemy": _snap_side(enemy), "lines": lines})
        if not any(p["hp"] > 0 for p in player) or not any(p["hp"] > 0 for p in enemy):
            break
    you_live = any(p["hp"] > 0 for p in player)
    foe_live = any(p["hp"] > 0 for p in enemy)
    if you_live and not foe_live:
        result = "win"
    elif foe_live and not you_live:
        result = "lose"
    else:
        result = "draw"
    return {"result": result, "log": log[-8:], "rounds": rounds, "player": player, "enemy": enemy, "frames": frames}
