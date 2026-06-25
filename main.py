# main.py
import asyncio
import logging
import sqlite3
import time
import datetime
import ccxt
import threading
from typing import Any, Optional

from config import (
    CCXT_SYMBOL,
    BASE_ASSET,
    TIMEFRAME,
    FLAT_TIMEOUT_SECONDS,
    MAX_VOL_USDT,
    ORDER_LIFETIME_SECONDS,
    MIN_ENTRY_DISCOUNT_PERC,
)
from database import (
    init_db,
    get_setting,
    set_setting,
    DB_BOT,
    save_trade_history,
)
from mexc_client import (
    fetch_market_klines,
    calculate_position_size,
    execute_order_safe,
    check_order_safe,
    get_current_price_safe,
)
from market_structure_analysis import calculate_trade_parameters, calculate_target_wall
from bot_interface import bot

# Налаштування базового логера без ламаючих фільтрів
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
mexc = ccxt.mexc()

STAGE_IDLE = "IDLE"
STAGE_WAITING_BUY = "WAITING_BUY"
STAGE_HOLDING_SELL = "HOLDING_SELL"

TERMINAL_ORDER_STATUSES = [
    "TIMEOUT_INVALID",
    "INVALID_SL",
    "INVALID_FVG_BREAK",
    "SUPERSEDED",
    "MISSED_TP",
    "CANCELLED",
    "TAKE_PROFIT",
    "STOP_LOSS",
    "CLOSED_TP",
    "CLOSED_SL",
    "CLOSED_FLAT",
    "CLOSED_FLAT_SAVED",
]


def get_log_time() -> str:
    """Повертає поточний локальний час для початку рядка логу."""
    return f"\033[0m[{datetime.datetime.now().strftime('%H:%M:%S')}] "


def get_cooldown_from_db() -> float:
    """Зчитує мітку кулдауну з SQLite."""
    try:
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("SELECT value FROM settings WHERE key = 'cooldown_until'")
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row and row[0] else 0.0
    except Exception:
        return 0.0


def set_cooldown_to_db(seconds_from_now: int, reason: str = "UNKNOWN") -> None:
    """Записує мітку кулдауну в SQLite з причиною для прозорого логування."""
    try:
        ts_end = time.time() + seconds_from_now
        now_ts = int(time.time())
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('cooldown_until', ?)",
            (str(ts_end),),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('cooldown_reason', ?)",
            (str(reason),),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('cooldown_started_at', ?)",
            (str(now_ts),),
        )
        conn.commit()
        conn.close()

        print(
            f"{get_log_time()}🧊 COOLDOWN SET | "
            f"Reason={reason} | Seconds={seconds_from_now}"
        )

    except Exception as e:
        print(f"{get_log_time()}\033[91m❌ Помилка запису кулдауну в базу: {e}\033[0m")


async def cancel_all_buy_orders() -> dict[str, Any]:
    """Безпечне скасування всіх відкритих лімітних ордерів BUY з підсумком для Telegram."""
    summary: dict[str, Any] = {
        "attempted": 0,
        "cancelled": [],
        "filled_during_stop": [],
        "failed": [],
        "remaining": [],
        "error": "",
    }

    try:
        print(f"{get_log_time()}🧹 Активовано захист: Скасування відкритих лімітних ордерів BUY...")
        from mexc_client import get_sync_exchange

        exchange = await asyncio.to_thread(get_sync_exchange)
        open_orders = await asyncio.to_thread(exchange.fetch_open_orders, CCXT_SYMBOL)
        open_buy_orders = [
            order for order in open_orders
            if str(order.get("side", "")).lower() == "buy"
        ]

        summary["attempted"] = len(open_buy_orders)

        if not open_buy_orders:
            print(f"{get_log_time()}🧹 BUY LIMIT для скасування не знайдено.")
            return summary

        for order in open_buy_orders:
            order_id = str(order.get("id", "")).strip()
            if not order_id:
                continue

            try:
                await asyncio.to_thread(exchange.cancel_order, order_id, CCXT_SYMBOL)
                await asyncio.sleep(0.5)

                checked = await check_order_safe(order_id)
                exchange_status = (
                    str(checked.get("status", "unknown")).lower()
                    if checked
                    else "unknown"
                )

                item = {"id": order_id, "status": exchange_status}

                if exchange_status in ["canceled", "cancelled"]:
                    summary["cancelled"].append(item)
                    print(
                        f"{get_log_time()}❌ Лімітний ордер BUY {order_id} "
                        f"успішно анульовано. Status={exchange_status}"
                    )
                    continue

                if exchange_status in ["closed", "filled"]:
                    summary["filled_during_stop"].append(item)
                    print(
                        f"{get_log_time()}🚨 BUY LIMIT FILLED DURING STOP CANCEL | "
                        f"Order={order_id} | Status={exchange_status}"
                    )
                    continue

                summary["failed"].append(item)
                print(
                    f"{get_log_time()}🚨 BUY LIMIT CANCEL NOT VERIFIED | "
                    f"Order={order_id} | Status={exchange_status}"
                )

            except Exception as cancel_error:
                summary["failed"].append(
                    {"id": order_id, "status": f"error: {cancel_error}"}
                )
                print(
                    f"{get_log_time()}🚨 Помилка скасування BUY LIMIT {order_id}: "
                    f"{cancel_error}"
                )

        try:
            open_orders_after = await asyncio.to_thread(exchange.fetch_open_orders, CCXT_SYMBOL)
            summary["remaining"] = [
                str(order.get("id", ""))
                for order in open_orders_after
                if str(order.get("side", "")).lower() == "buy"
            ]

            if summary["remaining"]:
                print(
                    f"{get_log_time()}🚨 BUY LIMIT REMAINING AFTER STOP CANCEL | "
                    f"Orders={summary['remaining']}"
                )

        except Exception as verify_error:
            summary["error"] = f"post_cancel_verify_error: {verify_error}"
            print(
                f"{get_log_time()}⚠️ Не вдалося перевірити open BUY orders після STOP: "
                f"{verify_error}"
            )

        return summary

    except Exception as e:
        summary["error"] = str(e)
        print(f"{get_log_time()}Помилка при скасуванні BUY-ордерів: {e}")
        return summary


async def cancel_specific_order_safe(order_id: str) -> bool:
    """Скасовує конкретний ордер на біржі за order_id і перевіряє результат."""
    try:
        from mexc_client import get_sync_exchange

        exchange = await asyncio.to_thread(get_sync_exchange)
        print(f"{get_log_time()}🧹 Скасування конкретного ордера: {order_id}")

        await asyncio.to_thread(exchange.cancel_order, order_id, CCXT_SYMBOL)
        await asyncio.sleep(1)

        checked = await check_order_safe(order_id)
        if checked:
            status = str(checked.get("status", "")).lower()
            if status in ["canceled", "cancelled", "closed"]:
                print(f"{get_log_time()}✅ Ордер {order_id} має статус: {status}")
                return True

            print(
                f"{get_log_time()}🚨 Ордер {order_id} не підтверджено як скасований. "
                f"Статус: {status}"
            )
            return False

        print(f"{get_log_time()}⚠️ Не вдалося перечитати ордер після cancel: {order_id}")
        return False

    except Exception as e:
        print(f"{get_log_time()}🚨 Помилка скасування конкретного ордера {order_id}: {e}")
        return False


async def exchange_position_guard_before_buy() -> bool:
    """
    Останній захист перед BUY.

    Returns True, якщо BUY треба заблокувати.
    """
    try:
        from mexc_client import get_spot_balance_details_safe, get_sync_exchange
        from bot_interface import send_direct_notification

        base_balance = await get_spot_balance_details_safe(BASE_ASSET)
        base_free = float(base_balance.get("free", 0.0))
        base_used = float(base_balance.get("used", 0.0))
        base_total = float(base_balance.get("total", 0.0))

        exchange = await asyncio.to_thread(get_sync_exchange)
        open_orders = await asyncio.to_thread(exchange.fetch_open_orders, CCXT_SYMBOL)
        open_sell_orders = [
            order for order in open_orders
            if str(order.get("side", "")).lower() == "sell"
        ]

        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT order_id, status
            FROM orders
            WHERE status = 'SELL_ACTIVE'
            ORDER BY id DESC
            LIMIT 1
            """
        )
        db_active_position = cursor.fetchone()
        conn.close()

        current_price = await get_current_price_safe()
        dust_value_usdt = 1.0
        total_value_usdt = base_total * current_price if current_price > 0 else 0.0
        used_value_usdt = base_used * current_price if current_price > 0 else 0.0

        guard_triggered = (
            total_value_usdt > dust_value_usdt
            or used_value_usdt > dust_value_usdt
            or len(open_sell_orders) > 0
            or db_active_position is not None
        )

        if not guard_triggered:
            return False

        print(
            f"{get_log_time()}🚨 EXCHANGE POSITION GUARD BLOCKED BUY | "
            f"{BASE_ASSET} free={base_free} | used={base_used} | total={base_total} | "
            f"used_value={used_value_usdt:.2f} USDT | total_value={total_value_usdt:.2f} USDT | "
            f"open_sell_orders={len(open_sell_orders)} | db_sell_active={db_active_position}"
        )

        set_setting("bot_status", "STOPPED")

        await send_direct_notification(
            f"🚨 *CRITICAL: BUY ЗАБЛОКОВАНО*\n\n"
            f"Перед новим BUY бот знайшов ознаки незакритої позиції "
            f"або відкритого SELL order.\n\n"
            f"● {BASE_ASSET} free: `{base_free}`\n"
            f"● {BASE_ASSET} used: `{base_used}`\n"
            f"● {BASE_ASSET} total: `{base_total}`\n"
            f"● Used value: `{used_value_usdt:.2f} USDT`\n"
            f"● Total value: `{total_value_usdt:.2f} USDT`\n"
            f"● Open SELL orders: `{len(open_sell_orders)}`\n"
            f"● DB SELL_ACTIVE: `{db_active_position}`\n\n"
            f"Новий BUY НЕ виставлено.\n"
            f"Бот переведено в STOPPED.\n\n"
            f"Перевір MEXC вручну."
        )

        return True

    except Exception as e:
        print(f"{get_log_time()}🚨 EXCHANGE POSITION GUARD ERROR | BUY blocked fail-safe | Error={e}")
        set_setting("bot_status", "STOPPED")

        try:
            from bot_interface import send_direct_notification
            await send_direct_notification(
                f"🚨 *CRITICAL: BUY ЗАБЛОКОВАНО*\n\n"
                f"Помилка exchange-position guard перед новим BUY.\n\n"
                f"● Error: `{e}`\n\n"
                f"Новий BUY НЕ виставлено.\n"
                f"Бот переведено в STOPPED."
            )
        except Exception:
            pass

        return True


def remember_missed_tp_context(order_id: str, entry_p: float, sl_p: float, tp_p: float) -> None:
    """Запамʼятовує сетап, де ціна дійшла до TP без входу."""
    set_setting("blocked_setup_reason", "MISSED_TP")
    set_setting("blocked_setup_order_id", str(order_id))
    set_setting("blocked_setup_entry", str(entry_p))
    set_setting("blocked_setup_sl", str(sl_p))
    set_setting("blocked_setup_tp", str(tp_p))
    set_setting("blocked_setup_ts", str(int(time.time())))


def is_blocked_missed_tp_context(entry_p: float, sl_p: float) -> bool:
    """Перевіряє, чи новий сетап схожий на недавній MISSED_TP-сетап."""
    if get_setting("blocked_setup_reason", "") != "MISSED_TP":
        return False

    try:
        blocked_entry = float(get_setting("blocked_setup_entry", "0"))
        blocked_sl = float(get_setting("blocked_setup_sl", "0"))
        blocked_ts = int(get_setting("blocked_setup_ts", "0"))

        if blocked_entry <= 0 or blocked_sl <= 0 or blocked_ts <= 0:
            return False

        max_age_seconds = 6 * 60 * 60
        if time.time() - blocked_ts > max_age_seconds:
            return False

        entry_diff = abs(entry_p - blocked_entry) / blocked_entry
        sl_diff = abs(sl_p - blocked_sl) / blocked_sl

        return entry_diff <= 0.0015 and sl_diff <= 0.0015

    except Exception as e:
        print(f"{get_log_time()}⚠️ MISSED_TP_CONTEXT_CHECK_ERROR | Error={e}")
        return False


async def notify_buy_limit_cancelled(
    reason: str,
    order_id: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    current_price: float = 0.0,
) -> None:
    """Telegram-повідомлення про скасування BUY LIMIT із причиною."""
    try:
        from bot_interface import send_direct_notification

        current_line = ""
        if current_price and current_price > 0:
            current_line = f"● Поточна ціна: `{current_price:.4f}`\n"

        await send_direct_notification(
            f"⚠️ *BUY LIMIT скасовано*\n\n"
            f"● Причина: `{reason}`\n"
            f"● Ордер: `{order_id}`\n\n"
            f"● Entry: `{float(entry_price):.4f}`\n"
            f"● SL: `{float(sl_price):.4f}`\n"
            f"● TP: `{float(tp_price):.4f}`\n"
            f"{current_line}"
        )

    except Exception as e:
        print(f"{get_log_time()}⚠️ Не вдалося надіслати Telegram про скасування BUY LIMIT: {e}")


async def resolve_exit_price_after_sell(
    sell_result: Optional[dict],
    fallback_price: float,
    entry_price: float,
    max_deviation_pct: float = 0.01,
) -> float:
    """
    Безпечно визначає фактичну ціну виходу після SELL.

    Якщо біржа повертає підозрілу ціну далеко від fallback_price,
    кандидат відкидається, щоб не зіпсувати PnL.
    """
    fallback_price = float(fallback_price)
    entry_price = float(entry_price)
    candidates = []

    def safe_float(value):
        try:
            if value is None:
                return None
            value_f = float(value)
            if value_f <= 0:
                return None
            return value_f
        except Exception:
            return None

    def collect_candidates(order_data):
        if not order_data:
            return

        avg_price = safe_float(order_data.get("average"))
        if avg_price:
            candidates.append(("average", avg_price))

        raw_price = safe_float(order_data.get("price"))
        if raw_price:
            candidates.append(("price", raw_price))

        filled = safe_float(order_data.get("filled"))
        cost = safe_float(order_data.get("cost"))
        if filled and cost and filled > 0:
            candidates.append(("cost/filled", cost / filled))

        info = order_data.get("info", {})
        if isinstance(info, dict):
            info_avg = safe_float(info.get("average"))
            if info_avg:
                candidates.append(("info.average", info_avg))

            info_price = safe_float(info.get("price"))
            if info_price:
                candidates.append(("info.price", info_price))

    collect_candidates(sell_result)

    try:
        if sell_result and sell_result.get("id"):
            await asyncio.sleep(2)
            fetched_order = await check_order_safe(sell_result["id"])
            if fetched_order:
                collect_candidates(fetched_order)
    except Exception as e:
        print(f"{get_log_time()}⚠️ Не вдалося уточнити SELL order через fetch_order: {e}")

    if fallback_price <= 0:
        fallback_price = entry_price

    for source, price in candidates:
        deviation = abs(price - fallback_price) / fallback_price if fallback_price > 0 else 0.0

        if deviation <= max_deviation_pct:
            print(
                f"{get_log_time()}✅ EXIT PRICE VERIFIED | "
                f"Source={source} | Exit={price:.4f} | Fallback={fallback_price:.4f} | "
                f"Deviation={deviation * 100:.2f}%"
            )
            return price

        print(
            f"{get_log_time()}⚠️ EXIT PRICE REJECTED | "
            f"Source={source} | Exit={price:.4f} | Fallback={fallback_price:.4f} | "
            f"Deviation={deviation * 100:.2f}%"
        )

    print(f"{get_log_time()}⚠️ EXIT PRICE FALLBACK USED | Exit={fallback_price:.4f}")
    return fallback_price


async def sync_local_stage() -> str:
    """Синхронізація локального стейджу з біржею та SQLite."""
    try:
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, status FROM orders ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            return STAGE_IDLE

        ord_id, status = row

        if status in TERMINAL_ORDER_STATUSES:
            return STAGE_IDLE

        if status == "BUY_PENDING":
            order_status = await check_order_safe(ord_id)

            if order_status:
                exchange_status = str(order_status.get("status", "")).lower()

                if exchange_status == "closed":
                    conn = sqlite3.connect(DB_BOT)
                    cursor = conn.cursor()
                    cursor.execute("SELECT status FROM orders WHERE order_id = ?", (ord_id,))
                    db_row = cursor.fetchone()

                    if not db_row:
                        conn.close()
                        return STAGE_IDLE

                    current_db_status = db_row[0]
                    if current_db_status != "BUY_PENDING":
                        conn.close()
                        return STAGE_HOLDING_SELL

                    print(
                        f"{get_log_time()}🔄 Синхронізація: Ордер #{ord_id} виконано! "
                        f"Перехід до LONG-супроводу."
                    )

                    cursor.execute(
                        """
                        SELECT price, qty, tp_price, sl_price
                        FROM orders
                        WHERE order_id = ?
                        """,
                        (ord_id,),
                    )
                    trade_row = cursor.fetchone()

                    if trade_row:
                        entry_price, qty, tp_price, sl_price = trade_row
                        entry_price_f = float(entry_price)
                        qty_f = float(qty)
                        tp_price_f = float(tp_price)
                        sl_price_f = float(sl_price)
                        risk = entry_price_f - sl_price_f
                        reward = tp_price_f - entry_price_f
                        rr = reward / risk if risk > 0 else 0.0
                        position_size = entry_price_f * qty_f

                        from bot_interface import send_direct_notification

                        await send_direct_notification(
                            f"✅ *BUY LIMIT виконано!*\n\n"
                            f"Позиція перейшла у супровід: `SELL_ACTIVE`\n\n"
                            f"● Ордер: `{ord_id}`\n"
                            f"● Вхід: `{entry_price_f:.4f}`\n"
                            f"● Кількість: `{qty_f:.2f} {BASE_ASSET}`\n"
                            f"● Обсяг позиції: `{position_size:.2f} USDT`\n\n"
                            f"● TP: `{tp_price_f:.4f}`\n"
                            f"● SL: `{sl_price_f:.4f}`\n"
                            f"● R:R: `1:{rr:.2f}`"
                        )

                    cursor.execute(
                        """
                        UPDATE orders
                        SET status = 'SELL_ACTIVE', timestamp = ?
                        WHERE order_id = ? AND status = 'BUY_PENDING'
                        """,
                        (int(time.time()), ord_id),
                    )
                    conn.commit()
                    conn.close()

                    # P0: якщо користувач уже натиснув STOP/STOPPING, не повертаємо сканер у RUNNING.
                    bot_status_now = get_setting("bot_status", "STOPPED")
                    if bot_status_now in ["STOPPED", "STOPPING"]:
                        set_setting("bot_status", "STOPPED")
                        print(
                            f"{get_log_time()}🛑 BUY FILLED WHILE STOPPED | "
                            f"Position is SELL_ACTIVE, scanner remains STOPPED."
                        )
                    else:
                        set_setting("bot_status", "RUNNING")

                    return STAGE_HOLDING_SELL

                if exchange_status in ["cancelled", "canceled"]:
                    conn = sqlite3.connect(DB_BOT)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE orders
                        SET status = 'CANCELLED'
                        WHERE order_id = ? AND status = 'BUY_PENDING'
                        """,
                        (ord_id,),
                    )
                    conn.commit()
                    conn.close()
                    return STAGE_IDLE

            return STAGE_WAITING_BUY

        if status == "SELL_ACTIVE":
            return STAGE_HOLDING_SELL

        return STAGE_IDLE

    except Exception as e:
        print(f"{get_log_time()}Помилка верифікації поточного стейджу: {e}")
        return STAGE_IDLE


async def close_active_position(
    order_id: str,
    entry_price: float,
    qty: float,
    tp_price: float,
    sl_price: float,
    trade_ts: int,
    current_price: float,
    close_reason: str,
    cooldown_seconds: int,
    emoji: str,
    title: str,
) -> bool:
    """Єдиний безпечний шлях закриття позиції market SELL + trade_history + CLOSED_* після SELL."""
    sell_result = await execute_order_safe(
        side="sell",
        order_type="market",
        qty=qty,
    )

    if not sell_result:
        print(
            f"{get_log_time()}🚨 CRITICAL: {close_reason} SELL FAILED | "
            f"Order={order_id} | Qty={qty} | Position remains SELL_ACTIVE"
        )

        try:
            from bot_interface import send_direct_notification
            await send_direct_notification(
                f"🚨 *КРИТИЧНО: SELL не виконано!*\n\n"
                f"● Причина: `{close_reason}`\n"
                f"● Ордер: `{order_id}`\n"
                f"● Qty: `{float(qty):.2f} {BASE_ASSET}`\n"
                f"● Поточна ціна: `{float(current_price):.4f}`\n\n"
                f"Позиція НЕ позначена як закрита. Бот продовжить моніторинг."
            )
        except Exception as e:
            print(f"{get_log_time()}⚠️ Не вдалося надіслати Telegram про SELL FAILED: {e}")

        await asyncio.sleep(5)
        return False

    exit_price = await resolve_exit_price_after_sell(
        sell_result=sell_result,
        fallback_price=current_price,
        entry_price=entry_price,
    )

    entry_price_f = float(entry_price)
    qty_f = float(qty)
    tp_price_f = float(tp_price)
    sl_price_f = float(sl_price)
    position_size = entry_price_f * qty_f
    pnl_usdt = (exit_price - entry_price_f) * qty_f
    pnl_pct = ((exit_price - entry_price_f) / entry_price_f) * 100 if entry_price_f > 0 else 0.0
    pnl_sign = "+" if pnl_usdt >= 0 else ""
    pct_sign = "+" if pnl_pct >= 0 else ""

    trade_stats = save_trade_history(
        order_id=order_id,
        symbol=CCXT_SYMBOL,
        close_reason=close_reason,
        entry_price=entry_price_f,
        exit_price=exit_price,
        tp_price=tp_price_f,
        sl_price=sl_price_f,
        qty=qty_f,
        opened_at=int(trade_ts),
    )

    conn = sqlite3.connect(DB_BOT)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status = ? WHERE order_id = ? AND status = 'SELL_ACTIVE'",
        (close_reason, order_id),
    )
    conn.commit()
    conn.close()

    if cooldown_seconds > 0:
        set_cooldown_to_db(cooldown_seconds, close_reason)

    print(
        f"{get_log_time()}📒 TRADE HISTORY SAVED | "
        f"Reason={close_reason} | "
        f"PnL={trade_stats['pnl_usdt']:+.4f} USDT ({trade_stats['pnl_pct']:+.2f}%)"
    )

    print(
        f"{get_log_time()}{emoji} [TRADE RESULT | {close_reason}] "
        f"Entry={entry_price_f:.4f} | Exit={exit_price:.4f} | "
        f"Qty={qty_f:.2f} {BASE_ASSET} | Size={position_size:.2f} USDT | "
        f"PnL={pnl_sign}{pnl_usdt:.4f} USDT ({pct_sign}{pnl_pct:.2f}%) | "
        f"TP={tp_price_f:.4f} | SL={sl_price_f:.4f}"
    )

    try:
        from bot_interface import send_direct_notification
        await send_direct_notification(
            f"{emoji} *{title}*\n\n"
            f"● Причина: `{close_reason}`\n"
            f"● Вхід: `{entry_price_f:.4f}`\n"
            f"● Вихід: `{exit_price:.4f}`\n"
            f"● Кількість: `{qty_f:.2f} {BASE_ASSET}`\n"
            f"● Обсяг позиції: `{position_size:.2f} USDT`\n\n"
            f"● TP: `{tp_price_f:.4f}`\n"
            f"● Фінальний SL: `{sl_price_f:.4f}`\n\n"
            f"💰 PnL: `{pnl_sign}{pnl_usdt:.4f} USDT`\n"
            f"📊 Результат: `{pct_sign}{pnl_pct:.2f}%`"
        )
    except Exception as e:
        print(f"{get_log_time()}⚠️ Не вдалося надіслати Telegram про {close_reason}: {e}")

    return True


async def mark_escape_limit_filled(
    order_id: str,
    escape_order: dict,
    entry_price: float,
    qty: float,
    tp_price: float,
    sl_price: float,
    trade_ts: int,
    fallback_price: float,
) -> None:
    """Закриття через rescue SELL LIMIT, якщо він підтверджено filled/closed."""
    exit_price = await resolve_exit_price_after_sell(
        sell_result=escape_order,
        fallback_price=fallback_price,
        entry_price=entry_price,
    )

    entry_price_f = float(entry_price)
    qty_f = float(qty)
    tp_price_f = float(tp_price)
    sl_price_f = float(sl_price)

    trade_stats = save_trade_history(
        order_id=order_id,
        symbol=CCXT_SYMBOL,
        close_reason="CLOSED_FLAT_SAVED",
        entry_price=entry_price_f,
        exit_price=exit_price,
        tp_price=tp_price_f,
        sl_price=sl_price_f,
        qty=qty_f,
        opened_at=int(trade_ts),
    )

    conn = sqlite3.connect(DB_BOT)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE orders
        SET status = 'CLOSED_FLAT_SAVED'
        WHERE order_id = ? AND status = 'SELL_ACTIVE'
        """,
        (order_id,),
    )
    conn.commit()
    conn.close()

    print(
        f"{get_log_time()}📒 TRADE HISTORY SAVED | Reason=CLOSED_FLAT_SAVED | "
        f"PnL={trade_stats['pnl_usdt']:+.4f} USDT ({trade_stats['pnl_pct']:+.2f}%)"
    )

    try:
        from bot_interface import send_direct_notification
        await send_direct_notification(
            f"🎉 *Smart Liquidation виконана Maker SELL LIMIT*\n\n"
            f"● Вхід: `{entry_price_f:.4f}`\n"
            f"● Вихід: `{exit_price:.4f}`\n"
            f"● Кількість: `{qty_f:.2f} {BASE_ASSET}`\n"
            f"● Причина: `CLOSED_FLAT_SAVED`"
        )
    except Exception:
        pass


async def trade_monitor_task() -> None:
    """Фоновий потік супроводу активної позиції."""
    breathing_room_active = False
    flat_timeout_current = FLAT_TIMEOUT_SECONDS

    while True:
        try:
            current_stage = await sync_local_stage()

            if current_stage == STAGE_HOLDING_SELL:
                conn = sqlite3.connect(DB_BOT)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT order_id, price, qty, tp_price, sl_price, timestamp
                    FROM orders
                    WHERE status = 'SELL_ACTIVE'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                )
                active_trade = cursor.fetchone()
                conn.close()

                if not active_trade:
                    await asyncio.sleep(2)
                    continue

                order_id, entry_price, qty, tp_price, sl_price, trade_ts = active_trade
                current_price = await get_current_price_safe()

                if current_price <= 0:
                    await asyncio.sleep(2)
                    continue

                elapsed_time = time.time() - trade_ts

                if int(time.time()) % 300 < 2:
                    time_left = int(flat_timeout_current - elapsed_time)
                    print(
                        f"{get_log_time()}📦 Супровід: Поточна={current_price:.4f} | "
                        f"Вхід={entry_price:.4f} | SL={sl_price:.4f} | TP={tp_price:.4f} | "
                        f"⏳ Флет-таймаут: {max(0, time_left // 60)} хв {max(0, time_left % 60)} сек"
                    )

                # Trailing SL раз на хвилину
                if int(time.time()) % 60 < 2:
                    try:
                        from market_structure_analysis import find_latest_swing_low
                        from config import SL_OFFSET_PERC

                        klines_raw = await fetch_market_klines()
                        latest_low = None

                        if klines_raw and isinstance(klines_raw, list):
                            res_low = find_latest_swing_low(klines_raw, min_candles_right=2)
                            latest_low = res_low if isinstance(res_low, dict) else {"low": float(res_low)}

                        if latest_low:
                            potential_new_sl = float(latest_low["low"] * (1 - SL_OFFSET_PERC))

                            if (
                                round(potential_new_sl, 4) > round(float(sl_price), 4)
                                and potential_new_sl < current_price * 0.995
                            ):
                                conn = sqlite3.connect(DB_BOT)
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE orders SET sl_price = ? WHERE order_id = ?",
                                    (potential_new_sl, order_id),
                                )
                                conn.commit()
                                conn.close()

                                print(
                                    f"{get_log_time()}🔥 ТРЕЙЛІНГ-СТОП: "
                                    f"{float(sl_price):.4f} ➔ {potential_new_sl:.4f}"
                                )

                                try:
                                    from bot_interface import send_direct_notification
                                    await send_direct_notification(
                                        f"🔥 *Nexus Трейлінг-Стоп*\n\n"
                                        f"Захист підтягнуто:\n"
                                        f"`{float(sl_price):.4f}` ➔ `{potential_new_sl:.4f}`"
                                    )
                                except Exception:
                                    pass

                                sl_price = potential_new_sl
                            else:
                                print(
                                    f"{get_log_time()} TRAIL BLOCKED | "
                                    f"Current={current_price:.4f} | "
                                    f"SwingLow={latest_low['low']:.4f} | "
                                    f"CandidateSL={potential_new_sl:.4f}"
                                )
                    except Exception:
                        pass

                if current_price >= float(tp_price):
                    print(
                        f"{get_log_time()}🍏 ТЕЙК-ПРОФІТ ДОСЯГНУТО! "
                        f"Ціна: {current_price:.4f} >= {float(tp_price):.4f}."
                    )

                    closed = await close_active_position(
                        order_id=order_id,
                        entry_price=float(entry_price),
                        qty=float(qty),
                        tp_price=float(tp_price),
                        sl_price=float(sl_price),
                        trade_ts=int(trade_ts),
                        current_price=float(current_price),
                        close_reason="CLOSED_TP",
                        cooldown_seconds=900,
                        emoji="🍏",
                        title="Позицію закрито по Тейк-Профіту!",
                    )

                    if closed:
                        breathing_room_active = False
                        flat_timeout_current = FLAT_TIMEOUT_SECONDS
                        await asyncio.sleep(10)
                    continue

                if current_price <= float(sl_price):
                    print(
                        f"{get_log_time()}🍎 СТОП-ЛОСС СПРАЦЮВАВ! "
                        f"Ціна: {current_price:.4f} <= {float(sl_price):.4f}."
                    )

                    closed = await close_active_position(
                        order_id=order_id,
                        entry_price=float(entry_price),
                        qty=float(qty),
                        tp_price=float(tp_price),
                        sl_price=float(sl_price),
                        trade_ts=int(trade_ts),
                        current_price=float(current_price),
                        close_reason="CLOSED_SL",
                        cooldown_seconds=2700,
                        emoji="🍎",
                        title="Позицію вибило по Стоп-Лоссу!",
                    )

                    if closed:
                        breathing_room_active = False
                        flat_timeout_current = FLAT_TIMEOUT_SECONDS
                        await asyncio.sleep(10)
                    continue

                # Flat manager
                if elapsed_time > flat_timeout_current:
                    if current_price > float(entry_price):
                        new_breakeven_sl = float(entry_price) * 1.0002
                        new_sl = max(float(sl_price), new_breakeven_sl)

                        print(
                            f"{get_log_time()} FLAT DEBUG | "
                            f"CurrentSL={float(sl_price):.4f} | Breakeven={new_breakeven_sl:.4f} | "
                            f"Chosen={new_sl:.4f}"
                        )

                        conn = sqlite3.connect(DB_BOT)
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE orders SET sl_price = ? WHERE order_id = ?",
                            (new_sl, order_id),
                        )
                        conn.commit()
                        conn.close()

                        flat_timeout_current += 120 * 60
                        print(f"{get_log_time()}🍏 [ФЛЕТ: СЦЕНАРІЙ А] ➔ Перенос в Б/У: {new_sl:.4f}")

                        try:
                            from bot_interface import send_direct_notification
                            await send_direct_notification(
                                f"🍏 *Nexus: Захист Б/У активовано*\n"
                                f"● Стоп перенесено: `{new_sl:.4f}`"
                            )
                        except Exception:
                            pass

                        continue

                    if breathing_room_active is False:
                        klines_check = await fetch_market_klines()
                        if klines_check and len(klines_check) >= 2:
                            last_close = float(klines_check[-1][4])
                            prev_close = float(klines_check[-2][4])

                            if last_close > prev_close:
                                flat_timeout_current += 15 * 60
                                breathing_room_active = True

                                print(
                                    f"{get_log_time()}🎰 [ФЛЕТ: СЦЕНАРІЙ Б] ➔ "
                                    f"Свічка росте! Close {prev_close:.4f} ➔ {last_close:.4f}. "
                                    f"Breathing Room +15 хвилин."
                                )

                                try:
                                    from bot_interface import send_direct_notification
                                    await send_direct_notification(
                                        f"🎰 *Nexus: Breathing Room +15 хв*\n\n"
                                        f"● Попередній close: `{prev_close:.4f}`\n"
                                        f"● Поточний close: `{last_close:.4f}`\n"
                                        f"● Тренд живий, таймер подовжено."
                                    )
                                except Exception:
                                    pass

                                continue

                    print(f"{get_log_time()}⏳ [ФЛЕТ: СЦЕНАРІЙ В] ➔ Мертвий ринок. Активація Smart Liquidation...")

                    try:
                        await cancel_all_buy_orders()
                    except Exception:
                        pass

                    escape_price = float(entry_price) * 1.0002
                    escape_order = await execute_order_safe(
                        side="sell",
                        order_type="limit",
                        qty=float(qty),
                        price=escape_price,
                    )

                    if escape_order and "id" in escape_order:
                        print(f"{get_log_time()}🏦 Рятувальний Maker виставлено на: {escape_price:.4f}. Очікування 3 хв...")
                        escape_start_ts = time.time()

                        while time.time() - escape_start_ts < 180:
                            await asyncio.sleep(3)
                            check_escape = await check_order_safe(escape_order["id"])
                            if check_escape and str(check_escape.get("status", "")).lower() == "closed":
                                print(f"{get_log_time()}🎉 ТРІУМФ SMART LIQUIDATION: Рятувальна лімітка виконана!")
                                await mark_escape_limit_filled(
                                    order_id=order_id,
                                    escape_order=check_escape,
                                    entry_price=float(entry_price),
                                    qty=float(qty),
                                    tp_price=float(tp_price),
                                    sl_price=float(sl_price),
                                    trade_ts=int(trade_ts),
                                    fallback_price=escape_price,
                                )
                                breathing_room_active = False
                                flat_timeout_current = FLAT_TIMEOUT_SECONDS
                                break
                        else:
                            print(
                                f"{get_log_time()}⚠️ Рятувальну SELL-лімітку не зачепило. "
                                f"Скасовую саме цей SELL order..."
                            )

                            cancel_ok = await cancel_specific_order_safe(escape_order["id"])
                            check_escape_after_cancel = await check_order_safe(escape_order["id"])
                            escape_status = (
                                str(check_escape_after_cancel.get("status", "")).lower()
                                if check_escape_after_cancel
                                else "unknown"
                            )

                            if escape_status in ["closed", "filled"]:
                                print(
                                    f"{get_log_time()}🎉 SMART LIQUIDATION FILLED DURING CANCEL | "
                                    f"EscapeOrder={escape_order['id']}"
                                )
                                await mark_escape_limit_filled(
                                    order_id=order_id,
                                    escape_order=check_escape_after_cancel,
                                    entry_price=float(entry_price),
                                    qty=float(qty),
                                    tp_price=float(tp_price),
                                    sl_price=float(sl_price),
                                    trade_ts=int(trade_ts),
                                    fallback_price=escape_price,
                                )
                                breathing_room_active = False
                                flat_timeout_current = FLAT_TIMEOUT_SECONDS
                                continue

                            if not cancel_ok or escape_status not in ["canceled", "cancelled"]:
                                print(
                                    f"{get_log_time()}🚨 CRITICAL: ESCAPE SELL LIMIT CANCEL NOT VERIFIED | "
                                    f"EscapeOrder={escape_order['id']} | Status={escape_status} | "
                                    f"Position remains SELL_ACTIVE"
                                )
                                set_setting("bot_status", "STOPPED")

                                try:
                                    from bot_interface import send_direct_notification
                                    await send_direct_notification(
                                        f"🚨 *CRITICAL: FLAT EXIT НЕ ПІДТВЕРДЖЕНО*\n\n"
                                        f"Не вдалося підтвердити скасування рятувального SELL LIMIT.\n\n"
                                        f"● BUY order: `{order_id}`\n"
                                        f"● Escape SELL order: `{escape_order['id']}`\n"
                                        f"● Entry: `{float(entry_price):.4f}`\n"
                                        f"● Qty: `{float(qty):.2f} {BASE_ASSET}`\n"
                                        f"● Escape price: `{escape_price:.4f}`\n"
                                        f"● Escape status: `{escape_status}`\n\n"
                                        f"⚠️ Market SELL НЕ виконано.\n"
                                        f"Позиція НЕ позначена як закрита.\n"
                                        f"Бот переведено в STOPPED.\n\n"
                                        f"Перевір MEXC вручну."
                                    )
                                except Exception:
                                    pass

                                await asyncio.sleep(10)
                                continue

                    print(f"{get_log_time()}🔴 Примусова маркет-ліквідація за таймаутом флету...")
                    closed = await close_active_position(
                        order_id=order_id,
                        entry_price=float(entry_price),
                        qty=float(qty),
                        tp_price=float(tp_price),
                        sl_price=float(sl_price),
                        trade_ts=int(trade_ts),
                        current_price=float(current_price),
                        close_reason="CLOSED_FLAT",
                        cooldown_seconds=0,
                        emoji="⏳",
                        title="Позицію закрито за жорстким таймаутом флету",
                    )

                    if closed:
                        breathing_room_active = False
                        flat_timeout_current = FLAT_TIMEOUT_SECONDS
                    continue

            else:
                breathing_room_active = False
                flat_timeout_current = FLAT_TIMEOUT_SECONDS

        except Exception as e:
            print(f"{get_log_time()}Помилка у фоновому потоці супроводу: {e}")

        await asyncio.sleep(2)


async def market_scanner_task() -> None:
    """Фоновий потік пошуку FVG та контролю BUY LIMIT."""
    await asyncio.to_thread(mexc.load_markets)

    while True:
        try:
            bot_status = get_setting("bot_status", "STOPPED")
            current_stage = await sync_local_stage()

            print(f"{get_log_time()} STATE CHECK | BotStatus={bot_status} | Stage={current_stage}")

            if bot_status == "WAITING_LIMIT" and current_stage == STAGE_IDLE:
                print(
                    f"{get_log_time()}🔄 WAITING_LIMIT → RUNNING | "
                    f"Ордер відсутній, повертаюсь до пошуку."
                )
                set_setting("bot_status", "RUNNING")
                await asyncio.sleep(1)
                continue

            if bot_status == "RUNNING" and current_stage == STAGE_IDLE:
                db_cooldown = get_cooldown_from_db()
                if time.time() < db_cooldown:
                    remaining_sec = max(0, int(db_cooldown - time.time()))
                    remaining_candles = (remaining_sec // 300) + 1
                    rem_mins = remaining_sec // 60
                    rem_secs = remaining_sec % 60
                    cooldown_reason = get_setting("cooldown_reason", "UNKNOWN")

                    print(
                        f"{get_log_time()}🛑 COOLDOWN ACTIVE | "
                        f"Reason={cooldown_reason} | "
                        f"Left={rem_mins} хв {rem_secs} сек | "
                        f"CandlesLeft={remaining_candles} | "
                        f"Stage={current_stage}"
                    )

                    await asyncio.sleep(60)
                    continue

                if db_cooldown > 0 and get_setting("cooldown_reason", ""):
                    print(f"{get_log_time()}✅ COOLDOWN FINISHED | Scanner unlocked")
                    set_setting("cooldown_reason", "")

                print(f"{get_log_time()}🔎 SCANNER ACTIVE | BotStatus={bot_status} | Stage={current_stage}")
                print(f"{get_log_time()}🔎 Сканування ринку на наявність структурних FVG за правилом ТЗ...")

                klines = await fetch_market_klines()
                if not klines:
                    print(f"{get_log_time()}🛑 SETUP SKIPPED | Reason=NO_KLINES")
                    await asyncio.sleep(60)
                    continue

                klines_close = [float(candle[4]) for candle in klines]
                setup_found, entry_p, sl_p, tp_p, comment, order_type, atr_value = calculate_trade_parameters(
                    klines,
                    klines_close,
                )

                if setup_found:
                    if sl_p >= entry_p or tp_p <= entry_p:
                        print(
                            f"{get_log_time()}🛑 SETUP SKIPPED | Reason=BAD_GEOMETRY | "
                            f"Entry={entry_p:.4f} | SL={sl_p:.4f} | TP={tp_p:.4f}"
                        )
                        setup_found = False

                if setup_found:
                    current_price = await get_current_price_safe()

                    if current_price <= 0:
                        print(f"{get_log_time()}🛑 SETUP SKIPPED | Reason=INVALID_CURRENT_PRICE | Price={current_price}")
                        await asyncio.sleep(30)
                        continue

                    # P0: Entry має бути нижче ринку.
                    if entry_p >= current_price:
                        print(
                            f"{get_log_time()}🛑 SETUP SKIPPED | Reason=ENTRY_NOT_BELOW_MARKET | "
                            f"Entry={entry_p:.4f} | Current={current_price:.4f}"
                        )
                        await asyncio.sleep(60)
                        continue

                    entry_discount = (current_price - entry_p) / current_price

                    # P0: Entry має бути не просто нижче, а достатньо нижче ринку.
                    if entry_discount < MIN_ENTRY_DISCOUNT_PERC:
                        print(
                            f"{get_log_time()}🛑 SETUP SKIPPED | Reason=ENTRY_TOO_CLOSE | "
                            f"Entry={entry_p:.4f} | Current={current_price:.4f} | "
                            f"Discount={entry_discount * 100:.2f}% | "
                            f"Min={MIN_ENTRY_DISCOUNT_PERC * 100:.2f}%"
                        )
                        await asyncio.sleep(60)
                        continue

                    if is_blocked_missed_tp_context(entry_p, sl_p):
                        print(
                            f"{get_log_time()}🛑 SETUP SKIPPED | Reason=MISSED_TP_CONTEXT | "
                            f"Entry={entry_p} | SL={sl_p}"
                        )
                        await asyncio.sleep(60)
                        continue

                    max_allocation = float(get_setting("max_vol_usdt", str(MAX_VOL_USDT)))
                    trade_allocation_usdt = max_allocation

                    try:
                        print(f"{get_log_time()}🔍 Рентген стакану: перевірка захисних стін покупців у межах 1%...")
                        target_wall_qty = calculate_target_wall(klines)
                        orderbook = await asyncio.to_thread(mexc.fetch_order_book, CCXT_SYMBOL, 200)
                        bids = orderbook.get("bids", [])

                        distance_to_entry_pct = abs(current_price - entry_p) / current_price
                        depth_buffer_pct = max(0.01, distance_to_entry_pct + 0.005)
                        lower_bound = entry_p * (1 - depth_buffer_pct)
                        upper_bound = current_price

                        cumulative_bid_volume = sum(
                            float(bid_q)
                            for bid_p, bid_q in bids
                            if lower_bound <= float(bid_p) <= upper_bound
                        )

                        print(
                            f"{get_log_time()}📊 [ORDERBOOK METRICS] Limit=200 | "
                            f"Zone={lower_bound:.4f}-{upper_bound:.4f} | "
                            f"Entry={entry_p:.4f} | Current={current_price:.4f} | "
                            f"DistanceToEntry={distance_to_entry_pct * 100:.2f}% | "
                            f"TargetWall={target_wall_qty:.1f} | BidVolume={cumulative_bid_volume:.1f}"
                        )

                        if cumulative_bid_volume < target_wall_qty:
                            trade_allocation_usdt = max_allocation * 0.5
                            print(
                                f"{get_log_time()}⚠️ СЛАБКА ЛІКВІДНІСТЬ СТАКАНУ: "
                                f"BidVolume={cumulative_bid_volume:.1f} < TargetWall={target_wall_qty:.1f}. "
                                f"Ризик занижено до {trade_allocation_usdt:.1f} USDT!"
                            )
                        else:
                            print(
                                f"{get_log_time()}🛡️ СТАКАН СХВАЛЕНО: "
                                f"BidVolume={cumulative_bid_volume:.1f} >= TargetWall={target_wall_qty:.1f}. "
                                f"Вхід на лот {trade_allocation_usdt:.1f} USDT."
                            )

                    except Exception as eb:
                        print(f"{get_log_time()}❌ Збій шлюзу книги ордерів: {eb}. Ризик знижено до 50%.")
                        trade_allocation_usdt = max_allocation * 0.5

                    qty = await calculate_position_size(entry_p, sl_p)
                    if trade_allocation_usdt == (max_allocation * 0.5) and qty:
                        qty = float(mexc.amount_to_precision(CCXT_SYMBOL, qty * 0.5))

                    if not qty:
                        print(f"{get_log_time()}🛑 BUY SKIPPED | Reason=POSITION_SIZE_INVALID")
                        await asyncio.sleep(60)
                        continue

                    buy_blocked = await exchange_position_guard_before_buy()
                    if buy_blocked:
                        print(f"{get_log_time()}🛑 BUY SKIPPED | Reason=EXCHANGE_POSITION_GUARD")
                        await asyncio.sleep(60)
                        continue

                    bot_status_now = get_setting("bot_status", "STOPPED")
                    if bot_status_now != "RUNNING":
                        print(
                            f"{get_log_time()}🛑 BUY SKIPPED | Reason=BOT_STATUS_CHANGED | "
                            f"BotStatus={bot_status_now}"
                        )
                        await asyncio.sleep(2)
                        continue

                    order = await execute_order_safe(
                        side="buy",
                        order_type=order_type,
                        qty=qty,
                        price=entry_p,
                    )

                    if order and "id" in order:
                        conn = sqlite3.connect(DB_BOT)
                        cursor = conn.cursor()

                        tp_p = max(tp_p, float(order.get("price", entry_p)) * 1.005)

                        cursor.execute(
                            """
                            INSERT INTO orders (
                                order_id, symbol, side, price, qty, status,
                                timestamp, tp_price, sl_price
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                order["id"],
                                CCXT_SYMBOL,
                                "BUY",
                                entry_p,
                                qty,
                                "BUY_PENDING",
                                int(time.time()),
                                tp_p,
                                sl_p,
                            ),
                        )

                        risk_calc = entry_p - sl_p
                        reward_calc = tp_p - entry_p
                        rr_actual = reward_calc / risk_calc if risk_calc > 0 else 0.0

                        if order_type == "limit":
                            cursor.execute(
                                "INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', 'WAITING_LIMIT')"
                            )
                            print(
                                f"{get_log_time()}📥 [ЛІМІТНИЙ ОРДЕР ВИСТАВЛЕНО] BUY LIMIT ➔ "
                                f"Ціна: {entry_p:.4f} | Лот: {float(qty):.2f} {BASE_ASSET} "
                                f"({trade_allocation_usdt:.1f}$) | SL: {sl_p:.4f} | TP: {tp_p:.4f}"
                            )
                        else:
                            print(
                                f"{get_log_time()}🟢 [МАРКЕТ-ВХІД ВИКОНАНО] MARKET BUY ➔ "
                                f"Ціна: {entry_p:.4f} | Лот: {float(qty):.2f} {BASE_ASSET} "
                                f"({trade_allocation_usdt:.1f}$) | SL: {sl_p:.4f} | TP: {tp_p:.4f}"
                            )

                        conn.commit()
                        conn.close()

                        from bot_interface import send_direct_notification
                        await send_direct_notification(
                            f"📥 *Виставлено новий ордер за сигналом FVG!*\n\n"
                            f"● Тип виконання: `{order_type.upper()}`\n"
                            f"● Вхід: `{entry_p:.4f}`\n"
                            f"● Лот: `{qty} {BASE_ASSET}` (Ціль: {trade_allocation_usdt:.1f} USDT)\n"
                            f"● Стоп-Лосс: `{sl_p:.4f}`\n"
                            f"● Тейк-Профіт: `{tp_p:.4f}`\n"
                            f"● Математичний R:R: `1:{rr_actual:.2f}`"
                        )

                        # P0: fast path — не спимо 60 сек після BUY LIMIT.
                        if order_type == "limit":
                            bot_status = "WAITING_LIMIT"
                            print(
                                f"{get_log_time()}⚡ WATCHDOG FAST PATH | "
                                f"BotStatus=WAITING_LIMIT | Entering 2s loop"
                            )
                            await asyncio.sleep(2)
                            continue

                else:
                    try:
                        live_price = await get_current_price_safe()
                        real_atr = atr_value
                    except Exception:
                        live_price = 0.0
                        real_atr = 0.0015

                    print(
                        f"{get_log_time()}🔎 NEXUS РАДАР | "
                        f"Price={live_price:.4f} | ATR={real_atr:.4f} | {comment}"
                    )

                    try:
                        with open("terminal.txt", "a", encoding="utf-8") as log_file:
                            clean_comment = (
                                comment
                                .replace("\033[94m", "")
                                .replace("\033[91m", "")
                                .replace("\033[92m", "")
                                .replace("\033[0m", "")
                            )
                            log_file.write(
                                f"[{datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}] {clean_comment}\n"
                            )
                    except Exception:
                        pass

            elif bot_status in ["RUNNING", "WAITING_LIMIT"] and current_stage == STAGE_WAITING_BUY:
                print(f"{get_log_time()} WATCHDOG | BotStatus={bot_status} | Stage={current_stage}")

                conn = sqlite3.connect(DB_BOT)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT order_id, price, tp_price, sl_price, timestamp
                    FROM orders
                    WHERE status = 'BUY_PENDING'
                    ORDER BY id DESC
                    LIMIT 1
                    """
                )
                pending_order = cursor.fetchone()
                conn.close()

                if pending_order:
                    ord_id, entry_p, tp_p, sl_p, order_ts = pending_order
                    current_price = await get_current_price_safe()

                    if current_price > 0:
                        if (time.time() - order_ts) > ORDER_LIFETIME_SECONDS:
                            timeout_minutes = ORDER_LIFETIME_SECONDS // 60
                            print(
                                f"{get_log_time()}⏳ ІНВАЛІДАЦІЯ ТАЙМАУТУ: "
                                f"Лімітка висить >{timeout_minutes} хв без зацепу. Скасування..."
                            )
                            await cancel_all_buy_orders()
                            await notify_buy_limit_cancelled(
                                reason=f"TIMEOUT_INVALID / Лімітка висіла >{timeout_minutes} хв без виконання",
                                order_id=ord_id,
                                entry_price=entry_p,
                                sl_price=sl_p,
                                tp_price=tp_p,
                                current_price=current_price,
                            )

                            conn = sqlite3.connect(DB_BOT)
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE orders
                                SET status = 'TIMEOUT_INVALID'
                                WHERE order_id = ? AND status = 'BUY_PENDING'
                                """,
                                (ord_id,),
                            )
                            conn.commit()
                            conn.close()

                            set_setting("bot_status", "RUNNING")
                            print(f"{get_log_time()} BOT STATUS CHANGED -> RUNNING")
                            continue

                        if current_price >= float(tp_p):
                            print(
                                f"{get_log_time()}🏁 END СЕТАП: Ринок виконав ціль TP без нас. "
                                f"Current={current_price:.4f} >= TP={float(tp_p):.4f}. Скасування BUY LIMIT..."
                            )
                            await cancel_all_buy_orders()
                            remember_missed_tp_context(ord_id, entry_p, sl_p, tp_p)
                            await notify_buy_limit_cancelled(
                                reason="MISSED_TP / Ціна дійшла до TP без входу",
                                order_id=ord_id,
                                entry_price=entry_p,
                                sl_price=sl_p,
                                tp_price=tp_p,
                                current_price=current_price,
                            )

                            conn = sqlite3.connect(DB_BOT)
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE orders
                                SET status = 'MISSED_TP'
                                WHERE order_id = ? AND status = 'BUY_PENDING'
                                """,
                                (ord_id,),
                            )
                            conn.commit()
                            conn.close()

                            set_setting("bot_status", "RUNNING")
                            print(f"{get_log_time()} BOT STATUS CHANGED -> RUNNING")
                            continue

                        if current_price <= float(sl_p):
                            print(
                                f"{get_log_time()}⚠️ ІНВАЛІДАЦІЯ SL: "
                                f"Current={current_price:.4f} <= SL={float(sl_p):.4f}. Скасування BUY LIMIT..."
                            )
                            await cancel_all_buy_orders()
                            await notify_buy_limit_cancelled(
                                reason="INVALID_SL / Ціна пробила SL до входу",
                                order_id=ord_id,
                                entry_price=entry_p,
                                sl_price=sl_p,
                                tp_price=tp_p,
                                current_price=current_price,
                            )

                            conn = sqlite3.connect(DB_BOT)
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE orders
                                SET status = 'INVALID_SL'
                                WHERE order_id = ? AND status = 'BUY_PENDING'
                                """,
                                (ord_id,),
                            )
                            conn.commit()
                            conn.close()

                            set_setting("bot_status", "RUNNING")
                            print(f"{get_log_time()} BOT STATUS CHANGED -> RUNNING")
                            continue

                        fvg_allowed_depth = float(entry_p) - (abs(float(entry_p) - float(sl_p)) * 0.85)
                        if current_price <= fvg_allowed_depth:
                            print(
                                f"{get_log_time()}⚠️ ІНВАЛІДАЦІЯ FVG: "
                                f"Current={current_price:.4f} <= Depth={fvg_allowed_depth:.4f}. Скасування BUY LIMIT..."
                            )
                            await cancel_all_buy_orders()
                            await notify_buy_limit_cancelled(
                                reason="INVALID_FVG_BREAK / Ціна пробила допустиму глибину FVG",
                                order_id=ord_id,
                                entry_price=entry_p,
                                sl_price=sl_p,
                                tp_price=tp_p,
                                current_price=current_price,
                            )

                            conn = sqlite3.connect(DB_BOT)
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                UPDATE orders
                                SET status = 'INVALID_FVG_BREAK'
                                WHERE order_id = ? AND status = 'BUY_PENDING'
                                """,
                                (ord_id,),
                            )
                            conn.commit()
                            conn.close()

                            set_setting("bot_status", "RUNNING")
                            print(f"{get_log_time()} BOT STATUS CHANGED -> RUNNING")
                            continue

                        if int(time.time()) % 60 < 3:
                            klines = await fetch_market_klines()
                            from market_structure_analysis import find_latest_swing_low
                            from config import SL_OFFSET_PERC

                            latest_market_low = find_latest_swing_low(klines, min_candles_right=2)
                            if latest_market_low:
                                potential_floor = float(latest_market_low["low"] * (1 - SL_OFFSET_PERC))

                                if potential_floor > float(sl_p):
                                    print(
                                        f"{get_log_time()}🔄 ІНВАЛІДАЦІЯ СТРУКТУРИ: Нове вище дно. "
                                        f"OldSL={float(sl_p):.4f} | NewFloor={potential_floor:.4f}. "
                                        f"Авто-скасування BUY LIMIT..."
                                    )
                                    await cancel_all_buy_orders()
                                    await notify_buy_limit_cancelled(
                                        reason="SUPERSEDED / Зʼявилось нове вище дно",
                                        order_id=ord_id,
                                        entry_price=entry_p,
                                        sl_price=sl_p,
                                        tp_price=tp_p,
                                        current_price=current_price,
                                    )

                                    conn = sqlite3.connect(DB_BOT)
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        """
                                        UPDATE orders
                                        SET status = 'SUPERSEDED'
                                        WHERE order_id = ? AND status = 'BUY_PENDING'
                                        """,
                                        (ord_id,),
                                    )
                                    conn.commit()
                                    conn.close()

                                    set_setting("bot_status", "RUNNING")
                                    print(f"{get_log_time()} BOT STATUS CHANGED -> RUNNING")
                                    continue

        except Exception as e:
            print(f"{get_log_time()}Помилка у циклі захисту ліміток: {e}")

        print(f"{get_log_time()} SLEEP BLOCK | BotStatus={bot_status}")

        try:
            if bot_status == "RUNNING":
                print(f"{get_log_time()} SLEEP 60 SEC")
                await asyncio.sleep(60)
            elif bot_status == "WAITING_LIMIT":
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(60)
        except Exception as e:
            print(f"{get_log_time()}Критичний збій таймера Скринера ринку: {e}")


async def main() -> None:
    """Головна точка входу архітектури Nexus Core."""
    import os
    os.system("color")

    print("===================================================")
    print("      NEXUS VECTOR ASYNC RISK CORE ACTIVE v2.1    ")
    print("===================================================")

    init_db()
    set_setting("bot_status", "STOPPED")

    if bot:
        tg_thread = threading.Thread(
            target=bot.infinity_polling,
            kwargs={"timeout": 20},
            daemon=True,
        )
        tg_thread.start()
        print(f"{get_log_time()}📡 Шлюз Telegram API успішно винесено в ізольований фоновий потік.")

        try:
            from bot_interface import send_welcome
            from telebot.types import Message, Chat, User

            chat_id = get_setting("telegram_chat_id", "").strip()
            if chat_id and "ВСТАВТЕ" not in chat_id:
                fake_chat = Chat(id=int(chat_id), type="private")
                fake_user = User(id=int(chat_id), is_bot=False, first_name="Admin")
                fake_message = Message(
                    message_id=0,
                    from_user=fake_user,
                    date=int(time.time()),
                    chat=fake_chat,
                    content_type="text",
                    options={},
                    json_string="",
                )
                send_welcome(fake_message)
                print(f"{get_log_time()}📱 Телеграм пульт запущено")
        except Exception as e:
            print(f"{get_log_time()}⚠️ Помилка авто-відправки пульта: {e}")
    else:
        print(f"{get_log_time()}⚠️ Telegram bot не активний: перевір token/chat_id у settings.")

    await asyncio.gather(
        market_scanner_task(),
        trade_monitor_task(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print(f"{get_log_time()}💤 Систему безпечно вимкнено користувачем.")
