"""Hunt gear WIP — weapons, crates, lootboxes, gems. Saved on the hunt user row."""
from __future__ import annotations

import random
from datetime import date
from typing import Any

from . import hunt_ranks as _hunt_ranks
from . import weapon_passives as _wpass

COMMON, UNCOMMON, RARE, EPIC, MYTHIC, ASTRAL, PRIMORDIAL, LEGENDARY, FABLED = (
    "common",
    "uncommon",
    "rare",
    "epic",
    "mythic",
    "astral",
    "primordial",
    "legendary",
    "fabled",
)
# Animal/weapon ladder includes Astral/Primordial; Legendary/Fabled remain gem-only tiers.
RARITY_ORDER = (COMMON, UNCOMMON, RARE, EPIC, MYTHIC, ASTRAL, PRIMORDIAL, LEGENDARY, FABLED)
RARITY_LABEL = {
    COMMON: "Common",
    UNCOMMON: "Uncommon",
    RARE: "Rare",
    EPIC: "Epic",
    MYTHIC: "Mythic",
    ASTRAL: "Astral",
    PRIMORDIAL: "Primordial",
    LEGENDARY: "Legendary",
    FABLED: "Fabled",
}
RARITY_MARK = _hunt_ranks.RARITY_MARK
rarity_mark = _hunt_ranks.rarity_mark

CRATE_WEIGHT = {
    COMMON: 380, UNCOMMON: 260, RARE: 170, EPIC: 110, MYTHIC: 50, ASTRAL: 22, PRIMORDIAL: 8,
}
# Gem drop % ≈ OwO gems.json (C→F). Weapon crates use CRATE_WEIGHT (C–P; gem L/F stay gem-only).
GEM_WEIGHT = {
    COMMON: 22,
    UNCOMMON: 22,
    RARE: 20,
    EPIC: 20,
    MYTHIC: 10,
    LEGENDARY: 5,
    FABLED: 1,
}
# Hunting extras: keep C–M 1..5; L/F from OwO Hunting amount (7 / 9).
GEM_EXTRA = {
    COMMON: 1,
    UNCOMMON: 2,
    RARE: 3,
    EPIC: 4,
    MYTHIC: 5,
    LEGENDARY: 7,
    FABLED: 9,
}
# Shared charge pool (OwO uses per-type hunt vs animal lengths — documented approx).
# C–M keep prior Aetherion values; L/F use OwO Hunting length 100.
GEM_HUNTS = {
    COMMON: 25,
    UNCOMMON: 25,
    RARE: 40,
    EPIC: 50,
    MYTHIC: 60,
    LEGENDARY: 100,
    FABLED: 100,
}
WEAPON_ATK = {
    COMMON: (4, 8), UNCOMMON: (7, 12), RARE: (11, 18), EPIC: (16, 24), MYTHIC: (22, 32),
    ASTRAL: (30, 42), PRIMORDIAL: (40, 55),
}
HUNT_XP = {COMMON: 1, UNCOMMON: 10, RARE: 20, EPIC: 400, MYTHIC: 1000, ASTRAL: 2500, PRIMORDIAL: 6000}
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
    # Aetherion name for OwO-feel Special: event-style rare-tier weight bump (no event pipeline yet).
    ("prism", "Prism Gem", "\u2b50", "boosts epic+ hunt weight"),
)
GEM_BY_KIND = {row[0]: row for row in GEM_KINDS}

def blank_gear() -> dict[str, Any]:
    return {"lootbox": 0, "crate": 0, "gems": {}, "weapons": {}, "next_wid": 1, "active": {}, "equip": {}, "day": "", "lb_today": 0, "crate_today": 0, "streak": 0, "best_streak": 0, "daily_grant": "", "shards": 0, "raid_ticket": 0, "hunt_streak": 0, "checklist_tiers": [], "battle_ticket_day": "", "hunt_ticket_day": ""}

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
    for key in ("lootbox", "crate", "next_wid", "lb_today", "crate_today", "streak", "best_streak", "shards", "raid_ticket", "hunt_streak"):
        try:
            blob[key] = max(0 if key != "next_wid" else 1, int(blob.get(key) or 0))
        except (TypeError, ValueError):
            blob[key] = 1 if key == "next_wid" else 0
    if blob["next_wid"] < 1:
        blob["next_wid"] = 1
    if not isinstance(blob.get("checklist_tiers"), list):
        blob["checklist_tiers"] = []
    for day_key in ("battle_ticket_day", "hunt_ticket_day"):
        if not isinstance(blob.get(day_key), str):
            blob[day_key] = ""
    return blob

def _today() -> str:
    return date.today().isoformat()

def _roll_day(blob: dict[str, Any]) -> None:
    today = _today()
    if blob.get("day") != today:
        blob["day"] = today
        blob["lb_today"] = 0
        blob["crate_today"] = 0
        blob["hunt_streak"] = 0

def roll_rarity(weights: dict[str, int], rng: random.Random) -> str:
    keys = [k for k in RARITY_ORDER if k in weights]
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]

_LUCKY_BUMP = {
    COMMON: 0,
    UNCOMMON: 8,
    RARE: 16,
    EPIC: 28,
    MYTHIC: 45,
    LEGENDARY: 60,
    FABLED: 80,
}


def lucky_weights(base: dict[str, int], rarity: str) -> dict[str, int]:
    bump = _LUCKY_BUMP.get(rarity, 0)
    out = dict(base)
    out[COMMON] = max(40, out.get(COMMON, 0) - bump * 4)
    out[UNCOMMON] = max(40, out.get(UNCOMMON, 0) - bump)
    out[RARE] = out.get(RARE, 0) + bump
    out[EPIC] = out.get(EPIC, 0) + bump
    out[MYTHIC] = out.get(MYTHIC, 0) + max(4, bump // 2)
    if ASTRAL in out:
        out[ASTRAL] = out.get(ASTRAL, 0) + max(2, bump // 4)
    if PRIMORDIAL in out:
        out[PRIMORDIAL] = out.get(PRIMORDIAL, 0) + max(1, bump // 8)
    return out


def prism_weights(base: dict[str, int]) -> dict[str, int]:
    """OwO Special ≈ ×2 top-rank chance → ×2 epic/mythic/astral/primordial weight."""
    out = dict(base)
    for key in (EPIC, MYTHIC, ASTRAL, PRIMORDIAL):
        if key in out:
            out[key] = max(1, int(out[key]) * 2)
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
    """Drop a weapon crate on any *finished* battle (win/lose/tie). `won` is ignored."""
    _roll_day(blob)
    if blob["crate_today"] >= CRATE_DAILY:
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
        return {"ok": False, "error": "No weapon crates. Battle to find one."}
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
        return {"ok": False, "error": "Gems are hunting, lucky, empower, or prism."}
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

def active_gems(blob: dict[str, Any]) -> dict[str, str]:
    """Peek active gems with charges left (kind → rarity). Does not spend."""
    used: dict[str, str] = {}
    for kind, item in list((blob.get("active") or {}).items()):
        if not isinstance(item, dict):
            continue
        if int(item.get("left") or 0) <= 0:
            continue
        if kind not in GEM_BY_KIND:
            continue
        used[kind] = item.get("rarity") or COMMON
    return used


def gem_durability_spend(kind: str, animal_count: int, active_kinds: set[str] | frozenset[str]) -> int:
    """OwO-like durability burn per hunt (catch.js getGemSql).

    Hunting: −1 (hunt unit). Empower: −⌊n/2⌋. Lucky/Prism: −n, or −⌊n/2⌋ when
    Hunting and Empowering are both active (same rule OwO uses for Lucky/Special).
    """
    n = max(0, int(animal_count))
    if kind == "hunting":
        return 1
    if kind == "empower":
        return n // 2
    if kind in ("lucky", "prism"):
        if "hunting" in active_kinds and "empower" in active_kinds:
            return n // 2
        return n
    return 1


def spend_gems(blob: dict[str, Any], used: dict[str, str], animal_count: int) -> None:
    """Apply role-based durability spend after the catch count is known."""
    active = blob.setdefault("active", {})
    kinds = set(used)
    dead: list[str] = []
    for kind in used:
        item = active.get(kind)
        if not isinstance(item, dict):
            dead.append(kind)
            continue
        spend = gem_durability_spend(kind, animal_count, kinds)
        left = int(item.get("left") or 0) - spend
        item["left"] = left
        if left <= 0:
            dead.append(kind)
    for kind in dead:
        active.pop(kind, None)


def consume_gems(blob: dict[str, Any], animal_count: int = 1) -> dict[str, str]:
    """Backward-compatible: peek actives, then spend using animal_count (default 1)."""
    used = active_gems(blob)
    if used:
        spend_gems(blob, used, animal_count)
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

# Style icons kept for list fallback; unique passives live in weapon_passives.
_STYLE_PASSIVE = {"strike": "⚔️", "cleave": "💥", "mend": "💚"}
# Matches aether_battle.apply_action WP spend — display + combat stay in sync.
STYLE_WP_COST = {"strike": 8, "cleave": 12, "mend": 10}
_STYLE_LABEL = {"strike": "Strike", "cleave": "Cleave", "mend": "Mend"}
_STYLE_DESC = {
    "strike": "Deals MAG damage to one random opponent (vs MR). Costs WP.",
    "cleave": "Deals ~70% MAG to all opponents (vs MR). Costs WP.",
    "mend": "Restores ~55% MAG HP to the lowest-health ally. Costs WP.",
}


def style_wp_cost(style: str | None) -> int:
    return int(STYLE_WP_COST.get(style or "strike", 8))


def style_description(style: str | None) -> str:
    return _STYLE_DESC.get(style or "strike", _STYLE_DESC["strike"])


def weapon_passive_meta(kind: str | None) -> dict[str, Any] | None:
    return _wpass.passive_for_kind(kind)


def weapon_hooks(kind: str | None, quality: int | float | None = 50) -> dict[str, float]:
    return _wpass.scaled_hooks(kind, quality)


def weapon_detail_text(
    wep: dict[str, Any],
    *,
    display_name: str = "Hunter",
    holder_label: str | None = None,
) -> str:
    """OwO-feel detail card: Description + unique Passive (Aetherion names)."""
    wid = wep.get("wid") or "?"
    name = wep.get("name") or "Weapon"
    emoji = wep.get("emoji") or ""
    rar = wep.get("rarity") or COMMON
    quality = int(wep.get("quality") or 0)
    atk = int(wep.get("atk") or 0)
    style = wep.get("style") or "strike"
    kind = wep.get("kind")
    meta = _wpass.passive_for_kind(kind)
    desc, passive_blurb = _wpass.passive_card_lines(kind, quality)
    if not desc:
        desc = style_description(style)
    icon = (meta or {}).get("icon") or _STYLE_PASSIVE.get(style, "")
    pname = (meta or {}).get("name") or _STYLE_LABEL.get(style, style.title())
    shards = int(SHARD_BY_RARITY.get(rar, 1))
    wp = style_wp_cost(style)
    lines = [
        f"**Name** {emoji} {name}".rstrip(),
        f"**ID** `{wid}`",
        f"**Salvage** {shards} shards",
        f"**Quality** {quality}%",
        f"**WP Cost** {wp}",
        f"**Description** {desc}",
        f"**Passives** {icon} **{pname}** — {passive_blurb} · +{atk} ATK while equipped",
    ]
    if holder_label:
        lines.append(f"**Equipped** {holder_label}")
    else:
        lines.append("**Equipped** none — use `/equip` with this id")
    return "\n".join(lines)


def weapon_line(wep: dict[str, Any] | None) -> str:
    """Compact team/weapon row: id · rank · emoji · passive icon · quality%."""
    if not wep:
        return "no weapon"
    from .hunt_emoji import weapon_mark

    wid = wep.get("wid") or "?"
    rar = wep.get("rarity") or COMMON
    style = wep.get("style") or "strike"
    kind = wep.get("kind")
    passive = _wpass.passive_icon(kind) or _STYLE_PASSIVE.get(style, "")
    quality = int(wep.get("quality") or 0)
    emoji = weapon_mark(kind, unicode_fallback=str(wep.get("emoji") or ""))
    return f"`{wid}` {rarity_mark(rar)} {emoji} {passive} {quality}%".strip()

def inventory_text(display_name: str, blob: dict[str, Any]) -> str:
    """Mobile-friendly /inv body: labeled supplies, spaced sections, short weapon rows."""
    _roll_day(blob)
    lines = [f"===== {display_name}'s Inventory =====", ""]
    lb = int(blob.get("lootbox") or 0)
    cr = int(blob.get("crate") or 0)
    lb_today = int(blob.get("lb_today") or 0)
    crate_today = int(blob.get("crate_today") or 0)
    shards = int(blob.get("shards") or 0)
    raid = int(blob.get("raid_ticket") or 0)
    lines.append("**Supplies**")
    lines.append(f"`050` 📦 LB `{lb}` · `100` 🪵 crate `{cr}`")
    lines.append(f"`200` 🪨 shards `{shards}` · `300` 🎟️ raid `{raid}`")
    lines.append("Easy 1 · Hard 2 · Crown 3 · craft 30 shards")
    lines.append(
        f"Hunt lootboxes today `[{lb_today}/{LB_DAILY}]` · battle crates today `[{crate_today}/{CRATE_DAILY}]`"
    )
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
        lines.append("")
        lines.append("**Gems**")
        lines.extend(gem_bits)
    active = blob.get("active") or {}
    bits = []
    for kind, item in active.items():
        meta = GEM_BY_KIND.get(kind)
        if not meta or not isinstance(item, dict):
            continue
        rar = item.get("rarity") or COMMON
        left = int(item.get("left") or 0)
        mx = int(GEM_HUNTS.get(rar) or left or 1)
        bits.append(f"{meta[2]} {RARITY_LABEL.get(rar, rar)} {meta[1]} `[{left}/{mx}]`")
    if bits:
        lines.append("")
        lines.append("**Active**")
        lines.extend(bits)
    weapons = blob.get("weapons") or {}
    lines.append("")
    if weapons:
        lines.append("**Weapons**")
        for wid, raw in list(weapons.items())[:20]:
            if not isinstance(raw, dict):
                continue
            meta = WEAPON_BY_ID.get(raw.get("kind"))
            if not meta:
                continue
            rar = raw.get("rarity") or COMMON
            q = int(raw.get("quality") or 0)
            style = raw.get("style") or meta[3]
            kind = raw.get("kind") or meta[0]
            passive = _wpass.passive_icon(kind) or _STYLE_PASSIVE.get(style, "")
            # Short quality token keeps id · rarity · emoji · name · passive on one mobile line.
            lines.append(
                f"`{wid}` {rarity_mark(rar)} {meta[2]} **{meta[1]}** {passive} `{q}%`"
            )
    else:
        lines.append("No weapons yet. Battle for a crate.")
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


SHARD_BY_RARITY = {COMMON: 1, UNCOMMON: 2, RARE: 4, EPIC: 8, MYTHIC: 15, ASTRAL: 30, PRIMORDIAL: 60}


def salvage_weapon(blob: dict[str, Any], wid: str) -> dict[str, Any]:
    weapons = blob.get("weapons") or {}
    raw = weapons.get(str(wid))
    if not isinstance(raw, dict):
        return {"ok": False, "error": "No weapon with that id. Check /inv or /weapon."}
    if raw.get("favorite"):
        return {"ok": False, "error": "That weapon is favorited. Unfavorite it before salvaging."}
    meta = WEAPON_BY_ID.get(raw.get("kind"))
    if not meta:
        return {"ok": False, "error": "That weapon entry is broken."}
    for animal_id, held in list((blob.get("equip") or {}).items()):
        if str(held) == str(wid):
            blob["equip"].pop(animal_id, None)
    del weapons[str(wid)]
    rarity = raw.get("rarity") or COMMON
    gained = int(SHARD_BY_RARITY.get(rarity, 1))
    blob["shards"] = int(blob.get("shards") or 0) + gained
    return {
        "ok": True,
        "wid": str(wid),
        "kind": raw.get("kind"),
        "name": meta[1],
        "emoji": meta[2],
        "rarity": rarity,
        "gained": gained,
        "shards": int(blob["shards"]),
    }



SHARD_TICKET_COST = 30


def add_raid_tickets(blob: dict[str, Any], amount: int = 1) -> int:
    """Grant raid tickets; returns new balance."""
    n = max(0, int(amount or 0))
    blob["raid_ticket"] = int(blob.get("raid_ticket") or 0) + n
    return int(blob["raid_ticket"])


def maybe_battle_win_ticket(blob: dict[str, Any]) -> dict[str, Any] | None:
    """First wild battle win of the calendar day → +1 ticket."""
    _roll_day(blob)
    today = _today()
    if blob.get("battle_ticket_day") == today:
        return None
    blob["battle_ticket_day"] = today
    left = add_raid_tickets(blob, 1)
    return {"amount": 1, "reason": "first battle win today", "tickets": left}


def note_hunt_and_maybe_ticket(blob: dict[str, Any]) -> dict[str, Any] | None:
    """Increment daily hunt streak; +1 ticket at 10 hunts once/day."""
    _roll_day(blob)
    blob["hunt_streak"] = int(blob.get("hunt_streak") or 0) + 1
    today = _today()
    if blob["hunt_streak"] < 10:
        return None
    if blob.get("hunt_ticket_day") == today:
        return None
    blob["hunt_ticket_day"] = today
    left = add_raid_tickets(blob, 1)
    return {"amount": 1, "reason": "10 hunts today", "tickets": left}


def maybe_checklist_tier_ticket(blob: dict[str, Any], caught: dict, animals, rarity_order) -> list[dict[str, Any]]:
    """Lifetime grants when a rarity row first reaches complete (C/U/R/E/M)."""
    claimed = blob.setdefault("checklist_tiers", [])
    if not isinstance(claimed, list):
        claimed = []
        blob["checklist_tiers"] = claimed
    awards: list[dict[str, Any]] = []
    caught = caught or {}
    for rarity in rarity_order:
        if rarity in claimed:
            continue
        pool = [aid for aid, _n, _e, rar in animals if rar == rarity]
        if not pool:
            continue
        if all(int(caught.get(aid) or 0) > 0 for aid in pool):
            claimed.append(rarity)
            left = add_raid_tickets(blob, 1)
            awards.append({"amount": 1, "reason": f"checklist {rarity}", "tickets": left})
    return awards


def craft_ticket_from_shards(blob: dict[str, Any]) -> dict[str, Any]:
    """Spend 30 shards → 1 raid ticket."""
    shards = int(blob.get("shards") or 0)
    if shards < SHARD_TICKET_COST:
        return {
            "ok": False,
            "error": f"Need {SHARD_TICKET_COST} shards for a raid ticket · you have {shards}.",
        }
    blob["shards"] = shards - SHARD_TICKET_COST
    left = add_raid_tickets(blob, 1)
    return {
        "ok": True,
        "spent": SHARD_TICKET_COST,
        "shards": int(blob["shards"]),
        "tickets": left,
        "amount": 1,
        "reason": "shard exchange",
    }


def grant_raid_clear_crate(blob: dict[str, Any]) -> bool:
    """Guaranteed weapon crate that bypasses daily battle-crate caps."""
    blob["crate"] = int(blob.get("crate") or 0) + 1
    return True


def grant_gem_kind(blob: dict[str, Any], kind: str, rarity: str) -> dict[str, Any]:
    """Put one rolled gem into inventory (lootbox-style grant)."""
    if kind not in GEM_BY_KIND or rarity not in RARITY_LABEL:
        return {"ok": False}
    gid = f"{kind}_{rarity}"
    gems = blob.setdefault("gems", {})
    gems[gid] = int(gems.get(gid) or 0) + 1
    meta = GEM_BY_KIND[kind]
    return {"ok": True, "kind": kind, "rarity": rarity, "emoji": meta[2], "label": meta[1]}


def grant_daily_supplies(blob: dict[str, Any]) -> dict[str, int]:
    today = _today()
    if blob.get("daily_grant") == today:
        return {"lootbox": 0, "crate": 0, "raid_ticket": 0}
    blob["daily_grant"] = today
    blob["lootbox"] = int(blob.get("lootbox") or 0) + DAILY_LOOTBOX
    blob["crate"] = int(blob.get("crate") or 0) + DAILY_CRATE
    blob["raid_ticket"] = int(blob.get("raid_ticket") or 0) + 1
    return {"lootbox": DAILY_LOOTBOX, "crate": DAILY_CRATE, "raid_ticket": 1}


def weapon_icon_png(kind: str, rarity: str | None = None, size: int = 96):
    from .weapon_art import weapon_icon_png as _draw
    return _draw(kind, rarity, size)


def inventory_sheet_png(blob: dict[str, Any], limit: int = 8):
    from .weapon_art import inventory_sheet_png as _draw
    return _draw(blob, limit)
