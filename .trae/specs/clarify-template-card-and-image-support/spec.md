# 消息卡片与图片支持约束 Spec

## Why
当前联调中对「模板卡片（template_card）」与「图片/文件」的发送与应答能力边界不够清晰，导致出现应答报错（如 invalid message type）与实现方式理解偏差。

## What Changes
- 梳理并固化 template_card 的发送、回调事件与卡片更新（respond_update_msg）链路
- 明确并在 SDK 行为中体现图片发送/应答的支持边界与降级策略
- 补充语音（voice）消息的基础处理说明与示例
- **BREAKING**：无

## Impact
- Affected specs: 消息类型支持、事件回调处理、主动推送与应答策略、联调脚本输出
- Affected code: `src/wechat_longlink_sdk/longlink.py`、`ws_longlink_probe.py`、相关文档（后续实现阶段更新）

## ADDED Requirements
### Requirement: Template Card 发送与更新
系统 SHALL 提供清晰可复用的方式来发送模板卡片消息，并在收到卡片交互事件时更新卡片内容。

#### Scenario: 发送模板卡片（主动推送）
- **WHEN** 调用发送接口并提供 `msgtype=template_card` 与合法的 `template_card` 结构体
- **THEN** SDK 将构造正确的协议载荷并发送，调用方获得统一的返回结构（ok/response）

#### Scenario: 用户点击卡片按钮触发更新
- **WHEN** 收到 `aibot_event_callback` 且事件类型为 `template_card_event`
- **THEN** 上层可使用 `aibot_respond_update_msg` 更新卡片并收到成功/失败结果

### Requirement: 图片/文件消息下载与解密（联调用途）
系统 SHALL 能在联调脚本中对回调提供的媒体下载 URL 做清洗与下载，并在存在 `aeskey` 时按 AES-256-CBC 解密，再提取可读文本预览（前 10 字符）。

#### Scenario: 文件回调预览（成功解密）
- **WHEN** 收到 `msgtype=file` 且 payload 含 `file.url` 与 `file.aeskey`
- **THEN** 联调脚本输出可读的明文预览；若不可读则输出明确提示而非乱码

### Requirement: 图片应答能力边界与降级
系统 SHALL 对「单聊应答接口」在图片类型不被支持的情况下提供可预期的降级行为。

#### Scenario: 单聊应答图片不支持
- **WHEN** 使用应答接口发送图片且返回 `errcode=40008`（invalid message type）
- **THEN** 系统输出明确日志并自动降级为 markdown 文本提示，不阻断主流程

## MODIFIED Requirements
### Requirement: 多消息类型能力说明与示例
系统 SHALL 在文档与示例中区分「主动推送 aibot_send_msg」与「应答 aibot_respond_msg」的适用场景与限制，并给出最小可运行示例。

## REMOVED Requirements
无

