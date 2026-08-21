# Agent Home 项目规则

本文是仓库内 Agent 的根入口。项目不依赖任何 Agent Home 插件或全局安装；仓库自身携带可选的
Task/Loop/Run 工作协议。

## 术语（全局强制，任何时候都适用）

- 使用标准术语，不造黑话。不用自己理解、概括或临时发明的说法替代已有概念，以教科书、官方文档、
  目标仓源码和任务书中的既有名称为准。
- 适用范围不因场合非正式而放宽：代码标识符、注释、文档、提交信息、Task/Loop/Run 记录、报告和对话
  汇报一律适用。
- 不确定标准叫法时先查上述来源，不靠语感造词。
- 确需新造名称时明确标注为自定义命名，给出定义，并指明它对应的标准概念。
- 遇到既有的私有简称、比喻式命名或黑话，替换为标准术语。

## 启动顺序

1. 读取 `PROJECT.md`，再读取与请求直接相关的源码、测试、`docs/` 或 `reports/`。
2. 若目录还没有 `AGENTS.md` 与 `.agent-home/manifest.json`，而用户要求用 agent-home 管理这个项目，
   使用 `agent-home-sync` Skill 完成安装。
3. 若 `PROJECT.md` 含 `agent-home-template:uninitialized` 标记，使用 `bootstrap-project` Skill 完成首次初始化。
4. 若用户请求已经给出项目目标，直接据此初始化；目标仍不明确时只问一个必要问题。
5. 初始化后直接处理用户请求。一次性工作直接完成；长期、多阶段、需要跨会话恢复或验证假设的工作使用
   `task-loop-run` Skill（技能）。

## 信息与所有权

- `AGENTS.md` 保存始终生效的工作规则。
- `PROJECT.md` 保存项目身份、目标、范围、约束和常用命令，不保存逐次工作状态。
- `.agents/skills/` 保存按需加载的领域工作流。Skill 的触发条件写在 `description` 中。
- `tasks/` 保存按需创建的 Task/Loop/Run 恢复真值；不是每个请求都要创建 Task。
- `.code/` 保存被操作的目标代码仓；本仓忽略它，代码由各代码仓自己提交管理。
- `docs/` 保存面向使用者的设计和说明。
- `reports/` 只保存跨会话仍有价值、且有源码、测试或原始产物支撑的结论。
- `tests/` 保存机器可复验的项目判据。
- `.claude/skills/` 只保存转读 `.agents/skills/` 的 Claude Code 发现包装层，不维护第二份工作流。
- `.agent-home/manifest.json` 保存模板来源、版本和受管理文件清单；`.agent-home/upstream/` 是模板仓
  本地缓存，不提交。

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
- Task 的方向空间保存在 `tasks/<task>/graph.json`：节点是方向、功能构成或未知问题，`requires` 边给出
  前置依赖，图随新证据更新。
- Task、Loop 或 Run 打开、恢复、遇到关键结果或阻塞时使用 `next-action`：先重算就绪集合，只在就绪
  节点里选择一个当前可执行动作。图由 Agent 直接编辑，`workflow.py` 只做前置门禁与结构校验。
- 放弃或暂缓一个方向必须记录复活条件，这些节点留在图上，每次重算就绪集合时都要重新复核。
- 只有会改变下一步、支撑结论或用于恢复与交接的事实才使用 `evidence-checkpoint`。
- Run 的 `contract.json` 打开后保持不变；执行偏差进入 checkpoint 或 `result.json`，不要改写合同制造通过。
- 不生成 `status.md`、会话日志、强制签名、晋升状态、插件锁或空证据文件。
- 创建、关闭或校验记录使用
  `.agents/skills/task-loop-run/scripts/workflow.py`，不要手工分配序号。

## 代码仓与工作区

- 被操作的目标代码仓放在 `.code/<repo>/`，每个都是独立 Git 仓库。本仓忽略 `.code/`，不把目标代码
  仓的文件、产物或提交带进本仓历史。
- 一个 Task 在目标代码仓上对应一个分支 `task/<task-id>`，代码改动在该分支上由代码仓自己提交。
- 使用 `add-repo` 放入代码仓并准备分支，不要手工 clone 到别处或手工拼分支名：

  ```bash
  python .agents/skills/task-loop-run/scripts/workflow.py add-repo tasks/<task> \
    --source <路径或 URL> [--name <目录名>] [--no-checkout]
  ```

- 只有一个 Task 在推进时，直接在主工作树的 `.code/<repo>` 上使用该 Task 分支。
- 多个 Task 需要并行时用链接工作树隔离：本仓分支 `task/<task-id>` 检出到一个链接工作树，其中的
  `.code/<repo>` 是目标代码仓的对应链接工作树。创建前先把 Task 记录提交到本仓，否则工作树看不到它：

  ```bash
  python .agents/skills/task-loop-run/scripts/workflow.py add-worktree tasks/<task> [--path <目录>]
  python .agents/skills/task-loop-run/scripts/workflow.py remove-worktree tasks/<task> [--merge]
  ```

- Task 完成后，把本仓的 Task 分支合入主工作树的当前分支并回收链接工作树；目标代码仓的 Task 分支
  是否合入、如何合入由用户决定，需要推送或提交 PR/MR 时按外部动作处理。
- 同一分支不能同时检出到两个工作树。遇到分支占用先解除占用，不要改名绕开。

## 模板同步

- `AGENTS.md`、`CLAUDE.md`、`.agents/` 和 `.claude/skills/` 由 agent-home 模板管理，版本记录在
  `.agent-home/manifest.json`；`PROJECT.md`、`tasks/`、`docs/`、`reports/` 和 `.code/` 归项目所有。
- 用户要求升级、同步模板或拉取最新规则时使用 `agent-home-sync` Skill：

  ```bash
  python3 .agents/scripts/agent_home.py status --fetch
  python3 .agents/scripts/agent_home.py upgrade
  ```

- 同步保留本地对受管理文件的改动：能三方合并的直接合并，冲突时保留本地并写出 `.new` 文件，需要人工
  合并，不要用 `.new` 直接覆盖。
- 不手工复制模板文件绕过同步器，那会让清单与实际内容脱节。

## Git 与外部动作

- 可以为当前请求做本地、可恢复的编辑和验证。
- 提交前检查暂存区差异；提交信息使用一行英文，描述工程结果，不写 Agent、模型或会话信息。
- 推送、创建 PR/MR、发布、改写远端历史、发送消息或配置外部系统，都需要用户明确授权。
- 首次初始化不得自动删除模板 `origin`、创建远端仓库或重写 Git 历史。

## 写作与安全

- 默认使用简体中文写项目文档；代码标识符、路径、命令和外部 API 名称保持原样。
- 不在文档、日志或聊天中保存 token、cookie、私钥、密码或其他凭据内容。
- 不把提示词、内部推理、Agent/模型身份或工具轨迹写入源码、提交、PR/MR 或对外材料。
- 不建立全局待办、会话日志或第二份项目规则入口。新的稳定规则直接更新本文件。

## 验证

模板契约使用标准库测试验证：

```bash
python -m unittest discover -s tests -v
```

项目初始化后，应在 `PROJECT.md` 补充项目自己的构建、测试和检查命令。
