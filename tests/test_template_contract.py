import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TemplateContractTest(unittest.TestCase):
    def test_required_entrypoints_exist(self):
        for path in (
            "README.md",
            "AGENTS.md",
            "CLAUDE.md",
            "PROJECT.md",
            ".agents/skills/bootstrap-project/SKILL.md",
            ".claude/skills/bootstrap-project/SKILL.md",
        ):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_claude_imports_the_root_rules(self):
        self.assertEqual((ROOT / "CLAUDE.md").read_text().strip(), "@AGENTS.md")

    def test_claude_wrapper_points_to_the_canonical_workflow(self):
        wrapper = (ROOT / ".claude/skills/bootstrap-project/SKILL.md").read_text()
        self.assertIn("name: bootstrap-project", wrapper)
        self.assertIn(".agents/skills/bootstrap-project/SKILL.md", wrapper)
        self.assertIn("discovery wrapper", wrapper)
        self.assertNotIn("## Workflow", wrapper)

    def test_bootstrap_skill_has_portable_metadata(self):
        text = (ROOT / ".agents/skills/bootstrap-project/SKILL.md").read_text()
        self.assertIn("name: bootstrap-project", text)
        self.assertIn("description:", text)
        self.assertNotIn("/home/", text)

    def test_plugin_and_record_surfaces_are_absent(self):
        for path in (".codex-plugin", ".agent-home", "agent_home", "tasks"):
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


if __name__ == "__main__":
    unittest.main()
