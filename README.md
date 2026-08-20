# Agent Home

一个可以直接用来管理项目的 Agent Home：根规则、项目说明、Task/Loop/Run 工作协议和可复用 Skill
（技能）都随 Git 分发，不需要安装插件，并且可以在项目里一句话同步到模板的新版本。

<!-- agent-install:start -->
## 给 Agent 的安装指令

被要求“使用本仓管理这个项目”时，在项目目录里执行：

```bash
git clone https://github.com/xchencehn/agent-home .agent-home/upstream
python3 .agent-home/upstream/.agents/scripts/agent_home.py init
```

然后读取生成的 `AGENTS.md`，按其中的启动顺序用 `bootstrap-project` 完成 `PROJECT.md` 初始化。
之后同步模板新版本用 `python3 .agents/scripts/agent_home.py upgrade`。
<!-- agent-install:end -->

## 开始使用

新建一个空目录，在里面启动 Codex 或 Claude Code：

```bash
mkdir sparseRT && cd sparseRT
codex
# 或
claude
```

直接说明要用本仓管理这个项目，并给出目标：

```text
使用 https://github.com/xchencehn/agent-home 管理这个项目，目标是模型图编译研发。
```

Agent 会执行上面的安装指令，把规则与技能装进当前目录，再初始化 `PROJECT.md`。项目仓库归项目自己
所有：`origin` 不指向模板仓，历史里也没有模板提交。

也可以继续把本仓直接克隆成项目骨架，但那样 `origin` 指向模板仓，后续升级只能手工合并：

```bash
git clone https://github.com/xchencehn/agent-home.git sparseRT
```

## 升级模板

模板仓更新后，在项目里一句话同步：

```text
把 agent-home 模板同步到最新版本。
```

Agent 使用 `agent-home-sync`，实际执行：

```bash
python3 .agents/scripts/agent_home.py status --fetch
python3 .agents/scripts/agent_home.py upgrade
```

受管理范围是 `AGENTS.md`、`CLAUDE.md`、`.agents/` 和 `.claude/skills/`，版本记录在
`.agent-home/manifest.json`。`PROJECT.md`、`tasks/`、`docs/`、`reports/` 和 `.code/` 归项目所有，同步
不会改动它们。本地改过的受管理文件按三方合并处理：能合并就合并，冲突时保留本地并写出 `.new` 文件
供人工处理。完整说明见 [用 agent-home 管理项目](docs/agent-home-usage.md)。

## 效果示例

启动后直接描述目标，例如：

```text
把这里初始化成一个用于开发 模型图编译研发 的项目，然后开启做第一个任务：调研当前市面上模型图编译有哪些标杆项目，哪些代表性的技术。
```

首次会话会使用 `bootstrap-project` 初始化 `PROJECT.md`。
```
已完成项目初始化，并开启第一个长期调研任务。

  - 项目身份已更新为模型图编译研发项目：PROJECT.md:1
  - Task 001_graph-compiler-research 保持活动：tasks/001_graph-compiler-research/task.json:1
  - 首轮市场扫描 Run 已完成，完整报告见：reports/graph-compiler-landscape-2026-08.md:1

  首版结论：

  - 核心标杆：PyTorch 2 Compiler、OpenXLA、TVM、IREE、TensorRT、ONNX Runtime。
  - 场景标杆：OpenVINO、MIGraphX、CANN GE/ATC、TensorRT-LLM、MLC LLM。
  - 代表技术集中在动态图捕获与 guards、多层 IR、动态 shape、图融合与成本模型、布局/内存规划、异构子图
    划分、Kernel autotuning、SPMD 分布式 Lowering，以及 LLM编译与运行时协同。
    PyTorch Compiler (https://docs.pytorch.org/docs/stable/user_guide/torch_compiler/torch.compiler.html)、
    TVM 架构(https://tvm.apache.org/docs/arch/index.html)、
    IREE (https://iree.dev/)、
    CANN GE(https://www.hiascend.com/document/detail/en/CANNCommunityEdition/900/programug/graphdevg/atlasag_25_0081.html)
  - 建议 sparseRT 首个原型做“动态 shape 感知的融合与异构子图划分闭环”，暂不先造完整前端、Kernel DSL 或运行时。

  下一行动已记录为：使用同一个动态 shape 最小模型，统一走读 PyTorch 2、OpenXLA、TVM、IREE 和 CANN GE 的 IR、融合、划分、artifact 与失败边界。

  验证结果：10 项仓库测试通过，Task/Loop/Run 结构检查通过，git diff --check 通过。没有提交、推送或修改远端；origin 仍指向模板仓库。
```

<!-- project-summary:start -->
## 当前项目

这是尚未初始化的 Agent Home 模板。项目身份与目标见 `PROJECT.md`。
<!-- project-summary:end -->

## 核心工作方法

简单请求直接完成。需要跨多步、多轮验证或跨会话恢复时，Agent 自动使用以下 Skill：

| Skill（技能） | 职责 |
| --- | --- |
| `agent-home-sync` | 安装模板，或把模板的新版本同步到当前项目 |
| `bootstrap-project` | 把刚安装或刚克隆的模板初始化成具体项目 |
| `task-loop-run` | Task 管目标，Loop 管可证伪方向，Run 管一次执行结果 |
| `design-grill` | 在实施前澄清范围、术语、风险、验收、未知项和转向条件 |
| `next-action` | 根据目标、行动前沿、阻塞和信息迷雾，每轮只选择一个下一步 |
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
最终结果进入 `result.json`。没有生成状态页、插件锁、插件市场、安装缓存或强制验收状态机。

完整设计思想见 [Agent Home：项目自有的持久工作环境](docs/home-engineering.md)。

## 目标代码仓与并行 Task

管理仓（本仓）只保存目标、规则、工作状态和结论；被操作的目标代码仓放在 `.code/` 下，由 Git 忽略，
各自提交自己的历史：

```text
agent-home/            # 管理仓：AGENTS.md、PROJECT.md、tasks/、docs/
└── .code/             # 被忽略：目标代码仓的工作面
    └── sparseRT/      # 独立 Git 仓，Task 分支 task/001_xxx
```

一个 Task 对应目标代码仓上的一个分支：

```bash
python .agents/skills/task-loop-run/scripts/workflow.py add-repo tasks/001_xxx \
  --source https://example.com/sparseRT.git
```

多个 Task 需要并行时，管理仓用 Git 工作树隔离，工作树内自带对应的代码仓工作树；Task 完成后合入
管理仓主分支并回收工作树：

```bash
git add tasks/002_yyy && git commit -m "Open task 002"
python .agents/skills/task-loop-run/scripts/workflow.py add-worktree tasks/002_yyy
python .agents/skills/task-loop-run/scripts/workflow.py remove-worktree tasks/002_yyy --merge
```

完整流程与边界见 [代码仓与并行工作区](docs/code-workspace.md)。

## 仓库结构

- `AGENTS.md`：Codex 与其他兼容 Agent 的根规则。
- `CLAUDE.md`：Claude Code 根入口，导入同一份 `AGENTS.md`。
- `PROJECT.md`：项目身份、目标、范围与常用命令。
- `.agents/skills/`：仓库级 Skill，也是工作流的唯一源码。
- `.agents/scripts/agent_home.py`：模板安装与同步器。
- `.agent-home/`：模板版本清单与模板仓本地缓存（缓存不提交）。
- `.claude/skills/`：Claude Code 的薄发现包装层，不复制工作流。
- `tasks/`：按需生成的跨会话工作记录。
- `.code/`：被操作的目标代码仓，Git 忽略，由各代码仓自行提交。
- `docs/`：面向使用者的设计和说明。
- `reports/`：需要长期保留、且有证据支持的工程结论。
- `tests/`：机器可复验的项目判据。

## 验证与 Git 边界

```bash
python -m unittest discover -s tests -v
```

通过安装指令得到的项目没有模板远端，`origin` 由项目自己决定；直接克隆本仓则会保留本模板为
`origin`。两种方式下首次初始化都不会删除或改写远端，也不会自动推送。

## 许可证

本项目使用 [MIT License](LICENSE)。另提供[简体中文参考译文](LICENSE.zh-CN)，法律效力以英文原文为准。
