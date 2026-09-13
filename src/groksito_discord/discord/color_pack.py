"""Built-in two-color gradient role pack for /reactionrole colors."""
from __future__ import annotations

# emoji, role name, primary hex, secondary hex
GRADIENT_COLOR_PACK: tuple[tuple[str, str, str, str], ...] = (
    ("\U0001F305", "Sunset", "#FF6B35", "#F7C948"),
    ("\U0001F338", "Blossom", "#FF6B9D", "#C77DFF"),
    ("\U0001F30A", "Ocean", "#00B4D8", "#0077B6"),
    ("\U0001F343", "Forest", "#2ECC71", "#145A32"),
    ("\U0001F347", "Nightshade", "#7B2CBF", "#E0AAFF"),
    ("\U0001F525", "Ember", "#ED4245", "#E67E22"),
    ("\U0001F9CA", "Frost", "#7FDBFF", "#5865F2"),
    ("\U0001F36F", "Honey", "#F1C40F", "#E67E22"),
    ("\U0001FA77", "Cotton", "#FF8DC7", "#FFD6E7"),
    ("\U0001F5A4", "Void", "#23272A", "#5865F2"),
    ("\U0001F308", "Aurora", "#00F5D4", "#9B5DE5"),
    ("\U0001F48E", "Prism", "#5865F2", "#EB459E"),
)


def pack_names() -> list[str]:
    return [name for _emoji, name, _p, _s in GRADIENT_COLOR_PACK]
