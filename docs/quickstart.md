# 快速开始

本指南仅覆盖企业微信 101463 长连接单一路径（`aibot_subscribe` / `aibot_send_msg` / 回调事件接收）。

## 1. 安装

```bash
pip install -e .
```

## 2. 准备配置

### 方式 A：代码传入

```python
from wechat_longlink_sdk import SDKConfig

config = SDKConfig(
    bot_id="your_bot_id",
    secret="your_secret",
    heartbeat_interval_seconds=30.0,
    reconnect_interval_seconds=5.0,
    max_reconnect_attempts=0,
)
```

### 方式 B：环境变量注入

```bash
set WECHAT_BOT_ID=your_bot_id
set WECHAT_BOT_SECRET=your_secret
set WECHAT_API_BOT_ID=33777000151280519
set BOT_ID=your_bot_id
set BOT_SECRET=your_secret
```

```python
from wechat_longlink_sdk import SDKConfig

config = SDKConfig.from_env()
```

## 3. 启动与停止客户端

```python
from wechat_longlink_sdk import SDKConfig, WecomLongLinkClient

config = SDKConfig(bot_id="your_bot_id", secret="your_secret")
client = WecomLongLinkClient(config)

client.start()
print(client.get_status())
client.stop()
```

## 4. 使用真实长连接发送消息

```python
from wechat_longlink_sdk import SDKConfig, WecomLongLinkClient

config = SDKConfig.from_env()
client = WecomLongLinkClient(config)
client.start()
client.aibot_send_msg(content="长连接发送测试", chatid="your_chat_id")
client.stop()
```

## 最小可运行示例

最小测试脚本已提供：`ws_longlink_probe.py`。

Windows 下可直接执行：

```bash
set WECHAT_BOT_ID=your_bot_id
set WECHAT_BOT_SECRET=your_secret
python ws_longlink_probe.py
```

运行后预期输出：
- 启动最小长连接测试与心跳间隔
- 订阅成功并进入等待回调状态
- 收到文本时打印 `req_id`、`msgid`、`chatid`、`userid`
- 自动回发最小确认消息
- `Ctrl + C` 后输出优雅断开日志

## 运行建议

- 生产环境优先使用 `SDKConfig.from_env()` 注入凭据。
- 环境变量优先级：`WECHAT_*` > `WECOM_*` > `BOT_*`，可选 `WECHAT_API_BOT_ID` 用于指定 API 中的机器人标识。
- 请勿在源码或日志中输出 Secret 明文。
- 调用 `start()` 后再调用 `aibot_send_msg()` 或 `send_command()`。
- 退出应用前调用 `stop()`，避免心跳线程残留。

## BREAKING 迁移说明

- 旧的并行调用口径已下线到非主路径，快速开始仅保留 101463 长连接流程。
- 发送接口统一为 `aibot_send_msg`，请将历史发送逻辑迁移为 `chatid` 或 `userid` 单目标发送。
- 接收处理统一迁移到 `get_next_event()` 返回事件，按 `event` 字段区分消息回调与事件回调。
