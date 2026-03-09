# 已实现 API 清单与请求响应模板

本文档聚焦两件事：

- 当前 SDK 已实现的 101463 能力清单
- 各能力推荐的请求/响应模板（按 SDK 实际行为）

## 已实现 API 清单

| 分类 | 文档能力 | SDK 入口 | 支持状态 | 关键约束 |
| --- | --- | --- | --- | --- |
| 连接 | `aibot_subscribe` | `start()` / `subscribe()` | 已支持 | 必须提供有效 `bot_id` 与 `secret` |
| 回调接收 | `aibot_msg_callback` | `get_next_event()` | 已支持 | 原始载荷保留在 `event["raw"]` |
| 回调接收 | `aibot_event_callback` | `get_next_event()` | 已支持 | `event_type` 为 `event` |
| 主动发送 | `aibot_send_msg` | `aibot_send_msg()` | 已支持 | `chatid` 与 `userid` 必须二选一 |
| 流式回复 | `start/update/finish` | `aibot_send_msg_stream_start/update/finish()` | 已支持 | `update/finish` 必须携带 `msgid` 与目标 |
| 回调应答 | `aibot_respond_msg` | `aibot_respond_msg()` | 已支持 | 必须提供 `req_id` |
| 欢迎语应答 | `aibot_respond_welcome_msg` | `aibot_respond_welcome_msg()` | 已支持 | 必须提供 `req_id` |
| 卡片更新应答 | `aibot_respond_update_msg` | `aibot_respond_update_msg()` | 已支持 | 必须提供 `req_id` 和 `template_card.card_type` |
| 消息类型支持 | `text/markdown/image/file/template_card` | `aibot_send_msg()` + `aibot_respond_*()` | 已支持 | 媒体消息需提供 `media_id/url/image_url/file_url/file_id` 之一 |
| 事件子类型识别 | `enter_chat/template_card_event/feedback_event/disconnected_event` | `get_next_event()` | 已支持 | 从统一事件 `event_name` 读取 |
| 心跳保活 | ping/pong | SDK 内置心跳线程 | 已支持 | `heartbeat_interval_seconds > 0` |
| 状态观测 | 连接状态查询 | `get_status()` | 已支持 | 仅反映本进程连接状态 |
| 文档 API 目录 | 目录与重试调用 | `DocumentAPIClient` | 受限支持 | 生产接入需自定义 `transport` |

## 示例请求/响应模板

### 1) 建连订阅

请求（协议层）：

```json
{
  "cmd": "aibot_subscribe",
  "headers": {
    "req_id": "REQUEST_ID"
  },
  "body": {
    "bot_id": "aib-xxxx",
    "secret": "******"
  }
}
```

响应（协议层）：

```json
{
  "headers": {
    "req_id": "REQUEST_ID"
  },
  "errcode": 0,
  "errmsg": "ok"
}
```

### 2) 主动发送普通消息

SDK 调用：

```python
result = client.aibot_send_msg(content="你好", chatid="chat_xxx")
```

统一返回模板：

```json
{
  "ok": true,
  "action": "aibot_send_msg",
  "attempt": 1,
  "errcode": 0,
  "errmsg": "ok",
  "payload": {},
  "response": {}
}
```

### 3) 流式回复（start/update/finish）

SDK 调用：

```python
start = client.aibot_send_msg_stream_start(content="第一段", chatid="chat_xxx")
msgid = start["response"]["msgid"]
client.aibot_send_msg_stream_update(content="第二段", msgid=msgid, chatid="chat_xxx")
client.aibot_send_msg_stream_finish(content="完成", msgid=msgid, chatid="chat_xxx")
```

关键语义：

- `start` 与 `update`：`stream.finish=false`
- `finish`：`stream.finish=true`

### 4) 回调应答

SDK 调用：

```python
client.aibot_respond_msg(req_id=req_id, content="已收到", msgtype="markdown")
```

协议层载荷模板：

```json
{
  "cmd": "aibot_respond_msg",
  "headers": {
    "req_id": "CALLBACK_REQ_ID"
  },
  "body": {
    "msgtype": "markdown",
    "markdown": {
      "content": "已收到"
    }
  }
}
```

### 5) 欢迎语应答

SDK 调用：

```python
client.aibot_respond_welcome_msg(req_id=req_id, content="你好，我已上线", msgtype="text")
```

协议层载荷模板：

```json
{
  "cmd": "aibot_respond_welcome_msg",
  "headers": {
    "req_id": "CALLBACK_REQ_ID"
  },
  "body": {
    "msgtype": "text",
    "text": {
      "content": "你好，我已上线"
    }
  }
}
```

### 6) 心跳保活

协议层请求模板：

```json
{
  "cmd": "ping",
  "headers": {
    "req_id": "REQUEST_ID"
  }
}
```

协议层响应模板：

```json
{
  "headers": {
    "req_id": "REQUEST_ID"
  },
  "errcode": 0,
  "errmsg": "ok"
}
```

### 7) 主动推送场景

SDK 调用（定时提醒 / 异步通知 / 告警）：

```python
client.aibot_send_msg(
    chatid="ops_chat",
    msgtype="text",
    content="每日巡检提醒：请在 18:00 前提交结果",
)
client.aibot_send_msg(
    userid="zhangsan",
    msgtype="markdown",
    content="任务 #A102 已完成，可前往控制台查看详情",
)
client.aibot_send_msg(
    chatid="ops_chat",
    msgtype="template_card",
    template_card={
        "card_type": "button_interaction",
        "main_title": {"title": "P1 告警：支付错误率升高"},
    },
)
```

对应协议层关键字段模板（以告警卡片为例）：

```json
{
  "cmd": "aibot_send_msg",
  "headers": {
    "req_id": "REQUEST_ID"
  },
  "body": {
    "chatid": "ops_chat",
    "msgtype": "template_card",
    "template_card": {
      "card_type": "button_interaction",
      "main_title": {
        "title": "P1 告警：支付错误率升高"
      }
    }
  }
}
```

## 使用建议

- 首选 SDK 高层方法（`aibot_send_msg` / `aibot_respond_*`），仅在扩展场景使用 `send_command()`。
- 生产环境固定单 BotID 单活连接，避免被新连接顶下线。
- 对非 `ok` 结果统一记录 `action/errcode/errmsg/attempt` 便于排障。
