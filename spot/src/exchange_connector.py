"""
exchange_connector.py
=====================
Smart Grid Trader Pro — Exchange Connector

Handles all direct communication with the Binance Spot API via CCXT.
Wraps calls in try/except with exponential backoff on rate-limit errors.
"""

import os
import time
import logging
import math
import ccxt
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ExchangeConnector:
    """
    Wraps the CCXT binance client with safety helpers:
    - Exponential backoff on rate-limit errors.
    - Precision rounding for qty and price using exchange filters.
    - Structured error logging for every API call.
    """

    MAX_RETRIES: int = 3
    BASE_BACKOFF: float = 1.0  # seconds

    def __init__(self) -> None:
        """Load credentials from .env and instantiate the CCXT client."""
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        if not api_key or not api_secret:
            raise EnvironmentError(
                "BINANCE_API_KEY and BINANCE_SECRET_KEY must be set in .env"
            )
        
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        # Load markets once on startup to cache precision data
        self.safe_api_call(self.exchange.load_markets)
        logger.info("ExchangeConnector (CCXT) initialised.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def safe_api_call(self, fn, *args, **kwargs):
        """
        Execute *fn* with exponential backoff on rate-limit errors.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except ccxt.RateLimitExceeded as exc:
                wait = self.BASE_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Rate-limit hit. Waiting %.1fs before retry %d/%d.",
                    wait, attempt + 1, self.MAX_RETRIES,
                )
                time.sleep(wait)
            except ccxt.NetworkError as exc:
                wait = self.BASE_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Network error. Waiting %.1fs before retry %d/%d. (%s)",
                    wait, attempt + 1, self.MAX_RETRIES, exc
                )
                time.sleep(wait)
            except ccxt.ExchangeError as exc:
                logger.error("ExchangeError: %s", exc)
                raise
            except Exception as exc:
                logger.error("Unexpected error in safe_api_call: %s", exc)
                raise
        logger.error("Exhausted %d retries for %s.", self.MAX_RETRIES, fn.__name__)
        raise RuntimeError(f"API call failed after {self.MAX_RETRIES} retries.")

    def reconnect(self, api_key: str, api_secret: str) -> bool:
        """
        Hot-reload the exchange client with new API credentials.

        This allows the Control Room to update keys without a process restart.

        Args:
            api_key:    New Binance API key.
            api_secret: New Binance API secret.

        Returns:
            True if the exchange was re-initialised successfully, False otherwise.
        """
        try:
            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'},
            })
            self.safe_api_call(self.exchange.load_markets)
            logger.info("ExchangeConnector reconnected with new credentials.")
            return True
        except Exception as exc:
            logger.error("ExchangeConnector reconnect failed: %s", exc)
            return False

    @staticmethod
    def _to_ccxt_symbol(symbol: str) -> str:
        """Convert 'BTCUSDT' to 'BTC/USDT'."""
        if "/" not in symbol and symbol.endswith("USDT"):
            return symbol[:-4] + "/USDT"
        return symbol

    def _map_ccxt_order(self, order: dict) -> dict:
        """Map CCXT order dict to what downstream components expect (python-binance keys)."""
        if not order:
            return {}
        return {
            "orderId": order.get("id"),
            "origQty": order.get("amount"),
            "executedQty": order.get("filled"),
            "price": order.get("price"),
            "side": order.get("side", "").upper(),
            "status": order.get("status", "").upper()
        }

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_balance(self, asset: str) -> float:
        try:
            balances = self.safe_api_call(self.exchange.fetch_balance)
            return float(balances.get(asset, {}).get("free", 0.0))
        except Exception as exc:
            logger.error("get_balance(%s) failed: %s", asset, exc)
            return 0.0

    def get_ticker_price(self, symbol: str) -> float:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            ticker = self.safe_api_call(self.exchange.fetch_ticker, ccxt_sym)
            return float(ticker.get("last", 0.0))
        except Exception as exc:
            logger.error("get_ticker_price(%s) failed: %s", symbol, exc)
            return 0.0

    def get_all_tickers(self) -> dict:
        """Return dict of symbol -> ticker stats for all symbols."""
        try:
            return self.safe_api_call(self.exchange.fetch_tickers)
        except Exception as exc:
            logger.error("get_all_tickers failed: %s", exc)
            return {}

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            return self.safe_api_call(
                self.exchange.fetch_ohlcv,
                symbol=ccxt_sym,
                timeframe=interval,
                limit=limit,
            )
        except Exception as exc:
            logger.error("get_klines(%s, %s) failed: %s", symbol, interval, exc)
            return []

    def place_limit_buy(self, symbol: str, qty: float, price: float) -> dict:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            order = self.safe_api_call(
                self.exchange.create_order,
                symbol=ccxt_sym,
                type='limit',
                side='buy',
                amount=qty,
                price=price,
            )
            logger.info("BUY placed: %s qty=%.6f @ %.4f", symbol, qty, price)
            return self._map_ccxt_order(order)
        except Exception as exc:
            logger.error("place_limit_buy failed: %s", exc)
            return {}

    def place_limit_sell(self, symbol: str, qty: float, price: float) -> dict:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            order = self.safe_api_call(
                self.exchange.create_order,
                symbol=ccxt_sym,
                type='limit',
                side='sell',
                amount=qty,
                price=price,
            )
            logger.info("SELL placed: %s qty=%.6f @ %.4f", symbol, qty, price)
            return self._map_ccxt_order(order)
        except Exception as exc:
            logger.error("place_limit_sell failed: %s", exc)
            return {}

    def place_market_sell(self, symbol: str, qty: float) -> dict:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            order = self.safe_api_call(
                self.exchange.create_order,
                symbol=ccxt_sym,
                type='market',
                side='sell',
                amount=qty,
            )
            logger.info("MARKET SELL placed: %s qty=%.6f", symbol, qty)
            return self._map_ccxt_order(order)
        except Exception as exc:
            logger.error("place_market_sell failed: %s", exc)
            return {}

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            result = self.safe_api_call(
                self.exchange.cancel_order, id=str(order_id), symbol=ccxt_sym
            )
            logger.info("Order %s cancelled on %s.", order_id, symbol)
            return result
        except Exception as exc:
            logger.error("cancel_order(%s) failed: %s", order_id, exc)
            return {}

    def get_open_orders(self, symbol: str) -> list:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            orders = self.safe_api_call(self.exchange.fetch_open_orders, symbol=ccxt_sym)
            return [self._map_ccxt_order(o) for o in orders]
        except Exception as exc:
            logger.error("get_open_orders(%s) failed: %s", symbol, exc)
            return []

    def get_symbol_info(self, symbol: str) -> dict:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        defaults = {
            "step_size": 0.00001,
            "tick_size": 0.01,
            "min_qty": 0.00001,
            "min_notional": 10.0,
        }
        try:
            market = self.exchange.market(ccxt_sym)
            if not market:
                return defaults
            return {
                "step_size": market['precision']['amount'],
                "tick_size": market['precision']['price'],
                "min_qty": market['limits']['amount']['min'],
                "min_notional": market['limits']['cost']['min'],
            }
        except Exception as exc:
            logger.error("get_symbol_info(%s) failed: %s", symbol, exc)
            return defaults

    def round_qty(self, qty: float, symbol: str) -> float:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            return float(self.exchange.amount_to_precision(ccxt_sym, qty))
        except Exception:
            return qty

    def round_price(self, price: float, symbol: str) -> float:
        ccxt_sym = self._to_ccxt_symbol(symbol)
        try:
            return float(self.exchange.price_to_precision(ccxt_sym, price))
        except Exception:
            return price
