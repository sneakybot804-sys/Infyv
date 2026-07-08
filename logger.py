"""Logging setup for the application."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import config

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger.

    Handlers are attached only once per logger to avoid duplicate output.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(config.log_level)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        config.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=config.paths.logs_dir / "app.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning("Could not create file log handler; using console only.")

    logger.propagate = False
    return logger
