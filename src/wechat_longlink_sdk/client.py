from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping

from .api_client import DocumentAPIClient
from .config import SDKConfig
from .logging_utils import ensure_redacting_filter, setup_sdk_logger
from .messages import BaseMessage, MessageType, message_from_payload


class SessionState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    STOPPING = "stopping"
    ERROR = "error"


class BotClient:
    def __init__(
        self,
        config: SDKConfig,
        logger: logging.Logger | None = None,
        connect_handler: Callable[[], None] | None = None,
        authenticate_handler: Callable[[str, str], str] | None = None,
        heartbeat_handler: Callable[[str], None] | None = None,
        send_handler: Callable[[str, BaseMessage], Mapping[str, Any] | None] | None = None,
        receive_callback: Callable[[BaseMessage], None] | None = None,
        api_client: DocumentAPIClient | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or setup_sdk_logger("wechat_longlink_sdk", secrets=[config.secret])
        ensure_redacting_filter(self.logger, secrets=[config.secret])
        self._connect_handler = connect_handler or self._default_connect
        self._authenticate_handler = authenticate_handler or self._default_authenticate
        self._heartbeat_handler = heartbeat_handler or self._default_heartbeat
        self._send_handler = send_handler or self._default_send
        self._receive_callback = receive_callback or self._default_receive
        self._api_client = api_client or DocumentAPIClient()
        self._receive_type_callbacks: dict[MessageType, list[Callable[[BaseMessage], None]]] = {
            message_type: [] for message_type in MessageType
        }
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._running = False
        self._state = SessionState.STOPPED
        self._connected = False
        self._authenticated = False
        self._session_id: str | None = None
        self._heartbeat_count = 0
        self._reconnect_attempts = 0
        self._last_connected_at: float | None = None
        self._last_heartbeat_at: float | None = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    @property
    def is_authenticated(self) -> bool:
        with self._lock:
            return self._authenticated

    @property
    def session_state(self) -> SessionState:
        with self._lock:
            return self._state

    @property
    def session_id(self) -> str | None:
        with self._lock:
            return self._session_id

    def start(self) -> None:
        with self._lock:
            if self._running:
                self.logger.info("bot client already running, bot_id=%s", self.config.bot_id)
                return
            self._running = True
            self._state = SessionState.STARTING
            self._stop_event.clear()
            self._session_id = None
            self._authenticated = False
            self._connected = False
            self._heartbeat_count = 0
            self._reconnect_attempts = 0
            self._last_connected_at = None
            self._last_heartbeat_at = None
            self._last_error = None
        self.logger.info("bot client starting, bot_id=%s", self.config.bot_id)
        self._connect_and_authenticate()
        self._start_heartbeat_loop()

    def stop(self) -> None:
        heartbeat_thread: threading.Thread | None = None
        with self._lock:
            if not self._running and self._state == SessionState.STOPPED:
                return
            self._state = SessionState.STOPPING
            self._running = False
            self._stop_event.set()
            heartbeat_thread = self._heartbeat_thread
            self._heartbeat_thread = None
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=max(self.config.heartbeat_interval_seconds, 1.0) + 1.0)
        with self._lock:
            self._connected = False
            self._authenticated = False
            self._session_id = None
            self._state = SessionState.STOPPED
        self.logger.info("bot client stopping, bot_id=%s", self.config.bot_id)

    def get_status(self) -> dict[str, object]:
        with self._lock:
            return {
                "running": self._running,
                "state": self._state.value,
                "connected": self._connected,
                "authenticated": self._authenticated,
                "session_id": self._session_id,
                "heartbeat_count": self._heartbeat_count,
                "reconnect_attempts": self._reconnect_attempts,
                "last_connected_at": self._format_time(self._last_connected_at),
                "last_heartbeat_at": self._format_time(self._last_heartbeat_at),
                "last_error": self._last_error,
            }

    def send_message(self, message: BaseMessage) -> dict[str, object]:
        with self._lock:
            if not self._running or not self._authenticated or not self._session_id:
                raise RuntimeError("bot client is not connected and authenticated")
            session_id = self._session_id
        try:
            handler_response = self._send_handler(session_id, message)
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise
        response_payload = dict(handler_response or {})
        response_payload.setdefault("ok", True)
        response_payload.setdefault("session_id", session_id)
        response_payload.setdefault("message_id", message.message_id)
        response_payload.setdefault("message_type", message.message_type.value)
        return response_payload

    def subscribe_message(
        self,
        message_type: MessageType,
        callback: Callable[[BaseMessage], None],
    ) -> None:
        with self._lock:
            self._receive_type_callbacks[message_type].append(callback)

    def handle_incoming(self, payload: Mapping[str, Any] | BaseMessage) -> BaseMessage:
        incoming_message = payload if isinstance(payload, BaseMessage) else message_from_payload(payload)
        self._receive_callback(incoming_message)
        with self._lock:
            callbacks = list(self._receive_type_callbacks[incoming_message.message_type])
        for callback in callbacks:
            callback(incoming_message)
        return incoming_message

    def list_supported_apis(self) -> list[str]:
        return self._api_client.list_apis()

    def call_api(self, api_name: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if not self._running or not self._authenticated or not self._session_id:
                raise RuntimeError("bot client is not connected and authenticated")
            session_id = self._session_id
        return self._api_client.call_api(api_name=api_name, params=params, session_id=session_id)

    def _connect_and_authenticate(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    self._state = SessionState.CONNECTING
                self._connect_handler()
                with self._lock:
                    self._connected = True
                    self._last_connected_at = time.time()
                    self._state = SessionState.AUTHENTICATING
                session_id = self._authenticate_handler(self.config.bot_id, self.config.secret)
                if not session_id or not session_id.strip():
                    raise RuntimeError("authenticate returned empty session id")
                with self._lock:
                    self._session_id = session_id
                    self._authenticated = True
                    self._state = SessionState.CONNECTED
                self.logger.info("bot client connected and authenticated, bot_id=%s", self.config.bot_id)
                return
            except Exception as exc:
                with self._lock:
                    self._connected = False
                    self._authenticated = False
                    self._session_id = None
                    self._last_error = str(exc)
                self.logger.warning("connection/auth failed, bot_id=%s error=%s", self.config.bot_id, exc)
                if not self._schedule_reconnect():
                    with self._lock:
                        self._running = False
                        self._state = SessionState.ERROR
                    raise RuntimeError("failed to establish session after reconnect attempts") from exc

    def _schedule_reconnect(self) -> bool:
        with self._lock:
            self._reconnect_attempts += 1
            max_reconnect_attempts = self.config.max_reconnect_attempts
            allow_retry = max_reconnect_attempts == 0 or self._reconnect_attempts <= max_reconnect_attempts
            if allow_retry:
                self._state = SessionState.RECONNECTING
        if not allow_retry or self._stop_event.is_set():
            return False
        self.logger.info(
            "reconnecting after %.2fs, attempt=%s",
            self.config.reconnect_interval_seconds,
            self._reconnect_attempts,
        )
        interrupted = self._stop_event.wait(self.config.reconnect_interval_seconds)
        return not interrupted

    def _start_heartbeat_loop(self) -> None:
        with self._lock:
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                return
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                name="wechat-longlink-heartbeat",
                daemon=True,
            )
            self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.config.heartbeat_interval_seconds):
            with self._lock:
                if not self._running:
                    return
                session_id = self._session_id
            if not session_id:
                continue
            try:
                self._heartbeat_handler(session_id)
                with self._lock:
                    self._heartbeat_count += 1
                    self._last_heartbeat_at = time.time()
                    if self._state != SessionState.CONNECTED:
                        self._state = SessionState.CONNECTED
                self.logger.debug("heartbeat success, session_id=%s", session_id)
            except Exception as exc:
                with self._lock:
                    self._connected = False
                    self._authenticated = False
                    self._session_id = None
                    self._last_error = str(exc)
                self.logger.warning("heartbeat failed, bot_id=%s error=%s", self.config.bot_id, exc)
                try:
                    self._connect_and_authenticate()
                except RuntimeError:
                    return

    def _default_connect(self) -> None:
        return None

    def _default_authenticate(self, bot_id: str, secret: str) -> str:
        return f"{bot_id}-{uuid.uuid4().hex}"

    def _default_heartbeat(self, session_id: str) -> None:
        return None

    def _default_send(self, session_id: str, message: BaseMessage) -> Mapping[str, Any] | None:
        return {
            "ok": True,
            "session_id": session_id,
            "message_id": message.message_id,
            "message_type": message.message_type.value,
        }

    def _default_receive(self, message: BaseMessage) -> None:
        return None

    def _format_time(self, timestamp: float | None) -> str | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
