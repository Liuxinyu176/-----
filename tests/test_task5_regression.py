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


class Task5RegressionTestCase(unittest.TestCase):
    def _build_client(self, fake_ws: FakeWebSocket) -> WecomLongLinkClient:
        config = SDKConfig(bot_id="bot_1", secret="secret_1", heartbeat_interval_seconds=0.05)
        return WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)

    def test_respond_msg_validates_req_id_and_content(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(ValueError):
            client.aibot_respond_msg(req_id=" ", content="valid")
        with self.assertRaises(ValueError):
            client.aibot_respond_msg(req_id="req_1", content=" ")
        client.stop()

    def test_respond_msg_validates_msgtype(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0})])
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(ValueError):
            client.aibot_respond_msg(req_id="req_1", content="reply", msgtype="unsupported")
        with self.assertRaises(ValueError):
            client.aibot_respond_msg(req_id="req_1", msgtype="image")
        client.stop()

    def test_send_command_raise_on_error_true_raises_runtime_error(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 93000, "errmsg": "denied"})])
        client = self._build_client(fake_ws)
        client.start()
        with self.assertRaises(RuntimeError):
            client.send_command({"action": "custom_action"}, wait_response=True, raise_on_error=True)
        client.stop()

    def test_send_msg_retry_on_timeout_exception(self) -> None:
        fake_ws = FakeWebSocket(recv_messages=[json.dumps({"errcode": 0}), json.dumps({"errcode": 0, "errmsg": "ok"})])
        client = self._build_client(fake_ws)
        client.start()
        attempts = {"count": 0}
        original_send_command = client.send_command

        def flaky_send_command(payload, wait_response=False, raise_on_error=True):  # type: ignore[no-untyped-def]
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("timeout while sending")
            return original_send_command(payload, wait_response=wait_response, raise_on_error=raise_on_error)

        client.send_command = flaky_send_command  # type: ignore[assignment]
        result = client.aibot_send_msg(
            content="hello",
            chatid="chat_1",
            max_attempts=2,
            retry_interval_seconds=0.001,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["attempt"], 2)
        client.stop()


if __name__ == "__main__":
    unittest.main()
