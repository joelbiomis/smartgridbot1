"""
main.py
=======
Smart Grid Trader Pro — Main Orchestration Loop

Initialises all modules, schedules the 15-minute trading cycle and the
end-of-month profit settlement, and handles clean shutdown on Ctrl-C.

Run with:
    python main.py
"""

import logging
import os
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# ── Project imports ────────────────────────────────────────────────────────
from src.exchange_connector import ExchangeConnector
from src.market_data        import MarketData
from src.regime_detector    import RegimeDetector
from src.grid_engine        import GridEngine
from src.profit_tracker     import ProfitTracker
from src.wallet_manager     import WalletManager
from src.risk_manager       import RiskManager
from src.telegram_alerts    import TelegramAlerter

# ── Bootstrap ──────────────────────────────────────────────────────────────
load_dotenv()

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "bot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# ── Configuration from .env ────────────────────────────────────────────────
SYMBOL           = os.getenv("TRADING_SYMBOL",   "BTCUSDT")
INITIAL_BALANCE  = float(os.getenv("INITIAL_BALANCE",   "100.0"))
MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT",   "0.20"))
GRID_LEVELS      = int(os.getenv("GRID_LEVELS",          "6"))
CAPITAL_PER_GRID = float(os.getenv("CAPITAL_PER_GRID",   "12.0"))

# ── Module initialisation ──────────────────────────────────────────────────
logger.info("=" * 60)
logger.info("  Smart Grid Trader Pro — Starting Up")
logger.info("  Symbol: %s  |  Capital: $%.2f", SYMBOL, INITIAL_BALANCE)
logger.info("=" * 60)

connector       = ExchangeConnector()
market_data     = MarketData(connector)
regime_detector = RegimeDetector()
grid_engine     = GridEngine(connector, SYMBOL, GRID_LEVELS, CAPITAL_PER_GRID)
profit_tracker  = ProfitTracker()
wallet_manager  = WalletManager(profit_tracker)
risk_manager    = RiskManager(connector, INITIAL_BALANCE, MAX_DRAWDOWN_PCT)
alerter         = TelegramAlerter()

# ── Global state ───────────────────────────────────────────────────────────
grid_active   = False
last_regime   = "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════════════
# Core trading cycle
# ═══════════════════════════════════════════════════════════════════════════

def run_cycle() -> None:
    """
    Execute one complete trading cycle. Called every 15 minutes.

    Flow:
      a) Risk check  → SAFE_MODE cancels grid and returns early.
      b) Fetch OHLCV candles.
      c) Detect market regime and ATR.
      d) RANGING + grid NOT active  → place fresh grid orders.
      e) RANGING + grid active      → check fills, log realized PnL.
      f) TRENDING / IDLE + grid on  → cancel all orders.
      g) Log state summary.
    """
    global grid_active, last_regime

    logger.info("─" * 50)
    logger.info("Cycle start — %s UTC", datetime.now(timezone.utc).strftime("%H:%M:%S"))

    # ── (a) Risk check ──────────────────────────────────────────────────
    mode, reason = risk_manager.check_safety()
    if mode == "SAFE_MODE":
        logger.warning("SAFE_MODE: %s", reason)
        alerter.alert_safe_mode(reason, connector.get_balance("USDT"))
        if grid_active:
            grid_engine.cancel_all_orders()
            grid_active = False
        return

    if mode == "PAUSE":
        logger.warning("PAUSED: %s", reason)
        return

    # ── (b) Fetch market data ───────────────────────────────────────────
    df = market_data.get_ohlcv(SYMBOL, interval="1h", limit=100)
    if df.empty:
        logger.error("Cycle aborted: no OHLCV data available.")
        return

    # ── (c) Detect regime ───────────────────────────────────────────────
    regime_data = regime_detector.detect(df)
    regime      = regime_data["regime"]
    atr         = regime_data["atr"]
    current_price = connector.get_ticker_price(SYMBOL)

    if regime != last_regime:
        alerter.alert_regime_change(last_regime, regime)
        last_regime = regime

    # ── (d) RANGING + grid OFF → place grid ─────────────────────────────
    if regime == "RANGING" and not grid_active:
        logger.info("RANGING detected — placing fresh grid orders.")
        grid_engine.place_grid_orders(current_price, atr)
        grid_active = len(grid_engine.active_orders) > 0

    # ── (e) RANGING + grid ON → refresh / check fills ───────────────────
    elif regime == "RANGING" and grid_active:
        # Rebuild if price has escaped the grid
        if not grid_engine.is_price_in_range(current_price):
            logger.info("Price outside grid — rebuilding.")
            grid_engine.cancel_all_orders()
            grid_engine.place_grid_orders(current_price, atr)
            grid_active = len(grid_engine.active_orders) > 0
        else:
            filled_orders = grid_engine.check_and_refresh_orders()
            for order in filled_orders:
                # Estimate realized PnL for a filled grid leg
                # Sell fills realise profit; buy fills are cost entries.
                fee = order["price"] * order["qty"] * 0.001   # 0.1 % Binance fee
                if order["side"] == "SELL":
                    pnl = order["price"] * order["qty"] - fee
                else:
                    pnl = -(order["price"] * order["qty"]) - fee

                profit_tracker.log_trade(
                    symbol=SYMBOL,
                    side=order["side"],
                    price=order["price"],
                    qty=order["qty"],
                    fee=fee,
                    realized_pnl=pnl,
                )
                alerter.alert_order_filled(
                    order["side"], order["price"], order["qty"], pnl
                )

            grid_active = len(grid_engine.active_orders) > 0

    # ── (f) TRENDING / IDLE + grid ON → cancel ──────────────────────────
    elif regime in ("TRENDING", "IDLE") and grid_active:
        logger.info("Regime %s — cancelling all grid orders.", regime)
        grid_engine.cancel_all_orders()
        grid_active = False

    # ── (g) State summary ────────────────────────────────────────────────
    usdt_balance  = connector.get_balance("USDT")
    daily_pnl     = profit_tracker.get_daily_pnl()
    open_orders   = len(grid_engine.active_orders)

    logger.info(
        "STATE | Regime=%-8s | Balance=$%.2f | OpenOrders=%d | DailyPnL=$%.4f",
        regime, usdt_balance, open_orders, daily_pnl,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Monthly settlement job
# ═══════════════════════════════════════════════════════════════════════════

def run_monthly_settlement() -> None:
    """
    Triggered on the last day of the month at 23:59 UTC.
    Deferred automatically if grid orders are still open.
    """
    logger.info("Running monthly settlement…")
    open_count = len(grid_engine.active_orders)
    result = wallet_manager.monthly_settlement(open_count)
    if result:
        alerter.send_monthly_report(
            result["profit"],
            result["withdrawal"],
            result["reinvestment"],
        )


# ═══════════════════════════════════════════════════════════════════════════
# Scheduler setup & entry point
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Initialise APScheduler, register jobs, and start the blocking loop."""
    scheduler = BlockingScheduler(timezone="UTC")

    # 15-minute trading cycle
    scheduler.add_job(
        run_cycle,
        trigger=IntervalTrigger(minutes=15),
        id="trading_cycle",
        name="Grid Trading Cycle (15 min)",
        max_instances=1,
        coalesce=True,
    )

    # Monthly settlement — last day of every month at 23:59 UTC
    scheduler.add_job(
        run_monthly_settlement,
        trigger=CronTrigger(day="last", hour=23, minute=59),
        id="monthly_settlement",
        name="Monthly Profit Settlement",
        max_instances=1,
    )

    logger.info("Scheduler ready. Running first cycle immediately…")
    # Fire once immediately so the bot doesn't sit idle for 15 minutes on startup
    run_cycle()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — shutting down cleanly.")
        if grid_active:
            logger.info("Cancelling all open grid orders before exit…")
            grid_engine.cancel_all_orders()
        scheduler.shutdown(wait=False)
        logger.info("Smart Grid Trader Pro stopped. Goodbye.")
        sys.exit(0)


if __name__ == "__main__":
    main()
