"""Per-weapon unique passives — source: owo-research/AETHERION_WEAPON_PASSIVES.md."""
from __future__ import annotations

import re
from typing import Any

# kind -> card + combat hooks. Every WEAPONS kind appears exactly once (P01–P42).
WEAPON_KIND_PASSIVES: dict[str, dict[str, Any]] = {
    "rift_blade": {
        "passive_id": "P24",
        "name": 'Rift Carve',
        "icon": '🕳️',
        "combat_hook": 'pierce_pr_pct',
        "band": '10–25%',
        "description": 'Tear a thin cut through the veil and drive MAG into one foe (vs MR). Costs WP.',
        "passive": "Your attacks ignore {n}% of the target's PR.",
        "hooks": {"pierce_pr_pct": 17.5},
    },
    "ember_bow": {
        "passive_id": "P25",
        "name": 'Ember Trail',
        "icon": '🔥',
        "combat_hook": 'on_hit_burn_pct',
        "band": '8–18% of hit as burn over 2 turns',
        "description": 'Loose a cinder shaft that scorches one opponent with MAG (vs MR). Costs WP.',
        "passive": 'Damage you deal applies a burn equal to {n}% of the hit, ticking over 2 turns.',
        "hooks": {"burn_pct": 13},
    },
    "ash_spear": {
        "passive_id": "P26",
        "name": 'Ash Pierce',
        "icon": '🌑',
        "combat_hook": 'ignore_pr_pct',
        "band": '12–28%',
        "description": 'Lunge through drifting ash and skewer one foe with MAG (vs MR). Costs WP.',
        "passive": 'Spear thrusts ignore an additional {n}% PR beyond other pierce effects.',
        "hooks": {"ignore_pr_pct": 20},
    },
    "peat_knife": {
        "passive_id": "P27",
        "name": 'Peat Sting',
        "icon": '🟤',
        "combat_hook": 'on_hit_dot_pct',
        "band": '10–20% of hit over 3 turns',
        "description": 'A quick peat-stained slash delivers MAG to one opponent (vs MR). Costs WP.',
        "passive": 'Hits leave a bog sting that deals {n}% of the hit as damage over 3 turns.',
        "hooks": {"dot_pct": 15},
    },
    "copper_axe": {
        "passive_id": "P01",
        "name": 'Iron Vein',
        "icon": '💪',
        "combat_hook": 'str_pct',
        "band": '5–20%',
        "description": 'Sweep copper-edged steel in a wide arc, hitting all foes for ~70% MAG (vs MR). Costs WP.',
        "passive": 'Increases STR by {n}%.',
        "hooks": {"bonus_phys_pct": 12.5},
    },
    "moss_club": {
        "passive_id": "P03",
        "name": 'Deep Reserve',
        "icon": '❤️',
        "combat_hook": 'hp_pct',
        "band": '5–20%',
        "description": 'Bring the club down on one foe with damp, heavy MAG force (vs MR). Costs WP.',
        "passive": 'Increases max HP by {n}%.',
        "hooks": {"bonus_hp_pct": 12.5},
    },
    "glass_rapier": {
        "passive_id": "P10",
        "name": 'Faultline',
        "icon": '💥',
        "combat_hook": 'crit_chance_pct',
        "band": 'c 10–30% · d 25–50%',
        "description": 'A crystalline thrust finds a seam and deals MAG to one opponent (vs MR). Costs WP.',
        "passive": 'Attacks have a {c}% chance to deal {d}% more (heals can crit).',
        "hooks": {"crit_chance": 20, "crit_damage": 37.5},
    },
    "storm_hammer": {
        "passive_id": "P08",
        "name": 'Spark Recycle',
        "icon": '⚡',
        "combat_hook": 'wp_refund_pct',
        "band": '15–30% of damage → WP',
        "description": 'Crash thunder through the line — ~70% MAG to all opponents (vs MR). Costs WP.',
        "passive": 'Damage you deal restores WP equal to {n}% of damage dealt.',
        "hooks": {"wp_refund_pct": 22.5},
    },
    "tide_trident": {
        "passive_id": "P28",
        "name": 'Tide Pull',
        "icon": '🌊',
        "combat_hook": 'on_hit_wp_drain_pct',
        "band": '8–18% of hit as WP stolen',
        "description": 'Hook the current and drive three tines of MAG into one foe (vs MR). Costs WP.',
        "passive": 'Hits drain WP from the target equal to {n}% of damage dealt (you gain it).',
        "hooks": {"wp_drain_pct": 13},
    },
    "thorn_flail": {
        "passive_id": "P09",
        "name": 'Mirror Spines',
        "icon": '🌵',
        "combat_hook": 'thorns_pct',
        "band": '15–35%',
        "description": 'Spin barbed links that rake every foe for ~70% MAG (vs MR). Costs WP.',
        "passive": 'Reflect {n}% of damage taken as true damage.',
        "hooks": {"thorns_pct": 25},
    },
    "cinder_maul": {
        "passive_id": "P17",
        "name": 'Blood Fever',
        "icon": '🩸',
        "combat_hook": 'missing_hp_dmg_pct',
        "band": '2–5% per 10% missing HP',
        "description": 'Heave a smoldering maul that batters all opponents for ~70% MAG (vs MR). Costs WP.',
        "passive": 'For every 10% missing HP, deal {n}% more damage.',
        "hooks": {"missing_hp_amp": 3.5},
    },
    "quartz_wand": {
        "passive_id": "P29",
        "name": 'Quartz Focus',
        "icon": '💎',
        "combat_hook": 'mend_power_pct',
        "band": '15–35%',
        "description": 'Channel clear quartz light to restore ~55% MAG HP to the lowest-health ally. Costs WP.',
        "passive": 'Your mend skills heal for {n}% more.',
        "hooks": {"mend_bonus": 25},
    },
    "void_scythe": {
        "passive_id": "P30",
        "name": 'Void Reap',
        "icon": '☠️',
        "combat_hook": 'execute_pct',
        "band": '+20–40% dmg vs targets below 30% HP',
        "description": 'Reap a crescent of emptiness across all foes for ~70% MAG (vs MR). Costs WP.',
        "passive": 'Deal {n}% more damage to targets below 30% HP.',
        "hooks": {"execute_pct": 30},
    },
    "aurora_lance": {
        "passive_id": "P31",
        "name": 'Aurora Tip',
        "icon": '🌌',
        "combat_hook": 'ignore_mr_pct',
        "band": '10–25%',
        "description": 'Pierce with northern light — MAG to one opponent that slips past wards (vs MR). Costs WP.',
        "passive": "Your attacks ignore {n}% of the target's MR.",
        "hooks": {"ignore_mr_pct": 17.5},
    },
    "moon_fan": {
        "passive_id": "P13",
        "name": 'Bloomroot',
        "icon": '🌿',
        "combat_hook": 'heal_amp_pct',
        "band": '20–40%',
        "description": 'Unfurl silver ribs of moonlight to restore ~55% MAG HP to the lowest-health ally. Costs WP.',
        "passive": 'Incoming healing increased by {n}%.',
        "hooks": {"heal_amp_pct": 30},
    },
    "star_chakram": {
        "passive_id": "P32",
        "name": 'Star Bounce',
        "icon": '✨',
        "combat_hook": 'bounce_hit_pct',
        "band": '25–45% of primary hit to a second foe',
        "description": 'Send a ringing disc that cleaves all foes for ~70% MAG (vs MR). Costs WP.',
        "passive": 'After a cleave, a star-echo hits a random foe for {n}% of the primary hit.',
        "hooks": {"bounce_hit_pct": 35},
    },
    "aether_scepter": {
        "passive_id": "P04",
        "name": 'Wellspring',
        "icon": '🔋',
        "combat_hook": 'wp_max_pct',
        "band": '10–30%',
        "description": 'Raise the scepter and pour aether into the weakest ally (~55% MAG HP). Costs WP.',
        "passive": 'Increases max WP by {n}%.',
        "hooks": {"bonus_wp_pct": 20},
    },
    "eclipse_glaive": {
        "passive_id": "P33",
        "name": 'Eclipse Dual',
        "icon": '🌓',
        "combat_hook": 'hybrid_amp_pct',
        "band": '8–18% to both STR and MAG damage',
        "description": 'Arc of day-night steel cuts every opponent for ~70% MAG (vs MR). Costs WP.',
        "passive": 'All damage you deal is amplified by {n}% (phys and magic alike).',
        "hooks": {"hybrid_amp_pct": 13},
    },
    "grave_pick": {
        "passive_id": "P18",
        "name": 'Last Flare',
        "icon": '💀',
        "combat_hook": 'on_death_nuke_pct',
        "band": '50–75% max HP as MAG to killer',
        "description": 'Drive the pick into one foe with burial-cold MAG (vs MR). Costs WP.',
        "passive": 'On death, deal {n}% of max HP as MAG to the attacker.',
        "hooks": {"death_nuke_pct": 62.5},
    },
    "crown_halberd": {
        "passive_id": "P20",
        "name": 'Bossbrand',
        "icon": '👑',
        "combat_hook": 'boss_dmg_pct',
        "band": '10–25%',
        "description": 'Royal sweep — ~70% MAG to all opponents (vs MR), hungriest for named threats. Costs WP.',
        "passive": 'Deal {n}% more damage to bosses / raid targets.',
        "hooks": {"boss_bonus_pct": 17.5},
    },
    "sol_brand": {
        "passive_id": "P34",
        "name": 'Sol Flare',
        "icon": '☀️',
        "combat_hook": 'on_hit_mag_splash_pct',
        "band": '15–30% of hit as MAG splash to adjacent',
        "description": 'Brand one foe with solar MAG (vs MR); heat rolls off the edge. Costs WP.',
        "passive": 'Hits splash {n}% of damage dealt as MAG to a second random foe.',
        "hooks": {"mag_splash_pct": 22.5},
    },
    "fog_needle": {
        "passive_id": "P35",
        "name": 'Fog Blind',
        "icon": '🌫️',
        "combat_hook": 'mark_bonus_pct',
        "band": '12–25% bonus vs marked; mark lasts 2 turns',
        "description": 'A needle through mist: MAG to one opponent (vs MR), leaving them outlined. Costs WP.',
        "passive": 'Your first hit marks the target; you deal {n}% more to marked foes for 2 turns.',
        "hooks": {"mark_bonus_pct": 18.5},
    },
    "river_hook": {
        "passive_id": "P36",
        "name": 'River Drag',
        "icon": '🎣',
        "combat_hook": 'on_kill_wp_pct',
        "band": '20–40% max WP restored on kill',
        "description": 'Yank a foe off-balance and punch MAG through them (vs MR). Costs WP.',
        "passive": 'When you down an enemy, restore {n}% of your max WP.',
        "hooks": {"on_kill_wp_pct": 30},
    },
    "lantern_staff": {
        "passive_id": "P15",
        "name": 'Second Wind',
        "icon": '🔄',
        "combat_hook": 'eot_heal_pct',
        "band": '5–10% max HP / turn',
        "description": 'Lift the lantern and warm the lowest-health ally for ~55% MAG HP. Costs WP.',
        "passive": 'After each turn, heal {n}% of max HP.',
        "hooks": {"eot_heal_pct": 7.5},
    },
    "weed_sling": {
        "passive_id": "P23",
        "name": 'Field Tutor',
        "icon": '📚',
        "combat_hook": 'xp_bonus_pct',
        "band": '5–15%',
        "description": 'Snap a seed-shot of MAG at one opponent (vs MR). Costs WP.',
        "passive": 'No battle effect. +{n}% XP after each battle for the bearer.',
        "hooks": {"xp_bonus_pct": 10},
    },
    "clay_shield": {
        "passive_id": "P05",
        "name": 'Stone Mantle',
        "icon": '🪨',
        "combat_hook": 'pr_pct',
        "band": '15–35%',
        "description": 'Brace and mend — restore ~55% MAG HP to the lowest-health ally behind kiln-hard clay. Costs WP.',
        "passive": 'Increases PR by {n}%.',
        "hooks": {"bonus_pr_pct": 25},
    },
    "iron_gauntlet": {
        "passive_id": "P14",
        "name": 'Aegis Spend',
        "icon": '🛡️',
        "combat_hook": 'wp_mitigate_pct',
        "band": '20–40% of damage negated via WP',
        "description": 'Drive an iron fist of MAG into one foe (vs MR). Costs WP.',
        "passive": 'Negate {n}% of damage taken by spending WP.',
        "hooks": {"wp_mitigate_pct": 30},
    },
    "drift_javelin": {
        "passive_id": "P37",
        "name": 'Drift Momentum',
        "icon": '💨',
        "combat_hook": 'successive_hit_pct',
        "band": '+4–8% dmg per consecutive hit (cap 4)',
        "description": 'Hurl a feather-light javelin of MAG at one opponent (vs MR). Costs WP.',
        "passive": 'Each consecutive hit on the same target deals {n}% more (stacks up to 4, resets on miss/swap).',
        "hooks": {"successive_hit_pct": 6},
    },
    "prism_orb": {
        "passive_id": "P12",
        "name": 'Surge Echo',
        "icon": '📶',
        "combat_hook": 'on_wp_nuke_pct',
        "band": '110–150% of restored WP as MAG',
        "description": 'Refract mend-light into the weakest ally (~55% MAG HP). Costs WP.',
        "passive": 'When WP is restored, deal {n}% of the restored amount as MAG damage to an enemy.',
        "hooks": {"on_wp_nuke_pct": 130},
    },
    "wyrm_fang": {
        "passive_id": "P07",
        "name": 'Crimson Siphon',
        "icon": '🧛',
        "combat_hook": 'lifesteal_pct',
        "band": '15–35%',
        "description": 'Rake serrated fang-edges across all foes for ~70% MAG (vs MR). Costs WP.',
        "passive": 'Damage you deal heals you for {n}% of damage dealt.',
        "hooks": {"lifesteal_pct": 25},
    },
    "mist_dagger": {
        "passive_id": "P38",
        "name": 'Mist Step',
        "icon": '👤',
        "combat_hook": 'evade_pct',
        "band": '8–18% chance to fully evade',
        "description": 'Step from fog and bury MAG in one opponent (vs MR). Costs WP.',
        "passive": 'You have a {n}% chance to fully evade incoming attacks.',
        "hooks": {"evade_pct": 13},
    },
    "peat_mace": {
        "passive_id": "P21",
        "name": 'Adaptive Shell',
        "icon": '🐢',
        "combat_hook": 'adapt_resist',
        "band": '5–10%/stack · cap ~5',
        "description": 'Swing sodden iron through the line — ~70% MAG to all (vs MR). Costs WP.',
        "passive": 'After taking phys, gain phys mitigation stacks; after magic, magic stacks (cap ~5; other type clears).',
        "hooks": {"adapt_resist_pct": 7.5},
    },
    "sol_crossbow": {
        "passive_id": "P39",
        "name": 'Radiant Bolt',
        "icon": '🔆',
        "combat_hook": 'convert_phys_to_mag_pct',
        "band": '20–40% of STR hit also as MAG',
        "description": 'Bolt of noon-light: MAG to one opponent (vs MR). Costs WP.',
        "passive": '{n}% of your physical damage is also dealt as MAG (vs MR).',
        "hooks": {"convert_phys_to_mag_pct": 30},
    },
    "void_orb": {
        "passive_id": "P19",
        "name": 'Parting Gift',
        "icon": '🎁',
        "combat_hook": 'on_death_ally_gift',
        "band": 'h 25–50% · w 15–35%',
        "description": 'Crack the orb open to mend the lowest-health ally (~55% MAG HP). Costs WP.',
        "passive": 'On death, allies heal {h}% of your max HP and restore {w}% of your max WP.',
        "hooks": {"death_ally_heal_pct": 37.5, "death_ally_wp_pct": 25},
    },
    "storm_cleaver": {
        "passive_id": "P40",
        "name": 'Storm Crash',
        "icon": '⛈️',
        "combat_hook": 'post_spend_dmg_pct',
        "band": '10–22% more dmg on the skill that spent WP',
        "description": 'Cleaving thunder — ~70% MAG to every opponent (vs MR). Costs WP.',
        "passive": 'Weapon skills that spend WP deal {n}% more damage on that action.',
        "hooks": {"post_spend_dmg_pct": 16},
    },
    "glass_shard": {
        "passive_id": "P41",
        "name": 'Glass Fracture',
        "icon": '🪞',
        "combat_hook": 'low_hp_target_bonus_pct',
        "band": '+15–30% vs targets below 50% HP',
        "description": 'Fling a razor flake of MAG at one foe (vs MR). Costs WP.',
        "passive": 'Deal {n}% more damage to targets below 50% HP.',
        "hooks": {"low_hp_target_bonus_pct": 22.5},
    },
    "moon_censer": {
        "passive_id": "P11",
        "name": 'Retributive Glow',
        "icon": '💫',
        "combat_hook": 'on_heal_nuke_pct',
        "band": '60–80% of heal as MAG',
        "description": 'Swing fragrant moon-smoke to restore ~55% MAG HP to the lowest-health ally. Costs WP.',
        "passive": 'When healed, deal {n}% of the heal as MAG damage to an enemy.',
        "hooks": {"on_heal_nuke_pct": 70},
    },
    "ember_chain": {
        "passive_id": "P42",
        "name": 'Ember Link',
        "icon": '🔗',
        "combat_hook": 'chain_splash_pct',
        "band": '20–35% of hit chains to a second foe',
        "description": 'Lash burning links that cleave all opponents for ~70% MAG (vs MR). Costs WP.',
        "passive": 'On hit, {n}% of damage dealt chains to another random enemy.',
        "hooks": {"chain_splash_pct": 27.5},
    },
    "rift_pike": {
        "passive_id": "P02",
        "name": 'Aether Edge',
        "icon": '🔮',
        "combat_hook": 'mag_pct',
        "band": '5–20%',
        "description": 'Long rift-steel drives MAG into one opponent (vs MR). Costs WP.',
        "passive": 'Increases MAG by {n}%.',
        "hooks": {"bonus_mag_pct": 12.5},
    },
    "aether_tome": {
        "passive_id": "P16",
        "name": 'Ley Tick',
        "icon": '📜',
        "combat_hook": 'eot_wp_flat',
        "band": '20–40 WP / turn',
        "description": 'Read a mend canto that restores ~55% MAG HP to the lowest-health ally. Costs WP.',
        "passive": 'After each turn, restore {n} WP.',
        "hooks": {"eot_wp_flat": 30},
    },
    "peat_sickle": {
        "passive_id": "P22",
        "name": 'Echo Chorus',
        "icon": '🎶',
        "combat_hook": 'buff_scale',
        "band": '5–10% each',
        "description": 'Harvesting arc — ~70% MAG to all opponents (vs MR). Costs WP.',
        "passive": '+{n}% damage per buff on you; −{n}% damage taken per debuff on you.',
        "hooks": {"buff_scale_pct": 7.5},
    },
    "prism_blade": {
        "passive_id": "P06",
        "name": 'Null Veil',
        "icon": '🧿',
        "combat_hook": 'mr_pct',
        "band": '15–35%',
        "description": 'Refracted edge: MAG to one opponent (vs MR) behind a shimmering ward. Costs WP.',
        "passive": 'Increases MR by {n}%.',
        "hooks": {"bonus_mr_pct": 25},
    },
}


def passive_for_kind(kind: str | None) -> dict[str, Any] | None:
    if not kind:
        return None
    row = WEAPON_KIND_PASSIVES.get(str(kind))
    return dict(row) if row else None


def quality_scale(quality: int | float | None) -> float:
    """Quality picks inside the band: 0%→low, 100%→high; mid at ~50%."""
    q = max(0, min(100, int(quality or 50)))
    # Map 0..100 → 0.75..1.25 around mid so mid-band stays the stored mid.
    return 0.75 + (q / 100.0) * 0.50


def scaled_hooks(kind: str | None, quality: int | float | None = 50) -> dict[str, float]:
    meta = passive_for_kind(kind)
    if not meta:
        return {}
    scale = quality_scale(quality)
    out: dict[str, float] = {}
    for key, val in (meta.get("hooks") or {}).items():
        try:
            out[key] = float(val) * scale
        except (TypeError, ValueError):
            continue
    return out


def passive_icon(kind: str | None) -> str:
    meta = passive_for_kind(kind)
    return str((meta or {}).get("icon") or "")


def _fill_blurb(text: str, hooks: dict[str, float]) -> str:
    """Replace {n}/{c}/{d}/{h}/{w} with scaled hook values when present."""
    if not text:
        return text
    vals = list(hooks.values())
    n = int(round(vals[0])) if vals else 0
    c = int(round(hooks.get("crit_chance") or n))
    d = int(round(hooks.get("crit_damage") or (vals[1] if len(vals) > 1 else n)))
    h = int(round(hooks.get("death_ally_heal_pct") or n))
    w = int(round(hooks.get("death_ally_wp_pct") or (vals[1] if len(vals) > 1 else n)))
    out = text
    out = out.replace("{n}", str(n)).replace("{c}", str(c)).replace("{d}", str(d))
    out = out.replace("{h}", str(h)).replace("{w}", str(w))
    return out


def passive_card_lines(kind: str | None, quality: int | float | None = 50) -> tuple[str, str]:
    meta = passive_for_kind(kind)
    if not meta:
        return ("", "")
    hooks = scaled_hooks(kind, quality)
    desc = str(meta.get("description") or "")
    passive = _fill_blurb(str(meta.get("passive") or ""), hooks)
    return desc, passive
