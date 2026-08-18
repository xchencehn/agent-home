---
name: evidence-checkpoint
description: 为当前 Run 追加并校验会影响决策的证据。当证据改变下一步、证明或证伪验收条件、记录重要源码或环境边界、支持恢复，或即将交接与收尾时使用。普通读取、拼写重试和没有产生新结论的重复命令不要记录。
---

# 证据检查点

只有事实会改变决策、支撑结论或用于恢复时才记录。

## 记录里程碑

1. 读取不可变的 `contract.json`、当前 `state.json` 和已有 `checkpoints.jsonl`。
2. 完整原始输出留在合适的项目日志或产物中；检查点只保存有边界的结论和来源指针。
3. 追加一个检查点：

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py checkpoint <run-path> \
     --kind validation \
     --summary "<有边界的结论>" \
     --result "<实际观察结果>" \
     --evidence-ref "<产物、命令、测试、提交或源码引用>" \
     --limitation "<这份证据不能证明什么>"
   ```

4. 每个改变决策的检查点写入后，都重新计算 Run 的 `next_action`。
5. 交接或收尾前运行 `workflow.py check <run-path>`。

检查点类型包括 `observation`、`decision`、`validation`、`blocker` 和 `handoff`。使用稳定生成的 ID
和明确的 UTC 时间戳。不要改写已经追加的检查点；另行追加纠正检查点，并指出被替代的 ID。

不要隐藏失败命令，不要把命令成功等同于结论被接受，也不要在缺少同案比较时宣称性能收益。执行会话可以
提出 `result.json`；若项目要求独立验收，仍应由人或另一个可区分的顶层会话完成。
