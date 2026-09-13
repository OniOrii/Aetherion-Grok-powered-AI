"""Persistent play-money Aether Coin ledger for Aetherion minigames.

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
STARTING_BALANCE = 500
DAILY_DRIP = 25
MIN_BET = 1
DEFAULT_BET = 10
MAX_BET = 1000
MIN_GRANT = 1
MAX_GRANT = 10000
CURRENCY = "Aether Coins"
CURRENCY_ONE = "Aether Coin"

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
    amount = int(amount)
    if amount < MIN_BET:
        return False, 0, f"Minimum bet is {MIN_BET} Aether Coin."
    if amount > MAX_BET:
        return False, 0, f"Maximum bet is {MAX_BET} Aether Coins."
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
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
        row["pending_bet"] = 0
        row["balance"] = int(row["balance"]) + credit
        _save_store(store)
        return int(row["balance"])


def grant_coins(user_id: int, amount: int) -> tuple[bool, int, str]:
    amount = int(amount)
    if amount < MIN_GRANT or amount > MAX_GRANT:
        return False, 0, f"Grant must be {MIN_GRANT}\u2013{MAX_GRANT} Aether Coins."
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        row["balance"] = int(row["balance"]) + amount
        _save_store(store)
        logger.info("granted coins user=%s amount=%s balance=%s", user_id, amount, row["balance"])
        return True, int(row["balance"]), ""


def snapshot_wallets() -> list[tuple[int, int, int]]:
    with _lock:
        store = _load_store()
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
    if stake < min_bet:
        return False, 0, f"Minimum bet is {min_bet} Aether Coins."
    if stake > max_bet:
        return False, 0, f"Maximum bet is {max_bet} Aether Coins."
    with _lock:
        store = _load_store()
        row = _ensure_user_unlocked(store, user_id)
        if int(row.get("pending_bet") or 0) > 0:
            return False, int(row["balance"]), "You already have a hand in progress."
        bal = int(row["balance"])
        if stake > bal:
            return False, bal, f"You only have {bal} Aether Coins."
        row["balance"] = bal - stake + payout
        _save_store(store)
        return True, int(row["balance"]), ""
