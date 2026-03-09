# 迁移说明（Task 3 清理项）

本次清理收敛为 101463 长连接单一路径，移除历史入口与过时描述。

## 变更总览

| 类型 | 旧项 | 新项 | 影响 |
| --- | --- | --- | --- |
| 历史入口文件 | `src/wechat_longlink_sdk/client.py` | `src/wechat_longlink_sdk/longlink.py` | `BotClient` / `SessionState` 不再维护，统一使用 `WecomLongLinkClient` / `LongLinkState` |
| 文档示例入口 | `BotClient` | `WecomLongLinkClient` | 新接入与故障处理示例统一到长连接主路径 |

## 替代关系

| 历史能力 | 推荐替代 |
| --- | --- |
| `BotClient.start()` | `WecomLongLinkClient.start()` |
| `BotClient.stop()` | `WecomLongLinkClient.stop()` |
| `BotClient.get_status()` | `WecomLongLinkClient.get_status()` |
| `BotClient.send_message(...)` | `WecomLongLinkClient.aibot_send_msg(...)` |
| `SessionState` | `LongLinkState` |

## 升级步骤

1. 将 `BotClient` 导入替换为 `WecomLongLinkClient`。
2. 将消息发送调用替换为 `aibot_send_msg`，并确保目标参数使用 `chatid` 或 `userid` 二选一。
3. 将状态枚举判断从 `SessionState` 替换为 `LongLinkState`。
4. 按 `README.md` 与 `docs/quickstart.md` 的最小流程重新验证连接、收包与发送。
