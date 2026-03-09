# Tasks
- [x] Task 1: 建立目标文档能力对照清单并标注支持状态
  - [x] SubTask 1.1: 解析目标文档中的消息类型、回调事件、回复与推送能力
  - [x] SubTask 1.2: 对照现有 SDK 入口与测试覆盖，标注缺口
  - [x] SubTask 1.3: 输出优先级（P0/P1）与实现顺序

- [x] Task 2: 补齐多消息类型能力并统一参数校验
  - [x] SubTask 2.1: 扩展发送/应答接口支持 text、markdown、image、file、template_card
  - [x] SubTask 2.2: 为各消息类型补齐必填字段校验与错误映射
  - [x] SubTask 2.3: 统一返回模型并更新示例调用

- [x] Task 3: 补齐关键事件回调与卡片更新能力
  - [x] SubTask 3.1: 统一识别 enter_chat、template_card_event、feedback_event、disconnected_event
  - [x] SubTask 3.2: 新增/完善 aibot_respond_update_msg 封装
  - [x] SubTask 3.3: 增加事件字段提取与更新命令回归测试

- [x] Task 4: 更新主动推送与能力文档
  - [x] SubTask 4.1: 更新 API 参考与能力矩阵中的支持状态
  - [x] SubTask 4.2: 补充主动推送场景示例（定时提醒、异步通知、告警）
  - [x] SubTask 4.3: 确保文档示例与 SDK 签名一致

- [x] Task 5: 全量验证并完成收敛
  - [x] SubTask 5.1: 新增/更新单元测试覆盖新增消息类型与事件类型
  - [x] SubTask 5.2: 执行全量 pytest 并修复失败项
  - [x] SubTask 5.3: 复核清单并完成最终对照结论

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 2, Task 3, and Task 4
