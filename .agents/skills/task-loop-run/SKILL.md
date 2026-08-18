---
name: task-loop-run
description: Manage durable work as Task, Loop, and Run records inside the repository. Use when opening or resuming a long-running goal, splitting a goal into a falsifiable direction, starting a bounded execution attempt, recovering work across sessions, or closing a Run, Loop, or Task. Do not use for a trivial one-step request that needs no recovery or handoff.
---

# Task Loop Run

Use one compact hierarchy:

- Task manages a durable objective.
- Loop manages one falsifiable direction or stage.
- Run manages one bounded execution result.
- Checkpoints record facts; navigation records the selected next action.

## Start or resume

1. Read `PROJECT.md`, then inspect `tasks/` for a matching active Task.
2. Resume the existing record when its objective matches. Do not create a parallel Task for the same objective.
3. Open a Task only for work likely to span several actions, hypotheses, sessions, or handoffs:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-task <slug> \
     --title "<title>" --objective "<objective>"
   ```

4. If the objective is still foggy, use `design-grill` before opening a Loop.
5. Open a Loop only after one direction can be stated as a falsifiable hypothesis:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-loop tasks/<task> <slug> \
     --goal "<bounded goal>" --hypothesis "<falsifiable hypothesis>" \
     --acceptance "<confirming evidence>" --falsification "<disproving evidence>"
   ```

6. Open a Run for one concrete execution with a frozen objective:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py open-run tasks/<task>/loops/<loop> <slug> \
     --objective "<one execution objective>" --acceptance "<observable pass condition>"
   ```

The command prints the created path. Treat `contract.json` as immutable after the Run starts.

## Work and close

1. Execute only the active Run contract.
2. Use `evidence-checkpoint` when a result changes the route, proves or falsifies a gate, creates a recovery boundary, or precedes handoff.
3. Use `next-action` whenever a record opens, resumes, changes direction, becomes blocked, or receives a decision-changing result.
4. Close a Run with a bounded verdict:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py close-run <run-path> \
     --verdict passed --summary "<result and limitations>"
   ```

5. Close or pivot the Loop only from Run results. Close the Task only when its acceptance boundary is met or the user explicitly abandons it:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py close-loop <loop-path> \
     --verdict confirmed --summary "<decision>"
   python .agents/skills/task-loop-run/scripts/workflow.py close-task <task-path> \
     --verdict completed --summary "<outcome>"
   ```

6. Validate recovery structure before handoff or closeout:

   ```bash
   python .agents/skills/task-loop-run/scripts/workflow.py check
   ```

## Record contract

- `tasks/<task>/task.json`: objective, lifecycle, outcome, and Task navigation.
- `tasks/<task>/grill/`: design brief, task-local terms, risks, and decisions.
- `loops/<loop>/goal.md`, `hypotheses.md`, `state.json`: frozen direction and Loop navigation.
- `runs/<run>/contract.json`: immutable execution contract.
- `runs/<run>/state.json`: mutable recovery state and Run navigation.
- `runs/<run>/checkpoints.jsonl`: append-only decision-relevant evidence.
- `runs/<run>/result.json`: proposed terminal result.

Do not create generated status views, session transcripts, mandatory empty evidence files, signatures, promotion states, plugin locks, or marketplace metadata.
