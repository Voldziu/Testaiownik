# src/testaiownik/utils/logger.py
import logging
import sys
from typing import Optional
from opencensus.ext.azure.log_exporter import AzureLogHandler


def setup_logger(
    name: str = "testaiownik",
    level: str = "INFO",
    azure_app_insights_connection_string: Optional[str] = None,
) -> logging.Logger:
    """Setup global logger for the project."""

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Azure handler
    if azure_app_insights_connection_string:
        azure_handler = AzureLogHandler(
            connection_string=azure_app_insights_connection_string
        )
        azure_handler.setFormatter(formatter)
        logger.addHandler(azure_handler)

    return logger


# Global logger instance
logger = setup_logger()
