import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".agents/skills/task-loop-run/scripts/workflow.py"
SKILLS = (
    "bootstrap-project",
    "task-loop-run",
    "design-grill",
    "next-action",
    "evidence-checkpoint",
)


class TemplateContractTest(unittest.TestCase):
    def run_workflow(self, root, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(WORKFLOW), "--root", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout.strip()

    def test_required_entrypoints_exist(self):
        for path in (
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
            "PROJECT.md",
            "LICENSE",
            "LICENSE.zh-CN",
            "docs/home-engineering.md",
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
        for path in (".codex-plugin", ".agent-home", "agent_home"):
            self.assertFalse((ROOT / path).exists(), path)

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
