"""Persistent play-money AI Coin ledger for Aetherion minigames.

Stored under data/ai_coins.json (gitignored runtime data, same folder as
welcome channels and reaction roles). Play-money only — no cash-out, no
transfers, no real-world value.

First seen user id starts at STARTING_BALANCE. Daily drip is claimed on
Eastern calendar date so it matches the date dock.
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
STARTING_BALANCE = 100
DAILY_DRIP = 25
MIN_BET = 1
DEFAULT_BET = 10
MAX_BET = 500

_lock = threading.Lock()


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


def _ensure_user_unlocked(store: dict[str, Any], user_id: int) -> dict[str, Any]:
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


def refund_stale_pending(user_id: int) -> int:
    """Return a held bet if the process died mid-hand. Safe to call often."""
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        held = int(row.get("pending_bet") or 0)
        if held <= 0:
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
        _save_store(store)
        return int(row["balance"])


def claim_daily(user_id: int) -> tuple[int, int, bool]:
    """Returns (balance, granted, already_claimed_today)."""
    today = _today_eastern()
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        if row.get("last_daily") == today:
            return int(row["balance"]), 0, True
        row["balance"] = int(row["balance"]) + DAILY_DRIP
        row["last_daily"] = today
        _save_store(store)
        return int(row["balance"]), DAILY_DRIP, False


def hold_bet(user_id: int, amount: int) -> tuple[bool, int, str]:
    """Take `amount` off the wallet and park it as pending_bet."""
    amount = int(amount)
    if amount < MIN_BET:
        return False, 0, f"Minimum bet is {MIN_BET} AI Coin."
    if amount > MAX_BET:
        return False, 0, f"Maximum bet is {MAX_BET} AI Coins."
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        if int(row.get("pending_bet") or 0) > 0:
            return False, int(row["balance"]), "You already have a hand in progress."
        bal = int(row["balance"])
        if amount > bal:
            return False, bal, f"You only have {bal} AI Coins."
        row["balance"] = bal - amount
        row["pending_bet"] = amount
        _save_store(store)
        return True, int(row["balance"]), ""


def add_to_pending(user_id: int, extra: int) -> tuple[bool, int, str]:
    """Double-down: pull `extra` more coins into the held bet."""
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
            return False, bal, f"You only have {bal} AI Coins left to double."
        row["balance"] = bal - extra
        row["pending_bet"] = held + extra
        _save_store(store)
        return True, int(row["balance"]), ""


def settle_hand(user_id: int, credit: int) -> int:
    """Clear pending_bet and add `credit` (0 on a loss, stake on a push, more on a win)."""
    credit = max(0, int(credit))
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        row["pending_bet"] = 0
        row["balance"] = int(row["balance"]) + credit
        _save_store(store)
        return int(row["balance"])
