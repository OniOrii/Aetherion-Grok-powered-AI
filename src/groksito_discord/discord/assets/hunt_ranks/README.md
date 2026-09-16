# Aetherion Hunt rank badges

Original Aetherion C/U/R/E/M/A/P letter tiles (not OwO assets).

| File | Rank | Fill |
|------|------|------|
| `rank_c.png` | common | `#9A4442` |
| `rank_u.png` | uncommon | `#388B9A` |
| `rank_r.png` | rare | `#D4A746` |
| `rank_e.png` | epic | `#4057E1` |
| `rank_m.png` | mythic | `#9558EF` |
| `rank_a.png` | astral | `#7EC8FF` |
| `rank_p.png` | primordial | `#C45C26` |

Upload these PNGs as Discord app/guild emojis (suggested names: `aether_c`…`aether_m`, `aether_a`, `aether_p`), then set `HUNT_RANK_EMOJI_COMMON` … `HUNT_RANK_EMOJI_PRIMORDIAL` in `.env` to the full `<:name:id>` markup. Until then, `rarity_mark()` uses a unicode color-square + letter fallback.
