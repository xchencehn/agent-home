#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"[^a-z0-9]+")
ID_RE = re.compile(r"^(\d{3})_([a-z0-9][a-z0-9-]*)$")
CODE_DIR = ".code"
REPO_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
USERINFO_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*://)[^/@]*@")
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
GRAPH_NAME = "graph.json"
NODE_KINDS = ("direction", "component", "question")
NODE_STATUSES = (
    "open",
    "active",
    "confirmed",
    "falsified",
    "blocked",
    "deferred",
    "abandoned",
    "superseded",
)
# 已经有结论的状态：不再进入前沿，但仍然是前置判定的依据。
SETTLED_STATUSES = ("confirmed", "falsified", "superseded")
# 暂缓与放弃的状态：每次计算前沿都要重新复核，避免机会被永久埋没。
REVIEW_STATUSES = ("deferred", "abandoned")
EDGE_KINDS = ("requires", "part-of", "informs", "conflicts", "supersedes")


class WorkflowError(Exception):
    pass


class ChineseArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", help="显示帮助并退出")
        self._positionals.title = "位置参数"
        self._optionals.title = "选项"

    def format_help(self):
        return super().format_help().replace("usage:", "用法：")

    def format_usage(self):
        return super().format_usage().replace("usage:", "用法：")

    def error(self, message):
        message = message.replace(
            "the following arguments are required:", "缺少必需参数："
        )
        message = message.replace("unrecognized arguments:", "无法识别的参数：")
        message = message.replace("invalid choice:", "值无效：")
        message = message.replace("choose from", "可选值")
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}：错误：{message}\n")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def project_root():
    return Path(__file__).resolve().parents[4]


def slugify(value):
    slug = SLUG_RE.sub("-", value.lower()).strip("-")
    if not slug:
        raise WorkflowError("slug 必须至少包含一个 ASCII 字母或数字")
    return slug


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"缺少文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"JSON 无效：{path}：{exc}") from exc


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
        raise WorkflowError(f"路径越出项目根目录：{path}") from exc
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
        "next_action": None,  # 关键：任何时刻只选择一个当前动作。
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
        raise WorkflowError(f"记录不是活动状态：{path}")


def empty_graph(task_id):
    timestamp = now()
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "direction_graph",
        "task_id": task_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "nodes": [],
        "edges": [],
    }


def load_graph(task):
    path = task / GRAPH_NAME
    if not path.is_file():
        record = read_json(task / "task.json")
        return empty_graph(record["id"])
    return read_json(path)


def save_graph(task, graph):
    graph["updated_at"] = now()
    write_json(task / GRAPH_NAME, graph)



def node_index(graph):
    return {node["id"]: node for node in graph["nodes"]}


def require_node(graph, node_id):
    node = node_index(graph).get(node_id)
    if node is None:
        raise WorkflowError(f"节点不存在：{node_id}")
    return node



def prerequisites(graph):
    """返回 {节点: [它依赖的前置节点]}，只看 requires 边。"""
    mapping = {node["id"]: [] for node in graph["nodes"]}
    for edge in graph["edges"]:
        if edge["kind"] == "requires":
            mapping.setdefault(edge["from"], []).append(edge["to"])
    return mapping


def compute_frontier(graph):
    """把节点分成推进中、就绪、等待前置、外部阻塞、待复核和已定论六组，返回节点 ID。"""
    nodes = node_index(graph)
    dependencies = prerequisites(graph)
    frontier = {key: [] for key in ("active", "ready", "waiting", "blocked", "review", "settled")}
    for node in graph["nodes"]:
        status = node["status"]
        if status in SETTLED_STATUSES:
            frontier["settled"].append(node["id"])
        elif status in REVIEW_STATUSES:
            frontier["review"].append(node["id"])
        elif status == "blocked":
            frontier["blocked"].append(node["id"])
        elif status == "active":
            frontier["active"].append(node["id"])
        else:
            missing = [
                target
                for target in dependencies.get(node["id"], [])
                if nodes.get(target, {}).get("status") != "confirmed"
            ]
            frontier["waiting" if missing else "ready"].append(node["id"])
    return frontier


def detect_cycle(graph):
    """在 requires 边上做深度优先搜索，返回第一个发现的环。"""
    dependencies = prerequisites(graph)
    color = {}
    stack = []

    def visit(node_id):
        color[node_id] = "gray"
        stack.append(node_id)
        for target in dependencies.get(node_id, []):
            if color.get(target) == "gray":
                return stack[stack.index(target) :] + [target]
            if color.get(target) is None:
                found = visit(target)
                if found:
                    return found
        color[node_id] = "black"
        stack.pop()
        return None

    for node in graph["nodes"]:
        if color.get(node["id"]) is None:
            found = visit(node["id"])
            if found:
                return found
    return None




def task_branch(task_id):
    return f"task/{task_id}"


def git(cwd, *arguments, check=True):
    result = subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise WorkflowError(f"git {' '.join(arguments)} 失败：{detail}")
    return result


def git_output(cwd, *arguments):
    return git(cwd, *arguments).stdout.strip()


def git_succeeds(cwd, *arguments):
    return git(cwd, *arguments, check=False).returncode == 0


def require_worktree(path, role):
    if not path.is_dir() or not git_succeeds(path, "rev-parse", "--is-inside-work-tree"):
        raise WorkflowError(f"{role}不是 Git 工作树：{path}")


def require_commit(repo, role):
    if not git_succeeds(repo, "rev-parse", "--verify", "--quiet", "HEAD"):
        raise WorkflowError(f"{role}还没有任何提交，无法创建 Task 分支：{repo}")


def branch_exists(repo, branch):
    return git_succeeds(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")


def worktree_paths(repo):
    """返回 {分支名: 检出目录}，覆盖主工作树和所有链接工作树。"""
    mapping = {}
    current = None
    for line in git_output(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree ") :])
        elif line.startswith("branch refs/heads/") and current is not None:
            mapping[line[len("branch refs/heads/") :]] = current
    return mapping


def require_free_branch(repo, branch, role):
    holder = worktree_paths(repo).get(branch)
    if holder is not None:
        raise WorkflowError(
            f"{role}：分支 {branch} 已经在 {holder} 检出。同一分支不能同时检出到两个工作树，"
            f"先在该工作树切换到别的分支，或者用 add-repo --no-checkout 登记后再建链接工作树"
        )


def sanitize_source(url):
    """去掉 URL 中的用户名与令牌，只保留可记录的来源。"""
    if not url:
        return None
    return USERINFO_RE.sub(r"\1", url)


def repo_name_from_source(source):
    name = source.rstrip("/").rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".git") else name


def find_repo_entry(record, name):
    for entry in record.get("repos", []):
        if entry.get("name") == name:
            return entry
    return None


def cmd_add_repo(args):
    task = resolve_ref(args.root, args.task)
    record = read_json(task / "task.json")
    require_active(record, task)
    name = args.name or repo_name_from_source(args.source or "")
    if not REPO_NAME_RE.fullmatch(name):
        raise WorkflowError(f"代码仓目录名无效：{name!r}")
    code = args.root / CODE_DIR
    code.mkdir(exist_ok=True)
    repo = ensure_under(args.root, code / name)
    if not repo.exists():
        if not args.source:
            raise WorkflowError(f"{repo} 不存在，需要用 --source 指定代码仓来源")
        git(code, "clone", args.source, name)
    require_worktree(repo, "代码仓")
    require_commit(repo, "代码仓")
    branch = task_branch(record["id"])
    if not branch_exists(repo, branch):
        git(repo, "branch", branch, args.base)
    if args.checkout:
        holder = worktree_paths(repo).get(branch)
        if holder is not None and holder.resolve() != repo.resolve():
            raise WorkflowError(
                f"分支 {branch} 已经在 {holder} 检出；并行 Task 使用 add-worktree 隔离"
            )
        git(repo, "checkout", branch)
    source = args.source
    if not source and git_succeeds(repo, "remote", "get-url", "origin"):
        source = git_output(repo, "remote", "get-url", "origin")
    entry = {
        "name": name,
        "path": f"{CODE_DIR}/{name}",
        "source": sanitize_source(source),
        "branch": branch,
        "registered_at": now(),
    }
    repos = [item for item in record.get("repos", []) if item.get("name") != name]
    repos.append(entry)
    record["repos"] = sorted(repos, key=lambda item: item["name"])
    record["updated_at"] = now()
    write_json(task / "task.json", record)
    print(entry["path"])


def cmd_add_worktree(args):
    task = resolve_ref(args.root, args.task)
    record = read_json(task / "task.json")
    require_active(record, task)
    require_worktree(args.root, "管理仓")
    require_commit(args.root, "管理仓")
    relative_task = task.relative_to(args.root).as_posix()
    if not git_succeeds(args.root, "ls-files", "--error-unmatch", f"{relative_task}/task.json"):
        raise WorkflowError(
            f"Task 记录还没有提交到管理仓，链接工作树看不到它：先提交 {relative_task}/"
        )
    branch = task_branch(record["id"])
    require_free_branch(args.root, branch, "管理仓")
    path = (
        Path(args.path).expanduser().resolve()
        if args.path
        else args.root.parent / f"{args.root.name}.worktrees" / record["id"]
    )
    if path.exists():
        raise WorkflowError(f"工作树路径已存在：{path}")
    for entry in record.get("repos", []):
        repo = args.root / entry["path"]
        if repo.is_dir():
            require_free_branch(repo, entry["branch"], f"代码仓 {entry['name']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists(args.root, branch):
        git(args.root, "worktree", "add", str(path), branch)
    else:
        git(args.root, "worktree", "add", "-b", branch, str(path), args.base)
    for entry in record.get("repos", []):
        repo = args.root / entry["path"]
        if not repo.is_dir():
            print(f"跳过尚未检出的代码仓：{entry['path']}", file=sys.stderr)
            continue
        target = path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if branch_exists(repo, entry["branch"]):
            git(repo, "worktree", "add", str(target), entry["branch"])
        else:
            git(repo, "worktree", "add", "-b", entry["branch"], str(target), args.base)
    print(path)


def cmd_remove_worktree(args):
    task = resolve_ref(args.root, args.task)
    record = read_json(task / "task.json")
    require_worktree(args.root, "管理仓")
    branch = task_branch(record["id"])
    holder = worktree_paths(args.root).get(branch)
    if holder is None or holder.resolve() == args.root.resolve():
        raise WorkflowError(f"没有找到检出 {branch} 的链接工作树")
    if git_output(holder, "status", "--porcelain") and not args.force:
        raise WorkflowError(f"链接工作树还有未提交改动：{holder}")
    if args.merge:
        if git_output(args.root, "status", "--porcelain"):
            raise WorkflowError(f"合入前主工作树必须干净：{args.root}")
        git(args.root, "merge", "--no-ff", branch, "-m", f"Merge branch '{branch}'")
    for entry in record.get("repos", []):
        repo = args.root / entry["path"]
        target = holder / entry["path"]
        if not repo.is_dir() or not target.is_dir():
            continue
        arguments = ["worktree", "remove", str(target)]
        if args.force:
            arguments.append("--force")
        git(repo, *arguments)
    leftover = holder / CODE_DIR
    remaining = sorted(item.name for item in leftover.iterdir()) if leftover.is_dir() else []
    if remaining and not args.force:
        raise WorkflowError(f"{leftover} 仍有未登记的代码仓：{'、'.join(remaining)}")
    arguments = ["worktree", "remove", str(holder)]
    if args.force:
        arguments.append("--force")
    git(args.root, *arguments)
    parent = holder.parent
    if parent != args.root and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
    print(holder)


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
        "repos": [],
        "active_loop_id": None,
        "outcome": None,
        "navigation": navigation(args.objective, "foggy", args.acceptance),
    }
    write_json(path / "task.json", record)
    write_json(path / GRAPH_NAME, empty_graph(task_id))
    copy_grill_templates(path, args.objective)
    print(path.relative_to(args.root))


def cmd_open_loop(args):
    task = resolve_ref(args.root, args.task)
    task_record = read_json(task / "task.json")
    require_active(task_record, task)
    if task_record.get("active_loop_id"):
        raise WorkflowError(f"Task 已有活动 Loop：{task_record['active_loop_id']}")
    loops = task / "loops"
    loops.mkdir(exist_ok=True)
    loop_id = next_id(loops, args.slug)
    path = loops / loop_id
    path.mkdir()
    (path / "runs").mkdir()
    timestamp = now()
    goal = (
        "# Loop 目标\n\n"
        f"{args.goal}\n\n"
        "## 验收条件\n\n"
        + "\n".join(f"- {item}" for item in args.acceptance)
        + "\n\n## 证伪条件\n\n"
        + "\n".join(f"- {item}" for item in args.falsification)
        + "\n\n## 来源梳理\n\n- `../../grill/design-brief.md`\n"
    )
    (path / "goal.md").write_text(goal, encoding="utf-8")
    (path / "hypotheses.md").write_text(
        f"# 假设\n\n- H1：{args.hypothesis}\n", encoding="utf-8"
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
        "node_id": args.node,
        "navigation": navigation(args.goal, "clear", args.acceptance),
    }
    if args.node:
        graph = load_graph(task)
        node = require_node(graph, args.node)
        nodes = node_index(graph)
        missing = [
            target
            for target in prerequisites(graph).get(node["id"], [])
            if nodes.get(target, {}).get("status") != "confirmed"
        ]
        if missing:
            raise WorkflowError(
                f"节点 {node['id']} 还有未满足的前置：{'、'.join(missing)}；先推进前置或改图"
            )
        if node["status"] in SETTLED_STATUSES:
            raise WorkflowError(f"节点 {node['id']} 已经定论（{node['status']}），先复核它的状态")
        node["status"] = "active"
        node["realized_as"] = f"loops/{loop_id}"
        node["updated_at"] = timestamp
        save_graph(task, graph)
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
        raise WorkflowError(f"Loop 已有活动 Run：{loop_state['active_run_id']}")
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
        raise WorkflowError(f"记录没有导航状态：{path}")
    require_active(record, path)
    return path, record




def owning_task(path):
    """从任意记录路径向上找到所属 Task 目录。"""
    start = path if path.is_dir() else path.parent
    for candidate in (start, *start.parents):
        if (candidate / "task.json").is_file():
            return candidate
    return None







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
        raise WorkflowError(f"动作类型 {args.kind!r} 不适用于清晰度 {clarity!r}")
    task = owning_task(path)
    graph = load_graph(task) if task else None
    if graph and graph["nodes"]:
        frontier = compute_frontier(graph)
        selectable = set(frontier["ready"] + frontier["active"])
        if args.node:
            node = require_node(graph, args.node)
            if node["id"] not in selectable:
                raise WorkflowError(
                    f"节点 {node['id']} 不在就绪集合里（状态 {node['status']}）："
                    "先满足它的前置，或先复核它的状态"
                )
        elif args.kind in ("probe", "execute", "decide", "verify") and not args.off_graph:
            raise WorkflowError(
                "方向图非空：用 --node 绑定这个动作对应的节点，或用 --off-graph 说明它为什么在图外"
            )
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
        "node_id": args.node,
        "off_graph": args.off_graph,
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
        raise WorkflowError(f"缺少文件：{path}")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"JSONL 无效：{path}:{number}：{exc}") from exc
    return records


def cmd_checkpoint(args):
    run = resolve_ref(args.root, args.run)
    contract = read_json(run / "contract.json")
    state = read_json(run / "state.json")
    require_active(state, run)
    checkpoints = read_checkpoints(run / "checkpoints.jsonl")
    if args.supersedes and args.supersedes not in {item.get("id") for item in checkpoints}:
        raise WorkflowError(f"被替代的检查点不存在：{args.supersedes}")
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
        raise WorkflowError("关闭 Run 前至少需要一个证据检查点")
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
        raise WorkflowError(f"请先关闭活动 Run：{state['active_run_id']}")
    timestamp = now()
    state["status"] = "terminal"
    state["updated_at"] = timestamp
    state["outcome"] = {"verdict": args.verdict, "summary": args.summary}
    terminal_navigation(state)
    task = loop.parents[1]
    node_id = state.get("node_id")
    if node_id:
        graph = load_graph(task)
        node = require_node(graph, node_id)
        target_status = {
            "confirmed": "confirmed",
            "falsified": "falsified",
            "blocked": "blocked",
            "abandoned": "abandoned",
        }[args.verdict]
        if args.revisit_when:
            node["revisit_when"] = args.revisit_when
        if target_status in REVIEW_STATUSES and not node.get("revisit_when"):
            raise WorkflowError(
                f"节点 {node_id} 转为 {target_status} 前必须用 --revisit-when 记录复活条件"
            )
        node["status"] = target_status
        node["reason"] = args.summary
        node["updated_at"] = timestamp
        save_graph(task, graph)
    write_json(loop / "state.json", state)
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
        raise WorkflowError(f"请先关闭活动 Loop：{record['active_loop_id']}")
    record["status"] = "terminal"
    record["updated_at"] = now()
    record["outcome"] = {"verdict": args.verdict, "summary": args.summary}
    terminal_navigation(record)
    write_json(task / "task.json", record)


def require_fields(record, fields, path):
    missing = [field for field in fields if field not in record]
    if missing:
        raise WorkflowError(f"{path} 缺少字段：{', '.join(missing)}")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise WorkflowError(f"{path} 使用了不支持的 schema_version")


def check_navigation(record, path):
    nav = record.get("navigation")
    missing = [
        field
        for field in ("destination", "candidates", "next_action", "blockers")
        if field not in (nav or {})
    ]
    if missing:
        raise WorkflowError(f"{path} 缺少导航字段：{', '.join(missing)}")
    clarity = nav["destination"].get("clarity")
    if clarity not in ("foggy", "provisional", "clear"):
        raise WorkflowError(f"{path} 的目标清晰度无效")
    selected = nav["next_action"]
    if selected is not None:
        ids = {item.get("id") for item in nav["candidates"]}
        if selected.get("candidate_id") not in ids:
            raise WorkflowError(f"{path} 的 next_action 指向不存在的候选")


def check_run(run):
    contract = read_json(run / "contract.json")
    state = read_json(run / "state.json")
    result = read_json(run / "result.json")
    require_fields(contract, ("schema_version", "kind", "id", "loop_id", "task_id", "objective", "acceptance"), run / "contract.json")
    require_fields(state, ("schema_version", "kind", "id", "loop_id", "task_id", "status", "contract_sha256", "navigation"), run / "state.json")
    if contract["id"] != run.name or state["id"] != run.name:
        raise WorkflowError(f"Run ID 与目录名不一致：{run}")
    if contract["loop_id"] != state["loop_id"] or contract["task_id"] != state["task_id"]:
        raise WorkflowError(f"Run 合同与状态的身份不一致：{run}")
    digest = hashlib.sha256((run / "contract.json").read_bytes()).hexdigest()
    if state["contract_sha256"] != digest:
        raise WorkflowError(f"Run 打开后合同被改写：{run}")
    check_navigation(state, run / "state.json")
    checkpoints = read_checkpoints(run / "checkpoints.jsonl")
    ids = []
    for item in checkpoints:
        require_fields(item, ("schema_version", "id", "run_id", "timestamp", "kind", "summary", "result", "evidence_refs", "limitation"), run / "checkpoints.jsonl")
        if item["run_id"] != run.name or item["kind"] not in CHECKPOINT_KINDS:
            raise WorkflowError(f"检查点身份或类型无效：{run}")
        if not isinstance(item["evidence_refs"], list) or not item["evidence_refs"]:
            raise WorkflowError(f"检查点没有证据引用：{run}")
        ids.append(item["id"])
    if len(ids) != len(set(ids)):
        raise WorkflowError(f"检查点 ID 重复：{run}")
    if state.get("checkpoint_count") != len(checkpoints):
        raise WorkflowError(f"checkpoint_count 与实际记录数不一致：{run}")
    expected_last = ids[-1] if ids else None
    if state.get("last_checkpoint_id") != expected_last:
        raise WorkflowError(f"last_checkpoint_id 与实际末条记录不一致：{run}")
    if state["status"] == "terminal":
        require_fields(result, ("schema_version", "status", "run_id", "verdict", "summary", "checkpoint_refs"), run / "result.json")
        if result["status"] != "complete" or result["run_id"] != run.name:
            raise WorkflowError(f"终态结果无效：{run}")
        if result["checkpoint_refs"] != ids:
            raise WorkflowError(f"终态结果引用的检查点与实际记录不一致：{run}")
    elif result.get("status") != "pending":
        raise WorkflowError(f"活动 Run 的结果必须是 pending：{run}")


def check_loop(loop):
    state = read_json(loop / "state.json")
    require_fields(state, ("schema_version", "kind", "id", "task_id", "status", "navigation"), loop / "state.json")
    if state["id"] != loop.name:
        raise WorkflowError(f"Loop ID 与目录名不一致：{loop}")
    if not (loop / "goal.md").is_file() or not (loop / "hypotheses.md").is_file():
        raise WorkflowError(f"Loop 缺少目标或假设文件：{loop}")
    check_navigation(state, loop / "state.json")
    for run in sorted((loop / "runs").glob("[0-9][0-9][0-9]_*")):
        check_run(run)
    active = state.get("active_run_id")
    if active and not (loop / "runs" / active).is_dir():
        raise WorkflowError(f"active_run_id 指向不存在的 Run：{loop}")
    if active and read_json(loop / "runs" / active / "state.json").get("status") != "active":
        raise WorkflowError(f"active_run_id 指向已经结束的 Run：{loop}")


def check_repos(record, path):
    repos = record.get("repos", [])
    if not isinstance(repos, list):
        raise WorkflowError(f"{path} 的 repos 必须是列表")
    names = []
    for entry in repos:
        missing = [field for field in ("name", "path", "branch") if not entry.get(field)]
        if missing:
            raise WorkflowError(f"{path} 的代码仓登记缺少字段：{', '.join(missing)}")
        if not REPO_NAME_RE.fullmatch(entry["name"]):
            raise WorkflowError(f"{path} 的代码仓目录名无效：{entry['name']!r}")
        if entry["path"] != f"{CODE_DIR}/{entry['name']}":
            raise WorkflowError(f"{path} 的代码仓路径必须是 {CODE_DIR}/<name>：{entry['path']}")
        if entry["branch"] != task_branch(record["id"]):
            raise WorkflowError(
                f"{path} 的代码仓分支必须是 {task_branch(record['id'])}：{entry['branch']}"
            )
        names.append(entry["name"])
    if len(names) != len(set(names)):
        raise WorkflowError(f"{path} 的代码仓登记重复")


def check_graph(task, record):
    path = task / GRAPH_NAME
    if not path.is_file():
        return
    graph = read_json(path)
    require_fields(graph, ("schema_version", "kind", "task_id", "nodes", "edges"), path)
    if graph["task_id"] != record["id"]:
        raise WorkflowError(f"{path} 的 task_id 与 Task 不一致")
    identifiers = []
    for node in graph["nodes"]:
        missing = [field for field in ("id", "kind", "title", "status") if not node.get(field)]
        if missing:
            raise WorkflowError(f"{path} 的节点缺少字段：{', '.join(missing)}")
        if node["kind"] not in NODE_KINDS:
            raise WorkflowError(f"{path} 的节点类型无效：{node['kind']}")
        if node["status"] not in NODE_STATUSES:
            raise WorkflowError(f"{path} 的节点状态无效：{node['status']}")
        if node["status"] in REVIEW_STATUSES and not node.get("revisit_when"):
            raise WorkflowError(f"{path} 的 {node['id']} 是 {node['status']} 但没有记录复活条件")
        if node["status"] == "active" and not node.get("realized_as"):
            raise WorkflowError(f"{path} 的 {node['id']} 是 active 但没有承载它的 Loop 或 Run")
        identifiers.append(node["id"])
    if len(identifiers) != len(set(identifiers)):
        raise WorkflowError(f"{path} 的节点 ID 重复")
    known = set(identifiers)
    for edge in graph["edges"]:
        missing = [field for field in ("from", "to", "kind") if not edge.get(field)]
        if missing:
            raise WorkflowError(f"{path} 的边缺少字段：{', '.join(missing)}")
        if edge["kind"] not in EDGE_KINDS:
            raise WorkflowError(f"{path} 的边类型无效：{edge['kind']}")
        if edge["from"] not in known or edge["to"] not in known:
            raise WorkflowError(f"{path} 的边引用了不存在的节点：{edge['from']} -> {edge['to']}")
        if edge["from"] == edge["to"]:
            raise WorkflowError(f"{path} 的边两端相同：{edge['from']}")
    cycle = detect_cycle(graph)
    if cycle:
        raise WorkflowError(f"{path} 的 requires 边形成环：{' -> '.join(cycle)}")


def check_task(task):
    record = read_json(task / "task.json")
    require_fields(record, ("schema_version", "kind", "id", "title", "objective", "status", "navigation"), task / "task.json")
    if record["id"] != task.name:
        raise WorkflowError(f"Task ID 与目录名不一致：{task}")
    check_repos(record, task / "task.json")
    check_graph(task, record)
    for name in ("design-brief.md", "glossary.md", "risks.md", "decisions.md"):
        if not (task / "grill" / name).is_file():
            raise WorkflowError(f"缺少设计梳理文件：{task / 'grill' / name}")
    check_navigation(record, task / "task.json")
    loops = task / "loops"
    if loops.exists():
        for loop in sorted(loops.glob("[0-9][0-9][0-9]_*")):
            check_loop(loop)
    active = record.get("active_loop_id")
    if active and not (loops / active).is_dir():
        raise WorkflowError(f"active_loop_id 指向不存在的 Loop：{task}")
    if active and read_json(loops / active / "state.json").get("status") != "active":
        raise WorkflowError(f"active_loop_id 指向已经结束的 Loop：{task}")


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
        raise WorkflowError(f"无法识别记录类型：{target}")
    print("通过")


def build_parser():
    parser = ChineseArgumentParser(description="仓库内置的 Task/Loop/Run 工作流")
    parser.add_argument("--root", type=Path, default=project_root(), help="项目根目录")
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=ChineseArgumentParser
    )

    command = subparsers.add_parser("open-task", help="打开一个长期 Task")
    command.add_argument("slug")
    command.add_argument("--title", required=True)
    command.add_argument("--objective", required=True)
    command.add_argument("--acceptance", action="append", default=[])
    command.add_argument("--non-goal", action="append", default=[])
    command.set_defaults(func=cmd_open_task)

    command = subparsers.add_parser("open-loop", help="打开一个可证伪 Loop")
    command.add_argument("task")
    command.add_argument("slug")
    command.add_argument("--goal", required=True)
    command.add_argument("--hypothesis", required=True)
    command.add_argument("--acceptance", action="append", required=True)
    command.add_argument("--falsification", action="append", required=True)
    command.add_argument("--node", help="这个 Loop 推进的方向图节点")
    command.set_defaults(func=cmd_open_loop)

    command = subparsers.add_parser("open-run", help="打开一次有边界的 Run")
    command.add_argument("loop")
    command.add_argument("slug")
    command.add_argument("--objective", required=True)
    command.add_argument("--acceptance", action="append", required=True)
    command.add_argument("--allowed-change", action="append", default=[])
    command.set_defaults(func=cmd_open_run)

    command = subparsers.add_parser("add-repo", help="把目标代码仓放入 .code/ 并准备 Task 分支")
    command.add_argument("task")
    command.add_argument("--source", help="代码仓来源，本地路径或远端 URL；.code/<name> 已存在时可省略")
    command.add_argument("--name", help="`.code/` 下的目录名，默认取自来源")
    command.add_argument("--base", default="HEAD", help="创建 Task 分支的基点")
    command.add_argument(
        "--no-checkout",
        dest="checkout",
        action="store_false",
        help="只创建分支和登记，不切换当前检出（并行 Task 使用）",
    )
    command.set_defaults(func=cmd_add_repo, checkout=True)

    command = subparsers.add_parser("add-worktree", help="为并行 Task 创建链接工作树")
    command.add_argument("task")
    command.add_argument("--path", help="工作树目录，默认 ../<仓库名>.worktrees/<task-id>")
    command.add_argument("--base", default="HEAD", help="创建 Task 分支的基点")
    command.set_defaults(func=cmd_add_worktree)

    command = subparsers.add_parser("remove-worktree", help="移除链接工作树，可选先合入主工作树")
    command.add_argument("task")
    command.add_argument("--merge", action="store_true", help="先把 Task 分支合入管理仓当前分支")
    command.add_argument("--force", action="store_true", help="忽略未提交改动和未登记代码仓")
    command.set_defaults(func=cmd_remove_worktree)

    command = subparsers.add_parser("set-next-action", help="选择并保存一个下一步")
    command.add_argument("record")
    command.add_argument("--node", help="这个动作推进的方向图节点")
    command.add_argument("--off-graph", help="动作不在方向图上的理由")
    command.add_argument("--kind", choices=ACTION_KINDS, required=True)
    command.add_argument("--action", required=True)
    command.add_argument("--target", required=True)
    command.add_argument("--done-when", required=True)
    command.add_argument("--why-now", required=True)
    command.add_argument("--source-ref", action="append", required=True)
    command.set_defaults(func=cmd_set_next_action)

    command = subparsers.add_parser("block", help="记录当前外部阻塞")
    command.add_argument("record")
    command.add_argument("--reason", required=True)
    command.add_argument("--unblock-when", required=True)
    command.set_defaults(func=cmd_block)

    command = subparsers.add_parser("checkpoint", help="追加一个证据检查点")
    command.add_argument("run")
    command.add_argument("--kind", choices=CHECKPOINT_KINDS, required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--result", required=True)
    command.add_argument("--evidence-ref", action="append", required=True)
    command.add_argument("--limitation", required=True)
    command.add_argument("--supersedes")
    command.set_defaults(func=cmd_checkpoint)

    command = subparsers.add_parser("close-run", help="关闭当前 Run")
    command.add_argument("run")
    command.add_argument("--verdict", choices=("passed", "failed", "blocked", "partial"), required=True)
    command.add_argument("--summary", required=True)
    command.set_defaults(func=cmd_close_run)

    command = subparsers.add_parser("close-loop", help="关闭当前 Loop")
    command.add_argument("loop")
    command.add_argument("--verdict", choices=("confirmed", "falsified", "blocked", "abandoned"), required=True)
    command.add_argument("--summary", required=True)
    command.add_argument("--revisit-when", help="放弃或暂缓时，什么新事实会让这个方向重新值得考虑")
    command.set_defaults(func=cmd_close_loop)

    command = subparsers.add_parser("close-task", help="关闭当前 Task")
    command.add_argument("task")
    command.add_argument("--verdict", choices=("completed", "blocked", "abandoned"), required=True)
    command.add_argument("--summary", required=True)
    command.set_defaults(func=cmd_close_task)

    command = subparsers.add_parser("check", help="校验记录的恢复结构")
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
        parser.exit(2, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
