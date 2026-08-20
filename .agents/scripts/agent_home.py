#!/usr/bin/env python3

"""Agent Home 模板的安装与同步器。

在空目录里安装：

    git clone <模板仓 URL> .agent-home/upstream
    python3 .agent-home/upstream/.agents/scripts/agent_home.py init

之后在项目里同步模板：

    python3 .agents/scripts/agent_home.py upgrade
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
STATE_DIR = ".agent-home"
UPSTREAM_DIR = "upstream"
MANIFEST_NAME = "manifest.json"
SCRIPT_PATH = ".agents/scripts/agent_home.py"
DEFAULT_SOURCE = "https://github.com/xchencehn/agent-home"
DEFAULT_REF = "main"
# 受模板管理的路径：升级时按三方合并更新
MANAGED_ROOTS = ("AGENTS.md", "CLAUDE.md", ".agents", ".claude/skills")
# 只在缺失时写入的种子文件：写入后归项目所有，升级不再改动
SEED_FILES = ("PROJECT.md",)
IGNORE_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache"}
GITIGNORE_START = "# agent-home:start"
GITIGNORE_END = "# agent-home:end"
GITIGNORE_ENTRIES = ("/.code/", "/.agent-home/upstream/")
USERINFO_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*://)[^/@]*@")


class AgentHomeError(Exception):
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
        message = message.replace("the following arguments are required:", "缺少必需参数：")
        message = message.replace("unrecognized arguments:", "无法识别的参数：")
        message = message.replace("invalid choice:", "值无效：")
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}：错误：{message}\n")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentHomeError(f"缺少文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise AgentHomeError(f"JSON 无效：{path}：{exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def git(cwd, *arguments, check=True):
    result = subprocess.run(
        ["git", "-C", str(cwd), *arguments], text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentHomeError(f"git {' '.join(arguments)} 失败：{detail}")
    return result


def git_output(cwd, *arguments):
    return git(cwd, *arguments).stdout.strip()


def git_succeeds(cwd, *arguments):
    return git(cwd, *arguments, check=False).returncode == 0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sanitize_source(url):
    """去掉 URL 中的用户名与令牌，只保留可记录的来源。"""
    return USERINFO_RE.sub(r"\1", url) if url else url


def state_path(target):
    return target / STATE_DIR


def manifest_path(target):
    return state_path(target) / MANIFEST_NAME


def upstream_path(target):
    return state_path(target) / UPSTREAM_DIR


def script_repository():
    """脚本所在的模板仓根目录。"""
    here = Path(__file__).resolve().parent
    if not git_succeeds(here, "rev-parse", "--is-inside-work-tree"):
        raise AgentHomeError(f"脚本不在 Git 工作树内，无法确定模板来源：{here}")
    return Path(git_output(here, "rev-parse", "--show-toplevel")).resolve()


def default_target(upstream):
    """脚本从 <项目>/.agent-home/upstream 运行时，默认目标就是该项目。"""
    parts = upstream.parts
    if len(parts) >= 3 and parts[-1] == UPSTREAM_DIR and parts[-2] == STATE_DIR:
        return Path(*parts[:-2])
    return Path.cwd().resolve()


def managed_target(reference):
    """向上查找已经由 agent-home 管理的目录。"""
    start = Path(reference).resolve() if reference else Path.cwd().resolve()
    for path in (start, *start.parents):
        if (path / STATE_DIR / MANIFEST_NAME).is_file():
            return path
    raise AgentHomeError(f"{start} 及其上级目录都没有 {STATE_DIR}/{MANIFEST_NAME}，请先运行 init")


def managed_files(root):
    """列出模板仓里受管理的文件，路径相对于仓库根。"""
    found = []
    for entry in MANAGED_ROOTS:
        path = root / entry
        if path.is_file():
            found.append(entry)
        elif path.is_dir():
            for item in path.rglob("*"):
                relative = item.relative_to(root)
                if item.is_file() and not IGNORE_NAMES.intersection(relative.parts):
                    found.append(relative.as_posix())
    return sorted(set(found))


def write_file(target, relative, data, mode=None):
    path = target / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mode is not None:
        path.chmod(mode)


def remote_url(repository):
    result = git(repository, "remote", "get-url", "origin", check=False)
    return sanitize_source(result.stdout.strip()) if result.returncode == 0 else None


def clone_upstream(source, destination, ref):
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--quiet", "--branch", ref, str(source), str(destination)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AgentHomeError(f"克隆模板仓失败：{(result.stderr or result.stdout).strip()}")


def ensure_upstream(target, source, ref):
    """准备本地模板仓缓存，并检出到 origin/<ref>。"""
    upstream = upstream_path(target)
    if not (upstream / ".git").exists():
        if upstream.exists() and any(upstream.iterdir()):
            raise AgentHomeError(f"{upstream} 已存在且不是 Git 仓库")
        clone_upstream(source, upstream, ref)
    else:
        git(upstream, "remote", "set-url", "origin", source)
        git(upstream, "fetch", "--quiet", "origin", ref)
    git(upstream, "checkout", "--quiet", "--detach", f"origin/{ref}")
    return upstream


def update_gitignore(target):
    """维护 .gitignore 中带标记的 agent-home 区块。"""
    block = "\n".join((GITIGNORE_START, *GITIGNORE_ENTRIES, GITIGNORE_END))
    path = target / ".gitignore"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if GITIGNORE_START in text and GITIGNORE_END in text:
        head = text[: text.index(GITIGNORE_START)]
        tail = text[text.index(GITIGNORE_END) + len(GITIGNORE_END) :]
        updated = head + block + tail
    else:
        separator = "" if not text or text.endswith("\n") else "\n"
        updated = f"{text}{separator}{block}\n"
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def merge_three_way(base, ours, theirs):
    """三方合并，返回 (合并结果, 是否冲突)。"""
    with tempfile.TemporaryDirectory() as directory:
        room = Path(directory)
        names = {"base": base, "ours": ours, "theirs": theirs}
        for name, data in names.items():
            (room / name).write_bytes(data)
        result = subprocess.run(
            [
                "git",
                "merge-file",
                "-p",
                "-L",
                "本地",
                "-L",
                "上次同步的模板",
                "-L",
                "新模板",
                str(room / "ours"),
                str(room / "base"),
                str(room / "theirs"),
            ],
            capture_output=True,
            check=False,
        )
    if result.returncode < 0:
        raise AgentHomeError("git merge-file 执行失败")
    return result.stdout, result.returncode > 0


def report_line(title, items):
    return f"{title}（{len(items)}）：" + "、".join(items) if items else None


def print_report(report, header):
    print(header)
    labels = (
        ("added", "新增"),
        ("updated", "更新"),
        ("merged", "合并本地改动"),
        ("kept", "保留本地改动"),
        ("conflicted", "冲突待处理"),
        ("removed", "删除"),
        ("orphaned", "上游已删除但本地有改动"),
        ("unchanged", "无变化"),
    )
    for key, label in labels:
        items = report.get(key, [])
        if not items:
            continue
        if key == "unchanged":
            print(f"- {label}：{len(items)} 个文件")
            continue
        print(f"- {label}（{len(items)}）：{'、'.join(items)}")


def cmd_init(args):
    upstream_repository = script_repository()
    target = Path(args.target).expanduser().resolve() if args.target else default_target(upstream_repository)
    target.mkdir(parents=True, exist_ok=True)
    if manifest_path(target).is_file() and not args.force:
        raise AgentHomeError(f"{target} 已经由 agent-home 管理，请改用 upgrade")
    source = sanitize_source(args.source) or remote_url(upstream_repository) or DEFAULT_SOURCE
    ref = args.ref or git_output(upstream_repository, "rev-parse", "--abbrev-ref", "HEAD")
    if ref == "HEAD":
        ref = DEFAULT_REF
    commit = git_output(upstream_repository, "rev-parse", "HEAD")

    files = managed_files(upstream_repository)
    if not files:
        raise AgentHomeError(f"模板仓没有受管理的文件：{upstream_repository}")
    occupied = []
    for relative in files:
        existing = target / relative
        if existing.is_file() and existing.read_bytes() != (upstream_repository / relative).read_bytes():
            occupied.append(relative)
    if occupied and not args.force:
        raise AgentHomeError(
            "以下文件已存在且与模板不同，确认可以覆盖后加 --force：" + "、".join(occupied)
        )

    report = {"added": [], "updated": [], "seeded": []}
    manifest_files = {}
    for relative in files:
        source_file = upstream_repository / relative
        data = source_file.read_bytes()
        destination = target / relative
        state = "updated" if destination.is_file() else "added"
        write_file(target, relative, data, source_file.stat().st_mode & 0o777)
        manifest_files[relative] = {"sha256": digest(data), "commit": commit}
        report[state].append(relative)
    for relative in SEED_FILES:
        seed = upstream_repository / relative
        if seed.is_file() and not (target / relative).exists():
            write_file(target, relative, seed.read_bytes())
            report["seeded"].append(relative)

    update_gitignore(target)
    if not args.no_git and not git_succeeds(target, "rev-parse", "--is-inside-work-tree"):
        if not git_succeeds(target, "init", "--quiet", "-b", DEFAULT_REF):
            git(target, "init", "--quiet")

    upstream = upstream_path(target)
    if upstream_repository != upstream.resolve():
        if not (upstream / ".git").exists():
            clone_upstream(upstream_repository, upstream, ref)
        git(upstream, "remote", "set-url", "origin", source)
    else:
        git(upstream, "remote", "set-url", "origin", source)

    write_json(
        manifest_path(target),
        {
            "schema_version": SCHEMA_VERSION,
            "source": source,
            "ref": ref,
            "commit": commit,
            "installed_at": now(),
            "updated_at": now(),
            "managed_roots": list(MANAGED_ROOTS),
            "files": manifest_files,
        },
    )
    print_report(report, f"已在 {target} 安装 agent-home（{source} @ {commit[:7]}）")
    if report["seeded"]:
        print(f"- 写入种子文件：{'、'.join(report['seeded'])}")
    print("下一步：读取 AGENTS.md，再用 bootstrap-project 完成 PROJECT.md 初始化。")


def maybe_reexec(args, target, upstream):
    """升级逻辑以新模板里的脚本为准，避免旧脚本按旧规则升级。"""
    if args.no_reexec:
        return
    candidate = upstream / SCRIPT_PATH
    running = Path(__file__).resolve()
    if not candidate.is_file() or candidate.resolve() == running:
        return
    if digest(candidate.read_bytes()) == digest(running.read_bytes()):
        return
    command = [sys.executable, str(candidate), "upgrade", "--target", str(target), "--no-reexec"]
    if args.ref:
        command += ["--ref", args.ref]
    if args.source:
        command += ["--source", args.source]
    if args.dry_run:
        command.append("--dry-run")
    os.execv(sys.executable, command)


def cmd_upgrade(args):
    target = managed_target(args.target)
    manifest = read_json(manifest_path(target))
    source = sanitize_source(args.source) or manifest.get("source") or DEFAULT_SOURCE
    ref = args.ref or manifest.get("ref") or DEFAULT_REF
    upstream = ensure_upstream(target, source, ref)
    maybe_reexec(args, target, upstream)

    commit = git_output(upstream, "rev-parse", "HEAD")
    recorded = manifest.get("files", {})
    files = managed_files(upstream)
    report = {key: [] for key in ("added", "updated", "merged", "kept", "conflicted", "removed", "orphaned", "unchanged")}
    updated_files = dict(recorded)

    for relative in files:
        new_data = (upstream / relative).read_bytes()
        new_digest = digest(new_data)
        entry = recorded.get(relative)
        local = target / relative
        mode = (upstream / relative).stat().st_mode & 0o777
        if not local.is_file():
            if not args.dry_run:
                write_file(target, relative, new_data, mode)
            report["added"].append(relative)
            updated_files[relative] = {"sha256": new_digest, "commit": commit}
            continue
        local_data = local.read_bytes()
        local_digest = digest(local_data)
        base_digest = entry.get("sha256") if entry else None
        if local_digest == new_digest:
            report["unchanged"].append(relative)
            updated_files[relative] = {"sha256": new_digest, "commit": commit}
            continue
        if base_digest == local_digest:
            if not args.dry_run:
                write_file(target, relative, new_data, mode)
            report["updated"].append(relative)
            updated_files[relative] = {"sha256": new_digest, "commit": commit}
            continue
        if base_digest == new_digest:
            report["kept"].append(relative)
            continue
        base_data = None
        if entry and entry.get("commit"):
            result = git(upstream, "show", f"{entry['commit']}:{relative}", check=False)
            if result.returncode == 0:
                base_data = result.stdout.encode("utf-8")
        if base_data is None:
            report["conflicted"].append(relative)
            if not args.dry_run:
                write_file(target, f"{relative}.agent-home-{commit[:7]}.new", new_data, mode)
            continue
        merged, conflicted = merge_three_way(base_data, local_data, new_data)
        if conflicted:
            report["conflicted"].append(relative)
            if not args.dry_run:
                write_file(target, f"{relative}.agent-home-{commit[:7]}.new", new_data, mode)
            continue
        if not args.dry_run:
            write_file(target, relative, merged, mode)
        report["merged"].append(relative)
        updated_files[relative] = {"sha256": new_digest, "commit": commit}

    for relative in sorted(set(recorded) - set(files)):
        local = target / relative
        entry = recorded[relative]
        if not local.is_file():
            updated_files.pop(relative, None)
            continue
        if digest(local.read_bytes()) == entry.get("sha256"):
            if not args.dry_run:
                local.unlink()
            report["removed"].append(relative)
            updated_files.pop(relative, None)
        else:
            report["orphaned"].append(relative)

    if not args.dry_run:
        changed_gitignore = update_gitignore(target)
        manifest.update(
            {
                "schema_version": SCHEMA_VERSION,
                "source": source,
                "ref": ref,
                "commit": commit,
                "updated_at": now(),
                "managed_roots": list(MANAGED_ROOTS),
                "files": updated_files,
            }
        )
        write_json(manifest_path(target), manifest)
    else:
        changed_gitignore = False

    previous = manifest.get("commit")
    header = f"agent-home 同步完成：{source} @ {commit[:7]}"
    if args.dry_run:
        header = f"agent-home 同步预演（未写入）：{source} @ {commit[:7]}"
    print_report(report, header)
    if changed_gitignore:
        print("- 更新 .gitignore 的 agent-home 区块")
    if report["conflicted"]:
        print("冲突文件保留了本地内容，新模板版本写在同名 .new 文件里，需要人工合并后删除 .new。")
    print("建议随后运行项目自己的测试确认规则与技能可用。")
    return 0 if not report["conflicted"] else 1


def cmd_status(args):
    target = managed_target(args.target)
    manifest = read_json(manifest_path(target))
    recorded = manifest.get("files", {})
    drifted = []
    missing = []
    for relative, entry in sorted(recorded.items()):
        path = target / relative
        if not path.is_file():
            missing.append(relative)
        elif digest(path.read_bytes()) != entry.get("sha256"):
            drifted.append(relative)
    print(f"项目：{target}")
    print(f"模板来源：{manifest.get('source')}（分支 {manifest.get('ref')}）")
    print(f"已同步版本：{str(manifest.get('commit'))[:7]}，最后同步 {manifest.get('updated_at')}")
    print(f"受管理文件：{len(recorded)} 个")
    print(f"本地已改动：{'、'.join(drifted) if drifted else '无'}")
    print(f"本地缺失：{'、'.join(missing) if missing else '无'}")
    if args.fetch:
        upstream = ensure_upstream(target, manifest.get("source", DEFAULT_SOURCE), manifest.get("ref", DEFAULT_REF))
        latest = git_output(upstream, "rev-parse", "HEAD")
        if latest == manifest.get("commit"):
            print("上游状态：已是最新")
        else:
            count = git_output(upstream, "rev-list", "--count", f"{manifest.get('commit')}..{latest}")
            print(f"上游状态：有 {count} 个新提交，最新 {latest[:7]}，运行 upgrade 同步")


def build_parser():
    parser = ChineseArgumentParser(description="Agent Home 模板的安装与同步器")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=ChineseArgumentParser)

    command = subparsers.add_parser("init", help="把模板安装到一个项目目录")
    command.add_argument("--target", help="项目目录，默认取当前目录或 .agent-home/upstream 的上级项目")
    command.add_argument("--source", help="记录到清单的模板仓 URL，默认取脚本所在仓的 origin")
    command.add_argument("--ref", help="模板分支，默认取脚本所在仓的当前分支")
    command.add_argument("--no-git", action="store_true", help="目标不是 Git 仓库时也不执行 git init")
    command.add_argument("--force", action="store_true", help="覆盖已存在且不同的受管理文件")
    command.set_defaults(func=cmd_init)

    command = subparsers.add_parser("upgrade", help="把模板的新版本同步到当前项目")
    command.add_argument("--target", help="项目目录，默认从当前目录向上查找")
    command.add_argument("--source", help="改用其它模板仓 URL")
    command.add_argument("--ref", help="改用其它模板分支")
    command.add_argument("--dry-run", action="store_true", help="只报告将要发生的变化")
    command.add_argument("--no-reexec", action="store_true", help="不切换到新模板里的同步器")
    command.set_defaults(func=cmd_upgrade)

    command = subparsers.add_parser("status", help="显示模板版本与本地改动")
    command.add_argument("--target", help="项目目录，默认从当前目录向上查找")
    command.add_argument("--fetch", action="store_true", help="联网检查上游是否有新提交")
    command.set_defaults(func=cmd_status)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        sys.exit(args.func(args) or 0)
    except AgentHomeError as exc:
        parser.exit(2, f"错误：{exc}\n")


if __name__ == "__main__":
    main()
