---
name: next-action
description: Recompute one precise next action from destination, current frontier, blockers, known facts, questions, and fog. Use when a Task, Loop, or Run opens, resumes, reaches a decision-changing result, becomes blocked, changes direction, or needs a handoff. Do not emit a speculative future todo chain.
---

# Next Action

Follow `定向 → 分层 → 选步 → 执行 → 观察 → 重算`.

## Recompute

1. Observe the smallest current Task, Loop, or Run state plus decisive checkpoint references.
2. Reassess:

   - destination and its clarity: `foggy`, `provisional`, or `clear`;
   - known facts and source pointers;
   - precise questions;
   - fog not yet expressible as a precise question;
   - out-of-scope work;
   - explicit blockers.

3. Generate only currently visible bounded candidates. Each candidate needs an action, target, completion condition, source pointer, and strategy basis.
4. Exclude blocked and out-of-scope candidates. Prefer destination-critical progress, then information gain, lower cost, and reversibility.
5. Select exactly one candidate. Execute only that action, observe its result, then recompute.

Candidate kinds are `orient`, `clarify`, `research`, `probe`, `decide`, `execute`, `unblock`, `verify`, and `closeout`. A foggy destination permits only the first four plus `unblock`; ordinary execution requires a clear destination.

## Persist the choice

Update the owning `task.json` or `state.json`:

```bash
python .agents/skills/task-loop-run/scripts/workflow.py set-next-action <record-path> \
  --kind probe \
  --action "<precise action>" \
  --target "<object or question>" \
  --done-when "<checkable condition>" \
  --why-now "<selection reason>" \
  --source-ref "<path or evidence ref>"
```

When no candidate is executable, record the blocker and leave `next_action` null:

```bash
python .agents/skills/task-loop-run/scripts/workflow.py block <record-path> \
  --reason "<external blocker>" --unblock-when "<observable condition>"
```

Waiting is a state, not an action. A handoff copy of `next_action` is context, not live authority; recompute after resuming.
