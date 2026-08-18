#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"[^a-z0-9]+")
ID_RE = re.compile(r"^(\d{3})_([a-z0-9][a-z0-9-]*)$")
ACTION_KINDS = (
    "orient",
    "clarify",
    "research",
    "probe",
    "decide",
    "execute",
    "unblock",
    "verify",
    "closeout",
)
CHECKPOINT_KINDS = ("observation", "decision", "validation", "blocker", "handoff")


class WorkflowError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_root():
    return Path(__file__).resolve().parents[4]


def slugify(value):
    slug = SLUG_RE.sub("-", value.lower()).strip("-")
    if not slug:
        raise WorkflowError("slug must contain an ASCII letter or digit")
    return slug


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON: {path}: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def ensure_under(root, path):
    root = root.resolve()
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise WorkflowError(f"path escapes project root: {path}") from exc
    return path


def resolve_ref(root, reference):
    path = Path(reference)
    if not path.is_absolute():
        path = root / path
    return ensure_under(root, path)


def next_id(parent, slug):
    highest = 0
    if parent.exists():
        for child in parent.iterdir():
            if child.is_dir() and (match := ID_RE.fullmatch(child.name)):
                highest = max(highest, int(match.group(1)))
    return f"{highest + 1:03d}_{slugify(slug)}"


def navigation(summary, clarity, completion_conditions=None):
    return {
        "destination": {
            "summary": summary,
            "clarity": clarity,
            "completion_conditions": completion_conditions or [],
        },
        "known_refs": [],
        "questions": [],
        "fog": [],
        "out_of_scope": [],
        "candidates": [],
        "next_action": None,
        "blockers": [],
    }


def copy_grill_templates(task_path, objective):
    source = Path(__file__).resolve().parents[1] / "assets"
    target = task_path / "grill"
    target.mkdir()
    names = ("design-brief.md", "glossary.md", "risks.md", "decisions.md")
    for name in names:
        text = (source / name).read_text(encoding="utf-8")
        text = text.replace("{{OBJECTIVE}}", objective)
        (target / name).write_text(text, encoding="utf-8")


def require_active(record, path):
    if record.get("status") != "active":
        raise WorkflowError(f"record is not active: {path}")


def cmd_open_task(args):
    tasks = args.root / "tasks"
    tasks.mkdir(exist_ok=True)
    task_id = next_id(tasks, args.slug)
    path = tasks / task_id
    path.mkdir()
    timestamp = now()
    record = {
        "schema_version": SCHEMA_VERSION,
        "kind": "task",
        "id": task_id,
        "title": args.title,
        "objective": args.objective,
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "acceptance": args.acceptance,
        "non_goals": args.non_goal,
        "active_loop_id": None,
        "outcome": None,
        "navigation": navigation(args.objective, "foggy", args.acceptance),
    }
    write_json(path / "task.json", record)
    copy_grill_templates(path, args.objective)
    print(path.relative_to(args.root))


def cmd_open_loop(args):
    task = resolve_ref(args.root, args.task)
    task_record = read_json(task / "task.json")
    require_active(task_record, task)
    if task_record.get("active_loop_id"):
        raise WorkflowError(f"task already has an active Loop: {task_record['active_loop_id']}")
    loops = task / "loops"
    loops.mkdir(exist_ok=True)
    loop_id = next_id(loops, args.slug)
    path = loops / loop_id
    path.mkdir()
    (path / "runs").mkdir()
    timestamp = now()
    goal = (
        "# Loop Goal\n\n"
        f"{args.goal}\n\n"
        "## Acceptance\n\n"
        + "\n".join(f"- {item}" for item in args.acceptance)
        + "\n\n## Falsification\n\n"
        + "\n".join(f"- {item}" for item in args.falsification)
        + "\n\n## Source Grill\n\n- `../../grill/design-brief.md`\n"
    )
    (path / "goal.md").write_text(goal, encoding="utf-8")
    (path / "hypotheses.md").write_text(
        f"# Hypotheses\n\n- H1: {args.hypothesis}\n", encoding="utf-8"
    )
    state = {
        "schema_version": SCHEMA_VERSION,
        "kind": "loop_state",
        "id": loop_id,
        "task_id": task_record["id"],
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "active_run_id": None,
        "outcome": None,
        "navigation": navigation(args.goal, "clear", args.acceptance),
    }
    write_json(path / "state.json", state)
    task_record["active_loop_id"] = loop_id
    task_record["updated_at"] = timestamp
    write_json(task / "task.json", task_record)
    print(path.relative_to(args.root))


def cmd_open_run(args):
    loop = resolve_ref(args.root, args.loop)
    loop_state = read_json(loop / "state.json")
    require_active(loop_state, loop)
    if loop_state.get("active_run_id"):
        raise WorkflowError(f"loop already has an active Run: {loop_state['active_run_id']}")
    runs = loop / "runs"
    runs.mkdir(exist_ok=True)
    run_id = next_id(runs, args.slug)
    path = runs / run_id
    path.mkdir()
    timestamp = now()
    contract = {
        "schema_version": SCHEMA_VERSION,
        "kind": "run_contract",
        "id": run_id,
        "loop_id": loop_state["id"],
        "task_id": loop_state["task_id"],
        "created_at": timestamp,
        "objective": args.objective,
        "acceptance": args.acceptance,
        "allowed_changes": args.allowed_change,
    }
    state = {
        "schema_version": SCHEMA_VERSION,
        "kind": "run_state",
        "id": run_id,
        "loop_id": loop_state["id"],
        "task_id": loop_state["task_id"],
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "checkpoint_count": 0,
        "last_checkpoint_id": None,
        "contract_sha256": None,
        "navigation": navigation(args.objective, "clear", args.acceptance),
    }
    write_json(path / "contract.json", contract)
    state["contract_sha256"] = hashlib.sha256(
        (path / "contract.json").read_bytes()
    ).hexdigest()
    write_json(path / "state.json", state)
    (path / "checkpoints.jsonl").write_text("", encoding="utf-8")
    write_json(path / "result.json", {"schema_version": SCHEMA_VERSION, "status": "pending"})
    loop_state["active_run_id"] = run_id
    loop_state["updated_at"] = timestamp
    write_json(loop / "state.json", loop_state)
    print(path.relative_to(args.root))


def load_navigation_record(root, reference):
    path = resolve_ref(root, reference)
    if path.is_dir():
        if (path / "task.json").is_file():
            path = path / "task.json"
        elif (path / "state.json").is_file():
            path = path / "state.json"
    record = read_json(path)
    if "navigation" not in record:
        raise WorkflowError(f"record has no navigation: {path}")
    require_active(record, path)
    return path, record


def cmd_set_next_action(args):
    path, record = load_navigation_record(args.root, args.record)
    nav = record["navigation"]
    clarity = nav.get("destination", {}).get("clarity")
    allowed = {
        "foggy": {"orient", "clarify", "research", "probe", "unblock"},
        "provisional": set(ACTION_KINDS) - {"execute", "closeout"},
        "clear": set(ACTION_KINDS),
    }
    if clarity not in allowed or args.kind not in allowed[clarity]:
        raise WorkflowError(f"action kind {args.kind!r} is invalid for clarity {clarity!r}")
    used = [int(item["id"][1:]) for item in nav["candidates"] if re.fullmatch(r"A\d+", item.get("id", ""))]
    candidate_id = f"A{max(used, default=0) + 1:03d}"
    candidate = {
        "id": candidate_id,
        "kind": args.kind,
        "action": args.action,
        "target": args.target,
        "done_when": args.done_when,
        "source_refs": args.source_ref,
        "strategy_basis": args.why_now,
        "created_at": now(),
    }
    nav["candidates"].append(candidate)
    nav["next_action"] = {
        "candidate_id": candidate_id,
        "why_now": args.why_now,
        "selected_at": now(),
    }
    nav["blockers"] = []
    record["updated_at"] = now()
    write_json(path, record)
    print(candidate_id)


def cmd_block(args):
    path, record = load_navigation_record(args.root, args.record)
    blockers = record["navigation"]["blockers"]
    blocker_id = f"B{len(blockers) + 1:03d}"
    blockers.append(
        {
            "id": blocker_id,
            "reason": args.reason,
            "unblock_when": args.unblock_when,
            "recorded_at": now(),
        }
    )
    record["navigation"]["next_action"] = None
    record["updated_at"] = now()
    write_json(path, record)
    print(blocker_id)


def read_checkpoints(path):
    records = []
    if not path.exists():
        raise WorkflowError(f"missing file: {path}")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"invalid JSONL: {path}:{number}: {exc}") from exc
    return records


def cmd_checkpoint(args):
    run = resolve_ref(args.root, args.run)
    contract = read_json(run / "contract.json")
    state = read_json(run / "state.json")
    require_active(state, run)
    checkpoints = read_checkpoints(run / "checkpoints.jsonl")
    if args.supersedes and args.supersedes not in {item.get("id") for item in checkpoints}:
        raise WorkflowError(f"superseded checkpoint does not exist: {args.supersedes}")
    checkpoint_id = f"CP{len(checkpoints) + 1:03d}"
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": checkpoint_id,
        "run_id": contract["id"],
        "timestamp": now(),
        "kind": args.kind,
        "summary": args.summary,
        "result": args.result,
        "evidence_refs": args.evidence_ref,
        "limitation": args.limitation,
        "supersedes": args.supersedes,
    }
    with (run / "checkpoints.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    state["checkpoint_count"] = len(checkpoints) + 1
    state["last_checkpoint_id"] = checkpoint_id
    state["updated_at"] = now()
    write_json(run / "state.json", state)
    print(checkpoint_id)


def terminal_navigation(record):
    record["navigation"]["next_action"] = None
    record["navigation"]["candidates"] = []


def cmd_close_run(args):
    run = resolve_ref(args.root, args.run)
    contract = read_json(run / "contract.json")
    state = read_json(run / "state.json")
    require_active(state, run)
    checkpoints = read_checkpoints(run / "checkpoints.jsonl")
    if not checkpoints:
        raise WorkflowError("close-run requires at least one evidence checkpoint")
    timestamp = now()
    write_json(
        run / "result.json",
        {
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
            "run_id": contract["id"],
            "verdict": args.verdict,
            "summary": args.summary,
            "checkpoint_refs": [item["id"] for item in checkpoints],
            "completed_at": timestamp,
        },
    )
    state["status"] = "terminal"
    state["updated_at"] = timestamp
    terminal_navigation(state)
    write_json(run / "state.json", state)
    loop = run.parents[1]
    loop_state = read_json(loop / "state.json")
    if loop_state.get("active_run_id") == contract["id"]:
        loop_state["active_run_id"] = None
        loop_state["updated_at"] = timestamp
        write_json(loop / "state.json", loop_state)


def cmd_close_loop(args):
    loop = resolve_ref(args.root, args.loop)
    state = read_json(loop / "state.json")
    require_active(state, loop)
    if state.get("active_run_id"):
        raise WorkflowError(f"close the active Run first: {state['active_run_id']}")
    timestamp = now()
    state["status"] = "terminal"
    state["updated_at"] = timestamp
    state["outcome"] = {"verdict": args.verdict, "summary": args.summary}
    terminal_navigation(state)
    write_json(loop / "state.json", state)
    task = loop.parents[1]
    task_record = read_json(task / "task.json")
    if task_record.get("active_loop_id") == state["id"]:
        task_record["active_loop_id"] = None
        task_record["updated_at"] = timestamp
        write_json(task / "task.json", task_record)


def cmd_close_task(args):
    task = resolve_ref(args.root, args.task)
    record = read_json(task / "task.json")
    require_active(record, task)
    if record.get("active_loop_id"):
        raise WorkflowError(f"close the active Loop first: {record['active_loop_id']}")
    record["status"] = "terminal"
    record["updated_at"] = now()
    record["outcome"] = {"verdict": args.verdict, "summary": args.summary}
    terminal_navigation(record)
    write_json(task / "task.json", record)


def require_fields(record, fields, path):
    missing = [field for field in fields if field not in record]
    if missing:
        raise WorkflowError(f"missing fields in {path}: {', '.join(missing)}")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise WorkflowError(f"unsupported schema_version in {path}")


def check_navigation(record, path):
    nav = record.get("navigation")
    missing = [
        field
        for field in ("destination", "candidates", "next_action", "blockers")
        if field not in (nav or {})
    ]
    if missing:
        raise WorkflowError(f"missing navigation fields in {path}: {', '.join(missing)}")
    clarity = nav["destination"].get("clarity")
    if clarity not in ("foggy", "provisional", "clear"):
        raise WorkflowError(f"invalid destination clarity in {path}")
    selected = nav["next_action"]
    if selected is not None:
        ids = {item.get("id") for item in nav["candidates"]}
        if selected.get("candidate_id") not in ids:
            raise WorkflowError(f"next_action selects a missing candidate in {path}")


def check_run(run):
    contract = read_json(run / "contract.json")
    state = read_json(run / "state.json")
    result = read_json(run / "result.json")
    require_fields(contract, ("schema_version", "kind", "id", "loop_id", "task_id", "objective", "acceptance"), run / "contract.json")
    require_fields(state, ("schema_version", "kind", "id", "loop_id", "task_id", "status", "contract_sha256", "navigation"), run / "state.json")
    if contract["id"] != run.name or state["id"] != run.name:
        raise WorkflowError(f"Run id does not match directory: {run}")
    if contract["loop_id"] != state["loop_id"] or contract["task_id"] != state["task_id"]:
        raise WorkflowError(f"Run contract/state identity mismatch: {run}")
    digest = hashlib.sha256((run / "contract.json").read_bytes()).hexdigest()
    if state["contract_sha256"] != digest:
        raise WorkflowError(f"Run contract changed after opening: {run}")
    check_navigation(state, run / "state.json")
    checkpoints = read_checkpoints(run / "checkpoints.jsonl")
    ids = []
    for item in checkpoints:
        require_fields(item, ("schema_version", "id", "run_id", "timestamp", "kind", "summary", "result", "evidence_refs", "limitation"), run / "checkpoints.jsonl")
        if item["run_id"] != run.name or item["kind"] not in CHECKPOINT_KINDS:
            raise WorkflowError(f"invalid checkpoint identity or kind: {run}")
        if not isinstance(item["evidence_refs"], list) or not item["evidence_refs"]:
            raise WorkflowError(f"checkpoint has no evidence refs: {run}")
        ids.append(item["id"])
    if len(ids) != len(set(ids)):
        raise WorkflowError(f"duplicate checkpoint id: {run}")
    if state.get("checkpoint_count") != len(checkpoints):
        raise WorkflowError(f"checkpoint_count mismatch: {run}")
    expected_last = ids[-1] if ids else None
    if state.get("last_checkpoint_id") != expected_last:
        raise WorkflowError(f"last_checkpoint_id mismatch: {run}")
    if state["status"] == "terminal":
        require_fields(result, ("schema_version", "status", "run_id", "verdict", "summary", "checkpoint_refs"), run / "result.json")
        if result["status"] != "complete" or result["run_id"] != run.name:
            raise WorkflowError(f"invalid terminal result: {run}")
        if result["checkpoint_refs"] != ids:
            raise WorkflowError(f"terminal result checkpoint refs mismatch: {run}")
    elif result.get("status") != "pending":
        raise WorkflowError(f"active Run must have a pending result: {run}")


def check_loop(loop):
    state = read_json(loop / "state.json")
    require_fields(state, ("schema_version", "kind", "id", "task_id", "status", "navigation"), loop / "state.json")
    if state["id"] != loop.name:
        raise WorkflowError(f"Loop id does not match directory: {loop}")
    if not (loop / "goal.md").is_file() or not (loop / "hypotheses.md").is_file():
        raise WorkflowError(f"missing Loop goal or hypotheses: {loop}")
    check_navigation(state, loop / "state.json")
    for run in sorted((loop / "runs").glob("[0-9][0-9][0-9]_*")):
        check_run(run)
    active = state.get("active_run_id")
    if active and not (loop / "runs" / active).is_dir():
        raise WorkflowError(f"active_run_id does not exist: {loop}")
    if active and read_json(loop / "runs" / active / "state.json").get("status") != "active":
        raise WorkflowError(f"active_run_id points to a terminal Run: {loop}")


def check_task(task):
    record = read_json(task / "task.json")
    require_fields(record, ("schema_version", "kind", "id", "title", "objective", "status", "navigation"), task / "task.json")
    if record["id"] != task.name:
        raise WorkflowError(f"Task id does not match directory: {task}")
    for name in ("design-brief.md", "glossary.md", "risks.md", "decisions.md"):
        if not (task / "grill" / name).is_file():
            raise WorkflowError(f"missing Grill file: {task / 'grill' / name}")
    check_navigation(record, task / "task.json")
    loops = task / "loops"
    if loops.exists():
        for loop in sorted(loops.glob("[0-9][0-9][0-9]_*")):
            check_loop(loop)
    active = record.get("active_loop_id")
    if active and not (loops / active).is_dir():
        raise WorkflowError(f"active_loop_id does not exist: {task}")
    if active and read_json(loops / active / "state.json").get("status") != "active":
        raise WorkflowError(f"active_loop_id points to a terminal Loop: {task}")


def cmd_check(args):
    target = resolve_ref(args.root, args.path) if args.path else args.root
    if (target / "contract.json").is_file():
        check_run(target)
    elif (target / "task.json").is_file():
        check_task(target)
    elif (target / "goal.md").is_file() and (target / "state.json").is_file():
        check_loop(target)
    elif target == args.root or target.name == "tasks":
        tasks = target / "tasks" if target == args.root else target
        if tasks.exists():
            for task in sorted(tasks.glob("[0-9][0-9][0-9]_*")):
                check_task(task)
    else:
        raise WorkflowError(f"cannot identify record type: {target}")
    print("ok")


def build_parser():
    parser = argparse.ArgumentParser(description="Repo-local Task/Loop/Run workflow")
    parser.add_argument("--root", type=Path, default=project_root())
    subparsers = parser.add_subparsers(dest="command", required=True)

    command = subparsers.add_parser("open-task")
    command.add_argument("slug")
    command.add_argument("--title", required=True)
    command.add_argument("--objective", required=True)
    command.add_argument("--acceptance", action="append", default=[])
    command.add_argument("--non-goal", action="append", default=[])
    command.set_defaults(func=cmd_open_task)

    command = subparsers.add_parser("open-loop")
    command.add_argument("task")
    command.add_argument("slug")
    command.add_argument("--goal", required=True)
    command.add_argument("--hypothesis", required=True)
    command.add_argument("--acceptance", action="append", required=True)
    command.add_argument("--falsification", action="append", required=True)
    command.set_defaults(func=cmd_open_loop)

    command = subparsers.add_parser("open-run")
    command.add_argument("loop")
    command.add_argument("slug")
    command.add_argument("--objective", required=True)
    command.add_argument("--acceptance", action="append", required=True)
    command.add_argument("--allowed-change", action="append", default=[])
    command.set_defaults(func=cmd_open_run)

    command = subparsers.add_parser("set-next-action")
    command.add_argument("record")
    command.add_argument("--kind", choices=ACTION_KINDS, required=True)
    command.add_argument("--action", required=True)
    command.add_argument("--target", required=True)
    command.add_argument("--done-when", required=True)
    command.add_argument("--why-now", required=True)
    command.add_argument("--source-ref", action="append", required=True)
    command.set_defaults(func=cmd_set_next_action)

    command = subparsers.add_parser("block")
    command.add_argument("record")
    command.add_argument("--reason", required=True)
    command.add_argument("--unblock-when", required=True)
    command.set_defaults(func=cmd_block)

    command = subparsers.add_parser("checkpoint")
    command.add_argument("run")
    command.add_argument("--kind", choices=CHECKPOINT_KINDS, required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--result", required=True)
    command.add_argument("--evidence-ref", action="append", required=True)
    command.add_argument("--limitation", required=True)
    command.add_argument("--supersedes")
    command.set_defaults(func=cmd_checkpoint)

    command = subparsers.add_parser("close-run")
    command.add_argument("run")
    command.add_argument("--verdict", choices=("passed", "failed", "blocked", "partial"), required=True)
    command.add_argument("--summary", required=True)
    command.set_defaults(func=cmd_close_run)

    command = subparsers.add_parser("close-loop")
    command.add_argument("loop")
    command.add_argument("--verdict", choices=("confirmed", "falsified", "blocked", "abandoned"), required=True)
    command.add_argument("--summary", required=True)
    command.set_defaults(func=cmd_close_loop)

    command = subparsers.add_parser("close-task")
    command.add_argument("task")
    command.add_argument("--verdict", choices=("completed", "blocked", "abandoned"), required=True)
    command.add_argument("--summary", required=True)
    command.set_defaults(func=cmd_close_task)

    command = subparsers.add_parser("check")
    command.add_argument("path", nargs="?")
    command.set_defaults(func=cmd_check)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.root = args.root.resolve()
    try:
        args.func(args)
    except WorkflowError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
