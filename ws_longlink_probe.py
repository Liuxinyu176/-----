from __future__ import annotations

import json
import logging
from pathlib import Path
import signal
import sys
import time
from collections.abc import Mapping
from typing import Any

from wechat_longlink_sdk import (
    DEFAULT_API_BOT_ID_ENV_KEYS,
    DEFAULT_BOT_ID_ENV_KEYS,
    DEFAULT_SECRET_ENV_KEYS,
    SDKConfig,
    WecomLongLinkClient,
)

PROBE_LOCAL_CONFIG_PATH = Path(__file__).with_name("ws_longlink_probe.local.json")


def _build_probe_logger() -> logging.Logger:
    logger = logging.getLogger("ws_longlink_probe")
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


def _read_local_probe_config() -> dict[str, Any]:
    if not PROBE_LOCAL_CONFIG_PATH.exists():
        return {}
    raw_content = PROBE_LOCAL_CONFIG_PATH.read_text(encoding="utf-8")
    if not raw_content.strip():
        return {}
    parsed = json.loads(raw_content)
    if not isinstance(parsed, dict):
        raise RuntimeError("ws_longlink_probe.local.json must be a JSON object")
    return parsed


def _as_non_empty_string(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _resolve_config() -> SDKConfig:
    local_config = _read_local_probe_config()
    bot_id = SDKConfig._first_non_empty_env_value(DEFAULT_BOT_ID_ENV_KEYS) or _as_non_empty_string(local_config.get("bot_id"))
    secret = SDKConfig._first_non_empty_env_value(DEFAULT_SECRET_ENV_KEYS) or _as_non_empty_string(local_config.get("secret"))
    api_bot_id_raw = SDKConfig._first_non_empty_env_value(DEFAULT_API_BOT_ID_ENV_KEYS) or _as_non_empty_string(
        local_config.get("api_bot_id")
    )
    api_bot_id = api_bot_id_raw or None
    websocket_url = _as_non_empty_string(local_config.get("websocket_url")) or "wss://openws.work.weixin.qq.com"
    heartbeat_interval_seconds = float(local_config.get("heartbeat_interval_seconds", 30.0))
    reconnect_interval_seconds = float(local_config.get("reconnect_interval_seconds", 5.0))
    max_reconnect_attempts = int(local_config.get("max_reconnect_attempts", 0))
    return SDKConfig(
        bot_id=bot_id,
        secret=secret,
        api_bot_id=api_bot_id,
        websocket_url=websocket_url,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        reconnect_interval_seconds=reconnect_interval_seconds,
        max_reconnect_attempts=max_reconnect_attempts,
    )


def _pick_from_payload(payload: Mapping[str, Any], field: str) -> Any:
    data = payload.get("data")
    body = payload.get("body")
    if isinstance(data, Mapping) and field in data:
        return data.get(field)
    if isinstance(body, Mapping) and field in body:
        return body.get(field)
    return payload.get(field)


def _extract_text(payload: Mapping[str, Any]) -> str:
    text_container = _pick_from_payload(payload, "text")
    if isinstance(text_container, Mapping):
        content = text_container.get("content")
        if isinstance(content, str):
            return content
    return ""


def _is_text_message(event: Mapping[str, Any]) -> bool:
    if event.get("event") != "aibot_msg_callback":
        return False
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return False
    return _pick_from_payload(raw, "msgtype") == "text"


def _event_name_from_payload(payload: Mapping[str, Any]) -> str:
    event_name = _pick_from_payload(payload, "event")
    if isinstance(event_name, str):
        return event_name
    if isinstance(event_name, Mapping):
        nested_event_type = event_name.get("eventtype")
        if isinstance(nested_event_type, str):
            return nested_event_type
    event_type = _pick_from_payload(payload, "event_type")
    if isinstance(event_type, str):
        return event_type
    return ""


def _normalized_event_name(event: Mapping[str, Any]) -> str:
    event_name = event.get("event_name")
    if isinstance(event_name, str) and event_name.strip():
        return event_name.strip().lower()
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return ""
    return _event_name_from_payload(raw).lower()


def _is_enter_chat_event(event: Mapping[str, Any]) -> bool:
    if event.get("event") != "aibot_event_callback":
        return False
    event_name = _normalized_event_name(event)
    return "enter_chat" in event_name


def _is_disconnected_event(event: Mapping[str, Any]) -> bool:
    if event.get("event") != "aibot_event_callback":
        return False
    event_name = _normalized_event_name(event)
    return "disconnected_event" in event_name


def _is_template_card_event(event: Mapping[str, Any]) -> bool:
    if event.get("event") != "aibot_event_callback":
        return False
    event_name = _normalized_event_name(event)
    return "template_card_event" in event_name


def _is_feedback_event(event: Mapping[str, Any]) -> bool:
    if event.get("event") != "aibot_event_callback":
        return False
    event_name = _normalized_event_name(event)
    return "feedback_event" in event_name


def _extract_req_id(payload: Mapping[str, Any]) -> str:
    headers = payload.get("headers")
    if not isinstance(headers, Mapping):
        return ""
    req_id = headers.get("req_id")
    if isinstance(req_id, str):
        return req_id
    return ""


def _echo_target(event: Mapping[str, Any]) -> tuple[str | None, str | None]:
    chatid = event.get("chatid")
    userid = event.get("userid")
    chatid_value = chatid if isinstance(chatid, str) and chatid.strip() else None
    userid_value = userid if isinstance(userid, str) and userid.strip() else None
    if chatid_value:
        return chatid_value, None
    if userid_value:
        return None, userid_value
    return None, None


def _reply_welcome(client: WecomLongLinkClient, event: Mapping[str, Any]) -> None:
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return
    req_id = _extract_req_id(raw)
    if not req_id:
        print("进入会话事件缺少 req_id，跳过欢迎语回复")
        return
    welcome_payload = {
        "cmd": "aibot_respond_welcome_msg",
        "headers": {"req_id": req_id},
        "body": {
            "msgtype": "text",
            "text": {"content": "你好，我已上线，可以直接向我提问。"},
        },
    }
    welcome_result = client.send_command(welcome_payload, wait_response=True, raise_on_error=False)
    if welcome_result.get("ok"):
        print("欢迎语回复成功")
        return
    response = welcome_result.get("response")
    if isinstance(response, Mapping):
        print(f"欢迎语回复失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
        return
    print("欢迎语回复失败")


def _reply_text_message(client: WecomLongLinkClient, event: Mapping[str, Any]) -> None:
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return
    text_content = _extract_text(raw)
    req_id = _extract_req_id(raw)
    msgid = event.get("msgid")
    chatid = event.get("chatid")
    userid = event.get("userid")
    target_label = f"chatid={chatid}" if isinstance(chatid, str) and chatid.strip() else f"userid={userid}"
    print(f"收到文本消息: {target_label}, content={text_content or '空文本'}")
    target_chatid, target_userid = _echo_target(event)
    if not target_chatid and not target_userid:
        print("无法确定回复目标，跳过回复")
        return
    if not target_chatid:
        if not req_id:
            print("缺少 req_id，无法通过应答接口回复单聊消息")
            return
        respond_payload = {
            "cmd": "aibot_respond_msg",
            "headers": {"req_id": req_id},
            "body": {
                "msgtype": "markdown",
                "markdown": {"content": f"已收到：{text_content or '空文本'}"},
            },
        }
        try:
            respond_result = client.send_command(respond_payload, wait_response=True, raise_on_error=False)
        except Exception as exc:
            print("应答接口回复失败:", str(exc))
            return
        if respond_result.get("ok"):
            print("应答接口回复成功")
            return
        response = respond_result.get("response")
        if isinstance(response, Mapping):
            print(f"应答接口回复失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
            return
        print("应答接口回复失败")
        return
    try:
        reply_result = client.aibot_send_msg(
            content=f"已收到：{text_content or '空文本'}",
            chatid=target_chatid,
            userid=target_userid,
            msgid=msgid if isinstance(msgid, str) and msgid.strip() else None,
            stream=False,
            finish=True,
            wait_response=True,
        )
    except Exception as exc:
        print("最小回复失败:", str(exc))
        return
    if reply_result.get("ok"):
        print("消息发送成功")
        return
    response = reply_result.get("response")
    if isinstance(response, Mapping):
        print(f"消息发送失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
        return
    print("消息发送失败")


def process_event(client: WecomLongLinkClient, event: Mapping[str, Any]) -> None:
    handled = False
    if _is_enter_chat_event(event):
        print("收到 enter_chat 事件")
        _reply_welcome(client, event)
        handled = True
    if _is_disconnected_event(event):
        print("收到 disconnected_event：当前 BotID 连接已失效，通常是被同 BotID 的新连接顶掉")
        handled = True
    if _is_template_card_event(event):
        print("收到 template_card_event 事件")
        handled = True
    if _is_feedback_event(event):
        print("收到 feedback_event 事件")
        handled = True
    if _is_text_message(event):
        _reply_text_message(client, event)
        handled = True
    if not handled:
        raw = event.get("raw")
        if isinstance(raw, Mapping):
            event_name = _event_name_from_payload(raw)
            if event_name:
                print(f"忽略事件: {event_name}")


def run() -> None:
    config = _resolve_config()
    logger = _build_probe_logger()
    client = WecomLongLinkClient(config, logger=logger)
    stopped = False

    def _stop(*_: Any) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    print(f"正在连接: {config.websocket_url}")
    client.start()
    print("连接成功，订阅成功，等待消息回调")
    try:
        while not stopped:
            event = client.get_next_event(timeout_seconds=1.0)
            if event is None:
                continue
            process_event(client, event)
    finally:
        client.stop()
        print("已优雅断开长连接")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("运行失败:", str(exc))
        sys.exit(1)
