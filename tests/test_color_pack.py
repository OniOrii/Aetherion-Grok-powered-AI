from groksito_discord.discord.color_pack import GRADIENT_COLOR_PACK, pack_names


def test_pack_has_unique_names_and_emojis():
    names = [name for _e, name, _p, _s in GRADIENT_COLOR_PACK]
    emojis = [emoji for emoji, _n, _p, _s in GRADIENT_COLOR_PACK]
    assert len(names) == len(set(names))
    assert len(emojis) == len(set(emojis))
    assert pack_names() == names
    assert len(GRADIENT_COLOR_PACK) >= 8


def test_pack_hex_looks_valid():
    for emoji, name, primary, secondary in GRADIENT_COLOR_PACK:
        assert primary.startswith("#") and len(primary) == 7
        assert secondary.startswith("#") and len(secondary) == 7
        assert emoji
        assert name
