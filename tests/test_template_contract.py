import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".agents/skills/task-loop-run/scripts/workflow.py"
SKILLS = (
    "agent-home-sync",
    "bootstrap-project",
    "task-loop-run",
    "design-grill",
    "next-action",
    "evidence-checkpoint",
)


def plugin_surface_violations(root):
    """列出插件化安装面。

    `.agent-home/` 保存模板版本清单与模板仓缓存，是安装式项目的正常组成部分，只有它下面出现别的
    安装产物时才算违规。
    """
    violations = [
        name
        for name in (".codex-plugin", "agent_home", "marketplace.json")
        if (root / name).exists()
    ]
    state = root / ".agent-home"
    if state.is_dir():
        violations.extend(
            f".agent-home/{item.name}"
            for item in sorted(state.iterdir())
            if item.name not in ("manifest.json", "upstream")
        )
    return violations


class TemplateContractTest(unittest.TestCase):
    def environment(self):
        """固定 Git 身份并隔离用户配置，使测试不依赖执行机器的 Git 设置。"""
        values = dict(os.environ)
        values.update(
            {
                "GIT_AUTHOR_NAME": "template test",
                "GIT_AUTHOR_EMAIL": "template@example.com",
                "GIT_COMMITTER_NAME": "template test",
                "GIT_COMMITTER_EMAIL": "template@example.com",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
            }
        )
        return values

    def run_workflow(self, root, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(WORKFLOW), "--root", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout.strip()

    def git(self, cwd, *arguments, expected=0):
        result = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout.strip()

    def init_repository(self, path, filename):
        path.mkdir(parents=True, exist_ok=True)
        self.git(path, "init", "-q", "-b", "main")
        (path / filename).write_text("seed\n", encoding="utf-8")
        self.git(path, "add", "-A")
        self.git(path, "commit", "-qm", "init")
        return path

    def test_required_entrypoints_exist(self):
        for path in (
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
            "PROJECT.md",
            "LICENSE",
            "LICENSE.zh-CN",
            "docs/home-engineering.md",
            "docs/code-workspace.md",
            "docs/agent-home-usage.md",
            "docs/direction-graph.md",
            ".agents/scripts/agent_home.py",
        ):
            self.assertTrue((ROOT / path).is_file(), path)
        for skill in SKILLS:
            self.assertTrue((ROOT / f".agents/skills/{skill}/SKILL.md").is_file(), skill)
            self.assertTrue((ROOT / f".claude/skills/{skill}/SKILL.md").is_file(), skill)

    def test_claude_imports_the_root_rules(self):
        self.assertEqual((ROOT / "CLAUDE.md").read_text().strip(), "@AGENTS.md")

    def test_claude_wrappers_point_to_canonical_workflows(self):
        for skill in SKILLS:
            wrapper = (ROOT / f".claude/skills/{skill}/SKILL.md").read_text()
            self.assertIn(f"name: {skill}", wrapper)
            self.assertIn(f".agents/skills/{skill}/SKILL.md", wrapper)
            self.assertIn("发现包装层", wrapper)
            self.assertNotIn("## 工作流程", wrapper)

    def test_skills_have_portable_metadata_and_no_placeholders(self):
        for skill in SKILLS:
            path = ROOT / f".agents/skills/{skill}/SKILL.md"
            text = path.read_text()
            self.assertIn(f"name: {skill}", text)
            self.assertIn("description:", text)
            self.assertNotIn("/home/", text)
            self.assertNotIn("TODO", text)
            if skill != "bootstrap-project":
                metadata = ROOT / f".agents/skills/{skill}/agents/openai.yaml"
                self.assertTrue(metadata.is_file(), metadata)

    def test_plugin_surfaces_are_absent(self):
        self.assertEqual(plugin_surface_violations(ROOT), [])

    def test_template_manifest_is_not_a_plugin_surface(self):
        """安装式项目的 .agent-home/ 必须能通过这条契约，否则迁移后的项目会误报。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".agent-home").mkdir()
            (root / ".agent-home/manifest.json").write_text("{}", encoding="utf-8")
            (root / ".agent-home/upstream").mkdir()
            self.assertEqual(plugin_surface_violations(root), [])
            (root / ".codex-plugin").mkdir()
            (root / ".agent-home/marketplace.json").write_text("{}", encoding="utf-8")
            self.assertEqual(
                plugin_surface_violations(root),
                [".codex-plugin", ".agent-home/marketplace.json"],
            )

    def test_project_state_is_consistent(self):
        project = (ROOT / "PROJECT.md").read_text()
        if "agent-home-template:uninitialized" in project:
            self.assertIn("名称：未初始化", project)
            self.assertIn("目标：由首次项目请求确定", project)
        else:
            self.assertIn("- 名称：", project)
            self.assertIn("- 目标：", project)
            self.assertNotIn("名称：未初始化", project)
            self.assertNotIn("目标：由首次项目请求确定", project)

    def test_readme_has_one_replaceable_project_summary(self):
        readme = (ROOT / "README.md").read_text()
        self.assertEqual(readme.count("project-summary:start"), 1)
        self.assertEqual(readme.count("project-summary:end"), 1)
        for skill in SKILLS:
            self.assertIn(f"`{skill}`", readme)
        self.assertIn("docs/home-engineering.md", readme)

    def test_user_facing_surfaces_are_simplified_chinese(self):
        for skill in SKILLS:
            canonical = (ROOT / f".agents/skills/{skill}/SKILL.md").read_text()
            wrapper = (ROOT / f".claude/skills/{skill}/SKILL.md").read_text()
            metadata = (ROOT / f".agents/skills/{skill}/agents/openai.yaml").read_text()
            self.assertRegex(canonical, r"[\u4e00-\u9fff]")
            self.assertRegex(wrapper, r"[\u4e00-\u9fff]")
            self.assertRegex(metadata, r"[\u4e00-\u9fff]")
            self.assertNotIn("This file is only", wrapper)
            self.assertNotIn("Use $", metadata)
        help_text = self.run_workflow(ROOT, "--help")
        self.assertIn("仓库内置的 Task/Loop/Run 工作流", help_text)

    def test_home_engineering_doc_preserves_the_vision_and_stays_concise(self):
        document = (ROOT / "docs/home-engineering.md").read_text()
        for statement in (
            "由项目或组织拥有、独立于具体模型与 Harness 的持久工作环境",
            "模型提供智力，Harness 提供行动能力，Home 提供项目工作能力",
            "Home 保存七类项目能力",
            "它们不等于 Agent Home 本身",
            "Agent 可以更换，Harness 可以升级，Home 持续积累",
        ):
            self.assertIn(statement, document)
        self.assertLessEqual(len(document.splitlines()), 200)

    def test_terminology_rule_is_always_in_force(self):
        rules = (ROOT / "AGENTS.md").read_text()
        self.assertIn("## 术语（全局强制，任何时候都适用）", rules)
        for statement in (
            "使用标准术语，不造黑话",
            "以教科书、官方文档、",
            "不因场合非正式而放宽",
            "明确标注为自定义命名",
        ):
            self.assertIn(statement, rules)
        self.assertLess(rules.index("## 术语"), rules.index("## 启动顺序"))

    def test_install_and_upgrade_entrypoints_are_documented(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("agent-install:start", readme)
        self.assertIn("agent-install:end", readme)
        self.assertIn("git clone https://github.com/xchencehn/agent-home .agent-home/upstream", readme)
        self.assertIn(".agent-home/upstream/.agents/scripts/agent_home.py init", readme)
        self.assertIn(".agents/scripts/agent_home.py upgrade", readme)
        self.assertIn("docs/agent-home-usage.md", readme)
        rules = (ROOT / "AGENTS.md").read_text()
        self.assertIn("## 模板同步", rules)
        self.assertIn(".agent-home/manifest.json", rules)
        self.assertIn("agent-home-sync", rules)
        self.assertIn("/.agent-home/upstream/", (ROOT / ".gitignore").read_text())
        self.assertIn("agent-home-usage.md", (ROOT / "docs/README.md").read_text())

    def test_direction_graph_is_wired_into_navigation(self):
        navigation = (ROOT / ".agents/skills/next-action/SKILL.md").read_text()
        for statement in ("graph.json", "就绪", "requires", "--node", "revisit_when"):
            self.assertIn(statement, navigation)
        workflow_skill = (ROOT / ".agents/skills/task-loop-run/SKILL.md").read_text()
        self.assertIn("方向图", workflow_skill)
        self.assertIn("graph.json", workflow_skill)
        self.assertIn("graph.json", (ROOT / ".agents/skills/design-grill/SKILL.md").read_text())
        rules = (ROOT / "AGENTS.md").read_text()
        self.assertIn("graph.json", rules)
        self.assertIn("前置门禁", rules)
        self.assertIn("复活条件", rules)
        readme = (ROOT / "README.md").read_text()
        self.assertIn("docs/direction-graph.md", readme)
        self.assertIn("direction-graph.md", (ROOT / "docs/README.md").read_text())

    def test_code_workspace_is_ignored_and_documented(self):
        self.assertIn("/.code/", (ROOT / ".gitignore").read_text())
        rules = (ROOT / "AGENTS.md").read_text()
        for statement in ("`.code/<repo>/`", "task/<task-id>", "add-repo", "add-worktree", "remove-worktree"):
            self.assertIn(statement, rules)
        readme = (ROOT / "README.md").read_text()
        self.assertIn("`.code/`", readme)
        self.assertIn("docs/code-workspace.md", readme)
        self.assertIn("code-workspace.md", (ROOT / "docs/README.md").read_text())
        workflow_skill = (ROOT / ".agents/skills/task-loop-run/SKILL.md").read_text()
        self.assertIn("add-repo", workflow_skill)
        self.assertIn("add-worktree", workflow_skill)

    def test_task_branch_and_parallel_worktree_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            upstream = self.init_repository(base / "upstream", "main.c")
            root = self.init_repository(base / "home", "PROJECT.md")
            (root / ".gitignore").write_text("/.code/\n", encoding="utf-8")
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "ignore code workspace")

            first = self.run_workflow(
                root, "open-task", "alpha", "--title", "第一个", "--objective", "第一个目标"
            )
            second = self.run_workflow(
                root, "open-task", "beta", "--title", "第二个", "--objective", "第二个目标"
            )

            registered = self.run_workflow(
                root, "add-repo", first, "--source", str(upstream), "--name", "demo"
            )
            self.assertEqual(registered, ".code/demo")
            code = root / ".code" / "demo"
            self.assertEqual(self.git(code, "rev-parse", "--abbrev-ref", "HEAD"), "task/001_alpha")
            self.assertEqual(self.git(root, "status", "--porcelain", "--", ".code"), "")

            self.run_workflow(
                root, "add-repo", second, "--source", str(upstream), "--name", "demo", "--no-checkout"
            )
            self.assertEqual(self.git(code, "rev-parse", "--abbrev-ref", "HEAD"), "task/001_alpha")
            entry = json.loads((root / second / "task.json").read_text())["repos"][0]
            self.assertEqual(entry["path"], ".code/demo")
            self.assertEqual(entry["branch"], "task/002_beta")

            self.run_workflow(root, "add-worktree", second, expected=2)
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "open tasks")

            worktree = Path(self.run_workflow(root, "add-worktree", second))
            self.assertTrue((worktree / second / "task.json").is_file())
            self.assertEqual(
                self.git(worktree / ".code" / "demo", "rev-parse", "--abbrev-ref", "HEAD"),
                "task/002_beta",
            )
            self.assertEqual(self.git(code, "rev-parse", "--abbrev-ref", "HEAD"), "task/001_alpha")
            self.run_workflow(
                root, "add-repo", second, "--source", str(upstream), "--name", "demo", expected=2
            )

            (worktree / ".code" / "demo" / "main.c").write_text("changed\n", encoding="utf-8")
            self.git(worktree / ".code" / "demo", "commit", "-qam", "beta code change")
            (worktree / second / "note.md").write_text("beta\n", encoding="utf-8")
            self.git(worktree, "add", "-A")
            self.git(worktree, "commit", "-qm", "record beta")

            self.run_workflow(root, "remove-worktree", second, "--merge")
            self.assertFalse(worktree.exists())
            self.assertTrue((root / second / "note.md").is_file())
            self.assertIn("beta code change", self.git(code, "log", "--oneline", "task/002_beta"))
            self.assertEqual(self.git(root, "status", "--porcelain"), "")
            self.assertEqual(self.run_workflow(root, "check"), "通过")

    def test_check_rejects_inconsistent_repo_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = self.run_workflow(
                root, "open-task", "alpha", "--title", "标题", "--objective", "目标"
            )
            record_path = root / task / "task.json"
            record = json.loads(record_path.read_text())
            self.assertEqual(record["repos"], [])
            for broken in (
                {"name": "demo", "path": ".code/demo", "branch": "task/999_other"},
                {"name": "demo", "path": "code/demo", "branch": "task/001_alpha"},
                {"name": "demo", "branch": "task/001_alpha"},
            ):
                record["repos"] = [broken]
                record_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
                self.run_workflow(root, "check", expected=2)

    def test_task_loop_run_round_trip_and_contract_immutability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = self.run_workflow(
                root,
                "open-task",
                "compiler-research",
                "--title",
                "编译器研究",
                "--objective",
                "找到发生故障的编译器层级",
                "--acceptance",
                "有证据支持故障层级结论",
            )
            self.run_workflow(
                root,
                "set-next-action",
                task,
                "--kind",
                "clarify",
                "--action",
                "检查最小失败产物",
                "--target",
                "故障边界",
                "--done-when",
                "形成一个可证伪假设",
                "--why-now",
                "它能减少主要未知项",
                "--source-ref",
                "PROJECT.md",
            )
            loop = self.run_workflow(
                root,
                "open-loop",
                task,
                "lowering",
                "--goal",
                "验证下沉阶段是否引入故障",
                "--hypothesis",
                "第一个无效 IR 出现在下沉阶段",
                "--acceptance",
                "前后 IR 能隔离第一个无效形态",
                "--falsification",
                "无效形态在下沉前已经存在",
            )
            self.assertIn("# Loop 目标", (root / loop / "goal.md").read_text())
            self.assertIn("## 验收条件", (root / loop / "goal.md").read_text())
            self.assertIn("# 假设", (root / loop / "hypotheses.md").read_text())
            run = self.run_workflow(
                root,
                "open-run",
                loop,
                "minimal-probe",
                "--objective",
                "生成最小前后 IR 对",
                "--acceptance",
                "两份 IR 均已捕获且可以比较",
                "--allowed-change",
                "只允许临时探针",
            )
            contract = root / run / "contract.json"
            original_contract = contract.read_bytes()
            self.run_workflow(
                root,
                "set-next-action",
                run,
                "--kind",
                "execute",
                "--action",
                "运行最小编译器探针",
                "--target",
                "前后 IR",
                "--done-when",
                "两份 IR 文件都存在",
                "--why-now",
                "Run 合同已经清晰",
                "--source-ref",
                f"{run}/contract.json",
            )
            self.run_workflow(
                root,
                "checkpoint",
                run,
                "--kind",
                "validation",
                "--summary",
                "第一个无效形态出现在下沉之后",
                "--result",
                "下沉前 IR 有效，下沉后 IR 无效",
                "--evidence-ref",
                "artifacts/before.mlir",
                "--evidence-ref",
                "artifacts/after.mlir",
                "--limitation",
                "探针只覆盖一个最小用例",
            )
            self.run_workflow(
                root,
                "close-run",
                run,
                "--verdict",
                "passed",
                "--summary",
                "探针隔离了下沉边界",
            )
            self.assertEqual(contract.read_bytes(), original_contract)
            self.run_workflow(
                root,
                "close-loop",
                loop,
                "--verdict",
                "confirmed",
                "--summary",
                "下沉是第一个发生故障的层级",
            )
            self.run_workflow(
                root,
                "close-task",
                task,
                "--verdict",
                "completed",
                "--summary",
                "已经识别发生故障的编译器层级",
            )
            self.assertEqual(self.run_workflow(root, "check"), "通过")
            result = json.loads((root / run / "result.json").read_text())
            self.assertEqual(result["verdict"], "passed")
            self.assertEqual(result["checkpoint_refs"], ["CP001"])
            changed_contract = json.loads(contract.read_text())
            changed_contract["objective"] = "执行后被改写"
            contract.write_text(json.dumps(changed_contract))
            self.run_workflow(root, "check", run, expected=2)

    def test_one_active_loop_and_run_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = self.run_workflow(
                root,
                "open-task",
                "one",
                "--title",
                "唯一方向",
                "--objective",
                "一个目标",
            )
            rejected = self.run_workflow(
                root,
                "set-next-action",
                task,
                "--kind",
                "execute",
                "--action",
                "实施未知方向",
                "--target",
                "模糊目标",
                "--done-when",
                "实现已经存在",
                "--why-now",
                "没有有效理由",
                "--source-ref",
                "PROJECT.md",
                expected=2,
            )
            self.assertEqual(rejected, "")
            loop = self.run_workflow(
                root,
                "open-loop",
                task,
                "first",
                "--goal",
                "第一个方向",
                "--hypothesis",
                "第一个假设",
                "--acceptance",
                "第一份证据",
                "--falsification",
                "相反证据",
            )
            duplicate = self.run_workflow(
                root,
                "open-loop",
                task,
                "second",
                "--goal",
                "第二个方向",
                "--hypothesis",
                "第二个假设",
                "--acceptance",
                "第二份证据",
                "--falsification",
                "相反证据",
                expected=2,
            )
            self.assertEqual(duplicate, "")
            self.run_workflow(
                root,
                "open-run",
                loop,
                "first",
                "--objective",
                "第一次执行",
                "--acceptance",
                "已观察到结果",
            )
            duplicate = self.run_workflow(
                root,
                "open-run",
                loop,
                "second",
                "--objective",
                "第二次执行",
                "--acceptance",
                "已观察到结果",
                expected=2,
            )
            self.assertEqual(duplicate, "")


if __name__ == "__main__":
    unittest.main()
