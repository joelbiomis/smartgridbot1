package com.example.data

import com.example.api.*

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(val message: String, val exception: Throwable? = null) : ApiResult<Nothing>()
}

class BotRepository {
    private val api: BotApiService get() = ServerConfig.api

    // ── helpers ──────────────────────────────────────────────────────────────

    private suspend fun <T> safeCall(block: suspend () -> T): ApiResult<T> {
        return try {
            ApiResult.Success(block())
        } catch (e: Exception) {
            ApiResult.Error(e.message ?: "Unknown error", e)
        }
    }

    // ── endpoints ────────────────────────────────────────────────────────────

    suspend fun health(): ApiResult<HealthResponse> = safeCall { api.health() }

    suspend fun getStatus(): ApiResult<StatusResponse> = safeCall { api.getStatus() }

    suspend fun getPortfolio(): ApiResult<PortfolioResponse> = safeCall { api.getPortfolio() }

    suspend fun getPrices(): ApiResult<PricesResponse> = safeCall { api.getPrices() }

    suspend fun getTransactions(limit: Int = 50): ApiResult<TransactionsResponse> =
        safeCall { api.getTransactions(limit) }

    suspend fun getGrid(symbol: String = ""): ApiResult<GridResponse> =
        safeCall { api.getGrid(symbol) }

    suspend fun getSettings(): ApiResult<SettingsResponse> = safeCall { api.getSettings() }

    suspend fun updateSettings(body: SettingsUpdateBody): ApiResult<GenericActionResponse> =
        safeCall { api.updateSettings(body) }

    suspend fun testConnection(): ApiResult<TestConnectionResponse> =
        safeCall { api.testConnection() }

    suspend fun forceProfitLock(): ApiResult<GenericActionResponse> =
        safeCall { api.forceProfitLock() }

    suspend fun panicLiquidate(): ApiResult<GenericActionResponse> =
        safeCall { api.panicLiquidate() }

    suspend fun getAnalyticsPnl(timeframe: String = "1M"): ApiResult<AnalyticsPnlResponse> =
        safeCall { api.getAnalyticsPnl(timeframe) }
}
