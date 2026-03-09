from __future__ import annotations

import json
import unittest

from wechat_longlink_sdk import LongLinkState, SDKConfig, WecomLongLinkClient


class WecomLongLinkUnitTestCase(unittest.TestCase):
    def test_start_stop_and_status(self) -> None:
        class FakeWebSocket:
            def __init__(self) -> None:
                self.closed = False
                self.sent: list[str] = []
                self._first = True

            def send(self, payload: str) -> None:
                self.sent.append(payload)

            def recv(self) -> str:
                if self._first:
                    self._first = False
                    return json.dumps({"errcode": 0})
                return ""

            def ping(self) -> None:
                return None

            def close(self) -> None:
                self.closed = True

        config = SDKConfig(bot_id="bot_1", secret="secret_1", heartbeat_interval_seconds=0.05)
        fake_ws = FakeWebSocket()
        client = WecomLongLinkClient(config=config, ws_factory=lambda *args, **kwargs: fake_ws)
        client.start()
        status = client.get_status()
        self.assertTrue(status["connected"])
        self.assertEqual(status["state"], LongLinkState.SUBSCRIBED.value)
        client.stop()
        stopped = client.get_status()
        self.assertFalse(stopped["connected"])
        self.assertEqual(stopped["state"], LongLinkState.STOPPED.value)


if __name__ == "__main__":
    unittest.main()
