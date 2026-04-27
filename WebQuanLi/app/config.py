import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    PROJECT_NAME: str = "WebQuanLi - Hệ Thống Cảnh Báo Buồn Ngủ"
    VERSION: str = "1.0.0"

    SECRET_KEY: str = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("Lỗi Bảo Mật: Chưa cấu hình SECRET_KEY trong .env. Vui lòng copy từ .env.example sang .env và sửa lại.")

    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'drowsiness.db'}")

    ESMS_API_KEY: str = os.getenv("ESMS_API_KEY", "")
    ESMS_SECRET_KEY: str = os.getenv("ESMS_SECRET_KEY", "")
    ESMS_BRANDNAME: str = os.getenv("ESMS_BRANDNAME", "Baotintuc")
    ESMS_SMS_TYPE: int = int(os.getenv("ESMS_SMS_TYPE", "2"))

    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME")
    if not ADMIN_USERNAME:
        raise ValueError("Lỗi Bảo Mật: Chưa cấu hình ADMIN_USERNAME trong .env.")

    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD")
    if not ADMIN_PASSWORD:
        raise ValueError("Lỗi Bảo Mật: Chưa cấu hình ADMIN_PASSWORD trong .env.")

    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    UPLOAD_DIR: Path = BASE_DIR / "static" / "updates"
    DATA_DIR: Path = BASE_DIR / "data"

    OFFLINE_THRESHOLD_SECONDS: int = 60
    SESSION_CLOSE_TIMEOUT_SECONDS: int = 300  # 5 minutes


settings = Settings()

import logging
import sys

class FerrariFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[94m",    # BLUE
        logging.INFO: "\033[92m",     # GREEN (🚀)
        logging.WARNING: "\033[93m",  # YELLOW (⚠️)
        logging.ERROR: "\033[91m",    # RED (🛑)
        logging.CRITICAL: "\033[95m", # MAGENTA (💥)
    }
    EMOJIS = {
        logging.DEBUG: "🔍 ",
        logging.INFO: "🚀 [OK] ",
        logging.WARNING: "⚠️ [WARN] ",
        logging.ERROR: "🛑 [ERROR] ",
        logging.CRITICAL: "💥 [CRITICAL] ",
    }
    def format(self, record):
        color = self.COLORS.get(record.levelno, "\033[0m")
        emoji = self.EMOJIS.get(record.levelno, "")
        reset = "\033[0m"
        record.msg = f"{color}{emoji}{record.msg}{reset}"
        return super().format(record)

def setup_cool_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Xoá handler có sẵn của Uvicorn để tránh in double
    if logger.hasHandlers():
        logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    formatter = FerrariFormatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
