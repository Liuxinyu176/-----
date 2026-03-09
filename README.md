# wechat-longlink-sdk

Python 企业微信机器人 SDK（仅支持 101463 长连接主路径）。

## 安装

```bash
pip install -e .
```

## 最小配置

```python
from wechat_longlink_sdk import SDKConfig, WecomLongLinkClient

config = SDKConfig(bot_id="your_bot_id", secret="your_secret")
client = WecomLongLinkClient(config)
```

## 环境变量注入

```python
from wechat_longlink_sdk import SDKConfig

config = SDKConfig.from_env()
```

默认读取：
- `WECHAT_BOT_ID`（优先）
- `WECOM_BOT_ID`
- `BOT_ID`
- `WECHAT_BOT_SECRET`（优先）
- `WECOM_BOT_SECRET`
- `BOT_SECRET`
- `WECHAT_API_BOT_ID`（可选，优先）
- `WECOM_API_BOT_ID`（可选）
- `API_BOT_ID`（可选）

## 101463 长连接主路径（WebSocket）

```python
from wechat_longlink_sdk import SDKConfig, WecomLongLinkClient

config = SDKConfig.from_env()
client = WecomLongLinkClient(config)
client.start()
client.aibot_send_msg(content="hello from longlink", chatid="your_chat_id")
client.stop()
```

## 能力矩阵（全量能力视图）

完整“已实现 API 清单 + 请求/响应模板”见：[能力矩阵与模板](docs/api-capability-matrix.md)。

| 能力项 | SDK 入口 | 支持状态 | 限制 | 示例 |
| --- | --- | --- | --- | --- |
| 连接鉴权订阅（`aibot_subscribe`） | `start()` / `subscribe()` | 已支持 | 需先提供有效 `bot_id` 与 `secret` | `client.start()` |
| 消息回调接收（`aibot_msg_callback`） | `get_next_event()` | 已支持 | 事件为统一模型，原始载荷在 `raw` | `event = client.get_next_event()` |
| 事件回调接收（`aibot_event_callback`） | `get_next_event()` | 已支持 | `event` 区分消息/事件 | `event["event"] == "aibot_event_callback"` |
| 主动发送/会话回复（`aibot_send_msg`） | `aibot_send_msg()` | 已支持 | `chatid` 与 `userid` 必须二选一；支持 `text/markdown/image/file/template_card` | `client.aibot_send_msg(content="hi", chatid="xxx", msgtype="markdown")` |
| 流式回复 start/update/finish | `aibot_send_msg_stream_start/update/finish()` | 已支持 | `update/finish` 需同时传 `msgid` 和目标（`chatid` 或 `userid`） | 见下方流式示例 |
| 应答回复（`aibot_respond_msg`） | `aibot_respond_msg()` | 已支持 | 必须提供回调 `req_id` | `client.aibot_respond_msg(req_id=req_id, content="ok")` |
| 欢迎语应答（`aibot_respond_welcome_msg`） | `aibot_respond_welcome_msg()` | 已支持 | 必须提供回调 `req_id` | `client.aibot_respond_welcome_msg(req_id=req_id, content="欢迎")` |
| 卡片事件更新应答（`aibot_respond_update_msg`） | `aibot_respond_update_msg()` | 已支持 | 必须提供回调 `req_id` 与 `template_card.card_type` | `client.aibot_respond_update_msg(req_id=req_id, template_card=card)` |
| 心跳保活 | 内置心跳线程 | 已支持 | 心跳间隔需大于 0 | `SDKConfig(heartbeat_interval_seconds=30.0)` |
| 状态观测 | `get_status()` | 已支持 | 仅返回当前进程内状态 | `client.get_status()` |
| 文档 API 能力目录 | `DocumentAPIClient` + `API_CATALOG` | 受限支持 | 默认 transport 为示例回显，接生产需自定义 transport | 见 `docs/api-reference.md` |

多消息类型与事件支持状态：

| 维度 | 具体项 | 支持状态 | 对应入口 |
| --- | --- | --- | --- |
| 发送/应答消息类型 | `text` / `markdown` / `image` / `file` / `template_card` | 已支持 | `aibot_send_msg()`、`aibot_respond_msg()`、`aibot_respond_welcome_msg()` |
| 事件子类型识别 | `enter_chat` / `template_card_event` / `feedback_event` / `disconnected_event` | 已支持 | `get_next_event()` 返回 `event_name` |

## 示例一致性（与 SDK 行为对齐）

流式发送示例（与 `aibot_send_msg_stream_*` 实际签名一致）：

```python
from wechat_longlink_sdk import SDKConfig, WecomLongLinkClient

client = WecomLongLinkClient(SDKConfig.from_env())
client.start()
start_result = client.aibot_send_msg_stream_start(content="第一段", chatid="your_chat_id")
stream_msgid = start_result["response"]["msgid"]
client.aibot_send_msg_stream_update(content="第二段", msgid=stream_msgid, chatid="your_chat_id")
client.aibot_send_msg_stream_finish(content="结束", msgid=stream_msgid, chatid="your_chat_id")
client.stop()
```

回调应答示例（优先使用公开方法）：

```python
client.aibot_respond_msg(req_id=req_id, content="已收到你的消息", msgtype="markdown")
client.aibot_respond_welcome_msg(req_id=req_id, content="你好，我已上线", msgtype="text")
client.aibot_respond_update_msg(
    req_id=req_id,
    template_card={"card_type": "button_interaction", "main_title": {"title": "处理中"}},
)
```

主动推送场景示例（与 SDK 签名一致）：

```python
# 1) 定时提醒
client.aibot_send_msg(
    chatid="ops_chat",
    msgtype="text",
    content="每日巡检提醒：请在 18:00 前提交结果",
)

# 2) 异步通知（任务结束）
client.aibot_send_msg(
    userid="zhangsan",
    msgtype="markdown",
    content="任务 #A102 已完成，可前往控制台查看详情",
)

# 3) 告警通知（卡片）
client.aibot_send_msg(
    chatid="ops_chat",
    msgtype="template_card",
    template_card={
        "card_type": "button_interaction",
        "main_title": {"title": "P1 告警：支付错误率升高"},
    },
)
```

## 最小长连接测试代码

先配置环境变量：

```bash
set WECHAT_BOT_ID=your_bot_id
set WECHAT_BOT_SECRET=your_secret
```

再直接运行：

```bash
python ws_longlink_probe.py
```

脚本将完成以下最小闭环：
- 连接 `wss://openws.work.weixin.qq.com`
- 自动发送 `aibot_subscribe` 完成鉴权
- 维持 30 秒心跳保活（由 SDK 内置心跳线程执行）
- 收到文本回调后打印 `req_id`、`msgid`、`chatid`、`userid` 并回复确认文本
- 收到 `enter_chat` 事件时触发欢迎语应答
- 按 `Ctrl + C` 触发优雅断开

## BREAKING 迁移说明

- SDK 已统一为 101463 长连接单一路径，不再建议使用并行旧流程口径。
- 主动发送统一使用 `aibot_send_msg`，目标必须二选一：`chatid` 或 `userid`。
- 接收事件统一关注 `aibot_msg_callback` / `aibot_event_callback`，并从事件中读取 `chatid`、`from.userid`、`aibotid` 等字段。
- 建议迁移后仅保留 `SDKConfig + WecomLongLinkClient` 作为主入口，并在连接建立后调用发送与收包方法。
- 历史入口 `BotClient` / `SessionState` 已下线，请按迁移映射替换到 `WecomLongLinkClient` / `LongLinkState`。

## 开发者文档

- [快速开始与最小示例](docs/quickstart.md)
- [API 参考](docs/api-reference.md)
- [能力矩阵与模板](docs/api-capability-matrix.md)
- [迁移说明与替代关系](docs/migration.md)
- [消息类型文档](docs/message-types.md)
- [错误码与最佳实践](docs/error-codes-and-best-practices.md)
