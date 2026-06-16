"""
telegram_alerts.py
==================
Smart Grid Trader Pro — Telegram Alerter

Sends real-time trade and status notifications via Telegram.
Uses python-telegram-bot (async) in a fire-and-forget pattern so that
Telegram errors NEVER block or crash the trading bot.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """
    Sends formatted Telegram messages for key bot events.

    Loads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from .env.
    All send failures are caught and logged silently — they will
    never propagate to the trading engine.
    """

    def __init__(self) -> None:
        self._token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self._enabled = bool(self._token and self._chat_id)
        if not self._enabled:
            logger.warning(
                "TelegramAlerter: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — "
                "alerts disabled."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, coro) -> None:
        """Execute an async coroutine from synchronous code."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(coro)
        except Exception as exc:
            logger.error("TelegramAlerter._run error: %s", exc)

    async def _send_async(self, text: str) -> None:
        """Send a Markdown message; swallow all Telegram errors."""
        if not self._enabled:
            return
        try:
            bot = Bot(token=self._token)
            await bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except TelegramError as exc:
            logger.error("Telegram send failed (TelegramError): %s", exc)
        except Exception as exc:
            logger.error("Telegram send failed (unexpected): %s", exc)

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ------------------------------------------------------------------
    # Public alert methods
    # ------------------------------------------------------------------

    def send_message(self, text: str) -> None:
        """
        Send a generic Telegram message.

        Args:
            text: Plain or Markdown-formatted message string.
        """
        self._run(self._send_async(text))

    def alert_regime_change(self, old_regime: str, new_regime: str) -> None:
        """
        Notify when the market regime changes.

        Args:
            old_regime: Previous regime string.
            new_regime: New regime string.
        """
        emoji_map = {"RANGING": "🔄", "TRENDING": "📈", "IDLE": "😴"}
        msg = (
            f"{emoji_map.get(new_regime, '❓')} *Regime Change*\n"
            f"`{old_regime}` → `{new_regime}`\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))

    def alert_order_filled(
        self, side: str, price: float, qty: float, pnl: float
    ) -> None:
        """
        Notify when a grid order is filled.

        Args:
            side:  'BUY' or 'SELL'.
            price: Fill price.
            qty:   Fill quantity.
            pnl:   Realized profit/loss for this fill.
        """
        side_emoji = "🟢" if side == "BUY" else "🔴"
        pnl_emoji  = "💰" if pnl >= 0 else "📉"
        msg = (
            f"{side_emoji} *Order Filled* — {side}\n"
            f"📍 Price : `{price:.4f}` USDT\n"
            f"📦 Qty   : `{qty:.6f}`\n"
            f"{pnl_emoji} PnL   : `{pnl:+.4f}` USDT\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))

    def alert_safe_mode(self, reason: str, balance: float) -> None:
        """
        Send an IMMEDIATE SAFE MODE alert.

        Args:
            reason:  Human-readable trigger description.
            balance: Current USDT balance.
        """
        msg = (
            f"🚨 *SAFE MODE ACTIVATED*\n"
            f"⚠️ Reason  : {reason}\n"
            f"💵 Balance : `{balance:.2f}` USDT\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))

    def send_monthly_report(
        self, profit: float, withdrawal: float, reinvestment: float
    ) -> None:
        """
        Send the end-of-month profit settlement summary.

        Args:
            profit:       Total realized monthly profit.
            withdrawal:   80 % taken out.
            reinvestment: 20 % reinvested.
        """
        msg = (
            f"📊 *Monthly Settlement Report*\n"
            f"────────────────────────\n"
            f"💹 Total Profit    : `{profit:+.4f}` USDT\n"
            f"💸 Withdrawal (80%): `{withdrawal:.4f}` USDT\n"
            f"🔄 Reinvested (20%): `{reinvestment:.4f}` USDT\n"
            f"────────────────────────\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))

    def send_daily_summary(
        self,
        pnl: float,
        trades: int,
        regime: str,
        balance: float,
    ) -> None:
        """
        Send end-of-day summary.

        Args:
            pnl:     Today's realized PnL.
            trades:  Number of trades today.
            regime:  Current market regime string.
            balance: Current USDT balance.
        """
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        regime_emoji = {"RANGING": "🔄", "TRENDING": "⚡", "IDLE": "😴"}.get(regime, "❓")
        msg = (
            f"🌙 *Daily Summary*\n"
            f"────────────────────────\n"
            f"{pnl_emoji} PnL Today  : `{pnl:+.4f}` USDT\n"
            f"🔢 Trades   : `{trades}`\n"
            f"{regime_emoji} Regime    : `{regime}`\n"
            f"💵 Balance  : `{balance:.2f}` USDT\n"
            f"────────────────────────\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))

    # ── Portfolio Profit Lock Bot alerts ───────────────────────────────

    def alert_profit_locked(
        self,
        cycle_num: int,
        coins: list,
        net_pnl: float,
        pct_gain: float,
        today_cycles: int,
        today_profit: float,
    ) -> None:
        """
        Send a notification when the portfolio profit target is reached
        and all positions are closed (profit locked).

        Args:
            cycle_num:     Sequential cycle number.
            coins:         List of symbols traded this cycle.
            net_pnl:       Net profit locked in USDT.
            pct_gain:      Profit as a decimal fraction (0.005 = 0.5%).
            today_cycles:  Total lock cycles completed today.
            today_profit:  Total profit locked today in USDT.
        """
        coins_str = ", ".join(coins)
        msg = (
            f"🔒 *Profit Lock #{cycle_num}* — TARGET REACHED\n"
            f"────────────────────────\n"
            f"🪙 Coins     : `{coins_str}`\n"
            f"💰 Net PnL   : `{net_pnl:+.4f}` USDT\n"
            f"📈 Gain      : `{pct_gain * 100:+.3f}%`\n"
            f"────────────────────────\n"
            f"📅 Today     : `{today_cycles}` locks | `{today_profit:+.4f}` USDT\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))

    def alert_portfolio_safe_mode(
        self,
        reason: str,
        net_pnl: float,
        drawdown_pct: float,
    ) -> None:
        """
        Send an immediate safe-mode alert for the portfolio bot.

        Args:
            reason:       Human-readable trigger description.
            net_pnl:      Current net PnL (negative = loss).
            drawdown_pct: Current drawdown as a percentage.
        """
        msg = (
            f"🚨 *PORTFOLIO SAFE MODE*\n"
            f"⚠️ Reason    : {reason}\n"
            f"📉 Net PnL   : `{net_pnl:+.4f}` USDT\n"
            f"🔻 Drawdown  : `{drawdown_pct * 100:.2f}%`\n"
            f"🛑 All positions closed\n"
            f"🕐 {self._ts()}"
        )
        self._run(self._send_async(msg))
