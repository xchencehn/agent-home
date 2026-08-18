---
name: design-grill
description: Shape a rough Task or proposed Loop into a clear, bounded, testable direction. Use when intent, scope, terminology, alternatives, acceptance, risks, unknowns, or pivot conditions remain unresolved before implementation. Stop immediately when the direction is already clear; do not invoke for routine execution.
---

# Design Grill

Turn fog into one precise direction. Do not implement while grilling.

## Task-level grill

1. Read `PROJECT.md`, the active `task.json`, and existing `grill/` files.
2. Separate four things explicitly:

   - known facts with source pointers;
   - precise questions that can be answered now;
   - fog whose question cannot yet be phrased;
   - non-goals that are consciously excluded.

3. Update only the smallest useful files:

   - `grill/design-brief.md`: target, context, scope, non-goals, alternatives, acceptance, first direction, open questions;
   - `grill/glossary.md`: task-specific terms only;
   - `grill/risks.md`: risk, consequence, probe, and pivot condition;
   - `grill/decisions.md`: lightweight decisions and their evidence.

4. Ask the user only for intent or trade-off choices that repository evidence cannot answer.
5. Stop when one Loop direction has a falsifiable hypothesis, acceptance evidence, falsification evidence, allowed change surface, and pivot condition.

## Loop shaping

Put Loop-level shaping directly in `goal.md` and `hypotheses.md`. Point back to relevant Task grill facts, risks, and decisions. Do not create `loops/<loop>/grill/`.

## Exit

Use `next-action` to choose one bounded clarification, research action, reversible probe, decision, or execution step. Never return “继续研究” or “继续优化”; name the uncertainty reduced and the checkable completion condition.

Keep raw commands and logs out of Grill files. Record execution evidence through `evidence-checkpoint` after a Run exists.
