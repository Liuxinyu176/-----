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
| send_command | `payload: Mapping, wait_response` | dict | 发送原始协议命令 |
| get_next_event | `timeout_seconds` | dict/None | 获取统一事件模型 |
| get_status | 无 | dict | 获取连接状态和重连信息 |

统一事件模型关键字段：

- `event`: 事件名（`aibot_msg_callback` / `aibot_event_callback`）
- `event_type`: `message` 或 `event`
- `msgid`: 消息 ID
- `chatid`: 会话 ID
- `userid`: 发送方用户 ID（从 `from.userid` 或 `userid` 提取）
- `aibotid`: 机器人 ID
- `raw`: 原始事件载荷

## 发送约束

- `aibot_send_msg` 必须且只能提供一个目标：`chatid` 或 `userid`。
- 可选 `msgid` 用于回复或关联上下文。
- 发送失败时返回协议错误信息，可结合调用侧重试策略处理。

## BREAKING 迁移说明

- API 参考已统一为 101463 长连接主路径，不再提供并行多路径说明。
- 历史发送调用请统一迁移到 `aibot_send_msg`。
- 历史接收处理请统一迁移到 `get_next_event()` 的事件模型。
