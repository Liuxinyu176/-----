from __future__ import annotations

import json
import unittest

from wechat_longlink_sdk import LongLinkState, SDKConfig, WecomLongLinkClient


class WecomLongLinkIntegrationTestCase(unittest.TestCase):
    def test_reconnect_after_connect_failure_then_success(self) -> None:
        class FakeWebSocket:
            def __init__(self) -> None:
                self.closed = False
                self.sent: list[str] = []
                self._first_recv = True

            def send(self, payload: str) -> None:
                self.sent.append(payload)

            def recv(self) -> str:
                if self._first_recv:
                    self._first_recv = False
                    return json.dumps({"errcode": 0})
                return ""

            def ping(self) -> None:
                return None

            def close(self) -> None:
                self.closed = True

        state = {"factory_count": 0}

        def ws_factory(*args, **kwargs):
            state["factory_count"] += 1
            if state["factory_count"] == 1:
                raise RuntimeError("network unavailable")
            return FakeWebSocket()

        config = SDKConfig(
            bot_id="bot_1",
            secret="secret_1",
            reconnect_interval_seconds=0.001,
            max_reconnect_attempts=2,
        )
        client = WecomLongLinkClient(config=config, ws_factory=ws_factory)

        client.start()
        status = client.get_status()
        self.assertEqual(state["factory_count"], 2)
        self.assertEqual(status["state"], LongLinkState.SUBSCRIBED.value)
        self.assertEqual(status["reconnect_attempts"], 0)
        client.stop()


if __name__ == "__main__":
    unittest.main()
