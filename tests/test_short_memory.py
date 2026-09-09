from groksito_discord.context.short_memory import (
    format_block,
    mentions_aetherion,
    record_turn,
)


def test_name_detects_aetherion_and_typos():
    assert mentions_aetherion("Aetherion what time is it")
    assert mentions_aetherion("hey ethereon")
    assert mentions_aetherion("ping Groksito")
    assert not mentions_aetherion("hello world")


def test_keeps_ten_turns_and_formats():
    uid = 424242
    for i in range(12):
        record_turn(uid, f"user {i}", f"bot {i}", source="text")
    block = format_block(uid)
    assert "user 1" not in block
    assert "user 2" in block
    assert "user 11" in block
    assert "Aetherion:" in block
