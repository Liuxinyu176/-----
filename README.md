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
- 按 `Ctrl + C` 触发优雅断开

## BREAKING 迁移说明

- SDK 已统一为 101463 长连接单一路径，不再建议使用并行旧流程口径。
- 主动发送统一使用 `aibot_send_msg`，目标必须二选一：`chatid` 或 `userid`。
- 接收事件统一关注 `aibot_msg_callback` / `aibot_event_callback`，并从事件中读取 `chatid`、`from.userid`、`aibotid` 等字段。
- 建议迁移后仅保留 `SDKConfig + WecomLongLinkClient` 作为主入口，并在连接建立后调用发送与收包方法。

## 开发者文档

- [快速开始与最小示例](docs/quickstart.md)
- [API 参考](docs/api-reference.md)
- [消息类型文档](docs/message-types.md)
- [错误码与最佳实践](docs/error-codes-and-best-practices.md)
