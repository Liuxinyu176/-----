from __future__ import annotations

import json
import queue
import unittest

from wechat_longlink_sdk import SDKConfig, WecomLongLinkClient


class FakeWebSocket:
    def __init__(self, recv_messages: list[str] | None = None) -> None:
        self.sent: list[str] = []
        self._recv_queue: queue.Queue[str] = queue.Queue()
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
        return None

    def close(self) -> None:
        return None

    def push_recv(self, payload: dict[str, object]) -> None:
        self._recv_queue.put(json.dumps(payload, ensure_ascii=False))


class Task23MessageEventParityTestCase(unittest.TestCase):
    def _build_client(self, fake_ws: FakeWebSocket) -> WecomLongLinkClient:
        config = SDKConfig(bot_id="bot_1", secret="secret_1", heartbeat_interval_seconds=0.05)
        return WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)

    def test_send_msg_supports_required_msgtypes(self) -> None:
        fake_ws = FakeWebSocket(
            recv_messages=[
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
            ]
        )
        client = self._build_client(fake_ws)
        client.start()
        client.aibot_send_msg(chatid="chat_1", msgtype="text", content="hello")
        client.aibot_send_msg(chatid="chat_1", msgtype="markdown", content="**hello**")
        client.aibot_send_msg(chatid="chat_1", msgtype="image", image={"media_id": "media_1"})
        client.aibot_send_msg(chatid="chat_1", msgtype="file", file={"file_id": "file_1"})
        client.aibot_send_msg(
            chatid="chat_1",
            msgtype="template_card",
            template_card={"card_type": "button_interaction", "main_title": {"title": "告警"}},
        )
        msgtypes = [json.loads(item)["body"]["msgtype"] for item in fake_ws.sent[-5:]]
        self.assertEqual(msgtypes, ["text", "markdown", "image", "file", "template_card"])
        client.stop()

    def test_respond_msg_and_update_msg_support_required_payloads(self) -> None:
        fake_ws = FakeWebSocket(
            recv_messages=[
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
                json.dumps({"errcode": 0}),
            ]
        )
        client = self._build_client(fake_ws)
        client.start()
        client.aibot_respond_msg(req_id="req_text", msgtype="text", content="ok")
        client.aibot_respond_msg(req_id="req_markdown", msgtype="markdown", content="**ok**")
        client.aibot_respond_msg(req_id="req_image", msgtype="image", image={"media_id": "media_2"})
        client.aibot_respond_msg(req_id="req_file", msgtype="file", file={"file_url": "https://example.com/a.txt"})
        client.aibot_respond_msg(
            req_id="req_card",
            msgtype="template_card",
            template_card={"card_type": "button_interaction", "main_title": {"title": "处理中"}},
        )
        client.aibot_respond_update_msg(
            req_id="req_update",
            template_card={"card_type": "button_interaction", "main_title": {"title": "已处理"}},
        )
        msgtypes = [json.loads(item)["body"]["msgtype"] for item in fake_ws.sent[-6:-1]]
        self.assertEqual(msgtypes, ["text", "markdown", "image", "file", "template_card"])
        update_payload = json.loads(fake_ws.sent[-1])
        self.assertEqual(update_payload["cmd"], "aibot_respond_update_msg")
        self.assertEqual(update_payload["body"]["response_type"], "update_template_card")
        client.stop()

    def test_event_callback_recognizes_required_event_types(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        event_types = ["enter_chat", "template_card_event", "feedback_event", "disconnected_event"]
        for index, event_type in enumerate(event_types, start=1):
            fake_ws.push_recv(
                {
                    "cmd": "aibot_event_callback",
                    "headers": {"req_id": f"req_{index}"},
                    "body": {
                        "msgid": f"msg_{index}",
                        "chatid": f"chat_{index}",
                        "from": {"userid": f"user_{index}"},
                        "event": {"eventtype": event_type},
                    },
                }
            )
        client = self._build_client(fake_ws)
        client.start()
        received = [client.get_next_event(timeout_seconds=1.0) for _ in range(4)]
        event_names = [item["event_name"] for item in received if item is not None]
        req_ids = [item["req_id"] for item in received if item is not None]
        self.assertEqual(event_names, event_types)
        self.assertEqual(req_ids, ["req_1", "req_2", "req_3", "req_4"])
        client.stop()


if __name__ == "__main__":
    unittest.main()
