from pathlib import Path

from groksito_discord.discord import aether_hunt as hunt
from groksito_discord.llm.persona import CREATOR_DISCORD_ID, creator_is_author


def test_catalog_has_thirty_original_animals():
    assert len(hunt.ANIMALS) == 30
    assert len(hunt.ANIMAL_BY_ID) == 30
    ids = [row[0] for row in hunt.ANIMALS]
    assert len(set(ids)) == 30
    assert "cowoncy" not in " ".join(ids)
    assert hunt.resolve_animal("Sol Wyrm") == "sol_wyrm"
    assert hunt.resolve_animal("aether drake") == "aether_drake"
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
    assert 1 <= len(enemy) <= 3
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
    assert "Turn 2 / 5" in card


def test_gear_catalog_has_thirty_weapons():
    from groksito_discord.discord import aether_gear as gear

    assert len(gear.WEAPONS) == 30
    assert len({row[0] for row in gear.WEAPONS}) == 30
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
    epic = hunt.hunt_catch_line("Ori", "aether_drake")
    assert "caught an **epic**" in epic
    board = hunt.zoo_board(
        "Ori",
        {"dust_mite": 2, "ember_moth": 0},
        {"dust_mite": 2},
    )
    assert "\U0001f33f \U0001f331 \U0001f333 **Ori's zoo!** \U0001f333 \U0001f331 \U0001f33f" in board
    assert "\u2753\u2080" in board
    assert "\U0001fab2\u2082" in board
    assert "**Zoo Points: __2__**" in board
    owned = hunt.owned_catalog({"dust_mite": 2, "sol_wyrm": 0})
    assert [row[0] for row in owned] == ["dust_mite"]


def test_battle_image_renders():
    from groksito_discord.discord import aether_battle as board

    player = [hunt._fighter("eclipse_lion", 19)]
    enemy = [hunt._fighter("ember_moth", 12)]
    png = board.render_battle_png(player, enemy, turn=2, max_turns=5)
    raw = png.getvalue()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 800
