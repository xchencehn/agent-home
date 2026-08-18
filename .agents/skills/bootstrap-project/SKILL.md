---
name: bootstrap-project
description: Initialize a freshly cloned or renamed Agent Home repository template into a concrete project. Use when PROJECT.md still contains agent-home-template:uninitialized, when the user asks to initialize or repurpose the template, or before the first substantive change in a fresh clone. Do not use for routine work after the marker has been removed.
---

# Bootstrap Project

Turn the fresh template into the user's project without requiring an installer or separate bootstrap command.

## Workflow

1. Resolve the Git root and read `AGENTS.md`, `PROJECT.md`, `README.md`, `git status --short --branch`, and
   `git remote -v`.
2. Use the root directory basename as the proposed project name. Do not rename the directory yourself.
3. Derive the goal and initial scope from the user's request. If the request does not reveal the goal, ask one concise
   question and stop initialization until answered.
4. Update `PROJECT.md` with the project name, goal, current scope, non-goals, discovered validation commands, and stable
   constraints. Remove the `agent-home-template:uninitialized` marker.
5. Replace only the block between `project-summary:start` and `project-summary:end` in `README.md` with the project
   name, purpose, and shortest useful start command. Keep the reusable Agent workspace explanation unless the user asks
   to remove it.
6. Add project-specific rules to `AGENTS.md` only when they are already known and always applicable. Put conditional
   workflows in a new repo-local Skill instead of enlarging the root rules.
7. Keep `.agents/skills/` as the workflow source of truth. Keep `.claude/skills/bootstrap-project/SKILL.md` as a
   discovery-only wrapper that points back to this file; do not copy the workflow into it.
8. Run `python -m unittest discover -s tests -v`, plus any project-native check discovered during initialization.
9. If the same request begins a long-running or multi-stage goal, hand off to `task-loop-run` after initialization.
10. Report the initialized identity, remaining unknowns, validation result, and current remote ownership.

## Boundaries

- Do not create Task, Loop, or Run merely because the template was initialized. Use `task-loop-run` only when the
  substantive request needs durable recovery, hypotheses, or several bounded execution attempts.
- Do not create session logs, plugin manifests, marketplace entries, install caches, generated status views, or
  mandatory governance records.
- Do not delete or rewrite Git history, remove or replace a remote, create an external repository, push, or publish
  without explicit user authorization.
- Do not invent build or test commands. Record unknown commands as unknown until the repository supplies evidence.
- Do not copy machine-specific paths, credentials, personal settings, or the template's historical implementation into
  the new project.
