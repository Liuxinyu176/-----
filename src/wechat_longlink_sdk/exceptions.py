from __future__ import annotations

from typing import Any


class SDKError(Exception):
    def __init__(self, message: str, *, error_code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class SDKConfigError(ValueError):
    pass


class APIError(SDKError):
    pass


class APINotFoundError(APIError):
    pass


class APIParameterValidationError(APIError):
    pass


class APITransportError(APIError):
    pass


class APIRetryExhaustedError(APIError):
    pass
