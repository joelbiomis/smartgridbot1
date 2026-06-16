"""
risk_manager.py
===============
Smart Grid Trader Pro — Risk Manager

Implements three safety checks that gate every trading cycle:
  1. SAFE_MODE — balance drawdown floor breached
  2. SAFE_MODE — USDT reserve ratio too low
  3. PAUSE     — ATR volatility spike detected
  4. ACTIVE    — all checks pass, normal trading
"""

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)

LOG_DIR  = "logs"
RISK_LOG = os.path.join(LOG_DIR, "risk_events.log")

RESERVE_RATIO       = 0.20   # USDT must be ≥ 20 % of total balance
ATR_SPIKE_MULTIPLIER = 3.0   # Current ATR > historical_avg * 3 → PAUSE


class RiskManager:
    """
    Evaluates pre-cycle safety conditions and enforces trading limits.

    Args:
        connector:         ExchangeConnector instance for live balance queries.
        initial_balance:   The starting USDT capital (drawdown floor baseline).
        max_drawdown_pct:  Maximum permitted drawdown fraction (default 0.20 = 20 %).
    """

    def __init__(
        self,
        connector: "ExchangeConnector",
        initial_balance: float = 100.0,
        max_drawdown_pct: float = 0.20,
    ) -> None:
        self.connector        = connector
        self.initial_balance  = initial_balance
        self.max_drawdown_pct = max_drawdown_pct

        # Running list of ATR samples used to compute historical average
        self._atr_history: list[float] = []

        os.makedirs(LOG_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Main safety gate
    # ------------------------------------------------------------------

    def check_safety(
        self, current_atr: float | None = None
    ) -> tuple[str, str]:
        """
        Run all safety checks in priority order and return a (mode, reason) tuple.

        Check order:
          1. SAFE_MODE if balance is below the drawdown floor.
          2. SAFE_MODE if liquid USDT is below the reserve ratio.
          3. PAUSE     if current ATR is a volatility spike (> 3× historical avg).
          4. ACTIVE    if all checks pass.

        Args:
            current_atr: The latest ATR value from RegimeDetector.
                         Pass None to skip the volatility-spike check.

        Returns:
            Tuple (mode: str, reason: str) where mode ∈ {'SAFE_MODE', 'PAUSE', 'ACTIVE'}.
        """
        usdt_balance = self.connector.get_balance("USDT")
        drawdown_floor = self.initial_balance * (1 - self.max_drawdown_pct)

        # ── Check 1: Drawdown floor ─────────────────────────────────────
        if usdt_balance < drawdown_floor:
            reason = (
                f"USDT balance {usdt_balance:.2f} is below drawdown floor "
                f"{drawdown_floor:.2f} ({self.max_drawdown_pct*100:.0f}% max drawdown)."
            )
            self.log_risk_event("SAFE_MODE", reason)
            return "SAFE_MODE", reason

        # ── Check 2: Reserve ratio ──────────────────────────────────────
        # Approximate total equity as USDT only (conservative — ignores held coins)
        total_balance = usdt_balance  # conservative lower bound
        if total_balance > 0 and (usdt_balance / total_balance) < RESERVE_RATIO:
            reason = (
                f"USDT reserve {usdt_balance:.2f} is below "
                f"{RESERVE_RATIO*100:.0f}% of total balance {total_balance:.2f}."
            )
            self.log_risk_event("SAFE_MODE", reason)
            return "SAFE_MODE", reason

        # ── Check 3: ATR volatility spike ───────────────────────────────
        if current_atr is not None and current_atr > 0:
            self._atr_history.append(current_atr)
            # Keep last 200 ATR samples for a stable average
            if len(self._atr_history) > 200:
                self._atr_history.pop(0)

            if len(self._atr_history) >= 10:
                avg_atr = sum(self._atr_history[:-1]) / (len(self._atr_history) - 1)
                if avg_atr > 0 and current_atr > avg_atr * ATR_SPIKE_MULTIPLIER:
                    reason = (
                        f"ATR spike detected: current ATR {current_atr:.4f} > "
                        f"{ATR_SPIKE_MULTIPLIER}× avg ATR {avg_atr:.4f}."
                    )
                    self.log_risk_event("PAUSE", reason)
                    return "PAUSE", reason

        # ── All clear ───────────────────────────────────────────────────
        return "ACTIVE", "All safety checks passed."

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def log_risk_event(self, event_type: str, detail: str) -> None:
        """
        Append a timestamped risk event to the audit log file.

        Args:
            event_type: Short category label, e.g. 'SAFE_MODE', 'PAUSE'.
            detail:     Human-readable description of the trigger condition.
        """
        ts = datetime.now(timezone.utc).isoformat()
        line = f"[{ts}] [{event_type}] {detail}\n"
        try:
            with open(RISK_LOG, "a", encoding="utf-8") as fh:
                fh.write(line)
            logger.warning("RISK EVENT [%s]: %s", event_type, detail)
        except Exception as exc:
            logger.error("log_risk_event write failed: %s", exc)
