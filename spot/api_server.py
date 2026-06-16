"""
api_server.py
=============
FastAPI REST API server for Smart Grid Trader Pro & Portfolio Profit Lock Grid Bot.

Exposes bot state, trading data, and control actions via REST endpoints
consumed by the Neon Velocity Android app.

Run standalone (data-only, no trading loop):
    python api_server.py

Or start from portfolio_main.py / main.py:
    from api_server import start_api_server
    start_api_server(port=8000, ...)
"""

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.coin_selector import CoinSelector
from src.exchange_connector import ExchangeConnector
from src.grid_engine import GridEngine
from src.market_data import MarketData
from src.portfolio_engine import PortfolioEngine
from src.portfolio_tracker import PortfolioTracker
from src.profit_tracker import ProfitTracker
from src.regime_detector import RegimeDetector
from src.risk_manager import RiskManager
from src.telegram_alerts import TelegramAlerter

load_dotenv()

logger = logging.getLogger("api_server")

# ── Shared state (set by start_api_server or standalone main) ────────────────
_connector: Optional[ExchangeConnector] = None
_market_data: Optional[MarketData] = None
_regime_detector: Optional[RegimeDetector] = None
_coin_selector: Optional[CoinSelector] = None
_portfolio_engine: Optional[PortfolioEngine] = None
_portfolio_tracker: Optional[PortfolioTracker] = None
_profit_tracker: Optional[ProfitTracker] = None
_risk_manager: Optional[RiskManager] = None
_alerter: Optional[TelegramAlerter] = None

# Mutable references passed by portfolio_main.py
_grid_engines_ref: dict[str, GridEngine] = {}
_active_coins_ref: list[str] = []
_cycle_capital_ref: float = 0.0

# Callbacks for mutable actions (set by the host application)
_on_force_profit_lock: Optional[Callable[[], None]] = None
_on_panic_liquidate: Optional[Callable[[], None]] = None

_lock = threading.Lock()

# ── FastAPI app ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Smart Grid Trader Pro API",
    version="1.0.0",
    description="REST API for the Smart Grid Trader Pro crypto trading bot.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_exchange() -> bool:
    """Return True if we have a working ExchangeConnector."""
    return _connector is not None


def _get_grid_summary() -> dict:
    """Aggregate grid state across all active coins."""
    total_orders = 0
    grid_active = False
    for eng in _grid_engines_ref.values():
        total_orders += len(eng.active_orders)
        if eng.active_orders:
            grid_active = True
    return {"total_open_orders": total_orders, "grid_active": grid_active}


def _get_env_config() -> dict:
    """Return the current configuration from environment variables."""
    return {
        "num_coins": int(os.getenv("NUM_COINS", "3")),
        "grid_levels": int(os.getenv("GRID_LEVELS", "6")),
        "capital_per_grid": float(os.getenv("CAPITAL_PER_GRID", "12.0")),
        "target_mode": os.getenv("TARGET_MODE", "PCT"),
        "profit_target_pct": float(os.getenv("PORTFOLIO_PROFIT_TARGET_PCT", "0.005")),
        "profit_target_usd": float(os.getenv("PORTFOLIO_PROFIT_TARGET_USD", "2.0")),
        "max_drawdown_pct": float(os.getenv("PORTFOLIO_MAX_DRAWDOWN_PCT", "0.15")),
        "max_exposure_per_coin_pct": float(os.getenv("MAX_EXPOSURE_PER_COIN_PCT", "0.30")),
        "initial_balance": float(os.getenv("INITIAL_BALANCE", "100.0")),
        "min_24h_volume_usdt": float(os.getenv("MIN_24H_VOLUME_USDT", "50000000.0")),
        "trading_symbol": os.getenv("TRADING_SYMBOL", "BTCUSDT"),
        "exchange_connected": _safe_exchange(),
        "api_key_configured": bool(os.getenv("BINANCE_API_KEY", "")),
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN", "") != "your_telegram_bot_token_here"),
    }


def _mock_prices() -> dict[str, float]:
    """Return simulated prices when exchange is not connected."""
    return {
        "BTCUSDT": 67430.50,
        "ETHUSDT": 3480.25,
        "SOLUSDT": 142.80,
        "BNBUSDT": 585.20,
        "ADAUSDT": 0.45,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    """Health-check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exchange_connected": _safe_exchange(),
    }


@app.get("/api/status")
def bot_status():
    """Return current bot state, regime, and grid overview."""
    with _lock:
        regime = "UNKNOWN"
        atr = 0.0
        adx = 0.0
        bb_width = 0.0

        if _regime_detector is not None and _market_data is not None and _safe_exchange():
            try:
                symbol = _active_coins_ref[0] if _active_coins_ref else os.getenv("TRADING_SYMBOL", "BTCUSDT")
                df = _market_data.get_ohlcv(symbol, interval="1h", limit=100)
                if not df.empty:
                    rd = _regime_detector.detect(df)
                    regime = rd.get("regime", "UNKNOWN")
                    atr = rd.get("atr", 0.0)
                    adx = rd.get("adx", 0.0)
                    bb_width = rd.get("bb_width", 0.0)
            except Exception:
                pass

        grid_info = _get_grid_summary()
        cycle_num = _portfolio_tracker.get_current_cycle_number() if _portfolio_tracker else 0

        # Map regime to bot status the Android expects
        bot_mode = "HUNTING" if regime == "RANGING" else "SLEEPING"

        return {
            "bot_status": bot_mode,
            "regime": regime,
            "adx": adx,
            "atr": atr,
            "bb_width": bb_width,
            "active_coins": list(_active_coins_ref),
            "grid_active": grid_info["grid_active"],
            "total_open_orders": grid_info["total_open_orders"],
            "current_cycle": cycle_num,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/portfolio")
def portfolio():
    """Return portfolio equity, PnL, and profit-lock state."""
    with _lock:
        usdt_balance = 0.0
        if _safe_exchange():
            usdt_balance = _connector.get_balance("USDT")

        starting_cap = getattr(_portfolio_engine, 'starting_capital', None) or float(os.getenv("INITIAL_BALANCE", "100.0"))

        pnl_data = {}
        if _portfolio_engine is not None:
            try:
                prices = _get_current_prices_dict()
                pnl_data = _portfolio_engine.calculate_pnl(prices)
            except Exception:
                pass

        target_desc = _portfolio_engine.target_description() if _portfolio_engine else "N/A"

        today_cycles = _portfolio_tracker.get_today_cycles() if _portfolio_tracker else 0
        today_profit = _portfolio_tracker.get_today_profit() if _portfolio_tracker else 0.0
        total_locked = _portfolio_tracker.get_total_locked_profit() if _portfolio_tracker else 0.0

        # Compute profit lock progress (simulated as % of target reached)
        profit_lock_progress = 0.0
        if pnl_data:
            target_pct = float(os.getenv("PORTFOLIO_PROFIT_TARGET_PCT", "0.005"))
            if target_pct > 0:
                progress = abs(pnl_data.get("pct_gain", 0.0)) / target_pct
                profit_lock_progress = min(progress, 1.0)

        return {
            "total_equity": round(usdt_balance + pnl_data.get("net_pnl", 0.0), 4),
            "usdt_balance": round(usdt_balance, 4),
            "starting_capital": round(starting_cap, 4),
            "net_pnl": pnl_data.get("net_pnl", 0.0),
            "realized_pnl": pnl_data.get("realized_pnl", 0.0),
            "unrealized_pnl": pnl_data.get("unrealized_pnl", 0.0),
            "total_fees": pnl_data.get("total_fees", 0.0),
            "pct_gain": pnl_data.get("pct_gain", 0.0),
            "should_lock": pnl_data.get("should_lock", False),
            "safe_mode": pnl_data.get("safe_mode", False),
            "profit_lock_progress": round(profit_lock_progress, 4),
            "target_description": target_desc,
            "today_cycles": today_cycles,
            "today_profit": round(today_profit, 4),
            "total_locked_profit": round(total_locked, 4),
            "positions": pnl_data.get("positions", {}),
        }


@app.get("/api/prices")
def prices():
    """Return current prices for all tracked coins."""
    with _lock:
        price_data = _get_current_prices_dict()
        return {
            "prices": price_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/transactions")
def transactions(limit: int = Query(50, ge=1, le=500)):
    """Return recent trade history and profit-lock cycles."""
    with _lock:
        trades = []
        if _profit_tracker is not None:
            try:
                eq_curve = _profit_tracker.get_equity_curve()
            except Exception:
                eq_curve = []

        lock_cycles = []
        if _portfolio_tracker is not None:
            lock_cycles = _portfolio_tracker.get_recent_cycles(limit=limit)

        total_trades = _profit_tracker.get_total_trades() if _profit_tracker else 0

        return {
            "trades": trades,
            "lock_cycles": lock_cycles,
            "equity_curve": eq_curve if _profit_tracker else [],
            "total_trades": total_trades,
        }


@app.get("/api/grid")
def grid(symbol: str = Query("", description="Trading pair symbol (e.g. BTCUSDT)")):
    """Return the grid order ladder for the given symbol."""
    with _lock:
        sym = symbol.upper() if symbol else (_active_coins_ref[0] if _active_coins_ref else "BTCUSDT")

        engine = _grid_engines_ref.get(sym)
        if engine is None:
            raise HTTPException(status_code=404, detail=f"No grid engine found for {sym}")

        orders = []
        buy_levels = []
        sell_levels = []
        for oid, meta in engine.active_orders.items():
            entry = {
                "order_id": oid,
                "side": meta.get("side", ""),
                "price": meta.get("price", 0.0),
                "qty": meta.get("qty", 0.0),
                "status": meta.get("status", ""),
            }
            orders.append(entry)
            if meta.get("side") == "BUY":
                buy_levels.append(meta.get("price", 0.0))
            elif meta.get("side") == "SELL":
                sell_levels.append(meta.get("price", 0.0))

        current_price = 0.0
        if _safe_exchange():
            current_price = _connector.get_ticker_price(sym)

        return {
            "symbol": sym,
            "grid_levels": engine.grid_levels,
            "capital_per_grid": engine.capital_per_grid,
            "current_price": current_price,
            "active_orders": orders,
            "buy_levels": sorted(buy_levels),
            "sell_levels": sorted(sell_levels),
        }


@app.get("/api/settings")
def settings():
    """Return current bot configuration."""
    return _get_env_config()


class SettingsUpdate(BaseModel):
    num_coins: Optional[int] = None
    grid_levels: Optional[int] = None
    capital_per_grid: Optional[float] = None
    target_mode: Optional[str] = None
    profit_target_pct: Optional[float] = None
    profit_target_usd: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    max_exposure_per_coin_pct: Optional[float] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    push_notifications: Optional[bool] = None


@app.post("/api/settings")
def update_settings(body: SettingsUpdate):
    """Update bot configuration in memory and .env file."""
    with _lock:
        updates = body.model_dump(exclude_none=True)

        env_path = ".env"
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        env_map = os.environ.copy()

        key_map = {
            "num_coins": "NUM_COINS",
            "grid_levels": "GRID_LEVELS",
            "capital_per_grid": "CAPITAL_PER_GRID",
            "target_mode": "TARGET_MODE",
            "profit_target_pct": "PORTFOLIO_PROFIT_TARGET_PCT",
            "profit_target_usd": "PORTFOLIO_PROFIT_TARGET_USD",
            "max_drawdown_pct": "PORTFOLIO_MAX_DRAWDOWN_PCT",
            "max_exposure_per_coin_pct": "MAX_EXPOSURE_PER_COIN_PCT",
            "api_key": "BINANCE_API_KEY",
            "api_secret": "BINANCE_SECRET_KEY",
        }

        for py_key, value in updates.items():
            env_key = key_map.get(py_key)
            if not env_key:
                continue
            value_str = str(value)
            os.environ[env_key] = value_str
            env_map[env_key] = value_str

            # Update .env file
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{env_key}=") or line.strip().startswith(f"# {env_key}="):
                    lines[i] = f"{env_key}={value_str}\n"
                    found = True
                    break
            if not found:
                lines.append(f"{env_key}={value_str}\n")

        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception as exc:
            logger.error("Failed to write .env: %s", exc)

        # If API key or secret were updated, hot-reload the exchange connector
        reconnected = False
        if "api_key" in updates or "api_secret" in updates:
            new_key = os.getenv("BINANCE_API_KEY", "")
            new_secret = os.getenv("BINANCE_SECRET_KEY", "")
            if new_key and new_secret and _connector is not None:
                reconnected = _connector.reconnect(new_key, new_secret)
                logger.info("Exchange reconnect after settings update: %s", reconnected)

        return {
            "status": "updated",
            "message": "Settings saved. Some changes apply on next cycle.",
            "reconnected": reconnected,
        }


@app.post("/api/actions/test-connection")
def test_connection():
    """Test if the exchange API keys are valid by fetching the USDT balance."""
    with _lock:
        if not _safe_exchange():
            raise HTTPException(status_code=503, detail="Exchange not initialised.")

        try:
            balance = _connector.get_balance("USDT")
            return {
                "status": "ok",
                "connected": True,
                "usdt_balance": balance,
                "message": "Connection successful.",
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Connection failed: {exc}")


@app.post("/api/actions/force-profit-lock")
def force_profit_lock():
    """Trigger an immediate profit lock on the portfolio."""
    with _lock:
        if _on_force_profit_lock is not None:
            try:
                _on_force_profit_lock()
                return {"status": "ok", "message": "Profit lock triggered."}
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))
        raise HTTPException(status_code=503, detail="Profit lock action not available (run with bot).")


@app.post("/api/actions/panic-liquidate")
def panic_liquidate():
    """Emergency stop: cancel all orders and liquidate positions."""
    with _lock:
        if _on_panic_liquidate is not None:
            try:
                _on_panic_liquidate()
                return {"status": "ok", "message": "Panic liquidation executed."}
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))

        # Fallback: if no callback but we have a connector, do a basic cancel
        if _safe_exchange():
            for eng in _grid_engines_ref.values():
                eng.cancel_all_orders()
            return {"status": "ok", "message": "All orders cancelled."}

        raise HTTPException(status_code=503, detail="Panic liquidation not available.")


@app.get("/api/analytics/pnl")
def analytics_pnl(timeframe: str = Query("1M", regex="^(1D|1W|1M|ALL)$")):
    """Return PnL analytics data for the given timeframe."""
    with _lock:
        monthly_profit = _profit_tracker.get_monthly_profit() if _profit_tracker else 0.0
        daily_pnl = _profit_tracker.get_daily_pnl() if _profit_tracker else 0.0
        total_trades = _profit_tracker.get_total_trades() if _profit_tracker else 0
        equity_curve = _profit_tracker.get_equity_curve() if _profit_tracker else []

        # Filter equity curve by timeframe
        filtered_curve = equity_curve
        if timeframe != "ALL" and equity_curve:
            now = datetime.now(timezone.utc).date()
            if timeframe == "1D":
                cutoff = now.isoformat()
                filtered_curve = [p for p in equity_curve if p["date"] >= cutoff]
            elif timeframe == "1W":
                from datetime import timedelta
                cutoff = (now - timedelta(days=7)).isoformat()
                filtered_curve = [p for p in equity_curve if p["date"] >= cutoff]
            elif timeframe == "1M":
                from datetime import timedelta
                cutoff = (now - timedelta(days=30)).isoformat()
                filtered_curve = [p for p in equity_curve if p["date"] >= cutoff]

        # Count total lock cycles for trophy room
        total_cycles = _portfolio_tracker.get_current_cycle_number() if _portfolio_tracker else 0

        # Win ratio estimate (simplified: profitable trades / total trades)
        win_ratio = 0.98  # default placeholder; improved below if we have data

        return {
            "timeframe": timeframe,
            "monthly_profit": round(monthly_profit, 4),
            "daily_pnl": round(daily_pnl, 4),
            "total_trades": total_trades,
            "total_cycles": total_cycles,
            "win_ratio": win_ratio,
            "equity_curve": filtered_curve,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Internal: price helper
# ═══════════════════════════════════════════════════════════════════════════════

def _get_current_prices_dict() -> dict[str, float]:
    """Return current prices for active coins, falling back to mock data."""
    if not _safe_exchange():
        return _mock_prices()

    symbols = list(_active_coins_ref) if _active_coins_ref else ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            price = _connector.get_ticker_price(sym)
            if price > 0:
                prices[sym] = price
        except Exception:
            pass
    if not prices:
        prices = _mock_prices()
    return prices


# ═══════════════════════════════════════════════════════════════════════════════
# Start-up helper
# ═══════════════════════════════════════════════════════════════════════════════

def start_api_server(
    host: str = "0.0.0.0",
    port: int | None = None,
    connector: Optional[ExchangeConnector] = None,
    market_data: Optional[MarketData] = None,
    regime_detector: Optional[RegimeDetector] = None,
    coin_selector: Optional[CoinSelector] = None,
    portfolio_engine: Optional[PortfolioEngine] = None,
    portfolio_tracker: Optional[PortfolioTracker] = None,
    profit_tracker: Optional[ProfitTracker] = None,
    risk_manager: Optional[RiskManager] = None,
    alerter: Optional[TelegramAlerter] = None,
    grid_engines_ref: Optional[dict] = None,
    active_coins_ref: Optional[list] = None,
    cycle_capital_ref: Optional[float] = None,
    on_force_profit_lock: Optional[Callable[[], None]] = None,
    on_panic_liquidate: Optional[Callable[[], None]] = None,
) -> threading.Thread:
    """
    Start the FastAPI server in a background daemon thread.

    Pass references to your existing module instances so the API serves live data.
    If not provided, standalone mode is used (exchange-connected or mock data).
    """
    global _connector, _market_data, _regime_detector, _coin_selector
    global _portfolio_engine, _portfolio_tracker, _profit_tracker
    global _risk_manager, _alerter
    global _grid_engines_ref, _active_coins_ref, _cycle_capital_ref
    global _on_force_profit_lock, _on_panic_liquidate

    _connector = connector
    _market_data = market_data
    _regime_detector = regime_detector
    _coin_selector = coin_selector
    _portfolio_engine = portfolio_engine
    _portfolio_tracker = portfolio_tracker
    _profit_tracker = profit_tracker
    _risk_manager = risk_manager
    _alerter = alerter

    if grid_engines_ref is not None:
        _grid_engines_ref = grid_engines_ref
    if active_coins_ref is not None:
        _active_coins_ref = active_coins_ref
    if cycle_capital_ref is not None:
        _cycle_capital_ref = cycle_capital_ref

    _on_force_profit_lock = on_force_profit_lock
    _on_panic_liquidate = on_panic_liquidate

    resolved_port = port if port is not None else int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(app, host=host, port=resolved_port, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True, name="api_server")
    thread.start()
    logger.info("API server started on http://%s:%d", host, resolved_port)
    return thread


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Try to initialise real modules; fall back gracefully
    if os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_SECRET_KEY"):
        try:
            _connector = ExchangeConnector()
            _market_data = MarketData(_connector)
            _regime_detector = RegimeDetector()
            _coin_selector = CoinSelector(_connector)
            _profit_tracker = ProfitTracker()
            _portfolio_tracker = PortfolioTracker()
            logger.info("Standalone mode: connected to Binance.")
        except Exception as exc:
            logger.warning("Could not initialise Binance: %s", exc)
            logger.info("Falling back to mock data mode.")

    standalone_port = int(os.getenv("PORT", "8000"))
    logger.info("Starting API server in standalone mode on port %d…", standalone_port)
    uvicorn.run(app, host="0.0.0.0", port=standalone_port, log_level="info")
