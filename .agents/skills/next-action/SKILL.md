---
name: next-action
description: 在方向图上重算就绪集合，并从中选出一个精确的下一步。当 Task、Loop 或 Run 打开、恢复、得到改变决策的结果、遇到阻塞、改变方向或需要交接时使用。不要生成推测性的未来待办链。
---

# 下一步导航

方向空间是一张有向无环图：节点是方向、功能构成或未知问题，`requires` 边给出前置依赖。导航遵循
`定向 → 重算图 → 选一步 → 执行 → 观察 → 更新图 → 重算`，本质是在图上做最佳优先搜索。

## 重算方向图

1. 读取最小范围内的当前 Task、Loop 或 Run 状态，以及决定性的检查点引用。
2. 重算前沿，而不是凭记忆挑候选：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py frontier tasks/<task>
   ```

   输出分为推进中、就绪、等待前置、外部阻塞、需要重新评估和已定论六组。
3. 逐条复核“需要重新评估”组。这些是暂缓与放弃的方向，每次决策都会重新列出：对照它们的复活条件与
   最新证据，判断当时的放弃理由是否已经不成立。发现机会时先复活节点，再继续选步。
4. 根据最新证据更新图本身，不要把图当成一次性计划：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py add-node tasks/<task> \
     --title "<方向或构成>" --kind direction --hypothesis "<可证伪假设>" \
     --value "<为什么值得做>" --cost "<粗估代价>" --requires <前置节点> --why "<为什么现在入图>"
   python .agents/skills/task-loop-run/scripts/workflow.py link tasks/<task> \
     --from <节点> --to <前置节点> --kind requires --why "<新发现的依赖>"
   python .agents/skills/task-loop-run/scripts/workflow.py set-node tasks/<task> <节点> \
     --status confirmed --evidence-ref "<证据>" --why "<改变判断的原因>"
   ```

   转为 `deferred` 或 `abandoned` 时必须写 `--revisit-when`：没有复活条件的放弃等于永久丢弃机会。

## 选一步

1. 候选只从就绪组里取：前置未满足的节点不能选，先推进它的前置或修改依赖关系。
2. 依次优先考虑：解锁的后继数量、对目标的关键性、信息增益、较低代价和可逆性。
3. 只选一个，并把它绑定到节点上：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py set-next-action <record-path> \
     --node <节点> --kind probe \
     --action "<精确动作>" --target "<对象或问题>" \
     --done-when "<可检查的完成条件>" --why-now "<现在选择它的原因>" \
     --source-ref "<路径或证据引用>"
   ```

   图非空时，`probe`、`execute`、`decide`、`verify` 必须绑定节点，或用 `--off-graph` 说明理由。
4. 方向节点由 Loop 承载，构成节点通常由 Run 承载：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-loop tasks/<task> <slug> --node <节点> ...
   ```

5. 没有候选可以执行时，记录阻塞并保持 `next_action` 为空：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py block <record-path> \
     --reason "<外部阻塞>" --unblock-when "<可观察的解除条件>"
   ```

动作类型包括 `orient`、`clarify`、`research`、`probe`、`decide`、`execute`、`unblock`、`verify`
和 `closeout`。目标处于 `foggy` 时只允许前四类和 `unblock`；普通实施要求目标已经 `clear`。

执行一步、观察结果，然后重新计算，不要静默继续下一个候选。等待是一种状态，不是动作。交接时复制的
`next_action` 只是上下文，不是实时真值；恢复后必须重新重算前沿。
