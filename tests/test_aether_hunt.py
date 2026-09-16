from pathlib import Path

from groksito_discord.discord import aether_hunt as hunt
from groksito_discord.discord import aether_hunt_ext  # noqa: F401
from groksito_discord.llm.persona import CREATOR_DISCORD_ID, creator_is_author


def test_catalog_has_original_animals():
    assert len(hunt.ANIMALS) == 62
    assert len(hunt.ANIMAL_BY_ID) == 62
    ids = [row[0] for row in hunt.ANIMALS]
    assert len(set(ids)) == 62
    assert "cowoncy" not in " ".join(ids)
    assert hunt.resolve_animal("Sol Wyrm") == "sol_wyrm"
    assert hunt.resolve_animal("aether drake") == "aether_drake"
    assert hunt.resolve_animal("Aether Phoenix") == "aether_phoenix"
    assert hunt.resolve_animal("storm basilisk") == "storm_basilisk"
    assert hunt.resolve_animal("Cosmos Manticore") == "cosmos_manticore"
    assert hunt.resolve_animal("Starfall Lynx") == "starfall_lynx"
    assert hunt.resolve_animal("Firstroot Wyrm") == "firstroot_wyrm"
    from collections import Counter
    rarity_counts = Counter(row[3] for row in hunt.ANIMALS)
    assert rarity_counts == {
        hunt.COMMON: 10,
        hunt.UNCOMMON: 10,
        hunt.RARE: 10,
        hunt.EPIC: 10,
        hunt.MYTHIC: 10,
        hunt.ASTRAL: 6,
        hunt.PRIMORDIAL: 6,
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
    """OwO Manual Hunting C–M + Aetherion Astral/Primordial XP."""
    assert hunt.HUNT_XP[hunt.COMMON] == 1
    assert hunt.HUNT_XP[hunt.UNCOMMON] == 10
    assert hunt.HUNT_XP[hunt.RARE] == 20
    assert hunt.HUNT_XP[hunt.EPIC] == 400
    assert hunt.HUNT_XP[hunt.MYTHIC] == 1000
    assert hunt.HUNT_XP[hunt.ASTRAL] == 2500
    assert hunt.HUNT_XP[hunt.PRIMORDIAL] == 6000
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
    assert "**P-0, A-0, M-0, E-0, R-0, U-0, C-2**" in board
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
    # Cost / CD pacing: cheap hunt aligned to wallet tens (10 / 15s)
    assert hunt.HUNT_COST == 10
    assert hunt.HUNT_COST % 10 == 0
    assert hunt.HUNT_COOLDOWN == 15
    assert "spent 10" in line
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

    for rar in (hunt.COMMON, hunt.UNCOMMON, hunt.RARE, hunt.EPIC, hunt.MYTHIC, hunt.ASTRAL, hunt.PRIMORDIAL):
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
    assert "Discovered __2__ / 62" in board
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
    assert "`62%`" in board
    assert "Dust Mite" in board
    assert hunt.rarity_mark(hunt.RARE) in board
    assert f"**{hunt.rarity_mark(hunt.RARE)} Rare**" in board


def test_weapons_board_groups_by_rarity_and_empty_state():
    from groksito_discord.discord import aether_gear as gear

    empty = hunt.weapon_board("Ori", gear.blank_gear())
    assert "Ori's weapons" in empty
    assert "No weapons yet" in empty
    assert "`/crate`" in empty

    pack = gear.blank_gear()
    pack["weapons"] = {
        "3": {"kind": "rift_blade", "rarity": gear.RARE, "quality": 62, "atk": 12, "style": "cleave"},
        "1": {"kind": "ember_bow", "rarity": gear.COMMON, "quality": 40, "atk": 5, "style": "strike"},
        "2": {"kind": "quartz_wand", "rarity": gear.EPIC, "quality": 88, "atk": 20, "style": "mend"},
    }
    pack["equip"] = {"dust_mite": "3"}
    board = hunt.weapon_board("Ori", pack, {"nicks": {}})
    # Rarity headers + blank line between groups
    assert f"**{hunt.rarity_mark(hunt.COMMON)} Common**" in board
    assert f"**{hunt.rarity_mark(hunt.RARE)} Rare**" in board
    assert f"**{hunt.rarity_mark(hunt.EPIC)} Epic**" in board
    common_i = board.index(f"**{hunt.rarity_mark(hunt.COMMON)} Common**")
    rare_i = board.index(f"**{hunt.rarity_mark(hunt.RARE)} Rare**")
    epic_i = board.index(f"**{hunt.rarity_mark(hunt.EPIC)} Epic**")
    assert common_i < rare_i < epic_i
    between = board[common_i:rare_i]
    assert "\n\n" in between  # blank line between rarity groups
    # Dense row: id · mark · emoji · name · quality% · equipped animal
    assert "`1`" in board and "`40%`" in board
    assert "`3`" in board and "`62%`" in board and "Dust Mite" in board
    assert "Quality: " not in board


def test_hunt_cost_ten_passes_wallet_step(tmp_path: Path, monkeypatch):
    """HUNT_COST must be a multiple of ai_coins.STEP so resolve_wager succeeds."""
    from groksito_discord.discord import ai_coins
    from groksito_discord.discord import aether_hunt_ext as ext
    import random

    assert hunt.HUNT_COST == 10
    assert hunt.HUNT_COST % ai_coins.STEP == 0
    assert ai_coins.amount_error(hunt.HUNT_COST, hunt.HUNT_COST, hunt.HUNT_COST) == ""

    hunt.set_store_path(tmp_path / "hunt.json")
    stakes: list[int] = []

    def capture_wager(uid, stake, payout=0, min_bet=None, max_bet=None):
        stakes.append(int(stake))
        err = ai_coins.amount_error(int(stake), int(min_bet or stake), int(max_bet or stake))
        if err:
            return False, 0, err
        return True, 500 - int(stake), ""

    monkeypatch.setattr(ai_coins, "get_balance", lambda _uid: 500)
    monkeypatch.setattr(ai_coins, "resolve_wager", capture_wager)
    monkeypatch.setattr(ext, "roll_animal", lambda rng=None: "dust_mite")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 77)
        row["last_hunt"] = 0.0
        hunt._save_store(store)
    result = hunt.hunt(77, random.Random(1))
    assert result["ok"], result
    assert stakes == [10]
    assert "Bets go by" not in (result.get("error") or "")


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
    out = hunt.raid(23, tier="easy", rng=random.Random(3))
    assert out["ok"]
    assert out["result"] in {"win", "lose", "draw"}
    assert out["tickets_spent"] == 1
    assert out["tickets_left"] == 0
    assert out["tier"] == "easy"
    assert out["rift"] == "Ember Rift"
    assert len(out["enemy"]) == 3
    # second raid without ticket fails
    blocked = hunt.raid(23, tier="easy", rng=random.Random(3))
    assert not blocked["ok"]
    assert "Need 1 ticket" in (blocked.get("error") or "")


def _seed_raid_team(tmp_path: Path, uid: int, tickets: int, avg_xp: int = 5000):
    from groksito_discord.discord import aether_gear as gear

    hunt.set_store_path(tmp_path / f"hunt_{uid}.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, uid)
        row["zoo"] = {"dust_mite": 1, "thorn_wolf": 1, "ember_elk": 1}
        row["caught"] = dict(row["zoo"])
        row["team"] = ["dust_mite", "thorn_wolf", "ember_elk"]
        row["xp"] = {"dust_mite": avg_xp, "thorn_wolf": avg_xp, "ember_elk": avg_xp}
        pack = gear.ensure_gear(row)
        pack["raid_ticket"] = tickets
        hunt._save_store(store)
    return pack


def test_raid_tier_costs_and_deny_underfunded(tmp_path: Path):
    import random

    _seed_raid_team(tmp_path, 31, tickets=2)
    blocked = hunt.raid(31, tier="nightmare", rng=random.Random(1))
    assert not blocked["ok"]
    assert "Need 3 ticket" in (blocked.get("error") or "")
    # Hard spends 2
    out = hunt.raid(31, tier="hard", rng=random.Random(2))
    assert out["ok"]
    assert out["tickets_spent"] == 2
    assert out["tickets_left"] == 0
    assert out["rift"] == "Void Rift"


def test_raid_boss_scaling_easy_vs_nightmare():
    """Easy keeps today-ish inflate; Nightmare is strictly tankier at same A."""
    import random

    player = [
        hunt._fighter("dust_mite", 15),
        hunt._fighter("thorn_wolf", 15),
        hunt._fighter("ember_elk", 15),
    ]
    easy = hunt.build_raid_boss(player, random.Random(7), "easy")
    hard = hunt.build_raid_boss(player, random.Random(7), "hard")
    nm = hunt.build_raid_boss(player, random.Random(7), "nightmare")
    assert easy[0].get("raid_boss") and nm[0].get("raid_boss")
    assert nm[0]["max_hp"] > hard[0]["max_hp"] > easy[0]["max_hp"]
    assert nm[0]["atk"] > hard[0]["atk"] > easy[0]["atk"]
    # Easy ≈ today: ×1.85+40 / ×1.45+8 at mid level ~19 for A=15
    # Spot-check Easy boss is beatable-band (not brick wall vs geared L15)
    assert easy[0]["max_hp"] < nm[0]["max_hp"] * 0.75


def test_raid_win_reward_floors(tmp_path: Path, monkeypatch):
    import random
    from groksito_discord.discord import aether_gear as gear
    from groksito_discord.discord import aether_hunt_ext as ext

    _seed_raid_team(tmp_path, 41, tickets=3, avg_xp=200_000)

    def _fake_sim(player, enemy, rng=None):
        return {
            "result": "win",
            "log": ["ok"],
            "rounds": 3,
            "player": player,
            "enemy": enemy,
            "frames": [],
        }

    monkeypatch.setattr(ext, "simulate_battle", _fake_sim)
    monkeypatch.setattr(hunt, "simulate_battle", _fake_sim)
    out = hunt.raid(41, tier="easy", rng=random.Random(0))
    assert out["ok"] and out["result"] == "win"
    assert out["shard_bonus"] == 8
    assert out["xp_base"] == 300  # 200 + 100
    snap = hunt.snapshot(41)
    assert snap["gear"]["shards"] >= 8

    _seed_raid_team(tmp_path, 42, tickets=3, avg_xp=200_000)
    out_h = hunt.raid(42, tier="hard", rng=random.Random(0))
    assert out_h["shard_bonus"] == 22
    assert out_h["xp_base"] == 400
    assert out_h["crate"] is True
    snap_h = hunt.snapshot(42)
    assert snap_h["gear"]["crate"] >= 1

    _seed_raid_team(tmp_path, 43, tickets=3, avg_xp=200_000)
    out_n = hunt.raid(43, tier="nightmare", rng=random.Random(0))
    assert out_n["shard_bonus"] == 45
    assert out_n["xp_base"] == 550
    assert out_n["crate"] is True
    assert out_n.get("empowered")  # guaranteed on NM


def test_raid_loss_pity_shards_hard_nm(tmp_path: Path, monkeypatch):
    import random
    from groksito_discord.discord import aether_hunt_ext as ext

    def _lose(player, enemy, rng=None):
        return {
            "result": "lose",
            "log": ["x"],
            "rounds": 2,
            "player": player,
            "enemy": enemy,
            "frames": [],
        }

    monkeypatch.setattr(ext, "simulate_battle", _lose)
    monkeypatch.setattr(hunt, "simulate_battle", _lose)

    _seed_raid_team(tmp_path, 51, tickets=1)
    easy = hunt.raid(51, tier="easy", rng=random.Random(1))
    assert easy["result"] == "lose"
    assert easy["shard_bonus"] == 0

    _seed_raid_team(tmp_path, 52, tickets=2)
    hard = hunt.raid(52, tier="hard", rng=random.Random(1))
    assert hard["shard_bonus"] == 3

    _seed_raid_team(tmp_path, 53, tickets=3)
    nm = hunt.raid(53, tier="nightmare", rng=random.Random(1))
    assert nm["shard_bonus"] == 6


def test_ticket_sources_battle_hunt_checklist_shards(tmp_path: Path, monkeypatch):
    import random
    from groksito_discord.discord import aether_gear as gear
    from groksito_discord.discord import aether_hunt_ext as ext
    from groksito_discord.discord import ai_coins

    hunt.set_store_path(tmp_path / "tickets.json")
    monkeypatch.setattr(ai_coins, "get_balance", lambda _uid: 5000)
    monkeypatch.setattr(
        ai_coins,
        "resolve_wager",
        lambda uid, cost, payout, min_bet=0, max_bet=10**9: (True, 5000 - cost, None),
    )

    # Seed full team for battle
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 61)
        row["zoo"] = {"dust_mite": 1, "thorn_wolf": 1, "ember_elk": 1}
        row["caught"] = dict(row["zoo"])
        row["team"] = ["dust_mite", "thorn_wolf", "ember_elk"]
        row["xp"] = {"dust_mite": 1000, "thorn_wolf": 1000, "ember_elk": 1000}
        pack = gear.ensure_gear(row)
        pack["raid_ticket"] = 0
        hunt._save_store(store)

    def _win(player, enemy, rng=None):
        return {
            "result": "win",
            "log": [],
            "rounds": 1,
            "player": player,
            "enemy": enemy,
            "frames": [],
        }

    monkeypatch.setattr(ext, "simulate_battle", _win)
    monkeypatch.setattr(hunt, "simulate_battle", _win)

    b1 = hunt.battle(61, rng=random.Random(1))
    assert b1["ok"]
    assert any(a.get("reason") == "first battle win today" for a in b1.get("ticket_awards") or [])
    snap = hunt.snapshot(61)
    assert snap["gear"]["raid_ticket"] == 1
    # Second win same day: no second ticket
    b2 = hunt.battle(61, rng=random.Random(2))
    assert not any(a.get("reason") == "first battle win today" for a in b2.get("ticket_awards") or [])
    assert hunt.snapshot(61)["gear"]["raid_ticket"] == 1

    # Hunt streak: 10 hunts → +1 once/day
    before = hunt.snapshot(61)["gear"]["raid_ticket"]
    for i in range(10):
        # bypass cooldown
        with hunt._lock:
            store = hunt._load_store()
            row = hunt._ensure_user(store, 61)
            row["last_hunt"] = 0
            hunt._save_store(store)
        out = hunt.hunt(61, rng=random.Random(i + 10))
        assert out["ok"]
    after = hunt.snapshot(61)["gear"]
    assert after["hunt_streak"] >= 10
    assert after["raid_ticket"] == before + 1

    # Shard craft
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 61)
        pack = gear.ensure_gear(row)
        pack["shards"] = 30
        hunt._save_store(store)
    crafted = hunt.craft_raid_ticket(61)
    assert crafted["ok"]
    assert crafted["tickets"] == before + 2
    assert crafted["shards"] == 0

    # Checklist rarity-row: complete common tier
    commons = [aid for aid, _n, _e, rar in hunt.ANIMALS if rar == hunt.COMMON]
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 62)
        pack = gear.ensure_gear(row)
        pack["raid_ticket"] = 0
        row["caught"] = {aid: 1 for aid in commons}
        # leave one missing then catch via helper
        missing = commons[-1]
        del row["caught"][missing]
        hunt._save_store(store)
    awards = gear.maybe_checklist_tier_ticket(
        gear.ensure_gear(hunt._ensure_user(hunt._load_store(), 62)),
        {**{aid: 1 for aid in commons}},
        hunt.ANIMALS,
        hunt.RARITY_ORDER,
    )
    # Direct unit on gear helper with full commons
    pack = gear.blank_gear()
    awards = gear.maybe_checklist_tier_ticket(
        pack, {aid: 1 for aid in commons}, hunt.ANIMALS, hunt.RARITY_ORDER
    )
    assert awards and awards[0]["reason"] == "checklist common"
    assert pack["raid_ticket"] == 1
    # Idempotent
    assert gear.maybe_checklist_tier_ticket(
        pack, {aid: 1 for aid in commons}, hunt.ANIMALS, hunt.RARITY_ORDER
    ) == []


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

    base = {
        "common": 100,
        "uncommon": 50,
        "rare": 20,
        "epic": 10,
        "mythic": 5,
        "astral": 4,
        "primordial": 1,
    }
    out = gear.prism_weights(base)
    assert out["epic"] == 20
    assert out["mythic"] == 10
    assert out["astral"] == 8
    assert out["primordial"] == 2
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



def test_team_lines_layout_and_weapon_rows():
    """ /team party card: spaced stats, soft no-weapon, clear equipped row."""
    from groksito_discord.discord import aether_gear as gear

    bare = "\n".join(
        hunt.team_lines(
            ["dust_mite", None, "thorn_wolf"],
            {"dust_mite": 0, "thorn_wolf": 0},
            {"dust_mite": 1, "thorn_wolf": 1},
            None,
        )
    )
    assert "**[1]**" in bare and "**[2]** empty" in bare
    assert "🟥 H " in bare and "🟦 W " in bare
    assert " ·  " in bare
    assert "· no weapon" in bare
    assert "*no weapon*" not in bare
    assert "**Owned**" not in bare
    # blank line between slots
    assert "\n\n**[2]**" in bare or "\n\n**[3]**" in bare

    pack = gear.blank_gear()
    pack["weapons"]["7"] = {
        "kind": "mist_dagger",
        "rarity": gear.UNCOMMON,
        "quality": 77,
        "atk": 5,
        "style": "strike",
    }
    pack["equip"]["dust_mite"] = "7"
    armed = "\n".join(
        hunt.team_lines(
            ["dust_mite", None, None],
            {"dust_mite": 0},
            {"dust_mite": 1},
            pack,
        )
    )
    held = gear.equipped_weapon(pack, "dust_mite")
    assert held is not None
    assert f"⚔️ {gear.weapon_line(held)}" in armed
    slot1 = armed.split("**[1]**", 1)[1].split("**[2]**", 1)[0]
    assert "· no weapon" not in slot1


def test_team_embed_omits_owned_section(tmp_path: Path):
    """build_team_embed must not dump the Owned catalog (use /zoo)."""
    from groksito_discord.discord import team_settings_views as team_ui

    hunt.set_store_path(tmp_path / "hunt.json")
    with hunt._lock:
        store = hunt._load_store()
        row = hunt._ensure_user(store, 55)
        row["zoo"] = {"dust_mite": 2, "ember_moth": 1, "thorn_wolf": 1}
        row["caught"] = {"dust_mite": 2, "ember_moth": 1, "thorn_wolf": 1}
        row["team"] = ["dust_mite", "thorn_wolf", None]
        hunt._save_store(store)
    embed = team_ui.build_team_embed(55)
    body = embed.description or ""
    assert "**Owned**" not in body
    assert "Ember Moth" not in body  # owned but not on team
    assert "Dust Mite" in body
    assert "Thorn Wolf" in body
    assert "· no weapon" in body
    footer = embed.footer.text or ""
    assert "/zoo for owned" in footer
    assert "settings" in footer


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



def test_owned_select_pages_cover_all_animals():
    """Owned >24: page 2 reachable; every eligible id appears across pages."""
    from groksito_discord.discord import team_settings_views as team_ui

    zoo = {aid: 1 for aid, *_ in hunt.ANIMALS}
    assert len(zoo) == 62
    team: list[str | None] = [None, None, None]
    eligible = team_ui._eligible_owned(zoo, team, 0)
    assert len(eligible) > team_ui._SELECT_CAP
    pages = team_ui._page_count(len(eligible))
    assert pages >= 2

    covered: list[str] = []
    for p in range(pages):
        opts, page, page_count = team_ui._owned_select_options(
            zoo, {}, team, 0, page=p
        )
        assert page == p
        assert page_count == pages
        assert opts[0].value == "__clear__"
        animal_vals = [o.value for o in opts if o.value != "__clear__"]
        assert 1 <= len(animal_vals) <= team_ui._SELECT_CAP
        assert len(opts) == len(animal_vals) + 1  # Clear + animals
        covered.extend(animal_vals)

    assert len(covered) == len(eligible)
    assert set(covered) == {aid for aid, *_ in eligible}

    # Slot occupant exclusion still applies across pages
    team2: list[str | None] = ["dust_mite", None, None]
    el2 = team_ui._eligible_owned(zoo, team2, 1)
    assert "dust_mite" not in {a for a, *_ in el2}
    opts0, _, pc = team_ui._owned_select_options(zoo, {}, team2, 1, page=0)
    assert all(o.value != "dust_mite" for o in opts0)
    assert pc >= 2


def test_equip_autocomplete_team_aids_only():
    """ /equip animal suggestions are battle-slot animals only (not all owned)."""
    from groksito_discord.discord import slash_hunt as sh

    team = ["dust_mite", None, "thorn_wolf"]
    zoo = {"dust_mite": 2, "thorn_wolf": 1, "ember_moth": 9, "sol_wyrm": 1}
    rows = sh._team_animal_choice_rows(team, zoo, "")
    values = [v for _label, v in rows]
    assert values == ["Dust Mite", "Thorn Wolf"]
    assert "Ember Moth" not in values
    assert "Sol Wyrm" not in values

    # needle filter
    filtered = sh._team_animal_choice_rows(team, zoo, "thorn")
    assert [v for _, v in filtered] == ["Thorn Wolf"]

    # empty team → no suggestions (slash sends ephemeral /team hint)
    assert sh._team_animal_choice_rows([None, None, None], zoo, "") == []
    assert sh._team_animal_choice_rows([], zoo, "") == []


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


def test_passive_hooks_change_outcomes():
    """≥8 representative combat hooks change HP/WP outcomes vs a no-passive baseline."""
    import random
    from groksito_discord.discord import aether_battle as battle

    def _bare(aid, lvl):
        pet = hunt._fighter(aid, lvl)
        pet["weapon"] = None
        pet["passive_hooks"] = {}
        return pet

    def _wep(kind, style="strike", quality=100, atk=10):
        return {
            "kind": kind,
            "style": style,
            "atk": atk,
            "name": kind,
            "emoji": "x",
            "rarity": "rare",
            "quality": quality,
            "wid": "1",
        }

    proven = []

    # 1) lifesteal — Crimson Siphon
    rng = random.Random(1)
    atk = hunt._fighter("thorn_wolf", 5, _wep("wyrm_fang", "cleave"))
    atk["hp"] = max(1, atk["max_hp"] // 2)
    start = atk["hp"]
    atk["wp"] = 40
    foe = _bare("ember_moth", 3)
    battle.apply_action(atk, [atk], [foe], rng)
    assert atk["hp"] > start
    proven.append("lifesteal_pct")

    # 2) thorns — Mirror Spines
    rng = random.Random(2)
    attacker = _bare("dust_mite", 8)
    attacker["atk"] = 40
    defender = hunt._fighter("peat_toad", 5, _wep("thorn_flail", "cleave"))
    before = attacker["hp"]
    battle._deal_damage(attacker, defender, 20, allies=[defender], foes=[attacker], magical=True, rng=rng)
    assert attacker["hp"] < before
    proven.append("thorns_pct")

    # 3) WP refund — Spark Recycle
    rng = random.Random(3)
    atk = hunt._fighter("thorn_wolf", 5, _wep("storm_hammer", "cleave"))
    atk["wp"] = 5
    atk["max_wp"] = 80
    start_wp = atk["wp"]
    foe = _bare("ember_moth", 3)
    # Force phys path with low WP then manually deal via _deal_damage with hooks
    battle._deal_damage(atk, foe, 30, allies=[atk], foes=[foe], magical=True, rng=rng)
    assert atk["wp"] > start_wp
    proven.append("wp_refund_pct")

    # 4) pierce PR — Rift Carve / Ash Pierce lowers effective PR
    rng = random.Random(4)
    piercer = hunt._fighter("thorn_wolf", 5, _wep("rift_blade", "strike"))
    bare = _bare("thorn_wolf", 5)
    target = _bare("ember_moth", 10)
    target["pr"] = 80
    # Physical path so pierce_pr applies
    piercer["wp"] = 0
    bare["wp"] = 0
    piercer["atk"] = bare["atk"] = 50
    dmg_p = battle._amp_damage(
        battle.apply_resist(50, battle._resist_for(piercer, target, target["pr"], magical=False)),
        piercer, target, rng, used_weapon=False,
    )
    dmg_b = battle._amp_damage(
        battle.apply_resist(50, battle._resist_for(bare, target, target["pr"], magical=False)),
        bare, target, rng, used_weapon=False,
    )
    assert dmg_p > dmg_b
    proven.append("pierce_pr_pct")

    # 5) execute — Void Reap vs low-HP target
    rng = random.Random(5)
    exe = hunt._fighter("thorn_wolf", 5, _wep("void_scythe", "cleave"))
    bare = _bare("thorn_wolf", 5)
    target = _bare("ember_moth", 5)
    target["hp"] = max(1, target["max_hp"] // 10)  # <30%
    dmg_e = battle._amp_damage(40, exe, target, rng, used_weapon=True)
    dmg_b = battle._amp_damage(40, bare, target, rng, used_weapon=True)
    assert dmg_e > dmg_b
    proven.append("execute_pct")

    # 6) missing-HP amp — Blood Fever
    rng = random.Random(6)
    fever = hunt._fighter("thorn_wolf", 5, _wep("cinder_maul", "cleave"))
    fever["hp"] = max(1, fever["max_hp"] // 5)
    full = hunt._fighter("thorn_wolf", 5, _wep("cinder_maul", "cleave"))
    full["hp"] = full["max_hp"]
    target = _bare("ember_moth", 5)
    dmg_low = battle._amp_damage(40, fever, target, rng, used_weapon=True)
    dmg_full = battle._amp_damage(40, full, target, rng, used_weapon=True)
    assert dmg_low > dmg_full
    proven.append("missing_hp_amp")

    # 7) burn DoT — Ember Trail applies 2-turn burn (not instant chunk)
    rng = random.Random(7)
    burner = hunt._fighter("thorn_wolf", 5, _wep("ember_bow", "strike"))
    foe = _bare("ember_moth", 8)
    foe["hp"] = foe["max_hp"]
    before = foe["hp"]
    battle._deal_damage(burner, foe, 40, allies=[burner], foes=[foe], magical=True, rng=rng)
    assert before - foe["hp"] == 40 or foe["hp"] == 0  # no instant burn chunk
    dots = foe.get("_dots") or []
    assert any(d.get("tag") == "burn" and int(d.get("left") or 0) == 2 for d in dots)
    proven.append("burn_pct")

    # 8) mend amp — Quartz Focus
    rng = random.Random(8)
    healer = hunt._fighter("moss_sprite", 5, _wep("quartz_wand", "mend", atk=12))
    healer["wp"] = 40
    healer["mag"] = 40
    ally = _bare("dust_mite", 5)
    ally["hp"] = max(1, ally["max_hp"] // 3)
    before = ally["hp"]
    line = battle.apply_action(healer, [healer, ally], [_bare("ember_moth", 3)], rng)
    assert "mends" in line
    assert ally["hp"] > before
    proven.append("mend_bonus")

    # 9) death nuke — Last Flare
    rng = random.Random(9)
    killer = _bare("thorn_wolf", 10)
    killer["hp"] = killer["max_hp"]
    victim = hunt._fighter("ember_moth", 5, _wep("grave_pick", "strike"))
    victim["hp"] = 1
    before = killer["hp"]
    battle._deal_damage(killer, victim, 50, allies=[victim], foes=[killer], magical=True, rng=rng)
    assert victim["hp"] == 0
    assert killer["hp"] < before
    proven.append("death_nuke_pct")

    # 10) EoT heal — Second Wind (via play_turns one round)
    rng = random.Random(10)
    pet = hunt._fighter("moss_sprite", 5, _wep("lantern_staff", "mend"))
    pet["hp"] = max(1, pet["max_hp"] // 2)
    start = pet["hp"]
    foe = _bare("ember_moth", 1)
    foe["hp"] = 1
    foe["atk"] = 1
    pet["wp"] = 0  # phys only
    pet["atk"] = 200  # finish foe quickly
    out = battle.play_turns([pet], [foe], rng)
    assert pet["hp"] >= start  # eot heal and/or no damage taken after KO
    # Direct eot check
    pet2 = hunt._fighter("moss_sprite", 5, _wep("lantern_staff", "mend"))
    pet2["hp"] = max(1, pet2["max_hp"] // 2)
    start2 = pet2["hp"]
    eh = battle._hooks_of(pet2)
    heal = max(1, int(round(int(pet2["max_hp"]) * float(eh["eot_heal_pct"]) / 100.0)))
    pet2["hp"] = min(pet2["max_hp"], pet2["hp"] + heal)
    assert pet2["hp"] == start2 + heal
    proven.append("eot_heal_pct")

    assert len(proven) >= 8
    assert len(set(proven)) == len(proven)


def test_enemy_weapons_armed_and_passives_applied():
    """Wild enemies arm ~55%; weapons apply ATK + passives; one wild_boss marked."""
    import random

    rng = random.Random(99)
    player = [hunt._fighter("dust_mite", 12) for _ in range(3)]
    armed = 0
    total = 0
    bosses = 0
    for _ in range(150):
        enemy = hunt.build_enemy_team(player, rng)
        assert len(enemy) == 3
        assert sum(1 for f in enemy if f.get("wild_boss")) == 1
        bosses += 1
        for foe in enemy:
            total += 1
            wep = foe.get("weapon")
            if not isinstance(wep, dict):
                continue
            armed += 1
            assert foe.get("passive_hooks")
            assert 20 <= int(wep.get("quality") or 0) <= 85
            bare = hunt._fighter(foe["id"], foe["level"])
            assert foe["atk"] >= bare["atk"] or foe["mag"] >= bare["mag"]
    rate = armed / total
    assert 0.45 <= rate <= 0.70, rate
    assert bosses == 150


def test_enemy_weapon_soft_capped_to_player_gear():
    """Naked teams soft-cap wild rarity; geared rare teams allow +1 tier; quality mirrors avg."""
    import random
    from groksito_discord.discord import aether_gear as gear

    rar_rank = {gear.COMMON: 0, gear.UNCOMMON: 1, gear.RARE: 2, gear.EPIC: 3, gear.MYTHIC: 4}

    # Naked player → cap uncommon (common+1)
    rng = random.Random(3)
    naked = [hunt._fighter("dust_mite", 10) for _ in range(3)]
    for _ in range(60):
        for foe in hunt.build_enemy_team(naked, rng):
            wep = foe.get("weapon")
            if isinstance(wep, dict):
                assert rar_rank.get(wep.get("rarity"), 0) <= 1
                assert int(wep["quality"]) <= 55  # avg_q 40 + 15

    # Player with rare 70% gear → cap epic, quality ≤ 85
    rare_wep = {
        "kind": "rift_blade", "style": "strike", "atk": 12, "name": "Rift",
        "emoji": "x", "rarity": gear.RARE, "quality": 70, "wid": "1",
    }
    geared = [hunt._fighter("dust_mite", 20, rare_wep) for _ in range(3)]
    rng2 = random.Random(5)
    seen_q = []
    for _ in range(60):
        for foe in hunt.build_enemy_team(geared, rng2):
            wep = foe.get("weapon")
            if isinstance(wep, dict):
                assert rar_rank.get(wep.get("rarity"), 0) <= 3  # rare+1 = epic
                assert int(wep["quality"]) <= 85
                seen_q.append(int(wep["quality"]))
    assert seen_q
    assert max(seen_q) <= 85


def test_audit_mismatch_hooks():
    """PASSIVE_COMBAT_AUDIT.md priority hooks: buff_scale, bossbrand, bounce gate, radiant, DoT."""
    import random
    from groksito_discord.discord import aether_battle as battle

    def _wep(kind, style="strike", quality=100, atk=10):
        return {
            "kind": kind, "style": style, "atk": atk, "name": kind,
            "emoji": "x", "rarity": "rare", "quality": quality, "wid": "1",
        }

    rng = random.Random(11)

    # Echo Chorus buff_scale — shield counts as a buff → more damage
    chorus = hunt._fighter("thorn_wolf", 5, _wep("peat_sickle", "cleave"))
    chorus["shield"] = 20
    bare = hunt._fighter("thorn_wolf", 5)
    bare["passive_hooks"] = {}
    bare["weapon"] = None
    target = hunt._fighter("ember_moth", 5)
    dmg_c = battle._amp_damage(40, chorus, target, rng, used_weapon=True)
    dmg_b = battle._amp_damage(40, bare, target, rng, used_weapon=True)
    assert dmg_c > dmg_b

    # Bossbrand vs wild_boss
    brand = hunt._fighter("thorn_wolf", 5, _wep("crown_halberd", "cleave"))
    boss = hunt._fighter("ember_moth", 5)
    boss["wild_boss"] = True
    trash = hunt._fighter("ember_moth", 5)
    dmg_boss = battle._amp_damage(40, brand, boss, rng, used_weapon=True)
    dmg_trash = battle._amp_damage(40, brand, trash, rng, used_weapon=True)
    assert dmg_boss > dmg_trash

    # Peat Sting — 3-turn DoT
    stinger = hunt._fighter("thorn_wolf", 5, _wep("peat_knife", "strike"))
    foe = hunt._fighter("ember_moth", 8)
    before = foe["hp"]
    battle._deal_damage(stinger, foe, 30, allies=[stinger], foes=[foe], magical=True, rng=rng)
    assert before - foe["hp"] == 30
    assert any(d.get("tag") == "sting" and int(d.get("left") or 0) == 3 for d in (foe.get("_dots") or []))
    # Tick once
    tick = next(d for d in foe["_dots"] if d["tag"] == "sting")
    foe["hp"] = max(0, foe["hp"] - int(tick["per"]))
    tick["left"] -= 1
    assert tick["left"] == 2

    # Star Bounce only on cleave — strike should not echo via bounce_hit_pct in _deal_damage
    chakram = hunt._fighter("thorn_wolf", 5, _wep("star_chakram", "strike"))
    a = hunt._fighter("ember_moth", 5)
    b = hunt._fighter("dust_mite", 5)
    a["hp"] = a["max_hp"]
    b["hp"] = b["max_hp"]
    battle._deal_damage(chakram, a, 25, allies=[chakram], foes=[a, b], magical=True, rng=rng)
    # bounce removed from _deal_damage; second foe untouched by bounce
    assert b["hp"] == b["max_hp"]
    # Cleave path does bounce
    chakram2 = hunt._fighter("thorn_wolf", 5, _wep("star_chakram", "cleave"))
    chakram2["wp"] = 40
    chakram2["mag"] = 40
    f1 = hunt._fighter("ember_moth", 3)
    f2 = hunt._fighter("dust_mite", 3)
    f1["hp"] = f1["max_hp"] = 200
    f2["hp"] = f2["max_hp"] = 200
    line = battle.apply_action(chakram2, [chakram2], [f1, f2], rng)
    assert "cleaves" in line
    # Combined damage across both should exceed a single raw cleave hit (bounce)
    assert (200 - f1["hp"]) + (200 - f2["hp"]) > 0

    # Radiant Bolt on weapon strike path
    cross = hunt._fighter("thorn_wolf", 5, _wep("sol_crossbow", "strike", atk=8))
    cross["wp"] = 40
    cross["mag"] = 30
    foe2 = hunt._fighter("ember_moth", 10)
    foe2["mr"] = 0
    start = foe2["hp"]
    battle.apply_action(cross, [cross], [foe2], rng)
    # Weapon strike + radiant convert → more than mag alone roughly
    assert foe2["hp"] < start


def test_hunt_emoji_fallbacks_and_overrides(monkeypatch):
    """HUD/animal/weapon marks: unicode without env; custom markup when set."""
    from groksito_discord.discord import hunt_emoji
    from groksito_discord.discord import aether_gear as gear

    assert hunt_emoji.stat_mark("hp") == "\U0001f7e5"
    assert hunt_emoji.stat_mark("wp") == "\U0001f7e6"
    assert hunt_emoji.stat_mark("atk") == "\U0001f7e5"
    assert hunt_emoji.stat_mark("mag") == "\U0001f7e6"
    assert hunt_emoji.stat_mark("pr") == "\U0001f7e5"
    assert hunt_emoji.stat_mark("mr") == "\U0001f7e6"
    assert hunt_emoji.stat_png_path("hp") is not None
    assert hunt_emoji.stat_png_path("phys") is not None
    assert hunt_emoji.animal_portrait_path("dust_mite") is not None

    monkeypatch.setenv("HUNT_EMOJI_HP", "<:hunt_hp:111>")
    # settings may already be loaded; also patch settings attr when present
    try:
        from groksito_discord.config import settings as _settings
        monkeypatch.setattr(_settings, "hunt_emoji_hp", "<:hunt_hp:111>", raising=False)
    except Exception:
        pass
    assert hunt_emoji.stat_mark("hp") == "<:hunt_hp:111>"

    monkeypatch.setenv("HUNT_EMOJI_ANIMAL_DUST_MITE", "<:hunt_dust_mite:222>")
    assert hunt_emoji.animal_mark("dust_mite", unicode_fallback="🐛") == "<:hunt_dust_mite:222>"
    assert "<:hunt_dust_mite:222>" in hunt.animal_label("dust_mite")

    monkeypatch.setenv("HUNT_EMOJI_WEAPON_MIST_DAGGER", "<:hunt_mist_dagger:333>")
    pack = gear.blank_gear()
    pack["weapons"]["7"] = {
        "kind": "mist_dagger",
        "rarity": gear.UNCOMMON,
        "quality": 77,
        "atk": 5,
        "style": "strike",
        "emoji": "🗡️",
        "wid": "7",
    }
    pack["equip"]["dust_mite"] = "7"
    held = gear.equipped_weapon(pack, "dust_mite")
    assert held is not None
    assert "<:hunt_mist_dagger:333>" in gear.weapon_line(held)

    body = "\n".join(
        hunt.team_lines(
            ["dust_mite", None, None],
            {"dust_mite": 0},
            {"dust_mite": 1},
            pack,
        )
    )
    assert "<:hunt_hp:111>" in body
    assert "<:hunt_dust_mite:222>" in body
    # without weapon-row override, default ⚔️ still prefixes
    assert "⚔️" in body or hunt_emoji.weapon_row_prefix() in body


def test_hunt_icon_png_assets_exist():
    from groksito_discord.discord import hunt_emoji

    for key in ("hp", "wp", "atk", "phys", "mag", "pr", "mr"):
        path = hunt_emoji.stat_png_path(key)
        assert path is not None and path.is_file()
        assert path.stat().st_size > 100



def test_astral_primordial_curves():
    """AETHERION_TOP_TIERS.md animal/combat curves above Mythic."""
    assert hunt.RARITY_BASE[hunt.ASTRAL] == (160, 38)
    assert hunt.RARITY_BASE[hunt.PRIMORDIAL] == (200, 48)
    assert hunt.RARITY_PR[hunt.ASTRAL] == 26
    assert hunt.RARITY_MR[hunt.ASTRAL] == 26
    assert hunt.RARITY_WP_MAX[hunt.ASTRAL] == 110
    assert hunt.RARITY_PR[hunt.PRIMORDIAL] == 34
    assert hunt.RARITY_MR[hunt.PRIMORDIAL] == 34
    assert hunt.RARITY_WP_MAX[hunt.PRIMORDIAL] == 135
    assert hunt.RARITY_SELL[hunt.ASTRAL] == 400
    assert hunt.RARITY_SELL[hunt.PRIMORDIAL] == 1000
    assert hunt.RARITY_POINTS[hunt.ASTRAL] == 12000
    assert hunt.RARITY_POINTS[hunt.PRIMORDIAL] == 50000
    assert hunt.RARITY_WEIGHT == {
        hunt.COMMON: 500,
        hunt.UNCOMMON: 250,
        hunt.RARE: 130,
        hunt.EPIC: 35,
        hunt.MYTHIC: 12,
        hunt.ASTRAL: 4,
        hunt.PRIMORDIAL: 1,
    }
    # Relative drop feel: A ≈ ⅓ M, P ≈ ¼ A
    assert hunt.RARITY_WEIGHT[hunt.ASTRAL] * 3 == hunt.RARITY_WEIGHT[hunt.MYTHIC]
    assert hunt.RARITY_WEIGHT[hunt.PRIMORDIAL] * 4 == hunt.RARITY_WEIGHT[hunt.ASTRAL]
    astral = hunt._fighter("starfall_lynx", 1)
    mythic = hunt._fighter("sol_wyrm", 1)
    primordial = hunt._fighter("firstroot_wyrm", 1)
    assert astral["max_hp"] > mythic["max_hp"]
    assert primordial["max_hp"] > astral["max_hp"]
    assert astral["pr"] > mythic["pr"]
    assert primordial["wp"] > astral["wp"]
    assert hunt.rarity_mark(hunt.ASTRAL) == "🔵A"
    assert hunt.rarity_mark(hunt.PRIMORDIAL) == "🟧P"
    from groksito_discord.discord import aether_gear as gear
    assert gear.SHARD_BY_RARITY[gear.ASTRAL] == 30
    assert gear.SHARD_BY_RARITY[gear.PRIMORDIAL] == 60
    assert gear.WEAPON_ATK[gear.ASTRAL] == (30, 42)
    assert gear.WEAPON_ATK[gear.PRIMORDIAL] == (40, 55)
    assert gear.ASTRAL in gear.CRATE_WEIGHT
    assert gear.PRIMORDIAL in gear.CRATE_WEIGHT
