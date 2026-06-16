"""
market_data.py
==============
Smart Grid Trader Pro — Market Data Module

Fetches OHLCV candles via ExchangeConnector and returns
a clean, validated pandas DataFrame ready for indicator calculation.
"""

import logging
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.exchange_connector import ExchangeConnector

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]
MIN_CANDLES = 50


class MarketData:
    """
    Fetches and validates OHLCV market data from Binance.

    Args:
        connector: An initialised ExchangeConnector instance (dependency injection).
    """

    def __init__(self, connector: "ExchangeConnector") -> None:
        self.connector = connector

    def get_ohlcv(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles and return as a validated DataFrame.

        Columns: open, high, low, close, volume (all float64).
        Index: UTC datetime parsed from the open-time timestamp.

        Args:
            symbol:   Trading pair, e.g. 'BTCUSDT'.
            interval: Kline interval, e.g. '1h', '15m'.
            limit:    Number of candles to fetch (max 1000).

        Returns:
            Validated DataFrame or empty DataFrame on failure.
        """
        raw = self.connector.get_klines(symbol, interval, limit)
        if not raw:
            logger.error("get_ohlcv: no klines returned for %s %s.", symbol, interval)
            return pd.DataFrame()

        try:
            df = pd.DataFrame(
                raw,
                columns=["open_time", "open", "high", "low", "close", "volume"],
            )
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
            df.set_index("open_time", inplace=True)
            df = df[REQUIRED_COLUMNS].astype(float)

            if not self.validate_data(df):
                return pd.DataFrame()

            return df
        except Exception as exc:
            logger.error("get_ohlcv parse error for %s: %s", symbol, exc)
            return pd.DataFrame()

    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate that the DataFrame meets minimum quality requirements.

        Checks:
        - At least MIN_CANDLES rows present.
        - No NaN values in any OHLCV column.
        - All OHLCV values are positive.

        Args:
            df: DataFrame to validate.

        Returns:
            True if valid, False otherwise (with warning logged).
        """
        if df.empty:
            logger.warning("validate_data: DataFrame is empty.")
            return False

        if len(df) < MIN_CANDLES:
            logger.warning(
                "validate_data: only %d candles returned (min %d required).",
                len(df), MIN_CANDLES,
            )
            return False

        if df[REQUIRED_COLUMNS].isnull().any().any():
            logger.warning("validate_data: NaN values detected in OHLCV data.")
            return False

        if (df[REQUIRED_COLUMNS] <= 0).any().any():
            logger.warning("validate_data: non-positive values detected in OHLCV data.")
            return False

        return True
