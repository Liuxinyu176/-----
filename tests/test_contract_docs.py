from __future__ import annotations

from pathlib import Path
import unittest

from wechat_longlink_sdk import LongLinkState, SDKConfig, WecomLongLinkClient
from wechat_longlink_sdk.api_client import API_CATALOG


class SDKContractTestCase(unittest.TestCase):
    def test_api_catalog_matches_documented_contract(self) -> None:
        documented_catalog = {
            "message.send_text": {
                "method": "POST",
                "path": "/v1/messages/text/send",
                "required": ("conversation_id", "content"),
                "optional": ("metadata", "request_id"),
            },
            "message.send_image": {
                "method": "POST",
                "path": "/v1/messages/image/send",
                "required": ("conversation_id", "image_url"),
                "optional": ("caption", "metadata", "request_id"),
            },
            "message.send_file": {
                "method": "POST",
                "path": "/v1/messages/file/send",
                "required": ("conversation_id", "file_name", "file_url"),
                "optional": ("file_size", "mime_type", "metadata", "request_id"),
            },
            "message.send_rich_media": {
                "method": "POST",
                "path": "/v1/messages/rich-media/send",
                "required": ("conversation_id", "title", "description", "resource_url"),
                "optional": ("thumbnail_url", "metadata", "request_id"),
            },
            "bot.profile.get": {
                "method": "GET",
                "path": "/v1/bot/profile",
                "required": (),
                "optional": ("bot_id",),
            },
            "conversation.history.list": {
                "method": "GET",
                "path": "/v1/conversations/history",
                "required": ("conversation_id",),
                "optional": ("cursor", "limit"),
            },
        }

        self.assertEqual(set(API_CATALOG.keys()), set(documented_catalog.keys()))
        for api_name, expected in documented_catalog.items():
            api_definition = API_CATALOG[api_name]
            self.assertEqual(api_definition.method, expected["method"])
            self.assertEqual(api_definition.path, expected["path"])
            self.assertEqual(api_definition.required_params, expected["required"])
            self.assertEqual(api_definition.optional_params, expected["optional"])

    def test_core_sdk_entrypoints_available(self) -> None:
        config = SDKConfig(bot_id="bot_1", secret="secret_1")
        self.assertEqual(config.bot_id, "bot_1")
        self.assertEqual(config.secret, "secret_1")
        self.assertEqual(LongLinkState.SUBSCRIBED.value, "subscribed")
        self.assertTrue(callable(WecomLongLinkClient))

    def test_quickstart_and_reference_docs_available(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        quickstart = (project_root / "docs" / "quickstart.md").read_text(encoding="utf-8")
        api_reference = (project_root / "docs" / "api-reference.md").read_text(encoding="utf-8")
        self.assertIn("最小可运行示例", quickstart)
        self.assertIn("SDKConfig", api_reference)
        self.assertIn("WecomLongLinkClient", api_reference)


if __name__ == "__main__":
    unittest.main()
