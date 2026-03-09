from __future__ import annotations

import json
import logging
import queue
import time
import unittest
from io import StringIO
from typing import Any

from wechat_longlink_sdk import LongLinkState, SDKConfig, WecomLongLinkClient


class FakeWebSocket:
    def __init__(self, recv_messages: list[str] | None = None, ping_error: Exception | None = None) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.ping_count = 0
        self._recv_queue: queue.Queue[str] = queue.Queue()
        self._ping_error = ping_error
        for message in recv_messages or []:
            self._recv_queue.put(message)

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def recv(self) -> str:
        try:
            return self._recv_queue.get(timeout=0.05)
        except queue.Empty:
            return ""

    def ping(self) -> None:
        self.ping_count += 1
        if self._ping_error is not None:
            raise self._ping_error

    def close(self) -> None:
        self.closed = True

    def push_recv(self, payload: dict[str, Any]) -> None:
        self._recv_queue.put(json.dumps(payload, ensure_ascii=False))


class WecomLongLinkClientTestCase(unittest.TestCase):
    def _build_client(self, fake_ws: FakeWebSocket) -> WecomLongLinkClient:
        config = SDKConfig(
            bot_id="bot_1",
            secret="secret_1",
            heartbeat_interval_seconds=0.05,
            reconnect_interval_seconds=0.01,
            max_reconnect_attempts=2,
        )
        return WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)

    def test_subscribe_payload_contains_required_fields(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0, "errmsg": "ok"})])
        config = SDKConfig(bot_id="bot_1", secret="secret_1", api_bot_id="33777000151280519")
        client = WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)
        client.start()
        self.assertEqual(client.state, LongLinkState.SUBSCRIBED)
        subscribe_payload = json.loads(fake_ws.sent[0])
        self.assertEqual(subscribe_payload["cmd"], "aibot_subscribe")
        self.assertTrue(subscribe_payload["headers"]["req_id"])
        self.assertEqual(subscribe_payload["body"]["bot_id"], "bot_1")
        self.assertEqual(subscribe_payload["body"]["secret"], "secret_1")
        self.assertEqual(subscribe_payload["body"]["aibotid"], "33777000151280519")
        client.stop()

    def test_aibot_send_msg_generates_command(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        response = client.aibot_send_msg(content="hello", chatid="chat_1")
        self.assertTrue(response["ok"])
        self.assertEqual(response["response"]["errcode"], 0)
        command_payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(command_payload["cmd"], "aibot_send_msg")
        self.assertEqual(command_payload["body"]["chatid"], "chat_1")
        self.assertEqual(command_payload["body"]["markdown"]["content"], "hello")
        client.stop()

    def test_aibot_send_msg_requires_target(self) -> None:
        fake_ws = FakeWebSocket()
        config = SDKConfig(bot_id="bot_1", secret="secret_1")
        client = WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)
        client.start()
        with self.assertRaises(ValueError):
            client.aibot_send_msg(content="hello")
        client.stop()

    def test_aibot_send_msg_rejects_chatid_and_userid_together(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(ValueError):
            client.aibot_send_msg(content="hello", chatid="chat_1", userid="user_1")
        client.stop()

    def test_aibot_send_msg_raises_on_protocol_error_response(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 93000, "errmsg": "denied"})])
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(RuntimeError):
            client.aibot_send_msg(content="hello", chatid="chat_1")
        client.stop()

    def test_aibot_send_msg_with_msgid_generates_command(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        response = client.aibot_send_msg(content="hello", msgid="msg_1", userid="user_1")
        self.assertTrue(response["ok"])
        command_payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(command_payload["cmd"], "aibot_send_msg")
        self.assertEqual(command_payload["body"]["userid"], "user_1")
        self.assertEqual(command_payload["body"]["msgid"], "msg_1")
        client.stop()

    def test_aibot_send_msg_retries_on_retryable_errcode(self) -> None:
        fake_ws = FakeWebSocket(
            recv_messages=[
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 93008, "errmsg": "server busy"}),
                json.dumps({"errcode": 0, "errmsg": "ok"}),
            ]
        )
        client = self._build_client(fake_ws)
        client.start()
        response = client.aibot_send_msg(content="hello", chatid="chat_1", max_attempts=2, retry_interval_seconds=0.001)
        self.assertTrue(response["ok"])
        self.assertEqual(response["attempt"], 2)
        self.assertEqual(len(fake_ws.sent), 3)
        client.stop()

    def test_aibot_send_msg_stops_retry_on_non_retryable_errcode(self) -> None:
        fake_ws = FakeWebSocket(
            recv_messages=[
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 93000, "errmsg": "denied"}),
                json.dumps({"errcode": 0, "errmsg": "unexpected"}),
            ]
        )
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(RuntimeError):
            client.aibot_send_msg(content="hello", chatid="chat_1", max_attempts=3, retry_interval_seconds=0.001)
        self.assertEqual(len(fake_ws.sent), 2)
        client.stop()

    def test_receive_event_unifies_key_fields(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        fake_ws.push_recv(
            {
                "event": "aibot_msg_callback",
                "msgid": "msg_001",
                "chatid": "chat_001",
                "from": {"userid": "user_001"},
                "aibotid": "33777000151280519",
            }
        )
        client = self._build_client(fake_ws)
        client.start()
        event = client.get_next_event(timeout_seconds=1.0)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["event"], "aibot_msg_callback")
        self.assertEqual(event["event_type"], "message")
        self.assertEqual(event["msgid"], "msg_001")
        self.assertEqual(event["chatid"], "chat_001")
        self.assertEqual(event["userid"], "user_001")
        self.assertEqual(event["aibotid"], "33777000151280519")
        client.stop()

    def test_receive_event_unifies_key_fields_from_data_payload(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        fake_ws.push_recv(
            {
                "action": "aibot_msg_callback",
                "data": {
                    "msgid": "msg_data_001",
                    "chatid": "chat_data_001",
                    "from": {"userid": "user_data_001"},
                    "aibotid": "33777000151280519",
                },
            }
        )
        client = self._build_client(fake_ws)
        client.start()
        event = client.get_next_event(timeout_seconds=1.0)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["event"], "aibot_msg_callback")
        self.assertEqual(event["msgid"], "msg_data_001")
        self.assertEqual(event["chatid"], "chat_data_001")
        self.assertEqual(event["userid"], "user_data_001")
        self.assertEqual(event["aibotid"], "33777000151280519")
        client.stop()

    def test_aibot_send_msg_includes_aibotid_and_stream_flags(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0})])
        config = SDKConfig(bot_id="bot_1", secret="secret_1", api_bot_id="33777000151280519")
        client = WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)
        client.start()
        response = client.aibot_send_msg(content="hello", chatid="chat_1", stream=True, finish=False)
        self.assertTrue(response["ok"])
        payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(payload["cmd"], "aibot_send_msg")
        self.assertEqual(payload["body"]["chatid"], "chat_1")
        self.assertEqual(payload["body"]["aibotid"], "33777000151280519")
        self.assertEqual(payload["body"]["stream"], {"finish": False})
        client.stop()

    def test_aibot_send_msg_omits_stream_when_stream_is_false(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        response = client.aibot_send_msg(content="hello", chatid="chat_1", stream=False, finish=True)
        self.assertTrue(response["ok"])
        payload = json.loads(fake_ws.sent[-1])
        self.assertNotIn("stream", payload["body"])
        client.stop()

    def test_aibot_send_msg_rejects_finish_false_when_stream_is_false(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(ValueError):
            client.aibot_send_msg(content="hello", chatid="chat_1", stream=False, finish=False)
        client.stop()

    def test_stream_stage_wrappers_generate_expected_stream_payload(self) -> None:
        fake_ws = FakeWebSocket(
            recv_messages=[
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
            ]
        )
        client = self._build_client(fake_ws)
        client.start()
        start_result = client.aibot_send_msg_stream_start(content="part1", chatid="chat_1")
        update_result = client.aibot_send_msg_stream_update(content="part2", msgid="msg_1", chatid="chat_1")
        finish_result = client.aibot_send_msg_stream_finish(content="part3", msgid="msg_1", chatid="chat_1")
        self.assertTrue(start_result["ok"])
        self.assertTrue(update_result["ok"])
        self.assertTrue(finish_result["ok"])
        start_payload = json.loads(fake_ws.sent[-3])
        update_payload = json.loads(fake_ws.sent[-2])
        finish_payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(start_payload["body"]["stream"], {"finish": False})
        self.assertNotIn("msgid", start_payload["body"])
        self.assertEqual(update_payload["body"]["stream"], {"finish": False})
        self.assertEqual(update_payload["body"]["msgid"], "msg_1")
        self.assertEqual(finish_payload["body"]["stream"], {"finish": True})
        self.assertEqual(finish_payload["body"]["msgid"], "msg_1")
        client.stop()

    def test_send_command_without_wait_response_uses_unified_result_model(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        result = client.send_command({"action": "custom_action", "data": {"foo": "bar"}}, wait_response=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "custom_action")
        self.assertEqual(result["attempt"], 1)
        self.assertEqual(result["errcode"], 0)
        self.assertEqual(result["errmsg"], "ok")
        self.assertIsNone(result["response"])
        client.stop()

    def test_send_command_with_error_response_uses_unified_result_model(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 93000, "errmsg": "denied"})])
        client = self._build_client(fake_ws)
        client.start()
        result = client.send_command({"action": "custom_action"}, wait_response=True, raise_on_error=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["action"], "custom_action")
        self.assertEqual(result["errcode"], 93000)
        self.assertEqual(result["errmsg"], "denied")
        self.assertEqual(result["response"]["errcode"], 93000)
        client.stop()

    def test_aibot_respond_msg_generates_command(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0, "errmsg": "ok"})])
        client = self._build_client(fake_ws)
        client.start()
        result = client.aibot_respond_msg(req_id="req_1", content="reply content")
        self.assertTrue(result["ok"])
        payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(payload["cmd"], "aibot_respond_msg")
        self.assertEqual(payload["headers"]["req_id"], "req_1")
        self.assertEqual(payload["body"]["msgtype"], "markdown")
        self.assertEqual(payload["body"]["markdown"]["content"], "reply content")
        client.stop()

    def test_aibot_respond_welcome_msg_generates_command(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0, "errmsg": "ok"})])
        client = self._build_client(fake_ws)
        client.start()
        result = client.aibot_respond_welcome_msg(req_id="req_2", content="welcome")
        self.assertTrue(result["ok"])
        payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(payload["cmd"], "aibot_respond_welcome_msg")
        self.assertEqual(payload["headers"]["req_id"], "req_2")
        self.assertEqual(payload["body"]["msgtype"], "text")
        self.assertEqual(payload["body"]["text"]["content"], "welcome")
        client.stop()

    def test_longlink_logs_redact_secret_and_emit_key_messages(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        config = SDKConfig(bot_id="bot_1", secret="s3cr3t")
        logger = logging.getLogger("test_wechat_longlink_client_logs")
        logger.handlers = []
        logger.filters = []
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        client = WecomLongLinkClient(config=config, logger=logger, ws_factory=lambda *args, **kwargs: fake_ws)
        client.start()
        client.stop()
        output = stream.getvalue()
        self.assertIn("longlink command sent", output)
        self.assertIn("longlink subscribed", output)
        self.assertIn("***", output)
        self.assertNotIn("s3cr3t", output)

    def test_reconnect_after_receive_closed_exception(self) -> None:
        first_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        second_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        first_read = {"count": 0}

        def first_recv() -> str:
            if first_read["count"] == 0:
                first_read["count"] += 1
                return ""
            from websocket import WebSocketConnectionClosedException

            raise WebSocketConnectionClosedException("closed")

        first_ws.recv = first_recv
        ws_pool = [first_ws, second_ws]
        config = SDKConfig(
            bot_id="bot_1",
            secret="secret_1",
            heartbeat_interval_seconds=0.05,
            reconnect_interval_seconds=0.01,
            max_reconnect_attempts=3,
        )
        client = WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: ws_pool.pop(0))
        client.start()
        time.sleep(0.1)
        status = client.get_status()
        self.assertIn(client.state, {LongLinkState.CONNECTED, LongLinkState.SUBSCRIBED, LongLinkState.RECONNECTING})
        self.assertTrue(status["connected"])
        self.assertGreaterEqual(status["reconnect_attempts"], 1)
        client.stop()

    def test_receive_timeout_does_not_trigger_reconnect(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        recv_count = {"count": 0}

        def timeout_then_idle() -> str:
            from websocket import WebSocketTimeoutException

            recv_count["count"] += 1
            if recv_count["count"] == 1:
                raise WebSocketTimeoutException("timeout")
            return ""

        fake_ws.recv = timeout_then_idle
        config = SDKConfig(
            bot_id="bot_1",
            secret="secret_1",
            heartbeat_interval_seconds=0.05,
            reconnect_interval_seconds=0.01,
            max_reconnect_attempts=3,
        )
        client = WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)
        client.start()
        time.sleep(0.1)
        status = client.get_status()
        self.assertEqual(status["reconnect_attempts"], 0)
        self.assertEqual(client.state, LongLinkState.SUBSCRIBED)
        self.assertTrue(status["connected"])
        client.stop()


if __name__ == "__main__":
    unittest.main()
