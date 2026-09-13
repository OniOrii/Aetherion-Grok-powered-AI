from groksito_discord.discord.slash_edit import clamp_edit_text, parse_message_ref
from groksito_discord.llm.persona import CREATOR_DISCORD_ID, creator_is_author


def test_parse_message_link():
    guild_id, channel_id, message_id = parse_message_ref(
        "https://discord.com/channels/1/2/3"
    )
    assert guild_id == 1
    assert channel_id == 2
    assert message_id == 3


def test_parse_bare_message_id():
    guild_id, channel_id, message_id = parse_message_ref("123456789012345678")
    assert guild_id is None
    assert channel_id is None
    assert message_id == 123456789012345678


def test_parse_empty_ref():
    assert parse_message_ref("") == (None, None, None)
    assert parse_message_ref("not-an-id") == (None, None, None)


def test_clamp_edit_text():
    assert clamp_edit_text("  hello  ") == "hello"
    assert len(clamp_edit_text("x" * 3000)) == 2000


def test_ori_is_still_the_only_editor():
    assert creator_is_author(CREATOR_DISCORD_ID)
    assert not creator_is_author(1)
