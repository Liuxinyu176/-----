# Tasks
- [x] Task 1: 搭建 SDK 基础骨架与配置入口
  - [x] SubTask 1.1: 建立可安装的 Python 包结构与版本管理
  - [x] SubTask 1.2: 设计最小配置模型，仅要求 Bot ID 与 Secret
  - [x] SubTask 1.3: 增加安全凭据注入与日志脱敏能力

- [x] Task 2: 实现长连接生命周期与鉴权机制
  - [x] SubTask 2.1: 实现连接建立、心跳保活、断线重连
  - [x] SubTask 2.2: 实现鉴权握手与会话状态管理
  - [x] SubTask 2.3: 暴露启动、停止、状态查询接口

- [x] Task 3: 封装通用消息接口并支持多消息类型
  - [x] SubTask 3.1: 定义统一消息基类与类型分发机制
  - [x] SubTask 3.2: 实现文本、图片、文件、富媒体、事件等消息模型
  - [x] SubTask 3.3: 提供统一发送与接收回调接口

- [x] Task 4: 对齐官方开发文档并实现全量 API 封装
  - [x] SubTask 4.1: 梳理文档 API 清单并建立映射表
  - [x] SubTask 4.2: 为每个 API 提供统一调用方法与错误映射
  - [x] SubTask 4.3: 增加参数校验、重试策略与异常边界处理

- [x] Task 5: 提供开放 API 与开发者文档
  - [x] SubTask 5.1: 编写快速开始与最小可运行示例
  - [x] SubTask 5.2: 编写 API 参考、消息类型说明与错误码说明
  - [x] SubTask 5.3: 补充接入规范与最佳实践

- [x] Task 6: 建立测试体系并完成验收验证
  - [x] SubTask 6.1: 编写连接流程与消息流程单元测试
  - [x] SubTask 6.2: 编写 API 对齐的集成测试与契约测试
  - [x] SubTask 6.3: 执行测试并修复阻塞问题直至全部通过

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 2
- Task 5 depends on Task 3 and Task 4
- Task 6 depends on Task 2, Task 3, Task 4, and Task 5
