# mexc_client.py
import asyncio
import logging
import ccxt
import math
from typing import List, Any, Optional
from config import (
    CCXT_SYMBOL,
    BASE_ASSET,
    TIMEFRAME,
    KLINES_LIMIT,
    MIN_VOL_USDT,
    MAX_VOL_USDT
)
from database import get_setting

DEBUG_BALANCE = False

def get_sync_exchange() -> ccxt.mexc:
    api_key = get_setting('mexc_api_key', '')
    secret_key = get_setting('mexc_secret_key', '')

    exchange = ccxt.mexc({
        'apiKey': api_key,
        'secret': secret_key,
        'options': {'defaultType': 'spot'},
        'enableRateLimit': True,
        'timeout': 10000
    })

    exchange.load_markets()

    return exchange
def truncate_float(number: float, decimals: int = 2) -> float:
    """Суворе квантове відсікання знаків після коми без округлення."""
    factor = 10 ** decimals
    return math.floor(number * factor) / factor

def _safe_balance_float(value, default: float = 0.0) -> float:
    """Safely converts CCXT balance values to float."""
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def sync_get_spot_balance_details(asset: str = BASE_ASSET) -> dict:
    """
    Returns full spot balance snapshot for asset:
    free / used / total.

    Important:
    - free = available balance
    - used = locked in open orders
    - total = free + used / exchange total
    """
    try:
        exchange = get_sync_exchange()
        balance = exchange.fetch_balance()

        free_bal = _safe_balance_float(
            balance.get("free", {}).get(asset, 0.0)
        )
        used_bal = _safe_balance_float(
            balance.get("used", {}).get(asset, 0.0)
        )
        total_bal = _safe_balance_float(
            balance.get("total", {}).get(asset, 0.0)
        )

        # Some exchanges may return total as 0/None while free+used is valid.
        if total_bal <= 0 and (free_bal > 0 or used_bal > 0):
            total_bal = free_bal + used_bal

        snapshot = {
            "asset": asset,
            "free": free_bal,
            "used": used_bal,
            "total": total_bal,
        }

        if DEBUG_BALANCE:
            logging.info(
                f"💰 BALANCE {asset}: "
                f"free={free_bal} | used={used_bal} | total={total_bal}"
            )

        return snapshot

    except Exception as e:
        logging.error(
            f"⚠️ Тимчасова помилка шлюзу MEXC при отриманні балансу {asset}: {repr(e)}"
        )
        return {
            "asset": asset,
            "free": 0.0,
            "used": 0.0,
            "total": 0.0,
        }


def sync_get_spot_balance(asset: str = BASE_ASSET) -> float:
    """
    Backward-compatible helper.

    Returns only FREE balance because old code expects float.
    For safety-critical logic use sync_get_spot_balance_details().
    """
    return sync_get_spot_balance_details(asset).get("free", 0.0)


async def get_spot_balance_safe(asset: str = BASE_ASSET) -> float:
    """Безпечне асинхронне отримання вільного балансу у потоці ОС."""
    return await asyncio.to_thread(sync_get_spot_balance, asset)


async def get_spot_balance_details_safe(asset: str = BASE_ASSET) -> dict:
    """Безпечне асинхронне отримання free / used / total балансу."""
    return await asyncio.to_thread(sync_get_spot_balance_details, asset)

def sync_fetch_klines() -> List[List[Any]]:
    exchange = ccxt.mexc({'options': {'defaultType': 'spot'}, 'enableRateLimit': True, 'timeout': 10000})
    try: return exchange.fetch_ohlcv(CCXT_SYMBOL, TIMEFRAME, limit=KLINES_LIMIT)
    except Exception as e: return []

async def fetch_market_klines() -> List[List[Any]]:
    return await asyncio.to_thread(sync_fetch_klines)

def sync_execute_order(side: str, order_type: str, qty: float, price: Optional[float] = None) -> Optional[dict]:
    exchange = get_sync_exchange()

    # Захист від "Oversold": якщо це маркет-продаж,
    # беремо реальний живий баланс з біржі.
    if side.lower() == "sell" and order_type.lower() == "market":
        balance_snapshot = sync_get_spot_balance_details(BASE_ASSET)

        base_free = float(balance_snapshot.get("free", 0.0))
        base_used = float(balance_snapshot.get("used", 0.0))
        base_total = float(balance_snapshot.get("total", 0.0))

        logging.info(
            f"🔍 Перевірка перед SELL: "
            f"{BASE_ASSET} free={base_free} | "
            f"used={base_used} | "
            f"total={base_total}"
        )

        if base_free <= 0:
            if base_total > 0 or base_used > 0:
                logging.error(
                    f"🚨 SELL ЗАБЛОКОВАНО: {BASE_ASSET} існує, "
                    f"але не доступний як free. "
                    f"Ймовірно, він locked/used у відкритому SELL LIMIT. "
                    f"free={base_free} | used={base_used} | total={base_total}. "
                    f"Спочатку треба скасувати відкритий SELL order."
                )
            else:
                logging.warning(
                    f"⚠️ SELL пропущено: {BASE_ASSET} відсутній на балансі. "
                    f"free={base_free} | used={base_used} | total={base_total}"
                )

            return None

        qty = truncate_float(base_free, 2)

        if qty <= 0:
            logging.error(
                f"🚨 SELL ЗАБЛОКОВАНО: після truncate qty <= 0. "
                f"free={base_free} | used={base_used} | total={base_total}"
            )
            return None

        logging.info(
            f"🔄 Коригування лоту SELL: "
            f"free={base_free} {BASE_ASSET} | "
            f"used={base_used} | "
            f"total={base_total}. "
            f"Продаємо: {qty} {BASE_ASSET}"
        )


    # 🛡️ ІНСТИТУЦІЙНИЙ МІСТ: Вирівнювання точності лоту та ціни під суворі ліміти споту MEXC
    try:
        qty_truncated = float(exchange.amount_to_precision(CCXT_SYMBOL, qty))
        if order_type.lower() == 'market':
            return exchange.create_order(CCXT_SYMBOL, 'market', side, qty_truncated)
        else:
            if price is None:
                raise ValueError("Для лімітного ордера BUY не передано ціну входу price!")
            p_rounded = float(exchange.price_to_precision(CCXT_SYMBOL, price))
            logging.info(
                f"📡 [БІРЖА API] Надсилаю істинну лімітку: "
                f"{side.upper()} {qty_truncated} {BASE_ASSET} по ціні {p_rounded}"
            )
            return exchange.create_order(CCXT_SYMBOL, 'limit', side, qty_truncated, p_rounded)
    except Exception as e:
        logging.error(
            f"❌ Помилка форматування ордера всередині CCXT: {e}"
        )
        return None

async def execute_order_safe(
    side: str,
    order_type: str,
    qty: float,
    price: Optional[float] = None
) -> Optional[dict]:

    try:
        return await asyncio.to_thread(
            sync_execute_order,
            side,
            order_type,
            qty,
            price
        )

    except Exception:
        logging.exception("❌ КРИТИЧНА ПОМИЛКА АПІ")
        return None

def sync_check_order(order_id: str) -> dict:
    exchange = get_sync_exchange()
    return exchange.fetch_order(order_id, CCXT_SYMBOL)

async def check_order_safe(order_id: str) -> Optional[dict]:
    try: return await asyncio.to_thread(sync_check_order, order_id)
    except Exception as e: return None

def sync_get_ticker_price() -> float:
    exchange = ccxt.mexc({'options': {'defaultType': 'spot'}, 'enableRateLimit': True, 'timeout': 10000})
    try:
        return exchange.fetch_ticker(CCXT_SYMBOL)['last']
    except Exception as e:
        logging.error(f"⚠️ Тимчасова помилка отримання ціни тікера через API: {e}")
        return 0.0

async def get_current_price_safe() -> float:
    return await asyncio.to_thread(sync_get_ticker_price)

async def calculate_position_size(entry_price: float, sl_price: float) -> Optional[float]:
    try: risk_usdt = float(get_setting('risk_usdt', '0.5'))
    except ValueError: risk_usdt = 0.5
    risk_per_token = abs(sl_price - entry_price)
    if risk_per_token == 0: return None
    qty = risk_usdt / risk_per_token
    total_volume_usdt = qty * entry_price

    logging.info(f"📐 Розрахунок лоту: Математичний об'єм стратегії = {total_volume_usdt:.2f} USDT (Ризик={risk_usdt} USDT)")

    if total_volume_usdt < MIN_VOL_USDT: return None
    if total_volume_usdt > MAX_VOL_USDT:
        qty = MAX_VOL_USDT / entry_price
        total_volume_usdt = MAX_VOL_USDT
        qty_truncated = truncate_float(qty, 2)
        logging.info(
            f"🛡️ Ризик-менеджмент: Об'єм перевищує ліміт! "
            f"Примусово зрізано до {total_volume_usdt:.2f} USDT "
            f"({qty_truncated} {BASE_ASSET})"
        )
        return qty_truncated

    return truncate_float(qty, 2)
