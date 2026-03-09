# 企业微信机器人最小长连接测试代码 Spec

## Why
用户需要一个可直接运行的最小测试代码，用于快速验证企业微信机器人长连接（WebSocket）是否可用。当前仓库虽有完整 SDK 能力，但缺少“开箱即测”的极简验证入口。

## What Changes
- 新增一个最小可运行测试脚本，覆盖连接、订阅鉴权、消息接收与最小回复闭环
- 统一采用环境变量注入 BotID 与 Secret，避免在代码中硬编码凭据
- 在示例中明确心跳保活与优雅断开行为，便于本地联调与排障
- 补充最小运行说明（安装、配置、启动、预期输出）

## Impact
- Affected specs: 长连接接入体验、快速验证能力、凭据安全实践
- Affected code: 示例脚本目录、README/快速开始相关章节、必要的测试验证文件

## ADDED Requirements
### Requirement: 最小长连接测试脚本
系统 SHALL 提供一个最小测试脚本，使开发者仅配置 BotID 与 Secret 即可建立到 `wss://openws.work.weixin.qq.com` 的长连接并完成订阅鉴权。

#### Scenario: 启动并鉴权成功
- **WHEN** 开发者设置有效的 BotID 与 Secret 并启动最小测试脚本
- **THEN** 脚本成功建立 WebSocket 连接并发送 `aibot_subscribe`
- **THEN** 收到 `errcode=0` 的订阅成功响应并进入可接收消息状态

#### Scenario: 收到文本后最小回复
- **WHEN** 脚本收到 `aibot_msg_callback` 且 `msgtype=text`
- **THEN** 能打印关键字段（req_id、msgid、chatid、from.userid）
- **THEN** 以最小回复接口返回一条文本确认消息，形成闭环验证

### Requirement: 心跳与安全基线
系统 SHALL 在最小测试脚本中体现心跳保活与凭据安全基线。

#### Scenario: 心跳保活
- **WHEN** 连接保持期间达到心跳周期（默认 30 秒）
- **THEN** 脚本发送心跳并在异常时触发可观测日志

#### Scenario: 凭据安全
- **WHEN** 开发者运行或查看日志
- **THEN** Secret 不以明文写入示例源码与日志输出

## MODIFIED Requirements
### Requirement: 快速开始最小示例
现有快速开始能力 SHALL 增补“最小长连接测试代码”入口，突出“仅凭 BotID+Secret 可完成联调验证”的路径，并给出运行前置条件和预期日志。

## REMOVED Requirements
### Requirement: 无
**Reason**: 本次为增量补充，不移除既有能力。
**Migration**: 无需迁移。
