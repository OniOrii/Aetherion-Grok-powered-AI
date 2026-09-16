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
    assert field.startswith("L. 19")
    assert " - " in field
    assert "*no weapon*" in field
    # Image-mode fields stay emoji-centric (no long animal names)
    assert "Eclipse Lion" not in field


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
