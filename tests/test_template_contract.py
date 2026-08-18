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
        for path in ("README.md", "AGENTS.md", "CLAUDE.md", "PROJECT.md", "LICENSE"):
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
            self.assertIn("discovery wrapper", wrapper)
            self.assertNotIn("## Workflow", wrapper)

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

    def test_task_loop_run_round_trip_and_contract_immutability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = self.run_workflow(
                root,
                "open-task",
                "compiler-research",
                "--title",
                "Compiler Research",
                "--objective",
                "Find the failing compiler layer",
                "--acceptance",
                "The failing layer is supported by evidence",
            )
            self.run_workflow(
                root,
                "set-next-action",
                task,
                "--kind",
                "clarify",
                "--action",
                "Inspect the smallest failing artifact",
                "--target",
                "failure boundary",
                "--done-when",
                "one falsifiable hypothesis exists",
                "--why-now",
                "it reduces the main uncertainty",
                "--source-ref",
                "PROJECT.md",
            )
            loop = self.run_workflow(
                root,
                "open-loop",
                task,
                "lowering",
                "--goal",
                "Test whether lowering introduces the failure",
                "--hypothesis",
                "The first invalid IR appears during lowering",
                "--acceptance",
                "Before and after IR isolate the first invalid form",
                "--falsification",
                "The invalid form exists before lowering",
            )
            run = self.run_workflow(
                root,
                "open-run",
                loop,
                "minimal-probe",
                "--objective",
                "Generate the smallest before and after IR pair",
                "--acceptance",
                "Both IR files are captured and comparable",
                "--allowed-change",
                "temporary probe only",
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
                "Run the minimal compiler probe",
                "--target",
                "before and after IR",
                "--done-when",
                "both IR files exist",
                "--why-now",
                "the Run contract is clear",
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
                "The first invalid form appears after lowering",
                "--result",
                "Before IR is valid and after IR is invalid",
                "--evidence-ref",
                "artifacts/before.mlir",
                "--evidence-ref",
                "artifacts/after.mlir",
                "--limitation",
                "The probe covers one minimized case",
            )
            self.run_workflow(
                root,
                "close-run",
                run,
                "--verdict",
                "passed",
                "--summary",
                "The probe isolated the lowering boundary",
            )
            self.assertEqual(contract.read_bytes(), original_contract)
            self.run_workflow(
                root,
                "close-loop",
                loop,
                "--verdict",
                "confirmed",
                "--summary",
                "Lowering is the first failing layer",
            )
            self.run_workflow(
                root,
                "close-task",
                task,
                "--verdict",
                "completed",
                "--summary",
                "The failing compiler layer is identified",
            )
            self.assertEqual(self.run_workflow(root, "check"), "ok")
            result = json.loads((root / run / "result.json").read_text())
            self.assertEqual(result["verdict"], "passed")
            self.assertEqual(result["checkpoint_refs"], ["CP001"])
            changed_contract = json.loads(contract.read_text())
            changed_contract["objective"] = "Rewritten after execution"
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
                "One",
                "--objective",
                "One objective",
            )
            rejected = self.run_workflow(
                root,
                "set-next-action",
                task,
                "--kind",
                "execute",
                "--action",
                "Implement an unknown direction",
                "--target",
                "foggy objective",
                "--done-when",
                "implementation exists",
                "--why-now",
                "no valid reason",
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
                "First direction",
                "--hypothesis",
                "First hypothesis",
                "--acceptance",
                "First evidence",
                "--falsification",
                "Contrary evidence",
            )
            duplicate = self.run_workflow(
                root,
                "open-loop",
                task,
                "second",
                "--goal",
                "Second direction",
                "--hypothesis",
                "Second hypothesis",
                "--acceptance",
                "Second evidence",
                "--falsification",
                "Contrary evidence",
                expected=2,
            )
            self.assertEqual(duplicate, "")
            self.run_workflow(
                root,
                "open-run",
                loop,
                "first",
                "--objective",
                "First execution",
                "--acceptance",
                "Observed result",
            )
            duplicate = self.run_workflow(
                root,
                "open-run",
                loop,
                "second",
                "--objective",
                "Second execution",
                "--acceptance",
                "Observed result",
                expected=2,
            )
            self.assertEqual(duplicate, "")


if __name__ == "__main__":
    unittest.main()
