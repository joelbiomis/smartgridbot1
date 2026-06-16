package com.example.api

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

// ── /api/health ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class HealthResponse(
    @Json(name = "status") val status: String,
    @Json(name = "timestamp") val timestamp: String,
    @Json(name = "exchange_connected") val exchangeConnected: Boolean,
)

// ── /api/status ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class StatusResponse(
    @Json(name = "bot_status") val botStatus: String,
    @Json(name = "regime") val regime: String,
    @Json(name = "adx") val adx: Double,
    @Json(name = "atr") val atr: Double,
    @Json(name = "bb_width") val bbWidth: Double,
    @Json(name = "active_coins") val activeCoins: List<String>,
    @Json(name = "grid_active") val gridActive: Boolean,
    @Json(name = "total_open_orders") val totalOpenOrders: Int,
    @Json(name = "current_cycle") val currentCycle: Int,
    @Json(name = "timestamp") val timestamp: String,
)

// ── /api/portfolio ───────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class PortfolioResponse(
    @Json(name = "total_equity") val totalEquity: Double,
    @Json(name = "usdt_balance") val usdtBalance: Double,
    @Json(name = "starting_capital") val startingCapital: Double,
    @Json(name = "net_pnl") val netPnl: Double,
    @Json(name = "realized_pnl") val realizedPnl: Double,
    @Json(name = "unrealized_pnl") val unrealizedPnl: Double,
    @Json(name = "total_fees") val totalFees: Double,
    @Json(name = "pct_gain") val pctGain: Double,
    @Json(name = "should_lock") val shouldLock: Boolean,
    @Json(name = "safe_mode") val safeMode: Boolean,
    @Json(name = "profit_lock_progress") val profitLockProgress: Double,
    @Json(name = "target_description") val targetDescription: String,
    @Json(name = "today_cycles") val todayCycles: Int,
    @Json(name = "today_profit") val todayProfit: Double,
    @Json(name = "total_locked_profit") val totalLockedProfit: Double,
    @Json(name = "positions") val positions: Map<String, PositionData>,
)

@JsonClass(generateAdapter = true)
data class PositionData(
    @Json(name = "qty") val qty: Double,
    @Json(name = "avg_cost") val avgCost: Double,
)

// ── /api/prices ──────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class PricesResponse(
    @Json(name = "prices") val prices: Map<String, Double>,
    @Json(name = "timestamp") val timestamp: String,
)

// ── /api/transactions ────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class TransactionsResponse(
    @Json(name = "trades") val trades: List<Any>,
    @Json(name = "lock_cycles") val lockCycles: List<LockCycleData>,
    @Json(name = "equity_curve") val equityCurve: List<EquityPoint>,
    @Json(name = "total_trades") val totalTrades: Int,
)

@JsonClass(generateAdapter = true)
data class LockCycleData(
    @Json(name = "cycle_number") val cycleNumber: Int,
    @Json(name = "timestamp") val timestamp: String,
    @Json(name = "coins_traded") val coinsTraded: List<String>,
    @Json(name = "total_profit") val totalProfit: Double,
    @Json(name = "profit_pct") val profitPct: Double,
)

@JsonClass(generateAdapter = true)
data class EquityPoint(
    @Json(name = "date") val date: String,
    @Json(name = "cumulative_pnl") val cumulativePnl: Double,
)

// ── /api/grid ────────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class GridResponse(
    @Json(name = "symbol") val symbol: String,
    @Json(name = "grid_levels") val gridLevels: Int,
    @Json(name = "capital_per_grid") val capitalPerGrid: Double,
    @Json(name = "current_price") val currentPrice: Double,
    @Json(name = "active_orders") val activeOrders: List<GridOrderData>,
    @Json(name = "buy_levels") val buyLevels: List<Double>,
    @Json(name = "sell_levels") val sellLevels: List<Double>,
)

@JsonClass(generateAdapter = true)
data class GridOrderData(
    @Json(name = "order_id") val orderId: Long,
    @Json(name = "side") val side: String,
    @Json(name = "price") val price: Double,
    @Json(name = "qty") val qty: Double,
    @Json(name = "status") val status: String,
)

// ── /api/settings ────────────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class SettingsResponse(
    @Json(name = "num_coins") val numCoins: Int,
    @Json(name = "grid_levels") val gridLevels: Int,
    @Json(name = "capital_per_grid") val capitalPerGrid: Double,
    @Json(name = "target_mode") val targetMode: String,
    @Json(name = "profit_target_pct") val profitTargetPct: Double,
    @Json(name = "profit_target_usd") val profitTargetUsd: Double,
    @Json(name = "max_drawdown_pct") val maxDrawdownPct: Double,
    @Json(name = "max_exposure_per_coin_pct") val maxExposurePerCoinPct: Double,
    @Json(name = "initial_balance") val initialBalance: Double,
    @Json(name = "min_24h_volume_usdt") val min24hVolumeUsdt: Double,
    @Json(name = "trading_symbol") val tradingSymbol: String,
    @Json(name = "exchange_connected") val exchangeConnected: Boolean,
    @Json(name = "api_key_configured") val apiKeyConfigured: Boolean,
    @Json(name = "telegram_configured") val telegramConfigured: Boolean,
)

// ── POST /api/settings (body + response) ─────────────────────────────────────

data class SettingsUpdateBody(
    @Json(name = "num_coins") val numCoins: Int? = null,
    @Json(name = "grid_levels") val gridLevels: Int? = null,
    @Json(name = "capital_per_grid") val capitalPerGrid: Double? = null,
    @Json(name = "target_mode") val targetMode: String? = null,
    @Json(name = "profit_target_pct") val profitTargetPct: Double? = null,
    @Json(name = "profit_target_usd") val profitTargetUsd: Double? = null,
    @Json(name = "max_drawdown_pct") val maxDrawdownPct: Double? = null,
    @Json(name = "max_exposure_per_coin_pct") val maxExposurePerCoinPct: Double? = null,
    @Json(name = "api_key") val apiKey: String? = null,
    @Json(name = "api_secret") val apiSecret: String? = null,
    @Json(name = "push_notifications") val pushNotifications: Boolean? = null,
)

// ── /api/actions/test-connection ─────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class TestConnectionResponse(
    @Json(name = "status") val status: String,
    @Json(name = "connected") val connected: Boolean,
    @Json(name = "usdt_balance") val usdtBalance: Double,
    @Json(name = "message") val message: String,
)

// ── /api/actions/* responses ─────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class GenericActionResponse(
    @Json(name = "status") val status: String,
    @Json(name = "message") val message: String,
)

// ── /api/analytics/pnl ───────────────────────────────────────────────────────

@JsonClass(generateAdapter = true)
data class AnalyticsPnlResponse(
    @Json(name = "timeframe") val timeframe: String,
    @Json(name = "monthly_profit") val monthlyProfit: Double,
    @Json(name = "daily_pnl") val dailyPnl: Double,
    @Json(name = "total_trades") val totalTrades: Int,
    @Json(name = "total_cycles") val totalCycles: Int,
    @Json(name = "win_ratio") val winRatio: Double,
    @Json(name = "equity_curve") val equityCurve: List<EquityPoint>,
)
