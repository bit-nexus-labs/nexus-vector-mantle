# database.py
import sqlite3
import logging
from config import DB_BOT, DB_TRADES

def init_trades_db() -> None:
    """Ініціалізація окремої бази історії завершених угод."""
    try:
        conn = sqlite3.connect(DB_TRADES)
        cursor = conn.cursor()

        cursor.execute("PRAGMA journal_mode=WAL;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                close_reason TEXT NOT NULL,

                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                tp_price REAL,
                sl_price REAL,
                qty REAL NOT NULL,
                position_usdt REAL NOT NULL,

                pnl_usdt REAL NOT NULL,
                pnl_pct REAL NOT NULL,

                opened_at INTEGER,
                closed_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        conn.commit()
        conn.close()

        logging.info("📒 Trade history database verified: trades_data.db")

    except Exception as e:
        logging.error(f"Failed to initialize trades_data.db: {e}")

def init_db() -> None:
    """Ініціалізація та верифікація інфраструктури WAL-бази даних бота."""
    try:
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()

        # Вмикаємо режим паралельного доступу WAL для захисту від блокувань потоків Windows
        cursor.execute("PRAGMA journal_mode=WAL;")

        # 1. Створення таблиці системних налаштувань
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # 2. Створення таблиці обліку ордерів та стейджів супроводу
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                qty REAL NOT NULL,
                status TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                tp_price REAL,
                sl_price REAL
            )
        ''')

        # --- РЕЄСТРАЦІЯ БАЗОВИХ ПАРАМЕТРІВ (INSERT OR IGNORE) ---
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_status', 'STOPPED')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('risk_usdt', '0.5')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('telegram_chat_id', 'ВСТАВТЕ_ВАШ_CHAT_ID')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('telegram_token', 'ВСТАВТЕ_ВАШ_ТОКЕН_БОТА')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mexc_api_key', 'ВСТАВТЕ_ВАШ_MEXC_API_KEY')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mexc_secret_key', 'ВСТАВТЕ_ВАШ_MEXC_SECRET_KEY')")

        # КЕШОВАНІ ДАНІ ДЛЯ МИТТЄВОЇ КНОПКИ СТАТУСУ
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cached_usdt', '0.0')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cached_xrp', '0.0')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cached_price', '0.0')")

        # Існуючий параметр R:R (залишається без змін)
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('min_rr_ratio', '1.2')")

        # НОВІ ПАРАМЕТРИ КУЛДАУНУ У СВІЧКАХ (Пункт 5 ТЗ)
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cooldown_tp_candles', '3')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('cooldown_sl_candles', '9')")

        conn.commit()
        conn.close()

        init_trades_db()

        logging.info("💾 Інфраструктура бази даних WAL успішно верифікована та готова.")
    except Exception as e:
        logging.critical(f"🚨 Критична помилка ініціалізації бази даних: {e}")

def get_setting(key: str, default: str = "") -> str:
    """Безпечне потокове зчитування значення з таблиці settings."""
    try:
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception as e:
        logging.error(f"Помилка зчитування параметра {key}: {e}")
        return default

def set_setting(key: str, value: str) -> None:
    """Безпечний атомарний запис або оновлення параметра в таблиці settings."""
    try:
        conn = sqlite3.connect(DB_BOT)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Помилка запису параметра {key}={value}: {e}")

def write_trade_journal(message: str) -> None:
    """Writes a closed trade record to trades.log."""
    try:
        import datetime
        from pathlib import Path

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_path = log_dir / "trades.log"

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} | "
                f"{message}\n"
            )

    except Exception as e:
        logging.error(f"Failed to write trades.log: {e}")


def save_trade_history(
    order_id: str,
    symbol: str,
    close_reason: str,
    entry_price: float,
    exit_price: float,
    tp_price: float,
    sl_price: float,
    qty: float,
    opened_at: int = None
) -> dict:
    """
    Stores a completed trade cycle in trades_data.db.
    INSERT OR IGNORE prevents duplicate close records for the same order_id.
    """
    try:
        import time

        entry_price = float(entry_price)
        exit_price = float(exit_price)
        tp_price = float(tp_price)
        sl_price = float(sl_price)
        qty = float(qty)

        position_usdt = entry_price * qty
        pnl_usdt = (exit_price - entry_price) * qty
        pnl_pct = (
            ((exit_price - entry_price) / entry_price) * 100
            if entry_price > 0
            else 0.0
        )

        now_ts = int(time.time())

        conn = sqlite3.connect(DB_TRADES)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR IGNORE INTO trade_history (
                order_id,
                symbol,
                close_reason,
                entry_price,
                exit_price,
                tp_price,
                sl_price,
                qty,
                position_usdt,
                pnl_usdt,
                pnl_pct,
                opened_at,
                closed_at,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                symbol,
                close_reason,
                entry_price,
                exit_price,
                tp_price,
                sl_price,
                qty,
                position_usdt,
                pnl_usdt,
                pnl_pct,
                opened_at,
                now_ts,
                now_ts
            )
        )

        inserted = cursor.rowcount == 1

        conn.commit()
        conn.close()

        if inserted:
            write_trade_journal(
                f"{close_reason} | "
                f"Order={order_id} | "
                f"Symbol={symbol} | "
                f"Entry={entry_price:.4f} | "
                f"Exit={exit_price:.4f} | "
                f"Qty={qty:.2f} | "
                f"Size={position_usdt:.2f} USDT | "
                f"PnL={pnl_usdt:+.4f} USDT ({pnl_pct:+.2f}%) | "
                f"TP={tp_price:.4f} | "
                f"SL={sl_price:.4f}"
            )
        else:
            logging.warning(f"Trade history duplicate ignored: order_id={order_id}")

        return {
            "position_usdt": position_usdt,
            "pnl_usdt": pnl_usdt,
            "pnl_pct": pnl_pct,
            "inserted": inserted
        }

    except Exception as e:
        logging.error(f"Failed to write trade_history: {e}")

        return {
            "position_usdt": 0.0,
            "pnl_usdt": 0.0,
            "pnl_pct": 0.0,
            "inserted": False
        }
