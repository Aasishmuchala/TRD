"""Structured JSON logging configuration."""

import logging
import json
import sys
from datetime import datetime
from app.config import config


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    """Configure structured logging for the application."""
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    if config.ENV == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
