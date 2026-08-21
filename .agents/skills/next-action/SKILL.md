---
name: next-action
description: 在 Task 的方向图上重算就绪集合，复核被放弃的方向，再选出一个精确且可执行的下一步。当 Task、Loop 或 Run 打开、恢复、得到改变决策的结果、遇到阻塞、改变方向或需要交接时使用。不要生成推测性的未来待办链。
---

# 下一步导航

方向空间是一张有向无环图，保存在 `tasks/<task>/graph.json`：节点是方向、功能构成或未知问题，
`requires` 边给出前置依赖。导航遵循 `定向 → 重算图 → 选一步 → 执行 → 观察 → 更新图 → 重算`，
本质是在图上做最佳优先搜索。图由你直接编辑，工具只负责前置门禁与结构校验。

## 重算方向图

1. 读取当前 Task、Loop 或 Run 状态、决定性的检查点引用，以及 `graph.json`。
2. 按状态与依赖把节点分组，不要凭记忆挑候选：

   - **推进中**：`active`，已有 Loop 或 Run 承载；
   - **就绪**：`open` 且所有 `requires` 前置都是 `confirmed`；
   - **等待前置**：`open` 但仍有前置未 `confirmed`，记下缺哪几个；
   - **外部阻塞**：`blocked`；
   - **需要重新评估**：`deferred` 与 `abandoned`；
   - **已定论**：`confirmed`、`falsified`、`superseded`。

3. 逐条复核“需要重新评估”组。对照每个节点的 `revisit_when` 与最新证据，判断当时的放弃理由是否
   已经不成立。发现机会时先把它改回 `open` 并补上 `evidence_refs`，再继续选步。
4. 根据新证据直接更新 `graph.json`：新方向加节点，新依赖加 `requires` 边，判断改变就改 `status`
   和 `reason`，依赖判断有误就删掉那条边。图是活的，不是一次成型的计划。
5. 转为 `deferred` 或 `abandoned` 时必须同时写 `revisit_when`，否则 `check` 会失败：没有复活条件的
   放弃等于永久丢弃机会。

节点字段与状态取值见 `docs/direction-graph.md`。

## 选一步

1. 候选只从就绪组里取。前置未满足的节点不能选，先推进它的前置或修正依赖关系。
2. 依次优先考虑：解锁的后继数量、对目标的关键性、信息增益、较低代价和可逆性。
3. 只选一个，并把它绑定到节点上：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py set-next-action <record-path> \
     --node <节点> --kind probe \
     --action "<精确动作>" --target "<对象或问题>" \
     --done-when "<可检查的完成条件>" --why-now "<现在选择它的原因>" \
     --source-ref "<路径或证据引用>"
   ```

   命令会拒绝前置未满足、已定论或不存在的节点。图非空时 `probe`、`execute`、`decide`、`verify`
   必须绑定节点，或用 `--off-graph` 说明这一步为什么在图外。
4. 方向节点由 Loop 承载，构成节点通常由 Run 承载。`open-loop --node <节点>` 会校验前置并把节点标成
   `active`，`close-loop` 按判定写回节点状态。
5. 没有候选可以执行时，记录阻塞并保持 `next_action` 为空：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py block <record-path> \
     --reason "<外部阻塞>" --unblock-when "<可观察的解除条件>"
   ```

动作类型包括 `orient`、`clarify`、`research`、`probe`、`decide`、`execute`、`unblock`、`verify`
和 `closeout`。目标处于 `foggy` 时只允许前四类和 `unblock`；普通实施要求目标已经 `clear`。

执行一步、观察结果，然后重新计算，不要静默继续下一个候选。等待是一种状态，不是动作。交接时复制的
`next_action` 只是上下文，不是实时真值；恢复后必须重新重算。
