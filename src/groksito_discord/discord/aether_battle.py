"""OwO-style PvE battle board and auto turn animation frames."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from .aether_gear import COMMON, WEAPON_BY_ID
from .weapon_art import weapon_icon_png

_PORTRAIT_DIR = Path(__file__).resolve().parent / "assets" / "hunt_portraits"

MAX_TURNS = 99
BOARD_W = 900
ROW_H = 128
PAD = 10
HEAD_H = 8
FOOT_H = 28

BG = (22, 24, 32)
PANEL = (36, 40, 54)
PANEL_DEAD = (28, 24, 30)
PANEL_EDGE = (64, 70, 90)
INK = (236, 230, 220)
MUTED = (168, 172, 184)
HP_RED = (214, 64, 72)
HP_TRAIL = (214, 160, 64)
HP_BACK = (62, 28, 32)
WP_BLUE = (56, 132, 214)
WP_BACK = (28, 44, 78)

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
        50 + int(digest[0:2], 16) % 160,
        46 + int(digest[2:4], 16) % 150,
        58 + int(digest[4:6], 16) % 150,
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
    draw.rounded_rectangle((x, y, x + w, y + h), radius=3, fill=back)
    frac = min(1.0, cur / mx)
    if frac > 0:
        draw.rounded_rectangle((x, y, x + max(4, int(w * frac)), y + h), radius=3, fill=fill)


def _shape(draw: ImageDraw.ImageDraw, kind: str, box: tuple[int, int, int, int], color) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    if kind == "bug":
        draw.ellipse((cx - 22, cy - 16, cx + 22, cy + 22), fill=color)
        draw.ellipse((cx - 12, cy - 28, cx + 12, cy - 6), fill=color)
        draw.line((cx - 18, cy - 22, cx - 30, cy - 34), fill=color, width=3)
        draw.line((cx + 18, cy - 22, cx + 30, cy - 34), fill=color, width=3)
    elif kind == "wing":
        draw.polygon([(cx, cy - 28), (cx - 34, cy + 10), (cx - 8, cy + 18)], fill=color)
        draw.polygon([(cx, cy - 28), (cx + 34, cy + 10), (cx + 8, cy + 18)], fill=color)
        draw.ellipse((cx - 14, cy - 8, cx + 14, cy + 26), fill=tuple(min(255, c + 30) for c in color))
    elif kind == "serp":
        draw.polygon([(cx - 8, cy + 30), (cx + 8, cy + 30), (cx + 4, cy - 6), (cx - 4, cy - 6)], fill=color)
        draw.ellipse((cx - 18, cy - 30, cx + 18, cy + 4), fill=color)
        draw.ellipse((cx - 8, cy - 20, cx - 2, cy - 14), fill=(20, 20, 24))
        draw.ellipse((cx + 2, cy - 20, cx + 8, cy - 14), fill=(20, 20, 24))
    elif kind == "squat":
        draw.ellipse((cx - 28, cy - 8, cx + 28, cy + 28), fill=color)
        draw.ellipse((cx - 16, cy - 26, cx + 16, cy + 2), fill=color)
        draw.ellipse((cx - 20, cy + 20, cx - 8, cy + 32), fill=color)
        draw.ellipse((cx + 8, cy + 20, cx + 20, cy + 32), fill=color)
    else:
        draw.ellipse((cx - 22, cy - 8, cx + 22, cy + 28), fill=color)
        draw.polygon([(cx - 22, cy - 4), (cx - 30, cy - 28), (cx - 8, cy - 10)], fill=color)
        draw.polygon([(cx + 22, cy - 4), (cx + 30, cy - 28), (cx + 8, cy - 10)], fill=color)
        draw.ellipse((cx - 16, cy - 18, cx + 16, cy + 10), fill=tuple(min(255, c + 24) for c in color))
        draw.ellipse((cx - 8, cy - 8, cx - 2, cy - 2), fill=(20, 20, 24))
        draw.ellipse((cx + 2, cy - 8, cx + 8, cy - 2), fill=(20, 20, 24))


def _family(animal_id: str) -> str:
    text = (animal_id or "").lower()
    if any(word in text for word in ("moth", "gnat", "beetle", "sprite", "mite")):
        return "bug"
    if any(word in text for word in ("finch", "owl", "heron", "drake", "wyrm", "leviathan")):
        return "wing"
    if any(word in text for word in ("serpent", "skink", "eel")):
        return "serp"
    if any(word in text for word in ("toad", "crab", "boar", "ram", "mouse")):
        return "squat"
    return "beast"


def _load_portrait_asset(animal_id: str, size: int) -> Image.Image | None:
    """Load a pre-baked Aetherion species portrait if present."""
    aid = (animal_id or "").strip().lower()
    if not aid:
        return None
    path = _PORTRAIT_DIR / f"{aid}.png"
    if not path.is_file():
        return None
    try:
        raw = Image.open(path).convert("RGBA")
    except OSError:
        return None
    if raw.size != (size, size):
        raw = raw.resize((size, size), Image.Resampling.LANCZOS)
    return raw


def _portrait(pet: dict[str, Any], size: int = 96) -> Image.Image:
    """Battle-board animal tile — prefer species PNG, else procedural silhouette."""
    rar = pet.get("rarity") or COMMON
    rim = RARITY_TINT.get(rar, (140, 140, 140))
    dead = int(pet.get("hp") or 0) <= 0
    asset = _load_portrait_asset(str(pet.get("id") or ""), size)
    if asset is not None:
        img = asset
        if dead:
            # Dim KO portraits so living species still read first
            img = ImageEnhance.Brightness(img).enhance(0.38)
            img = ImageEnhance.Color(img).enhance(0.35)
    else:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        fill = _tint(str(pet.get("id") or ""))
        if dead:
            fill = tuple(max(18, c // 3) for c in fill)
            rim = (90, 90, 96)
        draw.rounded_rectangle(
            (1, 1, size - 2, size - 2),
            radius=14,
            fill=(18, 20, 28, 255),
            outline=rim + (255,),
            width=4,
        )
        _shape(draw, _family(str(pet.get("id") or "")), (8, 8, size - 8, size - 8), fill)
    wep = pet.get("weapon")
    if isinstance(wep, dict) and wep.get("kind"):
        icon = Image.open(weapon_icon_png(str(wep["kind"]), wep.get("rarity"), size=28)).convert("RGBA")
        img.alpha_composite(icon, (size - 32, size - 32))
    return img


def _card(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    pet: dict[str, Any],
    box: tuple[int, int, int, int],
    *,
    flip: bool,
) -> None:
    x0, y0, x1, y1 = box
    dead = int(pet.get("hp") or 0) <= 0
    draw.rounded_rectangle(box, radius=12, fill=PANEL_DEAD if dead else PANEL, outline=PANEL_EDGE)
    port = _portrait(pet)
    if flip:
        # Enemy column: portrait on the right — keep bars/numbers clear of it
        img.paste(port, (x1 - 106, y0 + 16), port)
        text_x = x0 + 14
        content_right = x1 - 112
    else:
        img.paste(port, (x0 + 10, y0 + 16), port)
        text_x = x0 + 118
        content_right = x1 - 10
    name = str(pet.get("name") or pet.get("id") or "pet")
    label = f"L.{pet.get('level', 1)}  {name}"
    if dead:
        label += "  KO"
    draw.text((text_x, y0 + 14), label[:22], font=_font(15, True), fill=INK)
    wep = pet.get("weapon")
    gear = f"{wep.get('emoji', '')} {wep.get('name', 'weapon')}" if isinstance(wep, dict) else "no weapon"
    draw.text((text_x, y0 + 34), gear[:26], font=_font(12), fill=MUTED)
    hp = max(0, int(pet.get("hp") or 0))
    mx = max(1, int(pet.get("max_hp") or 1))
    wp = max(0, int(pet.get("wp") or 0))
    wpx = max(1, int(pet.get("max_wp") or 1))
    # Leave room for HP/WP tags + numeric readouts; never spill into the portrait
    tag_w = 28
    bar_w = max(80, content_right - text_x - 78 - tag_w)
    draw.text((text_x, y0 + 64), "HP", font=_font(11, True), fill=HP_RED, anchor="lm")
    _bar(draw, text_x + tag_w, y0 + 58, bar_w, 14, hp, mx, HP_RED, HP_BACK)
    draw.text((text_x + tag_w + bar_w + 8, y0 + 64), f"{hp}/{mx}", font=_font(12, True), fill=INK, anchor="lm")
    draw.text((text_x, y0 + 85), "WP", font=_font(11, True), fill=WP_BLUE, anchor="lm")
    _bar(draw, text_x + tag_w, y0 + 80, bar_w, 12, wp, wpx, WP_BLUE, WP_BACK)
    draw.text((text_x + tag_w + bar_w + 8, y0 + 85), f"{wp}/{wpx}", font=_font(11), fill=MUTED, anchor="lm")


def render_battle_png(
    player: list[dict[str, Any]],
    enemy: list[dict[str, Any]],
    *,
    turn: int,
    max_turns: int = MAX_TURNS,
    lines: list[str] | None = None,
) -> io.BytesIO:
    rows = max(len(player), len(enemy), 1)
    extra = 22 if lines else 0
    height = HEAD_H + rows * ROW_H + FOOT_H + extra
    img = Image.new("RGB", (BOARD_W, height), BG)
    draw = ImageDraw.Draw(img)
    mid = BOARD_W // 2
    draw.line((mid, 4, mid, HEAD_H + rows * ROW_H - 4), fill=PANEL_EDGE, width=2)
    for i in range(rows):
        top = HEAD_H + i * ROW_H
        left = (PAD, top + 6, mid - 8, top + ROW_H - 6)
        right = (mid + 8, top + 6, BOARD_W - PAD, top + ROW_H - 6)
        if i < len(player):
            _card(img, draw, player[i], left, flip=False)
        else:
            draw.rounded_rectangle(left, radius=12, fill=(28, 30, 38), outline=PANEL_EDGE)
        if i < len(enemy):
            _card(img, draw, enemy[i], right, flip=True)
        else:
            draw.rounded_rectangle(right, radius=12, fill=(28, 30, 38), outline=PANEL_EDGE)
    if lines:
        note = lines[-1][:90]
        draw.text((mid, height - 34), note, font=_font(13), fill=MUTED, anchor="mm")
    total = max(1, int(max_turns or turn or 1))
    draw.text((mid, height - 12), f"Turn {turn}/{total}", font=_font(13, True), fill=MUTED, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = "battle.png"
    return buf


def roster_field(side: list[dict[str, Any]]) -> str:
    """OwO image-mode team field: L. lvl emoji - weapon (compact / scannable)."""
    bits = []
    for pet in side:
        wep = pet.get("weapon") if isinstance(pet.get("weapon"), dict) else None
        if wep:
            gear = f"{wep.get('emoji', '')}{wep.get('name', 'weapon')}"
        else:
            gear = "*no weapon*"
        emoji = pet.get("emoji") or ""
        bits.append(f"L. {pet.get('level', 1)} {emoji} - {gear}")
    return "\n".join(bits) or "*empty*"


def result_caption(result: dict[str, Any]) -> str:
    outcome = result.get("result") or "draw"
    rounds = max(1, int(result.get("rounds") or 1))
    word = {"win": "won", "lose": "lost"}.get(outcome, "tied")
    base = int(result.get("xp_base") or 0)
    bonus = int(result.get("xp_bonus") or 0)
    if base <= 0:
        base = int(result.get("xp_gain") or 0) - max(0, bonus)
        if base <= 0:
            base = int(result.get("xp_gain") or 0)
            bonus = 0
    turns = f"{rounds} turn" if rounds == 1 else f"{rounds} turns"
    line = f"You {word} in {turns}! Your team gained {base} xp"
    if bonus > 0:
        line += f" + {bonus} bonus xp"
    streak = int(result.get("streak") or 0)
    prev = int(result.get("prev_streak") or 0)
    if outcome == "win":
        line += f"! Streak: {streak}"
    elif prev > 0:
        line += f"! You lost your streak of {prev} wins..."
    else:
        line += "!"
    if result.get("crate"):
        line += " You found a weapon crate!"
    return line


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
        frames.append(
            {
                "turn": min(MAX_TURNS, rounds + 1) if (
                    any(p["hp"] > 0 for p in player) and any(p["hp"] > 0 for p in enemy) and rounds < MAX_TURNS
                ) else rounds,
                "player": _snap_side(player),
                "enemy": _snap_side(enemy),
                "lines": lines,
            }
        )
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
