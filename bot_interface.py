# bot_interface.py
import logging
import sqlite3
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, Message
from config import DB_TRADES, DB_BOT
from database import get_setting, set_setting

TOKEN: str = get_setting('telegram_token', '').strip()
bot = telebot.TeleBot(TOKEN) if TOKEN and "ВСТАВТЕ" not in TOKEN else None


# TELEGRAM_ACCESS_GUARD_ACTIVE
# P0 Security: every inbound Telegram command must be restricted to the configured admin chat_id.
def _get_allowed_telegram_chat_id() -> str:
    """Returns the configured admin Telegram chat id, or empty string if not safely configured."""
    allowed_chat_id = get_setting("telegram_chat_id", "").strip()

    if not allowed_chat_id or "ВСТАВТЕ" in allowed_chat_id:
        logging.critical(
            "🚨 Telegram access guard is not configured: "
            "telegram_chat_id is empty or placeholder. Commands are blocked fail-safe."
        )
        return ""

    return allowed_chat_id


def is_authorized(message: Message) -> bool:
    """
    Allows Telegram control only from the configured admin chat id.

    Fail-closed behavior:
    - if telegram_chat_id is empty / placeholder: False;
    - if message/chat is malformed: False;
    - only exact string match is accepted.
    """
    allowed_chat_id = _get_allowed_telegram_chat_id()
    if not allowed_chat_id:
        return False

    try:
        incoming_chat_id = str(message.chat.id).strip()
    except Exception:
        logging.warning("🚫 Unauthorized Telegram access blocked | malformed message/chat")
        return False

    return incoming_chat_id == str(allowed_chat_id)


def reject_unauthorized(message: Message) -> None:
    """Logs unauthorized Telegram access without sending keyboard, status, balances, or commands."""
    try:
        from_user = getattr(message, "from_user", None)
        username = getattr(from_user, "username", None)
        user_id = getattr(from_user, "id", None)
        chat_id = getattr(getattr(message, "chat", None), "id", None)
        chat_type = getattr(getattr(message, "chat", None), "type", None)
        text = getattr(message, "text", None)

        logging.warning(
            "🚫 Unauthorized Telegram access blocked | "
            f"chat_id={chat_id} | chat_type={chat_type} | "
            f"user_id={user_id} | username={username} | text={text}"
        )
    except Exception:
        logging.warning("🚫 Unauthorized Telegram access blocked")


async def send_direct_notification(markdown_text: str) -> None:
    """Функція для миттєвої відправки повідомлень торговим ядром."""
    chat_id = get_setting('telegram_chat_id', '').strip()
    if bot and chat_id and "ВСТАВТЕ" not in chat_id:
        try:
            bot.send_message(chat_id, markdown_text, parse_mode="Markdown", reply_markup=generate_persistent_keyboard())
        except Exception as e:
            logging.error(f"Помилка надсилання сповіщення у Telegram: {e}")

def generate_persistent_keyboard() -> ReplyKeyboardMarkup:
    """Генерація постійного нижнього пульта керування (Нерухома клавіатура)."""
    status = get_setting('bot_status', 'STOPPED')
    btn_toggle = (
        "🔴 ЗУПИНИТИ БОТА"
        if status in ["RUNNING", "WAITING_LIMIT", "STOPPING"]
        else "🚀 ЗАПУСТИТИ БОТА"
    )

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton(btn_toggle))
    keyboard.add(KeyboardButton("📊 СТАТУС"), KeyboardButton("📈 СТАТИСТИКА"))
    return keyboard

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message: Message) -> None:
    """Initializes and sends the Telegram control panel with formatted status metrics."""
    if not is_authorized(message):
        reject_unauthorized(message)
        return

    status = get_setting('bot_status', 'STOPPED')
    risk = get_setting('risk_usdt', '0.5')

    # 🎨 СИНІЙ ІНСТИТУЦІЙНИЙ РОЗКРАС: Загортаємо статус та ризик у косі лапки `
    text = (
        f"🤖 *Квантове Ядро Nexus Core v2.0 успішно активовано!*\n\n"
        f"• Статус системи: `{status}`\n"
        f"• Поточний ризик на угоду: `{risk} USDT`\n\n"
        f"Панель моніторингу готова до ручного керування:"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=generate_persistent_keyboard())


def _format_order_id_list(items, limit: int = 5) -> str:
    """Формує короткий список order_id для Telegram Markdown."""
    ids = []
    for item in items or []:
        if isinstance(item, dict):
            order_id = str(item.get("id", "")).strip()
        else:
            order_id = str(item).strip()

        if order_id:
            ids.append(order_id)

    if not ids:
        return "`—`"

    visible = ids[:limit]
    suffix = "" if len(ids) <= limit else f" +{len(ids) - limit} ще"
    return ", ".join(f"`{order_id}`" for order_id in visible) + suffix


def format_stop_cancel_summary(cancel_summary) -> str:
    """Пояснює у Telegram, що саме сталося з BUY LIMIT після ручного STOP."""
    if not isinstance(cancel_summary, dict):
        return "\n\n🧹 STOP-захист: запит на скасування BUY LIMIT виконано."

    attempted = int(cancel_summary.get("attempted", 0) or 0)
    cancelled = cancel_summary.get("cancelled", []) or []
    filled = cancel_summary.get("filled_during_stop", []) or []
    failed = cancel_summary.get("failed", []) or []
    remaining = cancel_summary.get("remaining", []) or []
    error = str(cancel_summary.get("error", "") or "").strip()

    if attempted == 0 and not error:
        return "\n\n🧹 STOP-захист: відкритих BUY LIMIT для скасування не було."

    if filled:
        return (
            "\n\n⚠️ *STOP-захист: BUY LIMIT міг виконатися під час STOP!*\n"
            f"● Перевірено BUY: `{attempted}`\n"
            f"● Виконались під час STOP: `{len(filled)}`\n"
            f"● Ордери: {_format_order_id_list(filled)}\n\n"
            "Натисни `📊 СТАТУС` і перевір позицію на MEXC."
        )

    if failed or remaining or error:
        return (
            "\n\n🚨 *STOP-захист: скасування BUY LIMIT не повністю підтверджено!*\n"
            f"● Перевірено BUY: `{attempted}`\n"
            f"● Скасовано: `{len(cancelled)}`\n"
            f"● Не підтверджено: `{len(failed)}`\n"
            f"● Залишилось у стакані: `{len(remaining)}`\n"
            f"● Скасовані: {_format_order_id_list(cancelled)}\n"
            f"● Залишились: {_format_order_id_list(remaining)}\n"
            + (f"\n● Error: `{error}`" if error else "")
            + "\n\nПеревір MEXC вручну."
        )

    return (
        "\n\n🧹 *STOP-захист: BUY LIMIT ордери скасовано.*\n"
        f"● Перевірено BUY: `{attempted}`\n"
        f"● Скасовано: `{len(cancelled)}`\n"
        f"● Ордери: {_format_order_id_list(cancelled)}"
    )

@bot.message_handler(func=lambda msg: msg.text in ["🚀 ЗАПУСТИТИ БОТА", "🔴 ЗУПИНИТИ БОТА"])
def handle_toggle_bot(message: Message) -> None:
    """Обробник ручного перемикання станів Ядра із ЗАЛІЗОБЕТОННИМ захистом від розсинхрону."""
    if not is_authorized(message):
        reject_unauthorized(message)
        return

    current_status = get_setting("bot_status", "STOPPED")

    if "ЗУПИНИТИ" in message.text and current_status in ["STOPPING", "STOPPED"]:
        bot.send_message(
            message.chat.id,
            (
                f"ℹ️ STOP уже обробляється або бот уже зупинений.\n\n"
                f"● Поточний статус: `{current_status}`"
            ),
            parse_mode="Markdown",
            reply_markup=generate_persistent_keyboard()
        )
        return

    # Пряма логіка на основі тексту кнопки
    if "ЗАПУСТИТИ" in message.text:
        new_status = "RUNNING"
    else:
        new_status = "STOPPING"

    set_setting('bot_status', new_status)
    logging.info(f"🔄 Користувач вручну змінив статус бота на: {new_status}")

    stop_cancel_summary = None

    if new_status == "STOPPING":
        try:
            from main import cancel_all_buy_orders
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            stop_cancel_summary = loop.run_until_complete(cancel_all_buy_orders())
            loop.close()

        except Exception as e:
            logging.error(f"Помилка примусового скасування ордерів: {e}")
            stop_cancel_summary = {
                "attempted": 0,
                "cancelled": [],
                "filled_during_stop": [],
                "failed": [],
                "remaining": [],
                "error": str(e),
            }

    final_status = new_status

    if new_status == "STOPPING":
        set_setting("bot_status", "STOPPED")
        final_status = "STOPPED"

    text = f"📢 Систему переведено в режим: *{final_status}*"

    if new_status == "STOPPING":
        text += format_stop_cancel_summary(stop_cancel_summary)

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=generate_persistent_keyboard()
    )

@bot.message_handler(commands=['clear'])
def handle_clear_command(message: Message) -> None:
    """Ручна сервісна команда для очищення застряглих хвостів ордерів через чат."""
    if not is_authorized(message):
        reject_unauthorized(message)
        return

    try:
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders")
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🧹 *Локальний контекст ордерів успішно очищено через сервісний шлюз.*", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Помилка очищення бази: {e}")


@bot.message_handler(func=lambda msg: msg.text == "📊 СТАТУС")
def handle_status(message: Message) -> None:
    if not is_authorized(message):
        reject_unauthorized(message)
        return

    bot.send_chat_action(message.chat.id, 'typing')
    current_status = get_setting('bot_status', 'STOPPED')

    # 1. Запит ЖИВИХ і точних даних з біржі в момент натискання кнопки
    from mexc_client import (
        sync_get_spot_balance_details,
        sync_get_ticker_price,
        get_sync_exchange
    )
    from config import CCXT_SYMBOL, BASE_ASSET

    usdt_snapshot = sync_get_spot_balance_details("USDT")
    base_snapshot = sync_get_spot_balance_details(BASE_ASSET)

    usdt_bal = float(usdt_snapshot.get("free", 0.0))

    base_free = float(base_snapshot.get("free", 0.0))
    base_used = float(base_snapshot.get("used", 0.0))
    base_total = float(base_snapshot.get("total", 0.0))

    cur_price = sync_get_ticker_price()

    open_buy_orders = 0
    open_sell_orders = 0

    try:
        exchange = get_sync_exchange()
        open_orders = exchange.fetch_open_orders(CCXT_SYMBOL)

        open_buy_orders = sum(
            1 for order in open_orders
            if str(order.get("side", "")).lower() == "buy"
        )

        open_sell_orders = sum(
            1 for order in open_orders
            if str(order.get("side", "")).lower() == "sell"
        )

    except Exception as e:
        logging.error(f"Помилка зчитування open orders для STATUS: {e}")

    # Оновлюємо кеш в базі, щоб дані були актуальними всюди
    if cur_price > 0:
        set_setting("cached_usdt", str(usdt_bal))
        set_setting("cached_base", str(base_free))
        set_setting("cached_base_used", str(base_used))
        set_setting("cached_base_total", str(base_total))
        set_setting("cached_price", str(cur_price))
    else:
        # Якщо біржа на мікросекунду залагала,
        # беремо останні відомі дані з кешу.
        try:
            usdt_bal = float(get_setting("cached_usdt", "0.0"))

            base_free = float(
                get_setting(
                    "cached_base",
                    get_setting("cached_xrp", "0.0")
                )
            )

            base_used = float(
                get_setting(
                    "cached_base_used",
                    get_setting("cached_xrp_used", "0.0")
                )
            )

            base_total = float(
                get_setting(
                    "cached_base_total",
                    get_setting(
                        "cached_xrp_total",
                        str(base_free + base_used)
                    )
                )
            )

            cur_price = float(get_setting("cached_price", "0.0"))

        except ValueError:
            usdt_bal = 0.0
            base_free = 0.0
            base_used = 0.0
            base_total = 0.0
            cur_price = 0.0

    # 2. Зчитування активного ордера з бази даних WAL
    conn = sqlite3.connect(DB_BOT)
    cursor = conn.cursor()
    cursor.execute("SELECT status, price, tp_price, sl_price, qty FROM orders ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    order_info = "❌ Активні ордери у стакані відсутні"
    if row:
        status, price, tp, sl, qty = row
        if status in ['BUY_PENDING', 'SELL_ACTIVE']:
            # Вираховуємо реальний R:R для картки статусу
            risk_c = price - sl
            reward_c = tp - price
            rr_stat = reward_c / risk_c if risk_c > 0 else 0.0

            pnl_info = ""
            # ПУНКТ 7.2 ТЗ: Якщо позиція активна, прораховуємо ЖИВИЙ Плаваючий PnL (Floating PnL)
            if status == 'SELL_ACTIVE' and cur_price > 0:
                floating_pnl_usdt = (cur_price - price) * qty
                floating_pnl_perc = ((cur_price - price) / price) * 100
                pnl_marker = "🍏" if floating_pnl_usdt >= 0 else "🍎"
                pnl_info = (
                    f"● Поточний PnL позиції: {pnl_marker} `{floating_pnl_usdt:+.4f} USDT` (`{floating_pnl_perc:+.2f}%`)\n"
                    if floating_pnl_usdt >= 0 else
                    f"● Поточний PnL позиції: {pnl_marker} `{floating_pnl_usdt:.4f} USDT` (`{floating_pnl_perc:.2f}%`)\n"
                )

            order_info = (
                f"🟢 *АКТИВНИЙ LONG СЕТАП:*\n"
                f"● Стан: `{status}`\n"
                f"● Вхід Maker: `{price:.4f}`\n"
                f"● Кількість: `{qty} {BASE_ASSET}`\n"
                f"● Тейк-Профіт (TP): `{tp:.4f}`\n"
                f"● Стоп-Лосс (SL): `{sl:.4f}`\n"
                f"● Співвідношення R:R: `1:{rr_stat:.2f}`\n"
                f"{pnl_info}"
            )

    # 3. Формування красивої та чесної інформаційної картки
    text = (
        f"📊 *ПОТОЧНИЙ МОНІТОРИНГ EXCH*\n\n"
        f"● Режим роботи Ядра: `{current_status}`\n"
        f"● Ціна {CCXT_SYMBOL}: `{cur_price:.4f} USDT`\n\n"
        f"💰 *Живий баланс споту MEXC:*\n"
        f"● Доступно: `{usdt_bal:.2f} USDT`\n"
        f"● {BASE_ASSET} free: `{base_free:.2f}`\n"
        f"● {BASE_ASSET} used/locked: `{base_used:.2f}`\n"
        f"● {BASE_ASSET} total: `{base_total:.2f}` "
        f"(вартість: `{base_total * cur_price:.2f} USDT`)\n\n"
        f"📦 *Open orders на MEXC:*\n"
        f"● BUY orders: `{open_buy_orders}`\n"
        f"● SELL orders: `{open_sell_orders}`\n\n"
        f"{order_info}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=generate_persistent_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "📈 СТАТИСТИКА")
def handle_stats(message: Message) -> None:
    """Миттєве зчитування фінансової статистики."""
    if not is_authorized(message):
        reject_unauthorized(message)
        return

    try:
        conn = sqlite3.connect(DB_TRADES)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*),
                COALESCE(SUM(pnl_usdt), 0),
                COALESCE(AVG(pnl_pct), 0),
                COALESCE(SUM(position_usdt), 0)
            FROM trade_history
        """)

        row = cursor.fetchone()
        conn.close()

        trade_count = int(row[0] or 0)
        net_profit = float(row[1] or 0.0)
        avg_pnl_pct = float(row[2] or 0.0)
        total_volume = float(row[3] or 0.0)

    except Exception:
        trade_count = 0
        net_profit = 0.0
        avg_pnl_pct = 0.0
        total_volume = 0.0

    indicator = "🍏" if net_profit >= 0 else "🍎"
    text = (
        f"📈 *СТАТИСТИКА ЗАКРИТИХ УГОД*\n\n"
        f"● Кількість угод: `{trade_count}`\n"
        f"● Реалізований PnL: `{net_profit:+.4f} USDT` {indicator}\n"
        f"● Середній результат: `{avg_pnl_pct:+.2f}%`\n"
        f"● Сумарний обсяг: `{total_volume:.2f} USDT`\n\n"
        f"● База: `trade_history / WAL Mode`\n\n"
        f"_Враховуються лише повністю закриті цикли угод._"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=generate_persistent_keyboard())

