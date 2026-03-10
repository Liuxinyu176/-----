# Tasks
- [ ] Task 1: 梳理并固化 template_card 实现链路
  - [ ] SubTask 1.1: 明确 template_card 发送参数要求与典型 payload 结构
  - [ ] SubTask 1.2: 明确 template_card_event 回调字段与更新卡片请求结构
  - [ ] SubTask 1.3: 在 SDK 与联调脚本中补齐最小示例（发送/更新）

- [ ] Task 2: 明确图片发送/应答支持边界并加固降级策略
  - [ ] SubTask 2.1: 对应答接口图片失败（40008）输出可诊断日志并降级
  - [ ] SubTask 2.2: 区分单聊应答与群聊/主动推送的图片发送路径

- [ ] Task 3: 文件/图片下载解密与预览能力收敛
  - [ ] SubTask 3.1: URL 清洗、下载失败处理与超时策略
  - [ ] SubTask 3.2: AES-256-CBC 解密与 PKCS#7 去填充校验
  - [ ] SubTask 3.3: 对不可读二进制内容输出稳定提示

- [ ] Task 4: 文档化与回归验证
  - [ ] SubTask 4.1: 更新消息类型文档与 quickstart 示例（实现阶段）
  - [ ] SubTask 4.2: 增加最小回归用例（语音/文件/图片/卡片事件）

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 1, Task 2, and Task 3

