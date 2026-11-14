import logging
import re
import sys
from typing import Any, Dict


# Common patterns for PII / Secrets redaction
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
BEARER_TOKEN_REGEX = re.compile(r"Bearer\s+([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*)", re.IGNORECASE)


def redact_sensitive_data(text: str) -> str:
    """Redacts known sensitive patterns (SSN, credit card, bearer tokens) from log messages."""
    text = SSN_REGEX.sub("[REDACTED_SSN]", text)
    text = CREDIT_CARD_REGEX.sub("[REDACTED_CC]", text)
    text = BEARER_TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", text)
    return text


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs sensitive PII and secrets from log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_data(record.msg)
        return True


def setup_logging() -> logging.Logger:
    """Configures structured, security-aware logging for FinTrust."""
    logger = logging.getLogger("fintrust")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        
    return logger


logger = setup_logging()
