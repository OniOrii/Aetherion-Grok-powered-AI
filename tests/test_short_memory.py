from groksito_discord.context.short_memory import (
    clear,
    format_block,
    mentions_aetherion,
    record_turn,
)


def setup_function():
    clear()


def test_name_detects_aetherion_and_typos():
    assert mentions_aetherion("Aetherion what time is it")
    assert mentions_aetherion("hey ethereon")
    assert mentions_aetherion("ping Groksito")
    assert mentions_aetherion("Aetheron play that song")
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
    assert "Last conversations with this user" in block


def test_text_and_voice_share_the_same_buffer():
    uid = 777
    record_turn(uid, "play that song later", "say the word", source="text")
    record_turn(uid, "what song did I mention", "the one from earlier", source="voice")
    block = format_block(uid)
    assert "User (text): play that song later" in block
    assert "User (voice): what song did I mention" in block
