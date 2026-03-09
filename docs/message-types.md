# 消息类型文档

## 通用消息结构

所有消息类型均继承 `BaseMessage`，公共字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| type | str | 消息类型标识 |
| message_id | str | 消息唯一 ID，默认自动生成 |
| timestamp | float | 时间戳，默认自动写入 |
| metadata | dict | 扩展元数据 |

## 内置消息类型

### text

类名：`TextMessage`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| content | str | 是 | 文本内容，不能为空 |

示例：

```python
from wechat_longlink_sdk import TextMessage

message = TextMessage(content="hello")
payload = message.to_payload()
```

### image

类名：`ImageMessage`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| image_url | str | 是 | 图片 URL，不能为空 |
| caption | str \| None | 否 | 图片说明 |

### file

类名：`FileMessage`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| file_name | str | 是 | 文件名 |
| file_url | str | 是 | 文件 URL |
| file_size | int \| None | 否 | 文件大小，不能为负数 |
| mime_type | str \| None | 否 | 文件 MIME 类型 |

### rich_media

类名：`RichMediaMessage`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| title | str | 是 | 标题 |
| description | str | 是 | 描述 |
| resource_url | str | 是 | 资源链接 |
| thumbnail_url | str \| None | 否 | 缩略图链接 |

### event

类名：`EventMessage`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| event_name | str | 是 | 事件名 |
| event_data | dict | 否 | 事件数据 |

## 入站消息解析

使用 `message_from_payload(payload)` 可将字典负载反序列化为对应消息类实例。

```python
from wechat_longlink_sdk import message_from_payload

payload = {"type": "text", "content": "hello"}
message = message_from_payload(payload)
```

## 消息扩展机制

可通过 `register_message_type(message_type, message_class)` 注册自定义消息类型映射。
