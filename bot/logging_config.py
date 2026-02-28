"""
Centralized logging configuration.
- app.log   : general application events
- security.log : security-related events (login, auth, replay, brute-force)
Both use RotatingFileHandler (5 MB, 5 backups) with UTC timestamps.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class UTCFormatter(logging.Formatter):
    """Force all timestamps to UTC."""
    converter = lambda *args: datetime.now(timezone.utc).timetuple()


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _make_handler(filename: str, level: int = logging.DEBUG) -> RotatingFileHandler:
    path = os.path.join(LOG_DIR, filename)
    handler = RotatingFileHandler(
        path,
        maxBytes=3 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(level)
    fmt = UTCFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    handler.setFormatter(fmt)
    return handler


def _make_console_handler(level: int = logging.INFO) -> logging.StreamHandler:
    handler = logging.StreamHandler()
    handler.setLevel(level)
    fmt = UTCFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    handler.setFormatter(fmt)
    return handler


# ── Public loggers ──────────────────────────────────────────────

def get_app_logger(name: str = "app") -> logging.Logger:
    """Logger for general application events."""
    logger = logging.getLogger(f"attendance.{name}")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_make_handler("app.log"))
        logger.addHandler(_make_console_handler())
        logger.propagate = False
    return logger


def get_security_logger() -> logging.Logger:
    """Logger for security / audit events."""
    logger = logging.getLogger("attendance.security")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_make_handler("security.log"))
        logger.addHandler(_make_console_handler(logging.WARNING))
        logger.propagate = False
    return logger
