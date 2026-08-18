# Agent Home

一个可以直接克隆使用的 Agent 项目模板。仓库本身就是 Agent Home：根规则、项目说明、Task/Loop/Run
工作协议和可复用 Skills 都随 Git 一起分发，不需要安装插件。

## 开始使用

clone 时直接指定项目目录名：

```bash
git clone https://github.com/xchencehn/agent-home.git my-project
cd my-project
codex
# 或
claude
```

也可以先 clone 再改目录名：

```bash
git clone https://github.com/xchencehn/agent-home.git
mv agent-home my-project
cd my-project
codex
```

启动后直接描述目标，例如：

```text
把这里初始化成一个用于分析编译日志的项目，然后实现第一个日志解析器。
```

首次会话会使用 `bootstrap-project` 初始化 `PROJECT.md`。Codex 会从仓库根
`.agents/skills/` 自动发现 Skills；Claude Code 从 `.claude/skills/` 的薄 wrapper 转读同一份工作流。

<!-- project-summary:start -->
## 当前项目

这是尚未初始化的 Agent Home 模板。项目身份与目标见 `PROJECT.md`。
<!-- project-summary:end -->

## 核心工作方法

简单请求直接完成。需要跨多步、多轮验证或跨会话恢复时，Agent 自动使用以下 Skills：

| Skill | 职责 |
| --- | --- |
| `bootstrap-project` | 把刚 clone 或改名的模板初始化成具体项目 |
| `task-loop-run` | Task 管目标，Loop 管可证伪方向，Run 管一次执行结果 |
| `design-grill` | 在实施前澄清范围、术语、风险、验收、未知项和转向条件 |
| `next-action` | 根据 destination、frontier、blockers 和 fog 每轮只选择一个下一步 |
| `evidence-checkpoint` | 只记录会改变路线、支撑结论或用于恢复交接的关键证据 |

也可以在提示词中显式调用，例如：

```text
使用 $task-loop-run 为这个长期目标开一个 Task。
使用 $design-grill 先把这个想法梳理清楚，不要实现。
使用 $next-action 根据当前证据重新选择下一步。
```

## Task / Loop / Run

Task 使用 `NNN_slug` 自动编号。一个典型记录如下：

```text
tasks/001_example/
├── task.json
├── grill/
│   ├── design-brief.md
│   ├── glossary.md
│   ├── risks.md
│   └── decisions.md
└── loops/001_direction/
    ├── goal.md
    ├── hypotheses.md
    ├── state.json
    └── runs/001_probe/
        ├── contract.json
        ├── state.json
        ├── checkpoints.jsonl
        └── result.json
```

不必手写目录或序号。Agent 使用标准库脚本创建和校验记录：

```bash
python .agents/skills/task-loop-run/scripts/workflow.py --help
python .agents/skills/task-loop-run/scripts/workflow.py check
```

Run 打开后，`contract.json` 不再改写；事实追加到 `checkpoints.jsonl`，当前恢复位置在 `state.json`，
最终结果进入 `result.json`。没有生成状态页、插件锁、marketplace、安装缓存或强制验收状态机。

## 仓库结构

- `AGENTS.md`：Codex 与其他兼容 Agent 的根规则。
- `CLAUDE.md`：Claude Code 根入口，导入同一份 `AGENTS.md`。
- `PROJECT.md`：项目身份、目标、范围与常用命令。
- `.agents/skills/`：仓库级 Skills，也是工作流的唯一源码。
- `.claude/skills/`：Claude Code 的薄发现 wrapper，不复制工作流。
- `tasks/`：按需生成的跨会话工作记录。
- `docs/`：面向使用者的设计和说明。
- `reports/`：需要长期保留、且有证据支持的工程结论。
- `tests/`：机器可复验的项目判据。

## 验证与 Git 边界

```bash
python -m unittest discover -s tests -v
```

普通 clone 会保留本模板为 `origin`。首次初始化不会删除或改写 remote，也不会自动 push。准备发布到
自己的仓库时，再明确要求 Agent 配置目标 remote。

## License

本项目使用 [MIT License](LICENSE)。
