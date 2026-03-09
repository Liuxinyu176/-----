from __future__ import annotations

import unittest

from wechat_longlink_sdk.api_client import APIRetryPolicy, DocumentAPIClient
from wechat_longlink_sdk.exceptions import APIParameterValidationError, APIRetryExhaustedError


class DocumentAPIClientTestCase(unittest.TestCase):
    def test_call_api_success(self) -> None:
        client = DocumentAPIClient()
        response = client.call_api(
            "message.send_text",
            params={"conversation_id": "conv_1", "content": "hello"},
            session_id="session_1",
        )
        self.assertTrue(response["ok"])
        self.assertEqual(response["api_name"], "message.send_text")
        self.assertEqual(response["attempt"], 1)

    def test_param_validation_error(self) -> None:
        client = DocumentAPIClient()
        with self.assertRaises(APIParameterValidationError):
            client.call_api("message.send_text", params={"content": "hello"}, session_id="session_1")

    def test_retry_until_success(self) -> None:
        state = {"count": 0}

        def flaky_transport(path: str, method: str, params: dict[str, object], session_id: str | None) -> dict[str, object]:
            if state["count"] < 2:
                state["count"] += 1
                return {"ok": False, "error_code": "server_busy", "message": "busy"}
            return {"ok": True, "path": path, "method": method, "params": params, "session_id": session_id}

        client = DocumentAPIClient(
            transport=flaky_transport,
            retry_policy=APIRetryPolicy(max_attempts=3, initial_interval_seconds=0.001, max_interval_seconds=0.001),
        )
        response = client.call_api(
            "message.send_text",
            params={"conversation_id": "conv_1", "content": "hello"},
            session_id="session_1",
        )
        self.assertEqual(response["attempt"], 3)

    def test_retry_exhausted(self) -> None:
        def always_fail(path: str, method: str, params: dict[str, object], session_id: str | None) -> dict[str, object]:
            return {"ok": False, "error_code": "server_busy", "message": "busy"}

        client = DocumentAPIClient(
            transport=always_fail,
            retry_policy=APIRetryPolicy(max_attempts=2, initial_interval_seconds=0.001, max_interval_seconds=0.001),
        )
        with self.assertRaises(APIRetryExhaustedError):
            client.call_api(
                "message.send_text",
                params={"conversation_id": "conv_1", "content": "hello"},
                session_id="session_1",
            )


if __name__ == "__main__":
    unittest.main()
