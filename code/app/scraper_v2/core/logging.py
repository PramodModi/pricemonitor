"""
Logging for scraper_v2.

When running inside PriceMonitor: delegates to app.utils.logging.get_logger
so log format stays consistent across the whole app.

When running standalone (run_test.py, future FastAPI service): falls back
to a standard Python logger with the same format.
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger for the given module name.

    Tries to use PriceMonitor's get_logger first (consistent format).
    Falls back to a plain stdlib logger if running standalone.
    """
    try:
        from app.utils.logging import get_logger as pm_get_logger
        return pm_get_logger(name)
    except ImportError:
        return _make_standalone_logger(name)


def _make_standalone_logger(name: str) -> logging.Logger:
    """
    Minimal logger used when scraper runs outside PriceMonitor.
    Single handler to stdout, same level as LOG_LEVEL env var.
    """
    import os
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
