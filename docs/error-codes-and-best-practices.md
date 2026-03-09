# 错误码与最佳实践

## 错误模型

SDK 以异常为主，错误码为辅：

- `SDKConfigError`：配置错误（如 bot_id 或 secret 缺失）
- `APIError`：API 调用基类异常
- `APINotFoundError`：API 名称不存在
- `APIParameterValidationError`：参数缺失、类型错误或取值非法
- `APITransportError`：传输层异常
- `APIRetryExhaustedError`：重试后仍失败

## 错误码参考

### 参数与定义类

| 错误码 | 触发场景 | 对应异常 |
| --- | --- | --- |
| api_not_found | 调用未注册 API 名称 | APINotFoundError |
| missing_required_params | 缺少必填参数 | APIParameterValidationError |
| unknown_params | 传入未定义参数 | APIParameterValidationError |
| invalid_parameter | 参数类型或取值不符合约束 | APIParameterValidationError |

### 传输与重试类

| 错误码 | 触发场景 | 对应异常 |
| --- | --- | --- |
| transport_error | 传输调用抛出非 API 异常 | APITransportError |
| timeout | 调用超时且返回错误码 | APIRetryExhaustedError |
| rate_limited | 被限流 | APIRetryExhaustedError |
| server_busy | 服务端繁忙 | APIRetryExhaustedError |
| retry_exhausted | 无明确错误码但重试结束 | APIRetryExhaustedError |

说明：`timeout`、`rate_limited`、`server_busy`、`transport_error` 属于可重试错误码，受 `APIRetryPolicy` 控制。

## 异常处理示例

```python
from wechat_longlink_sdk import (
    APIParameterValidationError,
    APIRetryExhaustedError,
    BotClient,
    SDKConfig,
)

client = BotClient(SDKConfig(bot_id="your_bot_id", secret="your_secret"))
client.start()

try:
    client.call_api("message.send_text", {"conversation_id": "conv_001", "content": "hello"})
except APIParameterValidationError as exc:
    print("参数错误:", exc.error_code, exc.details)
except APIRetryExhaustedError as exc:
    print("调用失败:", exc.error_code, exc.details)
finally:
    client.stop()
```

## 最佳实践

- 使用环境变量注入 `BOT_ID` 和 `BOT_SECRET`，避免凭据硬编码。
- 在应用生命周期中只维护一个 `BotClient` 实例，减少重复连接开销。
- 先 `start()` 再发消息或调用 API，退出前始终 `stop()`。
- 对 `APIRetryExhaustedError` 记录 `details["errors"]`，用于故障排查。
- 将 `conversation.history.list` 的 `limit` 控制在合理区间，避免无效请求。
- 使用 `subscribe_message` 按消息类型拆分处理函数，降低业务耦合。
