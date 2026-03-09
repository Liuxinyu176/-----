# Tasks
- [x] Task 1: 收敛核心连接流程到101463长连接协议
  - [x] SubTask 1.1: 清理或隔离旧短连接与模拟默认路径
  - [x] SubTask 1.2: 校准订阅、心跳、重连状态机与错误返回
  - [x] SubTask 1.3: 统一事件接收模型与关键字段提取

- [x] Task 2: 统一发送与回复接口到aibot_send_msg
  - [x] SubTask 2.1: 定义发送入参与目标约束（chatid 或 userid）
  - [x] SubTask 2.2: 按101463协议组包并映射成功/失败结果
  - [x] SubTask 2.3: 补齐常见失败场景与重试边界

- [x] Task 3: 重构配置与对外API入口
  - [x] SubTask 3.1: 固化 BotID + Secret 必填并保留 api_bot_id 可选
  - [x] SubTask 3.2: 清理旧流程公开方法与过时导出
  - [x] SubTask 3.3: 对外暴露最小可用长连接接口集合

- [x] Task 4: 更新文档与示例为单一路径
  - [x] SubTask 4.1: 更新 README 与快速开始为101463流程
  - [x] SubTask 4.2: 更新 API 参考中的事件与发送说明
  - [x] SubTask 4.3: 标注 BREAKING 迁移说明

- [x] Task 5: 完成验证与回归
  - [x] SubTask 5.1: 新增长连接协议一致性单元测试
  - [x] SubTask 5.2: 增加关键联调日志校验测试
  - [x] SubTask 5.3: 执行全量测试并修复失败项

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 1, Task 2, Task 3, and Task 4
