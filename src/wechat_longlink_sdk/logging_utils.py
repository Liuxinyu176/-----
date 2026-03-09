from __future__ import annotations

import logging
import re
from typing import Iterable


class SecretRedactingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]
        self._secret_pattern = re.compile(r"(secret=)([^,\s]+)", re.IGNORECASE)

    def add_secrets(self, secrets: Iterable[str] | None = None) -> None:
        for secret in secrets or []:
            if secret and secret not in self._secrets:
                self._secrets.append(secret)

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        redacted = self._secret_pattern.sub(r"\1***", rendered)
        for secret in self._secrets:
            if secret:
                redacted = redacted.replace(secret, "***")
        record.msg = redacted
        record.args = ()
        return True


def setup_sdk_logger(name: str, secrets: Iterable[str] | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    ensure_redacting_filter(logger, secrets=secrets)
    return logger


def ensure_redacting_filter(logger: logging.Logger, secrets: Iterable[str] | None = None) -> logging.Logger:
    current = next((f for f in logger.filters if isinstance(f, SecretRedactingFilter)), None)
    if current is None:
        current = SecretRedactingFilter(secrets=secrets)
        logger.addFilter(current)
    else:
        current.add_secrets(secrets=secrets)
    return logger
