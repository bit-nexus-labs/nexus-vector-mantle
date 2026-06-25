# market_structure_analysis.py
import logging
from typing import Tuple, Optional, List, Dict, Any
from config import FVG_OFFSET_PERC, SL_OFFSET_PERC, MIN_RISK_REWARD_RATIO
from database import get_setting
import datetime

# ANSI Колірна гама для блискавичного зчитування табло Windows
C_BLUE = "\033[94m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_RESET = "\033[0m"

def find_latest_swing_low(klines, min_candles_right=2):
    """Шукає істинне математичне дно по РЕАЛЬНИХ ТІНЯХ (Low) свічок у двовимірному масиві."""
    if len(klines) < (min_candles_right + 3):
        return {"low": 0.0, "index": 0}

    # Беремо Low останньої стабільної свічки як стартову точку
    latest_low_price = float(klines[-1][3])

    for i in range(len(klines) - min_candles_right - 1, min_candles_right, -1):
        # Індекс [3] — це реальний мінімум (Low) свічки CCXT
        idx_low = float(klines[i][3])

        # Перевірка локального фрактального дна по тінях зліва і справа
        if idx_low < float(klines[i - 1][3]) and idx_low < float(klines[i + 1][3]):
            if idx_low < latest_low_price:
                latest_low_price = idx_low
                return {"low": latest_low_price, "index": i}

    return {"low": latest_low_price, "index": len(klines) - 1}

def find_latest_swing_high(klines, min_candles_right=2):
    """Шукає істинну математичну верхівку по РЕАЛЬНИХ ТІНЯХ (High) свічок у двовимірному масиві."""
    if len(klines) < (min_candles_right + 3):
        return {"high": 0.0, "index": 0}

    # Беремо High останньої стабільної свічки як стартову точку
    latest_high_price = float(klines[-1][2])

    for i in range(len(klines) - min_candles_right - 1, min_candles_right, -1):
        # Індекс [2] — це реальний максимум (High) свічки CCXT
        idx_high = float(klines[i][2])

        # Перевірка локальної фрактальної вершини по тінях зліва і справа
        if idx_high > float(klines[i - 1][2]) and idx_high > float(klines[i + 1][2]):
            if idx_high > latest_high_price:
                latest_high_price = idx_high
                return {"high": latest_high_price, "index": i}

    return {"high": latest_high_price, "index": len(klines) - 1}

def find_bullish_fvg_above_low(klines, swing_low_idx):
    length = len(klines)

    for i in range(swing_low_idx, length - 1):

        if i - 1 < 0 or i + 1 >= length:
            continue

        c1_high = float(klines[i - 1][2])
        c2_close = float(klines[i][4])
        c3_low = float(klines[i + 1][3])

        gap = c3_low - c1_high
        print(
            f"FVG CHECK | "
            f"i={i} | "
            f"C1H={c1_high:.4f} | "
            f"C3L={c3_low:.4f} | "
            f"GAP={gap:.4f} | "
            f"VALID={c3_low > c1_high}"
        )

        if c3_low > c1_high:
            return {
                "trigger_index": i + 1,
                "top": c3_low,
                "bottom": c1_high,
                "gap": c3_low - c1_high
            }

    return None

def calculate_atr(klines: List[List[Any]], period: int = 14) -> float:
    """⚙️ ПУНКТ 2 ТЗ: Розрахунок середнього істинного діапазону волатильності ATR."""
    if len(klines) < period + 1:
        return 0.0015
    tr_values = []
    for i in range(len(klines) - period, len(klines)):
        high = float(klines[i][2])
        low = float(klines[i][3])
        prev_close = float(klines[i-1][4]) # Індекс 4 - це Close свічки
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    return sum(tr_values) / len(tr_values)

def calculate_target_wall(klines_24h: List[List[Any]]) -> float:
    """⚙️ ПУНКТ 2 ТЗ: Визначення інституційного об'єму стіни (15% від середньої 5-хвилинки)."""
    if not klines_24h:
        return 300000.0
    # Індекс 5 в масиві CCXT — це об'єм торів свічки (Volume)
    total_volume = sum(float(k[5]) for k in klines_24h)
    avg_candle_volume = total_volume / len(klines_24h)
    return avg_candle_volume * 0.15

def calculate_trade_parameters(klines_raw, klines_close):

    atr_value = calculate_atr(klines_raw, period=14)

    if not klines_raw or len(klines_raw) < 10:
        return False, 0.0, 0.0, 0.0, "Недостатньо даних", "limit", atr_value


    swing_low = find_latest_swing_low(
        klines_raw,
        min_candles_right=2
    )

    if not swing_low:
        return False, 0.0, 0.0, 0.0, \
            "Swing Low не знайдено", "limit", atr_value

    print(
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
        f"SWING LOW FOUND | "
        f"Low={swing_low['low']:.4f} | "
        f"Index={swing_low['index']}"
    )

    current_price = float(klines_close[-1])

    distance = (
        (current_price - swing_low["low"])
        / current_price
    ) * 100

    print(
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
        f"MARKET DISTANCE | "
        f"Price={current_price:.4f} | "
        f"SwingLow={swing_low['low']:.4f} | "
        f"Distance={distance:.2f}%"
    )

    print(
    f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
    f"SCAN INFO | "
    f"Bars={len(klines_raw)} | "
    f"Current={current_price:.4f} | "
    f"ATR={atr_value:.4f}"
)

    fvg = find_bullish_fvg_above_low(
        klines_raw,
        swing_low["index"]
    )

    if not fvg:
        print(
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
            f"FVG SEARCH FAILED | "
            f"SwingLow={swing_low['low']:.4f}"
        )
        return False, 0.0, 0.0, 0.0, \
            "Бичий FVG не знайдено", "limit", atr_value


    swing_high = find_latest_swing_high(
        klines_raw,
        min_candles_right=2
    )

    if not swing_high:
        return False, 0.0, 0.0, 0.0, \
            "Swing High не знайдено", "limit", atr_value

    try:
        min_rr = float(
            get_setting(
                "min_rr_ratio",
                str(MIN_RISK_REWARD_RATIO)
            )
        )
    except:
        min_rr = MIN_RISK_REWARD_RATIO

    distance_to_fvg = (
            (current_price - fvg['top'])
            / current_price
        ) * 100

    print(
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
        f"Low={C_RED}{swing_low['low']:.4f}{C_RESET} | "
        f"FVG={C_BLUE}{fvg['bottom']:.4f}-{fvg['top']:.4f}{C_RESET} | "
        f"High={C_GREEN}{swing_high['high']:.4f}{C_RESET} | "
        f"Now={C_BLUE}{current_price:.4f}{C_RESET} | "
        f"Dist={distance_to_fvg:.2f}%"
    )

    sl_price = swing_low["low"] * (1 - SL_OFFSET_PERC)

    tp_price = swing_high["high"]

    fvg_top = float(
        fvg["top"] * (1 - FVG_OFFSET_PERC)
    )

    fvg_bottom = float(
        fvg["bottom"]
    )

    risk_top = fvg_top - sl_price
    reward_top = tp_price - fvg_top

    rr_top = reward_top / risk_top if risk_top > 0 else 0

    if rr_top >= min_rr:

        entry_price = fvg_top

    else:

        target_entry = (
            tp_price + sl_price * min_rr
        ) / (
            1 + min_rr
        )

        if fvg_bottom <= target_entry <= fvg_top:

            entry_price = target_entry

        else:

            comment = (
                f"🔕 [СЕТАП ПРОПУЩЕНО] "
                f"R:R=1:{rr_top:.2f}"
            )

            return (
                False,
                0.0,
                0.0,
                0.0,
                comment,
                "limit",
                atr_value
        )

    risk_actual = entry_price - sl_price
    reward_actual = tp_price - entry_price

    rr_actual = (
        reward_actual / risk_actual
        if risk_actual > 0
        else 0
    )

    print(
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
        f"SETUP CHECK | "
        f"RR_TOP=1:{rr_top:.2f} | "
        f"MIN_RR=1:{min_rr:.2f}"
    )
    comment = (
        f"🚀 [FVG LONG] "
        f"R:R=1:{rr_actual:.2f}"
    )


    discount = ((current_price - entry_price) / current_price) * 100

    print(
        f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
        f"{C_BLUE}FVG[{fvg_bottom:.4f}-{fvg_top:.4f}]{C_RESET} | "
        f"FVG_SIZE={(fvg['top'] - fvg['bottom']):.4f} | "
        f"Now={C_BLUE}{current_price:.4f}{C_RESET} | "
        f"Entry={C_BLUE}{entry_price:.4f}{C_RESET} | "
        f"Discount={C_GREEN}{discount:.2f}%{C_RESET} | "
        f"SL={C_RED}{sl_price:.4f}{C_RESET} | "
        f"TP={C_GREEN}{tp_price:.4f}{C_RESET} | "
        f"RR={C_BLUE}1:{rr_actual:.2f}{C_RESET}"
    )

    return (
        True,
        round(entry_price, 4),
        round(sl_price, 4),
        round(tp_price, 4),
        comment,
        "limit",
        atr_value
    )
