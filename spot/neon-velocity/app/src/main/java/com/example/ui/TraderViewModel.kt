package com.example.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.api.*
import com.example.data.AppDatabase
import com.example.data.BotRepository
import com.example.data.Transaction
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch


class TraderViewModel(application: Application) : AndroidViewModel(application) {
    private val db = AppDatabase.getDatabase(application)
    private val dao = db.transactionDao()
    private val repository = BotRepository()

    // ── Dashboard ─────────────────────────────────────────────────────────────

    private val _totalEquity = MutableStateFlow(1050.45)
    val totalEquity: StateFlow<Double> = _totalEquity.asStateFlow()

    private val _profitLockProgress = MutableStateFlow(0.0f)
    val profitLockProgress: StateFlow<Float> = _profitLockProgress.asStateFlow()

    private val _botStatus = MutableStateFlow("SLEEPING")
    val botStatus: StateFlow<String> = _botStatus.asStateFlow()

    private val _btcPrice = MutableStateFlow(0.0)
    val btcPrice: StateFlow<Double> = _btcPrice.asStateFlow()

    private val _ethPrice = MutableStateFlow(0.0)
    val ethPrice: StateFlow<Double> = _ethPrice.asStateFlow()

    private val _solPrice = MutableStateFlow(0.0)
    val solPrice: StateFlow<Double> = _solPrice.asStateFlow()

    // ── Grid Radar ────────────────────────────────────────────────────────────

    private val _selectedRadarCoin = MutableStateFlow("BTC/USDT")
    val selectedRadarCoin: StateFlow<String> = _selectedRadarCoin.asStateFlow()

    private val _gridData = MutableStateFlow<GridResponse?>(null)
    val gridData: StateFlow<GridResponse?> = _gridData.asStateFlow()

    // ── Analytics ─────────────────────────────────────────────────────────────

    private val _selectedTimeframe = MutableStateFlow("1M")
    val selectedTimeframe: StateFlow<String> = _selectedTimeframe.asStateFlow()

    private val _analyticsData = MutableStateFlow<AnalyticsPnlResponse?>(null)
    val analyticsData: StateFlow<AnalyticsPnlResponse?> = _analyticsData.asStateFlow()

    val transactions: StateFlow<List<Transaction>> = dao.getAllTransactions()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    // ── Settings ──────────────────────────────────────────────────────────────

    private val _exchangeConnected = MutableStateFlow(false)
    val exchangeConnected: StateFlow<Boolean> = _exchangeConnected.asStateFlow()

    private val _apiKey = MutableStateFlow("")
    val apiKey: StateFlow<String> = _apiKey.asStateFlow()

    private val _apiSecret = MutableStateFlow("")
    val apiSecret: StateFlow<String> = _apiSecret.asStateFlow()

    private val _profitLockTarget = MutableStateFlow(0.50f)
    val profitLockTarget: StateFlow<Float> = _profitLockTarget.asStateFlow()

    private val _maxDrawdown = MutableStateFlow(15.0f)
    val maxDrawdown: StateFlow<Float> = _maxDrawdown.asStateFlow()

    private val _maxCoinsToTrade = MutableStateFlow(3)
    val maxCoinsToTrade: StateFlow<Int> = _maxCoinsToTrade.asStateFlow()

    private val _gridLevels = MutableStateFlow(6)
    val gridLevels: StateFlow<Int> = _gridLevels.asStateFlow()

    private val _pushNotificationsEnabled = MutableStateFlow(true)
    val pushNotificationsEnabled: StateFlow<Boolean> = _pushNotificationsEnabled.asStateFlow()

    private val _lightThemeEnabled = MutableStateFlow(false)
    val lightThemeEnabled: StateFlow<Boolean> = _lightThemeEnabled.asStateFlow()

    private val _logMessage = MutableStateFlow<String?>(null)
    val logMessage: StateFlow<String?> = _logMessage.asStateFlow()

    // ── Init ──────────────────────────────────────────────────────────────────

    init {
        loadSettings()
        startPolling()
    }

    // ── Polling loop ──────────────────────────────────────────────────────────

    private fun startPolling() {
        viewModelScope.launch {
            delay(500)
            while (true) {
                pollPortfolio()
                pollStatus()
                pollPrices()
                pollTransactions()
                pollGridData()
                pollAnalyticsPnl()
                delay(3000)
            }
        }
    }

    private suspend fun pollPortfolio() {
        when (val result = repository.getPortfolio()) {
            is ApiResult.Success -> {
                _totalEquity.value = result.data.totalEquity
                _profitLockProgress.value = result.data.profitLockProgress.toFloat()
                _exchangeConnected.value = result.data.safeMode.not()
            }
            is ApiResult.Error -> { /* keep last good values */ }
        }
    }

    private suspend fun pollStatus() {
        when (val result = repository.getStatus()) {
            is ApiResult.Success -> {
                _botStatus.value = result.data.botStatus
            }
            is ApiResult.Error -> { /* keep last good values */ }
        }
    }

    private suspend fun pollPrices() {
        when (val result = repository.getPrices()) {
            is ApiResult.Success -> {
                _btcPrice.value = result.data.prices["BTCUSDT"] ?: _btcPrice.value
                _ethPrice.value = result.data.prices["ETHUSDT"] ?: _ethPrice.value
                _solPrice.value = result.data.prices["SOLUSDT"] ?: _solPrice.value
            }
            is ApiResult.Error -> { /* keep last good values */ }
        }
    }

    private suspend fun pollTransactions() {
        when (val result = repository.getTransactions(limit = 100)) {
            is ApiResult.Success -> {
                syncLockCyclesToRoom(result.data.lockCycles)
            }
            is ApiResult.Error -> { /* Room DB acts as fallback cache */ }
        }
    }

    private suspend fun pollGridData() {
        val coin = _selectedRadarCoin.value.replace("/USDT", "") + "USDT"
        when (val result = repository.getGrid(symbol = coin)) {
            is ApiResult.Success -> { _gridData.value = result.data }
            is ApiResult.Error -> { /* keep last good grid data */ }
        }
    }

    fun refreshGridData() {
        viewModelScope.launch { pollGridData() }
    }

    private suspend fun pollAnalyticsPnl() {
        when (val result = repository.getAnalyticsPnl(timeframe = _selectedTimeframe.value)) {
            is ApiResult.Success -> { _analyticsData.value = result.data }
            is ApiResult.Error -> { /* keep last good analytics */ }
        }
    }

    fun refreshAnalyticsPnl() {
        viewModelScope.launch { pollAnalyticsPnl() }
    }

    private suspend fun syncLockCyclesToRoom(cycles: List<LockCycleData>) {
        val existingTxids = dao.getAllTransactions().first().map { it.txid }.toSet()
        for (cycle in cycles) {
            if (existingTxids.contains("API#${cycle.cycleNumber}")) continue

            val msTimestamp = try {
                java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.US).apply {
                    timeZone = java.util.TimeZone.getTimeZone("UTC")
                }.parse(cycle.timestamp)?.time ?: System.currentTimeMillis()
            } catch (_: Exception) {
                System.currentTimeMillis()
            }

            dao.insertTransaction(
                Transaction(
                    type = "LOCK",
                    title = "Cycle Locked",
                    amount = cycle.totalProfit,
                    timestamp = msTimestamp,
                    txid = "API#${cycle.cycleNumber}"
                )
            )
        }
    }

    // ── Load settings from API ────────────────────────────────────────────────

    private fun loadSettings() {
        viewModelScope.launch {
            when (val result = repository.getSettings()) {
                is ApiResult.Success -> {
                    _profitLockTarget.value = (result.data.profitTargetPct * 100).toFloat()
                    _maxDrawdown.value = (result.data.maxDrawdownPct * 100).toFloat()
                    _maxCoinsToTrade.value = result.data.numCoins
                    _gridLevels.value = result.data.gridLevels
                    _apiKey.value = if (result.data.apiKeyConfigured) "••••••••" else ""
                    _exchangeConnected.value = result.data.exchangeConnected
                }
                is ApiResult.Error -> { /* use defaults */ }
            }
        }
    }

    // ── Settings actions (write to API) ───────────────────────────────────────

    fun updateExchangeConnection(connected: Boolean) {
        _exchangeConnected.value = connected
        viewModelScope.launch {
            showLog(if (connected) "Connecting to exchange..." else "Disconnecting...")
            repository.updateSettings(SettingsUpdateBody(
                apiKey = if (connected) _apiKey.value else "",
                apiSecret = if (connected) _apiSecret.value else "",
            ))
            if (connected) {
                delay(500)
                testConnection()
            } else {
                showLog("Exchange disconnected.")
            }
        }
    }

    fun updateCredentials(key: String, secret: String) {
        _apiKey.value = key
        _apiSecret.value = secret
        viewModelScope.launch {
            showLog("Updating API credentials...")
            repository.updateSettings(SettingsUpdateBody(
                apiKey = key,
                apiSecret = secret,
            ))
            delay(500)
            testConnection()
        }
    }

    fun testConnection() {
        viewModelScope.launch {
            showLog("Testing API connection...")
            when (val result = repository.testConnection()) {
                is ApiResult.Success -> {
                    _exchangeConnected.value = result.data.connected
                    showLog(if (result.data.connected) "Connected. Balance: $${"%.2f".format(result.data.usdtBalance)}"
                            else "Connection failed: ${result.data.message}")
                }
                is ApiResult.Error -> {
                    _exchangeConnected.value = false
                    showLog("Connection test failed: ${result.message}")
                }
            }
        }
    }

    fun updateStrategyParams(target: Float, maxDD: Float, coins: Int, levels: Int) {
        _profitLockTarget.value = target
        _maxDrawdown.value = maxDD
        _maxCoinsToTrade.value = coins
        _gridLevels.value = levels
        viewModelScope.launch {
            repository.updateSettings(SettingsUpdateBody(
                profitTargetPct = (target / 100).toDouble(),
                maxDrawdownPct = (maxDD / 100).toDouble(),
                numCoins = coins,
                gridLevels = levels,
            ))
        }
    }

    fun toggleSystemPreferences(notifications: Boolean, lightTheme: Boolean) {
        _pushNotificationsEnabled.value = notifications
        _lightThemeEnabled.value = lightTheme
        viewModelScope.launch {
            repository.updateSettings(SettingsUpdateBody(
                pushNotifications = notifications,
            ))
        }
    }

    // ── Navigation selectors ──────────────────────────────────────────────────

    fun selectRadarCoin(coin: String) {
        _selectedRadarCoin.value = coin
        refreshGridData()
    }

    fun selectTimeframe(tf: String) {
        _selectedTimeframe.value = tf
        refreshAnalyticsPnl()
    }

    // ── Bot status toggle ─────────────────────────────────────────────────────

    fun toggleBotStatus() {
        _botStatus.value = if (_botStatus.value == "HUNTING") "SLEEPING" else "HUNTING"
        showLog("Bot Mode: ${_botStatus.value}. ${if (_botStatus.value == "SLEEPING") "Halting active orders." else "Redeploying grid matrices."}")
    }

    // ── Force Profit Lock (calls API) ─────────────────────────────────────────

    fun triggerProfitLock(isAuto: Boolean = false) {
        viewModelScope.launch {
            showLog("Requesting profit lock...")
            when (val result = repository.forceProfitLock()) {
                is ApiResult.Success -> {
                    pollPortfolio()
                    pollTransactions()
                    showLog(result.data.message)
                }
                is ApiResult.Error -> {
                    showLog("API error: ${result.message}")
                }
            }
        }
    }

    // ── Panic Liquidation (calls API) ─────────────────────────────────────────

    fun triggerPanicLiquidate() {
        viewModelScope.launch {
            showLog("Executing emergency stop...")
            when (val result = repository.panicLiquidate()) {
                is ApiResult.Success -> {
                    _botStatus.value = "SLEEPING"
                    _profitLockProgress.value = 0f
                    pollPortfolio()
                    pollTransactions()
                    showLog(result.data.message)
                }
                is ApiResult.Error -> {
                    showLog("API error: ${result.message}")
                }
            }
        }
    }

    // ── Clear history ─────────────────────────────────────────────────────────

    fun clearHistory() {
        viewModelScope.launch {
            dao.clearAllTransactions()
            showLog("Audit archives cleared.")
        }
    }

    // ── Misc ──────────────────────────────────────────────────────────────────

    fun dismissLog() {
        _logMessage.value = null
    }

    private fun showLog(msg: String) {
        _logMessage.value = msg
    }
}
