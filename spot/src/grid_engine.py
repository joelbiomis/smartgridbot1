"""
grid_engine.py
==============
Smart Grid Trader Pro — Grid Engine

Calculates dynamic ATR-based grid levels and manages all grid orders:
placing, monitoring, refreshing, and cancelling them on Binance Spot.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)

MIN_ORDER_USDT = 10.0      # Binance minimum notional value
ATR_MULTIPLIER  = 1.5      # Grid spacing = ATR × 1.5


class GridEngine:
    """
    Manages the dynamic ATR-spaced grid of buy/sell limit orders.

    Args:
        connector:        ExchangeConnector instance.
        symbol:           Trading pair (e.g. 'BTCUSDT').
        grid_levels:      Number of buy AND sell levels to place.
        capital_per_grid: USDT allocated per grid level.
    """

    def __init__(
        self,
        connector: "ExchangeConnector",
        symbol: str,
        grid_levels: int = 6,
        capital_per_grid: float = 12.0,
    ) -> None:
        self.connector        = connector
        self.symbol           = symbol
        self.grid_levels      = grid_levels
        self.capital_per_grid = capital_per_grid

        # order_id → {side, price, qty, status}
        self.active_orders: dict[int, dict] = {}

        # Cache symbol precision info (avoids repeated API calls)
        self._sym_info: dict | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_sym_info(self) -> dict:
        if self._sym_info is None:
            self._sym_info = self.connector.get_symbol_info(self.symbol)
        return self._sym_info

    def _round_qty(self, qty: float) -> float:
        info = self._get_sym_info()
        return self.connector._step_round(qty, info["step_size"])

    def _round_price(self, price: float) -> float:
        info = self._get_sym_info()
        return self.connector._step_round(price, info["tick_size"])

    # ------------------------------------------------------------------
    # Grid construction
    # ------------------------------------------------------------------

    def build_grid(
        self, current_price: float, atr: float
    ) -> tuple[list[float], list[float]]:
        """
        Calculate grid buy/sell price levels using ATR-based spacing.

        Spacing between levels = ATR × ATR_MULTIPLIER.
        Levels are symmetric around *current_price*:
          buy_prices  = current_price - (1..N) × spacing
          sell_prices = current_price + (1..N) × spacing

        Args:
            current_price: Latest market price.
            atr:           Latest Average True Range value.

        Returns:
            Tuple (buy_prices, sell_prices), both sorted ascending.
        """
        spacing = atr * ATR_MULTIPLIER
        buy_prices  = []
        sell_prices = []
        for i in range(1, self.grid_levels + 1):
            buy_prices.append(self._round_price(current_price - i * spacing))
            sell_prices.append(self._round_price(current_price + i * spacing))
        buy_prices.sort()
        sell_prices.sort()
        logger.info(
            "Grid built: spacing=%.4f | buys=%s | sells=%s",
            spacing,
            [f"{p:.4f}" for p in buy_prices],
            [f"{p:.4f}" for p in sell_prices],
        )
        return buy_prices, sell_prices

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_grid_orders(self, current_price: float, atr: float) -> None:
        """
        Place all grid buy and sell limit orders on Binance.

        Before each order:
          - Checks available USDT balance ≥ capital_per_grid.
          - Skips levels where notional < MIN_ORDER_USDT.
          - Respects exchange stepSize / tickSize precision.

        Args:
            current_price: Latest market price.
            atr:           Latest ATR value for spacing calculation.
        """
        buy_prices, sell_prices = self.build_grid(current_price, atr)
        sym_info = self._get_sym_info()
        min_notional = sym_info.get("min_notional", MIN_ORDER_USDT)

        # --- Place BUY orders ---
        for price in buy_prices:
            if price <= 0:
                continue
            qty = self._round_qty(self.capital_per_grid / price)
            if qty * price < max(MIN_ORDER_USDT, min_notional):
                logger.warning("Skipping BUY at %.4f — notional too small.", price)
                continue
            usdt_balance = self.connector.get_balance("USDT")
            if usdt_balance < qty * price:
                logger.warning(
                    "Insufficient USDT (%.2f) for BUY %.6f @ %.4f — skipping.",
                    usdt_balance, qty, price,
                )
                continue
            order = self.connector.place_limit_buy(self.symbol, qty, price)
            if order and order.get("orderId"):
                self.active_orders[order["orderId"]] = {
                    "side": "BUY",
                    "price": price,
                    "qty": qty,
                    "status": "OPEN",
                }

        # --- Place SELL orders ---
        base_asset = self.symbol.replace("USDT", "")
        for price in sell_prices:
            if price <= 0:
                continue
            qty = self._round_qty(self.capital_per_grid / price)
            if qty * price < max(MIN_ORDER_USDT, min_notional):
                logger.warning("Skipping SELL at %.4f — notional too small.", price)
                continue
            asset_balance = self.connector.get_balance(base_asset)
            if asset_balance < qty:
                logger.warning(
                    "Insufficient %s (%.6f) for SELL %.6f @ %.4f — skipping.",
                    base_asset, asset_balance, qty, price,
                )
                continue
            order = self.connector.place_limit_sell(self.symbol, qty, price)
            if order and order.get("orderId"):
                self.active_orders[order["orderId"]] = {
                    "side": "SELL",
                    "price": price,
                    "qty": qty,
                    "status": "OPEN",
                }

        logger.info(
            "Grid placement complete. Active orders: %d", len(self.active_orders)
        )

    # ------------------------------------------------------------------
    # Order monitoring
    # ------------------------------------------------------------------

    def check_and_refresh_orders(self) -> list[dict]:
        """
        Compare locally tracked orders vs Binance open orders.

        Any order that was in active_orders but is NO LONGER open on
        Binance is considered filled. Those orders are removed from
        active_orders and returned as a list of filled order dicts.

        Returns:
            List of filled order dicts:
            [{order_id, side, price, qty}, ...]
        """
        if not self.active_orders:
            return []

        try:
            open_on_exchange = {
                o["orderId"]
                for o in self.connector.get_open_orders(self.symbol)
            }
        except Exception as exc:
            logger.error("check_and_refresh_orders: could not fetch open orders: %s", exc)
            return []

        filled = []
        for order_id, meta in list(self.active_orders.items()):
            if order_id not in open_on_exchange:
                filled.append({"order_id": order_id, **meta})
                del self.active_orders[order_id]
                logger.info(
                    "Order FILLED: id=%d side=%s price=%.4f qty=%.6f",
                    order_id, meta["side"], meta["price"], meta["qty"],
                )

        if filled:
            logger.info("%d order(s) filled this cycle.", len(filled))
        return filled

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel_all_orders(self) -> None:
        """
        Cancel every order in active_orders on Binance and clear the dict.
        """
        if not self.active_orders:
            logger.info("cancel_all_orders: nothing to cancel.")
            return
        for order_id in list(self.active_orders.keys()):
            self.connector.cancel_order(self.symbol, order_id)
        self.active_orders.clear()
        logger.info("All grid orders cancelled and active_orders cleared.")

    # ------------------------------------------------------------------
    # Range check
    # ------------------------------------------------------------------

    def is_price_in_range(self, current_price: float) -> bool:
        """
        Check whether *current_price* is still within the active grid range.

        Returns False (grid needs rebuilding) if the price has moved beyond
        the outermost buy or sell level, or if no orders are active.

        Args:
            current_price: Latest market price.

        Returns:
            True if price is within range, False otherwise.
        """
        if not self.active_orders:
            return False
        prices = [meta["price"] for meta in self.active_orders.values()]
        grid_min = min(prices)
        grid_max = max(prices)
        in_range = grid_min <= current_price <= grid_max
        if not in_range:
            logger.warning(
                "Price %.4f outside grid range [%.4f, %.4f] — rebuild needed.",
                current_price, grid_min, grid_max,
            )
        return in_range
