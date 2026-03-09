from __future__ import annotations

import io
import logging
import os
import unittest
from unittest.mock import patch

from wechat_longlink_sdk import SDKConfig
from wechat_longlink_sdk.exceptions import SDKConfigError
from wechat_longlink_sdk.logging_utils import setup_sdk_logger
from wechat_longlink_sdk.messages import MessageType, RichMediaMessage, message_from_payload


class ModelAndSecurityUnitTestCase(unittest.TestCase):
    def test_sdk_config_from_env_error_on_empty_values(self) -> None:
        with self.assertRaises(ValueError):
            SDKConfig(bot_id="", secret="secret_1")
        with self.assertRaises(ValueError):
            SDKConfig(bot_id="bot_1", secret="")

    def test_sdk_config_from_env_uses_unified_env_keys(self) -> None:
        with patch.dict(
            os.environ,
            {
                "WECHAT_BOT_ID": "wechat_bot",
                "WECHAT_BOT_SECRET": "wechat_secret",
                "WECHAT_API_BOT_ID": "33777000151280519",
            },
            clear=True,
        ):
            config = SDKConfig.from_env()
        self.assertEqual(config.bot_id, "wechat_bot")
        self.assertEqual(config.secret, "wechat_secret")
        self.assertEqual(config.api_bot_id, "33777000151280519")

    def test_sdk_config_from_env_fallback_order(self) -> None:
        with patch.dict(
            os.environ,
            {
                "WECOM_BOT_ID": "wecom_bot",
                "BOT_SECRET": "legacy_secret",
            },
            clear=True,
        ):
            config = SDKConfig.from_env()
        self.assertEqual(config.bot_id, "wecom_bot")
        self.assertEqual(config.secret, "legacy_secret")

    def test_sdk_config_from_env_requires_botid_and_secret(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SDKConfigError):
                SDKConfig.from_env()

    def test_rich_media_message_requires_description(self) -> None:
        with self.assertRaises(ValueError):
            RichMediaMessage(title="title", description=" ", resource_url="https://example.com")

    def test_message_from_payload_roundtrip_for_text(self) -> None:
        payload = {"type": "text", "content": "hello", "metadata": {"trace_id": "trace_1"}}
        parsed = message_from_payload(payload)
        serialized = parsed.to_payload()
        self.assertEqual(serialized["type"], "text")
        self.assertEqual(serialized["content"], "hello")
        self.assertEqual(serialized["metadata"]["trace_id"], "trace_1")

    def test_message_from_payload_supports_all_documented_types(self) -> None:
        payloads = [
            {"type": "text", "content": "hello"},
            {"type": "image", "image_url": "https://example.com/image.png", "caption": "caption"},
            {"type": "file", "file_name": "a.txt", "file_url": "https://example.com/a.txt", "file_size": 1},
            {
                "type": "rich_media",
                "title": "title",
                "description": "description",
                "resource_url": "https://example.com/rich",
            },
            {"type": "event", "event_name": "join", "event_data": {"room": "r1"}},
        ]
        parsed_types = [message_from_payload(payload).message_type for payload in payloads]
        self.assertEqual(
            parsed_types,
            [
                MessageType.TEXT,
                MessageType.IMAGE,
                MessageType.FILE,
                MessageType.RICH_MEDIA,
                MessageType.EVENT,
            ],
        )

    def test_logger_redacts_secret(self) -> None:
        log_stream = io.StringIO()
        logger = setup_sdk_logger("test_wechat_longlink_sdk", secrets=["s3cr3t"])
        logger.setLevel(logging.INFO)
        logger.handlers = []
        handler = logging.StreamHandler(log_stream)
        logger.addHandler(handler)
        logger.propagate = False
        logger.info("auth failed secret=s3cr3t")
        output = log_stream.getvalue()
        self.assertNotIn("s3cr3t", output)
        self.assertIn("***", output)


if __name__ == "__main__":
    unittest.main()
