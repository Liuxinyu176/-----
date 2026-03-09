# Tasks
- [x] Task 1: 建立 101463 API 能力清单与现状差异表
  - [x] SubTask 1.1: 列出文档中的连接、回调、回复、推送、心跳 API
  - [x] SubTask 1.2: 标注仓库现有实现与缺口
  - [x] SubTask 1.3: 形成“实现优先级与兼容策略”

- [x] Task 2: 补齐核心 API 封装与统一返回模型
  - [x] SubTask 2.1: 完成缺失 API 封装入口与参数校验
  - [x] SubTask 2.2: 统一成功/失败返回结构与错误映射
  - [x] SubTask 2.3: 对齐流式回复与普通回复行为边界

- [x] Task 3: 清理不需要或废弃文件并收敛单一路径
  - [x] SubTask 3.1: 识别冗余脚本、历史入口、过时文档段落
  - [x] SubTask 3.2: 删除确认废弃文件并修正引用
  - [x] SubTask 3.3: 输出迁移说明与替代关系

- [x] Task 4: 更新文档与示例到全量能力视图
  - [x] SubTask 4.1: 更新 README 与 API 参考
  - [x] SubTask 4.2: 增加能力矩阵（支持状态、限制、示例）
  - [x] SubTask 4.3: 校验示例与实际 SDK 行为一致

- [x] Task 5: 完成验证与回归
  - [x] SubTask 5.1: 增加/更新单元测试覆盖新增 API
  - [x] SubTask 5.2: 增加关键协议路径与错误场景测试
  - [x] SubTask 5.3: 执行测试并修复失败项直至通过

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 2, Task 3, and Task 4
