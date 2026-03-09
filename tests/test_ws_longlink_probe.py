from __future__ import annotations

import unittest
from typing import Any

import ws_longlink_probe


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.command_calls: list[dict[str, Any]] = []

    def aibot_send_msg(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"ok": True, "errcode": 0, "errmsg": "ok"}

    def send_command(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.command_calls.append({"payload": payload, **kwargs})
        return {"ok": True, "response": {"errcode": 0, "errmsg": "ok"}}


class WsLonglinkProbeTestCase(unittest.TestCase):
    def test_pick_from_payload_prefers_data(self) -> None:
        payload = {"msgtype": "other", "data": {"msgtype": "text"}}
        self.assertEqual(ws_longlink_probe._pick_from_payload(payload, "msgtype"), "text")

    def test_is_text_message_returns_true_for_text_callback(self) -> None:
        event = {
            "event": "aibot_msg_callback",
            "raw": {"msgtype": "text", "text": {"content": "hello"}},
        }
        self.assertTrue(ws_longlink_probe._is_text_message(event))

    def test_process_event_sends_reply_with_chatid(self) -> None:
        client = FakeClient()
        event = {
            "event": "aibot_msg_callback",
            "msgid": "msg_1",
            "chatid": "chat_1",
            "userid": "user_1",
            "raw": {
                "msgtype": "text",
                "text": {"content": "hello"},
                "headers": {"req_id": "req_1"},
            },
        }
        ws_longlink_probe.process_event(client, event)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["chatid"], "chat_1")
        self.assertIsNone(client.calls[0]["userid"])
        self.assertEqual(client.calls[0]["msgid"], "msg_1")

    def test_process_event_skips_non_text_message(self) -> None:
        client = FakeClient()
        event = {"event": "aibot_msg_callback", "raw": {"msgtype": "image"}}
        ws_longlink_probe.process_event(client, event)
        self.assertEqual(client.calls, [])

    def test_process_event_replies_welcome_on_enter_chat(self) -> None:
        client = FakeClient()
        event = {
            "event": "aibot_event_callback",
            "raw": {
                "cmd": "aibot_event_callback",
                "headers": {"req_id": "req_enter_1"},
                "body": {"event": "enter_chat"},
            },
        }
        ws_longlink_probe.process_event(client, event)
        self.assertEqual(len(client.command_calls), 1)
        payload = client.command_calls[0]["payload"]
        self.assertEqual(payload["cmd"], "aibot_respond_welcome_msg")
        self.assertEqual(payload["headers"]["req_id"], "req_enter_1")
        self.assertEqual(payload["body"]["msgtype"], "text")

    def test_process_event_replies_by_req_id_when_chatid_missing(self) -> None:
        client = FakeClient()
        event = {
            "event": "aibot_msg_callback",
            "msgid": "msg_2",
            "chatid": None,
            "userid": "user_2",
            "raw": {
                "msgtype": "text",
                "text": {"content": "hello"},
                "headers": {"req_id": "req_2"},
            },
        }
        ws_longlink_probe.process_event(client, event)
        self.assertEqual(client.calls, [])
        self.assertEqual(len(client.command_calls), 1)
        payload = client.command_calls[0]["payload"]
        self.assertEqual(payload["cmd"], "aibot_respond_msg")
        self.assertEqual(payload["headers"]["req_id"], "req_2")
        self.assertEqual(payload["body"]["msgtype"], "markdown")

    def test_extract_event_name_from_nested_eventtype(self) -> None:
        payload = {"body": {"event": {"eventtype": "disconnected_event"}}}
        self.assertEqual(ws_longlink_probe._event_name_from_payload(payload), "disconnected_event")

    def test_is_disconnected_event_returns_true(self) -> None:
        event = {
            "event": "aibot_event_callback",
            "raw": {"body": {"event": {"eventtype": "disconnected_event"}}},
        }
        self.assertTrue(ws_longlink_probe._is_disconnected_event(event))

    def test_template_card_and_feedback_event_detection(self) -> None:
        template_card_event = {
            "event": "aibot_event_callback",
            "event_name": "template_card_event",
            "raw": {},
        }
        feedback_event = {
            "event": "aibot_event_callback",
            "event_name": "feedback_event",
            "raw": {},
        }
        self.assertTrue(ws_longlink_probe._is_template_card_event(template_card_event))
        self.assertTrue(ws_longlink_probe._is_feedback_event(feedback_event))


if __name__ == "__main__":
    unittest.main()
