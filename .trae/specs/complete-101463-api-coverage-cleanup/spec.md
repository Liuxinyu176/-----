# 企业微信101463全量API封装与清理 Spec

## Why
当前仓库虽已完成长连接主路径，但尚未对齐 101463 文档中的全部可用 API 能力，且存在历史遗留/重复文件，增加维护成本与接入歧义。需要一次性完成 API 能力补齐与废弃资产清理，形成单一、完整、可维护实现。

## What Changes
- 补齐并统一封装 101463 文档中的消息回调、事件回调、回复消息、主动推送、心跳保活相关 API 能力。
- 统一请求/响应模型与错误映射，确保每个 API 的参数校验、返回结构、失败可判定。
- 明确流式回复机制（start/update/finish）与普通回复机制的接口边界。
- 增加 API 能力矩阵文档，标注“已支持/不适用/受限”并给出原因。
- 删除不需要或已废弃的文件、入口与文档片段，保留单一路径实现。
- **BREAKING**: 移除旧入口或旧命名别名后，仅保留规范化 API 与推荐调用路径。

## Impact
- Affected specs: 长连接连接管理、消息发送与回复、事件处理、文档与示例规范、清理策略。
- Affected code: `src/wechat_longlink_sdk/*`、`ws_longlink_probe.py`、`tests/*`、`docs/*`、`README.md`。

## Task 1 交付：101463 API 能力清单与现状缺口

### 能力清单与差异表

| 分类 | 101463 能力项 | 当前仓库入口 | 现状 | 缺口说明 |
| --- | --- | --- | --- | --- |
| 连接 | `aibot_subscribe` 建链鉴权订阅 | `WecomLongLinkClient.start()` / `subscribe()` | 已支持 | 已实现自动连接、订阅与重连。 |
| 回调 | `aibot_msg_callback` 消息回调接收 | `get_next_event()` / `_to_unified_event()` | 已支持 | 已统一 `event/msgid/chatid/userid/aibotid` 字段。 |
| 回调 | `aibot_event_callback` 事件回调接收 | `get_next_event()` / `_to_unified_event()` | 已支持 | 已覆盖事件收包与统一事件模型。 |
| 回复 | `aibot_send_msg` 主动推送与会话内回复 | `aibot_send_msg()` | 已支持 | 支持 `chatid/userid` 二选一、`msgid` 关联与重试。 |
| 回复 | `aibot_send_msg` 流式回复 `start/update/finish` | `aibot_send_msg(stream, finish)` | 部分支持 | 仅提供布尔开关，缺少阶段化语义封装与便捷入口。 |
| 回复 | `aibot_respond_msg` 应答接口 | `send_command(payload)` | 部分支持 | 仅原始命令方式可用，缺少强类型封装与参数校验。 |
| 回复 | `aibot_respond_welcome_msg` 欢迎语应答 | `send_command(payload)` | 部分支持 | 仅脚本示例可用，SDK 未提供独立公开方法。 |
| 心跳 | WebSocket 心跳与保活 | `_heartbeat_loop()` | 已支持 | 已有定时 ping 与失败触发重连。 |
| 观测 | 状态与错误观测 | `get_status()` | 已支持 | 可观测连接状态、重连次数、最近错误。 |

### 实现优先级与兼容策略

| 优先级 | 范围 | 落地策略 | 兼容策略 |
| --- | --- | --- | --- |
| P0 | `aibot_respond_msg`、`aibot_respond_welcome_msg` | 在 `WecomLongLinkClient` 增加公开封装方法，补齐参数校验与统一返回 | 保留 `send_command` 原能力，新增方法作为推荐路径。 |
| P1 | 流式回复阶段化封装 | 在 `aibot_send_msg` 之上增加 `start/update/finish` 便捷接口 | 保留当前 `stream/finish` 参数，新增语义化入口向后兼容。 |
| P2 | 能力矩阵与示例一致性 | 将能力状态同步到 `docs/api-reference.md` 与示例脚本 | 文档优先，旧表述标注迁移路径后移除。 |

## ADDED Requirements
### Requirement: 全量 API 能力映射
系统 SHALL 提供与 101463 文档一致的 API 能力封装，并形成可验证映射清单。

#### Scenario: API 能力可追溯
- **WHEN** 开发者查看能力矩阵
- **THEN** 可看到每个 API 的封装入口、参数约束、返回结构与验证状态

### Requirement: 废弃资产清理机制
系统 SHALL 在不破坏当前可用主链路前提下清理废弃/重复资产，并提供迁移说明。

#### Scenario: 清理后可平滑迁移
- **WHEN** 开发者升级到新版本
- **THEN** 能依据迁移说明完成替换，且核心用例可运行

## MODIFIED Requirements
### Requirement: 长连接 API 对外接口一致性
现有对外接口必须统一为“文档优先”的命名、行为和错误语义，禁止同一能力存在多个互斥实现路径。

## REMOVED Requirements
### Requirement: 历史兼容入口长期保留
**Reason**: 该要求导致文档与实现分叉，增加误用概率与维护负担。  
**Migration**: 提供旧入口到新入口映射表，保留有限过渡期并在文档中明确替代方案。
