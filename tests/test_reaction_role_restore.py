from groksito_discord.discord.reaction_roles import parse_panel_text


def test_parse_color_pack_message():
    text = (
        "React to pick a name color. One color at a time.\n"
        "\n"
        "\U0001F305 <@&111>\n"
        "\U0001F338 <@&222>\n"
    )
    mapping = parse_panel_text(text)
    assert mapping["\U0001F305"] == 111
    assert mapping["\U0001F338"] == 222


def test_parse_custom_emoji_and_embed_lines():
    body = "<:pink:999> <@&333>"
    extra = ["\U0001F525=444"]
    mapping = parse_panel_text(body, extra)
    assert mapping["pink:999"] == 333
    assert mapping["\U0001F525"] == 444
