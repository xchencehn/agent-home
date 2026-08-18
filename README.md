# Agent Home

一个可以直接克隆使用的 Agent 项目模板。仓库本身就是 Agent Home：根规则、项目说明、Task/Loop/Run
工作协议和可复用 Skill（技能）都随 Git 一起分发，不需要安装插件。

## 开始使用

克隆时直接指定项目目录名：

```bash
git clone https://github.com/xchencehn/agent-home.git sparseRT
cd sparseRT
codex
# 或
claude
```

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
| `bootstrap-project` | 把刚克隆或改名的模板初始化成具体项目 |
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

## 仓库结构

- `AGENTS.md`：Codex 与其他兼容 Agent 的根规则。
- `CLAUDE.md`：Claude Code 根入口，导入同一份 `AGENTS.md`。
- `PROJECT.md`：项目身份、目标、范围与常用命令。
- `.agents/skills/`：仓库级 Skill，也是工作流的唯一源码。
- `.claude/skills/`：Claude Code 的薄发现包装层，不复制工作流。
- `tasks/`：按需生成的跨会话工作记录。
- `docs/`：面向使用者的设计和说明。
- `reports/`：需要长期保留、且有证据支持的工程结论。
- `tests/`：机器可复验的项目判据。

## 验证与 Git 边界

```bash
python -m unittest discover -s tests -v
```

普通克隆会保留本模板为 `origin`。首次初始化不会删除或改写远端，也不会自动推送。准备发布到自己的
仓库时，再明确要求 Agent 配置目标远端。

## 许可证

本项目使用 [MIT License](LICENSE)。另提供[简体中文参考译文](LICENSE.zh-CN)，法律效力以英文原文为准。
