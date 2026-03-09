from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from enum import Enum
from queue import Empty, Queue
from typing import Any

from websocket import WebSocket, WebSocketConnectionClosedException, WebSocketTimeoutException, create_connection

from .config import SDKConfig
from .logging_utils import ensure_redacting_filter, setup_sdk_logger


class LongLinkState(str, Enum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class WecomLongLinkClient:
    _SEND_RETRYABLE_ERRCODES: set[int] = {-1, 408, 429, 500, 502, 503, 504, 93008}

    def __init__(
        self,
        config: SDKConfig,
        logger: logging.Logger | None = None,
        ws_factory: Callable[..., WebSocket] | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or setup_sdk_logger("wechat_longlink_sdk.longlink", secrets=[config.secret])
        ensure_redacting_filter(self.logger, secrets=[config.secret])
        self._ws_factory = ws_factory or create_connection
        self._ws: WebSocket | None = None
        self._state = LongLinkState.STOPPED
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._receive_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._inbox: Queue[dict[str, Any]] = Queue()
        self._response_inbox: Queue[dict[str, Any]] = Queue()
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._last_error: str | None = None
        self._reconnect_attempts = 0
        self._reconnect_lock = threading.Lock()

    @property
    def state(self) -> LongLinkState:
        with self._lock:
            return self._state

    def start(self) -> None:
        with self._lock:
            if self._state in {LongLinkState.CONNECTED, LongLinkState.SUBSCRIBED}:
                return
            self._stop_event.clear()
        self._connect_and_subscribe()
        self._start_background_loops()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            self._state = LongLinkState.STOPPED
            ws = self._ws
            self._ws = None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        for thread in (self._receive_thread, self._heartbeat_thread):
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        with self._response_inbox.mutex:
            self._response_inbox.queue.clear()
        with self._inbox.mutex:
            self._inbox.queue.clear()

    def subscribe(self, wait_response: bool = False) -> dict[str, Any]:
        payload = {
            "cmd": "aibot_subscribe",
            "headers": {"req_id": self._generate_req_id()},
            "body": {
                "bot_id": self.config.bot_id,
                "secret": self.config.secret,
            },
        }
        if self.config.api_bot_id:
            body = payload.get("body")
            if isinstance(body, dict):
                body["aibotid"] = self.config.api_bot_id
        return self.send_command(payload, wait_response=wait_response)

    def aibot_send_msg(
        self,
        content: str,
        chatid: str | None = None,
        userid: str | None = None,
        msgid: str | None = None,
        stream: bool = False,
        finish: bool = True,
        wait_response: bool = True,
        max_attempts: int = 1,
        retry_interval_seconds: float = 0.2,
    ) -> dict[str, Any]:
        data = self._build_send_data(content=content, chatid=chatid, userid=userid, msgid=msgid, stream=stream, finish=finish)
        payload = {"action": "aibot_send_msg", "data": data}
        command_result = self._send_with_retry(
            payload=payload,
            wait_response=wait_response,
            max_attempts=max_attempts,
            retry_interval_seconds=retry_interval_seconds,
        )
        return self._map_send_result(command_result)

    def send_command(
        self,
        payload: Mapping[str, Any],
        wait_response: bool = False,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        protocol_payload = self._to_protocol_payload(payload)
        serialized = json.dumps(protocol_payload, ensure_ascii=False)
        with self._lock:
            ws = self._ws
        if ws is None:
            raise RuntimeError("longlink websocket is not connected")
        ws.send(serialized)
        self.logger.debug("longlink command sent: %s", serialized)
        if not wait_response:
            return {"ok": True, "payload": dict(protocol_payload)}
        parsed = self._wait_response(ws=ws)
        result = self._map_command_result(payload=dict(protocol_payload), response=parsed)
        if raise_on_error and not result["ok"]:
            self._raise_on_error_response(parsed)
        return result

    def register_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)

    def get_next_event(self, timeout_seconds: float = 0.0) -> dict[str, Any] | None:
        try:
            return self._inbox.get(timeout=timeout_seconds)
        except Empty:
            return None

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state.value,
                "reconnect_attempts": self._reconnect_attempts,
                "last_error": self._last_error,
                "connected": self._ws is not None,
            }

    def _connect_and_subscribe(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    self._state = LongLinkState.CONNECTING
                ws = self._ws_factory(self.config.websocket_url, timeout=10)
                with self._lock:
                    self._ws = ws
                    self._state = LongLinkState.CONNECTED
                subscribe_result = self.subscribe(wait_response=True)
                with self._lock:
                    self._state = LongLinkState.SUBSCRIBED
                    self._last_error = None
                    self._reconnect_attempts = 0
                self.logger.info("longlink subscribed, result=%s", subscribe_result)
                return
            except Exception as exc:
                with self._lock:
                    self._reconnect_attempts += 1
                    self._last_error = str(exc)
                    self._state = LongLinkState.RECONNECTING
                if not self._can_retry():
                    with self._lock:
                        self._state = LongLinkState.ERROR
                    raise RuntimeError("failed to establish longlink connection") from exc
                time.sleep(self.config.reconnect_interval_seconds)

    def _can_retry(self) -> bool:
        if self.config.max_reconnect_attempts == 0:
            return True
        return self._reconnect_attempts <= self.config.max_reconnect_attempts

    def _start_background_loops(self) -> None:
        self._receive_thread = threading.Thread(target=self._receive_loop, name="wecom-longlink-recv", daemon=True)
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="wecom-longlink-heartbeat", daemon=True)
        self._receive_thread.start()
        self._heartbeat_thread.start()

    def _receive_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                ws = self._ws
            if ws is None:
                return
            try:
                raw = ws.recv()
            except WebSocketConnectionClosedException:
                self._reconnect()
                continue
            except WebSocketTimeoutException:
                continue
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                self._reconnect()
                continue
            if not raw:
                continue
            parsed = self._parse_event(raw)
            if self._is_callback_event(parsed):
                event = self._to_unified_event(parsed)
                self._inbox.put(event)
                for callback in list(self._callbacks):
                    callback(event)
                continue
            self._response_inbox.put(parsed)

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.config.heartbeat_interval_seconds):
            with self._lock:
                ws = self._ws
            if ws is None:
                return
            try:
                ws.ping()
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                    self._state = LongLinkState.RECONNECTING
                self._reconnect()
                return

    def _reconnect(self) -> None:
        if self._stop_event.is_set():
            return
        if not self._reconnect_lock.acquire(blocking=False):
            return
        with self._lock:
            self._state = LongLinkState.RECONNECTING
            self._reconnect_attempts += 1
            ws = self._ws
            self._ws = None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        try:
            self._connect_and_subscribe()
        finally:
            self._reconnect_lock.release()

    def _parse_event(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return {"raw": parsed}
        except json.JSONDecodeError:
            return {"raw": text}

    def _raise_on_error_response(self, response: Mapping[str, Any]) -> None:
        errcode = response.get("errcode")
        if isinstance(errcode, int) and errcode != 0:
            errmsg = str(response.get("errmsg", "unknown error"))
            raise RuntimeError(f"longlink command failed: errcode={errcode}, errmsg={errmsg}")

    def _map_command_result(self, payload: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
        errcode = response.get("errcode")
        ok = not isinstance(errcode, int) or errcode == 0
        return {"ok": ok, "payload": dict(payload), "response": dict(response)}

    def _map_send_result(self, command_result: Mapping[str, Any]) -> dict[str, Any]:
        response = command_result.get("response")
        response_dict = dict(response) if isinstance(response, Mapping) else None
        errcode = response_dict.get("errcode") if response_dict is not None else 0
        errmsg = response_dict.get("errmsg") if response_dict is not None else "ok"
        return {
            "ok": bool(command_result.get("ok")),
            "action": "aibot_send_msg",
            "attempt": int(command_result.get("attempt", 1)),
            "payload": dict(command_result.get("payload", {})),
            "response": response_dict,
            "errcode": errcode,
            "errmsg": str(errmsg) if errmsg is not None else "",
        }

    def _send_with_retry(
        self,
        payload: Mapping[str, Any],
        wait_response: bool,
        max_attempts: int,
        retry_interval_seconds: float,
    ) -> dict[str, Any]:
        if max_attempts < 1:
            raise ValueError("max_attempts must be greater than or equal to 1")
        if retry_interval_seconds < 0:
            raise ValueError("retry_interval_seconds must be greater than or equal to 0")
        if not wait_response and max_attempts > 1:
            raise ValueError("max_attempts must be 1 when wait_response is False")
        errors: list[dict[str, Any]] = []
        for attempt in range(1, max_attempts + 1):
            try:
                result = self.send_command(payload, wait_response=wait_response, raise_on_error=False)
            except RuntimeError as exc:
                errors.append({"attempt": attempt, "error": str(exc)})
                if attempt >= max_attempts or not self._is_retryable_send_exception(exc):
                    raise RuntimeError(
                        f"aibot_send_msg failed: attempts={attempt}, errors={errors}"
                    ) from exc
                time.sleep(retry_interval_seconds)
                continue
            if result.get("ok", False):
                merged = dict(result)
                merged["attempt"] = attempt
                return merged
            response = result.get("response", {})
            errcode = response.get("errcode") if isinstance(response, Mapping) else None
            errmsg = response.get("errmsg") if isinstance(response, Mapping) else "unknown error"
            errors.append({"attempt": attempt, "errcode": errcode, "errmsg": errmsg})
            if attempt >= max_attempts or not self._is_retryable_send_errcode(errcode):
                raise RuntimeError(
                    f"aibot_send_msg failed: errcode={errcode}, errmsg={errmsg}, attempts={attempt}, errors={errors}"
                )
            time.sleep(retry_interval_seconds)
        raise RuntimeError("aibot_send_msg failed: retry exhausted")

    def _is_retryable_send_exception(self, exc: RuntimeError) -> bool:
        message = str(exc).lower()
        return "timeout" in message or "closed" in message or "not connected" in message

    def _is_retryable_send_errcode(self, errcode: Any) -> bool:
        return isinstance(errcode, int) and errcode in self._SEND_RETRYABLE_ERRCODES

    def _build_send_data(
        self,
        content: str,
        chatid: str | None,
        userid: str | None,
        msgid: str | None,
        stream: bool,
        finish: bool,
    ) -> dict[str, Any]:
        if not content or not content.strip():
            raise ValueError("content is required")
        target = self._normalize_send_target(chatid=chatid, userid=userid)
        data: dict[str, Any] = {
            **target,
            "msgtype": "markdown",
            "markdown": {"content": content},
        }
        if stream:
            data["stream"] = {"finish": finish}
        if msgid is not None:
            clean_msgid = msgid.strip()
            if not clean_msgid:
                raise ValueError("msgid is required")
            data["msgid"] = clean_msgid
        if self.config.api_bot_id:
            data["aibotid"] = self.config.api_bot_id
        return data

    def _normalize_send_target(self, chatid: str | None, userid: str | None) -> dict[str, str]:
        clean_chatid = chatid.strip() if isinstance(chatid, str) else ""
        clean_userid = userid.strip() if isinstance(userid, str) else ""
        if clean_chatid and clean_userid:
            raise ValueError("chatid and userid cannot both be provided")
        if not clean_chatid and not clean_userid:
            raise ValueError("chatid or userid is required")
        if clean_chatid:
            return {"chatid": clean_chatid}
        return {"userid": clean_userid}

    def _wait_response(self, ws: WebSocket) -> dict[str, Any]:
        receive_thread_running = self._receive_thread is not None and self._receive_thread.is_alive()
        if receive_thread_running:
            try:
                return self._response_inbox.get(timeout=5.0)
            except Empty as exc:
                raise RuntimeError("longlink command response timeout") from exc
        try:
            raw = ws.recv()
        except WebSocketTimeoutException as exc:
            raise RuntimeError("longlink command response timeout") from exc
        parsed = self._parse_event(raw)
        if self._is_callback_event(parsed):
            event = self._to_unified_event(parsed)
            self._inbox.put(event)
            for callback in list(self._callbacks):
                callback(event)
            raise RuntimeError("longlink command response missing, received callback event")
        return parsed

    def _is_callback_event(self, payload: Mapping[str, Any]) -> bool:
        cmd = payload.get("cmd")
        action = payload.get("action")
        event = payload.get("event")
        event_name = (
            cmd
            if isinstance(cmd, str) and cmd
            else action
            if isinstance(action, str) and action
            else event
            if isinstance(event, str)
            else ""
        )
        return event_name in {"aibot_msg_callback", "aibot_event_callback"}

    def _to_unified_event(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        cmd = payload.get("cmd")
        action = payload.get("action")
        event = payload.get("event")
        event_name = (
            cmd
            if isinstance(cmd, str) and cmd
            else action
            if isinstance(action, str) and action
            else str(event or "")
        )
        data = payload.get("data")
        body = payload.get("body")
        source = data if isinstance(data, Mapping) else body if isinstance(body, Mapping) else payload
        msgid = source.get("msgid") or payload.get("msgid")
        chatid = source.get("chatid") or payload.get("chatid")
        source_from = source.get("from")
        payload_from = payload.get("from")
        source_from_dict = source_from if isinstance(source_from, Mapping) else {}
        payload_from_dict = payload_from if isinstance(payload_from, Mapping) else {}
        userid = (
            source_from_dict.get("userid")
            or source.get("userid")
            or payload_from_dict.get("userid")
            or payload.get("userid")
        )
        aibotid = source.get("aibotid") or payload.get("aibotid")
        unified_event = {
            "event": event_name,
            "event_type": "message" if event_name == "aibot_msg_callback" else "event",
            "msgid": msgid,
            "chatid": chatid,
            "userid": userid,
            "aibotid": aibotid,
            "raw": dict(payload),
        }
        for key, value in payload.items():
            if key not in unified_event:
                unified_event[key] = value
        return unified_event

    def _to_protocol_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload_dict = dict(payload)
        if "cmd" in payload_dict:
            return payload_dict
        action = payload_dict.get("action")
        if not isinstance(action, str) or not action:
            return payload_dict
        headers = payload_dict.get("headers")
        headers_dict = dict(headers) if isinstance(headers, Mapping) else {}
        headers_dict.setdefault("req_id", self._generate_req_id())
        if "body" in payload_dict and isinstance(payload_dict.get("body"), Mapping):
            body: Any = dict(payload_dict["body"])
        elif "data" in payload_dict and isinstance(payload_dict.get("data"), Mapping):
            body = dict(payload_dict["data"])
        else:
            body = {
                key: value
                for key, value in payload_dict.items()
                if key not in {"action", "headers", "body", "data"}
            }
        return {"cmd": action, "headers": headers_dict, "body": body}

    def _generate_req_id(self) -> str:
        return uuid.uuid4().hex
