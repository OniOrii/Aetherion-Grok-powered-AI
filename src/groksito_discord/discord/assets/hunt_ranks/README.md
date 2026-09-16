# Aetherion Hunt rank badges

Original Aetherion C/U/R/E/M letter tiles (not OwO assets).

| File | Rank | Fill |
|------|------|------|
| `rank_c.png` | common | `#9A4442` |
| `rank_u.png` | uncommon | `#388B9A` |
| `rank_r.png` | rare | `#D4A746` |
| `rank_e.png` | epic | `#4057E1` |
| `rank_m.png` | mythic | `#9558EF` |

Upload these five PNGs as Discord app/guild emojis (suggested names: `aether_c`, `aether_u`, `aether_r`, `aether_e`, `aether_m`), then set `HUNT_RANK_EMOJI_COMMON` … `HUNT_RANK_EMOJI_MYTHIC` in `.env` to the full `<:name:id>` markup. Until then, `rarity_mark()` uses a unicode color-square + letter fallback.
