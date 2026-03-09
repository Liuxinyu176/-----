# Tasks
- [x] Task 1: 实现最小长连接测试脚本
  - [x] SubTask 1.1: 基于现有 SDK 新增最小可运行示例入口
  - [x] SubTask 1.2: 接入连接、订阅鉴权、文本消息接收与最小回复
  - [x] SubTask 1.3: 增加心跳保活与优雅断开流程

- [x] Task 2: 加固示例的凭据与日志安全
  - [x] SubTask 2.1: 改为环境变量读取 BotID 与 Secret
  - [x] SubTask 2.2: 确保示例与日志无 Secret 明文输出

- [x] Task 3: 更新最小运行文档
  - [x] SubTask 3.1: 补充安装与启动步骤
  - [x] SubTask 3.2: 补充必需环境变量与示例命令
  - [x] SubTask 3.3: 补充预期日志与排障提示

- [x] Task 4: 完成可验证验收
  - [x] SubTask 4.1: 增加/更新与最小示例相关测试
  - [x] SubTask 4.2: 执行测试并修复失败项
  - [x] SubTask 4.3: 记录最终验证结果

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1 and Task 2
- Task 4 depends on Task 1, Task 2, and Task 3
