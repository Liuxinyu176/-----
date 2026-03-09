# 企业微信101463长连接单一化 Spec

## Why
当前仓库同时存在旧的模拟流程与多套接口语义，导致“已连接但收不到消息”与调用口径不一致。  
需要严格收敛到企业微信文档 101463 的长连接模式，统一协议、事件与发送逻辑，降低联调歧义。

## What Changes
- 保留并强化基于 `wss://openws.work.weixin.qq.com` 的长连接实现（`aibot_subscribe` / `aibot_send_msg` / 心跳）。
- 移除或下线旧的短连接回调思路、模拟传输默认行为与非 101463 协议字段映射。
- 将接收事件、发送消息、状态管理全部按 101463 协议字段重构（`aibot_msg_callback`、`aibot_event_callback` 等）。
- 统一配置入口：`BotID + Secret` 为必填，`api_bot_id` 为可选增强字段。
- 更新文档、示例、测试为“仅长连接模式”。
- **BREAKING**：废弃旧流程 API（含与 101463 不一致的调用约定）。

## Impact
- Affected specs: 长连接接入、消息接收与主动发送、配置模型、文档与测试
- Affected code: `src/wechat_longlink_sdk/longlink.py`、`src/wechat_longlink_sdk/client.py`、`src/wechat_longlink_sdk/api_client.py`、`src/wechat_longlink_sdk/config.py`、`docs/*`、`tests/*`

## ADDED Requirements
### Requirement: 仅支持101463长连接主流程
系统 SHALL 仅实现并暴露 101463 文档定义的长连接能力，不再提供并行旧流程入口。

#### Scenario: 建连订阅成功
- **WHEN** 用户提供有效 BotID 与 Secret 启动客户端
- **THEN** 客户端建立 WebSocket 长连接并成功完成 `aibot_subscribe`

### Requirement: 协议事件按101463原生结构透出
系统 SHALL 对接收消息与事件回调按原生字段透出并可订阅处理。

#### Scenario: 收到用户消息回调
- **WHEN** 企业微信侧产生 `aibot_msg_callback`
- **THEN** SDK 可读到 `msgid`、`chatid`、`from.userid`、`aibotid` 等关键字段并进入统一事件分发

### Requirement: 主动发送按101463执行
系统 SHALL 通过 `aibot_send_msg` 完成主动推送与普通回复能力。

#### Scenario: 主动向群或用户发送
- **WHEN** 调用发送接口并提供 `chatid` 或 `userid`
- **THEN** SDK 组装并发送符合协议的数据包，返回明确成功或失败信息

### Requirement: 心跳与重连可靠可观测
系统 SHALL 提供心跳保活、断线重连与状态可观测能力。

#### Scenario: 网络抖动恢复
- **WHEN** 连接中断或 ping 失败
- **THEN** SDK 自动重连并重新订阅，状态与错误可查询

## MODIFIED Requirements
### Requirement: 配置模型聚焦长连接
配置模型 SHALL 以 `BotID + Secret` 为核心，`api_bot_id` 仅作为可选字段；与短连接 URL/Token/AESKey 相关语义不再作为主路径。

## REMOVED Requirements
### Requirement: 并行旧流程兼容层
**Reason**: 并行流程导致协议口径混乱，影响真实联调稳定性。  
**Migration**: 统一迁移到长连接客户端；发送统一改为长连接消息发送接口；删除旧流程调用代码与文档示例。
