# -*- coding: utf-8 -*-
"""Centralized logging configuration for FastSM."""

import logging
import logging.handlers
import os
import sys
from typing import Optional

# Global logger instance
_logger: Optional[logging.Logger] = None
_config_dir: Optional[str] = None


def setup_logging(config_dir: str, debug: bool = False) -> logging.Logger:
    """Initialize application-wide logging.

    Args:
        config_dir: Directory to store log files
        debug: If True, log at DEBUG level; otherwise INFO

    Returns:
        Configured logger instance
    """
    global _logger, _config_dir
    _config_dir = config_dir

    # Create or get the fastsm logger
    logger = logging.getLogger('fastsm')

    # Clear any existing handlers (in case of re-initialization)
    logger.handlers.clear()

    # Set base level (handlers can filter further)
    logger.setLevel(logging.DEBUG)

    # Ensure config directory exists
    os.makedirs(config_dir, exist_ok=True)

    # File handler with rotation (5MB max, keep 3 backups)
    log_file = os.path.join(config_dir, 'fastsm.log')
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)

        # Detailed format for file (timestamp at end for easier reading)
        file_formatter = logging.Formatter(
            '%(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s - %(asctime)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If we can't create the file handler, log to stderr
        print(f"Warning: Could not create log file: {e}", file=sys.stderr)

    # Console handler for errors only (keeps stderr clean)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.ERROR)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    _logger = logger
    logger.info(f"Logging initialized (debug={debug})")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Optional name for a child logger (e.g., 'fastsm.api')
              If None, returns the main fastsm logger

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f'fastsm.{name}')
    return logging.getLogger('fastsm')


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug logging at runtime.

    Args:
        enabled: If True, set file handler to DEBUG level; otherwise INFO
    """
    logger = logging.getLogger('fastsm')
    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.setLevel(logging.DEBUG if enabled else logging.INFO)
            logger.info(f"Debug logging {'enabled' if enabled else 'disabled'}")
            break


def get_log_file_path() -> Optional[str]:
    """Get the path to the current log file.

    Returns:
        Path to log file, or None if logging not initialized
    """
    if _config_dir:
        return os.path.join(_config_dir, 'fastsm.log')
    return None
