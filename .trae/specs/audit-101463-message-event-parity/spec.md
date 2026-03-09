# 101463 消息与事件能力对照补齐 Spec

## Why
当前仓库已完成长连接主链路，但需要严格对照 `docs/企业微信智能机器人长连接API文档.md` 逐项核验“是否已支持”，并补齐多消息类型、关键回调事件与卡片更新能力，避免能力口径与官方文档不一致。

## What Changes
- 基于目标文档建立“能力对照表”，逐项标注：已支持/部分支持/未支持/不适用。
- 补齐多消息类型支持（至少覆盖 text、markdown、image、file、template_card 的发送与应答约束）。
- 补齐并统一事件回调识别：`enter_chat`、`template_card_event`、`feedback_event`、`disconnected_event`。
- 增加 `aibot_respond_update_msg` 封装，用于模板卡片点击后的卡片内容更新。
- 明确主动推送 `aibot_send_msg` 的使用规范与场景（定时提醒、异步任务通知、告警推送）。
- 更新 README / API 参考 / 能力矩阵与模板文档，确保与实现一致。
- **BREAKING**: 统一消息类型参数与事件模型字段命名，移除不一致的旧文档描述。

## Impact
- Affected specs: 消息类型能力、事件回调能力、卡片更新能力、主动推送能力、文档一致性。
- Affected code: `src/wechat_longlink_sdk/longlink.py`、`src/wechat_longlink_sdk/messages.py`、`ws_longlink_probe.py`、`tests/*`、`docs/api-reference.md`、`docs/api-capability-matrix.md`、`README.md`。

## Task 1 输出：目标文档能力对照清单
对照基线：`docs/企业微信智能机器人长连接API文档.md`

| 能力项 | 目标文档能力 | 当前 SDK 入口 | 测试覆盖 | 支持状态 | 缺口说明 | 优先级 | 实现顺序 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 连接订阅 | `aibot_subscribe` 建连鉴权 | `start()` / `subscribe()` | `tests/test_longlink_client.py` | 已支持 | 无 | P0 | 1 |
| 消息回调接收 | `aibot_msg_callback`（text/image/mixed/voice/file） | `get_next_event()` | `tests/test_longlink_client.py`、`tests/test_ws_longlink_probe.py` | 部分支持 | 仅统一透传，缺少按 msgtype 的标准化字段模型与类型化辅助 | P1 | 5 |
| 事件回调接收 | `aibot_event_callback`（enter_chat/template_card_event/feedback_event/disconnected_event） | `get_next_event()` | `tests/test_longlink_client.py`、`tests/test_ws_longlink_probe.py` | 部分支持 | 缺少 `template_card_event`、`feedback_event` 的统一字段提取与高层识别接口 | P0 | 3 |
| 回调应答 | `aibot_respond_msg` | `aibot_respond_msg()` | `tests/test_longlink_client.py`、`tests/test_task5_regression.py` | 部分支持 | 当前仅支持 `text/markdown`，未覆盖 `stream`、`template_card` 等扩展体裁 | P0 | 2 |
| 欢迎语应答 | `aibot_respond_welcome_msg` | `aibot_respond_welcome_msg()` | `tests/test_longlink_client.py`、`tests/test_ws_longlink_probe.py` | 已支持 | 无 | P0 | 4 |
| 模板卡片更新 | `aibot_respond_update_msg` | 无 | 无 | 未支持 | 缺少接口封装、参数校验与回归测试 | P0 | 2 |
| 主动推送 | `aibot_send_msg`（markdown/template_card） | `aibot_send_msg()` | `tests/test_longlink_client.py` | 部分支持 | 当前发送体固定 markdown，未支持 `template_card` 数据结构 | P0 | 2 |
| 心跳保活 | `ping` 心跳保活 | 内置心跳线程 | `tests/test_longlink_client.py` | 部分支持 | 当前使用 websocket ping 帧，未提供协议层 `cmd=ping` 请求封装 | P1 | 6 |

### Task 1 结论
- P0（先做）：多消息类型发送/应答扩展、`aibot_respond_update_msg`、关键事件识别补齐。
- P1（后做）：消息回调按类型结构化、协议层心跳命令封装与文档细化。
- 推荐迭代顺序：消息与卡片发送能力 → 关键事件识别 → 文档与测试收敛。

## ADDED Requirements
### Requirement: 文档对照可追溯
系统 SHALL 提供基于目标文档的能力对照结果，并可追溯到 SDK 入口与测试覆盖。

#### Scenario: 对照审计通过
- **WHEN** 开发者查看能力对照文档
- **THEN** 可看到每项能力的支持状态、限制、入口与测试位置

### Requirement: 关键事件全覆盖识别
系统 SHALL 统一识别并透传 `enter_chat`、`template_card_event`、`feedback_event`、`disconnected_event` 事件。

#### Scenario: 事件回调进入统一模型
- **WHEN** 收到上述任一事件回调
- **THEN** 事件名称、req_id、msgid、chatid、userid 与原始载荷均可稳定获取

### Requirement: 模板卡片更新能力
系统 SHALL 提供 `aibot_respond_update_msg` 封装，用于模板卡片点击事件后的卡片更新。

#### Scenario: 卡片点击后更新成功
- **WHEN** 收到 `template_card_event` 且调用更新接口
- **THEN** 正确下发 `aibot_respond_update_msg` 并返回统一结果结构

## MODIFIED Requirements
### Requirement: 消息发送与应答类型支持
现有发送/应答接口必须支持多消息类型，并在参数层明确不同类型的必填字段与互斥规则。

## REMOVED Requirements
### Requirement: 文档与实现可存在局部差异
**Reason**: 差异会导致接入方误判能力并引发联调失败。  
**Migration**: 以能力矩阵与 API 参考为唯一口径，旧描述统一迁移到新字段与新接口说明。
