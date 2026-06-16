"""
profit_tracker.py
=================
Smart Grid Trader Pro — Profit Tracker

SQLite-backed ledger for all CLOSED (realized) trade events.
Never logs unrealized (open order) values.
"""

import logging
import sqlite3
import os
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("data", "trades.db")

CREATE_TRADES_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,
    symbol       TEXT    NOT NULL,
    side         TEXT    NOT NULL,
    price        REAL    NOT NULL,
    qty          REAL    NOT NULL,
    fee          REAL    NOT NULL DEFAULT 0.0,
    realized_pnl REAL    NOT NULL DEFAULT 0.0
);
"""

CREATE_PROFIT_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS profit_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    total_profit  REAL    NOT NULL,
    withdrawal    REAL    NOT NULL,
    reinvestment  REAL    NOT NULL
);
"""


class ProfitTracker:
    """
    Logs realized trades to SQLite and provides PnL query methods.

    Database is auto-created at *data/trades.db* on first use.
    Only CLOSED fills should be passed to log_trade(); never open orders.
    """

    def __init__(self) -> None:
        os.makedirs("data", exist_ok=True)
        self._db_path = DB_PATH
        self._init_db()

    # ------------------------------------------------------------------
    # DB setup
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        try:
            with self._connect() as conn:
                conn.execute(CREATE_TRADES_SQL)
                conn.execute(CREATE_PROFIT_EVENTS_SQL)
            logger.info("ProfitTracker: database ready at %s.", self._db_path)
        except Exception as exc:
            logger.error("ProfitTracker: DB init failed: %s", exc)
            raise

    def _connect(self) -> sqlite3.Connection:
        """Return a new SQLite connection with Row factory enabled."""
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def log_trade(
        self,
        symbol: str,
        side: str,
        price: float,
        qty: float,
        fee: float,
        realized_pnl: float,
    ) -> None:
        """
        Persist a single realized trade to the trades table.

        Args:
            symbol:       Trading pair, e.g. 'BTCUSDT'.
            side:         'BUY' or 'SELL'.
            price:        Fill price.
            qty:          Fill quantity.
            fee:          Commission paid (in USDT equivalent).
            realized_pnl: Net profit/loss for this fill.
        """
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO trades
                       (timestamp, symbol, side, price, qty, fee, realized_pnl)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ts, symbol, side, price, qty, fee, realized_pnl),
                )
            logger.info(
                "Trade logged: %s %s @ %.4f | qty=%.6f | pnl=%.4f USDT",
                side, symbol, price, qty, realized_pnl,
            )
        except Exception as exc:
            logger.error("log_trade failed: %s", exc)

    def log_profit_event(
        self, total_profit: float, withdrawal: float, reinvestment: float
    ) -> None:
        """
        Persist a monthly profit-split event to profit_events.

        Args:
            total_profit:  Monthly realized profit to split.
            withdrawal:    80 % portion for withdrawal.
            reinvestment:  20 % portion reinvested.
        """
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO profit_events
                       (timestamp, total_profit, withdrawal, reinvestment)
                       VALUES (?, ?, ?, ?)""",
                    (ts, total_profit, withdrawal, reinvestment),
                )
        except Exception as exc:
            logger.error("log_profit_event failed: %s", exc)

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_monthly_profit(self) -> float:
        """
        Return total realized_pnl for the current calendar month (UTC).

        Returns:
            Sum of realized_pnl for this month, or 0.0 on error.
        """
        today = date.today()
        month_start = f"{today.year}-{today.month:02d}-01"
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(realized_pnl), 0.0) AS total "
                    "FROM trades WHERE timestamp >= ?",
                    (month_start,),
                ).fetchone()
            return float(row["total"]) if row else 0.0
        except Exception as exc:
            logger.error("get_monthly_profit failed: %s", exc)
            return 0.0

    def get_daily_pnl(self) -> float:
        """
        Return total realized_pnl for today (UTC calendar day).

        Returns:
            Sum of today's realized_pnl, or 0.0 on error.
        """
        today_str = date.today().isoformat()
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(realized_pnl), 0.0) AS total "
                    "FROM trades WHERE timestamp >= ?",
                    (today_str,),
                ).fetchone()
            return float(row["total"]) if row else 0.0
        except Exception as exc:
            logger.error("get_daily_pnl failed: %s", exc)
            return 0.0

    def get_total_trades(self) -> int:
        """
        Return the total number of logged trades.

        Returns:
            Count of rows in the trades table.
        """
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS cnt FROM trades").fetchone()
            return int(row["cnt"]) if row else 0
        except Exception as exc:
            logger.error("get_total_trades failed: %s", exc)
            return 0

    def get_equity_curve(self) -> list[dict[str, Any]]:
        """
        Return a daily cumulative PnL series for plotting an equity curve.

        Returns:
            List of dicts: [{date: str, cumulative_pnl: float}, ...]
            Sorted ascending by date.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT DATE(timestamp) AS day,
                              SUM(realized_pnl) AS daily_pnl
                       FROM trades
                       GROUP BY day
                       ORDER BY day ASC"""
                ).fetchall()
            cumulative = 0.0
            curve = []
            for row in rows:
                cumulative += float(row["daily_pnl"])
                curve.append({"date": row["day"], "cumulative_pnl": round(cumulative, 6)})
            return curve
        except Exception as exc:
            logger.error("get_equity_curve failed: %s", exc)
            return []
