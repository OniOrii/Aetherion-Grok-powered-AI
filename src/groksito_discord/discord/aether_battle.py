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
    """Dense text under the board: L.lvl · name · weapon badge (PNG board unchanged)."""
    from .aether_gear import rarity_mark
    from .aether_hunt import animal_label

    bits = []
    for pet in side:
        wep = pet.get("weapon") if isinstance(pet.get("weapon"), dict) else None
        if wep:
            rar = wep.get("rarity") or "common"
            badge = f"{rarity_mark(rar)}{wep.get('emoji', '')}"
        else:
            badge = "*no weapon*"
        emoji = pet.get("emoji") or ""
        name = pet.get("name") or animal_label(pet.get("id") or "")
        lvl = pet.get("level", 1)
        bits.append(f"L.{lvl} · {emoji} {name} · {badge}")
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
        n = max(1, int(result.get("crate_today") or 1))
        from .aether_hunt import daily_resets_in
        line += f" You found a **weapon crate**! `[{n}/3] RESETS IN: {daily_resets_in()}`"
    return line


def resist_mitigation(res: int | float | None) -> float:
    """OwO ``res/(100+res)*0.8`` — soft resist, asymptote 80% mitigation."""
    r = max(0.0, float(res or 0))
    return (r / (100.0 + r)) * 0.8


def apply_resist(raw: int | float, res: int | float | None) -> int:
    """Apply PR/MR mitigation; always at least 1 damage when raw > 0."""
    base = max(0, int(round(float(raw or 0))))
    if base <= 0:
        return 0
    dealt = int(round(base * (1.0 - resist_mitigation(res))))
    return max(1, dealt)


def _hooks_of(pet: dict[str, Any]) -> dict[str, float]:
    raw = pet.get("passive_hooks")
    if isinstance(raw, dict) and raw:
        return raw
    wep = pet.get("weapon") if isinstance(pet.get("weapon"), dict) else None
    if not wep:
        return {}
    from .aether_gear import weapon_hooks
    return weapon_hooks(wep.get("kind"), wep.get("quality") or 50)


def _amp_damage(raw: float, attacker: dict[str, Any], target: dict[str, Any], rng, *, used_weapon: bool = False) -> int:
    """Apply SoT passive damage amps (missing-HP, execute, hybrid, spend, crit, boss…)."""
    hooks = _hooks_of(attacker)
    dmg = float(raw)
    miss_amp = float(hooks.get("missing_hp_amp") or 0)
    if miss_amp:
        mx = max(1, int(attacker.get("max_hp") or 1))
        missing = max(0.0, 1.0 - (int(attacker.get("hp") or 0) / mx))
        bands = int(missing * 10)
        dmg *= 1.0 + (bands * miss_amp / 100.0)
    # Execute / low-HP target bonuses
    t_mx = max(1, int(target.get("max_hp") or 1))
    t_ratio = int(target.get("hp") or 0) / t_mx
    exe = float(hooks.get("execute_pct") or 0)
    if exe and t_ratio < 0.30:
        dmg *= 1.0 + exe / 100.0
    low = float(hooks.get("low_hp_target_bonus_pct") or 0)
    if low and t_ratio < 0.50:
        dmg *= 1.0 + low / 100.0
    hybrid = float(hooks.get("hybrid_amp_pct") or 0)
    if hybrid:
        dmg *= 1.0 + hybrid / 100.0
    if used_weapon:
        post = float(hooks.get("post_spend_dmg_pct") or 0)
        if post:
            dmg *= 1.0 + post / 100.0
    if not attacker.get("acted") and float(hooks.get("first_strike") or 0):
        dmg *= 1.0 + float(hooks["first_strike"]) / 100.0
    # Drift momentum: consecutive hits on same target
    succ = float(hooks.get("successive_hit_pct") or 0)
    if succ:
        last = attacker.get("_last_target_id")
        stacks = int(attacker.get("_hit_stacks") or 0)
        if last == target.get("id"):
            stacks = min(4, stacks + 1)
        else:
            stacks = 1
        attacker["_last_target_id"] = target.get("id")
        attacker["_hit_stacks"] = stacks
        dmg *= 1.0 + (stacks * succ / 100.0)
    # Fog Blind mark
    mark_b = float(hooks.get("mark_bonus_pct") or 0)
    if mark_b and target.get("_marked_by") == attacker.get("id"):
        dmg *= 1.0 + mark_b / 100.0
    boss_pct = float(hooks.get("boss_bonus_pct") or 0)
    if boss_pct and (target.get("raid_boss") or int(target.get("max_hp") or 0) >= 160):
        dmg *= 1.0 + boss_pct / 100.0
    chance = float(hooks.get("crit_chance") or 0)
    crit_d = float(hooks.get("crit_damage") or 0)
    if chance and crit_d and rng.random() * 100.0 < chance:
        dmg *= 1.0 + crit_d / 100.0
    return max(1, int(round(dmg)))


def _resist_for(attacker: dict[str, Any], target: dict[str, Any], base_resist, *, magical: bool) -> float:
    resist = float(base_resist or 0)
    hooks = _hooks_of(attacker)
    if magical:
        ignore = float(hooks.get("ignore_mr_pct") or 0)
        if ignore:
            resist = max(0.0, resist * (1.0 - ignore / 100.0))
    else:
        pierce = float(hooks.get("pierce_pr_pct") or 0) + float(hooks.get("ignore_pr_pct") or 0)
        if pierce:
            resist = max(0.0, resist * (1.0 - pierce / 100.0))
    # Adaptive shell stacks on target
    adapt = float(_hooks_of(target).get("adapt_resist_pct") or 0)
    if adapt:
        key = "_adapt_mr" if magical else "_adapt_pr"
        stacks = int(target.get(key) or 0)
        resist = resist * (1.0 + stacks * adapt / 100.0)
    return resist


def _deal_damage(
    attacker: dict[str, Any],
    target: dict[str, Any],
    amount: int,
    *,
    allies: list[dict[str, Any]] | None = None,
    foes: list[dict[str, Any]] | None = None,
    magical: bool = True,
    rng=None,
) -> int:
    """Shield → evade → WP mitigate → HP; thorns / death / on-hit converters."""
    import random as _random
    rng = rng or _random.Random()
    dmg = max(0, int(amount))
    if dmg <= 0:
        return 0
    th = _hooks_of(target)
    # Mist Step evade
    evade = float(th.get("evade_pct") or 0)
    if evade and rng.random() * 100.0 < evade:
        return 0
    # Aegis Spend: negate % by spending WP
    mit = float(th.get("wp_mitigate_pct") or 0)
    if mit and int(target.get("wp") or 0) > 0:
        negated = int(round(dmg * mit / 100.0))
        spend = min(int(target["wp"]), max(1, negated // 2))
        target["wp"] = int(target["wp"]) - spend
        dmg = max(0, dmg - negated)
    shield = int(target.get("shield") or 0)
    if shield > 0 and dmg > 0:
        absorb = min(shield, dmg)
        target["shield"] = shield - absorb
        dmg -= absorb
    if dmg <= 0:
        return 0
    target["hp"] = max(0, int(target["hp"]) - dmg)
    # Adaptive shell: stack resist of last damage type
    if float(th.get("adapt_resist_pct") or 0):
        if magical:
            target["_adapt_mr"] = min(5, int(target.get("_adapt_mr") or 0) + 1)
            target["_adapt_pr"] = 0
        else:
            target["_adapt_pr"] = min(5, int(target.get("_adapt_pr") or 0) + 1)
            target["_adapt_mr"] = 0
    # Thorns
    thorns = float(th.get("thorns_pct") or 0)
    if thorns and attacker.get("hp", 0) > 0:
        reflect = max(1, int(round(dmg * thorns / 100.0)))
        attacker["hp"] = max(0, int(attacker["hp"]) - reflect)
    # Death nuke / parting gift
    if int(target.get("hp") or 0) <= 0:
        nuke = float(th.get("death_nuke_pct") or 0)
        if nuke and attacker.get("hp", 0) > 0:
            chunk = max(1, int(round(int(target.get("max_hp") or 1) * nuke / 100.0)))
            chunk = apply_resist(chunk, attacker.get("mr"))
            attacker["hp"] = max(0, int(attacker["hp"]) - chunk)
        heal_p = float(th.get("death_ally_heal_pct") or 0)
        wp_p = float(th.get("death_ally_wp_pct") or 0)
        if allies and (heal_p or wp_p):
            for ally in allies:
                if ally is target or int(ally.get("hp") or 0) <= 0:
                    continue
                if heal_p:
                    ally["hp"] = min(int(ally["max_hp"]), int(ally["hp"]) + max(1, int(round(int(target["max_hp"]) * heal_p / 100.0))))
                if wp_p:
                    gain = max(1, int(round(int(target.get("max_wp") or 40) * wp_p / 100.0)))
                    ally["wp"] = min(int(ally.get("max_wp") or ally.get("wp") or 0), int(ally.get("wp") or 0) + gain)
        # Killer on-kill WP
        kill_wp = float(_hooks_of(attacker).get("on_kill_wp_pct") or 0)
        if kill_wp:
            gain = max(1, int(round(int(attacker.get("max_wp") or 40) * kill_wp / 100.0)))
            attacker["wp"] = min(int(attacker.get("max_wp") or 0), int(attacker.get("wp") or 0) + gain)
    # On-hit converters for attacker
    ah = _hooks_of(attacker)
    life = float(ah.get("lifesteal_pct") or 0)
    if life and attacker.get("hp", 0) > 0:
        heal = max(1, int(round(dmg * life / 100.0)))
        attacker["hp"] = min(int(attacker["max_hp"]), int(attacker["hp"]) + heal)
    refund = float(ah.get("wp_refund_pct") or 0)
    if refund:
        gain = max(1, int(round(dmg * refund / 100.0)))
        before = int(attacker.get("wp") or 0)
        attacker["wp"] = min(int(attacker.get("max_wp") or before), before + gain)
        gained = int(attacker["wp"]) - before
        # Surge Echo: WP restore → MAG nuke
        nuke_pct = float(ah.get("on_wp_nuke_pct") or 0)
        if nuke_pct and gained > 0 and foes:
            living = [p for p in foes if int(p.get("hp") or 0) > 0 and p is not target]
            if living:
                splash_t = rng.choice(living)
                splash = max(1, apply_resist(int(round(gained * nuke_pct / 100.0)), splash_t.get("mr")))
                splash_t["hp"] = max(0, int(splash_t["hp"]) - splash)
    drain = float(ah.get("wp_drain_pct") or 0)
    if drain:
        stolen = max(1, int(round(dmg * drain / 100.0)))
        target["wp"] = max(0, int(target.get("wp") or 0) - stolen)
        attacker["wp"] = min(int(attacker.get("max_wp") or 0), int(attacker.get("wp") or 0) + stolen)
    # Burn / DoT approximated as immediate bonus true damage chunk
    burn = float(ah.get("burn_pct") or 0) + float(ah.get("dot_pct") or 0)
    if burn and int(target.get("hp") or 0) > 0:
        extra = max(1, int(round(dmg * burn / 100.0)))
        target["hp"] = max(0, int(target["hp"]) - extra)
    # Splash / chain / bounce to a second foe
    splash_pct = float(ah.get("mag_splash_pct") or 0) + float(ah.get("chain_splash_pct") or 0) + float(ah.get("bounce_hit_pct") or 0)
    if splash_pct and foes:
        living = [p for p in foes if int(p.get("hp") or 0) > 0 and p is not target]
        if living:
            splash_t = rng.choice(living)
            splash = max(1, apply_resist(int(round(dmg * splash_pct / 100.0)), splash_t.get("mr")))
            splash_t["hp"] = max(0, int(splash_t["hp"]) - splash)
    # Fog Blind: mark on first hit
    if float(ah.get("mark_bonus_pct") or 0) and not target.get("_marked_by"):
        target["_marked_by"] = attacker.get("id")
        target["_mark_turns"] = 2
    return dmg


def apply_action(attacker: dict[str, Any], allies: list[dict[str, Any]], foes: list[dict[str, Any]], rng) -> str:
    """One auto action: physical (ATK/STR vs PR) or weapon (MAG vs MR, spends WP).

    Unique weapon passives (AETHERION_WEAPON_PASSIVES.md) lightly modify combat.
    """
    from .aether_hunt import animal_label
    from .aether_gear import style_wp_cost

    living = [p for p in foes if p["hp"] > 0]
    if not living:
        return ""
    wep = attacker.get("weapon") if isinstance(attacker.get("weapon"), dict) else None
    style = (wep or {}).get("style") or "strike"
    cost = style_wp_cost(style)
    hooks = _hooks_of(attacker)
    used_weapon = bool(wep) and int(attacker.get("wp") or 0) >= cost
    if used_weapon:
        attacker["wp"] = int(attacker["wp"]) - cost
    name = animal_label(attacker["id"])
    if used_weapon and style == "mend":
        wounded = [p for p in allies if p["hp"] > 0]
        if not wounded:
            attacker["acted"] = True
            return f"{name} has no ally to mend (weapon)."
        target = min(wounded, key=lambda p: p["hp"] / max(1, p["max_hp"]))
        heal = max(6, int(attacker.get("mag") or 0) * 55 // 100 + rng.randint(-2, 3))
        mend_b = float(hooks.get("mend_bonus") or 0)
        if mend_b:
            heal = max(1, int(round(heal * (1.0 + mend_b / 100.0))))
        chance = float(hooks.get("crit_chance") or 0)
        crit_d = float(hooks.get("crit_damage") or 0)
        if chance and crit_d and rng.random() * 100.0 < chance:
            heal = max(1, int(round(heal * (1.0 + crit_d / 100.0))))
        amp = float(_hooks_of(target).get("heal_amp_pct") or 0)
        if amp:
            heal = max(1, int(round(heal * (1.0 + amp / 100.0))))
        target["hp"] = min(target["max_hp"], target["hp"] + heal)
        # Retributive Glow: on heal → MAG nuke
        glow = float(hooks.get("on_heal_nuke_pct") or 0) + float(_hooks_of(target).get("on_heal_nuke_pct") or 0)
        if glow:
            living2 = [p for p in foes if p["hp"] > 0]
            if living2:
                foe = rng.choice(living2)
                nuke = max(1, apply_resist(int(round(heal * glow / 100.0)), foe.get("mr")))
                _deal_damage(attacker, foe, nuke, allies=allies, foes=foes, magical=True, rng=rng)
        attacker["acted"] = True
        return f"{name} mends {animal_label(target['id'])} for {heal} HP (weapon)."
    if used_weapon and style == "cleave":
        bits = []
        raw = max(1, int(attacker.get("mag") or 0) * 70 // 100)
        for target in list(living):
            resist = _resist_for(attacker, target, target.get("mr"), magical=True)
            taken = _amp_damage(apply_resist(raw, resist) + rng.randint(-2, 2), attacker, target, rng, used_weapon=True)
            dealt = _deal_damage(attacker, target, taken, allies=allies, foes=foes, magical=True, rng=rng)
            mark = "KO" if target["hp"] <= 0 else f"{target['hp']} HP"
            bits.append(f"{animal_label(target['id'])} {dealt} ({mark})")
        attacker["acted"] = True
        return f"{name} cleaves " + ", ".join(bits) + " (weapon)."
    target = rng.choice(living)
    if used_weapon:
        raw = max(1, int(attacker.get("mag") or 0))
        resist = _resist_for(attacker, target, target.get("mr"), magical=True)
        path = "weapon"
        verb = "strikes"
        magical = True
    else:
        raw = max(1, int(attacker.get("atk") or 0))
        resist = _resist_for(attacker, target, target.get("pr"), magical=False)
        path = "phys"
        verb = "hits"
        magical = False
    dmg = _amp_damage(apply_resist(raw, resist) + rng.randint(-2, 2), attacker, target, rng, used_weapon=used_weapon)
    dealt = _deal_damage(attacker, target, dmg, allies=allies, foes=foes, magical=magical, rng=rng)
    # Radiant Bolt: phys also deals MAG portion
    if not used_weapon:
        conv = float(hooks.get("convert_phys_to_mag_pct") or 0)
        if conv and int(target.get("hp") or 0) > 0:
            extra = max(1, apply_resist(int(round(dmg * conv / 100.0)), target.get("mr")))
            _deal_damage(attacker, target, extra, allies=allies, foes=foes, magical=True, rng=rng)
    attacker["acted"] = True
    mark = "KO" if target["hp"] <= 0 else f"{target['hp']} HP"
    return f"{name} {verb} {animal_label(target['id'])} for {dealt} ({path}). {mark}."



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
        # End-of-turn passives (Second Wind / Ley Tick)
        for pet in list(player) + list(enemy):
            if int(pet.get("hp") or 0) <= 0:
                continue
            eh = _hooks_of(pet)
            eot_h = float(eh.get("eot_heal_pct") or 0)
            if eot_h:
                heal = max(1, int(round(int(pet["max_hp"]) * eot_h / 100.0)))
                pet["hp"] = min(int(pet["max_hp"]), int(pet["hp"]) + heal)
            eot_w = float(eh.get("eot_wp_flat") or 0)
            if eot_w:
                pet["wp"] = min(int(pet.get("max_wp") or 0), int(pet.get("wp") or 0) + int(round(eot_w)))
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
