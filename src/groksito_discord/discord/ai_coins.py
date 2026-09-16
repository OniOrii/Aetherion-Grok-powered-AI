"""Persistent play-money Aether Coin ledger for Aetherion minigames.

Stored under data/ai_coins.json (gitignored runtime data, same folder as
welcome channels and reaction roles). Play-money only — no cash-out, no
transfers, no real-world value.

First seen user id starts at STARTING_BALANCE. Daily drip is claimed on
Eastern calendar date so it matches the date dock. Aetherion keeps a house
wallet (HOUSE_ID) that wins and loses against players.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings

logger = logging.getLogger("aetherion.ai_coins")

EASTERN = ZoneInfo("America/Detroit")
STARTING_BALANCE = 5000
DAILY_DRIP = 2000
STEP = 10
MIN_BET = 10
DEFAULT_BET = 10
MAX_BET = 1000
MIN_GRANT = 10
MAX_GRANT = 10000
CURRENCY = "Aether Coins"
CURRENCY_ONE = "Aether Coin"
SYMBOL = "\u2726"
HOUSE_ID = 0
HOUSE_NAME = "Aetherion"
HOUSE_START = 1_000_000


def coins(amount: int | str) -> str:
    """Same mark slots uses next to an Aether Coin amount."""
    return f"{SYMBOL} {amount}"


def signed_coins(net: int) -> str:
    """+120 / -40 / 0 next to the Aether mark."""
    net = int(net)
    if net > 0:
        return coins(f"+{net:,}")
    if net < 0:
        return coins(f"-{abs(net):,}")
    return coins("0")


def won_line(net: int) -> str:
    """End-of-game payout line. Use this on every new game too."""
    net = int(net)
    if net > 0:
        return f"Won {signed_coins(net)}"
    if net < 0:
        return f"Lost {coins(f'{abs(net):,}')}"
    return "Push"


_lock = threading.Lock()


def amount_error(amount: int, min_v: int, max_v: int, word: str = "Bet") -> str:
    amount = int(amount)
    if amount % STEP:
        return f"{word}s go by {STEP}s."
    if amount < min_v:
        return f"Minimum {word.lower()} is {min_v} Aether Coins."
    if amount > max_v:
        return f"Maximum {word.lower()} is {max_v} Aether Coins."
    return ""


def _store_path() -> Path:
    base = Path(getattr(settings, "data_dir", Path("./data")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "ai_coins.json"


def _empty_store() -> dict[str, Any]:
    return {"users": {}}


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty_store()
        users = data.get("users")
        if not isinstance(users, dict):
            data["users"] = {}
        return data
    except Exception:
        logger.exception("ai_coins store read failed")
        return _empty_store()


def _save_store(data: dict[str, Any]) -> None:
    path = _store_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _today_eastern() -> str:
    return datetime.now(EASTERN).date().isoformat()


def _blank_user() -> dict[str, Any]:
    return {
        "balance": STARTING_BALANCE,
        "pending_bet": 0,
        "last_daily": None,
        "created_at": datetime.now(EASTERN).isoformat(timespec="seconds"),
    }


def _ensure_house_unlocked(store: dict[str, Any]) -> dict[str, Any]:
    users = store.setdefault("users", {})
    key = str(HOUSE_ID)
    row = users.get(key)
    if not isinstance(row, dict):
        row = {
            "balance": HOUSE_START,
            "pending_bet": 0,
            "last_daily": None,
            "created_at": datetime.now(EASTERN).isoformat(timespec="seconds"),
            "house": True,
        }
        users[key] = row
        return row
    try:
        row["balance"] = int(row.get("balance", HOUSE_START))
    except (TypeError, ValueError):
        row["balance"] = HOUSE_START
    try:
        row["pending_bet"] = int(row.get("pending_bet", 0) or 0)
    except (TypeError, ValueError):
        row["pending_bet"] = 0
    if row["balance"] < 0:
        row["balance"] = 0
    if row["pending_bet"] < 0:
        row["pending_bet"] = 0
    row["house"] = True
    return row


def _ensure_user_unlocked(store: dict[str, Any], user_id: int) -> dict[str, Any]:
    if int(user_id) == HOUSE_ID:
        return _ensure_house_unlocked(store)
    users = store.setdefault("users", {})
    key = str(user_id)
    row = users.get(key)
    if not isinstance(row, dict):
        row = _blank_user()
        users[key] = row
        return row
    try:
        row["balance"] = int(row.get("balance", STARTING_BALANCE))
    except (TypeError, ValueError):
        row["balance"] = STARTING_BALANCE
    try:
        row["pending_bet"] = int(row.get("pending_bet", 0) or 0)
    except (TypeError, ValueError):
        row["pending_bet"] = 0
    if row["balance"] < 0:
        row["balance"] = 0
    if row["pending_bet"] < 0:
        row["pending_bet"] = 0
    return row


def _touch_house(store: dict[str, Any], delta: int) -> int:
    house = _ensure_house_unlocked(store)
    house["balance"] = max(0, int(house["balance"]) + int(delta))
    return int(house["balance"])


def refund_stale_pending(user_id: int) -> int:
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        held = int(row.get("pending_bet") or 0)
        if held <= 0:
            _ensure_house_unlocked(store)
            _save_store(store)
            return 0
        row["balance"] = int(row["balance"]) + held
        row["pending_bet"] = 0
        _save_store(store)
        logger.info("refunded stale pending bet user=%s amount=%s", user_id, held)
        return held


def get_balance(user_id: int) -> int:
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        _ensure_house_unlocked(store)
        _save_store(store)
        return int(row["balance"])


def claim_daily(user_id: int) -> tuple[int, int, bool]:
    if int(user_id) == HOUSE_ID:
        return get_balance(user_id), 0, True
    today = _today_eastern()
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        _ensure_house_unlocked(store)
        if row.get("last_daily") == today:
            _save_store(store)
            return int(row["balance"]), 0, True
        row["balance"] = int(row["balance"]) + DAILY_DRIP
        row["last_daily"] = today
        _save_store(store)
        return int(row["balance"]), DAILY_DRIP, False


def hold_bet(user_id: int, amount: int, *, max_bet: int | None = None) -> tuple[bool, int, str]:
    amount = int(amount)
    cap = MAX_BET if max_bet is None else int(max_bet)
    err = amount_error(amount, MIN_BET, cap)
    if err:
        return False, 0, err
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        _ensure_house_unlocked(store)
        if int(row.get("pending_bet") or 0) > 0:
            return False, int(row["balance"]), "You already have a hand in progress."
        bal = int(row["balance"])
        if amount > bal:
            return False, bal, f"You only have {bal} Aether Coins."
        row["balance"] = bal - amount
        row["pending_bet"] = amount
        _save_store(store)
        return True, int(row["balance"]), ""


def add_to_pending(user_id: int, extra: int) -> tuple[bool, int, str]:
    extra = int(extra)
    if extra <= 0:
        return False, 0, "Nothing to add."
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        held = int(row.get("pending_bet") or 0)
        if held <= 0:
            return False, int(row["balance"]), "No hand in progress."
        bal = int(row["balance"])
        if extra > bal:
            return False, bal, f"You only have {bal} Aether Coins left to double."
        row["balance"] = bal - extra
        row["pending_bet"] = held + extra
        _save_store(store)
        return True, int(row["balance"]), ""


def settle_hand(user_id: int, credit: int) -> int:
    credit = max(0, int(credit))
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        held = int(row.get("pending_bet") or 0)
        row["pending_bet"] = 0
        row["balance"] = int(row["balance"]) + credit
        if int(user_id) != HOUSE_ID and held:
            _touch_house(store, held - credit)
        else:
            _ensure_house_unlocked(store)
        _save_store(store)
        return int(row["balance"])


def grant_coins(user_id: int, amount: int) -> tuple[bool, int, str]:
    amount = int(amount)
    err = amount_error(amount, MIN_GRANT, MAX_GRANT, word="Grant")
    if err:
        return False, 0, err
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        row["balance"] = int(row["balance"]) + amount
        _ensure_house_unlocked(store)
        _save_store(store)
        logger.info("granted coins user=%s amount=%s balance=%s", user_id, amount, row["balance"])
        return True, int(row["balance"]), ""


def snapshot_wallets() -> list[tuple[int, int, int]]:
    with _lock:
        store = _load_store()
        _ensure_house_unlocked(store)
        _save_store(store)
        out: list[tuple[int, int, int]] = []
        users = store.get("users") or {}
        if not isinstance(users, dict):
            return out
        for key, row in users.items():
            try:
                uid = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(row, dict):
                continue
            try:
                bal = int(row.get("balance", 0) or 0)
            except (TypeError, ValueError):
                bal = 0
            try:
                pending = int(row.get("pending_bet", 0) or 0)
            except (TypeError, ValueError):
                pending = 0
            out.append((uid, max(0, bal), max(0, pending)))
        return out


def resolve_wager(
    user_id: int,
    stake: int,
    payout: int,
    *,
    min_bet: int,
    max_bet: int,
) -> tuple[bool, int, str]:
    stake = int(stake)
    payout = max(0, int(payout))
    err = amount_error(stake, min_bet, max_bet)
    if err:
        return False, 0, err
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        if int(row.get("pending_bet") or 0) > 0:
            return False, int(row["balance"]), "You already have a hand in progress."
        bal = int(row["balance"])
        if stake > bal:
            return False, bal, f"You only have {bal} Aether Coins."
        row["balance"] = bal - stake + payout
        if int(user_id) != HOUSE_ID:
            _touch_house(store, stake - payout)
        _save_store(store)
        return True, int(row["balance"]), ""
