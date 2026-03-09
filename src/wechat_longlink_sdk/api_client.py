from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .exceptions import (
    APIError,
    APINotFoundError,
    APIParameterValidationError,
    APIRetryExhaustedError,
    APITransportError,
)

TransportCallable = Callable[[str, str, Mapping[str, Any], str | None], Mapping[str, Any]]


@dataclass(frozen=True)
class APIDefinition:
    name: str
    path: str
    method: str
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()
    retryable: bool = True

    @property
    def allowed_params(self) -> set[str]:
        return set(self.required_params).union(self.optional_params)


@dataclass(frozen=True)
class APIRetryPolicy:
    max_attempts: int = 3
    initial_interval_seconds: float = 0.2
    backoff_factor: float = 2.0
    max_interval_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than or equal to 1")
        if self.initial_interval_seconds <= 0:
            raise ValueError("initial_interval_seconds must be greater than 0")
        if self.backoff_factor < 1:
            raise ValueError("backoff_factor must be greater than or equal to 1")
        if self.max_interval_seconds <= 0:
            raise ValueError("max_interval_seconds must be greater than 0")


API_CATALOG: dict[str, APIDefinition] = {
    "message.send_text": APIDefinition(
        name="message.send_text",
        path="/v1/messages/text/send",
        method="POST",
        required_params=("conversation_id", "content"),
        optional_params=("metadata", "request_id"),
    ),
    "message.send_image": APIDefinition(
        name="message.send_image",
        path="/v1/messages/image/send",
        method="POST",
        required_params=("conversation_id", "image_url"),
        optional_params=("caption", "metadata", "request_id"),
    ),
    "message.send_file": APIDefinition(
        name="message.send_file",
        path="/v1/messages/file/send",
        method="POST",
        required_params=("conversation_id", "file_name", "file_url"),
        optional_params=("file_size", "mime_type", "metadata", "request_id"),
    ),
    "message.send_rich_media": APIDefinition(
        name="message.send_rich_media",
        path="/v1/messages/rich-media/send",
        method="POST",
        required_params=("conversation_id", "title", "description", "resource_url"),
        optional_params=("thumbnail_url", "metadata", "request_id"),
    ),
    "bot.profile.get": APIDefinition(
        name="bot.profile.get",
        path="/v1/bot/profile",
        method="GET",
        required_params=(),
        optional_params=("bot_id",),
    ),
    "conversation.history.list": APIDefinition(
        name="conversation.history.list",
        path="/v1/conversations/history",
        method="GET",
        required_params=("conversation_id",),
        optional_params=("cursor", "limit"),
    ),
}

ERROR_CODE_TO_EXCEPTION: dict[str, type[APIError]] = {
    "invalid_parameter": APIParameterValidationError,
    "not_found": APINotFoundError,
    "transport_error": APITransportError,
}

RETRYABLE_ERROR_CODES: set[str] = {
    "timeout",
    "rate_limited",
    "server_busy",
    "transport_error",
}


class DocumentAPIClient:
    def __init__(
        self,
        transport: TransportCallable | None = None,
        retry_policy: APIRetryPolicy | None = None,
        api_catalog: Mapping[str, APIDefinition] | None = None,
    ) -> None:
        self._transport = transport or self._default_transport
        self._retry_policy = retry_policy or APIRetryPolicy()
        self._api_catalog = dict(api_catalog or API_CATALOG)

    def list_apis(self) -> list[str]:
        return sorted(self._api_catalog.keys())

    def get_api_definition(self, api_name: str) -> APIDefinition:
        api_definition = self._api_catalog.get(api_name)
        if api_definition is None:
            raise APINotFoundError(
                f"unsupported api: {api_name}",
                error_code="api_not_found",
                details={"api_name": api_name},
            )
        return api_definition

    def call_api(
        self,
        api_name: str,
        params: Mapping[str, Any] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        api_definition = self.get_api_definition(api_name)
        safe_params = dict(params or {})
        self._validate_params(api_definition, safe_params)
        return self._execute_with_retry(api_definition, safe_params, session_id)

    def _validate_params(self, api_definition: APIDefinition, params: Mapping[str, Any]) -> None:
        missing_params = [param for param in api_definition.required_params if param not in params]
        if missing_params:
            raise APIParameterValidationError(
                "missing required params",
                error_code="missing_required_params",
                details={"api_name": api_definition.name, "missing_params": missing_params},
            )
        unknown_params = [key for key in params if key not in api_definition.allowed_params]
        if unknown_params:
            raise APIParameterValidationError(
                "unknown params found",
                error_code="unknown_params",
                details={"api_name": api_definition.name, "unknown_params": unknown_params},
            )
        for key, value in params.items():
            self._validate_param_value(key, value)

    def _validate_param_value(self, key: str, value: Any) -> None:
        if isinstance(value, str) and not value.strip():
            raise APIParameterValidationError(
                "string param cannot be empty",
                error_code="invalid_parameter",
                details={"param": key},
            )
        if key == "limit":
            if not isinstance(value, int):
                raise APIParameterValidationError(
                    "limit must be int",
                    error_code="invalid_parameter",
                    details={"param": key},
                )
            if value <= 0 or value > 200:
                raise APIParameterValidationError(
                    "limit must be in range 1-200",
                    error_code="invalid_parameter",
                    details={"param": key, "value": value},
                )
        if key == "file_size":
            if not isinstance(value, int):
                raise APIParameterValidationError(
                    "file_size must be int",
                    error_code="invalid_parameter",
                    details={"param": key},
                )
            if value < 0:
                raise APIParameterValidationError(
                    "file_size must be greater than or equal to 0",
                    error_code="invalid_parameter",
                    details={"param": key, "value": value},
                )

    def _execute_with_retry(
        self,
        api_definition: APIDefinition,
        params: Mapping[str, Any],
        session_id: str | None,
    ) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                response = dict(self._transport(api_definition.path, api_definition.method, params, session_id))
                self._raise_for_error_response(api_definition.name, response)
                response.setdefault("ok", True)
                response.setdefault("api_name", api_definition.name)
                response.setdefault("attempt", attempt)
                return response
            except APIError as exc:
                retryable = api_definition.retryable and self._is_retryable_error(exc)
                errors.append(
                    {
                        "attempt": attempt,
                        "error_code": exc.error_code,
                        "message": str(exc),
                        "details": dict(exc.details),
                    }
                )
                if not retryable or attempt >= self._retry_policy.max_attempts:
                    raise APIRetryExhaustedError(
                        "api call failed after retry attempts",
                        error_code=exc.error_code or "api_call_failed",
                        details={"api_name": api_definition.name, "attempts": attempt, "errors": errors},
                    ) from exc
                self._sleep_before_retry(attempt)
            except Exception as exc:
                wrapped_exc = APITransportError(
                    "unexpected transport exception",
                    error_code="transport_error",
                    details={"api_name": api_definition.name, "exception": str(exc), "attempt": attempt},
                )
                retryable = api_definition.retryable and self._is_retryable_error(wrapped_exc)
                errors.append(
                    {
                        "attempt": attempt,
                        "error_code": wrapped_exc.error_code,
                        "message": str(wrapped_exc),
                        "details": dict(wrapped_exc.details),
                    }
                )
                if not retryable or attempt >= self._retry_policy.max_attempts:
                    raise APIRetryExhaustedError(
                        "api call failed after retry attempts",
                        error_code=wrapped_exc.error_code,
                        details={"api_name": api_definition.name, "attempts": attempt, "errors": errors},
                    ) from exc
                self._sleep_before_retry(attempt)
        raise APIRetryExhaustedError(
            "api call failed after retry attempts",
            error_code="retry_exhausted",
            details={"api_name": api_definition.name, "errors": errors},
        )

    def _raise_for_error_response(self, api_name: str, response: Mapping[str, Any]) -> None:
        if response.get("ok", True):
            return
        error_code = str(response.get("error_code", "unknown_error"))
        message = str(response.get("message", "api call failed"))
        details = {"api_name": api_name, "response": dict(response)}
        exception_class = ERROR_CODE_TO_EXCEPTION.get(error_code, APIError)
        raise exception_class(message, error_code=error_code, details=details)

    def _is_retryable_error(self, exc: APIError) -> bool:
        return bool(exc.error_code and exc.error_code in RETRYABLE_ERROR_CODES)

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self._retry_policy.initial_interval_seconds * (self._retry_policy.backoff_factor ** (attempt - 1))
        time.sleep(min(delay, self._retry_policy.max_interval_seconds))

    def _default_transport(
        self,
        path: str,
        method: str,
        params: Mapping[str, Any],
        session_id: str | None,
    ) -> Mapping[str, Any]:
        return {
            "ok": True,
            "path": path,
            "method": method,
            "params": dict(params),
            "session_id": session_id,
        }
