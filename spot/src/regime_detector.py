"""
regime_detector.py
==================
Smart Grid Trader Pro — Market Regime Detector

Uses ADX, Bollinger Bands, and ATR (via the `ta` library) to classify
the current market into one of three regimes:
  - RANGING : low trend strength, sufficient volatility → grid trading ON
  - TRENDING: strong directional move → grid trading OFF
  - IDLE     : low volatility → grid trading OFF
"""

import logging
import pandas as pd
import ta
from ta.trend import ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange

logger = logging.getLogger(__name__)

# ── Regime thresholds ──────────────────────────────────────
ADX_TREND_THRESHOLD = 25.0   # ADX >= 25 → TRENDING
ADX_IDLE_THRESHOLD  = 15.0   # ADX <  15 → IDLE
BB_WIDTH_THRESHOLD  = 0.02   # BB width > 2 % → enough volatility for RANGING

# ── Indicator windows ──────────────────────────────────────
ADX_WINDOW = 14
BB_WINDOW  = 20
BB_DEV     = 2.0
ATR_WINDOW = 14


class RegimeDetector:
    """
    Classifies the market regime from OHLCV data.

    Regime logic (evaluated in order):
      1. ADX >= ADX_TREND_THRESHOLD                        → TRENDING
      2. ADX <  ADX_IDLE_THRESHOLD                         → IDLE
      3. ADX <  ADX_TREND_THRESHOLD AND BB_width > 0.02   → RANGING
      4. Fallback                                           → IDLE
    """

    def detect(self, df: pd.DataFrame) -> dict:
        """
        Run regime detection on the supplied OHLCV DataFrame.

        Args:
            df: DataFrame with columns [open, high, low, close, volume].
                Index should be a DatetimeIndex (UTC).

        Returns:
            dict with keys:
              regime      (str)  : 'RANGING' | 'TRENDING' | 'IDLE'
              adx         (float): latest ADX value
              bb_width    (float): latest Bollinger Band width (fraction of mid)
              atr         (float): latest ATR value
              upper_band  (float): latest BB upper band
              lower_band  (float): latest BB lower band
        """
        if df.empty or len(df) < max(ADX_WINDOW, BB_WINDOW, ATR_WINDOW) + 5:
            logger.warning("RegimeDetector: insufficient data — defaulting to IDLE.")
            return self._idle_result()

        try:
            # ── ADX ────────────────────────────────────────────────────
            adx_ind = ADXIndicator(
                high=df["high"], low=df["low"], close=df["close"],
                window=ADX_WINDOW, fillna=False,
            )
            adx_val = float(adx_ind.adx().iloc[-1])

            # ── Bollinger Bands ────────────────────────────────────────
            bb_ind = BollingerBands(
                close=df["close"], window=BB_WINDOW,
                window_dev=BB_DEV, fillna=False,
            )
            upper = float(bb_ind.bollinger_hband().iloc[-1])
            lower = float(bb_ind.bollinger_lband().iloc[-1])
            mid   = float(bb_ind.bollinger_mavg().iloc[-1])
            bb_width = (upper - lower) / mid if mid > 0 else 0.0

            # ── ATR ────────────────────────────────────────────────────
            atr_ind = AverageTrueRange(
                high=df["high"], low=df["low"], close=df["close"],
                window=ATR_WINDOW, fillna=False,
            )
            atr_val = float(atr_ind.average_true_range().iloc[-1])

            # ── Classify ───────────────────────────────────────────────
            if adx_val >= ADX_TREND_THRESHOLD:
                regime = "TRENDING"
            elif adx_val < ADX_IDLE_THRESHOLD:
                regime = "IDLE"
            elif bb_width > BB_WIDTH_THRESHOLD:
                regime = "RANGING"
            else:
                regime = "IDLE"

            result = {
                "regime":     regime,
                "adx":        round(adx_val, 4),
                "bb_width":   round(bb_width, 6),
                "atr":        round(atr_val, 6),
                "upper_band": round(upper, 6),
                "lower_band": round(lower, 6),
            }
            logger.info(
                "Regime: %s | ADX=%.2f | BB_width=%.4f | ATR=%.4f",
                regime, adx_val, bb_width, atr_val,
            )
            return result

        except Exception as exc:
            logger.error("RegimeDetector.detect() error: %s", exc)
            return self._idle_result()

    @staticmethod
    def _idle_result() -> dict:
        """Return a safe default IDLE result."""
        return {
            "regime": "IDLE",
            "adx": 0.0,
            "bb_width": 0.0,
            "atr": 0.0,
            "upper_band": 0.0,
            "lower_band": 0.0,
        }


# ── Self-test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np

    logging.basicConfig(level=logging.INFO)

    # Generate synthetic sideways (ranging) price data
    np.random.seed(42)
    n = 120
    close = 30000 + np.cumsum(np.random.randn(n) * 50)
    high  = close + abs(np.random.randn(n) * 30)
    low   = close - abs(np.random.randn(n) * 30)
    open_ = close + np.random.randn(n) * 20

    sample_df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": np.random.rand(n) * 1000 + 500},
        index=pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
    )

    detector = RegimeDetector()
    result   = detector.detect(sample_df)
    print("\n=== RegimeDetector Self-Test ===")
    for k, v in result.items():
        print(f"  {k:12s}: {v}")
