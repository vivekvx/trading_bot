"""
Centralized logging configuration for the trading bot.

All API requests, responses, and errors are logged to a rotating log file
(trading_bot.log) as well as printed to the console at a higher level so the
log file stays useful for debugging without spamming the terminal.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent / "trading_bot.log"


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """
    Configure and return the root 'trading_bot' logger.

    - File handler: DEBUG level, captures everything (requests, responses, errors)
    - Console handler: INFO level, keeps terminal output clean
    """
    logger = logging.getLogger("trading_bot")
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging() is called more than once
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
