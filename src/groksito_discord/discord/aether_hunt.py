"""Aetherion Hunt WIP — original animals, zoo, team, and PvE battles.

Runtime save: data/aether_hunt.json. Play-money spends go through ai_coins.
Crates, huntbot, and public access are not in this slice.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from pathlib import Path
from typing import Any

from ..config import settings
from . import ai_coins

logger = logging.getLogger("aetherion.hunt")

HUNT_COST = 10
HUNT_COOLDOWN = 15
TEAM_SIZE = 3
LEVEL_CAP = 50
WIN_PAYOUT = 20
DRAW_PAYOUT = 10
EMBED_GOLD = 0xC9A227
EMBED_WIN = 0x3D9B64
EMBED_LOSE = 0xC45C4A
WIP_FOOTER = "WIP \u00b7 Test 1 \u00b7 Ori only \u00b7 crates later"

COMMON = "common"
UNCOMMON = "uncommon"
RARE = "rare"
EPIC = "epic"
MYTHIC = "mythic"
RARITY_ORDER = (COMMON, UNCOMMON, RARE, EPIC, MYTHIC)
RARITY_LABEL = {COMMON: "Common", UNCOMMON: "Uncommon", RARE: "Rare", EPIC: "Epic", MYTHIC: "Mythic"}
RARITY_WEIGHT = {COMMON: 550, UNCOMMON: 270, RARE: 120, EPIC: 45, MYTHIC: 15}
RARITY_SELL = {COMMON: 10, UNCOMMON: 20, RARE: 40, EPIC: 80, MYTHIC: 150}
# Source: owo-research/AETHERION_WEAPON_PASSIVES.md §3
RARITY_BASE = {COMMON: (40, 8), UNCOMMON: (52, 11), RARE: (72, 16), EPIC: (96, 22), MYTHIC: (128, 30)}
RARITY_PR = {COMMON: 6, UNCOMMON: 8, RARE: 11, EPIC: 15, MYTHIC: 20}
RARITY_MR = {COMMON: 6, UNCOMMON: 8, RARE: 11, EPIC: 15, MYTHIC: 20}
RARITY_WP_MAX = {COMMON: 40, UNCOMMON: 48, RARE: 58, EPIC: 72, MYTHIC: 90}
# Letter aliases stay c/u/r/e/m; marks resolve via hunt_ranks (emoji ID or unicode).
RARITY_LETTER = {
    COMMON: "c",
    UNCOMMON: "u",
    RARE: "r",
    EPIC: "e",
    MYTHIC: "m",
}
RARITY_EMBED = {
    COMMON: 0x9A4442,
    UNCOMMON: 0x388B9A,
    RARE: 0xD4A746,
    EPIC: 0x4057E1,
    MYTHIC: 0x9558EF,
}
RARITY_POINTS = {COMMON: 1, UNCOMMON: 5, RARE: 20, EPIC: 250, MYTHIC: 3000}
# OwO Manual Hunting / animal.json ranks (C–M). Team pets gain this on catch.
HUNT_XP = {COMMON: 1, UNCOMMON: 10, RARE: 20, EPIC: 400, MYTHIC: 1000}
# OwO battle base awards (ext may add streak / level-diff on win).
BATTLE_XP = {"win": 200, "draw": 100, "lose": 50}
ZOO_COLS = 5

ANIMALS: tuple[tuple[str, str, str, str], ...] = (
    ("dust_mite", "Dust Mite", "\U0001fab2", COMMON),
    ("ember_moth", "Ember Moth", "\U0001f98b", COMMON),
    ("pebble_toad", "Pebble Toad", "\U0001f438", COMMON),
    ("moss_pup", "Moss Pup", "\U0001f436", COMMON),
    ("drift_finch", "Drift Finch", "\U0001f426", COMMON),
    ("copper_beetle", "Copper Beetle", "\U0001f41e", COMMON),
    ("fog_hare", "Fog Hare", "\U0001f430", COMMON),
    ("river_skink", "River Skink", "\U0001f98e", COMMON),
    ("ash_mouse", "Ash Mouse", "\U0001f42d", COMMON),
    ("lantern_gnat", "Lantern Gnat", "\u2728", COMMON),
    ("glass_fox", "Glass Fox", "\U0001f98a", UNCOMMON),
    ("storm_lynx", "Storm Lynx", "\U0001f431", UNCOMMON),
    ("iron_ram", "Iron Ram", "\U0001f40f", UNCOMMON),
    ("tide_otter", "Tide Otter", "\U0001f9a6", UNCOMMON),
    ("ember_elk", "Ember Elk", "\U0001f98c", UNCOMMON),
    ("quartz_owl", "Quartz Owl", "\U0001f989", UNCOMMON),
    ("thorn_wolf", "Thorn Wolf", "\U0001f43a", UNCOMMON),
    ("cinder_boar", "Cinder Boar", "\U0001f417", UNCOMMON),
    ("aether_kite", "Aether Kite", "\U0001f985", UNCOMMON),
    ("void_ferret", "Void Ferret", "\U0001f9ad", UNCOMMON),
    ("void_heron", "Void Heron", "\U0001f426\u200d\u2b1b", RARE),
    ("aurora_stag", "Aurora Stag", "\U0001f98c", RARE),
    ("rift_serpent", "Rift Serpent", "\U0001f40d", RARE),
    ("moon_badger", "Moon Badger", "\U0001f9a1", RARE),
    ("star_hyena", "Star Hyena", "\U0001f9b4", RARE),
    ("ember_griffin", "Ember Griffin", "\U0001f985", RARE),
    ("moon_kraken", "Moon Kraken", "\U0001f991", RARE),
    ("glass_mantis", "Glass Mantis", "\U0001fab2", RARE),
    ("storm_basilisk", "Storm Basilisk", "\U0001f40d", RARE),
    ("tide_wraith", "Tide Wraith", "\U0001f47b", RARE),
    ("aether_drake", "Aether Drake", "\U0001f409", EPIC),
    ("eclipse_lion", "Eclipse Lion", "\U0001f981", EPIC),
    ("gravemaw", "Gravemaw", "\U0001f40a", EPIC),
    ("rift_colossus", "Rift Colossus", "\U0001f9a3", EPIC),
    ("quartz_hydra", "Quartz Hydra", "\U0001f409", EPIC),
    ("thorn_behemoth", "Thorn Behemoth", "\U0001f9a3", EPIC),
    ("cinder_sphinx", "Cinder Sphinx", "\U0001f981", EPIC),
    ("aurora_titan", "Aurora Titan", "\u26a1", EPIC),
    ("fog_djinn", "Fog Djinn", "\U0001f9de", EPIC),
    ("star_wyvern", "Star Wyvern", "\U0001f432", EPIC),
    ("crown_leviathan", "Crown Leviathan", "\U0001f40b", MYTHIC),
    ("sol_wyrm", "Sol Wyrm", "\U0001f432", MYTHIC),
    ("aether_phoenix", "Aether Phoenix", "\U0001f54a\ufe0f", MYTHIC),
    ("void_sovereign", "Void Sovereign", "\U0001f578\ufe0f", MYTHIC),
    ("eclipse_serpent", "Eclipse Serpent", "\U0001f40d", MYTHIC),
    ("rift_emperor", "Rift Emperor", "\U0001f451", MYTHIC),
    ("aether_oracle", "Aether Oracle", "\U0001f52e", MYTHIC),
    ("dawn_leviathan", "Dawn Leviathan", "\U0001f40b", MYTHIC),
    ("starforge_drake", "Starforge Drake", "\U0001f409", MYTHIC),
    ("cosmos_manticore", "Cosmos Manticore", "\U0001f981", MYTHIC),
)
ANIMAL_BY_ID = {row[0]: row for row in ANIMALS}
_NAME_INDEX: dict[str, str] = {}
for _aid, _name, _emoji, _rar in ANIMALS:
    _NAME_INDEX[_aid] = _aid
    _NAME_INDEX[_name.lower()] = _aid
    _NAME_INDEX[_name.lower().replace(" ", "")] = _aid

_lock = threading.Lock()
_store_override: Path | None = None

def set_store_path(path: Path | None) -> None:
    global _store_override
    _store_override = path

def _store_path() -> Path:
    if _store_override is not None:
        return _store_override
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "aether_hunt.json"

def _empty_store() -> dict[str, Any]:
    return {"users": {}}

def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_store()
        if not isinstance(data.get("users"), dict):
            data["users"] = {}
        return data
    except Exception:
        logger.exception("aether_hunt store read failed")
        return _empty_store()

def _save_store(data: dict[str, Any]) -> None:
    path = _store_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)

def _blank_user() -> dict[str, Any]:
    return {"zoo": {}, "caught": {}, "team": [None, None, None], "xp": {}, "last_hunt": 0.0}

def _normalize_team(raw: Any) -> list[str | None]:
    team: list[str | None] = [None, None, None]
    if not isinstance(raw, list):
        return team
    seen: set[str] = set()
    slot = 0
    for item in raw:
        if slot >= TEAM_SIZE:
            break
        if not item:
            slot += 1
            continue
        aid = str(item)
        if aid in ANIMAL_BY_ID and aid not in seen:
            team[slot] = aid
            seen.add(aid)
        slot += 1
    return team

def _ensure_user(store: dict[str, Any], user_id: int) -> dict[str, Any]:
    users = store.setdefault("users", {})
    key = str(int(user_id))
    row = users.get(key)
    if not isinstance(row, dict):
        row = _blank_user()
        users[key] = row
        return row
    zoo = row.get("zoo")
    if not isinstance(zoo, dict):
        row["zoo"] = {}
    else:
        clean: dict[str, int] = {}
        for aid, count in zoo.items():
            if aid not in ANIMAL_BY_ID:
                continue
            try:
                n = int(count)
            except (TypeError, ValueError):
                continue
            if n > 0:
                clean[str(aid)] = n
        row["zoo"] = clean
    row["team"] = _normalize_team(row.get("team"))
    xp = row.get("xp")
    if not isinstance(xp, dict):
        row["xp"] = {}
    else:
        clean_xp: dict[str, int] = {}
        for aid, val in xp.items():
            if aid not in ANIMAL_BY_ID:
                continue
            try:
                clean_xp[str(aid)] = max(0, int(val))
            except (TypeError, ValueError):
                continue
        row["xp"] = clean_xp
    caught = row.get("caught")
    if not isinstance(caught, dict):
        caught = {}
        for aid, count in (row.get("zoo") or {}).items():
            try:
                n = int(count)
            except (TypeError, ValueError):
                continue
            if n > 0 and aid in ANIMAL_BY_ID:
                caught[str(aid)] = n
        row["caught"] = caught
    else:
        clean_c = {}
        for aid, val in caught.items():
            if aid not in ANIMAL_BY_ID:
                continue
            try:
                clean_c[str(aid)] = max(0, int(val))
            except (TypeError, ValueError):
                continue
        for aid, count in (row.get("zoo") or {}).items():
            try:
                n = int(count)
            except (TypeError, ValueError):
                continue
            if n > 0:
                clean_c[str(aid)] = max(clean_c.get(str(aid), 0), n)
        row["caught"] = clean_c
    try:
        row["last_hunt"] = float(row.get("last_hunt") or 0)
    except (TypeError, ValueError):
        row["last_hunt"] = 0.0
    return row

def resolve_animal(query: str | None) -> str | None:
    if not query:
        return None
    text = " ".join(str(query).strip().lower().split())
    if not text:
        return None
    if text in _NAME_INDEX:
        return _NAME_INDEX[text]
    compact = text.replace(" ", "").replace("_", "").replace("-", "")
    if compact in _NAME_INDEX:
        return _NAME_INDEX[compact]
    hits = [aid for aid, name, _emoji, _rar in ANIMALS if text in aid or text in name.lower()]
    return hits[0] if len(hits) == 1 else None

def animal_label(animal_id: str) -> str:
    row = ANIMAL_BY_ID.get(animal_id)
    return f"{row[2]} {row[1]}" if row else animal_id

def rarity_of(animal_id: str) -> str:
    row = ANIMAL_BY_ID.get(animal_id)
    return row[3] if row else COMMON

def sell_value(animal_id: str) -> int:
    return RARITY_SELL[rarity_of(animal_id)]

def xp_for_level(lvl: int) -> int:
    """OwO getXP: XP needed to advance from current level `lvl` to `lvl+1`."""
    lvl = max(1, int(lvl))
    return (lvl ** 4) + 1000


def level_of(xp: int) -> int:
    """OwO toLvl: start at 1; subtract xp_for_level while XP allows; cap at LEVEL_CAP.

    level_of(0) == 1. Threshold L1→L2 is 1001 (= 1^4 + 1000).
    """
    remaining = max(0, int(xp))
    lvl = 1
    while lvl < LEVEL_CAP and remaining >= xp_for_level(lvl):
        remaining -= xp_for_level(lvl)
        lvl += 1
    return lvl


def xp_progress(xp: int) -> tuple[int, int, int]:
    """Return (level, xp_into_level, xp_needed_for_next).

    At LEVEL_CAP, needed is 0. Display as ``Lvl N [cur/need]``.
    """
    remaining = max(0, int(xp))
    lvl = 1
    while lvl < LEVEL_CAP and remaining >= xp_for_level(lvl):
        remaining -= xp_for_level(lvl)
        lvl += 1
    need = 0 if lvl >= LEVEL_CAP else xp_for_level(lvl)
    return lvl, remaining, need

def stats_for(animal_id: str, level: int) -> tuple[int, int]:
    hp0, atk0 = RARITY_BASE[rarity_of(animal_id)]
    extra = max(0, int(level) - 1)
    return hp0 + extra * 6, atk0 + extra * 2

def owned_count(row: dict[str, Any], animal_id: str) -> int:
    try:
        return int((row.get("zoo") or {}).get(animal_id) or 0)
    except (TypeError, ValueError):
        return 0

def xp_of(row: dict[str, Any], animal_id: str) -> int:
    try:
        return int((row.get("xp") or {}).get(animal_id) or 0)
    except (TypeError, ValueError):
        return 0

def add_xp(row: dict[str, Any], animal_id: str, amount: int) -> None:
    if animal_id not in ANIMAL_BY_ID or amount <= 0:
        return
    xp = row.setdefault("xp", {})
    xp[animal_id] = xp_of(row, animal_id) + int(amount)

def roll_animal(rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    buckets = [(rarity, weight) for rarity, weight in RARITY_WEIGHT.items() if any(rar == rarity for *_n, rar in ((a,) for a in ANIMALS))]
    buckets = []
    for rarity, weight in RARITY_WEIGHT.items():
        if any(row[3] == rarity for row in ANIMALS):
            buckets.append((rarity, weight))
    rarity = rng.choices([item[0] for item in buckets], weights=[item[1] for item in buckets], k=1)[0]
    pool = [aid for aid, _n, _e, rar in ANIMALS if rar == rarity]
    return rng.choice(pool)

def cooldown_left(row: dict[str, Any], now: float | None = None) -> float:
    now = time.time() if now is None else now
    return max(0.0, HUNT_COOLDOWN - (now - float(row.get("last_hunt") or 0)))

def hunt(user_id: int, rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        wait = cooldown_left(row)
        if wait > 0:
            return {"ok": False, "error": f"Hunt is cooling down. Wait {int(wait + 0.99)}s."}
        pocket = ai_coins.get_balance(user_id)
        if pocket < HUNT_COST:
            return {"ok": False, "error": f"Hunt costs {ai_coins.coins(HUNT_COST)}. You have {ai_coins.coins(pocket)}."}
        ok, balance, err = ai_coins.resolve_wager(user_id, HUNT_COST, 0, min_bet=HUNT_COST, max_bet=HUNT_COST)
        if not ok:
            return {"ok": False, "error": err or "Could not spend Aether Coins."}
        animal_id = roll_animal(rng)
        zoo = row.setdefault("zoo", {})
        zoo[animal_id] = owned_count(row, animal_id) + 1
        caught = row.setdefault("caught", {})
        try:
            caught[animal_id] = int(caught.get(animal_id) or 0) + 1
        except (TypeError, ValueError):
            caught[animal_id] = 1
        # OwO: hunt XP goes to team pets only (caught animal does not, unless on team).
        xp_gain = int(HUNT_XP.get(rarity_of(animal_id), 1))
        for mate in row["team"]:
            if mate:
                add_xp(row, mate, xp_gain)
        row["last_hunt"] = time.time()
        _save_store(store)
        return {"ok": True, "animal_id": animal_id, "count": zoo[animal_id], "balance": balance, "new": zoo[animal_id] == 1, "xp_gain": xp_gain}

def snapshot(user_id: int) -> dict[str, Any]:
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        _save_store(store)
        return {"zoo": dict(row["zoo"]), "caught": dict(row.get("caught") or {}), "team": list(row["team"]), "xp": dict(row["xp"]), "last_hunt": float(row["last_hunt"]), "cooldown": cooldown_left(row), "points": zoo_points_for(row.get("caught") or {})}

def sell(user_id: int, query: str, count: int = 1) -> dict[str, Any]:
    animal_id = resolve_animal(query)
    if animal_id is None:
        return {"ok": False, "error": "I do not know that animal. Check /zoo."}
    try:
        count = int(count)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Count has to be a whole number."}
    if count < 1:
        return {"ok": False, "error": "Sell at least one."}
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
        payout = sell_value(animal_id) * count
        ok, balance, err = ai_coins.grant_coins(user_id, payout)
        if not ok:
            return {"ok": False, "error": err or "Could not pay out Aether Coins."}
        row["zoo"][animal_id] = have - count
        if row["zoo"][animal_id] <= 0:
            del row["zoo"][animal_id]
        _save_store(store)
        return {"ok": True, "animal_id": animal_id, "sold": count, "payout": payout, "left": owned_count(row, animal_id), "balance": balance}

def set_team_slot(user_id: int, slot: int, query: str | None) -> dict[str, Any]:
    if slot < 1 or slot > TEAM_SIZE:
        return {"ok": False, "error": f"Team slots are 1–{TEAM_SIZE}."}
    animal_id = resolve_animal(query) if query else None
    if query and animal_id is None:
        return {"ok": False, "error": "I do not know that animal. Check /zoo."}
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        idx = slot - 1
        if animal_id is None:
            row["team"][idx] = None
            _save_store(store)
            return {"ok": True, "team": list(row["team"]), "cleared": slot}
        if owned_count(row, animal_id) < 1:
            return {"ok": False, "error": f"You do not have a {animal_label(animal_id)} yet. Hunt first."}
        if animal_id in row["team"] and row["team"][idx] != animal_id:
            return {"ok": False, "error": f"{animal_label(animal_id)} is already on the team."}
        row["team"][idx] = animal_id
        _save_store(store)
        return {"ok": True, "team": list(row["team"]), "set": animal_id, "slot": slot}

def active_team(row: dict[str, Any]) -> list[str]:
    return [aid for aid in row["team"] if aid]

def _fighter(animal_id: str, level: int) -> dict[str, Any]:
    hp, atk = stats_for(animal_id, level)
    return {"id": animal_id, "level": level, "hp": hp, "max_hp": hp, "atk": atk, "side": ""}

def _living(side: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [pet for pet in side if pet["hp"] > 0]

def build_enemy_team(player: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    size = max(1, len(player))
    avg = sum(pet["level"] for pet in player) / size
    out: list[dict[str, Any]] = []
    used: set[str] = set()
    pool = [aid for aid, *_rest in ANIMALS]
    rng.shuffle(pool)
    for _i in range(size):
        pick = next((aid for aid in pool if aid not in used), pool[0])
        used.add(pick)
        lvl = min(LEVEL_CAP, max(1, int(round(avg)) + rng.randint(-1, 1)))
        out.append(_fighter(pick, lvl))
    return out

def simulate_battle(player: list[dict[str, Any]], enemy: list[dict[str, Any]], rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    for pet in player:
        pet["side"] = "you"
    for pet in enemy:
        pet["side"] = "foe"
    log: list[str] = []
    rounds = 0
    while _living(player) and _living(enemy) and rounds < 12:
        rounds += 1
        order = _living(player) + _living(enemy)
        rng.shuffle(order)
        for attacker in order:
            if attacker["hp"] <= 0:
                continue
            foes = _living(enemy) if attacker["side"] == "you" else _living(player)
            if not foes:
                break
            target = rng.choice(foes)
            dmg = max(1, attacker["atk"] + rng.randint(-2, 2))
            target["hp"] = max(0, target["hp"] - dmg)
            mark = "KO" if target["hp"] <= 0 else f"{target['hp']} HP"
            log.append(f"{animal_label(attacker['id'])} hits {animal_label(target['id'])} for {dmg}. {mark}.")
    you_live = bool(_living(player))
    foe_live = bool(_living(enemy))
    if you_live and not foe_live:
        result = "win"
    elif foe_live and not you_live:
        result = "lose"
    else:
        result = "draw"
    return {"result": result, "log": log[-8:], "rounds": rounds, "player": player, "enemy": enemy}

def battle(user_id: int, rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    with _lock:
        store = _load_store()
        row = _ensure_user(store, user_id)
        team_ids = active_team(row)
        if not team_ids:
            return {"ok": False, "error": "Set a team with /team first."}
        player = [_fighter(aid, level_of(xp_of(row, aid))) for aid in team_ids]
        enemy = build_enemy_team(player, rng)
        outcome = simulate_battle(player, enemy, rng)
        result = outcome["result"]
        xp_gain = int(BATTLE_XP.get(result, 50))
        for aid in team_ids:
            add_xp(row, aid, xp_gain)
        payout = WIN_PAYOUT if result == "win" else DRAW_PAYOUT if result == "draw" else 0
        balance = ai_coins.get_balance(user_id)
        if payout:
            ok, balance, err = ai_coins.grant_coins(user_id, payout)
            if not ok:
                payout = 0
                logger.warning("hunt battle payout failed user=%s err=%s", user_id, err)
        _save_store(store)
        return {"ok": True, "result": result, "log": outcome["log"], "rounds": outcome["rounds"], "player": outcome["player"], "enemy": outcome["enemy"], "xp_gain": xp_gain, "payout": payout, "balance": balance}

def rarity_mark(rarity: str) -> str:
    """OwO-like rank badge for catch/zoo/checklist/gear.

    Prefers configured Discord custom emoji strings (HUNT_RANK_EMOJI_*), else
    a unicode color-square + capital letter fallback. PNG tiles for upload live
    under discord/assets/hunt_ranks/.
    """
    from .hunt_ranks import rarity_mark as _rank_mark

    return _rank_mark(rarity)


def _small_count(n: int, width: int = 2) -> str:
    """OwO-style unicode superscript counts (min 2 digits like OwO 00/04; grow with densest)."""
    digits = "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079"
    raw = str(max(0, int(n)))
    width = max(2, int(width or 2), len(raw))
    raw = raw.zfill(width)
    return "".join(digits[int(ch)] for ch in raw)


def _fancy_num(n: int) -> str:
    return f"{max(0, int(n)):,}"


def zoo_rank_tally(caught: dict[str, int]) -> str:
    """OwO-like lifetime catch shorthand: M-#, E-#, R-#, U-#, C-#."""
    counts = {rarity: 0 for rarity in RARITY_ORDER}
    for aid, n in (caught or {}).items():
        if aid not in ANIMAL_BY_ID:
            continue
        try:
            count = int(n)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        counts[rarity_of(aid)] += count
    letters = {MYTHIC: "M", EPIC: "E", RARE: "R", UNCOMMON: "U", COMMON: "C"}
    return ", ".join(f"{letters[r]}-{counts[r]}" for r in (MYTHIC, EPIC, RARE, UNCOMMON, COMMON))

def daily_resets_in(now: float | None = None) -> str:
    """OwO-style `RESETS IN: H M S` until local midnight (daily lb/crate caps)."""
    from datetime import datetime, timedelta

    stamp = datetime.fromtimestamp(now if now is not None else time.time())
    nxt = (stamp + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    secs = max(0, int((nxt - stamp).total_seconds()))
    hours, rem = divmod(secs, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours}H {mins}M {secs}S"


def hunt_catch_line(
    display_name: str,
    animal_id: str,
    extras: list[str] | None = None,
    lootbox: bool = False,
    team_xp: list[tuple[str, int]] | None = None,
    gems_hud: list[dict[str, Any]] | None = None,
    lootbox_count: int | None = None,
) -> str:
    """OwO-shaped catch: seedling | spend/caught, or gem empower + You found strip."""
    row = ANIMAL_BY_ID.get(animal_id)
    if not row:
        return f"**\U0001f331 | {display_name}** spent {HUNT_COST} \u2726 and nothing turned up."
    _aid, _name, emoji, rarity = row
    label = RARITY_LABEL[rarity].lower()
    article = "an" if rarity in (UNCOMMON, EPIC) else "a"
    mark = rarity_mark(rarity)
    lines: list[str] = []
    animal_ids = [animal_id] + [aid for aid in (extras or []) if aid]
    if gems_hud:
        gem_bits = []
        for gem in gems_hud:
            gem_emoji = gem.get("emoji") or "\U0001f48e"
            left = int(gem.get("left") or 0)
            mx = max(1, int(gem.get("max") or left or 1))
            gem_bits.append(f"{gem_emoji}`[{left}/{mx}]`")
        lines.append(
            f"**\U0001f331 | {display_name}**, hunt is empowered by {' '.join(gem_bits)} !"
        )
        strip: list[str] = []
        for aid in animal_ids:
            extra = ANIMAL_BY_ID.get(aid)
            if extra:
                strip.append(extra[2])
        if strip:
            lines.append(f"| You found: {' '.join(strip)}")
    else:
        lines.append(
            f"**\U0001f331 | {display_name}** spent {HUNT_COST} \u2726 and caught {article} **{label}** {mark} {emoji}!"
        )
        extra_bits: list[str] = []
        for aid in extras or []:
            extra = ANIMAL_BY_ID.get(aid)
            if extra:
                extra_bits.append(extra[2])
        if extra_bits:
            lines.append(f"| You found: {' '.join(extra_bits)}")
    # Team XP: collapse pet emojis onto one OwO-style line when possible
    xp_emojis: list[str] = []
    xp_total = 0
    for pet_emoji, xp_n in team_xp or []:
        if not pet_emoji:
            continue
        try:
            n = int(xp_n)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        xp_emojis.append(pet_emoji)
        xp_total = n
    if xp_emojis:
        lines.append(f"| {''.join(xp_emojis)} gained **{xp_total}xp**!")
    if lootbox:
        n = max(1, int(lootbox_count or 1))
        lines.append(
            f"**\U0001f4e6 |** You found a **lootbox**! `[{n}/3] RESETS IN: {daily_resets_in()}`"
        )
    return "\n".join(lines)


def zoo_points_for(caught: dict[str, int]) -> int:
    total = 0
    for aid, n in (caught or {}).items():
        try:
            count = int(n)
        except (TypeError, ValueError):
            continue
        if count <= 0 or aid not in ANIMAL_BY_ID:
            continue
        total += count * RARITY_POINTS[rarity_of(aid)]
    return total

def _rank_unlocked(caught: dict[str, int], rarity: str) -> bool:
    """Common always shows; higher ranks unlock after any lifetime catch of that rank."""
    if rarity == COMMON:
        return True
    for aid, n in (caught or {}).items():
        if aid not in ANIMAL_BY_ID:
            continue
        try:
            count = int(n)
        except (TypeError, ValueError):
            continue
        if count > 0 and rarity_of(aid) == rarity:
            return True
    return False


def zoo_board(display_name: str, zoo: dict[str, int], caught: dict[str, int]) -> str:
    # OwO plant header (mirrored): herb seedling tree … tree seedling herb
    lines = [f"\U0001f33f \U0001f331 \U0001f333 **{display_name}'s zoo!** \U0001f333 \U0001f331 \U0001f33f"]
    biggest = 0
    for source in (zoo, caught):
        for val in (source or {}).values():
            try:
                biggest = max(biggest, int(val))
            except (TypeError, ValueError):
                continue
    width = max(2, len(str(max(0, biggest))))
    shown = False
    for rarity in RARITY_ORDER:
        if not _rank_unlocked(caught or {}, rarity):
            continue
        shown = True
        pool = [row for row in ANIMALS if row[3] == rarity]
        cells: list[str] = []
        for aid, _name, emoji, _rar in pool:
            try:
                ever = int((caught or {}).get(aid) or 0)
            except (TypeError, ValueError):
                ever = 0
            try:
                have = int((zoo or {}).get(aid) or 0)
            except (TypeError, ValueError):
                have = 0
            if ever > 0 or have > 0:
                cells.append(f"{emoji}{_small_count(have, width)}")
            else:
                # Locked ? for undiscovered species inside an unlocked rank
                cells.append(f"\u2753{_small_count(0, width)}")
        mark = rarity_mark(rarity)
        for i in range(0, max(len(cells), 1), ZOO_COLS):
            chunk = cells[i : i + ZOO_COLS]
            # Rank mark + 3 spaces (OwO), then emoji+count units spaced with 2
            prefix = f"{mark}   " if i == 0 else "\u3000\u3000   "
            lines.append(prefix + "  ".join(chunk))
    if not shown:
        # Empty lifetime: still show common rank of locked ?
        mark = rarity_mark(COMMON)
        pool = [row for row in ANIMALS if row[3] == COMMON]
        cells = [f"\u2753{_small_count(0, 2)}" for _ in pool]
        for i in range(0, max(len(cells), 1), ZOO_COLS):
            chunk = cells[i : i + ZOO_COLS]
            prefix = f"{mark}   " if i == 0 else "\u3000\u3000   "
            lines.append(prefix + "  ".join(chunk))
    points = zoo_points_for(caught)
    # Lifetime Zoo Points — display only, not spendable
    lines.append(f"**Zoo Points: __{_fancy_num(points)}__**")
    lines.append(f"**{zoo_rank_tally(caught)}**")
    return "\n".join(lines)

def owned_catalog(zoo: dict[str, int]) -> list[tuple[str, str, str, str]]:
    out: list[tuple[str, str, str, str]] = []
    for aid, name, emoji, rarity in ANIMALS:
        try:
            n = int((zoo or {}).get(aid) or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            out.append((aid, name, emoji, rarity))
    return out

def zoo_lines(zoo: dict[str, int], xp: dict[str, int]) -> list[str]:
    if not zoo:
        return ["The menagerie is empty. Run /hunt."]
    lines: list[str] = []
    for rarity in RARITY_ORDER:
        chunk = [(aid, count) for aid, count in zoo.items() if rarity_of(aid) == rarity]
        if not chunk:
            continue
        chunk.sort(key=lambda item: ANIMAL_BY_ID[item[0]][1])
        lines.append(f"**{RARITY_LABEL[rarity]}**")
        for aid, count in chunk:
            lvl = level_of(int(xp.get(aid) or 0))
            lines.append(f"{animal_label(aid)} \u00d7{count} \u00b7 Lv {lvl}")
    return lines


def settings_slot_display(animal_id: str | None, xp: dict[str, int] | None = None, *, display_name: str | None = None) -> str:
    """OwO-feel settings row: `emoji [Lvl N] name`, or `empty`."""
    if not animal_id:
        return "empty"
    row = ANIMAL_BY_ID.get(animal_id)
    if not row:
        return "empty"
    _aid, name, emoji, _rar = row
    shown = (display_name or name).strip() or name
    lvl = level_of(int((xp or {}).get(animal_id) or 0))
    return f"{emoji} [Lvl {lvl}] {shown}"


def team_settings_description(team: list[str | None], xp: dict[str, int] | None = None) -> str:
    """Team Settings embed body — Active Battle Team + three slot rows."""
    xp = xp or {}
    lines = [
        "`Current Active Battle Team`",
        "Team 1",
        "",
    ]
    for i in range(TEAM_SIZE):
        aid = team[i] if i < len(team) else None
        lines.append(f"`Animal in Team Slot {i + 1}`")
        lines.append(settings_slot_display(aid, xp))
        if i < TEAM_SIZE - 1:
            lines.append("")
    return "\n".join(lines)


def team_lines(team: list[str | None], xp: dict[str, int], zoo: dict[str, int]) -> list[str]:
    lines: list[str] = []
    for i in range(TEAM_SIZE):
        aid = team[i] if i < len(team) else None
        if not aid:
            lines.append(f"**{i + 1}.** empty")
            continue
        lvl = level_of(int(xp.get(aid) or 0))
        hp, atk = stats_for(aid, lvl)
        have = int(zoo.get(aid) or 0)
        lines.append(f"**{i + 1}.** {animal_label(aid)} \u00b7 Lv {lvl} \u00b7 {hp} HP / {atk} ATK \u00b7 owned {have}")
    return lines

def fighter_line(pet: dict[str, Any]) -> str:
    return f"{animal_label(pet['id'])} Lv {pet['level']} ({max(0, pet['hp'])}/{pet['max_hp']})"
