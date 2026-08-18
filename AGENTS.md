# Agent Home 项目规则

本文是仓库内 Agent 的根入口。项目不依赖任何 Agent Home 插件或全局安装；仓库自身携带可选的
Task/Loop/Run 工作协议。

## 启动顺序

1. 读取 `PROJECT.md`，再读取与请求直接相关的源码、测试、`docs/` 或 `reports/`。
2. 若 `PROJECT.md` 含 `agent-home-template:uninitialized` 标记，使用 `bootstrap-project` Skill 完成首次初始化。
3. 若用户请求已经给出项目目标，直接据此初始化；目标仍不明确时只问一个必要问题。
4. 初始化后直接处理用户请求。一次性工作直接完成；长期、多阶段、需要跨会话恢复或验证假设的工作使用
   `task-loop-run` Skill。

## 信息与所有权

- `AGENTS.md` 保存始终生效的工作规则。
- `PROJECT.md` 保存项目身份、目标、范围、约束和常用命令，不保存逐次工作状态。
- `.agents/skills/` 保存按需加载的领域工作流。Skill 的触发条件写在 `description` 中。
- `tasks/` 保存按需创建的 Task/Loop/Run 恢复真值；不是每个请求都要创建 Task。
- `docs/` 保存面向使用者的设计和说明。
- `reports/` 只保存跨会话仍有价值、且有源码、测试或原始产物支撑的结论。
- `tests/` 保存机器可复验的项目判据。
- `.claude/skills/` 只保存转读 `.agents/skills/` 的 Claude Code 发现 wrapper，不维护第二份工作流。

## 工作方式

- 理解项目时先只读确认 Git 根、当前分支、工作树、权威文件、实现边界和验证入口。
- 修改时只触碰请求范围内的文件，保留用户已有改动，不清理不相关的 dirty worktree。
- 优先使用仓库已有构建、测试、格式化和诊断入口；没有入口时再添加最小工具。
- 结论按证据强度表述：区分静态检查、机器测试、真实运行、性能测量和外部交付。
- 行为正确性、性能和安全边界需要与主张相称的验证；不能把命令退出码或旧产物当成充分证据。
- 做事的会话不能签署自己的独立接受。确需独立评审时，由用户启动可区分的顶层会话。

## Task / Loop / Run

- Task 管长期目标，Loop 管一个可证伪方向或阶段，Run 管一次具体执行结果。
- 目标、范围或验收仍模糊时使用 `design-grill`，不要带着迷雾直接实施。
- Task、Loop 或 Run 打开、恢复、遇到关键结果或阻塞时使用 `next-action`，只选择一个当前可执行动作。
- 只有会改变下一步、支撑结论或用于恢复与交接的事实才使用 `evidence-checkpoint`。
- Run 的 `contract.json` 打开后保持不变；执行偏差进入 checkpoint 或 `result.json`，不要改写合同制造通过。
- 不生成 `status.md`、会话日志、强制签名、晋升状态、插件锁或空证据文件。
- 创建、关闭或校验记录使用
  `.agents/skills/task-loop-run/scripts/workflow.py`，不要手工分配序号。

## Git 与外部动作

- 可以为当前请求做本地、可恢复的编辑和验证。
- commit 前检查 staged diff；提交信息使用一行英文，描述工程结果，不写 Agent、模型或会话信息。
- push、创建 PR/MR、发布、改写远端历史、发送消息或配置外部系统，都需要用户明确授权。
- 首次初始化不得自动删除模板 `origin`、创建远端仓库或重写 Git 历史。

## 写作与安全

- 默认使用简体中文写项目文档；代码标识符、路径、命令和外部 API 名称保持原样。
- 不在文档、日志或聊天中保存 token、cookie、私钥、密码或其他凭据内容。
- 不把提示词、内部推理、Agent/模型身份或工具轨迹写入源码、提交、PR/MR 或对外材料。
- 不建立全局 todo、会话日志或第二份项目规则入口。新的稳定规则直接更新本文件。

## 验证

模板契约使用标准库测试验证：

```bash
python -m unittest discover -s tests -v
```

项目初始化后，应在 `PROJECT.md` 补充项目自己的构建、测试和检查命令。
