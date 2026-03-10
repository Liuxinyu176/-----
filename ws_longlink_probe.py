from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import uuid
from pathlib import Path
import signal
import sys
import time
import urllib.parse
import urllib.request
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


def _resolve_media_upload_credentials() -> tuple[str, str]:
    local_config = _read_local_probe_config()
    corp_id = os.environ.get("WECOM_CORP_ID", "").strip() or _as_non_empty_string(local_config.get("wecom_corp_id"))
    corp_secret = os.environ.get("WECOM_CORP_SECRET", "").strip() or _as_non_empty_string(local_config.get("wecom_corp_secret"))
    return corp_id, corp_secret


def _get_wecom_access_token(corp_id: str, corp_secret: str) -> str:
    query = urllib.parse.urlencode({"corpid": corp_id, "corpsecret": corp_secret})
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?{query}"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        raise RuntimeError(f"获取 access_token 失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("获取 access_token 失败: 响应不是 JSON 对象")
    if payload.get("errcode") != 0:
        raise RuntimeError(f"获取 access_token 失败: errcode={payload.get('errcode')}, errmsg={payload.get('errmsg')}")
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("获取 access_token 失败: 缺少 access_token")
    return token


def _build_multipart_form_data(field_name: str, filename: str, content_type: str, content: bytes, boundary: str) -> bytes:
    boundary_bytes = boundary.encode("utf-8")
    header = (
        b"--"
        + boundary_bytes
        + b"\r\n"
        + f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        + f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    )
    footer = b"\r\n--" + boundary_bytes + b"--\r\n"
    return header + content + footer


def _wecom_upload_media(access_token: str, media_type: str, filename: str, content: bytes) -> str:
    boundary = f"----wechat-longlink-probe-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body = _build_multipart_form_data("media", filename, content_type, content, boundary)
    url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={urllib.parse.quote(access_token)}&type={urllib.parse.quote(media_type)}"
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        raise RuntimeError(f"上传素材失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("上传素材失败: 响应不是 JSON 对象")
    if payload.get("errcode") not in (0, None):
        raise RuntimeError(f"上传素材失败: errcode={payload.get('errcode')}, errmsg={payload.get('errmsg')}")
    media_id = payload.get("media_id")
    if not isinstance(media_id, str) or not media_id:
        raise RuntimeError("上传素材失败: 缺少 media_id")
    return media_id


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


def _extract_voice_text(payload: Mapping[str, Any]) -> str:
    voice_container = _pick_from_payload(payload, "voice")
    if isinstance(voice_container, Mapping):
        content = voice_container.get("content")
        if isinstance(content, str):
            return content
    return ""


def _extract_msgtype(payload: Mapping[str, Any]) -> str:
    msgtype = _pick_from_payload(payload, "msgtype")
    if isinstance(msgtype, str):
        return msgtype.strip().lower()
    return ""


def _is_text_message(event: Mapping[str, Any]) -> bool:
    if event.get("event") != "aibot_msg_callback":
        return False
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return False
    return _extract_msgtype(raw) == "text"


def _is_message_callback(event: Mapping[str, Any]) -> bool:
    return event.get("event") == "aibot_msg_callback"


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


def _reply_markdown(client: WecomLongLinkClient, event: Mapping[str, Any], content: str) -> None:
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return
    req_id = _extract_req_id(raw)
    msgid = event.get("msgid")
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
                "markdown": {"content": content},
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
            content=content,
            chatid=target_chatid,
            userid=target_userid,
            msgid=msgid if isinstance(msgid, str) and msgid.strip() else None,
            stream=False,
            finish=True,
            wait_response=True,
        )
    except Exception as exc:
        print("消息发送失败:", str(exc))
        return
    if reply_result.get("ok"):
        print("消息发送成功")
        return
    response = reply_result.get("response")
    if isinstance(response, Mapping):
        print(f"消息发送失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
        return
    print("消息发送失败")


def _reply_image(client: WecomLongLinkClient, event: Mapping[str, Any], media_id: str, url: str) -> None:
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return
    req_id = _extract_req_id(raw)
    msgid = event.get("msgid")
    target_chatid, target_userid = _echo_target(event)
    if not target_chatid and not target_userid:
        print("无法确定回复目标，跳过图片回复")
        return
    try:
        image_payload: dict[str, Any] = {}
        if media_id:
            image_payload["media_id"] = media_id
        if url:
            image_payload["url"] = url
        if not image_payload:
            print("图片缺少 media_id/url，跳过图片重发")
            return
        reply_result = client.aibot_send_msg(
            chatid=target_chatid,
            userid=target_userid,
            msgid=msgid if isinstance(msgid, str) and msgid.strip() else None,
            msgtype="image",
            image=image_payload,
            wait_response=True,
        )
    except Exception as exc:
        print("图片重发失败:", str(exc))
        if target_userid and req_id:
            _reply_markdown(client, event, "图片发送失败，已降级为文本提示。")
        return
    if reply_result.get("ok"):
        print("图片重发成功")
        return
    response = reply_result.get("response")
    if isinstance(response, Mapping):
        print(f"图片重发失败: errcode={response.get('errcode')}, errmsg={response.get('errmsg')}")
        if response.get("errcode") == 40008:
            _reply_markdown(client, event, "当前通道不支持发送图片，已降级为文本提示。")
        return
    print("图片重发失败")


def _extract_image_media_id_and_url(data: Mapping[str, Any]) -> tuple[str, str]:
    media_id = data.get("media_id")
    if not isinstance(media_id, str) or not media_id.strip():
        media_id = data.get("file_id")
    media_id_value = media_id.strip() if isinstance(media_id, str) and media_id.strip() else ""
    url_candidates = [data.get("url"), data.get("image_url")]
    image_obj = data.get("image")
    if isinstance(image_obj, Mapping):
        url_candidates.extend([image_obj.get("url"), image_obj.get("image_url")])
    url_value = ""
    for candidate in url_candidates:
        cleaned = _sanitize_url(candidate)
        if cleaned:
            url_value = cleaned
            break
    return media_id_value, url_value


def _extract_image_aeskey(data: Mapping[str, Any]) -> str:
    candidates: list[Any] = [data.get("aeskey")]
    image_obj = data.get("image")
    if isinstance(image_obj, Mapping):
        candidates.append(image_obj.get("aeskey"))
    file_obj = data.get("file")
    if isinstance(file_obj, Mapping):
        candidates.append(file_obj.get("aeskey"))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _download_bytes(url: str, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                part = response.read(64 * 1024)
                if not part:
                    break
                chunks.append(part)
                total += len(part)
                if total > max_bytes:
                    raise RuntimeError("文件过大")
            return b"".join(chunks)
    except Exception as exc:
        raise RuntimeError(f"下载失败: {exc}") from exc


def _decrypt_media_bytes(cipher_bytes: bytes, aes_key: str) -> bytes:
    if not aes_key:
        return cipher_bytes
    decrypted = _decrypt_file_bytes(cipher_bytes, aes_key)
    return decrypted or b""


def _try_upload_and_send_image(client: WecomLongLinkClient, event: Mapping[str, Any], url: str, aes_key: str) -> bool:
    corp_id, corp_secret = _resolve_media_upload_credentials()
    if not corp_id or not corp_secret:
        return False
    try:
        cipher_bytes = _download_bytes(url)
        plain_bytes = _decrypt_media_bytes(cipher_bytes, aes_key)
        if not plain_bytes:
            raise RuntimeError("解密失败或结果为空")
        access_token = _get_wecom_access_token(corp_id, corp_secret)
        media_id = _wecom_upload_media(access_token, "image", "image.jpg", plain_bytes)
    except Exception as exc:
        print("图片上传换取 media_id 失败:", str(exc))
        return False
    _reply_image(client, event, media_id, "")
    return True


def _to_preview_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, Mapping):
        content = value.get("content")
        if isinstance(content, str):
            return content
    if value is None:
        return ""
    return str(value)


def _extract_file_name_and_preview(data: Mapping[str, Any]) -> tuple[str, str]:
    filename_candidates = (
        data.get("filename"),
        data.get("file_name"),
        data.get("name"),
    )
    filename = ""
    for candidate in filename_candidates:
        if isinstance(candidate, str) and candidate.strip():
            filename = candidate.strip()
            break
    file_obj = data.get("file")
    if not filename and isinstance(file_obj, Mapping):
        file_name_nested = file_obj.get("name")
        if isinstance(file_name_nested, str) and file_name_nested.strip():
            filename = file_name_nested.strip()
    if not filename and isinstance(file_obj, Mapping):
        file_name_nested = file_obj.get("filename")
        if isinstance(file_name_nested, str) and file_name_nested.strip():
            filename = file_name_nested.strip()
    content_candidates = (
        data.get("content"),
        data.get("file_content"),
        data.get("text"),
        data.get("file_text"),
    )
    preview_source = ""
    for candidate in content_candidates:
        preview_source = _to_preview_text(candidate)
        if preview_source:
            break
    if not preview_source and isinstance(file_obj, Mapping):
        preview_source = _to_preview_text(file_obj.get("content"))
    preview = preview_source[:10]
    fallback_name_candidates = (
        data.get("file_id"),
        data.get("media_id"),
    )
    for candidate in fallback_name_candidates:
        if isinstance(candidate, str) and candidate.strip():
            return filename or candidate.strip(), preview
    return filename or "unknown", preview


def _sanitize_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip().strip("`").strip().strip("'\"")
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return ""


def _fallback_filename_from_url(data: Mapping[str, Any]) -> str:
    file_obj = data.get("file")
    url_candidates = [data.get("url"), data.get("file_url"), data.get("download_url")]
    if isinstance(file_obj, Mapping):
        url_candidates.extend([file_obj.get("url"), file_obj.get("file_url"), file_obj.get("download_url")])
    for candidate in url_candidates:
        cleaned = _sanitize_url(candidate)
        if not cleaned:
            continue
        parsed = urllib.parse.urlparse(cleaned)
        name = Path(parsed.path).name
        if name:
            return name
    return ""


def _download_file_preview(data: Mapping[str, Any]) -> str:
    url_candidates = (
        data.get("file_url"),
        data.get("url"),
        data.get("download_url"),
        data.get("media_url"),
    )
    file_obj = data.get("file")
    if isinstance(file_obj, Mapping):
        url_candidates = (
            *url_candidates,
            file_obj.get("url"),
            file_obj.get("download_url"),
            file_obj.get("file_url"),
        )
    download_url = ""
    for candidate in url_candidates:
        cleaned = _sanitize_url(candidate)
        if cleaned:
            download_url = cleaned
            break
    if not download_url:
        return ""
    try:
        with urllib.request.urlopen(download_url, timeout=8) as response:
            raw_bytes = response.read(4096)
    except Exception as exc:
        print("文件下载失败:", str(exc))
        return ""
    if not raw_bytes:
        return ""
    file_obj = data.get("file")
    aes_key = ""
    if isinstance(file_obj, Mapping):
        aes_key_raw = file_obj.get("aeskey")
        if isinstance(aes_key_raw, str):
            aes_key = aes_key_raw.strip()
    if aes_key:
        decrypted_bytes = _decrypt_file_bytes(raw_bytes, aes_key)
        if decrypted_bytes:
            raw_bytes = decrypted_bytes
    return _extract_text_preview_from_bytes(raw_bytes)


def _extract_text_preview_from_bytes(raw_bytes: bytes) -> str:
    if not raw_bytes:
        return ""
    printable_count = sum(1 for ch in raw_bytes if 32 <= ch <= 126 or ch in (9, 10, 13))
    if printable_count / len(raw_bytes) < 0.6:
        return ""
    return raw_bytes.decode("utf-8", errors="ignore")[:10]


def _decode_aes_key(key: str) -> bytes:
    normalized = key.strip().replace("-", "+").replace("_", "/")
    padded = normalized + "=" * ((4 - len(normalized) % 4) % 4)
    return base64.b64decode(padded)


def _pkcs7_unpad(raw_bytes: bytes) -> bytes:
    if not raw_bytes:
        return raw_bytes
    pad = raw_bytes[-1]
    if pad <= 0:
        return raw_bytes
    for block_size in (32, 16):
        if pad > block_size:
            continue
        if len(raw_bytes) < pad:
            continue
        if raw_bytes[-pad:] == bytes([pad]) * pad:
            return raw_bytes[:-pad]
    return raw_bytes


def _decrypt_file_bytes(cipher_bytes: bytes, aes_key: str) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception:
        print("缺少 cryptography 依赖，无法解密文件内容")
        return b""
    try:
        key_bytes = _decode_aes_key(aes_key)
    except Exception as exc:
        print("AESKey 解析失败:", str(exc))
        return b""
    if len(key_bytes) != 32:
        print("AESKey 长度异常，期望 32 字节")
        return b""
    iv = key_bytes[:16]
    try:
        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_plain = decryptor.update(cipher_bytes) + decryptor.finalize()
        return _pkcs7_unpad(padded_plain)
    except Exception as exc:
        print("文件解密失败:", str(exc))
        return b""


def _extract_message_data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    data = payload.get("data")
    if isinstance(data, Mapping):
        return data
    body = payload.get("body")
    if isinstance(body, Mapping):
        return body
    return payload


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
    chatid = event.get("chatid")
    userid = event.get("userid")
    target_label = f"chatid={chatid}" if isinstance(chatid, str) and chatid.strip() else f"userid={userid}"
    print(f"收到文本消息: {target_label}, content={text_content or '空文本'}")
    _reply_markdown(client, event, f"已收到：{text_content or '空文本'}")


def _reply_voice_message(client: WecomLongLinkClient, event: Mapping[str, Any]) -> None:
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return
    voice_content = _extract_voice_text(raw)
    chatid = event.get("chatid")
    userid = event.get("userid")
    target_label = f"chatid={chatid}" if isinstance(chatid, str) and chatid.strip() else f"userid={userid}"
    print(f"收到语音消息: {target_label}, content={voice_content or '空内容'}")
    _reply_markdown(client, event, f"收到语音转写：{voice_content or '空内容'}")


def _handle_non_text_message(client: WecomLongLinkClient, event: Mapping[str, Any]) -> None:
    raw = event.get("raw")
    if not isinstance(raw, Mapping):
        return
    msgtype = _extract_msgtype(raw)
    if not msgtype or msgtype == "text":
        return
    data = _extract_message_data(raw)
    if msgtype == "image":
        media_id, url = _extract_image_media_id_and_url(data)
        print(f"收到图片消息: media_id={media_id or 'none'}, url={'yes' if url else 'no'}")
        if media_id:
            _reply_image(client, event, media_id, "")
            return
        if url:
            aes_key = _extract_image_aeskey(data)
            if _try_upload_and_send_image(client, event, url, aes_key):
                return
            _reply_markdown(
                client,
                event,
                "收到图片消息但缺少 media_id。该 url 为加密下载链接，需要配置 WECOM_CORP_ID/WECOM_CORP_SECRET 上传换取 media_id 才能发图。",
            )
            return
        _reply_markdown(client, event, "收到图片消息但缺少 media_id/url，无法重发。")
        return
    if msgtype == "voice":
        _reply_voice_message(client, event)
        return
    if msgtype == "file":
        filename, preview = _extract_file_name_and_preview(data)
        file_id = data.get("file_id")
        if filename == "unknown":
            url_fallback_name = _fallback_filename_from_url(data)
            if url_fallback_name:
                filename = url_fallback_name
        if not preview:
            preview = _download_file_preview(data)
        if not preview:
            preview = "加密或二进制文件，无法直接读取"
        print(f"收到文件消息: filename={filename}, file_id={file_id}")
        _reply_markdown(client, event, f"文件名：{filename}，前10字符：{preview}")
        return
    if msgtype == "template_card":
        card_type = ""
        template_card = data.get("template_card")
        if isinstance(template_card, Mapping):
            card_type_raw = template_card.get("card_type")
            if isinstance(card_type_raw, str):
                card_type = card_type_raw
        print(f"收到模板卡片消息: card_type={card_type or 'unknown'}")
        _reply_markdown(client, event, "已收到卡片交互消息，正在处理。")
        return
    print(f"收到非文本消息: msgtype={msgtype}")
    _reply_markdown(client, event, f"已收到 {msgtype} 消息，正在处理。")


def _print_event_json(event: Mapping[str, Any]) -> None:
    print("收到事件JSON:")
    print(json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def process_event(client: WecomLongLinkClient, event: Mapping[str, Any]) -> None:
    _print_event_json(event)
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
    if _is_message_callback(event):
        _handle_non_text_message(client, event)
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
