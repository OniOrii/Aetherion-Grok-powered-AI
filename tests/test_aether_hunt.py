from pathlib import Path

from groksito_discord.discord import aether_hunt as hunt
from groksito_discord.discord import aether_hunt_ext  # noqa: F401
from groksito_discord.llm.persona import CREATOR_DISCORD_ID, creator_is_author


def test_catalog_has_original_animals():
    assert len(hunt.ANIMALS) == 46
    assert len(hunt.ANIMAL_BY_ID) == 46
    ids = [row[0] for row in hunt.ANIMALS]
    assert len(set(ids)) == 46
    assert "cowoncy" not in " ".join(ids)
    assert hunt.resolve_animal("Sol Wyrm") == "sol_wyrm"
    assert hunt.resolve_animal("aether drake") == "aether_drake"
    assert hunt.resolve_animal("Aether Phoenix") == "aether_phoenix"
    assert hunt.resolve_animal("mist vole") == "mist_vole"
    assert hunt.resolve_animal("nope") is None


def test_rarity_roll_stays_in_catalog(tmp_path: Path):
    import random

    rng = random.Random(1)
    seen = {hunt.roll_animal(rng) for _ in range(200)}
    assert seen <= set(hunt.ANIMAL_BY_ID)
    assert any(hunt.rarity_of(aid) == hunt.COMMON for aid in seen)


def test_level_and_stats_scale():
    assert hunt.level_of(0) == 1
    assert hunt.level_of(25) == 2
    assert hunt.level_of(10_000) == hunt.LEVEL_CAP
    hp1, atk1 = hunt.stats_for("dust_mite", 1)
    hp5, atk5 = hunt.stats_for("dust_mite", 5)
    assert hp5 > hp1
    assert atk5 > atk1


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
    assert second["lootbox"] == 0
    assert second["crate"] == 0
    snap = hunt.snapshot(7)
    assert snap["gear"]["lootbox"] == 5


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
    assert "Discovered __2__ / 46" in board
    assert "cowoncy" not in board.lower()
    assert hunt.rarity_mark(hunt.COMMON) in board
    assert hunt.rarity_mark(hunt.EPIC) in board
    # No legacy backtick letter marks
    assert "`c`" not in board
    assert "`e`" not in board
