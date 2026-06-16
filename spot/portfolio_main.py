"""
portfolio_main.py
=================
Portfolio Profit Lock Grid Bot — Main Orchestration Loop

Runs multiple independent ATR-spaced grids across the top-N most liquid
coins simultaneously. Every 15 minutes it evaluates the COMBINED portfolio
PnL. The moment the total gain reaches the configured profit target
(expressed as % or fixed $), it:

  1. Cancels ALL open grid orders across ALL coins
  2. Logs the locked profit to SQLite
  3. Sends a Telegram notification
  4. Immediately starts a fresh cycle with new coin selection

Run with:
    python portfolio_main.py

Configuration is loaded from .env — see .env for all available keys.
"""

import logging
import os
import sys
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

# ── Project imports ─────────────────────────────────────────────────────────
from src.exchange_connector  import ExchangeConnector
from src.market_data         import MarketData
from src.regime_detector     import RegimeDetector
from src.grid_engine         import GridEngine
from src.coin_selector       import CoinSelector
from src.portfolio_engine    import PortfolioEngine
from src.portfolio_tracker   import PortfolioTracker
from src.telegram_alerts     import TelegramAlerter
from src.profit_tracker      import ProfitTracker
from api_server              import start_api_server

# ── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv()

os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join("logs", "portfolio_bot.log"), encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger("portfolio_main")

# ── Configuration from .env ──────────────────────────────────────────────────
NUM_COINS              = int(os.getenv("NUM_COINS",                    "3"))
GRID_LEVELS            = int(os.getenv("GRID_LEVELS",                  "6"))
CAPITAL_PER_GRID       = float(os.getenv("CAPITAL_PER_GRID",           "12.0"))
TARGET_MODE            = os.getenv("TARGET_MODE",                       "PCT")
PROFIT_TARGET_PCT      = float(os.getenv("PORTFOLIO_PROFIT_TARGET_PCT","0.005"))
PROFIT_TARGET_USD      = float(os.getenv("PORTFOLIO_PROFIT_TARGET_USD","2.0"))
MAX_DRAWDOWN_PCT       = float(os.getenv("PORTFOLIO_MAX_DRAWDOWN_PCT", "0.15"))
MAX_EXPOSURE_PER_COIN  = float(os.getenv("MAX_EXPOSURE_PER_COIN_PCT",  "0.30"))
INITIAL_CAPITAL        = float(os.getenv("INITIAL_BALANCE",            "100.0"))
MIN_24H_VOLUME         = float(os.getenv("MIN_24H_VOLUME_USDT",  "50000000.0"))

# ── Module initialisation ────────────────────────────────────────────────────
logger.info("=" * 60)
logger.info("  Portfolio Profit Lock Grid Bot — Starting Up")
logger.info("  Coins: %d  |  Target: %s  |  Capital: $%.2f",
            NUM_COINS, TARGET_MODE, INITIAL_CAPITAL)
logger.info("=" * 60)

connector        = ExchangeConnector()
market_data      = MarketData(connector)
regime_detector  = RegimeDetector()
coin_selector    = CoinSelector(connector, num_coins=NUM_COINS,
                                min_volume=MIN_24H_VOLUME)
portfolio_engine = PortfolioEngine(
    connector        = connector,
    starting_capital = INITIAL_CAPITAL,
    target_mode      = TARGET_MODE,
    target_pct       = PROFIT_TARGET_PCT,
    target_usd       = PROFIT_TARGET_USD,
    max_drawdown_pct = MAX_DRAWDOWN_PCT,
)
portfolio_tracker = PortfolioTracker()
profit_tracker    = ProfitTracker()
alerter           = TelegramAlerter()

# ── Per-coin GridEngine instances (created dynamically) ──────────────────────
# Dict: symbol → GridEngine
_grid_engines: dict[str, GridEngine] = {}
_active_coins: list[str]             = []
_cycle_start_capital: float          = INITIAL_CAPITAL


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _get_or_create_engine(symbol: str) -> GridEngine:
    """Return an existing GridEngine for *symbol*, creating one if needed."""
    if symbol not in _grid_engines:
        _grid_engines[symbol] = GridEngine(
            connector        = connector,
            symbol           = symbol,
            grid_levels      = GRID_LEVELS,
            capital_per_grid = CAPITAL_PER_GRID,
        )
    return _grid_engines[symbol]


def _cancel_all_coins() -> None:
    """Cancel every open grid order across ALL active coins."""
    for sym, eng in _grid_engines.items():
        if eng.active_orders:
            logger.info("Cancelling all orders for %s…", sym)
            eng.cancel_all_orders()


def _select_coins_and_start_cycle() -> None:
    """
    Select the top-N liquid coins, reset the portfolio engine,
    and prepare fresh GridEngine instances.
    """
    global _active_coins, _cycle_start_capital, _grid_engines, CAPITAL_PER_GRID

    usdt_balance = connector.get_balance("USDT")
    _cycle_start_capital = max(usdt_balance, 1.0)

    # Scale capital per grid level to strictly respect MAX_EXPOSURE_PER_COIN
    max_capital_per_coin = _cycle_start_capital * MAX_EXPOSURE_PER_COIN
    CAPITAL_PER_GRID     = max(12.0, max_capital_per_coin / GRID_LEVELS)

    coins = coin_selector.get_eligible_coins()
    if not coins:
        logger.warning("No eligible coins found — using previous selection.")
        return

    _active_coins.clear()
    _active_coins.extend(coins)
    _grid_engines.clear()
    portfolio_engine.reset_cycle(_cycle_start_capital)

    logger.info(
        "New cycle started | capital=%.2f USDT | coins=%s",
        _cycle_start_capital, _active_coins,
    )


def _liquidate_all_positions(positions: dict) -> None:
    """Execute market sell orders for all held coins to liquidate the portfolio."""
    for sym, pos in positions.items():
        qty = pos.get("qty", 0.0)
        if qty > 0:
            qty = connector.round_qty(qty, sym)
            price = connector.get_ticker_price(sym)
            if qty * price >= 10.0:  # Binance minimum notional ~10 USDT
                logger.info("Liquidating %.6f %s at market...", qty, sym)
                connector.place_market_sell(sym, qty)
            else:
                logger.warning("Skipping liquidation of %s (value < $10)", sym)


def _lock_profit(pnl_data: dict) -> None:
    """
    Execute the profit-lock sequence:
    1. Cancel all orders across all coins.
    2. Liquidate all held positions.
    3. Log the cycle to PortfolioTracker.
    4. Send Telegram alert.
    5. Start a fresh cycle.
    """
    logger.info("🔒 PROFIT TARGET REACHED — locking profit now…")

    # 1. Cancel all open grid orders
    _cancel_all_coins()

    # 2. Liquidate positions
    _liquidate_all_positions(pnl_data.get("positions", {}))

    # 3. Persist lock cycle
    cycle_id = portfolio_tracker.log_lock_cycle(
        coins_traded     = _active_coins,
        total_profit     = pnl_data["net_pnl"],
        profit_pct       = pnl_data["pct_gain"],
        starting_capital = _cycle_start_capital,
    )
    logger.info("Profit lock cycle #%d persisted (db id=%d).",
                portfolio_tracker.get_current_cycle_number(), cycle_id)

    # 3. Telegram alert
    today_cycles = portfolio_tracker.get_today_cycles()
    today_profit = portfolio_tracker.get_today_profit()
    alerter.alert_profit_locked(
        cycle_num    = portfolio_tracker.get_current_cycle_number(),
        coins        = _active_coins,
        net_pnl      = pnl_data["net_pnl"],
        pct_gain     = pnl_data["pct_gain"],
        today_cycles = today_cycles,
        today_profit = today_profit,
    )

    # 4. Start fresh
    _select_coins_and_start_cycle()


def _handle_safe_mode(pnl_data: dict) -> None:
    """Cancel all orders, liquidate, and alert on portfolio drawdown breach."""
    reason = (
        f"Portfolio drawdown {abs(pnl_data['pct_gain']) * 100:.2f}% "
        f"exceeds floor {MAX_DRAWDOWN_PCT * 100:.0f}%."
    )
    logger.warning("PORTFOLIO SAFE MODE: %s", reason)
    _cancel_all_coins()
    _liquidate_all_positions(pnl_data.get("positions", {}))
    alerter.alert_portfolio_safe_mode(
        reason       = reason,
        net_pnl      = pnl_data["net_pnl"],
        drawdown_pct = abs(pnl_data["pct_gain"]),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Core trading cycle
# ═══════════════════════════════════════════════════════════════════════════════

def run_cycle() -> None:
    """
    Execute one complete portfolio trading cycle. Called every 15 minutes.

    Flow for each coin:
      a) Fetch 100 × 1h OHLCV candles.
      b) Detect market regime (RANGING / TRENDING / IDLE).
      c) RANGING + no grid  → place fresh grid orders.
      d) RANGING + grid on  → check fills, record to PortfolioEngine.
      e) TRENDING / IDLE    → cancel grid orders for this coin.

    After processing all coins:
      f) Fetch current prices.
      g) Evaluate combined portfolio PnL.
      h) SAFE MODE: cancel everything and alert.
      i) TARGET HIT: lock profit, restart cycle.
      j) Log state summary.
    """
    logger.info("─" * 60)
    logger.info(
        "Portfolio cycle start — %s UTC | coins=%s",
        datetime.now(timezone.utc).strftime("%H:%M:%S"),
        _active_coins,
    )

    if not _active_coins:
        logger.warning("No active coins — running coin selection…")
        _select_coins_and_start_cycle()
        if not _active_coins:
            logger.error("Still no coins available. Skipping cycle.")
            return

    # ── (a–e) Per-coin grid management ──────────────────────────────────────
    for symbol in _active_coins:
        engine = _get_or_create_engine(symbol)

        # (a) Fetch OHLCV
        df = market_data.get_ohlcv(symbol, interval="1h", limit=100)
        if df.empty:
            logger.error("No OHLCV data for %s — skipping.", symbol)
            continue

        # (b) Detect regime
        regime_data   = regime_detector.detect(df)
        regime        = regime_data["regime"]
        atr           = regime_data["atr"]
        current_price = connector.get_ticker_price(symbol)

        if current_price <= 0:
            logger.error("Invalid price for %s — skipping.", symbol)
            continue

        # (c) RANGING + no grid → place orders
        if regime == "RANGING" and not engine.active_orders:
            logger.info("[%s] RANGING — placing fresh grid orders.", symbol)
            engine.place_grid_orders(current_price, atr)

        # (d) RANGING + grid on → check fills
        elif regime == "RANGING" and engine.active_orders:
            if not engine.is_price_in_range(current_price):
                logger.info("[%s] Price outside grid — rebuilding.", symbol)
                engine.cancel_all_orders()
                engine.place_grid_orders(current_price, atr)
            else:
                filled_orders = engine.check_and_refresh_orders()
                for order in filled_orders:
                    fee = order["price"] * order["qty"] * 0.001
                    portfolio_engine.record_fill(
                        symbol = symbol,
                        side   = order["side"],
                        price  = order["price"],
                        qty    = order["qty"],
                        fee    = fee,
                    )

        # (e) TRENDING / IDLE → cancel
        elif regime in ("TRENDING", "IDLE") and engine.active_orders:
            logger.info("[%s] Regime %s — cancelling grid orders.", symbol, regime)
            engine.cancel_all_orders()

    # ── (f) Fetch current prices ─────────────────────────────────────────────
    current_prices = coin_selector.get_coin_prices(_active_coins)

    # ── (g) Evaluate combined portfolio PnL ──────────────────────────────────
    pnl_data = portfolio_engine.calculate_pnl(current_prices)

    # ── (h) Safe mode check ───────────────────────────────────────────────────
    if pnl_data["safe_mode"]:
        _handle_safe_mode(pnl_data)
        return

    # ── (i) Profit lock check ─────────────────────────────────────────────────
    if pnl_data["should_lock"]:
        _lock_profit(pnl_data)
        return

    # ── (j) State summary ─────────────────────────────────────────────────────
    total_open_orders = sum(
        len(eng.active_orders) for eng in _grid_engines.values()
    )
    logger.info(
        "STATE | NetPnL=%+.4f USDT (%.3f%%) | OpenOrders=%d | "
        "Target=%s | TodayLocks=%d",
        pnl_data["net_pnl"],
        pnl_data["pct_gain"] * 100,
        total_open_orders,
        portfolio_engine.target_description(),
        portfolio_tracker.get_today_cycles(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler setup & entry point
# ═══════════════════════════════════════════════════════════════════════════════

def _api_force_profit_lock() -> None:
    """Callback: force profit lock from the API."""
    current_prices = coin_selector.get_coin_prices(_active_coins)
    pnl_data = portfolio_engine.calculate_pnl(current_prices)
    if pnl_data.get("should_lock") or True:
        _lock_profit(pnl_data)
    else:
        logger.info("API force profit lock: target not reached, locking anyway.")


def _api_panic_liquidate() -> None:
    """Callback: emergency liquidation from the API."""
    logger.warning("API panic liquidation triggered!")
    _cancel_all_coins()
    current_prices = coin_selector.get_coin_prices(_active_coins)
    pnl_data = portfolio_engine.calculate_pnl(current_prices)
    _liquidate_all_positions(pnl_data.get("positions", {}))
    alerter.alert_portfolio_safe_mode(
        reason="Manual panic liquidation via API",
        net_pnl=pnl_data.get("net_pnl", 0.0),
        drawdown_pct=abs(pnl_data.get("pct_gain", 0.0)),
    )


def main() -> None:
    """Initialise the scheduler, select the first coin set, and start the loop."""
    # Run initial coin selection before the scheduler starts
    _select_coins_and_start_cycle()

    # ── Start REST API server in background ──────────────────────────────────
    api_port = int(os.getenv("PORT", "8000"))
    start_api_server(
        port=api_port,
        connector=connector,
        market_data=market_data,
        regime_detector=regime_detector,
        coin_selector=coin_selector,
        portfolio_engine=portfolio_engine,
        portfolio_tracker=portfolio_tracker,
        profit_tracker=profit_tracker,
        risk_manager=None,
        alerter=alerter,
        grid_engines_ref=_grid_engines,
        active_coins_ref=_active_coins,
        cycle_capital_ref=_cycle_start_capital,
        on_force_profit_lock=_api_force_profit_lock,
        on_panic_liquidate=_api_panic_liquidate,
    )

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_cycle,
        trigger   = IntervalTrigger(minutes=15),
        id        = "portfolio_cycle",
        name      = "Portfolio Profit Lock Cycle (15 min)",
        max_instances = 1,
        coalesce  = True,
    )

    logger.info("Scheduler ready. Running first portfolio cycle immediately…")
    logger.info(
        "Profit target: %s | Max drawdown: %.0f%%",
        portfolio_engine.target_description(),
        MAX_DRAWDOWN_PCT * 100,
    )

    # Fire once immediately
    run_cycle()

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt — shutting down cleanly.")
        _cancel_all_coins()
        scheduler.shutdown(wait=False)
        logger.info("Portfolio Profit Lock Grid Bot stopped. Goodbye.")
        sys.exit(0)


if __name__ == "__main__":
    main()
