from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import SDKConfigError

DEFAULT_BOT_ID_ENV_KEYS: tuple[str, ...] = (
    "WECHAT_BOT_ID",
    "WECOM_BOT_ID",
    "BOT_ID",
)
DEFAULT_SECRET_ENV_KEYS: tuple[str, ...] = (
    "WECHAT_BOT_SECRET",
    "WECOM_BOT_SECRET",
    "BOT_SECRET",
)
DEFAULT_API_BOT_ID_ENV_KEYS: tuple[str, ...] = (
    "WECHAT_API_BOT_ID",
    "WECOM_API_BOT_ID",
    "API_BOT_ID",
)


@dataclass(frozen=True)
class SDKConfig:
    bot_id: str
    secret: str
    api_bot_id: str | None = None
    websocket_url: str = "wss://openws.work.weixin.qq.com"
    heartbeat_interval_seconds: float = 30.0
    reconnect_interval_seconds: float = 5.0
    max_reconnect_attempts: int = 0

    def __post_init__(self) -> None:
        if not self.bot_id or not self.bot_id.strip():
            raise SDKConfigError("bot_id is required")
        if not self.secret or not self.secret.strip():
            raise SDKConfigError("secret is required")
        if self.heartbeat_interval_seconds <= 0:
            raise SDKConfigError("heartbeat_interval_seconds must be greater than 0")
        if self.reconnect_interval_seconds <= 0:
            raise SDKConfigError("reconnect_interval_seconds must be greater than 0")
        if self.max_reconnect_attempts < 0:
            raise SDKConfigError("max_reconnect_attempts must be greater than or equal to 0")
        if not self.websocket_url or not self.websocket_url.strip():
            raise SDKConfigError("websocket_url is required")
        if self.api_bot_id is not None and not self.api_bot_id.strip():
            raise SDKConfigError("api_bot_id cannot be empty")

    @classmethod
    def from_env(
        cls,
        bot_id_env: str | tuple[str, ...] = DEFAULT_BOT_ID_ENV_KEYS,
        secret_env: str | tuple[str, ...] = DEFAULT_SECRET_ENV_KEYS,
        api_bot_id_env: str | tuple[str, ...] = DEFAULT_API_BOT_ID_ENV_KEYS,
    ) -> "SDKConfig":
        bot_id = cls._first_non_empty_env_value(bot_id_env)
        secret = cls._first_non_empty_env_value(secret_env)
        api_bot_id = cls._first_non_empty_env_value(api_bot_id_env) or None
        return cls(bot_id=bot_id, secret=secret, api_bot_id=api_bot_id)

    @staticmethod
    def _first_non_empty_env_value(keys: str | tuple[str, ...]) -> str:
        env_keys = (keys,) if isinstance(keys, str) else keys
        for env_key in env_keys:
            value = os.getenv(env_key, "")
            if value and value.strip():
                return value
        return ""
