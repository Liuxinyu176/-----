# API 参考

本文档仅描述 101463 长连接主路径相关 API。

## 核心对象

### SDKConfig

用于承载 SDK 基础配置。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| bot_id | str | 是 | 无 | 机器人 ID |
| secret | str | 是 | 无 | 机器人密钥 |
| api_bot_id | str | 否 | None | API 消息体内机器人标识（如 33777000151280519） |
| websocket_url | str | 否 | wss://openws.work.weixin.qq.com | 智能机器人长连接地址 |
| heartbeat_interval_seconds | float | 否 | 30.0 | 心跳间隔，必须大于 0 |
| reconnect_interval_seconds | float | 否 | 5.0 | 重连间隔，必须大于 0 |
| max_reconnect_attempts | int | 否 | 0 | 最大重连次数，0 表示不限 |

构造方法：

- `SDKConfig(...)`
- `SDKConfig.from_env(bot_id_env=("WECHAT_BOT_ID","WECOM_BOT_ID","BOT_ID"), secret_env=("WECHAT_BOT_SECRET","WECOM_BOT_SECRET","BOT_SECRET"), api_bot_id_env=("WECHAT_API_BOT_ID","WECOM_API_BOT_ID","API_BOT_ID"))`

### WecomLongLinkClient

智能机器人长连接客户端，使用 BotID + Secret 建立 WebSocket 连接并收发消息。

常用方法：

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| start | 无 | None | 建立连接并发送 `aibot_subscribe` |
| stop | 无 | None | 关闭连接并停止心跳 |
| aibot_send_msg | `content, chatid 或 userid, msgid(可选)` | dict | 按 101463 协议发送并等待返回 |
| aibot_send_msg_stream_start | `content, chatid 或 userid` | dict | 发送流式起始分片（`stream.finish=False`） |
| aibot_send_msg_stream_update | `content, msgid, chatid 或 userid` | dict | 发送流式中间分片 |
| aibot_send_msg_stream_finish | `content, msgid, chatid 或 userid` | dict | 发送流式结束分片（`stream.finish=True`） |
| aibot_respond_msg | `req_id, content, msgtype` | dict | 使用回调 `req_id` 进行应答 |
| aibot_respond_welcome_msg | `req_id, content, msgtype` | dict | 使用回调 `req_id` 发送欢迎语 |
| aibot_respond_update_msg | `req_id, template_card, response_type(可选)` | dict | 使用回调 `req_id` 更新卡片 |
| send_command | `payload: Mapping, wait_response` | dict | 发送原始协议命令 |
| get_next_event | `timeout_seconds` | dict/None | 获取统一事件模型 |
| get_status | 无 | dict | 获取连接状态和重连信息 |

统一事件模型关键字段：

- `event`: 事件名（`aibot_msg_callback` / `aibot_event_callback`）
- `event_type`: `message` 或 `event`
- `event_name`: 事件子类型（如 `enter_chat`、`template_card_event`、`feedback_event`、`disconnected_event`）
- `msgid`: 消息 ID
- `chatid`: 会话 ID
- `userid`: 发送方用户 ID（从 `from.userid` 或 `userid` 提取）
- `aibotid`: 机器人 ID
- `raw`: 原始事件载荷

## 发送约束

- `aibot_send_msg` 必须且只能提供一个目标：`chatid` 或 `userid`。
- `aibot_send_msg` 支持 `text`、`markdown`、`image`、`file`、`template_card` 五种消息类型。
- 可选 `msgid` 用于回复或关联上下文。
- 流式接口 `aibot_send_msg_stream_update/finish` 必须提供 `msgid`，且仍需提供目标（`chatid` 或 `userid`）。
- `aibot_respond_msg` / `aibot_respond_welcome_msg` 也支持上述五种消息类型。
- `aibot_respond_update_msg` 必须提供 `template_card` 且包含 `card_type`。
- 发送失败时返回协议错误信息，可结合调用侧重试策略处理。

## 文档 API 目录能力

### DocumentAPIClient

用于承载文档 API 目录的统一调用、参数校验与重试策略，核心对象位于 `wechat_longlink_sdk.api_client`。

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| list_apis | 无 | list[str] | 返回 API 名称列表 |
| get_api_definition | `api_name` | APIDefinition | 返回 API 路径/方法/参数定义 |
| call_api | `api_name, params, session_id` | dict | 执行调用并按重试策略返回结果 |

已内置 API 目录：

| API 名称 | Method | Path | 必填参数 | 可选参数 |
| --- | --- | --- | --- | --- |
| message.send_text | POST | `/v1/messages/text/send` | `conversation_id`, `content` | `metadata`, `request_id` |
| message.send_image | POST | `/v1/messages/image/send` | `conversation_id`, `image_url` | `caption`, `metadata`, `request_id` |
| message.send_file | POST | `/v1/messages/file/send` | `conversation_id`, `file_name`, `file_url` | `file_size`, `mime_type`, `metadata`, `request_id` |
| message.send_rich_media | POST | `/v1/messages/rich-media/send` | `conversation_id`, `title`, `description`, `resource_url` | `thumbnail_url`, `metadata`, `request_id` |
| bot.profile.get | GET | `/v1/bot/profile` | 无 | `bot_id` |
| conversation.history.list | GET | `/v1/conversations/history` | `conversation_id` | `cursor`, `limit` |

说明：
- `DocumentAPIClient` 默认 transport 为本地回显实现，接入真实后端时需传入自定义 `transport`。
- 参数校验会校验空字符串、`limit` 范围（1-200）与 `file_size` 非负整数约束。
- 失败会抛出 `APIRetryExhaustedError` 及其错误链，错误码映射在 `ERROR_CODE_TO_EXCEPTION`。

## 能力矩阵（支持状态、限制、示例）

如需直接对接，可优先参考“已实现 API 清单 + 请求/响应模板”：[`docs/api-capability-matrix.md`](api-capability-matrix.md)。

| 能力分类 | 能力项 | SDK 入口 | 支持状态 | 限制 | 示例 |
| --- | --- | --- | --- | --- | --- |
| 连接 | `aibot_subscribe` 鉴权订阅 | `start()` / `subscribe()` | 已支持 | 连接前需正确配置 `bot_id` 与 `secret` | `client.start()` |
| 回调 | `aibot_msg_callback` 接收 | `get_next_event()` | 已支持 | 统一事件在 `raw` 保留原始字段 | `event["event"] == "aibot_msg_callback"` |
| 回调 | `aibot_event_callback` 接收 | `get_next_event()` | 已支持 | `event_type` 固定为 `event` | `event["event_type"] == "event"` |
| 回复 | `aibot_send_msg` 主动发送 | `aibot_send_msg()` | 已支持 | `chatid/userid` 需二选一 | `client.aibot_send_msg(content="hello", chatid="xxx")` |
| 回复 | 流式 `start/update/finish` | `aibot_send_msg_stream_*()` | 已支持 | `update/finish` 必须携带 `msgid` 与目标 | `client.aibot_send_msg_stream_finish(..., msgid="m1", chatid="xxx")` |
| 回复 | `aibot_respond_msg` | `aibot_respond_msg()` | 已支持 | 必须传回调 `req_id` | `client.aibot_respond_msg(req_id=req_id, content="ok")` |
| 回复 | `aibot_respond_welcome_msg` | `aibot_respond_welcome_msg()` | 已支持 | 必须传回调 `req_id` | `client.aibot_respond_welcome_msg(req_id=req_id, content="welcome", msgtype="text")` |
| 回复 | `aibot_respond_update_msg` | `aibot_respond_update_msg()` | 已支持 | 必须传 `req_id` 和 `template_card.card_type` | `client.aibot_respond_update_msg(req_id=req_id, template_card=card)` |
| 消息类型 | `text/markdown/image/file/template_card` | `aibot_send_msg()` + `aibot_respond_*()` | 已支持 | 媒体消息需提供 media_id/url/image_url/file_url/file_id 之一 | `client.aibot_send_msg(chatid="xxx", msgtype="image", image={"media_id":"m1"})` |
| 事件子类型 | `enter_chat/template_card_event/feedback_event/disconnected_event` | `get_next_event()` | 已支持 | 从统一事件 `event_name` 获取 | `event["event_name"] == "template_card_event"` |
| 心跳 | ping 保活 | 内置心跳线程 | 已支持 | `heartbeat_interval_seconds > 0` | `SDKConfig(heartbeat_interval_seconds=30.0)` |
| 观测 | 状态可观测 | `get_status()` | 已支持 | 仅观测本地连接状态 | `client.get_status()` |
| 文档 API | 目录与重试调用 | `DocumentAPIClient` | 受限支持 | 真实网络调用依赖自定义 transport | `DocumentAPIClient().list_apis()` |

## 主动推送场景示例

以下示例均与 `WecomLongLinkClient` 当前公开签名一致。

```python
# 定时提醒
client.aibot_send_msg(
    chatid="ops_chat",
    msgtype="text",
    content="每日巡检提醒：请在 18:00 前提交结果",
)

# 异步通知
client.aibot_send_msg(
    userid="zhangsan",
    msgtype="markdown",
    content="任务 #A102 已完成，可前往控制台查看详情",
)

# 告警通知（卡片）
client.aibot_send_msg(
    chatid="ops_chat",
    msgtype="template_card",
    template_card={
        "card_type": "button_interaction",
        "main_title": {"title": "P1 告警：支付错误率升高"},
    },
)
```

## BREAKING 迁移说明

- API 参考已统一为 101463 长连接主路径，不再提供并行多路径说明。
- 历史发送调用请统一迁移到 `aibot_send_msg`。
- 历史接收处理请统一迁移到 `get_next_event()` 的事件模型。
- 历史入口 `BotClient` / `SessionState` 已移除，替代关系见 `docs/migration.md`。
