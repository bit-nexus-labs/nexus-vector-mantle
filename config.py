# config.py
import sys
import logging
import threading
from pathlib import Path

# Примусове налаштування виводу для Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

RUNTIME_LOG_FILE = LOG_DIR / "nexus_runtime.log"
TRADES_LOG_FILE = LOG_DIR / "trades.log"

# AUTO_LOG_TRIM_ACTIVE
# Активний runtime-журнал тримає тільки останні рядки,
# а старі рядки автоматично переносить в logs/archive/.
LOG_ARCHIVE_DIR = LOG_DIR / "archive"
LOG_ARCHIVE_DIR.mkdir(exist_ok=True)
MAX_ACTIVE_LOG_LINES: int = 2000
TRIM_TRIGGER_LOG_LINES: int = 2300


class TeeStream:
    """
    Дублює потік терміналу у текстовий runtime-журнал.

    Додатково автоматично обрізає logs/nexus_runtime.log,
    щоб активний файл залишався компактним для перегляду та аналізу.
    trades.log не чіпається.
    """

    _rotation_lock = threading.RLock()

    def __init__(self, terminal_stream, log_path: Path):
        self.terminal_stream = terminal_stream
        self.log_path = Path(log_path)
        self._trimming = False
        self._line_count = self._count_existing_lines()
        self.log_file = open(self.log_path, "a", encoding="utf-8", buffering=1)

    def _count_existing_lines(self) -> int:
        try:
            if not self.log_path.exists():
                return 0
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _trim_runtime_log_if_needed(self) -> None:
        if self._trimming or self.log_path.name != RUNTIME_LOG_FILE.name:
            return

        if self._line_count < TRIM_TRIGGER_LOG_LINES:
            return

        with TeeStream._rotation_lock:
            if self._trimming:
                return

            self._trimming = True

            try:
                self.log_file.flush()

                with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                if len(lines) <= TRIM_TRIGGER_LOG_LINES:
                    self._line_count = len(lines)
                    return

                archived_lines = lines[:-MAX_ACTIVE_LOG_LINES]
                active_lines = lines[-MAX_ACTIVE_LOG_LINES:]

                archive_name = f"nexus_runtime_archive_{__import__('datetime').datetime.now():%Y-%m-%d}.log"
                archive_path = LOG_ARCHIVE_DIR / archive_name

                with open(archive_path, "a", encoding="utf-8") as archive_file:
                    archive_file.writelines(archived_lines)

                self.log_file.close()

                with open(self.log_path, "w", encoding="utf-8") as active_file:
                    active_file.writelines(active_lines)

                self.log_file = open(self.log_path, "a", encoding="utf-8", buffering=1)
                self._line_count = len(active_lines)

                # Пишемо напряму в термінал, без print(), щоб не створити рекурсію.
                try:
                    self.terminal_stream.write(
                        f"\n[LOG ROTATION] Archived={len(archived_lines)} lines | "
                        f"Active={len(active_lines)} lines | File={self.log_path}\n"
                    )
                    self.terminal_stream.flush()
                except Exception:
                    pass

            except Exception as e:
                try:
                    self.terminal_stream.write(f"\n[LOG ROTATION ERROR] {e}\n")
                    self.terminal_stream.flush()
                except Exception:
                    pass

            finally:
                self._trimming = False

    def write(self, message):
        self.terminal_stream.write(message)
        self.log_file.write(message)

        if message:
            self._line_count += str(message).count("\n")
            self._trim_runtime_log_if_needed()

    def flush(self):
        self.terminal_stream.flush()
        self.log_file.flush()

    def isatty(self):
        return self.terminal_stream.isatty()

    def __getattr__(self, name):
        return getattr(self.terminal_stream, name)


sys.stdout = TeeStream(sys.stdout, RUNTIME_LOG_FILE)
sys.stderr = TeeStream(sys.stderr, RUNTIME_LOG_FILE)

# Залізобетонний формат логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ТОРГОВІ НАЛАШТУВАННЯ
SYMBOL: str = "XRPUSDT"
CCXT_SYMBOL: str = "XRP/USDT"

BASE_ASSET: str = CCXT_SYMBOL.split("/")[0]
QUOTE_ASSET: str = CCXT_SYMBOL.split("/")[1]

TIMEFRAME: str = "5m"
KLINES_LIMIT: int = 40

# КВАНТОВІ ПАРАМЕТРИ СТРАТЕГІЇ
FVG_OFFSET_PERC: float = 0.0000  # Вхід чітко по межі FVG
SL_OFFSET_PERC: float = 0.0010   # -0.1% безпечний відступ від Swing Low для захисту стопу
ORDER_LIFETIME_SECONDS: int = 45 * 60
FLAT_TIMEOUT_SECONDS: int = 35 * 60

# НОВА АРХІТЕКТУРНА КОНСТАНТА (Пункт 1 ТЗ)
MIN_RISK_REWARD_RATIO: float = 1.2   # Мінімально допустимий поріг R:R для входу в Long
MIN_ENTRY_DISCOUNT_PERC: float = 0.0015  # Entry must be at least 0.15% below current price

# ОБМЕЖЕННЯ ОБ'ЄМУ (Захист капіталу)
MIN_VOL_USDT: float = 5.0
MAX_VOL_USDT: float = 30.0

# Назви файлів баз даних
DB_BOT: str = "bot_data.db"
DB_TRADES: str = "trades_data.db"
