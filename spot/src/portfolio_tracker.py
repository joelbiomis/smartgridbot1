"""
portfolio_tracker.py
====================
Portfolio Profit Lock Grid Bot — Portfolio Tracker

SQLite-backed ledger that records every "profit lock cycle":
  - Which coins were traded
  - Total profit locked
  - Timestamp and cycle number

Also exposes helper queries used by the portfolio engine and alerter.
"""

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("data", "portfolio.db")

CREATE_LOCK_CYCLES_SQL = """
CREATE TABLE IF NOT EXISTS lock_cycles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    cycle_number  INTEGER NOT NULL DEFAULT 1,
    coins_traded  TEXT    NOT NULL,   -- JSON list of symbols
    total_profit  REAL    NOT NULL,
    profit_pct    REAL    NOT NULL,
    starting_capital REAL NOT NULL
);
"""

CREATE_PORTFOLIO_TRADES_SQL = """
CREATE TABLE IF NOT EXISTS portfolio_trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,
    cycle_id     INTEGER NOT NULL,
    symbol       TEXT    NOT NULL,
    side         TEXT    NOT NULL,
    price        REAL    NOT NULL,
    qty          REAL    NOT NULL,
    fee          REAL    NOT NULL DEFAULT 0.0,
    realized_pnl REAL    NOT NULL DEFAULT 0.0,
    FOREIGN KEY (cycle_id) REFERENCES lock_cycles(id)
);
"""


class PortfolioTracker:
    """
    Records profit lock cycles and individual trades to SQLite.

    Database is auto-created at *data/portfolio.db* on first use.
    """

    def __init__(self) -> None:
        os.makedirs("data", exist_ok=True)
        self._db_path   = DB_PATH
        self._cycle_num = 0
        self._init_db()
        self._cycle_num = self._get_latest_cycle_number()

    # ------------------------------------------------------------------
    # DB setup
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        try:
            with self._connect() as conn:
                conn.execute(CREATE_LOCK_CYCLES_SQL)
                conn.execute(CREATE_PORTFOLIO_TRADES_SQL)
            logger.info("PortfolioTracker: database ready at %s.", self._db_path)
        except Exception as exc:
            logger.error("PortfolioTracker: DB init failed: %s", exc)
            raise

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_latest_cycle_number(self) -> int:
        """Return the highest cycle_number stored, or 0 if table is empty."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(MAX(cycle_number), 0) AS max_cycle FROM lock_cycles"
                ).fetchone()
            return int(row["max_cycle"]) if row else 0
        except Exception as exc:
            logger.error("_get_latest_cycle_number failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def log_lock_cycle(
        self,
        coins_traded: list[str],
        total_profit: float,
        profit_pct: float,
        starting_capital: float,
    ) -> int:
        """
        Persist a completed profit-lock cycle.

        Args:
            coins_traded:      List of symbols that were in the portfolio.
            total_profit:      Net profit locked in USDT.
            profit_pct:        Profit as a fraction of starting capital.
            starting_capital:  USDT capital at cycle start.

        Returns:
            The new cycle's database row ID (used when logging per-trade details).
        """
        self._cycle_num += 1
        ts = datetime.now(timezone.utc).isoformat()
        coins_json = json.dumps(coins_traded)
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """INSERT INTO lock_cycles
                       (timestamp, cycle_number, coins_traded,
                        total_profit, profit_pct, starting_capital)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (ts, self._cycle_num, coins_json,
                     total_profit, profit_pct, starting_capital),
                )
                row_id = cursor.lastrowid
            logger.info(
                "PortfolioTracker: lock cycle #%d logged | profit=%.4f USDT (%.2f%%)",
                self._cycle_num, total_profit, profit_pct * 100,
            )
            return row_id
        except Exception as exc:
            logger.error("log_lock_cycle failed: %s", exc)
            return -1

    def log_trade(
        self,
        cycle_id: int,
        symbol: str,
        side: str,
        price: float,
        qty: float,
        fee: float,
        realized_pnl: float,
    ) -> None:
        """
        Persist a single trade associated with a lock cycle.

        Args:
            cycle_id:     Row ID from log_lock_cycle().
            symbol:       Trading pair, e.g. 'BTCUSDT'.
            side:         'BUY' or 'SELL'.
            price:        Fill price.
            qty:          Fill quantity.
            fee:          Fee paid in USDT.
            realized_pnl: Net realized PnL for this fill.
        """
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO portfolio_trades
                       (timestamp, cycle_id, symbol, side,
                        price, qty, fee, realized_pnl)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ts, cycle_id, symbol, side, price, qty, fee, realized_pnl),
                )
        except Exception as exc:
            logger.error("PortfolioTracker.log_trade failed: %s", exc)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_today_cycles(self) -> int:
        """Return the number of lock cycles completed today (UTC)."""
        today_str = date.today().isoformat()
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM lock_cycles WHERE timestamp >= ?",
                    (today_str,),
                ).fetchone()
            return int(row["cnt"]) if row else 0
        except Exception as exc:
            logger.error("get_today_cycles failed: %s", exc)
            return 0

    def get_today_profit(self) -> float:
        """Return total profit locked today (UTC) in USDT."""
        today_str = date.today().isoformat()
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(total_profit), 0.0) AS total "
                    "FROM lock_cycles WHERE timestamp >= ?",
                    (today_str,),
                ).fetchone()
            return float(row["total"]) if row else 0.0
        except Exception as exc:
            logger.error("get_today_profit failed: %s", exc)
            return 0.0

    def get_total_locked_profit(self) -> float:
        """Return cumulative profit locked across all cycles ever."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(total_profit), 0.0) AS total FROM lock_cycles"
                ).fetchone()
            return float(row["total"]) if row else 0.0
        except Exception as exc:
            logger.error("get_total_locked_profit failed: %s", exc)
            return 0.0

    def get_current_cycle_number(self) -> int:
        """Return the current cycle counter."""
        return self._cycle_num

    def get_recent_cycles(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Return the most recent *limit* lock cycles.

        Returns:
            List of dicts with keys: cycle_number, timestamp,
            coins_traded, total_profit, profit_pct.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT cycle_number, timestamp, coins_traded,
                              total_profit, profit_pct
                       FROM lock_cycles
                       ORDER BY id DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [
                {
                    "cycle_number":  r["cycle_number"],
                    "timestamp":     r["timestamp"],
                    "coins_traded":  json.loads(r["coins_traded"]),
                    "total_profit":  r["total_profit"],
                    "profit_pct":    r["profit_pct"],
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("get_recent_cycles failed: %s", exc)
            return []
