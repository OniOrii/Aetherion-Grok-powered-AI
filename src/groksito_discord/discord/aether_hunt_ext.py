"""Test 3 overlay installed onto aether_hunt at import time."""
from __future__ import annotations

import random
import time
from typing import Any

from . import aether_gear as gear
from . import aether_hunt as base
from . import ai_coins

COMMON, UNCOMMON, RARE, EPIC, MYTHIC, ASTRAL, PRIMORDIAL = (
    base.COMMON, base.UNCOMMON, base.RARE, base.EPIC, base.MYTHIC, base.ASTRAL, base.PRIMORDIAL
)
ANIMALS = base.ANIMALS
ANIMAL_BY_ID = base.ANIMAL_BY_ID
TEAM_SIZE = base.TEAM_SIZE
HUNT_COST = base.HUNT_COST
WIN_PAYOUT = base.WIN_PAYOUT
DRAW_PAYOUT = base.DRAW_PAYOUT
RARITY_LABEL = base.RARITY_LABEL
RARITY_WEIGHT = base.RARITY_WEIGHT
_lock = base._lock
_load_store = base._load_store
_save_store = base._save_store
_ensure_user = base._ensure_user
owned_count = base.owned_count
xp_of = base.xp_of
add_xp = base.add_xp
level_of = base.level_of
xp_progress = base.xp_progress
stats_for = base.stats_for
rarity_of = base.rarity_of
rarity_mark = base.rarity_mark
animal_label = base.animal_label
resolve_animal = base.resolve_animal
roll_animal = base.roll_animal
cooldown_left = base.cooldown_left
active_team = base.active_team
zoo_points_for = base.zoo_points_for

LEVEL_CAP = 50
WIP_FOOTER = "WIP \u00b7 Test 3 \u00b7 Ori only"
HUNT_XP = {
    COMMON: 1,
    UNCOMMON: 10,
    RARE: 20,
    EPIC: 400,
    MYTHIC: 1000,
    ASTRAL: 2500,
    PRIMORDIAL: 6000,
}
BATTLE_XP = {"win": 200, "draw": 100, "lose": 50}


def _catch_one(row, animal_id):
    zoo = row.setdefault("zoo", {})
    zoo[animal_id] = owned_count(row, animal_id) + 1
    caught = row.setdefault("caught", {})
    try:
        caught[animal_id] = int(caught.get(animal_id) or 0) + 1
    except (TypeError, ValueError):
        caught[animal_id] = 1


def _rarity_pools(rarity: str, level: int) -> tuple[int, int, int]:
    """PR / MR / WP_MAX from rarity tables, plus light level growth."""
    lvl = max(0, int(level))
    pr0 = int(getattr(base, "RARITY_PR", {}).get(rarity, 6))
    mr0 = int(getattr(base, "RARITY_MR", {}).get(rarity, 6))
    wp0 = int(getattr(base, "RARITY_WP_MAX", {}).get(rarity, 40))
    # Keep a modest level bump so high-level commons still grow.
    pr = min(80, pr0 + lvl)
    mr = min(80, mr0 + lvl // 2)
    wp = wp0 + lvl * 8
    return pr, mr, wp


def _apply_weapon_passives(pet: dict, wep: dict | None) -> None:
    """Flat % hooks + start shield from unique weapon passive (quality-scaled)."""
    if not wep:
        return
    hooks = gear.weapon_hooks(wep.get("kind"), wep.get("quality") or 50)
    pet["passive_hooks"] = hooks
    if not hooks:
        return
    phys_pct = float(hooks.get("bonus_phys_pct") or 0)
    mag_pct = float(hooks.get("bonus_mag_pct") or 0)
    hp_pct = float(hooks.get("bonus_hp_pct") or 0)
    wp_pct = float(hooks.get("bonus_wp_pct") or 0)
    pr_pct = float(hooks.get("bonus_pr_pct") or 0)
    mr_pct = float(hooks.get("bonus_mr_pct") or 0)
    if phys_pct:
        pet["atk"] = max(1, int(round(pet["atk"] * (1.0 + phys_pct / 100.0))))
    if mag_pct:
        pet["mag"] = max(1, int(round(pet["mag"] * (1.0 + mag_pct / 100.0))))
    if hp_pct:
        boost = max(1, int(round(pet["max_hp"] * hp_pct / 100.0)))
        pet["max_hp"] += boost
        pet["hp"] += boost
    if wp_pct:
        boost = max(1, int(round(pet["max_wp"] * wp_pct / 100.0)))
        pet["max_wp"] += boost
        pet["wp"] += boost
    if pr_pct:
        pet["pr"] = int(round(pet["pr"] * (1.0 + pr_pct / 100.0)))
    if mr_pct:
        pet["mr"] = int(round(pet["mr"] * (1.0 + mr_pct / 100.0)))
    shield_pct = float(hooks.get("start_shield_pct") or 0)
    if shield_pct:
        pet["shield"] = max(1, int(round(pet["max_hp"] * shield_pct / 100.0)))
    xp_pct = float(hooks.get("xp_bonus_pct") or 0)
    if xp_pct:
        pet["xp_bonus_pct"] = xp_pct


def _fighter(animal_id, level, weapon=None):
    """Build a battle pet. P/ATK vs PR for physical; M/MAG vs MR for weapon skills.

    Weapon ATK bonus: strike/cleave raise physical ATK; all equipped weapons raise MAG
    so WP-gated skills scale with gear. Mend puts the full bonus on MAG only.
    Rarity scales HP/ATK via stats_for and WP/PR/MR via RARITY_POOL_MULT.
    """
    hp, atk = stats_for(animal_id, level)
    wep = dict(weapon) if isinstance(weapon, dict) else None
    bonus = int((wep or {}).get("atk") or 0) if wep else 0
    style = (wep or {}).get("style") or "strike"
    row = ANIMAL_BY_ID.get(animal_id)
    rarity = row[3] if row else COMMON
    if style == "mend":
        phys = atk  # mend kits punch with base STR only
        mag = atk + bonus
    else:
        phys = atk + bonus
        mag = max(4, atk // 3) + bonus
    pr, mr, wp = _rarity_pools(rarity, level)
    pet = {
        "id": animal_id,
        "name": row[1] if row else animal_id,
        "emoji": row[2] if row else "",
        "rarity": rarity,
        "level": level,
        "hp": hp,
        "max_hp": hp,
        "atk": phys,
        "mag": mag,
        "wp": wp,
        "max_wp": wp,
        "pr": pr,
        "mr": mr,
        "shield": 0,
        "side": "",
        "weapon": wep,
        "acted": False,
        "passive_hooks": {},
    }
    _apply_weapon_passives(pet, wep)
    return pet


# Wild weapons: softer than player crates (PASSIVE_COMBAT_AUDIT.md).
_WILD_WEAPON_WEIGHT = {
    COMMON: 500,
    UNCOMMON: 300,
    RARE: 140,
    EPIC: 50,
    MYTHIC: 10,
}
_ENEMY_ARM_RATE = 0.55
_WEAPON_RARITY_RANK = (COMMON, UNCOMMON, RARE, EPIC, MYTHIC, ASTRAL, PRIMORDIAL)


def _player_gear_caps(player: list) -> tuple[int, int]:
    """Max equipped rarity rank + avg quality (defaults when team is naked)."""
    ranks: list[int] = []
    qualities: list[int] = []
    for pet in player or []:
        wep = pet.get("weapon") if isinstance(pet.get("weapon"), dict) else None
        if not wep:
            continue
        rar = str(wep.get("rarity") or COMMON)
        if rar in _WEAPON_RARITY_RANK:
            ranks.append(_WEAPON_RARITY_RANK.index(rar))
        try:
            qualities.append(int(wep.get("quality") or 50))
        except (TypeError, ValueError):
            qualities.append(50)
    max_rank = max(ranks) if ranks else 0  # Common soft-cap when naked
    avg_q = int(round(sum(qualities) / len(qualities))) if qualities else 40
    return max_rank, avg_q


def _roll_enemy_weapon(player: list, rng: random.Random) -> dict[str, Any]:
    """Wild weapon soft-capped to player gear (+1 rarity tier); quality 20..min(85, avg+15)."""
    max_rank, avg_q = _player_gear_caps(player)
    kind, name, emoji, style = rng.choice(gear.WEAPONS)
    rarity = gear.roll_rarity(_WILD_WEAPON_WEIGHT, rng)
    idx = _WEAPON_RARITY_RANK.index(rarity) if rarity in _WEAPON_RARITY_RANK else 0
    cap = min(len(_WEAPON_RARITY_RANK) - 1, max_rank + 1)
    if idx > cap:
        rarity = _WEAPON_RARITY_RANK[cap]
    lo, hi = gear.WEAPON_ATK[rarity]
    q_hi = max(20, min(85, avg_q + 15))
    quality = rng.randint(20, q_hi)
    atk = rng.randint(lo, hi)
    return {
        "kind": kind,
        "name": name,
        "emoji": emoji,
        "style": style,
        "rarity": rarity,
        "quality": quality,
        "atk": atk,
    }


def _mark_wild_boss(enemy: list) -> None:
    """Bossbrand target in wild PvE: highest animal-rarity foe (HP tie-break)."""
    if not enemy:
        return
    rank = {COMMON: 0, UNCOMMON: 1, RARE: 2, EPIC: 3, MYTHIC: 4, ASTRAL: 5, PRIMORDIAL: 6}
    best = max(
        enemy,
        key=lambda p: (
            rank.get(str(p.get("rarity") or COMMON), 0),
            int(p.get("max_hp") or 0),
        ),
    )
    best["wild_boss"] = True


def build_enemy_team(player, rng):
    """Wild 3v3 — ~55% armed; rarity/quality soft-capped vs player gear; one wild boss."""
    size = TEAM_SIZE
    avg = sum(int(pet.get("level") or 1) for pet in player) / max(1, len(player))
    out = []
    used = set()
    pool = [aid for aid, *_rest in ANIMALS]
    rng.shuffle(pool)
    for _i in range(size):
        pick = next((aid for aid in pool if aid not in used), pool[0])
        used.add(pick)
        lvl = min(LEVEL_CAP, max(1, int(round(avg)) + rng.randint(-1, 1)))
        wep = _roll_enemy_weapon(player, rng) if rng.random() < _ENEMY_ARM_RATE else None
        out.append(_fighter(pick, lvl, wep))
    _mark_wild_boss(out)
    return out


def simulate_battle(player, enemy, rng=None):
    rng = rng or random.Random()
    for pet in player:
        pet["side"] = "you"
        pet.setdefault("wp", 40 + int(pet.get("level") or 1) * 8)
        pet.setdefault("max_wp", pet["wp"])
        pet.setdefault("mag", max(4, int(pet.get("atk") or 8) // 3))
        pet.setdefault("pr", 16)
        pet.setdefault("mr", 16)
    for pet in enemy:
        pet["side"] = "foe"
        pet.setdefault("wp", 40 + int(pet.get("level") or 1) * 8)
        pet.setdefault("max_wp", pet["wp"])
        pet.setdefault("mag", max(4, int(pet.get("atk") or 8) // 3))
        pet.setdefault("pr", 16)
        pet.setdefault("mr", 16)
    from .aether_battle import play_turns
    return play_turns(player, enemy, rng)


def _streak_bonus(streak):
    # OwO battleUtil: largest multiple of 10/50/100/500/1000; Math.round; cap 100k.
    x = max(0, int(streak))
    if x <= 0:
        return 0
    if x % 1000 == 0:
        return min(100000, round(250 * (x ** 0.5) + 12500))
    if x % 500 == 0:
        return min(100000, round(100 * (x ** 0.5) + 5000))
    if x % 100 == 0:
        return min(100000, round(50 * (x ** 0.5) + 2500))
    if x % 50 == 0:
        return min(100000, round(30 * (x ** 0.5) + 1500))
    if x % 10 == 0:
        return min(100000, round(10 * (x ** 0.5) + 500))
    return 0


def _level_diff_xp(player, enemy):
    # OwO source: Math.round(600 * max(0, mean(enemy) - mean(player))); float avgs.
    if not player or not enemy:
        return 0
    yours = sum(int(p["level"]) for p in player) / len(player)
    theirs = sum(int(p["level"]) for p in enemy) / len(enemy)
    diff = max(0.0, theirs - yours)
    if diff <= 0:
        return 0
    return round(600 * diff)


def hunt(user_id, rng=None):
    rng = rng or random.Random()
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        wait = cooldown_left(row)
        if wait > 0:
            return {"ok": False, "error": f"Hunt is cooling down. Wait {int(wait + 0.99)}s."}
        pocket = ai_coins.get_balance(user_id)
        if pocket < HUNT_COST:
            return {"ok": False, "error": f"Hunt costs {ai_coins.coins(HUNT_COST)}. You have {ai_coins.coins(pocket)}."}
        ok, balance, err = ai_coins.resolve_wager(user_id, HUNT_COST, 0, min_bet=HUNT_COST, max_bet=HUNT_COST)
        if not ok:
            return {"ok": False, "error": err or "Could not spend Aether Coins."}
        # Peek actives first — durability spend needs final animal count (OwO role rules).
        used = gear.active_gems(pack)
        weights = dict(RARITY_WEIGHT)
        if "lucky" in used:
            weights = gear.lucky_weights(weights, used["lucky"])
        if "prism" in used:
            weights = gear.prism_weights(weights)
        need_weighted = "lucky" in used or "prism" in used
        extra = gear.extra_catches(used)
        animals = []
        for _i in range(1 + extra):
            if need_weighted:
                rarity = gear.roll_rarity(weights, rng)
                pool = [aid for aid, _n, _e, rar in ANIMALS if rar == rarity] or list(ANIMAL_BY_ID)
                aid = rng.choice(pool)
            else:
                aid = roll_animal(rng)
            _catch_one(row, aid)
            animals.append(aid)
        animal_id = animals[0]
        # Role-based durability after n is known (HUD [left/max] is post-spend).
        if used:
            gear.spend_gems(pack, used, len(animals))
        # OwO: sum of caught-rank XP; awarded to active team pets only (not the catch itself).
        xp_gain = sum(int(HUNT_XP.get(rarity_of(aid), 1)) for aid in animals)
        for mate in row["team"]:
            if mate:
                add_xp(row, mate, xp_gain)
        dropped = gear.maybe_lootbox(pack, rng)
        gems_hud = []
        # Stable HUD order: GEM_KINDS order, only gems that were used this hunt.
        for kind, _label, emoji, _desc in gear.GEM_KINDS:
            if kind not in used:
                continue
            rar = used[kind]
            active = (pack.get("active") or {}).get(kind) or {}
            left = int(active.get("left") or 0)
            mx = int(gear.GEM_HUNTS.get(rar) or left or 1)
            gems_hud.append({"kind": kind, "emoji": emoji, "left": left, "max": mx, "rarity": rar})
        row["last_hunt"] = time.time()
        ticket_awards = []
        hunt_aw = gear.note_hunt_and_maybe_ticket(pack)
        if hunt_aw:
            ticket_awards.append(hunt_aw)
        for aw in gear.maybe_checklist_tier_ticket(
            pack, row.get("caught") or {}, ANIMALS, base.RARITY_ORDER
        ):
            ticket_awards.append(aw)
        _save_store(store)
        return {
            "ok": True,
            "animal_id": animal_id,
            "animals": animals,
            "count": owned_count(row, animal_id),
            "balance": balance,
            "new": owned_count(row, animal_id) == 1,
            "lootbox": dropped,
            "lootbox_count": int(pack.get("lb_today") or 0) if dropped else 0,
            "xp_gain": xp_gain,
            "gems_hud": gems_hud,
            "ticket_awards": ticket_awards,
            "hunt_streak": int(pack.get("hunt_streak") or 0),
        }


def snapshot(user_id):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        _save_store(store)
        nicks = row.get("nicks") if isinstance(row.get("nicks"), dict) else {}
        return {"zoo": dict(row["zoo"]), "caught": dict(row.get("caught") or {}), "team": list(row["team"]), "xp": dict(row["xp"]), "last_hunt": float(row["last_hunt"]), "cooldown": cooldown_left(row), "points": zoo_points_for(row.get("caught") or {}), "gear": pack, "streak": int(pack.get("streak") or 0), "best_streak": int(pack.get("best_streak") or 0), "essence": essence_of(row), "nicks": dict(nicks)}


def battle(user_id, rng=None):
    rng = rng or random.Random()
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        team_ids = active_team(row)
        if len(team_ids) < TEAM_SIZE:
            return {"ok": False, "error": f"Battle is 3v3. Fill all {TEAM_SIZE} team slots with /team first."}
        player = [_fighter(aid, level_of(xp_of(row, aid)), gear.equipped_weapon(pack, aid)) for aid in team_ids]
        enemy = build_enemy_team(player, rng)
        outcome = simulate_battle(player, enemy, rng)
        result = outcome["result"]
        prev_streak = int(pack.get("streak") or 0)
        if result == "win":
            pack["streak"] = prev_streak + 1
        else:
            pack["streak"] = 0
        pack["best_streak"] = max(int(pack.get("best_streak") or 0), int(pack.get("streak") or 0))
        xp_base = BATTLE_XP[result]
        xp_bonus = 0
        if result == "win":
            xp_bonus = _streak_bonus(pack["streak"]) + _level_diff_xp(player, enemy)
        xp_gain = xp_base + xp_bonus
        highest = max(level_of(xp_of(row, aid)) for aid in team_ids)
        by_aid = {p["id"]: p for p in player}
        for aid in team_ids:
            extra = xp_gain
            gap = highest - level_of(xp_of(row, aid))
            if gap > 0:
                extra = int(extra * min(10.0, 2 + 0.1 * gap))
            # Field Tutor / Codex Tutor: bearer XP bump (meta hook).
            pet = by_aid.get(aid) or {}
            xp_pct = float(pet.get("xp_bonus_pct") or 0)
            if not xp_pct:
                xp_pct = float((pet.get("passive_hooks") or {}).get("xp_bonus_pct") or 0)
            if xp_pct:
                extra = int(round(extra * (1.0 + xp_pct / 100.0)))
            add_xp(row, aid, extra)
        payout = 0
        balance = ai_coins.get_balance(user_id)
        # OwO: crate chance on any finished battle (win/lose/tie), not win-only
        crate = gear.maybe_crate(pack, True, rng)
        ticket_awards = []
        if result == "win":
            awarded = gear.maybe_battle_win_ticket(pack)
            if awarded:
                ticket_awards.append(awarded)
        _save_store(store)
        return {"ok": True, "result": result, "log": outcome["log"], "rounds": outcome["rounds"], "player": outcome["player"], "enemy": outcome["enemy"], "frames": outcome.get("frames") or [], "xp_gain": xp_gain, "xp_base": xp_base, "xp_bonus": xp_bonus, "payout": payout, "balance": balance, "streak": int(pack.get("streak") or 0), "prev_streak": prev_streak, "best_streak": int(pack.get("best_streak") or 0), "crate": crate, "crate_today": int(pack.get("crate_today") or 0), "ticket_awards": ticket_awards}



def team_lines(team, xp, zoo, pack=None):
    """OwO-feel party card: slot header, Lvl [cur/need], H/P/p · W/M/m, weapon row.

    Maps honestly to existing fighter stats (no new combat math).
    H=HP, P=ATK, p=PR, W=WP, M=MAG, m=MR — same formulas as `_fighter`.
    Blank line between slots; spaced H/P/p · W/M/m; equipped weapon prefixed;
    empty gear stays a soft · no weapon (Owned catalog lives on /zoo).
    """
    lines = []
    for i in range(TEAM_SIZE):
        if i > 0:
            lines.append("")
        aid = team[i] if i < len(team) else None
        if not aid:
            lines.append(f"**[{i + 1}]** empty")
            continue
        total_xp = int(xp.get(aid) or 0)
        lvl, into, need = xp_progress(total_xp)
        # Mirror `_fighter` including rarity pool mult + flat passive % (display).
        snap = _fighter(aid, lvl, gear.equipped_weapon(pack, aid) if pack else None)
        base_hp = int(snap["max_hp"])
        atk = int(snap["atk"])
        mag = int(snap["mag"])
        wp = int(snap["max_wp"])
        pr = int(snap["pr"])
        mr = int(snap["mr"])
        held = snap.get("weapon") if isinstance(snap.get("weapon"), dict) else None
        xp_bit = f"{into}/{need}" if need else f"{into}/—"
        from .hunt_emoji import stat_mark, weapon_row_prefix

        lines.append(f"**[{i + 1}]** {animal_label(aid)}")
        lines.append(f"Lvl {lvl} [{xp_bit}]")
        lines.append(f"{stat_mark('hp')} H {base_hp}  ·  {stat_mark('wp')} W {wp}")
        lines.append(f"{stat_mark('atk')} P {atk}  ·  {stat_mark('mag')} M {mag}")
        lines.append(f"{stat_mark('pr')} p {pr}  ·  {stat_mark('mr')} m {mr}")
        if held:
            lines.append(f"{weapon_row_prefix()} {gear.weapon_line(held)}")
        else:
            lines.append("· no weapon")
    return lines


def _roster_line(pet):
    """Compact OwO-class team line with HP/WP readouts."""
    wep = pet.get("weapon") if isinstance(pet.get("weapon"), dict) else None
    gear_txt = gear.weapon_line(wep) if wep else "*no weapon*"
    emoji = pet.get("emoji") or ""
    name = pet.get("name") or animal_label(pet["id"])
    hp = max(0, int(pet.get("hp") or 0))
    wp = max(0, int(pet.get("wp") or 0))
    mark = rarity_mark(pet.get("rarity") or rarity_of(pet["id"]))
    return (
        f"L. {pet.get('level', 1)} {emoji} {name} {mark}\n"
        f"`{hp} HP` `{wp} WP` · {gear_txt}"
    )


def _hp_bar(pet):
    hp = max(0, int(pet.get("hp") or 0))
    mx = max(1, int(pet.get("max_hp") or 1))
    wp = max(0, int(pet.get("wp") or 0))
    wpx = max(1, int(pet.get("max_wp") or pet.get("wp") or 1))
    filled = round(10 * hp / mx)
    bar = "\u2588" * filled + "\u2591" * (10 - filled)
    return f"{bar} `{hp}/{mx} HP` `{wp}/{wpx} WP`"


def battle_card(display_name, result):
    you = result.get("player") or []
    foe = result.get("enemy") or []
    log = result.get("log") or []
    rounds = max(1, int(result.get("rounds") or 1))
    lines = [f"{display_name} goes into battle!", f"**{display_name}'s Team**"]
    lines.extend(_roster_line(p) for p in you)
    lines.append("**Enemy Team**")
    lines.extend(_roster_line(p) for p in foe)
    lines.append("")
    for p in you:
        lines.append(f"{animal_label(p['id'])} {_hp_bar(p)}")
    lines.append("")
    for p in foe:
        lines.append(f"{animal_label(p['id'])} {_hp_bar(p)}")
    if log:
        lines.append("")
        lines.extend(log[-6:])
    lines.append(f"Turn {rounds}")
    from .aether_battle import result_caption
    lines.append(result_caption(result))
    return "\n".join(lines)


def open_lootbox(user_id):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        out = gear.open_lootbox(gear.ensure_gear(row))
        _save_store(store)
        return out


def open_crate(user_id):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        out = gear.open_crate(gear.ensure_gear(row))
        _save_store(store)
        return out


def use_gem(user_id, kind, rarity=None):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        out = gear.use_gem(gear.ensure_gear(row), kind, rarity)
        _save_store(store)
        return out


def equip_weapon(user_id, query, animal_query):
    animal_id = resolve_animal(animal_query)
    if animal_id is None:
        return {"ok": False, "error": "I do not know that animal. Check /zoo."}
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        wid = gear.resolve_weapon(pack, query)
        if not wid:
            return {"ok": False, "error": "No matching weapon. Use the id from /inv."}
        out = gear.equip_weapon(pack, wid, animal_id)
        if out.get("ok"):
            out["animal_id"] = animal_id
            out["label"] = gear.weapon_line(gear.equipped_weapon(pack, animal_id))
        _save_store(store)
        return out



RENAME_FEE = 50
NICK_MAX = 24
ESSENCE_BY_RARITY = dict(base.RARITY_SELL)


def essence_of(row):
    try:
        return max(0, int(row.get("essence") or 0))
    except (TypeError, ValueError):
        return 0


def nick_of(row, animal_id):
    nicks = row.get("nicks")
    if not isinstance(nicks, dict):
        return None
    raw = nicks.get(animal_id)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def nick_label(animal_id, row=None):
    label = animal_label(animal_id)
    if row is None:
        return label
    nick = nick_of(row, animal_id)
    return f'{label} "{nick}"' if nick else label


def weapon_board(display_name, pack, row=None):
    """Zoo-style armory: rarity headers, dense id · mark · emoji · name · quality% · holder."""
    lines = [
        f"\u2694\ufe0f **{display_name}'s weapons** \u2694\ufe0f",
        "Board `/weapons` · Detail `/weapon id:` · Equip `/equip` · Salvage `/salvage`",
        "",
    ]
    weapons = (pack or {}).get("weapons") or {}
    equip = (pack or {}).get("equip") or {}
    by_wid = {str(held): aid for aid, held in equip.items() if held}
    if not weapons:
        lines.append("No weapons yet. Win a battle for a crate, then `/crate`.")
        return "\n".join(lines)

    grouped: dict[str, list[tuple[str, dict, tuple]]] = {r: [] for r in base.RARITY_ORDER}
    orphan: list[tuple[str, dict, tuple]] = []
    for wid, raw in weapons.items():
        if not isinstance(raw, dict):
            continue
        meta = gear.WEAPON_BY_ID.get(raw.get("kind"))
        if not meta:
            continue
        rar = raw.get("rarity") or COMMON
        if rar in grouped:
            grouped[rar].append((str(wid), raw, meta))
        else:
            orphan.append((str(wid), raw, meta))

    def _wid_key(item: tuple[str, dict, tuple]):
        wid = item[0]
        return (0, int(wid)) if wid.isdigit() else (1, wid)

    def _holder_label(wid: str) -> str | None:
        holder = by_wid.get(str(wid))
        if not holder:
            return None
        animal = ANIMAL_BY_ID.get(holder)
        if row is not None:
            return nick_label(holder, row)
        if animal:
            return f"{animal[2]} {animal[1]}".strip()
        return holder

    shown = False
    for rarity in base.RARITY_ORDER:
        items = grouped.get(rarity) or []
        if not items:
            continue
        if shown:
            lines.append("")
        shown = True
        mark = rarity_mark(rarity)
        lines.append(f"**{mark} {RARITY_LABEL.get(rarity, rarity)}**")
        for wid, raw, meta in sorted(items, key=_wid_key):
            q = int(raw.get("quality") or 0)
            line = f"`{wid}` {mark} {meta[2]} **{meta[1]}** `{q}%`"
            held = _holder_label(wid)
            if held:
                line = f"{line} · {held}"
            lines.append(line)
    if orphan:
        if shown:
            lines.append("")
        lines.append("**Other**")
        for wid, raw, meta in sorted(orphan, key=_wid_key):
            rar = raw.get("rarity") or COMMON
            mark = rarity_mark(rar)
            q = int(raw.get("quality") or 0)
            line = f"`{wid}` {mark} {meta[2]} **{meta[1]}** `{q}%`"
            held = _holder_label(wid)
            if held:
                line = f"{line} · {held}"
            lines.append(line)
    return "\n".join(lines)


def weapon_detail(user_id, query, display_name="Hunter"):
    """OwO-feel `/weapon {id}` detail card from existing style/ATK/WP data."""
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        wid = gear.resolve_weapon(pack, query)
        if not wid:
            return {"ok": False, "error": "No matching weapon. Use the id from `/weapons`."}
        raw = (pack.get("weapons") or {}).get(str(wid))
        if not isinstance(raw, dict):
            return {"ok": False, "error": "That weapon entry is broken."}
        meta = gear.WEAPON_BY_ID.get(raw.get("kind"))
        if not meta:
            return {"ok": False, "error": "That weapon entry is broken."}
        wep = {
            "wid": str(wid),
            "kind": raw.get("kind"),
            "name": meta[1],
            "emoji": meta[2],
            "style": raw.get("style") or meta[3],
            "rarity": raw.get("rarity") or COMMON,
            "quality": int(raw.get("quality") or 50),
            "atk": int(raw.get("atk") or 0),
        }
        holder_label = None
        for animal_id, held in (pack.get("equip") or {}).items():
            if str(held) == str(wid):
                # nick_label / animal_label already include the species emoji
                holder_label = nick_label(animal_id, row)
                break
        body = gear.weapon_detail_text(
            wep, display_name=display_name, holder_label=holder_label
        )
        return {
            "ok": True,
            "wid": str(wid),
            "kind": wep["kind"],
            "name": wep["name"],
            "emoji": wep["emoji"],
            "rarity": wep["rarity"],
            "body": body,
            "wep": wep,
        }


def sacrifice(user_id, query, count=1):
    animal_id = resolve_animal(query)
    if animal_id is None:
        return {"ok": False, "error": "I do not know that animal. Check /zoo."}
    try:
        count = int(count)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Count has to be a whole number."}
    if count < 1:
        return {"ok": False, "error": "Sacrifice at least one."}
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        have = owned_count(row, animal_id)
        on_team = animal_id in row["team"]
        keep = 1 if on_team else 0
        if have - count < keep:
            if on_team:
                return {"ok": False, "error": f"{animal_label(animal_id)} is on your team. Keep at least one, or take it off the team first."}
            if have <= 0:
                return {"ok": False, "error": f"You do not have a {animal_label(animal_id)}."}
            return {"ok": False, "error": f"You only have {have}."}
        gain = int(ESSENCE_BY_RARITY.get(rarity_of(animal_id), 10)) * count
        row["zoo"][animal_id] = have - count
        if row["zoo"][animal_id] <= 0:
            del row["zoo"][animal_id]
        total = essence_of(row) + gain
        row["essence"] = total
        _save_store(store)
        return {
            "ok": True,
            "animal_id": animal_id,
            "sacrificed": count,
            "gained": gain,
            "essence": total,
            "left": owned_count(row, animal_id),
        }


def rename_animal(user_id, query, nickname=None):
    animal_id = resolve_animal(query)
    if animal_id is None:
        return {"ok": False, "error": "I do not know that animal. Check /zoo."}
    nick = " ".join(str(nickname or "").strip().split())
    if len(nick) > NICK_MAX:
        return {"ok": False, "error": f"Nicknames stay under {NICK_MAX} characters."}
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        if owned_count(row, animal_id) < 1:
            return {"ok": False, "error": f"You do not have a {animal_label(animal_id)} yet. Hunt first."}
        nicks = row.get("nicks")
        if not isinstance(nicks, dict):
            nicks = {}
            row["nicks"] = nicks
        if not nick:
            nicks.pop(animal_id, None)
            if not nicks:
                row.pop("nicks", None)
            _save_store(store)
            return {"ok": True, "animal_id": animal_id, "nickname": None, "cleared": True, "fee": 0, "balance": ai_coins.get_balance(user_id)}
        pocket = ai_coins.get_balance(user_id)
        if pocket < RENAME_FEE:
            return {"ok": False, "error": f"Renaming costs {ai_coins.coins(RENAME_FEE)}. You have {ai_coins.coins(pocket)}."}
        ok, balance, err = ai_coins.resolve_wager(
            user_id, RENAME_FEE, 0, min_bet=RENAME_FEE, max_bet=RENAME_FEE
        )
        if not ok:
            return {"ok": False, "error": err or "Could not spend Aether Coins."}
        nicks[animal_id] = nick
        _save_store(store)
        return {"ok": True, "animal_id": animal_id, "nickname": nick, "cleared": False, "fee": RENAME_FEE, "balance": balance}


def checklist_board(display_name, caught):
    lines = [
        f"**{display_name}'s field guide**",
        "Species you have discovered versus those still missing from the wilds.",
    ]
    total_found = 0
    for rarity in base.RARITY_ORDER:
        pool = [row for row in ANIMALS if row[3] == rarity]
        found = []
        missing = []
        for aid, name, emoji, _rar in pool:
            try:
                ever = int((caught or {}).get(aid) or 0)
            except (TypeError, ValueError):
                ever = 0
            if ever > 0:
                found.append(f"{emoji} {name}")
                total_found += 1
            else:
                missing.append(f"{emoji} {name}")
        mark = rarity_mark(rarity)
        lines.append(f"\n{mark} **{RARITY_LABEL[rarity]}** · {len(found)}/{len(pool)}")
        lines.append("Found · " + (", ".join(found) if found else "none yet"))
        lines.append("Missing · " + (", ".join(missing) if missing else "none — tier complete"))
    lines.append(f"\n**Discovered __{total_found}__ / {len(ANIMALS)}**")
    return "\n".join(lines)



LORE_BY_RARITY = {
    COMMON: "A familiar presence in the peat and fog — easy to overlook, hard to forget once named.",
    UNCOMMON: "Sharper senses and stubborn will. Hunters trade stories about this one around campfires.",
    RARE: "Rift-touched and wary. Meeting one is luck; keeping one is skill.",
    EPIC: "A legend half-written. The aether bends around its stride.",
    MYTHIC: "Older than the maps. Catching sight of it rewrites what you thought the wilds could hold.",
    ASTRAL: "Drawn from omen-sky and constellation. It arrives like a quiet prophecy.",
    PRIMORDIAL: "First-world flesh. The peat remembers its footprint from before names existed.",
}


def bestiary_card(display_name, animal_id, row=None, pack=None):
    meta = ANIMAL_BY_ID.get(animal_id)
    if not meta:
        return None
    _aid, name, emoji, rarity = meta
    row = row or {}
    owned = owned_count(row, animal_id)
    try:
        discovered = int((row.get("caught") or {}).get(animal_id) or 0)
    except (TypeError, ValueError):
        discovered = 0
    lvl = level_of(xp_of(row, animal_id)) if owned or discovered else 1
    hp, atk = stats_for(animal_id, lvl)
    mark = rarity_mark(rarity)
    label = RARITY_LABEL.get(rarity, rarity)
    nick = nick_of(row, animal_id) if row else None
    title = f'{emoji} {name}' + (f' "{nick}"' if nick else "")
    lines = [
        f"**{display_name}'s bestiary**",
        f"**{title}** · {mark} {label}",
        f"Lv {lvl} · {hp} HP / {atk} ATK",
        f"Owned **{owned}** · discovered **{discovered}**",
    ]
    if pack:
        held = gear.equipped_weapon(pack, animal_id)
        if held:
            lines.append(f"Armed with {gear.weapon_line(held)}")
    lines.append("")
    lines.append(LORE_BY_RARITY.get(rarity, LORE_BY_RARITY[COMMON]))
    sell = int(base.RARITY_SELL.get(rarity, 10))
    essence = int(ESSENCE_BY_RARITY.get(rarity, sell))
    lines.append(f"Sell **{sell}** \u2726 · sacrifice **{essence}** Essence each")
    return "\n".join(lines)


def bestiary(user_id, query, display_name="Hunter"):
    animal_id = resolve_animal(query)
    if animal_id is None:
        return {"ok": False, "error": "I do not know that animal. Check /zoo or /checklist."}
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        try:
            discovered = int((row.get("caught") or {}).get(animal_id) or 0)
        except (TypeError, ValueError):
            discovered = 0
        if discovered < 1 and owned_count(row, animal_id) < 1:
            return {
                "ok": False,
                "error": f"You have not discovered {animal_label(animal_id)} yet. Hunt first.",
            }
        body = bestiary_card(display_name, animal_id, row, pack)
        return {
            "ok": True,
            "animal_id": animal_id,
            "body": body,
            "rarity": rarity_of(animal_id),
        }


def salvage(user_id, query):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        wid = gear.resolve_weapon(pack, query)
        if not wid:
            return {"ok": False, "error": "No matching weapon. Use the id from /inv or /weapon."}
        out = gear.salvage_weapon(pack, wid)
        if out.get("ok"):
            _save_store(store)
        return out



# --- Raid tiers (owo-research/RAID_BOSS_TIERS.md CoS V1) ---
RAID_TIERS = {
    "easy": {
        "key": "easy",
        "label": "Easy",
        "rift": "Ember Rift",
        "cost": 1,
        "hp_mult": 1.85,
        "hp_flat": 40,
        "atk_mult": 1.45,
        "atk_flat": 8,
        "wp_bonus": 30,
        "boss_lvl": (3, 5),
        "boss_lvl_floor": 5,
        "escort_lvl": (2, 4),
        "escort_arm": 0.85,
        "escort_pool": "epic_mythic",
        "escort_epic_plus": False,
        "ignore_softcap": False,
        "wep_quality": (85, 95),
        "wep_atk_bonus": 6,
        "xp_bonus": 100,
        "shards_win": 8,
        "shards_lose": 0,
        "shards_draw": 2,
        "crate_mode": "maybe",  # normal maybe_crate with daily cap
        "crate_extra_p": 0.0,
        "empowered": None,  # None | "roll" | "guaranteed"
        "empowered_p": 0.0,
        "gem": "easy",
        "bonus_ticket_p": 0.0,
    },
    "hard": {
        "key": "hard",
        "label": "Hard",
        "rift": "Void Rift",
        "cost": 2,
        "hp_mult": 2.25,
        "hp_flat": 55,
        "atk_mult": 1.70,
        "atk_flat": 12,
        "wp_bonus": 45,
        "boss_lvl": (5, 8),
        "boss_lvl_floor": 8,
        "escort_lvl": (3, 6),
        "escort_arm": 1.0,
        "escort_pool": "epic_mythic",
        "escort_epic_plus": False,
        "ignore_softcap": False,
        "wep_quality": (90, 98),
        "wep_atk_bonus": 10,
        "xp_bonus": 200,
        "shards_win": 22,
        "shards_lose": 3,
        "shards_draw": 6,
        "crate_mode": "guaranteed",
        "crate_extra_p": 0.0,
        "empowered": "roll",
        "empowered_p": 0.10,
        "gem": "hard",
        "bonus_ticket_p": 0.05,
    },
    "nightmare": {
        "key": "nightmare",
        "label": "Nightmare",
        "rift": "Crown Rift",
        "cost": 3,
        "hp_mult": 2.75,
        "hp_flat": 80,
        "atk_mult": 1.95,
        "atk_flat": 16,
        "wp_bonus": 60,
        "boss_lvl": (7, 10),
        "boss_lvl_floor": 12,
        "escort_lvl": (5, 8),
        "escort_arm": 1.0,
        "escort_pool": "mythic",
        "escort_epic_plus": True,
        "ignore_softcap": True,
        "wep_quality": (95, 100),
        "wep_atk_bonus": 14,
        "xp_bonus": 350,
        "shards_win": 45,
        "shards_lose": 6,
        "shards_draw": 10,
        "crate_mode": "guaranteed",
        "crate_extra_p": 0.40,
        "empowered": "guaranteed",
        "empowered_p": 1.0,
        "gem": "nightmare",
        "bonus_ticket_p": 0.12,
    },
}

_EMPOWERED_WEIGHT = {RARE: 40, EPIC: 45, MYTHIC: 15}
_EMPOWERED_HARD_MIN = EPIC  # Hard 10% epic+


def resolve_raid_tier(tier: str | None) -> dict:
    key = str(tier or "easy").strip().lower()
    aliases = {
        "easy": "easy",
        "ember": "easy",
        "ember_rift": "easy",
        "hard": "hard",
        "void": "hard",
        "void_rift": "hard",
        "nightmare": "nightmare",
        "nm": "nightmare",
        "crown": "nightmare",
        "crown_rift": "nightmare",
    }
    resolved = aliases.get(key, key)
    if resolved not in RAID_TIERS:
        return RAID_TIERS["easy"]
    return RAID_TIERS[resolved]


def _clamp_lvl(lo: int, hi: int, floor: int) -> tuple[int, int]:
    return max(floor, lo), min(LEVEL_CAP, hi)


def _raid_boss_weapon(tier: dict, rng: random.Random) -> dict:
    kind, name, emoji, style = rng.choice(gear.WEAPONS)
    rarity = MYTHIC
    lo, hi = gear.WEAPON_ATK[rarity]
    q_lo, q_hi = tier["wep_quality"]
    quality = rng.randint(int(q_lo), int(q_hi))
    atk = rng.randint(lo, hi) + int(tier["wep_atk_bonus"])
    return {
        "kind": kind,
        "name": name,
        "emoji": emoji,
        "style": style,
        "rarity": rarity,
        "quality": quality,
        "atk": atk,
    }


def _raid_escort_weapon(player, tier: dict, rng: random.Random) -> dict | None:
    if rng.random() >= float(tier["escort_arm"]):
        return None
    if tier.get("ignore_softcap") or tier.get("escort_epic_plus"):
        kind, name, emoji, style = rng.choice(gear.WEAPONS)
        # Nightmare escorts: epic+ only; ignore soft-cap
        weights = {EPIC: 70, MYTHIC: 30} if tier.get("escort_epic_plus") else {
            COMMON: 0, UNCOMMON: 0, RARE: 20, EPIC: 50, MYTHIC: 30,
        }
        weights = {k: v for k, v in weights.items() if v > 0}
        rarity = gear.roll_rarity(weights, rng)
        lo, hi = gear.WEAPON_ATK[rarity]
        quality = rng.randint(40, 90)
        return {
            "kind": kind, "name": name, "emoji": emoji, "style": style,
            "rarity": rarity, "quality": quality, "atk": rng.randint(lo, hi),
        }
    return _roll_enemy_weapon(player, rng)


def build_raid_boss(player, rng, tier="easy"):
    """Tiered mythic boss + escorts — CoS RAID_BOSS_TIERS.md."""
    spec = resolve_raid_tier(tier)
    avg = sum(int(pet.get("level") or 1) for pet in player) / max(1, len(player))
    a = int(round(avg))
    b_lo, b_hi = spec["boss_lvl"]
    floor = int(spec["boss_lvl_floor"])
    lvl_lo, lvl_hi = _clamp_lvl(a + b_lo, a + b_hi, floor)
    if lvl_lo > lvl_hi:
        lvl_lo = lvl_hi
    boss_lvl = rng.randint(lvl_lo, lvl_hi)

    mythics = [aid for aid, _n, _e, rar in ANIMALS if rar == MYTHIC] or [aid for aid, *_ in ANIMALS]
    epics = [aid for aid, _n, _e, rar in ANIMALS if rar == EPIC] or mythics
    boss_id = rng.choice(mythics)
    boss_wep = _raid_boss_weapon(spec, rng)
    boss = _fighter(boss_id, boss_lvl, boss_wep)
    boss["max_hp"] = int(boss["max_hp"] * float(spec["hp_mult"])) + int(spec["hp_flat"])
    boss["hp"] = boss["max_hp"]
    boss["atk"] = int(boss["atk"] * float(spec["atk_mult"])) + int(spec["atk_flat"])
    boss["mag"] = int(boss.get("mag") or boss["atk"]) + int(spec["atk_flat"])
    boss["wp"] = int(boss.get("wp") or 40) + int(spec["wp_bonus"])
    boss["max_wp"] = boss["wp"]
    boss["raid_boss"] = True

    out = [boss]
    used = {boss_id}
    if spec["escort_pool"] == "mythic":
        pool = [aid for aid in mythics if aid not in used]
    else:
        pool = [aid for aid in (epics + mythics) if aid not in used]
    rng.shuffle(pool)
    e_lo, e_hi = spec["escort_lvl"]
    for aid in pool[:2]:
        used.add(aid)
        el_lo, el_hi = _clamp_lvl(a + e_lo, a + e_hi, 3)
        if el_lo > el_hi:
            el_lo = el_hi
        lvl = rng.randint(el_lo, el_hi)
        escort_wep = _raid_escort_weapon(player, spec, rng)
        out.append(_fighter(aid, lvl, escort_wep))
    return out


def _grant_empowered_weapon(pack, rng, *, hard_epic_plus: bool = False):
    kind, name, emoji, style = rng.choice(gear.WEAPONS)
    if hard_epic_plus:
        weights = {EPIC: 70, MYTHIC: 30}
    else:
        weights = dict(_EMPOWERED_WEIGHT)
    rarity = gear.roll_rarity(weights, rng)
    lo, hi = gear.WEAPON_ATK[rarity]
    quality = rng.randint(70, 100)
    atk = lo + int((hi - lo) * quality / 100)
    wid = str(int(pack.get("next_wid") or 1))
    pack["next_wid"] = int(wid) + 1
    pack.setdefault("weapons", {})[wid] = {
        "kind": kind, "rarity": rarity, "quality": quality, "atk": atk, "style": style,
    }
    return {
        "wid": wid, "kind": kind, "name": name, "emoji": emoji,
        "rarity": rarity, "quality": quality, "atk": atk, "style": style,
    }


def _roll_raid_gem(spec: dict, rng: random.Random) -> tuple[str, str] | None:
    mode = spec.get("gem")
    if mode == "easy":
        if rng.random() >= 0.08:
            return None
        kind = rng.choice(["hunting", "lucky", "empower"])
        rarity = gear.roll_rarity(gear.GEM_WEIGHT, rng)
        return kind, rarity
    if mode == "hard":
        if rng.random() >= 0.20:
            return None
        kind = rng.choice(["lucky", "prism"])
        rarity = gear.roll_rarity(gear.GEM_WEIGHT, rng)
        return kind, rarity
    if mode == "nightmare":
        if rng.random() < 0.40:
            rarity = gear.roll_rarity(gear.GEM_WEIGHT, rng)
            return "prism", rarity
        if rng.random() < 0.25:
            kind = rng.choice(["lucky", "empower"])
            rarity = gear.roll_rarity(gear.GEM_WEIGHT, rng)
            return kind, rarity
        return None
    return None


def _apply_raid_rewards(pack, result: str, spec: dict, rng: random.Random) -> dict:
    """Win / lose / draw loot per RAID_BOSS_TIERS.md. Mutates pack."""
    notes: list[str] = []
    shard_bonus = 0
    crate = False
    crate_extra = False
    empowered = None
    gem = None
    bonus_ticket = False

    if result == "win":
        shard_bonus = int(spec["shards_win"])
        pack["shards"] = int(pack.get("shards") or 0) + shard_bonus
        notes.append(f"+{shard_bonus} shards")
        mode = spec["crate_mode"]
        if mode == "maybe":
            crate = gear.maybe_crate(pack, True, rng)
            if crate:
                notes.append("crate!")
        else:
            crate = gear.grant_raid_clear_crate(pack)
            notes.append("crate!")
            if float(spec.get("crate_extra_p") or 0) and rng.random() < float(spec["crate_extra_p"]):
                gear.grant_raid_clear_crate(pack)
                crate_extra = True
                notes.append("second crate!")
        emp = spec.get("empowered")
        if emp == "guaranteed" or (emp == "roll" and rng.random() < float(spec.get("empowered_p") or 0)):
            empowered = _grant_empowered_weapon(
                pack, rng, hard_epic_plus=(spec["key"] == "hard")
            )
            notes.append(f"empowered {empowered['emoji']} {empowered['name']}!")
        rolled = _roll_raid_gem(spec, rng)
        if rolled:
            kind, rarity = rolled
            gem = gear.grant_gem_kind(pack, kind, rarity)
            if gem.get("ok"):
                notes.append(f"{gem['emoji']} {gear.RARITY_LABEL.get(rarity, rarity)} {gem['label']}!")
        if float(spec.get("bonus_ticket_p") or 0) and rng.random() < float(spec["bonus_ticket_p"]):
            gear.add_raid_tickets(pack, 1)
            bonus_ticket = True
            notes.append("rift ticket returned!")
    elif result == "lose":
        shard_bonus = int(spec["shards_lose"])
        if shard_bonus:
            pack["shards"] = int(pack.get("shards") or 0) + shard_bonus
            notes.append(f"+{shard_bonus} shards")
    else:  # draw
        shard_bonus = int(spec["shards_draw"])
        if shard_bonus:
            pack["shards"] = int(pack.get("shards") or 0) + shard_bonus
            notes.append(f"+{shard_bonus} shards")

    return {
        "shard_bonus": shard_bonus,
        "crate": crate,
        "crate_extra": crate_extra,
        "empowered": empowered,
        "gem": gem,
        "bonus_ticket": bonus_ticket,
        "reward_notes": notes,
    }


def raid(user_id, tier="easy", rng=None):
    """Spend tier ticket cost, then simulate. Spend happens before sim."""
    if isinstance(tier, random.Random):
        # Back-compat: raid(user_id, rng)
        rng = tier
        tier = "easy"
    rng = rng or random.Random()
    spec = resolve_raid_tier(tier)
    cost = int(spec["cost"])
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        tickets = int(pack.get("raid_ticket") or 0)
        if tickets < cost:
            need = cost
            return {
                "ok": False,
                "error": (
                    f"Need {need} ticket{'s' if need != 1 else ''} for {spec['label']} "
                    f"· you have {tickets} · /daily, battle, hunt streak, checklist, or 30 shards"
                ),
            }
        team_ids = active_team(row)
        if len(team_ids) < TEAM_SIZE:
            return {"ok": False, "error": f"Raid is 3v3. Fill all {TEAM_SIZE} team slots with /team first."}
        pack["raid_ticket"] = tickets - cost
        player = [
            _fighter(aid, level_of(xp_of(row, aid)), gear.equipped_weapon(pack, aid))
            for aid in team_ids
        ]
        enemy = build_raid_boss(player, rng, spec["key"])
        outcome = simulate_battle(player, enemy, rng)
        result = outcome["result"]
        prev_streak = int(pack.get("streak") or 0)
        if result == "win":
            pack["streak"] = prev_streak + 1
        else:
            pack["streak"] = 0
        pack["best_streak"] = max(int(pack.get("best_streak") or 0), int(pack.get("streak") or 0))
        xp_base = BATTLE_XP[result]
        xp_bonus = 0
        if result == "win":
            xp_base = xp_base + int(spec["xp_bonus"])
            xp_bonus = _streak_bonus(pack["streak"]) + _level_diff_xp(player, enemy)
        xp_gain = xp_base + xp_bonus
        highest = max(level_of(xp_of(row, aid)) for aid in team_ids)
        for aid in team_ids:
            extra = xp_gain
            gap = highest - level_of(xp_of(row, aid))
            if gap > 0:
                extra = int(extra * min(10.0, 2 + 0.1 * gap))
            add_xp(row, aid, extra)
        loot = _apply_raid_rewards(pack, result, spec, rng)
        _save_store(store)
        return {
            "ok": True,
            "result": result,
            "log": outcome["log"],
            "rounds": outcome["rounds"],
            "player": outcome["player"],
            "enemy": outcome["enemy"],
            "frames": outcome.get("frames") or [],
            "xp_gain": xp_gain,
            "xp_base": xp_base,
            "xp_bonus": xp_bonus,
            "payout": 0,
            "balance": ai_coins.get_balance(user_id),
            "streak": int(pack.get("streak") or 0),
            "prev_streak": prev_streak,
            "best_streak": int(pack.get("best_streak") or 0),
            "crate": loot["crate"],
            "crate_extra": loot["crate_extra"],
            "tickets_left": int(pack.get("raid_ticket") or 0),
            "tickets_spent": cost,
            "shard_bonus": loot["shard_bonus"],
            "empowered": loot["empowered"],
            "gem": loot["gem"],
            "bonus_ticket": loot["bonus_ticket"],
            "reward_notes": loot["reward_notes"],
            "boss": True,
            "tier": spec["key"],
            "tier_label": spec["label"],
            "rift": spec["rift"],
        }


def craft_raid_ticket(user_id):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        out = gear.craft_ticket_from_shards(pack)
        if out.get("ok"):
            _save_store(store)
        return out



def grant_daily_supplies(user_id):
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        out = gear.grant_daily_supplies(gear.ensure_gear(row))
        _save_store(store)
        return out


def grant_supplies(user_id, kind, amount=1):
    kind = str(kind or "").strip().lower()
    if kind in {"lootbox", "lootboxes", "box", "boxes"}:
        key, label = "lootbox", "lootbox"
    elif kind in {"crate", "crates", "weapon", "weapons"}:
        key, label = "crate", "weapon crate"
    else:
        return {"ok": False, "error": "Give a lootbox or a crate."}
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Amount has to be a whole number."}
    if amount < 1 or amount > 100:
        return {"ok": False, "error": "Give between 1 and 100."}
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        pack = gear.ensure_gear(row)
        pack[key] = int(pack.get(key) or 0) + amount
        _save_store(store)
        return {"ok": True, "kind": key, "label": label, "amount": amount, "left": int(pack[key])}


def install(mod=None):
    mod = mod or base
    mod.LEVEL_CAP = 50
    mod.WIP_FOOTER = WIP_FOOTER
    mod.HUNT_XP = HUNT_XP
    mod.BATTLE_XP = BATTLE_XP
    mod.xp_for_level = base.xp_for_level
    mod.level_of = base.level_of
    mod.xp_progress = base.xp_progress
    for name in (
        "_fighter", "build_enemy_team", "simulate_battle", "hunt", "snapshot",
        "battle", "team_lines", "battle_card",
        "open_lootbox", "open_crate", "use_gem", "equip_weapon",
        "grant_daily_supplies", "grant_supplies",
        "essence_of", "nick_of", "nick_label", "weapon_board", "weapon_detail",
        "sacrifice", "rename_animal", "checklist_board",
        "bestiary_card", "bestiary", "salvage", "build_raid_boss", "raid",
        "resolve_raid_tier", "craft_raid_ticket", "RAID_TIERS",
        "_roll_enemy_weapon", "_player_gear_caps", "_apply_weapon_passives", "_mark_wild_boss",
        "RENAME_FEE", "ESSENCE_BY_RARITY", "LORE_BY_RARITY",
    ):
        setattr(mod, name, globals()[name])


install()
