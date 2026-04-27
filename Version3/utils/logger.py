"""
DrowsiGuard — Centralized Logging
Structured logging with module tags, file rotation, and console output.
"""
import logging
import logging.handlers
import os
import sys

_configured = False


def setup_logger(name: str = "drowsiguard", level: str = "INFO",
                 log_file: str = None, max_bytes: int = 5 * 1024 * 1024,
                 backup_count: int = 3) -> logging.Logger:
    """Configure and return root logger for the project.

    Call once from main.py. Subsequent calls from modules should use
    ``logging.getLogger("drowsiguard.module_name")``.
    """
    global _configured

    logger = logging.getLogger(name)

    if _configured:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)-25s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler. Windows terminals often default to cp1252, which
    # crashes on demo-friendly status icons unless we opt into UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler (optional)
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Return a child logger for a specific module."""
    return logging.getLogger(f"drowsiguard.{module_name}")
