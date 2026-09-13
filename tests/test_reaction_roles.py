from groksito_discord.discord.reaction_roles import (
    emoji_key_from_partial,
    parse_emoji_input,
)


class _Emoji:
    def __init__(self, name, id=None):
        self.name = name
        self.id = id


def test_parse_unicode_emoji():
    parsed = parse_emoji_input("❤️")
    assert parsed is not None
    key, value = parsed
    assert key == "❤️"
    assert value == "❤️"


def test_parse_custom_emoji_mention():
    parsed = parse_emoji_input("<:blob:123456789012345678>")
    assert parsed is not None
    key, value = parsed
    assert key == "blob:123456789012345678"
    assert getattr(value, "id") == 123456789012345678


def test_parse_custom_emoji_id_form():
    parsed = parse_emoji_input("star:99")
    assert parsed is not None
    key, _value = parsed
    assert key == "star:99"


def test_emoji_key_from_partial_unicode():
    assert emoji_key_from_partial(_Emoji("🔥")) == "🔥"


def test_emoji_key_from_partial_custom():
    assert emoji_key_from_partial(_Emoji("star", 99)) == "star:99"
