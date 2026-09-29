"""Simple logger module for the application."""

import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """Get or create a logger instance."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        # Configure handler
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger
