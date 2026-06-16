"""
backtest.py
===========
Smart Grid Trader Pro — Historical Backtester

Simulates grid trading on historical OHLCV data to validate strategy
performance before deploying real capital.

Usage:
    # From CSV:
    python backtest.py --source csv --file data/BTCUSDT_1h.csv

    # From Binance API (requires valid .env keys):
    python backtest.py --source binance --symbol BTCUSDT --days 180

Success criteria (all must pass before live deployment):
    ✅ Monthly ROI > 3 % in ranging periods
    ✅ Max drawdown  < 20 %
    ✅ Win rate       > 60 %
    ✅ Profitable months > 60 % of months tested
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless — no GUI required
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv

from src.regime_detector import RegimeDetector

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backtest")

# ── Constants ──────────────────────────────────────────────────────────────
FEE_PCT          = 0.001      # 0.1 % Binance spot maker/taker fee
ATR_MULTIPLIER   = 1.5        # grid spacing = ATR × 1.5
GRID_LEVELS      = 6
CAPITAL_PER_GRID = 12.0       # USDT per grid level
MIN_NOTIONAL     = 10.0       # minimum order size in USDT
WARM_UP_CANDLES  = 30         # skip first N candles (indicators need history)

# ── Success thresholds ─────────────────────────────────────────────────────
THRESH_MONTHLY_ROI   = 0.03   # > 3 %
THRESH_MAX_DRAWDOWN  = 0.20   # < 20 %
THRESH_WIN_RATE      = 0.60   # > 60 %
THRESH_PROFIT_MONTHS = 0.60   # > 60 % of months profitable


# ═══════════════════════════════════════════════════════════════════════════
# Data loaders
# ═══════════════════════════════════════════════════════════════════════════

def load_from_csv(filepath: str) -> pd.DataFrame:
    """Load OHLCV data from a CSV file."""
    logger.info("Loading data from CSV: %s", filepath)
    df = pd.read_csv(filepath, parse_dates=["open_time"])
    df.set_index("open_time", inplace=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    logger.info("Loaded %d candles (%s → %s).", len(df), df.index[0].date(), df.index[-1].date())
    return df


def load_from_binance(symbol: str, days: int = 180) -> pd.DataFrame:
    """Download historical klines from Binance (requires API keys in .env)."""
    from src.exchange_connector import ExchangeConnector
    from src.market_data import MarketData

    logger.info("Downloading %d days of %s data from Binance…", days, symbol)
    connector = ExchangeConnector()
    market    = MarketData(connector)

    # Binance limit = 1000 candles per request; batch if needed
    candles_needed = days * 24          # 1 h candles
    all_frames: list[pd.DataFrame] = []
    limit = min(candles_needed, 1000)
    df = market.get_ohlcv(symbol, interval="1h", limit=limit)
    if df.empty:
        raise RuntimeError("No data returned from Binance.")
    all_frames.append(df)
    logger.info("Downloaded %d candles.", len(df))
    result = pd.concat(all_frames).sort_index()
    result = result[~result.index.duplicated(keep="first")]
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Grid simulation helpers
# ═══════════════════════════════════════════════════════════════════════════

def build_grid_levels(
    current_price: float, atr: float
) -> tuple[list[float], list[float]]:
    """Return (buy_prices, sell_prices) for a grid centred at current_price."""
    spacing = atr * ATR_MULTIPLIER
    buys  = [round(current_price - (i + 1) * spacing, 8) for i in range(GRID_LEVELS)]
    sells = [round(current_price + (i + 1) * spacing, 8) for i in range(GRID_LEVELS)]
    return sorted(buys), sorted(sells)


def compute_qty(price: float) -> float:
    """Compute order quantity for a given price."""
    if price <= 0:
        return 0.0
    qty = CAPITAL_PER_GRID / price
    return round(qty, 6)


# ═══════════════════════════════════════════════════════════════════════════
# Main backtest engine
# ═══════════════════════════════════════════════════════════════════════════

def run_backtest(df: pd.DataFrame) -> dict:
    """
    Simulate grid trading on historical OHLCV data.

    For each candle (after warm-up):
      1. Run RegimeDetector on rolling window.
      2. If RANGING and no active grid → build and 'place' virtual grid.
      3. For each active grid level:
           - If candle low  <= buy_price  → fill buy  (deduct USDT, gain coin).
           - If candle high >= sell_price → fill sell (gain USDT, deduct coin).
      4. Track equity curve, PnL, drawdown.

    Returns:
        Summary dict with all performance metrics.
    """
    detector  = RegimeDetector()
    equity    = 100.0          # starting USDT
    coin_held = 0.0            # base asset held
    total_pnl = 0.0
    peak_equity = equity

    trades:     list[dict] = []
    equity_series: list[tuple] = []

    active_buys:  list[float] = []   # active buy  price levels
    active_sells: list[float] = []   # active sell price levels
    grid_active   = False
    last_regime   = "UNKNOWN"
    win_count     = 0
    loss_count    = 0

    # Monthly PnL tracker: {"YYYY-MM": pnl}
    monthly_pnl: dict[str, float] = {}

    logger.info("Starting backtest simulation over %d candles…", len(df))

    for i in range(WARM_UP_CANDLES, len(df)):
        candle    = df.iloc[i]
        window    = df.iloc[max(0, i - 100): i + 1]
        ts        = df.index[i]
        month_key = ts.strftime("%Y-%m")

        # ── Regime detection ────────────────────────────────────────────
        regime_data = detector.detect(window)
        regime = regime_data["regime"]
        atr    = regime_data["atr"]

        # ── Grid lifecycle ──────────────────────────────────────────────
        if regime == "RANGING" and not grid_active:
            mid = float(candle["close"])
            active_buys, active_sells = build_grid_levels(mid, atr)
            grid_active = True
            last_regime = regime

        elif regime in ("TRENDING", "IDLE") and grid_active:
            # Mark-to-market: liquidate coin at close price
            if coin_held > 0:
                close_val = coin_held * float(candle["close"])
                equity   += close_val
                coin_held = 0.0
            active_buys.clear()
            active_sells.clear()
            grid_active = False
            last_regime = regime

        # ── Simulate fills ──────────────────────────────────────────────
        if grid_active:
            candle_low  = float(candle["low"])
            candle_high = float(candle["high"])

            # --- BUY fills ---
            new_buys = []
            for bp in active_buys:
                if candle_low <= bp and equity >= bp * compute_qty(bp):
                    qty  = compute_qty(bp)
                    cost = bp * qty
                    fee  = cost * FEE_PCT
                    if cost + fee > equity:
                        new_buys.append(bp)
                        continue
                    equity   -= (cost + fee)
                    coin_held += qty
                    trades.append({
                        "ts": ts, "side": "BUY",
                        "price": bp, "qty": qty,
                        "fee": fee, "pnl": -(cost + fee),
                    })
                    # Don't re-add — one fill per level per grid placement
                else:
                    new_buys.append(bp)
            active_buys = new_buys

            # --- SELL fills ---
            new_sells = []
            for sp in active_sells:
                if candle_high >= sp and coin_held >= compute_qty(sp):
                    qty      = compute_qty(sp)
                    proceeds = sp * qty
                    fee      = proceeds * FEE_PCT
                    net      = proceeds - fee
                    equity   += net
                    coin_held -= qty
                    pnl       = net - CAPITAL_PER_GRID    # profit over cost basis
                    total_pnl += pnl
                    if pnl >= 0:
                        win_count += 1
                    else:
                        loss_count += 1
                    trades.append({
                        "ts": ts, "side": "SELL",
                        "price": sp, "qty": qty,
                        "fee": fee, "pnl": pnl,
                    })
                    monthly_pnl[month_key] = monthly_pnl.get(month_key, 0.0) + pnl
                else:
                    new_sells.append(sp)
            active_sells = new_sells

        # ── Equity snapshot ─────────────────────────────────────────────
        mark_value = equity + coin_held * float(candle["close"])
        equity_series.append((ts, mark_value))

        if mark_value > peak_equity:
            peak_equity = mark_value

    # ── Final mark-to-market ────────────────────────────────────────────
    if coin_held > 0:
        last_close = float(df.iloc[-1]["close"])
        equity    += coin_held * last_close
        coin_held  = 0.0

    # ── Performance metrics ─────────────────────────────────────────────
    equity_vals = [v for _, v in equity_series]
    peak        = equity_vals[0]
    max_dd      = 0.0
    for v in equity_vals:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    total_trades  = win_count + loss_count
    win_rate      = win_count / total_trades if total_trades > 0 else 0.0
    total_months  = len(monthly_pnl)
    profit_months = sum(1 for v in monthly_pnl.values() if v > 0)
    profit_month_ratio = profit_months / total_months if total_months > 0 else 0.0

    # Average monthly ROI on starting capital
    months_elapsed = max(total_months, 1)
    avg_monthly_roi = (equity - 100.0) / 100.0 / months_elapsed

    return {
        "starting_equity":     100.0,
        "final_equity":        round(equity, 4),
        "total_pnl":           round(total_pnl, 4),
        "total_trades":        total_trades,
        "win_count":           win_count,
        "loss_count":          loss_count,
        "win_rate":            round(win_rate, 4),
        "max_drawdown":        round(max_dd, 4),
        "months_tested":       total_months,
        "profitable_months":   profit_months,
        "profit_month_ratio":  round(profit_month_ratio, 4),
        "avg_monthly_roi":     round(avg_monthly_roi, 4),
        "monthly_pnl":         monthly_pnl,
        "equity_series":       equity_series,
        "trades":              trades,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════

def print_report(r: dict) -> None:
    """Print a formatted performance summary to stdout."""
    sep = "═" * 54

    def chk(val: float, threshold: float, above: bool = True) -> str:
        ok = val > threshold if above else val < threshold
        return "✅ PASS" if ok else "❌ FAIL"

    print(f"\n{sep}")
    print("  SMART GRID TRADER PRO — BACKTEST REPORT")
    print(sep)
    print(f"  Starting capital  : $100.00 USDT")
    print(f"  Final equity      : ${r['final_equity']:.2f} USDT")
    print(f"  Total PnL         : ${r['total_pnl']:+.4f} USDT")
    print(f"  Total trades      : {r['total_trades']}")
    print(f"  Wins / Losses     : {r['win_count']} / {r['loss_count']}")
    print(sep)
    print(f"  Win rate          : {r['win_rate']*100:.1f}%  "
          f"   {chk(r['win_rate'], THRESH_WIN_RATE)}")
    print(f"  Max drawdown      : {r['max_drawdown']*100:.1f}%  "
          f"   {chk(r['max_drawdown'], THRESH_MAX_DRAWDOWN, above=False)}")
    print(f"  Avg monthly ROI   : {r['avg_monthly_roi']*100:.2f}%  "
          f"   {chk(r['avg_monthly_roi'], THRESH_MONTHLY_ROI)}")
    print(f"  Profitable months : {r['profitable_months']}/{r['months_tested']}  "
          f"   {chk(r['profit_month_ratio'], THRESH_PROFIT_MONTHS)}")
    print(sep)

    all_pass = (
        r["win_rate"]           > THRESH_WIN_RATE
        and r["max_drawdown"]   < THRESH_MAX_DRAWDOWN
        and r["avg_monthly_roi"] > THRESH_MONTHLY_ROI
        and r["profit_month_ratio"] > THRESH_PROFIT_MONTHS
    )
    verdict = "🚀 BOT IS READY FOR LIVE DEPLOYMENT" if all_pass else "⚠️  NOT YET READY — review failing criteria"
    print(f"\n  {verdict}")
    print(f"{sep}\n")


def plot_equity_curve(equity_series: list, output_path: str = "backtest_result.png") -> None:
    """Save an equity curve chart as a PNG file."""
    timestamps = [ts for ts, _ in equity_series]
    values     = [v  for _, v  in equity_series]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(timestamps, values, color="#00d4aa", linewidth=1.5, label="Portfolio Equity")
    ax.axhline(100, color="#ff6b6b", linestyle="--", linewidth=1, label="Starting Capital ($100)")
    ax.fill_between(timestamps, 100, values,
                    where=[v >= 100 for v in values],
                    alpha=0.15, color="#00d4aa", label="Above baseline")
    ax.fill_between(timestamps, 100, values,
                    where=[v < 100 for v in values],
                    alpha=0.15, color="#ff6b6b", label="Below baseline")

    ax.set_title("Smart Grid Trader Pro — Equity Curve (Backtest)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio Value (USDT)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=30)
    ax.legend()
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    logger.info("Equity curve saved → %s", output_path)
    plt.close()


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smart Grid Trader Pro — Backtester"
    )
    parser.add_argument(
        "--source", choices=["csv", "binance"], default="binance",
        help="Data source: 'csv' or 'binance' (default: binance)",
    )
    parser.add_argument(
        "--file", type=str, default="data/BTCUSDT_1h.csv",
        help="CSV file path (used when --source csv)",
    )
    parser.add_argument(
        "--symbol", type=str, default="BTCUSDT",
        help="Trading pair for Binance download (default: BTCUSDT)",
    )
    parser.add_argument(
        "--days", type=int, default=180,
        help="Number of days of history to download (default: 180)",
    )
    parser.add_argument(
        "--output", type=str, default="backtest_result.png",
        help="Output filename for equity curve chart",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Load data
    if args.source == "csv":
        if not os.path.exists(args.file):
            logger.error("CSV file not found: %s", args.file)
            sys.exit(1)
        df = load_from_csv(args.file)
    else:
        df = load_from_binance(args.symbol, args.days)

    if df.empty or len(df) < 60:
        logger.error("Not enough historical data to backtest (min 60 candles).")
        sys.exit(1)

    # Run simulation
    results = run_backtest(df)

    # Report
    print_report(results)

    # Plot
    plot_equity_curve(results["equity_series"], output_path=args.output)
