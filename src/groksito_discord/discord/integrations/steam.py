"""Removed. Steam slash commands are gone. Stub kept so old imports cannot crash a deploy mid-rollout."""

async def warmup_steam_app_list(*_a, **_k):
    return None

async def get_steam_game_data(*_a, **_k):
    return []

async def get_top_steam_games(*_a, **_k):
    return []

def get_game_color(*_a, **_k):
    return 0x2B2D31

def stmchr_game_names_csv():
    return ""

def stmchr_preresolved_map():
    return {}

def normalize_game_name_for_lookup(name):
    return name or ""

_STMCHR_GAMES = []
