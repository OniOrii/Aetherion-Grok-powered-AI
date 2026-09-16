from pathlib import Path

from groksito_discord.discord import aether_hunt as hunt
from groksito_discord.discord import aether_hunt_ext  # noqa: F401
from groksito_discord.llm.persona import CREATOR_DISCORD_ID, creator_is_author


def test_catalog_has_original_animals():
    assert len(hunt.ANIMALS) == 50
    assert len(hunt.ANIMAL_BY_ID) == 50
    ids = [row[0] for row in hunt.ANIMALS]
    assert len(set(ids)) == 50
    assert "cowoncy" not in " ".join(ids)
    assert hunt.resolve_animal("Sol Wyrm") == "sol_wyrm"
    assert hunt.resolve_animal("aether drake") == "aether_drake"
    assert hunt.resolve_animal("Aether Phoenix") == "aether_phoenix"
    assert hunt.resolve_animal("storm basilisk") == "storm_basilisk"
    assert hunt.resolve_animal("Cosmos Manticore") == "cosmos_manticore"
    from collections import Counter
    rarity_counts = Counter(row[3] for row in hunt.ANIMALS)
    assert rarity_counts == {
        hunt.COMMON: 10,
        hunt.UNCOMMON: 10,
        hunt.RARE: 10,
        hunt.EPIC: 10,
        hunt.MYTHIC: 10,
    }
    assert hunt.resolve_animal("nope") is None


def test_rarity_roll_stays_in_catalog(tmp_path: Path):
    import random

    rng = random.Random(1)
    seen = {hunt.roll_animal(rng) for _ in range(200)}
    assert seen <= set(hunt.ANIMAL_BY_ID)
    assert any(hunt.rarity_of(aid) == hunt.COMMON for aid in seen)


def test_level_and_stats_scale():
    # OwO curve: level_of(0)==1; L1→L2 needs 1^4+1000=1001 XP
    assert hunt.level_of(0) == 1
    assert hunt.xp_for_level(1) == 1001
    assert hunt.level_of(1000) == 1
    assert hunt.level_of(1001) == 2
    assert hunt.level_of(1001 + 1016) == 3  # through L2→L3
    assert hunt.LEVEL_CAP == 50
    # Huge XP still clamps at LEVEL_CAP
    assert hunt.level_of(10**18) == hunt.LEVEL_CAP
    hp1, atk1 = hunt.stats_for("dust_mite", 1)
    hp5, atk5 = hunt.stats_for("dust_mite", 5)
    assert hp5 > hp1
    assert atk5 > atk1


def test_hunt_xp_table_owo_manual():
    """OwO Manual Hunting / animal.json C–M hunt XP amounts."""
    assert hunt.HUNT_XP[hunt.COMMON] == 1
    assert hunt.HUNT_XP[hunt.UNCOMMON] == 10
    assert hunt.HUNT_XP[hunt.RARE] == 20
    assert hunt.HUNT_XP[hunt.EPIC] == 400
    assert hunt.HUNT_XP[hunt.MYTHIC] == 1000
    assert hunt.BATTLE_XP == {"win": 200, "draw": 100, "lose": 50}


def test_battle_bonus_xp_matches_owo_source():
    """Streak + level-diff follow OwO battleUtil (PET_LEVELING.md / source)."""
    from groksito_discord.discord import aether_hunt_ext as ext

    assert ext._streak_bonus(10) == 532
    assert ext._streak_bonus(50) == 1712
    assert ext._streak_bonus(100) == 3000
    assert ext._streak_bonus(7) == 0
    # Float mean avgs: teams 15/23/30 vs 50/50 → round(600 * (50 - 68/3)) = 16400
    player = [{"level": 15}, {"level": 23}, {"level": 30}]
    enemy = [{"level": 50}, {"level": 50}]
    assert ext._level_diff_xp(player, enemy) == 16400
    assert ext._level_diff_xp(enemy, player) == 0


def test_hunt_grants_team_xp_by_rarity(tmp_path: Path, monkeypatch):
    from groksito_discord.discord import ai_coins

    hunt.set_store_path(tmp_path / "hunt.json")
    monkeypatch.setattr(ai_coins, "get_balance", lambda _uid: 500)
    monkeypatch.setattr(
        ai_coins,
        "resolve_wager",
        lambda *_a, **_k: (True, 490, ""),
    )
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 42)
        row["zoo"] = {"dust_mite": 1, "thorn_wolf": 1}
        row["caught"] = {"dust_mite": 1, "thorn_wolf": 1}
        row["team"] = ["dust_mite", "thorn_wolf", None]
        row["xp"] = {}
        row["last_hunt"] = 0.0
        hunt._save_store(store)

    import random
    from groksito_discord.discord import aether_hunt_ext as ext

    # Force a common catch (ext.hunt binds roll_animal from its own module)
    monkeypatch.setattr(ext, "roll_animal", lambda rng=None: "ember_moth")
    result = hunt.hunt(42, random.Random(1))
    assert result["ok"]
    assert result["xp_gain"] == 1
    snap = hunt.snapshot(42)
    assert snap["xp"]["dust_mite"] == 1
    assert snap["xp"]["thorn_wolf"] == 1
    # Caught animal not on team does not get hunt XP (OwO team-only)
    assert snap["xp"].get("ember_moth", 0) == 0


def test_battle_ends_with_a_result():
    import random

    rng = random.Random(7)
    player = [hunt._fighter("thorn_wolf", 3), hunt._fighter("ember_elk", 2)]
    enemy = hunt.build_enemy_team(player, rng)
    assert len(enemy) == 3
    out = hunt.simulate_battle(player, enemy, rng)
    assert out["result"] in {"win", "lose", "draw"}
    assert out["rounds"] >= 1


def test_ori_gate_id_unchanged():
    assert creator_is_author(CREATOR_DISCORD_ID)
    assert not creator_is_author(1)


def test_battle_card_looks_like_owo():
    card = hunt.battle_card(
        "Ori",
        {
            "player": [hunt._fighter("eclipse_lion", 19)],
            "enemy": [hunt._fighter("ember_moth", 12)],
            "log": ["Eclipse Lion hits Ember Moth for 8. KO."],
            "rounds": 2,
            "xp_gain": 50,
            "streak": 1,
            "best_streak": 1,
        },
    )
    assert "Ori goes into battle!" in card
    assert "Ori's Team" in card
    assert "Enemy Team" in card
    assert "Turn 2" in card
    assert "`" in card and "HP`" in card and "WP`" in card
    assert "L. 19" in card
    assert "*no weapon*" in card or "no weapon" in card


def test_gear_catalog_has_weapons():
    from groksito_discord.discord import aether_gear as gear

    assert len(gear.WEAPONS) == 42
    assert len({row[0] for row in gear.WEAPONS}) == 42
    assert "mist_dagger" in gear.WEAPON_BY_ID
    assert "aether_tome" in gear.WEAPON_BY_ID
    pack = gear.blank_gear()
    pack["lootbox"] = 1
    pack["crate"] = 1
    assert gear.open_lootbox(pack)["ok"]
    crate = gear.open_crate(pack)
    assert crate["ok"]
    assert crate["wid"] == "1"


def test_hunt_and_zoo_match_owo_layout():
    line = hunt.hunt_catch_line("Ori", "dust_mite")
    assert line.startswith("**\U0001f331 | Ori** spent")
    assert "caught a **common**" in line
    assert "\U0001fab2" in line
    # OwO catch keeps the rank mark on the line: **rank** {mark} {emoji}!
    assert hunt.rarity_mark(hunt.COMMON) in line
    assert line.rstrip().endswith("!")
    epic = hunt.hunt_catch_line("Ori", "aether_drake")
    assert "caught an **epic**" in epic
    assert hunt.rarity_mark(hunt.EPIC) in epic
    # Multi-catch extras use OwO "You found:" strip (no + append)
    multi = hunt.hunt_catch_line(
        "Ori",
        "dust_mite",
        extras=["ember_moth"],
        team_xp=[("\U0001f42e", 1)],
    )
    assert "+" not in multi.splitlines()[0]
    assert "| You found:" in multi
    assert "| \U0001f42e gained **1xp**!" in multi
    board = hunt.zoo_board(
        "Ori",
        {"dust_mite": 2, "ember_moth": 0},
        {"dust_mite": 2},
    )
    # OwO plant header (mirrored): tree seedling herb on the right
    assert "\U0001f33f \U0001f331 \U0001f333 **Ori's zoo!** \U0001f333 \U0001f331 \U0001f33f" in board
    # Unseen slots stay ? with OwO-like min-2 superscript zeros; owned padded
    assert "\u2753\u2070\u2070" in board
    assert "\U0001fab2\u2070\u00b2" in board
    assert "**Zoo Points: __2__**" in board
    assert "**M-0, E-0, R-0, U-0, C-2**" in board
    # Brick/teal/gold/blue/purple unicode fallbacks (no backtick letters)
    assert hunt.rarity_mark(hunt.COMMON) == "\U0001f7e5C"
    assert hunt.rarity_mark(hunt.UNCOMMON) == "\U0001fa75U"
    assert hunt.rarity_mark(hunt.RARE) == "\U0001f7e8R"
    assert hunt.rarity_mark(hunt.EPIC) == "\U0001f7e6E"
    assert hunt.rarity_mark(hunt.MYTHIC) == "\U0001f7eaM"
    assert "`c`" not in hunt.rarity_mark(hunt.COMMON)
    assert hunt.rarity_mark(hunt.COMMON) in board
    # Rank mark packs with three spaces before the emoji strip
    assert hunt.rarity_mark(hunt.COMMON) + "   " in board
    # Locked ranks (no lifetime catch) stay hidden; common stays unlocked with ?
    assert hunt.rarity_mark(hunt.EPIC) not in board
    assert hunt.rarity_mark(hunt.MYTHIC) not in board
    # Cost / CD pacing matches OwO feel (5 / 15s)
    assert hunt.HUNT_COST == 5
    assert hunt.HUNT_COOLDOWN == 15
    assert "spent 5" in line
    # Gem empower HUD + lootbox [n/3] RESETS IN
    gemmed = hunt.hunt_catch_line(
        "Ori",
        "dust_mite",
        extras=["ember_moth"],
        gems_hud=[{"kind": "hunting", "emoji": "💎", "left": 24, "max": 25}],
        lootbox=True,
        lootbox_count=1,
        team_xp=[("🐮", 2)],
    )
    assert "hunt is empowered by" in gemmed
    assert "`[24/25]`" in gemmed
    assert "| You found:" in gemmed
    assert "**📦 |** You found a **lootbox**!" in gemmed
    assert "`[1/3] RESETS IN:" in gemmed
    assert "gained **2xp**!" in gemmed
    owned = hunt.owned_catalog({"dust_mite": 2, "sol_wyrm": 0})
    assert [row[0] for row in owned] == ["dust_mite"]


def test_rarity_marks_match_gear_and_checklist():
    from groksito_discord.discord import aether_gear as gear

    assert gear.RARITY_MARK[gear.COMMON] == hunt.rarity_mark(hunt.COMMON)
    assert gear.RARITY_MARK[gear.MYTHIC] == hunt.rarity_mark(hunt.MYTHIC)
    board = hunt.checklist_board("Ori", {"dust_mite": 1})
    assert hunt.rarity_mark(hunt.COMMON) in board
    assert hunt.rarity_mark(hunt.MYTHIC) in board



def test_hunt_rank_png_assets_exist():
    from groksito_discord.discord import hunt_ranks

    for rar in (hunt.COMMON, hunt.UNCOMMON, hunt.RARE, hunt.EPIC, hunt.MYTHIC):
        png_path = hunt_ranks.rank_png_path(rar)
        assert png_path is not None and png_path.is_file()
        raw = hunt_ranks.rank_png_bytes(rar)
        assert raw and raw[:8] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])

def test_battle_image_renders():
    from groksito_discord.discord import aether_battle as board

    player = [hunt._fighter("eclipse_lion", 19)]
    enemy = [hunt._fighter("ember_moth", 12)]
    png = board.render_battle_png(player, enemy, turn=2, max_turns=5)
    raw = png.getvalue()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 800


def test_battle_roster_field_is_owo_compact():
    from groksito_discord.discord import aether_battle as board

    pet = hunt._fighter("eclipse_lion", 19)
    field = board.roster_field([pet])
    assert field.startswith("L.19")
    assert " · " in field
    assert "*no weapon*" in field
    # Dense text under the board includes animal name + weapon badge
    assert "Eclipse Lion" in field


def test_grant_daily_supplies_once(tmp_path: Path):
    hunt.set_store_path(tmp_path / "hunt.json")
    first = hunt.grant_daily_supplies(7)
    second = hunt.grant_daily_supplies(7)
    assert first["lootbox"] == 5
    assert first["crate"] == 5
    assert first.get("raid_ticket") == 1
    assert second["lootbox"] == 0
    assert second["crate"] == 0
    assert second.get("raid_ticket") == 0
    snap = hunt.snapshot(7)
    assert snap["gear"]["lootbox"] == 5
    assert snap["gear"]["raid_ticket"] == 1


def test_grant_supplies_adds_boxes(tmp_path: Path):
    hunt.set_store_path(tmp_path / "hunt.json")
    box = hunt.grant_supplies(9, "lootbox", 3)
    crate = hunt.grant_supplies(9, "crate", 2)
    assert box["ok"] and box["left"] == 3
    assert crate["ok"] and crate["left"] == 2
    snap = hunt.snapshot(9)
    assert snap["gear"]["lootbox"] == 3
    assert snap["gear"]["crate"] == 2


def test_lootbox_is_not_guaranteed():
    import random
    from groksito_discord.discord import aether_gear as gear

    pack = gear.blank_gear()
    # First lootbox of the day is forced; later rolls are 5%
    assert gear.maybe_lootbox(pack, random.Random(1)) is True
    assert pack["lb_today"] == 1
    miss = False
    for seed in range(200):
        if gear.maybe_lootbox(pack, random.Random(seed)) is False:
            miss = True
            break
    assert miss
    found = False
    pack2 = gear.blank_gear()
    rng = random.Random(99)
    for _ in range(80):
        if gear.maybe_lootbox(pack2, rng):
            found = True
            break
    assert found
    assert pack2["lb_today"] >= 1


def test_sacrifice_essence_keeps_team_copy(tmp_path: Path):
    hunt.set_store_path(tmp_path / "hunt.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 11)
        row["zoo"] = {"dust_mite": 3, "glass_fox": 1}
        row["caught"] = {"dust_mite": 3, "glass_fox": 1}
        row["team"] = ["dust_mite", None, None]
        hunt._save_store(store)
    blocked = hunt.sacrifice(11, "dust_mite", 3)
    assert not blocked["ok"]
    out = hunt.sacrifice(11, "dust_mite", 2)
    assert out["ok"]
    assert out["sacrificed"] == 2
    assert out["gained"] == 20
    assert out["essence"] == 20
    assert out["left"] == 1
    snap = hunt.snapshot(11)
    assert snap["essence"] == 20
    assert snap["zoo"]["dust_mite"] == 1


def test_rename_sets_and_clears(tmp_path: Path, monkeypatch):
    from groksito_discord.discord import ai_coins

    hunt.set_store_path(tmp_path / "hunt.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 12)
        row["zoo"] = {"sol_wyrm": 1}
        row["caught"] = {"sol_wyrm": 1}
        hunt._save_store(store)

    monkeypatch.setattr(ai_coins, "get_balance", lambda _uid: 500)
    monkeypatch.setattr(
        ai_coins,
        "resolve_wager",
        lambda *_a, **_k: (True, 450, ""),
    )
    set_out = hunt.rename_animal(12, "sol_wyrm", "Solace")
    assert set_out["ok"]
    assert set_out["nickname"] == "Solace"
    assert set_out["fee"] == hunt.RENAME_FEE
    snap = hunt.snapshot(12)
    assert snap["nicks"]["sol_wyrm"] == "Solace"
    assert 'Sol Wyrm "Solace"' in hunt.nick_label("sol_wyrm", {"nicks": snap["nicks"]})

    clear = hunt.rename_animal(12, "sol_wyrm", "")
    assert clear["ok"] and clear["cleared"]
    snap2 = hunt.snapshot(12)
    assert "sol_wyrm" not in (snap2.get("nicks") or {})


def test_checklist_marks_discovered_and_missing():
    board = hunt.checklist_board("Ori", {"dust_mite": 2, "aether_drake": 1})
    assert "Ori's field guide" in board
    assert "Dust Mite" in board
    assert "Aether Drake" in board
    assert "Sol Wyrm" in board
    assert "Missing" in board
    assert "Found" in board
    assert "Discovered __2__ / 50" in board
    assert "cowoncy" not in board.lower()
    assert hunt.rarity_mark(hunt.COMMON) in board
    assert hunt.rarity_mark(hunt.EPIC) in board
    # No legacy backtick letter marks
    assert "`c`" not in board
    assert "`e`" not in board


def test_bestiary_requires_discovery(tmp_path: Path):
    hunt.set_store_path(tmp_path / "hunt.json")
    blocked = hunt.bestiary(21, "sol_wyrm", "Ori")
    assert not blocked["ok"]
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 21)
        row["zoo"] = {"dust_mite": 1}
        row["caught"] = {"dust_mite": 2}
        hunt._save_store(store)
    out = hunt.bestiary(21, "dust_mite", "Ori")
    assert out["ok"]
    assert "Ori's bestiary" in out["body"]
    assert "Dust Mite" in out["body"]
    assert "HP" in out["body"]
    assert "cowoncy" not in out["body"].lower()
    assert "owodex" not in out["body"].lower()


def test_salvage_weapon_to_shards(tmp_path: Path):
    from groksito_discord.discord import aether_gear as gear

    hunt.set_store_path(tmp_path / "hunt.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 22)
        pack = gear.ensure_gear(row)
        pack["weapons"]["1"] = {
            "kind": "rift_blade",
            "rarity": gear.RARE,
            "quality": 80,
            "atk": 15,
            "style": "strike",
        }
        pack["equip"]["dust_mite"] = "1"
        hunt._save_store(store)
    fav = hunt.salvage(22, "1")
    # not favorited — should work
    assert fav["ok"]
    assert fav["gained"] == gear.SHARD_BY_RARITY[gear.RARE]
    snap = hunt.snapshot(22)
    assert "1" not in (snap["gear"].get("weapons") or {})
    assert snap["gear"]["shards"] == fav["gained"]
    assert "dust_mite" not in (snap["gear"].get("equip") or {})

    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 22)
        pack = gear.ensure_gear(row)
        pack["weapons"]["2"] = {
            "kind": "ember_bow",
            "rarity": gear.COMMON,
            "quality": 50,
            "atk": 5,
            "style": "strike",
            "favorite": True,
        }
        hunt._save_store(store)
    blocked = hunt.salvage(22, "2")
    assert not blocked["ok"]
    assert "favorite" in blocked["error"].lower()



def test_weapon_detail_embed_fields(tmp_path: Path):
    from groksito_discord.discord import aether_gear as gear

    hunt.set_store_path(tmp_path / "hunt.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 31)
        pack = gear.ensure_gear(row)
        pack["weapons"]["7"] = {
            "kind": "rift_blade",
            "rarity": gear.RARE,
            "quality": 62,
            "atk": 12,
            "style": "cleave",
        }
        pack["equip"]["dust_mite"] = "7"
        hunt._save_store(store)

    missing = hunt.weapon_detail(31, "999", "Ori")
    assert not missing["ok"]

    out = hunt.weapon_detail(31, "7", "Ori")
    assert out["ok"]
    body = out["body"]
    assert "**Name**" in body and "Rift Blade" in body
    assert "**ID** `7`" in body
    assert "**Salvage**" in body and "shards" in body
    assert "**Quality** 62%" in body
    assert "**WP Cost**" in body
    assert str(gear.style_wp_cost("cleave")) in body
    assert "**Description**" in body and ("foe" in body.lower() or "opponent" in body.lower() or "veil" in body.lower())
    assert "**Passives**" in body and "Rift Carve" in body
    assert "**Equipped**" in body and "Dust Mite" in body
    assert "cowoncy" not in body.lower()
    assert "owo" not in body.lower()

    board = hunt.weapon_board("Ori", pack, row)
    assert "`7`" in board
    assert "Quality: 62%" in board
    assert "Dust Mite" in board


def test_weapon_detail_text_styles():
    from groksito_discord.discord import aether_gear as gear

    strike = gear.weapon_detail_text(
        {"wid": "1", "name": "Rift Blade", "emoji": "x", "rarity": gear.COMMON, "quality": 40, "atk": 5, "style": "strike"}
    )
    mend = gear.weapon_detail_text(
        {"wid": "2", "name": "Lantern Staff", "emoji": "y", "rarity": gear.EPIC, "quality": 90, "atk": 20, "style": "mend"}
    )
    assert gear.style_wp_cost("strike") == 8
    assert gear.style_wp_cost("mend") == 10
    assert "one random opponent" in strike
    assert "lowest-health ally" in mend or "ally" in mend.lower()
    assert "Salvage" in mend



def test_raid_spends_ticket_and_fights(tmp_path: Path):
    import random
    from groksito_discord.discord import aether_gear as gear

    hunt.set_store_path(tmp_path / "hunt.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 23)
        row["zoo"] = {"dust_mite": 1, "thorn_wolf": 1, "ember_elk": 1}
        row["caught"] = dict(row["zoo"])
        row["team"] = ["dust_mite", "thorn_wolf", "ember_elk"]
        row["xp"] = {"dust_mite": 5000, "thorn_wolf": 5000, "ember_elk": 5000}
        pack = gear.ensure_gear(row)
        pack["raid_ticket"] = 1
        hunt._save_store(store)
    out = hunt.raid(23, random.Random(3))
    assert out["ok"]
    assert out["result"] in {"win", "lose", "draw"}
    assert out["tickets_left"] == 0
    assert len(out["enemy"]) == 3
    # second raid without ticket fails
    blocked = hunt.raid(23, random.Random(3))
    assert not blocked["ok"]


def test_crate_drops_on_finished_battle_not_win_only():
    import random
    from groksito_discord.discord import aether_gear as gear

    pack = gear.blank_gear()
    # First of day is forced even when "won" is False (lose/tie)
    assert gear.maybe_crate(pack, False, random.Random(1)) is True
    assert pack["crate_today"] == 1
    assert pack["crate"] == 1
    # Cap still applies
    pack["crate_today"] = 3
    assert gear.maybe_crate(pack, True, random.Random(1)) is False


def test_inventory_shows_daily_cadence_brackets():
    from groksito_discord.discord import aether_gear as gear

    pack = gear.blank_gear()
    pack["lootbox"] = 2
    pack["crate"] = 1
    pack["lb_today"] = 1
    pack["crate_today"] = 2
    pack["day"] = __import__("datetime").date.today().isoformat()
    pack["active"] = {"hunting": {"rarity": "common", "left": 20}}
    text = gear.inventory_text("Ori", pack)
    assert "`[1/3]`" in text
    assert "`[2/3]`" in text
    assert "Hunt lootboxes today" in text
    assert "battle crates today" in text
    assert "`[20/25]`" in text
    assert "**Supplies**" in text
    assert "LB `2`" in text
    assert "crate `1`" in text
    assert "**Active**" in text
    # Active gem sits under its own header, not jammed onto one line with the label.
    assert "\n**Active**\n" in text or text.index("**Active**") < text.index("Hunting Gem")


def test_inventory_mobile_layout_short_weapon_rows():
    """Weapon quality is short (`N%`) and sections are spaced for mobile Discord."""
    from groksito_discord.discord import aether_gear as gear

    pack = gear.blank_gear()
    pack["lootbox"] = 0
    pack["crate"] = 1
    pack["shards"] = 200
    pack["raid_ticket"] = 0
    pack["day"] = __import__("datetime").date.today().isoformat()
    pack["gems"]["lucky_uncommon"] = 1
    pack["active"] = {"hunting": {"rarity": "epic", "left": 37}}
    pack["weapons"] = {
        "1": {"kind": "ash_spear", "rarity": "common", "quality": 57, "atk": 6, "style": "strike"},
        "2": {"kind": "eclipse_glaive", "rarity": "rare", "quality": 64, "atk": 14, "style": "cleave"},
    }
    text = gear.inventory_text("Ori", pack)
    assert "**Supplies**" in text
    assert "shards `200`" in text
    assert "raid `0`" in text
    assert "**Gems**" in text
    assert "Lucky Gem x1" in text
    assert "**Active**" in text
    assert "`[37/50]`" in text
    assert "**Weapons**" in text
    assert "`57%`" in text
    assert "`64%`" in text
    assert "Quality:" not in text
    assert "| Quality" not in text
    # Blank line before each major section header.
    assert "\n\n**Gems**\n" in text
    assert "\n\n**Active**\n" in text
    assert "\n\n**Weapons**\n" in text
    # Long name still uses compact quality — not the wrapping "Quality: N%" form.
    assert "**Eclipse Glaive**" in text
    assert "owo" not in text.lower()


def test_battle_result_caption_crate_has_cadence():
    from groksito_discord.discord import aether_battle as board

    line = board.result_caption(
        {"result": "lose", "rounds": 4, "xp_base": 50, "xp_bonus": 0, "crate": True, "crate_today": 1}
    )
    assert "You lost" in line
    assert "weapon crate" in line
    assert "`[1/3] RESETS IN:" in line

def test_gem_durability_spend_by_role():
    """OwO-like role burn: hunting −1, empower −⌊n/2⌋, lucky/prism −n or −⌊n/2⌋."""
    from groksito_discord.discord import aether_gear as gear

    kinds = {"hunting", "empower", "lucky"}
    assert gear.gem_durability_spend("hunting", 4, kinds) == 1
    assert gear.gem_durability_spend("empower", 4, kinds) == 2
    assert gear.gem_durability_spend("lucky", 4, kinds) == 2  # all three → half
    assert gear.gem_durability_spend("lucky", 4, {"lucky"}) == 4
    assert gear.gem_durability_spend("prism", 5, {"prism"}) == 5
    assert gear.gem_durability_spend("prism", 5, {"hunting", "empower", "prism"}) == 2


def test_gem_tiers_include_legendary_fabled_and_prism():
    from groksito_discord.discord import aether_gear as gear

    assert gear.LEGENDARY in gear.RARITY_ORDER
    assert gear.FABLED in gear.RARITY_ORDER
    assert gear.GEM_EXTRA[gear.LEGENDARY] == 7
    assert gear.GEM_EXTRA[gear.FABLED] == 9
    assert gear.GEM_HUNTS[gear.LEGENDARY] == 100
    assert gear.GEM_HUNTS[gear.FABLED] == 100
    assert "prism" in gear.GEM_BY_KIND
    assert gear.GEM_BY_KIND["prism"][1] == "Prism Gem"
    # Drop table includes L/F; weapon crate table stays C–M
    assert gear.LEGENDARY in gear.GEM_WEIGHT
    assert gear.FABLED in gear.GEM_WEIGHT
    assert gear.LEGENDARY not in gear.CRATE_WEIGHT


def test_spend_gems_updates_left_and_clears_expired():
    from groksito_discord.discord import aether_gear as gear

    pack = gear.blank_gear()
    pack["gems"]["hunting_common"] = 1
    pack["gems"]["lucky_common"] = 1
    assert gear.use_gem(pack, "hunting", "common")["ok"]
    assert gear.use_gem(pack, "lucky", "common")["ok"]
    used = gear.active_gems(pack)
    assert set(used) == {"hunting", "lucky"}
    # n=3, no empower → hunting −1, lucky −3
    gear.spend_gems(pack, used, 3)
    assert pack["active"]["hunting"]["left"] == 24
    assert pack["active"]["lucky"]["left"] == 22
    # Drain lucky to 0
    pack["active"]["lucky"]["left"] = 2
    gear.spend_gems(pack, {"lucky": "common"}, 3)  # spend 3 → expire
    assert "lucky" not in pack["active"]
    assert "hunting" in pack["active"]


def test_prism_weights_double_epic_mythic():
    from groksito_discord.discord import aether_gear as gear

    base = {"common": 100, "uncommon": 50, "rare": 20, "epic": 10, "mythic": 5}
    out = gear.prism_weights(base)
    assert out["epic"] == 20
    assert out["mythic"] == 10
    assert out["common"] == 100


def test_hunt_applies_role_durability_and_hud(tmp_path: Path, monkeypatch):
    import random
    from groksito_discord.discord import aether_gear as gear
    from groksito_discord.discord import ai_coins

    hunt.set_store_path(tmp_path / "hunt.json")
    monkeypatch.setattr(ai_coins, "get_balance", lambda _uid: 500)
    monkeypatch.setattr(
        ai_coins,
        "resolve_wager",
        lambda *_a, **_k: (True, 495, ""),
    )
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 99)
        row["last_hunt"] = 0.0
        pack = gear.ensure_gear(row)
        pack["gems"]["hunting_common"] = 1
        pack["gems"]["empower_common"] = 1
        assert gear.use_gem(pack, "hunting", "common")["ok"]
        assert gear.use_gem(pack, "empower", "common")["ok"]
        hunt._save_store(store)
    # hunting +1 + empower double → extra = 1*2+1 = 3 → n = 4
    out = hunt.hunt(99, random.Random(1))
    assert out["ok"]
    assert len(out["animals"]) == 4
    hud = {g["kind"]: g for g in out.get("gems_hud") or []}
    assert "hunting" in hud and "empower" in hud
    # Post-spend: hunting 25−1=24; empower 25−⌊4/2⌋=23
    assert hud["hunting"]["left"] == 24
    assert hud["hunting"]["max"] == 25
    assert hud["empower"]["left"] == 23
    assert hud["empower"]["max"] == 25
    # Persisted
    snap = hunt.snapshot(99)
    assert snap["gear"]["active"]["hunting"]["left"] == 24
    assert snap["gear"]["active"]["empower"]["left"] == 23


def test_inventory_lists_prism_and_fabled_tiers():
    from groksito_discord.discord import aether_gear as gear

    pack = gear.blank_gear()
    pack["gems"]["prism_fabled"] = 2
    pack["gems"]["hunting_legendary"] = 1
    pack["active"] = {"prism": {"rarity": "fabled", "left": 80}}
    text = gear.inventory_text("Ori", pack)
    assert "Prism Gem" in text
    assert "Fabled" in text
    assert "Legendary" in text
    assert "`[80/100]`" in text
    assert "**Gems**" in text
    assert "**Active**" in text


def test_resist_mitigation_owo_curve():
    """OwO res/(100+res)*0.8 — never fully nullifies; asymptote 80%."""
    from groksito_discord.discord import aether_battle as board

    assert board.resist_mitigation(0) == 0.0
    # res=100 → 100/200*0.8 = 0.4
    assert abs(board.resist_mitigation(100) - 0.4) < 1e-9
    # high resist still < 0.8
    assert board.resist_mitigation(10_000) < 0.8
    assert board.resist_mitigation(10_000) > 0.79
    # 100 raw vs 100 PR → 60 dealt
    assert board.apply_resist(100, 100) == 60
    assert board.apply_resist(50, 0) == 50
    assert board.apply_resist(10, 500) >= 1


def test_combat_phys_vs_weapon_paths():
    """Physical = ATK vs PR; weapon strike = MAG vs MR + WP spend; random target."""
    import random
    from groksito_discord.discord import aether_battle as board

    rng = random.Random(0)
    attacker = {
        "id": "thorn_wolf",
        "atk": 40,
        "mag": 25,
        "wp": 20,
        "max_wp": 20,
        "hp": 50,
        "max_hp": 50,
        "pr": 10,
        "mr": 10,
        "weapon": {"kind": "rift_blade", "style": "strike", "atk": 8, "name": "Rift Blade", "emoji": "x"},
    }
    foe_a = {"id": "ember_moth", "hp": 80, "max_hp": 80, "pr": 0, "mr": 100, "atk": 1, "mag": 1, "wp": 0}
    foe_b = {"id": "dust_mite", "hp": 80, "max_hp": 80, "pr": 100, "mr": 0, "atk": 1, "mag": 1, "wp": 0}
    # Weapon path: spends strike WP (8), MAG vs MR — prefer low-MR foe if chosen
    line = board.apply_action(attacker, [attacker], [foe_a, foe_b], rng)
    assert attacker["wp"] == 12  # 20 - 8
    assert "(weapon)" in line
    assert "strikes" in line or "cleaves" in line or "mends" in line
    # Damage should have landed on exactly one foe for strike
    damaged = [p for p in (foe_a, foe_b) if p["hp"] < 80]
    assert len(damaged) == 1


def test_combat_wp_fallback_to_physical():
    """WP too low for weapon style → physical ATK vs PR, no WP spend."""
    import random
    from groksito_discord.discord import aether_battle as board
    from groksito_discord.discord import aether_gear as gear

    rng = random.Random(1)
    cost = gear.style_wp_cost("cleave")
    attacker = {
        "id": "thorn_wolf",
        "atk": 50,
        "mag": 80,
        "wp": cost - 1,
        "max_wp": 40,
        "hp": 50,
        "max_hp": 50,
        "pr": 10,
        "mr": 10,
        "weapon": {"kind": "copper_axe", "style": "cleave", "atk": 10, "name": "Copper Axe", "emoji": "x"},
    }
    foe = {"id": "ember_moth", "hp": 100, "max_hp": 100, "pr": 0, "mr": 0, "atk": 1, "mag": 1, "wp": 0}
    before = attacker["wp"]
    line = board.apply_action(attacker, [attacker], [foe], rng)
    assert attacker["wp"] == before  # no spend
    assert "(phys)" in line
    assert "hits" in line
    assert "cleaves" not in line
    assert foe["hp"] < 100


def test_combat_cleave_and_mend_overrides():
    """Cleave = multi foe MAG vs MR; mend = ally heal; both spend WP."""
    import random
    from groksito_discord.discord import aether_battle as board
    from groksito_discord.discord import aether_gear as gear

    rng = random.Random(2)
    cleaver = {
        "id": "thorn_wolf",
        "atk": 10,
        "mag": 40,
        "wp": 30,
        "max_wp": 30,
        "hp": 50,
        "max_hp": 50,
        "weapon": {"kind": "copper_axe", "style": "cleave", "atk": 5, "name": "Axe", "emoji": "x"},
    }
    foes = [
        {"id": "ember_moth", "hp": 60, "max_hp": 60, "pr": 0, "mr": 0},
        {"id": "dust_mite", "hp": 60, "max_hp": 60, "pr": 0, "mr": 0},
    ]
    line = board.apply_action(cleaver, [cleaver], foes, rng)
    assert cleaver["wp"] == 30 - gear.style_wp_cost("cleave")
    assert "cleaves" in line and "(weapon)" in line
    assert all(p["hp"] < 60 for p in foes)

    healer = {
        "id": "ember_elk",
        "atk": 10,
        "mag": 40,
        "wp": 20,
        "max_wp": 20,
        "hp": 50,
        "max_hp": 50,
        "weapon": {"kind": "quartz_wand", "style": "mend", "atk": 5, "name": "Wand", "emoji": "y"},
    }
    ally = {"id": "thorn_wolf", "hp": 10, "max_hp": 50}
    healthy = {"id": "dust_mite", "hp": 50, "max_hp": 50}
    line2 = board.apply_action(healer, [healer, ally, healthy], [{"id": "ember_moth", "hp": 40, "max_hp": 40}], rng)
    assert healer["wp"] == 20 - gear.style_wp_cost("mend")
    assert "mends" in line2 and "(weapon)" in line2
    assert ally["hp"] > 10
    assert healthy["hp"] == 50


def test_fighter_mag_mirrors_team_card():
    """Weapon bonus raises MAG for skills; H/P/p · W/M/m stays consistent."""
    # weed_sling = Field Tutor (meta only) so ATK/MAG math stays clean for this check
    wep = {"kind": "weed_sling", "style": "strike", "atk": 12, "name": "Weed Sling", "emoji": "x", "rarity": "rare", "quality": 70, "wid": "1"}
    bare = hunt._fighter("thorn_wolf", 5)
    armed = hunt._fighter("thorn_wolf", 5, wep)
    assert armed["atk"] == bare["atk"] + 12
    assert armed["mag"] == bare["mag"] + 12
    mend = hunt._fighter("thorn_wolf", 5, {**wep, "style": "mend", "kind": "aether_tome"})
    assert mend["atk"] == bare["atk"]  # mend does not boost physical
    assert mend["mag"] > bare["mag"]



def test_settings_slot_display_and_team_settings_body():
    """Pure helpers for Team Settings embed rows (OwO-feel labels)."""
    assert hunt.settings_slot_display(None) == "empty"
    assert hunt.settings_slot_display("nope") == "empty"
    text = hunt.settings_slot_display("dust_mite", {"dust_mite": 0})
    assert text.startswith("🪲")
    assert "[Lvl 1]" in text
    assert "Dust Mite" in text
    nick = hunt.settings_slot_display("dust_mite", {"dust_mite": 1001}, display_name="Sparky")
    assert "[Lvl 2]" in nick and "Sparky" in nick

    body = hunt.team_settings_description(
        ["dust_mite", None, "thorn_wolf"],
        {"dust_mite": 0, "thorn_wolf": 0},
    )
    assert "`Current Active Battle Team`" in body
    assert "Team 1" in body
    assert "`Animal in Team Slot 1`" in body
    assert "`Animal in Team Slot 2`" in body
    assert "`Animal in Team Slot 3`" in body
    assert "empty" in body
    assert "Dust Mite" in body
    assert "Thorn Wolf" in body


def test_set_team_slot_clear_and_swap(tmp_path: Path, monkeypatch):
    """Slot helper used by settings Select still clears and rejects dupes."""
    store = tmp_path / "hunt.json"
    monkeypatch.setattr(hunt, "_store_path", lambda: store)
    with hunt._lock:
        data = hunt._empty_store()
        row = hunt._ensure_user(data, 42)
        row["zoo"] = {"dust_mite": 1, "thorn_wolf": 1, "ember_elk": 1}
        hunt._save_store(data)
    assert hunt.set_team_slot(42, 1, "dust_mite")["ok"]
    assert hunt.set_team_slot(42, 2, "thorn_wolf")["ok"]
    dup = hunt.set_team_slot(42, 3, "dust_mite")
    assert not dup["ok"]
    cleared = hunt.set_team_slot(42, 1, None)
    assert cleared["ok"]
    assert cleared["team"][0] is None
    assert hunt.set_team_slot(42, 3, "dust_mite")["ok"]


def test_weapon_kind_passives_unique():
    """Every WEAPONS kind has a distinct Aetherion passive id (P01–P42) + name."""
    from groksito_discord.discord import aether_gear as gear
    from groksito_discord.discord import weapon_passives as wp

    kinds = [row[0] for row in gear.WEAPONS]
    assert len(kinds) == len(wp.WEAPON_KIND_PASSIVES) == 42
    assert set(kinds) == set(wp.WEAPON_KIND_PASSIVES)
    ids = [row["passive_id"] for row in wp.WEAPON_KIND_PASSIVES.values()]
    names = [row["name"] for row in wp.WEAPON_KIND_PASSIVES.values()]
    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))
    assert set(ids) == {f"P{i:02d}" for i in range(1, 43)}
    assert wp.WEAPON_KIND_PASSIVES["rift_blade"]["name"] == "Rift Carve"
    assert wp.WEAPON_KIND_PASSIVES["wyrm_fang"]["name"] == "Crimson Siphon"
    blob = " ".join(f"{v['name']} {v['passive']} {v['description']}" for v in wp.WEAPON_KIND_PASSIVES.values())
    assert "owo" not in blob.lower()
    assert "cowoncy" not in blob.lower()


def test_mythic_stats_outclass_common_at_level_1():
    """Rarer animals are stronger in HP/ATK and WP/PR/MR pools at the same level."""
    common = hunt._fighter("dust_mite", 1)  # common
    mythic = hunt._fighter("sol_wyrm", 1)  # mythic
    assert mythic["max_hp"] > common["max_hp"]
    assert mythic["atk"] > common["atk"]
    assert mythic["wp"] > common["wp"]
    assert mythic["pr"] > common["pr"]
    assert mythic["mr"] > common["mr"]
    # SoT RARITY_BASE: C(40,8) … M(128,30); PR/MR/WP_MAX C 6/6/40 … M 20/20/90
    hp_m, atk_m = hunt.stats_for("sol_wyrm", 1)
    hp_c, atk_c = hunt.stats_for("dust_mite", 1)
    assert (hp_c, atk_c) == (40, 8)
    assert (hp_m, atk_m) == (128, 30)
    assert hunt.RARITY_WP_MAX[hunt.MYTHIC] > hunt.RARITY_WP_MAX[hunt.COMMON]
    assert hunt.RARITY_PR[hunt.MYTHIC] > hunt.RARITY_PR[hunt.COMMON]


def test_passive_lifesteal_combat_hook():
    """Crimson Siphon (wyrm_fang) heals the attacker when dealing damage."""
    import random
    from groksito_discord.discord import aether_battle as battle

    rng = random.Random(0)
    wep = {
        "kind": "wyrm_fang",
        "style": "cleave",
        "atk": 10,
        "name": "Wyrm Fang",
        "emoji": "x",
        "rarity": "rare",
        "quality": 100,
        "wid": "9",
    }
    attacker = hunt._fighter("thorn_wolf", 5, wep)
    # Drop HP so lifesteal can restore
    attacker["hp"] = max(1, attacker["max_hp"] // 2)
    start_hp = attacker["hp"]
    foe = hunt._fighter("ember_moth", 3)
    attacker["wp"] = max(attacker["wp"], 30)
    line = battle.apply_action(attacker, [attacker], [foe], rng)
    assert "cleaves" in line or "strikes" in line or "hits" in line
    assert attacker["hp"] > start_hp
    assert foe["hp"] < foe["max_hp"] or foe["hp"] == 0

