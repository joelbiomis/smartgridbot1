package com.example.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface BotApiService {

    @GET("api/health")
    suspend fun health(): HealthResponse

    @GET("api/status")
    suspend fun getStatus(): StatusResponse

    @GET("api/portfolio")
    suspend fun getPortfolio(): PortfolioResponse

    @GET("api/prices")
    suspend fun getPrices(): PricesResponse

    @GET("api/transactions")
    suspend fun getTransactions(
        @Query("limit") limit: Int = 50,
    ): TransactionsResponse

    @GET("api/grid")
    suspend fun getGrid(
        @Query("symbol") symbol: String = "",
    ): GridResponse

    @GET("api/settings")
    suspend fun getSettings(): SettingsResponse

    @POST("api/settings")
    suspend fun updateSettings(
        @Body body: SettingsUpdateBody,
    ): GenericActionResponse

    @POST("api/actions/test-connection")
    suspend fun testConnection(): TestConnectionResponse

    @POST("api/actions/force-profit-lock")
    suspend fun forceProfitLock(): GenericActionResponse

    @POST("api/actions/panic-liquidate")
    suspend fun panicLiquidate(): GenericActionResponse

    @GET("api/analytics/pnl")
    suspend fun getAnalyticsPnl(
        @Query("timeframe") timeframe: String = "1M",
    ): AnalyticsPnlResponse
}
