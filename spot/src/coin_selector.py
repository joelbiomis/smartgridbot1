"""
coin_selector.py
================
Portfolio Profit Lock Grid Bot — Coin Selector

Selects the most liquid USDT-quoted trading pairs each cycle by fetching
24-hour ticker statistics from Binance and applying volume + price filters.

Eligible pairs are ranked by descending quote volume so that the bot always
trades the deepest, most liquid markets available.
"""

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)

# ── Defaults (overridable via .env) ────────────────────────────────────────
DEFAULT_NUM_COINS     = 3          # how many coins to trade simultaneously
MIN_24H_VOLUME_USDT   = 50_000_000 # minimum 24-hour quote volume ($50M)
BLACKLIST: set[str]   = {"USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDTUSDT",
                         "FDUSDUSDT", "PYUSDUSDT"}   # stable-coin pairs


class CoinSelector:
    """
    Selects the top-N most liquid USDT pairs for the portfolio each cycle.

    Args:
        connector:  Initialised ExchangeConnector instance.
        num_coins:  Maximum number of coins to select (default 3).
        min_volume: Minimum 24-hour quote volume in USDT (default $50M).
        blacklist:  Set of symbols to always exclude (stable coins, etc.).
    """

    def __init__(
        self,
        connector: "ExchangeConnector",
        num_coins: int   = DEFAULT_NUM_COINS,
        min_volume: float = MIN_24H_VOLUME_USDT,
        blacklist: set[str] | None = None,
    ) -> None:
        self.connector  = connector
        self.num_coins  = num_coins
        self.min_volume = min_volume
        self.blacklist  = blacklist if blacklist is not None else BLACKLIST

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_eligible_coins(self) -> list[str]:
        """
        Fetch 24-hour ticker stats from Binance and return the top-N symbols.

        Filters applied (in order):
          1. Only USDT-quoted pairs (symbol ends with 'USDT').
          2. Not in the blacklist (stable-coins, etc.).
          3. 24-hour quote volume ≥ min_volume.
          4. Ranked descending by quote volume.
          5. Top num_coins selected.

        Returns:
            List of symbol strings, e.g. ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'].
            Returns an empty list on API failure.
        """
        try:
            tickers = self.connector.get_all_tickers()
        except Exception as exc:
            logger.error("CoinSelector: failed to fetch tickers: %s", exc)
            return []

        eligible = []
        for ccxt_sym, t in tickers.items():
            if not ccxt_sym.endswith("/USDT"):
                continue
            symbol = ccxt_sym.replace("/", "")
            if symbol in self.blacklist:
                continue
            try:
                quote_vol = float(t.get("quoteVolume", 0))
                price     = float(t.get("last", 0))
            except (ValueError, TypeError):
                continue
            if quote_vol < self.min_volume or price <= 0:
                continue
            eligible.append({"symbol": symbol, "volume": quote_vol, "price": price})

        # Sort descending by volume, pick top-N
        eligible.sort(key=lambda x: x["volume"], reverse=True)
        selected = [e["symbol"] for e in eligible[: self.num_coins]]

        logger.info(
            "CoinSelector: selected %d coins: %s",
            len(selected),
            selected,
        )
        return selected

    def get_coin_prices(self, symbols: list[str]) -> dict[str, float]:
        """
        Return the current price for each symbol in *symbols*.

        Args:
            symbols: List of trading pair strings.

        Returns:
            Dict mapping symbol → current price.  Missing/failed symbols
            are omitted from the result.
        """
        prices: dict[str, float] = {}
        for sym in symbols:
            price = self.connector.get_ticker_price(sym)
            if price > 0:
                prices[sym] = price
            else:
                logger.warning("CoinSelector: could not fetch price for %s.", sym)
        return prices
