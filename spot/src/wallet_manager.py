"""
wallet_manager.py
=================
Smart Grid Trader Pro — Wallet Manager

Handles end-of-month profit settlement using an 80 / 20 split:
  80 % → withdrawal (your profit)
  20 % → reinvestment (grows the trading account)

Settlement is DEFERRED if any grid orders are still open.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.profit_tracker import ProfitTracker

logger = logging.getLogger(__name__)

WITHDRAWAL_PCT   = 0.80
REINVESTMENT_PCT = 0.20


class WalletManager:
    """
    Manages monthly profit settlement and reinvestment logic.

    Args:
        profit_tracker: Initialised ProfitTracker instance (dependency injection).
    """

    def __init__(self, profit_tracker: "ProfitTracker") -> None:
        self.profit_tracker = profit_tracker

    def monthly_settlement(self, open_orders_count: int) -> dict | None:
        """
        Perform end-of-month profit settlement.

        Settlement rules (checked in order):
        1. If any grid orders are still open → log warning and DEFER.
        2. If monthly profit ≤ 0 → log info and SKIP.
        3. Otherwise → split 80 / 20, persist event, return summary.

        Args:
            open_orders_count: Number of currently open grid orders.
                               Pass `len(grid_engine.active_orders)`.

        Returns:
            dict with keys {profit, withdrawal, reinvestment, timestamp}
            if settlement was performed, else None.
        """
        # ── Guard: open orders ──────────────────────────────────────────
        if open_orders_count > 0:
            logger.warning(
                "Monthly settlement DEFERRED: %d grid order(s) still open. "
                "Will retry next cycle.",
                open_orders_count,
            )
            return None

        # ── Guard: no profit ───────────────────────────────────────────
        monthly_profit = self.profit_tracker.get_monthly_profit()
        if monthly_profit <= 0:
            logger.info(
                "Monthly settlement SKIPPED: monthly profit is %.4f USDT (≤ 0).",
                monthly_profit,
            )
            return None

        # ── Perform split ──────────────────────────────────────────────
        withdrawal   = round(monthly_profit * WITHDRAWAL_PCT,   6)
        reinvestment = round(monthly_profit * REINVESTMENT_PCT, 6)
        ts           = datetime.now(timezone.utc).isoformat()

        self.profit_tracker.log_profit_event(monthly_profit, withdrawal, reinvestment)

        result = {
            "profit":       round(monthly_profit, 6),
            "withdrawal":   withdrawal,
            "reinvestment": reinvestment,
            "timestamp":    ts,
        }
        logger.info(
            "Monthly settlement COMPLETED: profit=%.4f | "
            "withdrawal=%.4f (80%%) | reinvestment=%.4f (20%%)",
            monthly_profit, withdrawal, reinvestment,
        )
        return result
