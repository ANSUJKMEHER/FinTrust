import json
import logging
import os
import re
import sys
from typing import Any, Dict


# Common patterns for PII / Secrets redaction
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
BEARER_TOKEN_REGEX = re.compile(r"Bearer\s+([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*)", re.IGNORECASE)
JWT_REGEX = re.compile(r"\beyJ[A-Za-z0-9-_=]{10,}\.[A-Za-z0-9-_=]{10,}\.[A-Za-z0-9-_=]{10,}\b")
SENSITIVE_KEY_VALUE_REGEX = re.compile(
    r'(["\']?(?:password|client_secret|api_key|secret_key|private_key)["\']?\s*[:=]\s*["\'])([^"\']+)(["\'])',
    re.IGNORECASE
)


def redact_sensitive_data(text: str) -> str:
    """Redacts known sensitive patterns (SSN, credit card, bearer tokens, passwords) from log messages."""
    text = SSN_REGEX.sub("[REDACTED_SSN]", text)
    text = CREDIT_CARD_REGEX.sub("[REDACTED_CC]", text)
    text = BEARER_TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", text)
    text = JWT_REGEX.sub("[REDACTED_JWT]", text)
    text = SENSITIVE_KEY_VALUE_REGEX.sub(r"\g<1>[REDACTED]\g<3>", text)
    return text


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs sensitive PII and secrets from log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        return True


class JSONLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for production ingestion (ELK, CloudWatch, Datadog)."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
            "module": record.module,
            "line": record.lineno
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Include custom context attributes if present
        for attr in ("request_id", "tenant_id", "user_id"):
            val = getattr(record, attr, None)
            if val is not None:
                log_obj[attr] = str(val)
        return json.dumps(log_obj)


def setup_logging() -> logging.Logger:
    """Configures structured, security-aware logging for FinTrust."""
    logger = logging.getLogger("fintrust")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        log_format = os.getenv("LOG_FORMAT", "text").lower()
        if log_format == "json":
            handler.setFormatter(JSONLogFormatter(datefmt="%Y-%m-%dT%H:%M:%S%z"))
        else:
            handler.setFormatter(logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        
    return logger


logger = setup_logging()
