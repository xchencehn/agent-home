# 代码仓与并行工作区

本仓是**管理仓**：保存目标、规则、Task/Loop/Run 状态、证据和结论。被操作的**目标代码仓**不属于管理仓
的历史，放在 `.code/` 下，由它们自己提交管理。

## 目录布局

```text
agent-home/                  # 管理仓
├── AGENTS.md                # 规则
├── PROJECT.md               # 项目身份
├── tasks/001_xxx/task.json  # Task 记录，含 repos 登记
└── .code/                   # .gitignore 忽略，不进入管理仓历史
    └── sparseRT/            # 目标代码仓，独立 Git 仓库
```

`.gitignore` 中的 `/.code/` 保证管理仓永远看不到目标代码仓的文件与产物。目标代码仓自己的分支、提交
和远端由它自己管理，管理仓只在 `task.json` 的 `repos` 里登记目录、来源和分支，用于跨会话恢复。

## 一个 Task 一个分支

Task 对应目标代码仓上的分支 `task/<task-id>`，`<task-id>` 就是 `tasks/` 下的目录名。

```bash
python .agents/skills/task-loop-run/scripts/workflow.py open-task sparse-kernel \
  --title "稀疏 Kernel" --objective "..."
python .agents/skills/task-loop-run/scripts/workflow.py add-repo tasks/001_sparse-kernel \
  --source https://example.com/sparseRT.git
```

`add-repo` 做四件事：`.code/<name>` 不存在时克隆；确认它是有提交的 Git 仓库；创建分支
`task/001_sparse-kernel`（`--base` 指定基点，默认当前 `HEAD`）；把登记写入 `task.json`。默认会切换到该
分支，`--no-checkout` 则只创建分支和登记。

来源 URL 中的用户名与令牌在登记前会被去掉，`task.json` 里只保留可公开的来源地址。

代码改动在该分支上由代码仓自己提交：

```bash
git -C .code/sparseRT commit -am "Add blocked sparse kernel"
```

## 并行 Task 用工作树隔离

同一个分支不能同时检出到两个工作树，多个 Task 并行时给每个 Task 一套隔离工作面：管理仓的
`task/<task-id>` 分支检出到独立工作树，工作树内的 `.code/<repo>` 是目标代码仓的对应工作树。

```bash
# 1. 登记但不占用主工作树
python .agents/skills/task-loop-run/scripts/workflow.py add-repo tasks/002_layout \
  --source https://example.com/sparseRT.git --no-checkout

# 2. Task 记录必须先提交，链接工作树才看得到它
git add tasks/002_layout && git commit -m "Open task 002"

# 3. 创建链接工作树，默认路径 ../<仓库名>.worktrees/<task-id>
python .agents/skills/task-loop-run/scripts/workflow.py add-worktree tasks/002_layout
```

得到的结构：

```text
agent-home/                              # 主工作树，推进 001
└── .code/sparseRT                       # 分支 task/001_sparse-kernel
agent-home.worktrees/002_layout/         # 链接工作树，推进 002
└── .code/sparseRT                       # 分支 task/002_layout
```

之后所有工作在该工作树内进行：Task 记录提交到管理仓的 `task/002_layout` 分支，代码提交到代码仓的
同名分支。两套提交互不干扰，也不会互相覆盖工作区。

## 完成后合入

```bash
python .agents/skills/task-loop-run/scripts/workflow.py remove-worktree tasks/002_layout --merge
```

命令按顺序执行：检查链接工作树没有未提交改动；`--merge` 时要求主工作树干净，再把 `task/002_layout`
以 `--no-ff` 合入管理仓当前分支；移除登记代码仓的工作树；确认工作树的 `.code/` 没有未登记残留后移除
管理仓工作树，并清理空的父目录。`--force` 跳过未提交改动与残留检查，会丢失这些改动，只在确认可丢弃时使用。

目标代码仓的 `task/002_layout` 分支保留在代码仓内。是否合入它的主分支、是否推送或提交 PR/MR，由用户
决定；推送和创建 PR/MR 属于外部动作，需要明确授权。

## 边界与常见错误

| 情况 | 命令行为 |
| --- | --- |
| `.code/<name>` 不存在且未给 `--source` | 拒绝，提示需要来源 |
| 目标代码仓没有任何提交 | 拒绝，无法创建 Task 分支 |
| Task 分支已在另一个工作树检出 | 拒绝，提示用 `add-worktree` 隔离 |
| Task 记录尚未提交到管理仓 | 拒绝创建工作树，提示先提交 |
| 链接工作树有未提交改动 | 拒绝移除 |
| 工作树 `.code/` 有未登记的代码仓 | 拒绝移除，避免连带删除 |
| `task.json` 的 `repos` 分支与 Task 不一致 | `workflow.py check` 报错 |

不要把目标代码仓的内容复制进管理仓，不要为绕开分支占用而改分支名，也不要在管理仓提交代码仓的构建
产物。
