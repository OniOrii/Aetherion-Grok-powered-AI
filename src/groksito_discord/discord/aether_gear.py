"""Hunt gear WIP — weapons, crates, lootboxes, gems. Saved on the hunt user row."""
from __future__ import annotations

import random
from datetime import date
from typing import Any

from . import hunt_ranks as _hunt_ranks

COMMON, UNCOMMON, RARE, EPIC, MYTHIC = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "mythic",
)
RARITY_ORDER = (COMMON, UNCOMMON, RARE, EPIC, MYTHIC)
RARITY_LABEL = {
    COMMON: "Common",
    UNCOMMON: "Uncommon",
    RARE: "Rare",
    EPIC: "Epic",
    MYTHIC: "Mythic",
}
RARITY_MARK = _hunt_ranks.RARITY_MARK
rarity_mark = _hunt_ranks.rarity_mark

CRATE_WEIGHT = {COMMON: 420, UNCOMMON: 280, RARE: 180, EPIC: 90, MYTHIC: 30}
GEM_WEIGHT = {COMMON: 22, UNCOMMON: 22, RARE: 20, EPIC: 20, MYTHIC: 16}
GEM_EXTRA = {COMMON: 1, UNCOMMON: 2, RARE: 3, EPIC: 4, MYTHIC: 5}
GEM_HUNTS = {COMMON: 25, UNCOMMON: 25, RARE: 40, EPIC: 50, MYTHIC: 60}
WEAPON_ATK = {COMMON: (4, 8), UNCOMMON: (7, 12), RARE: (11, 18), EPIC: (16, 24), MYTHIC: (22, 32)}
HUNT_XP = {COMMON: 8, UNCOMMON: 12, RARE: 20, EPIC: 40, MYTHIC: 80}
LB_DAILY = 3
CRATE_DAILY = 3
DAILY_LOOTBOX = 5
DAILY_CRATE = 5
DROP_CHANCE = 0.05

WEAPONS: tuple[tuple[str, str, str, str], ...] = (
    ("rift_blade", "Rift Blade", "\U0001f5e1\ufe0f", "strike"),
    ("ember_bow", "Ember Bow", "\U0001f3f9", "strike"),
    ("ash_spear", "Ash Spear", "\U0001f531", "strike"),
    ("peat_knife", "Peat Knife", "\U0001f52a", "strike"),
    ("copper_axe", "Copper Axe", "\U0001fa93", "cleave"),
    ("moss_club", "Moss Club", "\U0001f3cf", "strike"),
    ("glass_rapier", "Glass Rapier", "\u2694\ufe0f", "strike"),
    ("storm_hammer", "Storm Hammer", "\U0001f528", "cleave"),
    ("tide_trident", "Tide Trident", "\U0001f531", "strike"),
    ("thorn_flail", "Thorn Flail", "\u26d3\ufe0f", "cleave"),
    ("cinder_maul", "Cinder Maul", "\U0001fab5", "cleave"),
    ("quartz_wand", "Quartz Wand", "\U0001fa84", "mend"),
    ("void_scythe", "Void Scythe", "\u26b0\ufe0f", "cleave"),
    ("aurora_lance", "Aurora Lance", "\U0001f5e1\ufe0f", "strike"),
    ("moon_fan", "Moon Fan", "\U0001faad", "mend"),
    ("star_chakram", "Star Chakram", "\U0001faa9", "cleave"),
    ("aether_scepter", "Aether Scepter", "\U0001fa84", "mend"),
    ("eclipse_glaive", "Eclipse Glaive", "\U0001f5e1\ufe0f", "cleave"),
    ("grave_pick", "Grave Pick", "\u26cf\ufe0f", "strike"),
    ("crown_halberd", "Crown Halberd", "\U0001f6e1\ufe0f", "cleave"),
    ("sol_brand", "Sol Brand", "\U0001f525", "strike"),
    ("fog_needle", "Fog Needle", "\U0001f4cc", "strike"),
    ("river_hook", "River Hook", "\U0001fa9d", "strike"),
    ("lantern_staff", "Lantern Staff", "\U0001f3ee", "mend"),
    ("weed_sling", "Weed Sling", "\U0001fa80", "strike"),
    ("clay_shield", "Clay Shield", "\U0001f6e1\ufe0f", "mend"),
    ("iron_gauntlet", "Iron Gauntlet", "\U0001f94a", "strike"),
    ("drift_javelin", "Drift Javelin", "\U0001fab6", "strike"),
    ("prism_orb", "Prism Orb", "\U0001f52e", "mend"),
    ("wyrm_fang", "Wyrm Fang", "\U0001f9b7", "cleave"),
    ("mist_dagger", "Mist Dagger", "\U0001f5e1\ufe0f", "strike"),
    ("peat_mace", "Peat Mace", "\U0001f528", "cleave"),
    ("sol_crossbow", "Sol Crossbow", "\U0001f3f9", "strike"),
    ("void_orb", "Void Orb", "\U0001f52e", "mend"),
    ("storm_cleaver", "Storm Cleaver", "\u2694\ufe0f", "cleave"),
    ("glass_shard", "Glass Shard", "\U0001faa8", "strike"),
    ("moon_censer", "Moon Censer", "\U0001f6d3", "mend"),
    ("ember_chain", "Ember Chain", "\u26d3\ufe0f", "cleave"),
    ("rift_pike", "Rift Pike", "\U0001f531", "strike"),
    ("aether_tome", "Aether Tome", "\U0001f4d6", "mend"),
    ("peat_sickle", "Peat Sickle", "\U0001f9f2", "cleave"),
    ("prism_blade", "Prism Blade", "\U0001f5e1\ufe0f", "strike"),
)
WEAPON_BY_ID = {row[0]: row for row in WEAPONS}
GEM_KINDS = (
    ("hunting", "Hunting Gem", "\U0001f48e", "more animals each hunt"),
    ("lucky", "Lucky Gem", "\U0001f340", "rarer animals"),
    ("empower", "Empowering Gem", "\u2728", "double the catch"),
)
GEM_BY_KIND = {row[0]: row for row in GEM_KINDS}

def blank_gear() -> dict[str, Any]:
    return {"lootbox": 0, "crate": 0, "gems": {}, "weapons": {}, "next_wid": 1, "active": {}, "equip": {}, "day": "", "lb_today": 0, "crate_today": 0, "streak": 0, "best_streak": 0, "daily_grant": ""}

def ensure_gear(row: dict[str, Any]) -> dict[str, Any]:
    blob = row.get("gear")
    if not isinstance(blob, dict):
        blob = blank_gear()
        row["gear"] = blob
        return blob
    for key, val in blank_gear().items():
        if key not in blob:
            blob[key] = val
    for key in ("gems", "weapons", "active", "equip"):
        if not isinstance(blob.get(key), dict):
            blob[key] = {}
    for key in ("lootbox", "crate", "next_wid", "lb_today", "crate_today", "streak", "best_streak"):
        try:
            blob[key] = max(0 if key != "next_wid" else 1, int(blob.get(key) or 0))
        except (TypeError, ValueError):
            blob[key] = 1 if key == "next_wid" else 0
    if blob["next_wid"] < 1:
        blob["next_wid"] = 1
    return blob

def _today() -> str:
    return date.today().isoformat()

def _roll_day(blob: dict[str, Any]) -> None:
    today = _today()
    if blob.get("day") != today:
        blob["day"] = today
        blob["lb_today"] = 0
        blob["crate_today"] = 0

def roll_rarity(weights: dict[str, int], rng: random.Random) -> str:
    keys = [k for k in RARITY_ORDER if k in weights]
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]

def lucky_weights(base: dict[str, int], rarity: str) -> dict[str, int]:
    bump = {"common": 0, "uncommon": 8, "rare": 16, "epic": 28, "mythic": 45}[rarity]
    out = dict(base)
    out[COMMON] = max(40, out[COMMON] - bump * 4)
    out[UNCOMMON] = max(40, out[UNCOMMON] - bump)
    out[RARE] = out[RARE] + bump
    out[EPIC] = out[EPIC] + bump
    out[MYTHIC] = out[MYTHIC] + max(4, bump // 2)
    return out

def maybe_lootbox(blob: dict[str, Any], rng: random.Random) -> bool:
    _roll_day(blob)
    if blob["lb_today"] >= LB_DAILY:
        return False
    if blob["lb_today"] == 0 or rng.random() < DROP_CHANCE:
        blob["lootbox"] += 1
        blob["lb_today"] += 1
        return True
    return False

def maybe_crate(blob: dict[str, Any], won: bool, rng: random.Random) -> bool:
    _roll_day(blob)
    if not won or blob["crate_today"] >= CRATE_DAILY:
        return False
    if blob["crate_today"] == 0 or rng.random() < DROP_CHANCE:
        blob["crate"] += 1
        blob["crate_today"] += 1
        return True
    return False

def open_lootbox(blob: dict[str, Any], rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    if blob["lootbox"] < 1:
        return {"ok": False, "error": "No lootboxes. Hunt to find one."}
    blob["lootbox"] -= 1
    kind = rng.choice([row[0] for row in GEM_KINDS])
    rarity = roll_rarity(GEM_WEIGHT, rng)
    gid = f"{kind}_{rarity}"
    blob["gems"][gid] = int(blob["gems"].get(gid) or 0) + 1
    return {"ok": True, "kind": kind, "rarity": rarity, "left": blob["lootbox"]}

def open_crate(blob: dict[str, Any], rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    if blob["crate"] < 1:
        return {"ok": False, "error": "No weapon crates. Win a battle to find one."}
    blob["crate"] -= 1
    kind, name, emoji, style = rng.choice(WEAPONS)
    rarity = roll_rarity(CRATE_WEIGHT, rng)
    lo, hi = WEAPON_ATK[rarity]
    quality = rng.randint(40, 100)
    atk = lo + int((hi - lo) * quality / 100)
    wid = str(blob["next_wid"])
    blob["next_wid"] = int(blob["next_wid"]) + 1
    blob["weapons"][wid] = {"kind": kind, "rarity": rarity, "quality": quality, "atk": atk, "style": style}
    return {"ok": True, "wid": wid, "kind": kind, "name": name, "emoji": emoji, "rarity": rarity, "quality": quality, "atk": atk, "style": style, "left": blob["crate"]}

def use_gem(blob: dict[str, Any], kind: str, rarity: str | None = None) -> dict[str, Any]:
    if kind not in GEM_BY_KIND:
        return {"ok": False, "error": "Gems are hunting, lucky, or empower."}
    pick = None
    if rarity:
        gid = f"{kind}_{rarity}"
        if int(blob["gems"].get(gid) or 0) > 0:
            pick = (gid, rarity)
    if pick is None:
        for rar in reversed(RARITY_ORDER):
            gid = f"{kind}_{rar}"
            if int(blob["gems"].get(gid) or 0) > 0:
                pick = (gid, rar)
                break
    if pick is None:
        return {"ok": False, "error": f"No {kind} gem to use."}
    gid, rar = pick
    blob["gems"][gid] = int(blob["gems"][gid]) - 1
    if blob["gems"][gid] <= 0:
        del blob["gems"][gid]
    blob["active"][kind] = {"rarity": rar, "left": GEM_HUNTS[rar]}
    return {"ok": True, "kind": kind, "rarity": rar, "left": GEM_HUNTS[rar], "label": GEM_BY_KIND[kind][1]}

def consume_gems(blob: dict[str, Any]) -> dict[str, Any]:
    used = {}
    active = blob.get("active") or {}
    dead = []
    for kind, item in list(active.items()):
        if not isinstance(item, dict):
            dead.append(kind)
            continue
        left = int(item.get("left") or 0) - 1
        item["left"] = left
        used[kind] = item.get("rarity") or COMMON
        if left <= 0:
            dead.append(kind)
    for kind in dead:
        active.pop(kind, None)
    return used

def extra_catches(used: dict[str, Any]) -> int:
    extra = 0
    if "hunting" in used:
        extra += GEM_EXTRA.get(used["hunting"], 1)
    if "empower" in used:
        extra = extra * 2 + 1
    return extra

def equipped_weapon(blob: dict[str, Any], animal_id: str) -> dict[str, Any] | None:
    wid = (blob.get("equip") or {}).get(animal_id)
    if not wid:
        return None
    raw = (blob.get("weapons") or {}).get(str(wid))
    if not isinstance(raw, dict):
        return None
    meta = WEAPON_BY_ID.get(raw.get("kind"))
    if not meta:
        return None
    return {"wid": str(wid), "kind": raw.get("kind"), "name": meta[1], "emoji": meta[2], "style": raw.get("style") or meta[3], "rarity": raw.get("rarity") or COMMON, "quality": int(raw.get("quality") or 50), "atk": int(raw.get("atk") or 0)}

def equip_weapon(blob: dict[str, Any], wid: str, animal_id: str) -> dict[str, Any]:
    if wid not in (blob.get("weapons") or {}):
        return {"ok": False, "error": "No weapon with that id. Check /inv."}
    for other, held in list((blob.get("equip") or {}).items()):
        if str(held) == str(wid):
            blob["equip"].pop(other, None)
    blob.setdefault("equip", {})[animal_id] = str(wid)
    return {"ok": True, "wid": str(wid), "animal_id": animal_id}

def unequip_slot(blob: dict[str, Any], animal_id: str) -> None:
    (blob.get("equip") or {}).pop(animal_id, None)

def weapon_line(wep: dict[str, Any] | None) -> str:
    if not wep:
        return "no weapon"
    return f"{wep['emoji']} {wep['name']} {rarity_mark(wep['rarity'])}"

def inventory_text(display_name: str, blob: dict[str, Any]) -> str:
    lines = [f"===== {display_name}'s Inventory ====="]
    lines.append(f"`050` \U0001f4e6 `{int(blob.get('lootbox') or 0)}`  `100` \U0001fab5 `{int(blob.get('crate') or 0)}`")
    gem_bits = []
    for gid, n in sorted((blob.get("gems") or {}).items()):
        try:
            count = int(n)
        except (TypeError, ValueError):
            continue
        if count <= 0 or "_" not in gid:
            continue
        kind, rar = gid.split("_", 1)
        meta = GEM_BY_KIND.get(kind)
        if not meta or rar not in RARITY_LABEL:
            continue
        gem_bits.append(f"{meta[2]} {RARITY_LABEL[rar]} {meta[1]} x{count}")
    if gem_bits:
        lines.append("**Gems** " + " \u00b7 ".join(gem_bits))
    active = blob.get("active") or {}
    bits = []
    for kind, item in active.items():
        meta = GEM_BY_KIND.get(kind)
        if not meta or not isinstance(item, dict):
            continue
        rar = item.get("rarity") or COMMON
        bits.append(f"{meta[2]} {RARITY_LABEL.get(rar, rar)} {meta[1]} \u00b7 {item.get('left', 0)} hunts")
    if bits:
        lines.append("**Active** " + " \u00b7 ".join(bits))
    weapons = blob.get("weapons") or {}
    if weapons:
        lines.append("**Weapons**")
        for wid, raw in list(weapons.items())[:20]:
            if not isinstance(raw, dict):
                continue
            meta = WEAPON_BY_ID.get(raw.get("kind"))
            if not meta:
                continue
            rar = raw.get("rarity") or COMMON
            lines.append(f"`{wid}` {meta[2]} {meta[1]} {rarity_mark(rar) if rar else rar} Q{int(raw.get('quality') or 0)} +{int(raw.get('atk') or 0)} ATK")
    else:
        lines.append("No weapons yet. Win a battle for a crate.")
    return "\n".join(lines)

def resolve_weapon(blob: dict[str, Any], query: str | None) -> str | None:
    if not query:
        return None
    text = str(query).strip().lower()
    if text in (blob.get("weapons") or {}):
        return text
    hits = []
    for wid, raw in (blob.get("weapons") or {}).items():
        if not isinstance(raw, dict):
            continue
        meta = WEAPON_BY_ID.get(raw.get("kind"))
        name = (meta[1] if meta else "").lower()
        if text in wid or text in name or text in str(raw.get("kind") or ""):
            hits.append(wid)
    return hits[0] if len(hits) == 1 else None

def owned_weapons(blob: dict[str, Any]) -> list[tuple[str, str, str]]:
    out = []
    for wid, raw in (blob.get("weapons") or {}).items():
        if not isinstance(raw, dict):
            continue
        meta = WEAPON_BY_ID.get(raw.get("kind"))
        if not meta:
            continue
        rar = raw.get("rarity") or COMMON
        out.append((wid, f"{meta[2]} {meta[1]} {rarity_mark(rar) if rar else rar}", meta[1]))
    return out


def grant_daily_supplies(blob: dict[str, Any]) -> dict[str, int]:
    today = _today()
    if blob.get("daily_grant") == today:
        return {"lootbox": 0, "crate": 0}
    blob["daily_grant"] = today
    blob["lootbox"] = int(blob.get("lootbox") or 0) + DAILY_LOOTBOX
    blob["crate"] = int(blob.get("crate") or 0) + DAILY_CRATE
    return {"lootbox": DAILY_LOOTBOX, "crate": DAILY_CRATE}


def weapon_icon_png(kind: str, rarity: str | None = None, size: int = 96):
    from .weapon_art import weapon_icon_png as _draw
    return _draw(kind, rarity, size)


def inventory_sheet_png(blob: dict[str, Any], limit: int = 8):
    from .weapon_art import inventory_sheet_png as _draw
    return _draw(blob, limit)
