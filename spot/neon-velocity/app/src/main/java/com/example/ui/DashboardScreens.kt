package com.example.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.TrendingUp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.api.EquityPoint
import com.example.data.Transaction
import com.example.ui.theme.*
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.*
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

// Fluid Premium Easing curve for luxurious decelerating slide-ups
val PremiumEasing = CubicBezierEasing(0.16f, 1f, 0.3f, 1f)

@Composable
fun AnimatedEntrance(
    delayMillis: Int = 0,
    content: @Composable () -> Unit
) {
    val animProgress = remember { Animatable(0f) }
    val density = LocalDensity.current.density
    LaunchedEffect(Unit) {
        if (delayMillis > 0) {
            delay(delayMillis.toLong())
        }
        animProgress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 400, easing = PremiumEasing)
        )
    }
    Box(
        modifier = Modifier.graphicsLayer {
            alpha = animProgress.value
            translationY = (30 * (1f - animProgress.value)) * density
        }
    ) {
        content()
    }
}

// Helper date formatters
fun formatTime(timeMs: Long): String {
    val formatter = SimpleDateFormat("MMM dd, h:mm a", Locale.US)
    return formatter.format(Date(timeMs)).uppercase()
}

@Composable
fun MainScreen(viewModel: TraderViewModel) {
    var activeTab by remember { mutableStateOf("home") } // Default to Home/Dashboard
    val lightTheme by viewModel.lightThemeEnabled.collectAsState()

    // Dynamically adjust theme palette locally if requested
    val bg = if (lightTheme) Color(0xFFFBFBFB) else DarkBackground
    val textPrimary = if (lightTheme) Color(0xFF131313) else TextPrimary
    val cardBg = if (lightTheme) Color(0xFFF0F0F0) else DarkSurface
    val borderCol = if (lightTheme) Color(0xFFE2E2E2) else Color(0xFF201F1F)

    // System Alert Log Banner
    val logMessage by viewModel.logMessage.collectAsState()

    Scaffold(
        modifier = Modifier
            .fillMaxSize()
            .background(bg),
        bottomBar = {
            BottomNavigationBar(
                activeTab = activeTab, 
                onTabSelect = { activeTab = it },
                lightTheme = lightTheme,
                cardBg = cardBg,
                borderCol = borderCol
            )
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(bg)
        ) {
            Column(modifier = Modifier.fillMaxSize()) {
                // Toast Log Notification Alert Banner
                AnimatedVisibility(
                    visible = logMessage != null,
                    enter = fadeIn() + slideInVertically(),
                    exit = fadeOut() + slideOutVertically()
                ) {
                    logMessage?.let { msg ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            colors = CardDefaults.cardColors(containerColor = NeonLime),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 16.dp, vertical = 12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(
                                    modifier = Modifier.weight(1f),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Info,
                                        contentDescription = "Alert",
                                        tint = DarkBackground,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Text(
                                        text = msg,
                                        style = MaterialTheme.typography.bodyMedium.copy(
                                            color = DarkBackground,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 12.sp
                                        )
                                    )
                                }
                                Icon(
                                    imageVector = Icons.Default.Close,
                                    contentDescription = "Dismiss",
                                    tint = DarkBackground,
                                    modifier = Modifier
                                        .size(18.dp)
                                        .clickable { viewModel.dismissLog() }
                                )
                            }
                        }
                    }
                }

                // Inner Main Screen Selection
                Box(modifier = Modifier.weight(1f)) {
                    AnimatedContent(
                        targetState = activeTab,
                        transitionSpec = {
                            fadeIn(animationSpec = tween(durationMillis = 320, easing = PremiumEasing)) +
                                    slideInVertically(initialOffsetY = { 40 }, animationSpec = tween(durationMillis = 320, easing = PremiumEasing)) togetherWith
                                    fadeOut(animationSpec = tween(durationMillis = 150))
                        },
                        label = "tab_switch"
                    ) { targetTab ->
                        when (targetTab) {
                            "home" -> HomeScreen(viewModel = viewModel, lightTheme = lightTheme, cardBg = cardBg, textPrimary = textPrimary, borderCol = borderCol)
                            "scan" -> GridRadarScreen(viewModel = viewModel, lightTheme = lightTheme, cardBg = cardBg, textPrimary = textPrimary, borderCol = borderCol)
                            "analytics" -> AnalyticsScreen(viewModel = viewModel, lightTheme = lightTheme, cardBg = cardBg, textPrimary = textPrimary, borderCol = borderCol)
                            "settings" -> ControlRoomScreen(viewModel = viewModel, lightTheme = lightTheme, cardBg = cardBg, textPrimary = textPrimary, borderCol = borderCol)
                        }
                    }
                }
            }
        }
    }
}

// BOTTOM NAVIGATION COMPONENT
@Composable
fun BottomNavigationBar(
    activeTab: String, 
    onTabSelect: (String) -> Unit,
    lightTheme: Boolean,
    cardBg: Color,
    borderCol: Color
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = cardBg.copy(alpha = 0.9f)),
        border = BorderStroke(1.dp, borderCol)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically
        ) {
            BottomNavItem(
                label = "Dashboard",
                icon = Icons.Default.Home,
                selected = activeTab == "home",
                onSelect = { onTabSelect("home") },
                lightTheme = lightTheme,
                modifier = Modifier.testTag("nav_home_tab")
            )

            BottomNavItem(
                label = "Grid Radar",
                icon = Icons.Default.Radar,
                selected = activeTab == "scan",
                onSelect = { onTabSelect("scan") },
                lightTheme = lightTheme,
                modifier = Modifier.testTag("nav_scan_tab")
            )

            BottomNavItem(
                label = "Analytics",
                icon = Icons.Default.QueryStats,
                selected = activeTab == "analytics",
                onSelect = { onTabSelect("analytics") },
                lightTheme = lightTheme,
                modifier = Modifier.testTag("nav_analytics_tab")
            )

            BottomNavItem(
                label = "Control Room",
                icon = Icons.Default.Settings,
                selected = activeTab == "settings",
                onSelect = { onTabSelect("settings") },
                lightTheme = lightTheme,
                modifier = Modifier.testTag("nav_settings_tab")
            )
        }
    }
}

@Composable
fun BottomNavItem(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    onSelect: () -> Unit,
    lightTheme: Boolean,
    modifier: Modifier = Modifier
) {
    val unselectedColor = if (lightTheme) Color(0xFF7c7c7c) else TextSecondary.copy(alpha = 0.5f)
    Column(
        modifier = modifier
            .clickable { onSelect() }
            .padding(horizontal = 12.dp, vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = if (selected) NeonLimeDim else unselectedColor,
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall.copy(
                fontSize = 9.sp,
                fontWeight = FontWeight.Bold,
                color = if (selected) NeonLimeDim else unselectedColor
            )
        )
    }
}

// HEADER COMPONENT WITH PROFILE AND LIVE ACTIONS
@Composable
fun ScreenHeader(
    viewModel: TraderViewModel, 
    title: String,
    lightTheme: Boolean,
    textPrimary: Color,
    cardBg: Color,
    borderCol: Color
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            // High contrast premium avatar badge with Sajibur Rahman style
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(
                        brush = Brush.radialGradient(
                            colors = listOf(Color(0xFF8257E5).copy(alpha = 0.3f), Color.Transparent)
                        ),
                        shape = CircleShape
                    )
                    .border(BorderStroke(1.5.dp, Color(0xFF7857FF)), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                // Circular Avatar Placeholder showing initial of user or premium avatar
                Box(
                    modifier = Modifier
                        .size(38.dp)
                        .clip(CircleShape)
                        .background(Color(0xFF1E172E))
                ) {
                    Icon(
                        imageVector = Icons.Default.Person,
                        contentDescription = "Avatar",
                        tint = Color(0xFFA594F9),
                        modifier = Modifier.size(20.dp).align(Alignment.Center)
                    )
                }
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "Sajibur Rahman",
                        style = MaterialTheme.typography.bodyMedium.copy(
                            color = textPrimary,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    // Verified Badge Pill
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color(0xFF10261A))
                            .padding(horizontal = 5.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "Verified",
                            color = Color(0xFF2ED17B),
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 8.sp,
                            fontFamily = FontFamily.SansSerif
                        )
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    // PRO Badge Pill
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color(0xFF423700))
                            .padding(horizontal = 5.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "PRO",
                            color = Color(0xFFFFD700),
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 8.sp,
                            fontFamily = FontFamily.SansSerif
                        )
                    }
                }
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge.copy(
                        color = textPrimary.copy(alpha = 0.9f),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.SemiBold,
                        fontFamily = FontFamily.SansSerif
                    )
                )
            }
        }

        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Live Manual Injection Node (Bolt)
            IconButton(
                onClick = { viewModel.triggerProfitLock(isAuto = false) },
                modifier = Modifier
                    .size(40.dp)
                    .background(cardBg, CircleShape)
                    .border(BorderStroke(1.dp, borderCol.copy(alpha = 0.6f)), CircleShape)
                    .testTag("inject_trigger_btn")
            ) {
                Icon(
                    imageVector = Icons.Default.Bolt,
                    contentDescription = "Manual Cycle Tick",
                    tint = NeonLimeDim,
                    modifier = Modifier.size(20.dp)
                )
            }

            // Bell notification badge
            Box(
                modifier = Modifier.size(40.dp)
            ) {
                IconButton(
                    onClick = { viewModel.triggerProfitLock(isAuto = false) },
                    modifier = Modifier
                        .size(40.dp)
                        .background(cardBg.copy(alpha = 0.8f), CircleShape)
                        .border(BorderStroke(1.dp, borderCol.copy(alpha = 0.6f)), CircleShape)
                ) {
                    Icon(
                        imageVector = Icons.Default.Notifications,
                        contentDescription = "Notification Bell",
                        tint = textPrimary.copy(alpha = 0.7f),
                        modifier = Modifier.size(19.dp)
                    )
                }
                // Purple notification count
                Box(
                    modifier = Modifier
                        .size(16.dp)
                        .align(Alignment.TopEnd)
                        .offset(x = 1.dp, y = (-2).dp)
                        .clip(CircleShape)
                        .background(Color(0xFF7857FF)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "2",
                        color = Color.White,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Black
                    )
                }
            }
        }
    }
}

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    lightTheme: Boolean,
    borderCol: Color,
    contentPadding: PaddingValues = PaddingValues(20.dp),
    content: @Composable ColumnScope.() -> Unit
) {
    val containerColor = if (lightTheme) {
        Color.White.copy(alpha = 0.55f)
    } else {
        Color(0xFF131313).copy(alpha = 0.55f)
    }
    
    val borderBrush = if (lightTheme) {
        Brush.linearGradient(
            colors = listOf(
                Color.White.copy(alpha = 0.9f),
                Color.Black.copy(alpha = 0.08f),
                Color.White.copy(alpha = 0.4f)
            )
        )
    } else {
        Brush.linearGradient(
            colors = listOf(
                Color.White.copy(alpha = 0.25f),
                Color(0xFF9FFB06).copy(alpha = 0.35f),
                Color.White.copy(alpha = 0.05f),
                Color(0xFF8257E5).copy(alpha = 0.25f)
            )
        )
    }

    Card(
        modifier = modifier,
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        border = BorderStroke(1.2.dp, borderBrush)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(contentPadding),
            content = content
        )
    }
}

// ==================== SCREEN 1: DASHBOARD ====================
@Composable
fun HomeScreen(
    viewModel: TraderViewModel,
    lightTheme: Boolean,
    cardBg: Color,
    textPrimary: Color,
    borderCol: Color
) {
    val totalEquity by viewModel.totalEquity.collectAsState()
    val profitProgress by viewModel.profitLockProgress.collectAsState()
    val botStatus by viewModel.botStatus.collectAsState()

    val btcPrice by viewModel.btcPrice.collectAsState()
    val ethPrice by viewModel.ethPrice.collectAsState()
    val solPrice by viewModel.solPrice.collectAsState()

    val targetPercent = viewModel.profitLockTarget.collectAsState().value

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(28.dp),
        contentPadding = PaddingValues(top = 24.dp, bottom = 48.dp)
    ) {
        item {
            AnimatedEntrance(delayMillis = 0) {
                ScreenHeader(viewModel, "Dashboard", lightTheme, textPrimary, cardBg, borderCol)
            }
        }

        item {
            AnimatedEntrance(delayMillis = 100) {
                GlassCard(
                    modifier = Modifier.fillMaxWidth().testTag("dashboard_hero_balance_card"),
                    lightTheme = lightTheme,
                    borderCol = borderCol,
                    contentPadding = PaddingValues(24.dp)
                ) {
                    Text(
                        text = "TOTAL PORTFOLIO EQUITY",
                        style = MaterialTheme.typography.labelSmall.copy(
                            color = if (lightTheme) Color(0xFF5A5A5A) else Color(0xFF8C849C),
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.6.sp
                        )
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                    Row(
                        verticalAlignment = Alignment.Bottom,
                        horizontalArrangement = Arrangement.SpaceBetween,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = Icons.Default.AccountBalanceWallet,
                                    contentDescription = "Balance",
                                    tint = if (lightTheme) Color(0xFF131313) else Color(0xFF8BDC00),
                                    modifier = Modifier.size(26.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = String.format("$%,.2f", totalEquity),
                                    style = MaterialTheme.typography.titleLarge.copy(
                                        color = textPrimary,
                                        fontSize = 32.sp,
                                        fontWeight = FontWeight.Black,
                                        fontFamily = FontFamily.SansSerif
                                    )
                                )
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "USDT Balance",
                                style = MaterialTheme.typography.bodySmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF7F7A8A),
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            )
                        }

                        Column(horizontalAlignment = Alignment.End) {
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(50))
                                    .background(if (lightTheme) Color(0xFFE2FBEA) else Color(0xFF102D1E))
                                    .padding(horizontal = 12.dp, vertical = 6.dp)
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        imageVector = Icons.AutoMirrored.Filled.TrendingUp,
                                        contentDescription = "Up",
                                        tint = Color(0xFF2ED17B),
                                        modifier = Modifier.size(12.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = String.format("%+.2f%%", profitProgress),
                                        color = if (profitProgress >= 0) Color(0xFF2ED17B) else Color(0xFFFFB4AB),
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 11.sp
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "Cycle Progress",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF7F7A8A),
                                    fontSize = 10.sp
                                )
                            )
                        }
                    }
                }
            }
        }

        // COHESIVE METRICS GRID - ROW 1 (ENGINE INTEL & CYCLE PROGRESS)
        item {
            AnimatedEntrance(delayMillis = 160) {
                val transition = rememberInfiniteTransition("pulse_cohesive")
                val scale by transition.animateFloat(
                    initialValue = 0.8f,
                    targetValue = 1.3f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(800),
                        repeatMode = RepeatMode.Reverse
                    ),
                    label = "pulse_scale"
                )
                val statusColor = if (botStatus == "HUNTING") NeonLimeDim else Color(0xFFFFB4AB)

                Row(
                    modifier = Modifier.fillMaxWidth().testTag("dashboard_metrics_row_1"),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Card 1: Engine Status
                    GlassCard(
                        modifier = Modifier
                            .weight(1f)
                            .height(150.dp)
                            .clickable { viewModel.toggleBotStatus() },
                        lightTheme = lightTheme,
                        borderCol = borderCol,
                        contentPadding = PaddingValues(18.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "INTELLIGENCE",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF8C849C),
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 1.sp
                                )
                            )
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .drawBehind {
                                        drawCircle(
                                            color = statusColor,
                                            radius = (size.width / 2) * scale
                                        )
                                    }
                            )
                        }
                        Spacer(modifier = Modifier.height(14.dp))
                        Text(
                            text = botStatus,
                            style = MaterialTheme.typography.titleMedium.copy(
                                color = if (botStatus == "HUNTING") Color(0xFF2ED17B) else ErrorRed,
                                fontWeight = FontWeight.Black,
                                fontSize = 18.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "Tap to toggle state",
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (lightTheme) Color(0xFF8B8B8B) else Color(0xFF7F7A8A),
                                fontSize = 10.sp
                            )
                        )
                    }

                    // Card 2: Cycle Lock Progress
                    val fillPercent = (profitProgress / targetPercent).coerceIn(0f, 1f)
                    val animatedFillPercent by animateFloatAsState(
                        targetValue = fillPercent,
                        animationSpec = spring(stiffness = Spring.StiffnessMediumLow, dampingRatio = Spring.DampingRatioLowBouncy),
                        label = "fill_progress_spring"
                    )

                    GlassCard(
                        modifier = Modifier
                            .weight(1f)
                            .height(150.dp),
                        lightTheme = lightTheme,
                        borderCol = borderCol,
                        contentPadding = PaddingValues(18.dp)
                    ) {
                        Text(
                            "CYCLE RANGE",
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF8C849C),
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = String.format("+%.2f%%", profitProgress),
                            style = MaterialTheme.typography.titleMedium.copy(
                                color = NeonLime,
                                fontWeight = FontWeight.Black,
                                fontSize = 18.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = String.format("Target: +%.2f%%", targetPercent),
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (lightTheme) Color(0xFF8B8B8B) else Color(0xFF7F7A8A),
                                fontSize = 10.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(6.dp)
                                .clip(RoundedCornerShape(3.dp))
                                .background(if (lightTheme) Color(0xFFE2E2E2) else Color(0x229FFB06))
                        ) {
                            Box(
                                modifier = Modifier
                                    .fillMaxHeight()
                                    .fillMaxWidth(animatedFillPercent)
                                    .clip(RoundedCornerShape(3.dp))
                                    .background(
                                        Brush.horizontalGradient(
                                            colors = listOf(NeonLimeDim, NeonLime)
                                        )
                                    )
                            )
                        }
                    }
                }
            }
        }

        // COHESIVE METRICS GRID - ROW 2 (ASSET ALLOCATIONS & ENGINE CYCLES)
        item {
            AnimatedEntrance(delayMillis = 220) {
                Row(
                    modifier = Modifier.fillMaxWidth().testTag("dashboard_metrics_row_2"),
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Card 3: Asset Allocations
                    GlassCard(
                        modifier = Modifier
                            .weight(1f)
                            .height(150.dp),
                        lightTheme = lightTheme,
                        borderCol = borderCol,
                        contentPadding = PaddingValues(18.dp)
                    ) {
                        Text(
                            "ALLOCATIONS",
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF8C849C),
                                fontSize = 10.sp,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = 1.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(12.dp))

                        Column(
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(modifier = Modifier.size(5.dp).clip(CircleShape).background(NeonLime))
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("USDT Balance", color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF7F7A8A), fontSize = 9.sp)
                                }
                                Text(
                                    text = String.format("$%,.2f", totalEquity),
                                    style = MaterialTheme.typography.labelSmall.copy(
                                        color = textPrimary,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 10.sp
                                    )
                                )
                            }
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(modifier = Modifier.size(5.dp).clip(CircleShape).background(Color(0xFF2ED17B)))
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text("Open PnL", color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF7F7A8A), fontSize = 9.sp)
                                }
                                Text(
                                    text = String.format("%+.2f%%", profitProgress),
                                    style = MaterialTheme.typography.labelSmall.copy(
                                        color = if (profitProgress >= 0) Color(0xFF2ED17B) else Color(0xFFFFB4AB),
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 10.sp
                                    )
                                )
                            }
                        }
                    }

                    // Card 4: Investment Period
                    GlassCard(
                        modifier = Modifier
                            .weight(1f)
                            .height(150.dp),
                        lightTheme = lightTheme,
                        borderCol = borderCol,
                        contentPadding = PaddingValues(18.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "CYCLE TERM",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF8C849C),
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    letterSpacing = 1.sp
                                )
                            )
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = null,
                                tint = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF8BDC00),
                                modifier = Modifier.size(12.dp)
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "6 Months",
                            style = MaterialTheme.typography.titleMedium.copy(
                                color = textPrimary,
                                fontWeight = FontWeight.Bold,
                                fontSize = 18.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "Active Lockup",
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (lightTheme) Color(0xFF8B8B8B) else Color(0xFF7F7A8A),
                                fontSize = 10.sp
                            )
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(50))
                                .background(if (lightTheme) Color(0xFFE2E2E2) else Color(0xFF1E1C24))
                                .padding(horizontal = 8.dp, vertical = 2.dp)
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    text = "Locked Mode",
                                    color = textPrimary,
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.width(3.dp))
                                Icon(
                                    imageVector = Icons.Default.KeyboardArrowDown,
                                    contentDescription = null,
                                    tint = textPrimary.copy(alpha = 0.6f),
                                    modifier = Modifier.size(10.dp)
                                )
                            }
                        }
                    }
                }
            }
        }

        // MIDDLE SECTION: THE DRAFT (CURRENT COINS)
        item {
            AnimatedEntrance(delayMillis = 280) {
                Text(
                    text = "Current Cycle Assets",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        item {
            AnimatedEntrance(delayMillis = 240) {
                LazyRow(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    // Coin 1: BTC
                    item {
                        DraftCoinCard(
                            ticker = "BTC/USDT",
                            price = btcPrice,
                            metric = "Vol: 24.8B (ADX: High)",
                            lightTheme = lightTheme,
                            cardBg = cardBg,
                            textPrimary = textPrimary,
                            borderCol = borderCol,
                            onTabSelect = { viewModel.selectRadarCoin("BTC/USDT") }
                        )
                    }
                    // Coin 2: ETH
                    item {
                        DraftCoinCard(
                            ticker = "ETH/USDT",
                            price = ethPrice,
                            metric = "Vol: 12.1B (Ranging)",
                            lightTheme = lightTheme,
                            cardBg = cardBg,
                            textPrimary = textPrimary,
                            borderCol = borderCol,
                            onTabSelect = { viewModel.selectRadarCoin("ETH/USDT") }
                        )
                    }
                    // Coin 3: SOL
                    item {
                        DraftCoinCard(
                            ticker = "SOL/USDT",
                            price = solPrice,
                            metric = "Vol: 3.2B (ADX: Low)",
                            lightTheme = lightTheme,
                            cardBg = cardBg,
                            textPrimary = textPrimary,
                            borderCol = borderCol,
                            onTabSelect = { viewModel.selectRadarCoin("SOL/USDT") }
                        )
                    }
                }
            }
        }

        // BOTTOM SECTION: QUICK ACTIONS
        item {
            AnimatedEntrance(delayMillis = 320) {
                Text(
                        text = "Tactical Actions",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        // Force Profit Lock Manual resetting button
        item {
            AnimatedEntrance(delayMillis = 380) {
                Button(
                    onClick = { viewModel.triggerProfitLock(isAuto = false) },
                    colors = ButtonDefaults.buttonColors(containerColor = NeonLime),
                    shape = RoundedCornerShape(18.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("action_force_lock"),
                    contentPadding = PaddingValues(16.dp),
                    elevation = ButtonDefaults.buttonElevation(defaultElevation = 2.dp, pressedElevation = 6.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Lock,
                        contentDescription = null,
                        tint = DarkBackground
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "FORCE CYCLE PROFIT LOCK",
                        style = MaterialTheme.typography.labelSmall.copy(
                            color = DarkBackground,
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 12.sp
                        )
                    )
                }
            }
        }

        // Panic Swipe Slider Component
        item {
            AnimatedEntrance(delayMillis = 440) {
                SwipeToPanicSlider(
                    onPanicConfirm = { viewModel.triggerPanicLiquidate() },
                    lightTheme = lightTheme,
                    cardBg = cardBg,
                    textPrimary = textPrimary
                )
            }
        }
    }
}

@Composable
fun DraftCoinCard(
    ticker: String,
    price: Double,
    metric: String,
    lightTheme: Boolean,
    cardBg: Color,
    textPrimary: Color,
    borderCol: Color,
    onTabSelect: () -> Unit
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.95f else 1.0f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy, stiffness = Spring.StiffnessMedium),
        label = "coin_card_scale"
    )

    val cleanTicker = ticker.substringBefore("/USDT")
    val fullName = when(cleanTicker) {
        "BTC" -> "Bitcoin (BTC)"
        "ETH" -> "Ethereum (ETH)"
        else -> "Solana (SOL)"
    }
    
    val coinColor = when(cleanTicker) {
        "BTC" -> Color(0xFFF7931A)
        "ETH" -> Color(0xFF627EEA) // Ether Violet
        else -> Color(0xFF14F195) // Solana mint green
    }

    val rewardRate = when(cleanTicker) {
        "BTC" -> "21.60%"
        "ETH" -> "23.47%"
        else -> "17.39%"
    }

    val gainsString = when(cleanTicker) {
        "BTC" -> "+1.89%"
        "ETH" -> "+ 3.89%"
        else -> "• 2.37%"
    }

    val graphOffsetValue = when(cleanTicker) {
        "BTC" -> "+$2,650"
        "ETH" -> "+$2,100"
        else -> "+$1,200"
    }

    Card(
        modifier = Modifier
            .width(180.dp)
            .scale(scale)
            .clickable(
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                onClick = onTabSelect
            )
            .testTag("draft_card_$ticker"),
        colors = CardDefaults.cardColors(containerColor = cardBg),
        shape = RoundedCornerShape(24.dp),
        border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            // Proof of Stake / Ledger type label
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Circle logo
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .clip(CircleShape)
                        .background(coinColor.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = if (cleanTicker == "BTC") Icons.Default.CurrencyBitcoin else Icons.Default.Token,
                        contentDescription = null,
                        tint = coinColor,
                        modifier = Modifier.size(14.dp)
                    )
                }
                Text(
                    text = "Proof of Stake",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF6B6B6B) else Color(0xFF7F7A8A),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold
                    )
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Full Coin Name
            Text(
                text = fullName,
                style = MaterialTheme.typography.bodyLarge.copy(
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = textPrimary
                )
            )

            Spacer(modifier = Modifier.height(6.dp))

            // Reward rate and dynamic gains status row
            Text(
                text = "Reward Rate",
                style = MaterialTheme.typography.labelSmall.copy(
                    fontSize = 10.sp,
                    color = if (lightTheme) Color(0xFF7c7c7c) else Color(0xFF7F7A8A)
                )
            )
            Text(
                text = rewardRate,
                style = MaterialTheme.typography.titleLarge.copy(
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Black,
                    color = textPrimary,
                    fontFamily = FontFamily.SansSerif
                )
            )

            Spacer(modifier = Modifier.height(4.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.TrendingUp,
                    contentDescription = null,
                    tint = Color(0xFF2ED17B),
                    modifier = Modifier.size(10.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = gainsString,
                    style = MaterialTheme.typography.labelSmall.copy(
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF2ED17B)
                    )
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Premium Custom Sparkline inside the Asset Card!
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(60.dp)
            ) {
                Canvas(
                    modifier = Modifier.fillMaxSize()
                ) {
                    val w = size.width
                    val h = size.height
                    
                    // Simple simulated coordinate points
                    val p1 = Offset(0f, h * 0.8f)
                    val p2 = Offset(w * 0.25f, h * 0.75f)
                    val p3 = Offset(w * 0.5f, h * 0.35f)
                    val p4 = Offset(w * 0.75f, h * 0.45f)
                    val p5 = Offset(w, h * 0.15f)

                    val curvePath = androidx.compose.ui.graphics.Path().apply {
                        moveTo(p1.x, p1.y)
                        cubicTo((p1.x + p2.x)/2, p1.y, (p1.x + p2.x)/2, p2.y, p2.x, p2.y)
                        cubicTo((p2.x + p3.x)/2, p2.y, (p2.x + p3.x)/2, p3.y, p3.x, p3.y)
                        cubicTo((p3.x + p4.x)/2, p3.y, (p3.x + p4.x)/2, p4.y, p4.x, p4.y)
                        cubicTo((p4.x + p5.x)/2, p4.y, (p4.x + p5.x)/2, p5.y, p5.x, p5.y)
                    }

                    val fillPath = androidx.compose.ui.graphics.Path().apply {
                        addPath(curvePath)
                        lineTo(w, h)
                        lineTo(0f, h)
                        close()
                    }

                    // Bottom ambient glow gradient
                    drawPath(
                        path = fillPath,
                        brush = Brush.verticalGradient(
                            colors = listOf(coinColor.copy(alpha = 0.22f), Color.Transparent)
                        )
                    )

                    // Sharp vector curve
                    drawPath(
                        path = curvePath,
                        color = coinColor,
                        style = Stroke(width = 2.dp.toPx(), cap = StrokeCap.Round)
                    )

                    // Draw tracking anchor circle highlight
                    drawCircle(
                        color = coinColor,
                        radius = 3.dp.toPx(),
                        center = p5
                    )
                    drawCircle(
                        color = coinColor.copy(alpha = 0.3f),
                        radius = 6.dp.toPx(),
                        center = p5
                    )
                }

                // Overlay Highlight bubble at peak
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .offset(x = 6.dp, y = (-8).dp)
                        .clip(RoundedCornerShape(50))
                        .background(Color(0xFF201B2E))
                        .border(BorderStroke(0.5.dp, coinColor.copy(alpha = 0.4f)), RoundedCornerShape(50))
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = graphOffsetValue,
                        color = coinColor,
                        fontWeight = FontWeight.Bold,
                        fontSize = 8.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }
    }
}

// SWIPE PANEL SLIDER IMPLEMENTATION (Panic Button)
@Composable
fun SwipeToPanicSlider(
    onPanicConfirm: () -> Unit,
    lightTheme: Boolean,
    cardBg: Color,
    textPrimary: Color
) {
    var widthState by remember { mutableStateOf(0) }
    var dragAmount by remember { mutableStateOf(0f) }

    val maxSwipe = (widthState - with(LocalDensity.current) { 56.dp.toPx() }).coerceAtLeast(0f)
    val swipeOffset = dragAmount.coerceIn(0f, maxSwipe)

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(56.dp)
            .testTag("panic_slide_container")
            .drawBehind {
                widthState = size.width.toInt()
            },
        colors = CardDefaults.cardColors(containerColor = Color(0xFF33090C)),
        shape = RoundedCornerShape(50),
        border = BorderStroke(1.dp, Color(0xFF93000A))
    ) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.CenterStart
        ) {
            // Background help swipe guidance label
            Text(
                text = "SLIDE TO EMERGENCY LIQUIDATE",
                style = MaterialTheme.typography.labelSmall.copy(
                    color = Color(0xFFFFB4AB).copy(alpha = 0.7f),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 1.2.sp
                ),
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center
            )

            // Slidable glowing panic handle knob
            Box(
                modifier = Modifier
                    .offset { IntOffset(swipeOffset.roundToInt(), 0) }
                    .size(48.dp)
                    .padding(4.dp)
                    .clip(CircleShape)
                    .background(Color(0xFF93000A))
                    .pointerInput(Unit) {
                        detectHorizontalDragGestures(
                            onDragEnd = {
                                if (dragAmount >= maxSwipe * 0.85f) {
                                    onPanicConfirm()
                                }
                                dragAmount = 0f
                            },
                            onHorizontalDrag = { _, dragAmountPx ->
                                dragAmount += dragAmountPx
                            }
                        )
                    }
                    .testTag("panic_swipe_nob"),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.ChevronRight,
                    contentDescription = null,
                    tint = Color.White
                )
            }
        }
    }
}


// ==================== SCREEN 2: GRID RADAR ====================
@Composable
fun GridRadarScreen(
    viewModel: TraderViewModel,
    lightTheme: Boolean,
    cardBg: Color,
    textPrimary: Color,
    borderCol: Color
) {
    val selectedCoin by viewModel.selectedRadarCoin.collectAsState()
    val activeCoins = listOf("BTC/USDT", "ETH/USDT", "SOL/USDT")
    val gridData by viewModel.gridData.collectAsState()

    val btcPrice by viewModel.btcPrice.collectAsState()
    val ethPrice by viewModel.ethPrice.collectAsState()
    val solPrice by viewModel.solPrice.collectAsState()

    val currentPrice = when (selectedCoin) {
        "BTC/USDT" -> btcPrice
        "ETH/USDT" -> ethPrice
        else -> solPrice
    }

    val gridLevels by viewModel.gridLevels.collectAsState()

    val realGrid = gridData
    val buyLevels = realGrid?.buyLevels ?: emptyList()
    val sellLevels = realGrid?.sellLevels ?: emptyList()
    val activeOrders = realGrid?.activeOrders ?: emptyList()
    val filledOrders = activeOrders.filter { it.status == "CLOSED" || it.status == "FILLED" }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
        contentPadding = PaddingValues(top = 20.dp, bottom = 40.dp)
    ) {
        item {
            AnimatedEntrance(delayMillis = 0) {
                ScreenHeader(viewModel, "Grid Radar", lightTheme, textPrimary, cardBg, borderCol)
            }
        }

        item {
            AnimatedEntrance(delayMillis = 100) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    activeCoins.forEach { token ->
                        val isSelected = selectedCoin == token
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(50))
                                .background(if (isSelected) NeonLime else cardBg)
                                .border(BorderStroke(1.dp, if (isSelected) NeonLime else borderCol.copy(alpha = 0.5f)), RoundedCornerShape(50))
                                .clickable { viewModel.selectRadarCoin(token) }
                                .padding(horizontal = 16.dp, vertical = 8.dp)
                                .testTag("radar_tab_chip_$token"),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = token,
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (isSelected) DarkBackground else textPrimary,
                                    fontWeight = FontWeight.Black,
                                    fontSize = 11.sp
                                )
                            )
                        }
                    }
                }
            }
        }

        item {
            AnimatedEntrance(delayMillis = 180) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(26.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Column(modifier = Modifier.padding(24.dp)) {
                        Text(
                            "Market Weather Status",
                            style = MaterialTheme.typography.labelSmall.copy(
                                color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(10.dp)
                                        .clip(CircleShape)
                                        .background(if (realGrid != null) NeonLime else TextSecondary.copy(alpha = 0.5f))
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    if (realGrid != null) "${selectedCoin} Radar Active" else "No Grid Data",
                                    style = MaterialTheme.typography.labelSmall.copy(
                                        color = if (realGrid != null) NeonLimeDim else TextSecondary,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                )
                            }
                            Text(
                                text = if (realGrid != null) "Orders: ${activeOrders.size}" else "Offline",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = textPrimary,
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                            )
                        }
                        Spacer(modifier = Modifier.height(20.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceAround
                        ) {
                            CoinMetricGauge(
                                label = "Grid Levels",
                                value = if (realGrid != null) realGrid.gridLevels.toFloat() / 20f else 0f,
                                lightTheme = lightTheme
                            )
                            CoinMetricGauge(
                                label = "Orders Filled",
                                value = if (activeOrders.isNotEmpty()) filledOrders.size.toFloat() / activeOrders.size.toFloat().coerceAtLeast(1f) else 0f,
                                lightTheme = lightTheme
                            )
                        }
                    }
                }
            }
        }

        item {
            AnimatedEntrance(delayMillis = 280) {
                Text(
                    "Bot Grid Order Ladder Matrix",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        item {
            AnimatedEntrance(delayMillis = 340) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("ladder_visualizer_card"),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(26.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Column(modifier = Modifier.padding(24.dp)) {
                        if (sellLevels.isNotEmpty()) {
                            sellLevels.sortedDescending().forEachIndexed { idx, price ->
                                GridLadderRow(
                                    label = "Sell Level ${idx + 1}",
                                    price = price,
                                    color = ErrorRed,
                                    isFilled = activeOrders.any { it.side == "SELL" && it.price == price && (it.status == "FILLED" || it.status == "CLOSED") },
                                    lightTheme = lightTheme
                                )
                            }
                        } else {
                            listOf(3, 2, 1).forEach { level ->
                                GridLadderRow(
                                    label = "Sell Limit #$level",
                                    price = currentPrice + (level * (currentPrice * 0.005)),
                                    color = ErrorRed,
                                    isFilled = false,
                                    lightTheme = lightTheme
                                )
                            }
                        }

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(NeonLime.copy(alpha = 0.12f))
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Current Mark Price",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = NeonLimeDim,
                                    fontWeight = FontWeight.Bold
                                )
                            )
                            Text(
                                text = String.format("$%,.2f", currentPrice),
                                style = MaterialTheme.typography.labelLarge.copy(
                                    color = NeonLime,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.ExtraBold
                                )
                            )
                        }

                        if (buyLevels.isNotEmpty()) {
                            buyLevels.forEachIndexed { idx, price ->
                                GridLadderRow(
                                    label = "Buy Level ${idx + 1}",
                                    price = price,
                                    color = NeonLimeDim,
                                    isFilled = activeOrders.any { it.side == "BUY" && it.price == price && (it.status == "FILLED" || it.status == "CLOSED") },
                                    lightTheme = lightTheme
                                )
                            }
                        } else {
                            listOf(1, 2, 3).forEach { level ->
                                GridLadderRow(
                                    label = "Buy Limit #$level",
                                    price = currentPrice - (level * (currentPrice * 0.005)),
                                    color = NeonLimeDim,
                                    isFilled = false,
                                    lightTheme = lightTheme
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "Active Matrix Levels",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary,
                                    fontSize = 11.sp
                                )
                            )
                            Text(
                                "${activeOrders.size} Open | ${filledOrders.size} Filled",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = NeonLimeDim,
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun GridLadderRow(
    label: String,
    price: Double,
    color: Color,
    isFilled: Boolean,
    lightTheme: Boolean
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .clip(CircleShape)
                    .background(if (isFilled) color else Color.Transparent)
                    .border(BorderStroke(1.dp, color), CircleShape)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "$label (${if (isFilled) "Filled" else "Waiting"})",
                style = MaterialTheme.typography.labelSmall.copy(
                    color = color.copy(alpha = if (isFilled) 1f else 0.6f),
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold
                )
            )
        }

        Text(
            text = String.format("$%,.2f", price),
            style = MaterialTheme.typography.labelSmall.copy(
                fontFamily = FontFamily.Monospace,
                color = if (lightTheme) Color.Black else Color.White
            )
        )
    }
}

@Composable
fun CoinMetricGauge(
    label: String,
    value: Float,
    lightTheme: Boolean
) {
    val animatedPercent by animateFloatAsState(
        targetValue = value,
        animationSpec = tween(durationMillis = 1000, easing = PremiumEasing),
        label = "gauge_radial_sweep"
    )

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Box(
            modifier = Modifier.size(54.dp),
            contentAlignment = Alignment.Center
        ) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                // Background arc track
                drawArc(
                    color = if (lightTheme) Color(0xFFE2E2E2) else Color(0x1BFFFFFF),
                    startAngle = -225f,
                    sweepAngle = 270f,
                    useCenter = false,
                    style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
                )
                // Colored active sweeping arc
                drawArc(
                    color = NeonLime,
                    startAngle = -225f,
                    sweepAngle = 270f * animatedPercent,
                    useCenter = false,
                    style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
                )
            }
            Text(
                text = String.format("%.0f%%", animatedPercent * 100),
                style = MaterialTheme.typography.labelSmall.copy(
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall.copy(
                fontSize = 8.sp,
                color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary
            )
        )
    }
}


// ==================== SCREEN 3: ANALYTICS ====================
@Composable
fun AnalyticsScreen(
    viewModel: TraderViewModel,
    lightTheme: Boolean,
    cardBg: Color,
    textPrimary: Color,
    borderCol: Color
) {
    val txs by viewModel.transactions.collectAsState()
    val timeframe by viewModel.selectedTimeframe.collectAsState()
    val analytics by viewModel.analyticsData.collectAsState()

    val totalSimProfit = txs.sumOf { it.amount }

    val netPnl = (analytics?.monthlyProfit ?: 0.0) + totalSimProfit
    val totalCycles = analytics?.totalCycles ?: (42 + txs.count { it.type == "LOCK" })
    val winRatio = analytics?.winRatio ?: 0.98
    val totalTrades = analytics?.totalTrades ?: 0
    val equityCurve = analytics?.equityCurve ?: emptyList()

    var selectedHistoryItem by remember { mutableStateOf<Transaction?>(null) }
    var isCandleMode by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
        contentPadding = PaddingValues(top = 20.dp, bottom = 40.dp)
    ) {
        item {
            AnimatedEntrance(delayMillis = 0) {
                ScreenHeader(viewModel, "Analytics", lightTheme, textPrimary, cardBg, borderCol)
            }
        }

        item {
            AnimatedEntrance(delayMillis = 100) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("pnl_analytics_card"),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(26.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.Top
                        ) {
                            Column {
                                Text(
                                    "Portfolio PnL",
                                    style = MaterialTheme.typography.labelSmall.copy(
                                        color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary,
                                        fontSize = 11.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                )
                                Text(
                                    text = String.format("%s$%,.2f", if (netPnl >= 0) "+" else "", netPnl),
                                    style = MaterialTheme.typography.titleLarge.copy(
                                        color = if (netPnl >= 0) NeonLime else ErrorRed,
                                        fontSize = 24.sp,
                                        fontWeight = FontWeight.Black,
                                        fontFamily = FontFamily.Monospace
                                    )
                                )
                            }

                            Card(
                                colors = CardDefaults.cardColors(containerColor = if (lightTheme) Color(0xFFE2E2E2) else Color(0x33414A34)),
                                shape = RoundedCornerShape(50),
                                border = BorderStroke(1.dp, borderCol.copy(alpha = 0.4f))
                            ) {
                                Row(modifier = Modifier.padding(4.dp)) {
                                    listOf("1D", "1W", "1M", "ALL").forEach { tf ->
                                        val isSelected = timeframe == tf
                                        Box(
                                            modifier = Modifier
                                                .clip(RoundedCornerShape(50))
                                                .background(if (isSelected) NeonLime else Color.Transparent)
                                                .clickable { viewModel.selectTimeframe(tf) }
                                                .padding(horizontal = 12.dp, vertical = 6.dp),
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Text(
                                                text = tf,
                                                style = MaterialTheme.typography.labelSmall.copy(
                                                    color = if (isSelected) DarkBackground else textPrimary,
                                                    fontWeight = FontWeight.Bold,
                                                    fontSize = 10.sp
                                                )
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(14.dp))

                        if (equityCurve.isNotEmpty()) {
                            AnalyticsEquityCurveChart(
                                equityPoints = equityCurve,
                                lightTheme = lightTheme
                            )
                        } else {
                            InteractiveLineChart(timeframe = timeframe, lightTheme = lightTheme)
                        }
                    }
                }
            }
        }

        item {
            AnimatedEntrance(delayMillis = 180) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "The Trophy Room",
                        style = MaterialTheme.typography.labelSmall.copy(
                            color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.2.sp,
                            fontSize = 11.sp
                        )
                    )
                    Icon(
                        imageVector = Icons.Default.Stars,
                        contentDescription = null,
                        tint = NeonLime,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }
        }

        item {
            AnimatedEntrance(delayMillis = 240) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Card(
                        modifier = Modifier
                            .weight(1f)
                            .testTag("trophy_cycle_locks"),
                        colors = CardDefaults.cardColors(containerColor = cardBg),
                        shape = RoundedCornerShape(20.dp),
                        border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text(
                                text = "Total Cycles",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "$totalCycles",
                                style = MaterialTheme.typography.titleLarge.copy(
                                    color = NeonLime,
                                    fontSize = 28.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace
                                )
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Targets Secured",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF7c7c7c) else TextSecondary.copy(alpha = 0.6f),
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            )
                        }
                    }

                    Card(
                        modifier = Modifier
                            .weight(1f)
                            .testTag("trophy_win_rate"),
                        colors = CardDefaults.cardColors(containerColor = cardBg),
                        shape = RoundedCornerShape(20.dp),
                        border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text(
                                text = "Win Ratio",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "${(winRatio * 100).toInt()} %",
                                style = MaterialTheme.typography.titleLarge.copy(
                                    color = NeonLime,
                                    fontSize = 28.sp,
                                    fontWeight = FontWeight.Bold,
                                    fontFamily = FontFamily.Monospace
                                )
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "${totalTrades} total trades",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (lightTheme) Color(0xFF7c7c7c) else TextSecondary.copy(alpha = 0.6f),
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            )
                        }
                    }
                }
            }
        }

        item {
            AnimatedEntrance(delayMillis = 320) {
                Text(
                    text = "Secured Cycles Feed",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        if (txs.isEmpty()) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(16.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Text(
                        text = "No lock cycles yet. Complete a profit lock to populate the feed.",
                        style = MaterialTheme.typography.bodyMedium.copy(
                            color = TextSecondary,
                            fontSize = 12.sp,
                            textAlign = TextAlign.Center
                        ),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp)
                    )
                }
            }
        } else {
            itemsIndexed(txs) { index, trans ->
                AnimatedEntrance(delayMillis = 380 + index * 50) {
                    TransactionFeedItem(
                        trans = trans,
                        lightTheme = lightTheme,
                        cardBg = cardBg,
                        borderCol = borderCol,
                        onItemClick = { selectedHistoryItem = trans }
                    )
                }
            }
        }
    }

    selectedHistoryItem?.let { trans ->
        AlertDialog(
            onDismissRequest = { selectedHistoryItem = null },
            confirmButton = {
                TextButton(
                    onClick = { selectedHistoryItem = null },
                    colors = ButtonDefaults.textButtonColors(contentColor = NeonLimeDim)
                ) {
                    Text("TERMINATE OVERLAY")
                }
            },
            title = {
                Text(
                    text = "Cycle Crypto Audit",
                    style = MaterialTheme.typography.labelSmall.copy(color = NeonLime, fontWeight = FontWeight.Bold)
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "Realized Outcome: +$${String.format("%.2f", trans.amount)} USDT",
                        style = MaterialTheme.typography.bodyLarge.copy(color = Color.White, fontWeight = FontWeight.Bold)
                    )
                    Text(
                        text = "Status: ${trans.title}\nID: ${trans.txid}\nTime: ${formatTime(trans.timestamp)}",
                        style = MaterialTheme.typography.bodyMedium.copy(color = TextSecondary, fontSize = 13.sp)
                    )
                    Divider(color = borderCol)
                    Text(
                        text = "Draft assets assigned and locked during this block:",
                        style = MaterialTheme.typography.labelSmall.copy(color = NeonLimeDim, fontSize = 10.sp)
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("• BTC/USDT", style = MaterialTheme.typography.bodyMedium.copy(color = Color.White))
                        Text("• ETH/USDT", style = MaterialTheme.typography.bodyMedium.copy(color = Color.White))
                        Text("• SOL/USDT", style = MaterialTheme.typography.bodyMedium.copy(color = Color.White))
                    }
                }
            },
            containerColor = DarkSurface,
            shape = RoundedCornerShape(20.dp),
            modifier = Modifier.testTag("dialog_transaction_audit")
        )
    }
}

@Composable
fun AnalyticsEquityCurveChart(
    equityPoints: List<EquityPoint>,
    lightTheme: Boolean
) {
    val animProgress = remember { Animatable(0f) }
    LaunchedEffect(equityPoints) {
        animProgress.snapTo(0f)
        animProgress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 900, easing = PremiumEasing)
        )
    }

    if (equityPoints.size < 2) {
        Text(
            text = "Not enough equity data yet.",
            style = MaterialTheme.typography.bodyMedium.copy(
                color = TextSecondary,
                fontSize = 11.sp
            ),
            modifier = Modifier.padding(vertical = 24.dp)
        )
        return
    }

    val minPnl = equityPoints.minOf { it.cumulativePnl }
    val maxPnl = equityPoints.maxOf { it.cumulativePnl }
    val range = (maxPnl - minPnl).coerceAtLeast(1.0)

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(130.dp)
    ) {
        val w = size.width
        val h = size.height
        val stepX = w / (equityPoints.size - 1).coerceAtLeast(1)

        val pts = equityPoints.mapIndexed { i, pt ->
            val x = i * stepX
            val y = h - ((pt.cumulativePnl - minPnl) / range * h).toFloat()
            Offset(x, y)
        }

        val linePath = androidx.compose.ui.graphics.Path().apply {
            moveTo(pts[0].x, pts[0].y + (h - pts[0].y) * (1f - animProgress.value))
            for (i in 1 until pts.size) {
                val prev = pts[i - 1]
                val curr = pts[i]
                val cy = curr.y + (h - curr.y) * (1f - animProgress.value)
                cubicTo(
                    (prev.x + curr.x) / 2, prev.y + (h - prev.y) * (1f - animProgress.value),
                    (prev.x + curr.x) / 2, cy,
                    curr.x, cy
                )
            }
        }

        val fillPath = androidx.compose.ui.graphics.Path().apply {
            addPath(linePath)
            lineTo(w, h)
            lineTo(0f, h)
            close()
        }

        drawPath(
            path = fillPath,
            brush = Brush.verticalGradient(
                colors = listOf(NeonLime.copy(alpha = 0.25f), Color.Transparent)
            )
        )

        drawPath(
            path = linePath,
            color = NeonLime,
            style = Stroke(width = 2.5.dp.toPx(), cap = StrokeCap.Round)
        )

        drawCircle(
            color = NeonLime,
            radius = 4.dp.toPx(),
            center = pts.last()
        )
    }
}

@Composable
fun TransactionFeedItem(
    trans: Transaction,
    lightTheme: Boolean,
    cardBg: Color,
    borderCol: Color,
    onItemClick: () -> Unit
) {
    val isLock = trans.type == "LOCK"
    val colorAccent = if (isLock) NeonLimeDim else ErrorRed

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onItemClick() }
            .testTag("transaction_item_${trans.txid}"),
        colors = CardDefaults.cardColors(containerColor = cardBg),
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(38.dp)
                        .clip(CircleShape)
                        .background(colorAccent.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = if (isLock) Icons.Default.Lock else Icons.Default.LockOpen,
                        contentDescription = null,
                        tint = colorAccent,
                        modifier = Modifier.size(18.dp)
                    )
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = trans.title,
                        style = MaterialTheme.typography.bodyMedium.copy(
                            fontWeight = FontWeight.Bold,
                            color = if (lightTheme) Color.Black else Color.White
                        )
                    )
                    Text(
                        text = formatTime(trans.timestamp),
                        style = MaterialTheme.typography.labelSmall.copy(
                            fontSize = 8.sp,
                            color = if (lightTheme) Color(0xFF6B6B6B) else TextSecondary
                        )
                    )
                }
            }

            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = String.format("${if (trans.amount >= 0) "+" else ""}$%,.2f", trans.amount),
                    style = MaterialTheme.typography.labelLarge.copy(
                        color = colorAccent,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                )
                Text(
                    text = trans.txid,
                    style = MaterialTheme.typography.labelSmall.copy(
                        fontSize = 8.sp,
                        color = if (lightTheme) Color(0xFF7c7c7c) else TextSecondary.copy(alpha = 0.6f)
                    )
                )
            }
        }
    }
}

// Interactive multi-timeframe Canvas Candlestick and Volume Chart
@Composable
fun InteractiveCandlestickChart(timeframe: String, lightTheme: Boolean) {
    val animProgress = remember { Animatable(0f) }
    LaunchedEffect(timeframe) {
        animProgress.snapTo(0f)
        animProgress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 900, easing = PremiumEasing)
        )
    }

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(130.dp)
    ) {
        val width = size.width
        val height = size.height

        // Draw ambient dotted grid levels
        val gridLines = 4
        for (i in 1..gridLines) {
            val y = (height / (gridLines + 1)) * i
            drawLine(
                color = if (lightTheme) Color(0xFFE2E2E2) else Color(0x1BFFFFFF),
                start = Offset(0f, y),
                end = Offset(width, y),
                strokeWidth = 1.dp.toPx(),
                pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(floatArrayOf(10f, 10f), 0f)
            )
        }

        // Setup mock candle offsets: bodyOpenY, bodyCloseY, wickHighY, wickLowY, color, isGreen
        // Scaled by animProgress
        val baseH = height
        val candleCount = 10
        val candleWidth = (width / candleCount) * 0.45f
        val candleSpacing = (width / candleCount)

        val rawCandles = when (timeframe) {
            "1D" -> listOf(
                Pair(0.75f, 0.70f), Pair(0.70f, 0.62f), Pair(0.62f, 0.68f), Pair(0.68f, 0.55f),
                Pair(0.55f, 0.48f), Pair(0.48f, 0.52f), Pair(0.52f, 0.40f), Pair(0.40f, 0.35f),
                Pair(0.35f, 0.28f), Pair(0.28f, 0.18f)
            )
            "1W" -> listOf(
                Pair(0.80f, 0.78f), Pair(0.78f, 0.82f), Pair(0.82f, 0.70f), Pair(0.70f, 0.60f),
                Pair(0.60f, 0.62f), Pair(0.62f, 0.45f), Pair(0.45f, 0.52f), Pair(0.52f, 0.38f),
                Pair(0.38f, 0.25f), Pair(0.25f, 0.15f)
            )
            "1M" -> listOf(
                Pair(0.85f, 0.82f), Pair(0.82f, 0.76f), Pair(0.76f, 0.78f), Pair(0.78f, 0.65f),
                Pair(0.65f, 0.70f), Pair(0.70f, 0.55f), Pair(0.55f, 0.45f), Pair(0.45f, 0.30f),
                Pair(0.30f, 0.35f), Pair(0.35f, 0.20f)
            )
            else -> listOf( // ALL
                Pair(0.75f, 0.72f), Pair(0.72f, 0.68f), Pair(0.68f, 0.60f), Pair(0.60f, 0.64f),
                Pair(0.64f, 0.55f), Pair(0.55f, 0.45f), Pair(0.45f, 0.48f), Pair(0.48f, 0.35f),
                Pair(0.35f, 0.25f), Pair(0.25f, 0.10f)
            )
        }

        val baseline = baseH * 0.9f

        rawCandles.forEachIndexed { index, (openRatio, closeRatio) ->
            val xCenter = (index * candleSpacing) + (candleSpacing / 2)
            
            // Scaled body according to animation progress
            val openY = baseline - (baseline - (openRatio * baseH)) * animProgress.value
            val closeY = baseline - (baseline - (closeRatio * baseH)) * animProgress.value
            
            val isGreen = closeRatio <= openRatio // in Android coords, smaller Y is higher up / profit!
            val candleAccentColor = if (isGreen) Color(0xFF2ED17B) else Color(0xFFFA5C7C)

            val highRatio = (minOf(openRatio, closeRatio) - 0.05f).coerceAtLeast(0.02f)
            val lowRatio = (maxOf(openRatio, closeRatio) + 0.04f).coerceAtMost(0.95f)

            val highY = baseline - (baseline - (highRatio * baseH)) * animProgress.value
            val lowY = baseline - (baseline - (lowRatio * baseH)) * animProgress.value

            // Draw Wick Line
            drawLine(
                color = candleAccentColor.copy(alpha = 0.8f),
                start = Offset(xCenter, highY),
                end = Offset(xCenter, lowY),
                strokeWidth = 1.5.dp.toPx()
            )

            // Draw Body Rect
            val topBody = minOf(openY, closeY)
            val bottomBody = maxOf(openY, closeY)
            val bodyHeight = (bottomBody - topBody).coerceAtLeast(2.dp.toPx())

            drawRect(
                color = candleAccentColor,
                topLeft = Offset(xCenter - (candleWidth / 2), topBody),
                size = androidx.compose.ui.geometry.Size(candleWidth, bodyHeight)
            )

            // Draw Volumetric Histogram Bar at the bottom
            val volRatio = when (index % 4) {
                0 -> 0.15f
                1 -> 0.35f
                2 -> 0.20f
                else -> 0.28f
            }
            val volHeight = (baseH * 0.25f * volRatio) * animProgress.value
            drawRect(
                color = candleAccentColor.copy(alpha = 0.18f),
                topLeft = Offset(xCenter - (candleWidth / 2), baseH - volHeight),
                size = androidx.compose.ui.geometry.Size(candleWidth, volHeight)
            )
        }

        // Peak floating green badge pointing to the peak candle (index 9 is the peak)
        if (rawCandles.isNotEmpty()) {
            val lastY = baseline - (baseline - (rawCandles.last().second * baseH)) * animProgress.value
            val lastX = ((rawCandles.size - 1) * candleSpacing) + (candleSpacing / 2)

            drawCircle(
                color = Color(0xFF2ED17B),
                radius = 4.dp.toPx(),
                center = Offset(lastX, lastY)
            )
        }
    }
}

// Interactive multi-timeframe Canvas line chart
@Composable
fun InteractiveLineChart(timeframe: String, lightTheme: Boolean) {
    val animProgress = remember { Animatable(0f) }
    LaunchedEffect(timeframe) {
        animProgress.snapTo(0f)
        animProgress.animateTo(
            targetValue = 1f,
            animationSpec = tween(durationMillis = 900, easing = PremiumEasing)
        )
    }

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(130.dp)
    ) {
        val width = size.width
        val height = size.height

        val rawPoints = when (timeframe) {
            "1D" -> listOf(
                Offset(0f, height * 0.9f),
                Offset(width * 0.25f, height * 0.85f),
                Offset(width * 0.5f, height * 0.78f),
                Offset(width * 0.75f, height * 0.45f),
                Offset(width, height * 0.2f)
            )
            "1W" -> listOf(
                Offset(0f, height * 0.8f),
                Offset(width * 0.2f, height * 0.82f),
                Offset(width * 0.4f, height * 0.5f),
                Offset(width * 0.6f, height * 0.62f),
                Offset(width * 0.8f, height * 0.3f),
                Offset(width, height * 0.15f)
            )
            "1M" -> listOf(
                Offset(0f, height * 0.85f),
                Offset(width * 0.15f, height * 0.82f),
                Offset(width * 0.3f, height * 0.72f),
                Offset(width * 0.45f, height * 0.67f),
                Offset(width * 0.65f, height * 0.74f),
                Offset(width * 0.82f, height * 0.3f),
                Offset(width, height * 0.22f)
            )
            else -> listOf(
                Offset(0f, height * 0.75f),
                Offset(width * 0.33f, height * 0.58f),
                Offset(width * 0.66f, height * 0.65f),
                Offset(width, height * 0.1f)
            )
        }

        // Animate spline points upwards from baseline
        val points = rawPoints.map { pt ->
            Offset(
                x = pt.x,
                y = height - (height - pt.y) * animProgress.value
            )
        }

        val splinePath = androidx.compose.ui.graphics.Path().apply {
            if (points.isNotEmpty()) {
                moveTo(points[0].x, points[0].y)
                for (i in 1 until points.size) {
                    val prev = points[i - 1]
                    val curr = points[i]
                    cubicTo(
                        (prev.x + curr.x) / 2, prev.y,
                        (prev.x + curr.x) / 2, curr.y,
                        curr.x, curr.y
                    )
                }
            }
        }

        // Under gradient fill
        val fillPath = androidx.compose.ui.graphics.Path().apply {
            addPath(splinePath)
            lineTo(width, height)
            lineTo(0f, height)
            close()
        }

        drawPath(
            path = fillPath,
            brush = Brush.verticalGradient(
                colors = listOf(NeonLime.copy(alpha = 0.25f), Color.Transparent)
            )
        )

        drawPath(
            path = splinePath,
            color = NeonLime,
            style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
        )

        // Draw active tracking pulse
        if (points.size >= 2) {
            val highLight = points[points.size - 2]
            drawCircle(
                color = NeonLime,
                radius = 5.dp.toPx(),
                center = highLight
            )
            drawCircle(
                color = NeonLime.copy(alpha = 0.35f),
                radius = 9.dp.toPx(),
                center = highLight
            )
        }
    }
}


// ==================== SCREEN 4: CONTROL ROOM ====================
@Composable
fun ControlRoomScreen(
    viewModel: TraderViewModel,
    lightTheme: Boolean,
    cardBg: Color,
    textPrimary: Color,
    borderCol: Color
) {
    var keyVisible by remember { mutableStateOf(false) }
    var secretVisible by remember { mutableStateOf(false) }

    // Settings Parameters
    val currentKey by viewModel.apiKey.collectAsState()
    val currentSecret by viewModel.apiSecret.collectAsState()
    val isConnected by viewModel.exchangeConnected.collectAsState()

    val profitTarget by viewModel.profitLockTarget.collectAsState()
    val maxDD by viewModel.maxDrawdown.collectAsState()
    val coinsToTrade by viewModel.maxCoinsToTrade.collectAsState()
    val gridLevels by viewModel.gridLevels.collectAsState()

    val pushEnabled by viewModel.pushNotificationsEnabled.collectAsState()

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
        contentPadding = PaddingValues(top = 20.dp, bottom = 40.dp)
    ) {
        item {
            AnimatedEntrance(delayMillis = 0) {
                ScreenHeader(viewModel, "Control Room", lightTheme, textPrimary, cardBg, borderCol)
            }
        }

        // EXCHANGE INTEGRATION BANNER STATUS
        item {
            AnimatedEntrance(delayMillis = 80) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("exchange_connection_banner"),
                    colors = CardDefaults.cardColors(
                        containerColor = if (isConnected) Color(0xFF102000) else Color(0xFF33090C)
                    ),
                    shape = RoundedCornerShape(20.dp),
                    border = BorderStroke(1.dp, if (isConnected) NeonLimeDim else Color(0xFF93000A))
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(if (isConnected) NeonLime else Color(0xFFFFB4AB))
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = if (isConnected) "Connected to Binance" else "Desynced / Disconnected",
                                style = MaterialTheme.typography.labelSmall.copy(
                                    color = if (isConnected) NeonLime else Color(0xFFFFB4AB),
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 11.sp
                                )
                            )
                        }

                        Switch(
                            checked = isConnected,
                            onCheckedChange = { viewModel.updateExchangeConnection(it) },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = DarkBackground,
                                checkedTrackColor = NeonLimeDim
                            ),
                            modifier = Modifier.testTag("exchange_toggle")
                        )
                    }
                }
            }
        }

        // INPUTS: CREDENTIALS EYE TOGGLES
        item {
            AnimatedEntrance(delayMillis = 140) {
                Text(
                    "Cryptographic Exchange Keys",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        item {
            AnimatedEntrance(delayMillis = 200) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(26.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        // API Key Field
                        OutlinedTextField(
                            value = currentKey,
                            onValueChange = { viewModel.updateCredentials(it, currentSecret) },
                            label = { Text("API Key") },
                            trailingIcon = {
                                IconButton(onClick = { keyVisible = !keyVisible }) {
                                    Icon(
                                        imageVector = if (keyVisible) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                                        contentDescription = null,
                                        tint = NeonLimeDim
                                    )
                                }
                            },
                            visualTransformation = if (keyVisible) VisualTransformation.None else PasswordVisualTransformation(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = NeonLimeDim,
                                unfocusedBorderColor = borderCol.copy(alpha = 0.4f),
                                focusedLabelColor = NeonLimeDim
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("input_api_key")
                        )

                        // API Secret Field
                        OutlinedTextField(
                            value = currentSecret,
                            onValueChange = { viewModel.updateCredentials(currentKey, it) },
                            label = { Text("API Secret") },
                            trailingIcon = {
                                IconButton(onClick = { secretVisible = !secretVisible }) {
                                    Icon(
                                        imageVector = if (secretVisible) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                                        contentDescription = null,
                                        tint = NeonLimeDim
                                    )
                                }
                            },
                            visualTransformation = if (secretVisible) VisualTransformation.None else PasswordVisualTransformation(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = NeonLimeDim,
                                unfocusedBorderColor = borderCol.copy(alpha = 0.4f),
                                focusedLabelColor = NeonLimeDim
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("input_api_secret")
                        )
                    }
                }
            }
        }

        // STRATEGY PARAMETERS SECTION
        item {
            AnimatedEntrance(delayMillis = 260) {
                Text(
                    "Grid Algorithm Engine Parameters",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        item {
            AnimatedEntrance(delayMillis = 320) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(26.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Column(
                        modifier = Modifier.padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(18.dp)
                    ) {
                        // Profit Lock slider
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    "Profit Lock Target (%)",
                                    style = MaterialTheme.typography.labelSmall.copy(color = textPrimary)
                                )
                                Text(
                                    text = String.format("%.2f%%", profitTarget),
                                    style = MaterialTheme.typography.labelSmall.copy(color = NeonLime, fontWeight = FontWeight.Bold)
                                )
                            }
                            Slider(
                                value = profitTarget,
                                onValueChange = { viewModel.updateStrategyParams(it, maxDD, coinsToTrade, gridLevels) },
                                valueRange = 0.1f..2.0f,
                                colors = SliderDefaults.colors(
                                    thumbColor = NeonLimeDim,
                                    activeTrackColor = NeonLime
                                ),
                                modifier = Modifier.testTag("slider_profit_lock")
                            )
                        }

                        // Max Drawdown Slider
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    "Max Drawdown Stop-Loss",
                                    style = MaterialTheme.typography.labelSmall.copy(color = textPrimary)
                                )
                                Text(
                                    text = String.format("%.1f%%", maxDD),
                                    style = MaterialTheme.typography.labelSmall.copy(color = NeonLime, fontWeight = FontWeight.Bold)
                                )
                            }
                            Slider(
                                value = maxDD,
                                onValueChange = { viewModel.updateStrategyParams(profitTarget, it, coinsToTrade, gridLevels) },
                                valueRange = 5.0f..50.0f,
                                colors = SliderDefaults.colors(
                                    thumbColor = NeonLimeDim,
                                    activeTrackColor = NeonLime
                                ),
                                modifier = Modifier.testTag("slider_drawdown")
                            )
                        }

                        // Max Coins Numeric Input (with Row Incrementor buttons)
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "Max Coins to Trade",
                                style = MaterialTheme.typography.labelSmall.copy(color = textPrimary)
                            )
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(
                                    onClick = { 
                                        if (coinsToTrade > 1) {
                                            viewModel.updateStrategyParams(profitTarget, maxDD, coinsToTrade - 1, gridLevels)
                                        }
                                    },
                                    modifier = Modifier
                                        .size(32.dp)
                                        .background(Color(0x339FFB06), CircleShape)
                                ) {
                                    Icon(Icons.Default.Remove, contentDescription = null, tint = NeonLimeDim, modifier = Modifier.size(16.dp))
                                }
                                Text(
                                    text = "$coinsToTrade",
                                    style = MaterialTheme.typography.labelLarge.copy(color = textPrimary, fontWeight = FontWeight.Bold),
                                    modifier = Modifier
                                        .padding(horizontal = 14.dp)
                                        .testTag("label_max_coins")
                                )
                                IconButton(
                                    onClick = { 
                                        if (coinsToTrade < 10) {
                                            viewModel.updateStrategyParams(profitTarget, maxDD, coinsToTrade + 1, gridLevels)
                                        }
                                    },
                                    modifier = Modifier
                                        .size(32.dp)
                                        .background(Color(0x339FFB06), CircleShape)
                                ) {
                                    Icon(Icons.Default.Add, contentDescription = null, tint = NeonLimeDim, modifier = Modifier.size(16.dp))
                                }
                            }
                        }

                        // Grid Levels Numeric Layout
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "Grid Levels",
                                style = MaterialTheme.typography.labelSmall.copy(color = textPrimary)
                            )
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                IconButton(
                                    onClick = { 
                                        if (gridLevels > 2) {
                                            viewModel.updateStrategyParams(profitTarget, maxDD, coinsToTrade, gridLevels - 1)
                                        }
                                    },
                                    modifier = Modifier
                                        .size(32.dp)
                                        .background(Color(0x339FFB06), CircleShape)
                                ) {
                                    Icon(Icons.Default.Remove, contentDescription = null, tint = NeonLimeDim, modifier = Modifier.size(16.dp))
                                }
                                Text(
                                    text = "$gridLevels",
                                    style = MaterialTheme.typography.labelLarge.copy(color = textPrimary, fontWeight = FontWeight.Bold),
                                    modifier = Modifier
                                        .padding(horizontal = 14.dp)
                                        .testTag("label_grid_levels")
                                )
                                IconButton(
                                    onClick = { 
                                        if (gridLevels < 20) {
                                            viewModel.updateStrategyParams(profitTarget, maxDD, coinsToTrade, gridLevels + 1)
                                        }
                                    },
                                    modifier = Modifier
                                        .size(32.dp)
                                        .background(Color(0x339FFB06), CircleShape)
                                ) {
                                    Icon(Icons.Default.Add, contentDescription = null, tint = NeonLimeDim, modifier = Modifier.size(16.dp))
                                }
                            }
                        }
                    }
                }
            }
        }

        // PREFERENCES SECTION
        item {
            AnimatedEntrance(delayMillis = 380) {
                Text(
                    "System Interface Codes",
                    style = MaterialTheme.typography.labelSmall.copy(
                        color = if (lightTheme) Color(0xFF4C4C4C) else TextSecondary,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        fontSize = 11.sp
                    )
                )
            }
        }

        item {
            AnimatedEntrance(delayMillis = 440) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = cardBg),
                    shape = RoundedCornerShape(26.dp),
                    border = BorderStroke(1.dp, borderCol.copy(alpha = 0.5f))
                ) {
                    Column(
                        modifier = Modifier.padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(18.dp)
                    ) {
                        // Push Notification setting row
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    "Push Notifications Alert",
                                    style = MaterialTheme.typography.labelSmall.copy(color = textPrimary, fontWeight = FontWeight.Bold)
                                )
                                Text(
                                    "Alert me when a Profit Lock hits",
                                    style = MaterialTheme.typography.labelSmall.copy(color = if (lightTheme) Color(0xFF7c7c7c) else TextSecondary.copy(alpha = 0.6f), fontSize = 10.sp)
                                )
                            }
                            Switch(
                                checked = pushEnabled,
                                onCheckedChange = { viewModel.toggleSystemPreferences(it, lightTheme) },
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = DarkBackground,
                                    checkedTrackColor = NeonLimeDim
                                ),
                                modifier = Modifier.testTag("push_notifications_switch")
                            )
                        }

                        // Theme setting row
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(
                                    "Interface Luminescence",
                                    style = MaterialTheme.typography.labelSmall.copy(color = textPrimary, fontWeight = FontWeight.Bold)
                                )
                                Text(
                                    "Toggle light / dark terminal modes",
                                    style = MaterialTheme.typography.labelSmall.copy(color = if (lightTheme) Color(0xFF7c7c7c) else TextSecondary.copy(alpha = 0.6f), fontSize = 10.sp)
                                )
                            }
                            Switch(
                                checked = lightTheme,
                                onCheckedChange = { viewModel.toggleSystemPreferences(pushEnabled, it) },
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = DarkBackground,
                                    checkedTrackColor = NeonLimeDim
                                ),
                                modifier = Modifier.testTag("theme_selection_switch")
                            )
                        }
                    }
                }
            }
        }

        // RESET SYSTEM CONTROLS
        item {
            AnimatedEntrance(delayMillis = 500) {
                Button(
                    onClick = { viewModel.clearHistory() },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF33090C)),
                    shape = RoundedCornerShape(18.dp),
                    border = BorderStroke(1.dp, Color(0xFF93000A)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("btn_reset_audit"),
                    contentPadding = PaddingValues(16.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.DeleteForever,
                        contentDescription = null,
                        tint = Color(0xFFFFB4AB)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Clear Audit Path & Archives",
                        style = MaterialTheme.typography.labelSmall.copy(
                            color = Color(0xFFFFB4AB),
                            fontWeight = FontWeight.ExtraBold,
                            fontSize = 11.sp
                        )
                    )
                }
            }
        }
    }
}

// End of File
