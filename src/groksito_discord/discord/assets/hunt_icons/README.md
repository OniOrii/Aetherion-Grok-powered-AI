# Aetherion Hunt icons (custom Discord emojis)

Original Aetherion HUD tiles + pointers to animal portraits. Discord cannot
inline arbitrary PNGs in message text, so `/team` (and related lines) use:

1. Configured custom emoji markup from env (`HUNT_EMOJI_*`), or
2. Unicode fallbacks (colored squares / species glyphs) until Ori uploads.

Upload is **optional**. Empty env keys keep unicode fallbacks; tests never
require Discord.

## What lives here

| File | Role | Suggested Discord name |
|------|------|------------------------|
| `hp.png` | HP | `hunt_hp` |
| `wp.png` | WP | `hunt_wp` |
| `atk.png` / `phys.png` | Physical ATK | `hunt_atk` |
| `mag.png` | MAG | `hunt_mag` |
| `pr.png` | Physical resist | `hunt_pr` |
| `mr.png` | Magic resist | `hunt_mr` |

Sizes are **96×96** RGBA (fine for Discord app/server emoji; 64–128px range).

## Animals (reuse portraits — do not duplicate)

Species avatars already ship under `../hunt_portraits/{animal_id}.png`
(50 originals, 128×128). Upload those as emojis (suggested name
`hunt_{animal_id}`, e.g. `hunt_dust_mite`), then set:

```env
HUNT_EMOJI_ANIMAL_DUST_MITE=<:hunt_dust_mite:123456789012345678>
```

Leave blank to keep the unicode glyph from the animal catalog.

## Weapons (optional overrides)

Weapon icons are painted at runtime (`weapon_art.py`). To swap the glyph on
`/team` weapon rows / lists, export a small PNG (or screenshot the crate
reveal), upload it, and set:

```env
HUNT_EMOJI_WEAPON_MIST_DAGGER=<:hunt_mist_dagger:123456789012345678>
HUNT_EMOJI_WEAPON_ROW=<:hunt_sword:123456789012345678>   # optional /team row prefix (default ⚔️)
```

## How Ori uploads & wires IDs

1. Open Discord → **Server Settings → Emoji** (or the bot application’s emoji
   page) → upload the PNGs above (and portraits you want).
2. Right-click an emoji in chat (or use a picker that shows IDs) and copy the
   full markup `<:name:id>` (animated uses `<a:name:id>`).
3. Paste into `.env` (see repo root `.env.example`):

```env
HUNT_EMOJI_HP=<:hunt_hp:123456789012345678>
HUNT_EMOJI_WP=<:hunt_wp:123456789012345678>
HUNT_EMOJI_ATK=<:hunt_atk:123456789012345678>
HUNT_EMOJI_MAG=<:hunt_mag:123456789012345678>
HUNT_EMOJI_PR=<:hunt_pr:123456789012345678>
HUNT_EMOJI_MR=<:hunt_mr:123456789012345678>
# optional per animal / weapon:
# HUNT_EMOJI_ANIMAL_DUST_MITE=<:hunt_dust_mite:…>
# HUNT_EMOJI_WEAPON_MIST_DAGGER=<:hunt_mist_dagger:…>
```

4. Restart the bot process so settings reload.
5. `/team` stat lines and weapon rows show custom marks when set; unicode when not.

Resolver: `groksito_discord.discord.hunt_emoji` (`stat_mark`, `animal_mark`,
`weapon_mark`). Rank letter badges stay under `../hunt_ranks/` +
`HUNT_RANK_EMOJI_*`.
