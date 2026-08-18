---
name: evidence-checkpoint
description: Append and validate decision-relevant evidence for an active Run. Use when evidence changes the next action, proves or falsifies an acceptance gate, records an important source or environment boundary, supports recovery, or precedes handoff or closeout. Do not record ordinary reads, typo retries, or repeated commands with no new conclusion.
---

# Evidence Checkpoint

Record facts only when they change a decision, support a verdict, or are required for recovery.

## Record a milestone

1. Read the immutable `contract.json`, current `state.json`, and existing `checkpoints.jsonl`.
2. Keep full raw output in an appropriate project log or artifact. Put only the bounded conclusion and references in the checkpoint.
3. Append one checkpoint:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py checkpoint <run-path> \
     --kind validation \
     --summary "<bounded conclusion>" \
     --result "<observed result>" \
     --evidence-ref "<artifact, command, test, commit, or source ref>" \
     --limitation "<what this does not prove>"
   ```

4. Recompute the Run `next_action` after every decision-changing checkpoint.
5. Run `workflow.py check <run-path>` before handoff or closeout.

Checkpoint kinds are `observation`, `decision`, `validation`, `blocker`, and `handoff`. Use stable generated IDs and explicit UTC timestamps. Never rewrite an appended checkpoint; append a correcting checkpoint that names the superseded ID.

Do not make a failed command disappear, confuse command success with claim acceptance, or claim performance without a same-case comparison. The executing session may propose `result.json`; any independent acceptance required by the project remains a separate human or top-level-session action.
