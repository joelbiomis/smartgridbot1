"""
portfolio_engine.py
===================
Portfolio Profit Lock Grid Bot — Portfolio PnL Engine

Calculates the real-time combined portfolio profit/loss across all active
coins and determines whether the profit-lock target has been reached.

Two target modes are supported (set via .env TARGET_MODE):
  PCT  — lock when portfolio gain ≥ PORTFOLIO_PROFIT_TARGET_PCT
  USD  — lock when portfolio gain ≥ PORTFOLIO_PROFIT_TARGET_USD (fixed $)

PnL is computed as:
  realized_pnl  = sum of all SELL fills logged since cycle start
  unrealized_pnl = mark-to-market value of coin positions at current prices
  total_pnl     = realized_pnl + unrealized_pnl - total_fees_paid
"""

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)

TARGET_MODE_PCT = "PCT"
TARGET_MODE_USD = "USD"

FEE_RATE = 0.001   # 0.1 % Binance taker fee


class PortfolioEngine:
    """
    Tracks all open positions across a multi-coin portfolio and evaluates
    whether the global profit-lock target has been reached.

    Args:
        connector:         ExchangeConnector instance (for live price queries).
        starting_capital:  USDT capital deployed at the start of this cycle.
        target_mode:       'PCT' (percentage) or 'USD' (fixed dollar amount).
        target_pct:        Minimum gain fraction to trigger lock (e.g. 0.005 = 0.5%).
        target_usd:        Minimum gain in USDT to trigger lock (e.g. 2.0).
        max_drawdown_pct:  Portfolio hard floor as a fraction (default 0.15 = 15%).
    """

    def __init__(
        self,
        connector: "ExchangeConnector",
        starting_capital: float,
        target_mode: str   = TARGET_MODE_PCT,
        target_pct: float  = 0.005,
        target_usd: float  = 2.0,
        max_drawdown_pct: float = 0.15,
    ) -> None:
        self.connector        = connector
        self.starting_capital = starting_capital
        self.target_mode      = target_mode.upper()
        self.target_pct       = target_pct
        self.target_usd       = target_usd
        self.max_drawdown_pct = max_drawdown_pct

        # coin → {"qty": float, "avg_cost": float}  (running position)
        self._positions: dict[str, dict] = {}

        # Running totals across the current cycle
        self._realized_pnl: float = 0.0
        self._total_fees:   float = 0.0

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------

    def record_fill(
        self,
        symbol: str,
        side: str,
        price: float,
        qty: float,
        fee: float,
    ) -> None:
        """
        Update the internal position book when a grid order is filled.

        BUY fills increase the held position; SELL fills reduce it and
        realise profit/loss.

        Args:
            symbol: Trading pair (e.g. 'BTCUSDT').
            side:   'BUY' or 'SELL'.
            price:  Fill price in USDT.
            qty:    Fill quantity in base asset.
            fee:    Commission paid in USDT.
        """
        self._total_fees += fee

        if side == "BUY":
            pos = self._positions.get(symbol, {"qty": 0.0, "avg_cost": 0.0})
            total_qty  = pos["qty"] + qty
            total_cost = pos["qty"] * pos["avg_cost"] + qty * price
            self._positions[symbol] = {
                "qty":      total_qty,
                "avg_cost": total_cost / total_qty if total_qty > 0 else price,
            }

        elif side == "SELL":
            pos = self._positions.get(symbol, {"qty": 0.0, "avg_cost": 0.0})
            avg_cost = pos.get("avg_cost", price)
            pnl = (price - avg_cost) * qty - fee
            self._realized_pnl += pnl

            new_qty = max(0.0, pos["qty"] - qty)
            self._positions[symbol] = {
                "qty":      new_qty,
                "avg_cost": avg_cost if new_qty > 0 else 0.0,
            }

        logger.debug(
            "record_fill: %s %s %.6f @ %.4f | realized_pnl_total=%.4f",
            side, symbol, qty, price, self._realized_pnl,
        )

    def reset_cycle(self, starting_capital: float) -> None:
        """
        Reset all position tracking for a new cycle.

        Args:
            starting_capital: Fresh USDT capital for the new cycle.
        """
        self._positions      = {}
        self._realized_pnl   = 0.0
        self._total_fees     = 0.0
        self.starting_capital = starting_capital
        logger.info(
            "PortfolioEngine: cycle reset. New starting capital = %.2f USDT.",
            starting_capital,
        )

    # ------------------------------------------------------------------
    # PnL calculation
    # ------------------------------------------------------------------

    def calculate_pnl(self, current_prices: dict[str, float]) -> dict:
        """
        Compute the full portfolio PnL snapshot.

        Args:
            current_prices: Dict of symbol → latest price, e.g.
                            {'BTCUSDT': 65000.0, 'ETHUSDT': 3200.0}.

        Returns:
            Dict with keys:
              realized_pnl   (float): Profit from closed SELL fills.
              unrealized_pnl (float): Mark-to-market value of open positions.
              total_fees     (float): Cumulative fees paid this cycle.
              net_pnl        (float): realized + unrealized − fees.
              pct_gain       (float): net_pnl / starting_capital.
              should_lock    (bool):  True if target has been reached.
              safe_mode      (bool):  True if drawdown floor breached.
              positions      (dict):  Current positions snapshot.
        """
        unrealized = 0.0
        for symbol, pos in self._positions.items():
            qty = pos["qty"]
            if qty <= 0:
                continue
            price = current_prices.get(symbol, 0.0)
            if price > 0:
                avg_cost   = pos.get("avg_cost", 0.0)
                unrealized += (price - avg_cost) * qty

        net_pnl  = self._realized_pnl + unrealized - self._total_fees
        pct_gain = net_pnl / self.starting_capital if self.starting_capital > 0 else 0.0

        # ── Profit lock check ────────────────────────────────────────────
        if self.target_mode == TARGET_MODE_PCT:
            should_lock = pct_gain >= self.target_pct
        else:
            should_lock = net_pnl >= self.target_usd

        # ── Drawdown / safe mode check ───────────────────────────────────
        drawdown    = -net_pnl / self.starting_capital if net_pnl < 0 and self.starting_capital > 0 else 0.0
        safe_mode   = drawdown >= self.max_drawdown_pct

        result = {
            "realized_pnl":   round(self._realized_pnl, 6),
            "unrealized_pnl": round(unrealized, 6),
            "total_fees":     round(self._total_fees, 6),
            "net_pnl":        round(net_pnl, 6),
            "pct_gain":       round(pct_gain, 6),
            "should_lock":    should_lock,
            "safe_mode":      safe_mode,
            "positions":      {k: dict(v) for k, v in self._positions.items()},
        }

        logger.info(
            "Portfolio PnL | net=%.4f USDT (%.3f%%) | realized=%.4f | "
            "unrealized=%.4f | fees=%.4f | lock=%s | safe_mode=%s",
            net_pnl, pct_gain * 100,
            self._realized_pnl, unrealized, self._total_fees,
            should_lock, safe_mode,
        )
        return result

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_active_symbols(self) -> list[str]:
        """Return symbols with a non-zero held position."""
        return [s for s, p in self._positions.items() if p["qty"] > 0]

    def get_position(self, symbol: str) -> dict:
        """Return {qty, avg_cost} for *symbol*, or zeros if not held."""
        return self._positions.get(symbol, {"qty": 0.0, "avg_cost": 0.0})

    def target_description(self) -> str:
        """Human-readable description of the current profit target."""
        if self.target_mode == TARGET_MODE_PCT:
            return f"{self.target_pct * 100:.2f}% gain"
        return f"${self.target_usd:.2f} USD gain"
