---
name: next-action
description: 根据目标、当前行动前沿、阻塞、已知事实、问题和信息迷雾，重新计算一个精确下一步。当 Task、Loop 或 Run 打开、恢复、得到改变决策的结果、遇到阻塞、改变方向或需要交接时使用。不要生成推测性的未来待办链。
---

# 下一步导航

遵循 `定向 → 分层 → 选步 → 执行 → 观察 → 重算`。

## 重新计算

1. 读取最小范围内的当前 Task、Loop 或 Run 状态，以及决定性的检查点引用。
2. 重新判断：

   - 目标及其清晰度：`foggy`、`provisional` 或 `clear`；
   - 已知事实与来源指针；
   - 精确问题；
   - 尚无法表述成精确问题的迷雾；
   - 范围外工作；
   - 明确阻塞。

3. 只生成当前能够看见的有边界候选。每个候选必须包含动作、对象、完成条件、来源指针和选择依据。
4. 排除被阻塞和范围外的候选。依次优先考虑：对目标关键的进展、信息增益、较低成本和可逆性。
5. 只选择一个候选。执行该动作、观察结果，然后重新计算，不要静默继续下一个候选。

候选类型包括 `orient`、`clarify`、`research`、`probe`、`decide`、`execute`、`unblock`、
`verify` 和 `closeout`。目标处于 `foggy` 时，只允许前四类和 `unblock`；普通实施要求目标已经 `clear`。

## 保存选择

更新所属的 `task.json` 或 `state.json`：

```bash
python .agents/skills/task-loop-run/scripts/workflow.py set-next-action <record-path> \
  --kind probe \
  --action "<精确动作>" \
  --target "<对象或问题>" \
  --done-when "<可检查的完成条件>" \
  --why-now "<现在选择它的原因>" \
  --source-ref "<路径或证据引用>"
```

没有候选可以执行时，记录阻塞并保持 `next_action` 为空：

```bash
python .agents/skills/task-loop-run/scripts/workflow.py block <record-path> \
  --reason "<外部阻塞>" --unblock-when "<可观察的解除条件>"
```

等待是一种状态，不是动作。交接时复制的 `next_action` 只是上下文，不是实时真值；恢复后必须重新计算。
