---
name: task-loop-run
description: 在仓库内用 Task、Loop 和 Run 记录管理持久工作。当需要打开或恢复长期目标、把目标拆成可证伪方向、开始一次有边界的执行、跨会话恢复工作，或关闭 Run、Loop 与 Task 时使用。无需恢复或交接的一步请求不要使用。
---

# Task / Loop / Run

使用一个紧凑层级：

- Task 管理持久目标。
- Loop 管理一个可证伪方向或阶段。
- Run 管理一次有边界的执行结果。
- 检查点记录事实，导航状态记录选中的下一步。

## 打开或恢复

1. 读取 `PROJECT.md`，再检查 `tasks/` 中是否已有目标相同的活动 Task。
2. 目标相同时恢复已有记录，不要为同一目标创建并行 Task。
3. 只有工作可能跨越多个动作、假设、会话或交接时才打开 Task：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-task <slug> \
     --title "<标题>" --objective "<目标>"
   ```

4. 目标仍然模糊时，先使用 `design-grill`，不要直接打开 Loop。
5. 只有一个方向已经能够表述为可证伪假设时才打开 Loop：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-loop tasks/<task> <slug> \
     --goal "<有边界的目标>" --hypothesis "<可证伪假设>" \
     --acceptance "<支持假设的证据>" --falsification "<推翻假设的证据>"
   ```

6. 为一次具体执行打开 Run，并冻结它的目标：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-run tasks/<task>/loops/<loop> <slug> \
     --objective "<本次执行目标>" --acceptance "<可观察的通过条件>"
   ```

命令会输出新建路径。Run 开始后，把 `contract.json` 视为不可变合同。

## 执行与关闭

1. 只执行当前 Run 合同规定的内容。
2. 当结果改变路线、证明或证伪条件、形成恢复边界或即将交接时，使用 `evidence-checkpoint`。
3. 记录打开、恢复、改变方向、遇到阻塞或收到改变决策的结果时，使用 `next-action`。
4. 用有边界的结论关闭 Run：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py close-run <run-path> \
     --verdict passed --summary "<结果与限制>"
   ```

5. 只根据 Run 结果关闭或转向 Loop。只有达到验收边界或用户明确放弃时才关闭 Task：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py close-loop <loop-path> \
     --verdict confirmed --summary "<决策>"
   python .agents/skills/task-loop-run/scripts/workflow.py close-task <task-path> \
     --verdict completed --summary "<最终结果>"
   ```

6. 交接或收尾前校验恢复结构：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py check
   ```

## 记录契约

- `tasks/<task>/task.json`：目标、生命周期、最终结果和 Task 导航。
- `tasks/<task>/grill/`：设计简报、Task 术语、风险和决策。
- `loops/<loop>/goal.md`、`hypotheses.md`、`state.json`：冻结的方向和 Loop 导航。
- `runs/<run>/contract.json`：不可变的执行合同。
- `runs/<run>/state.json`：可变恢复状态和 Run 导航。
- `runs/<run>/checkpoints.jsonl`：只追加的决策相关证据。
- `runs/<run>/result.json`：待确认的终态结果。

不要创建生成状态视图、会话流水、强制空证据文件、签名、晋升状态、插件锁或插件市场元数据。
