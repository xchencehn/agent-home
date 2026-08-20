import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / ".agents/scripts/agent_home.py"
TEMPLATE_AGENTS = """# 模板规则

## 第一节

第一条
第二条

## 第二节

第三条
"""


class AgentHomeSyncTest(unittest.TestCase):
    def environment(self):
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

    def run_installer(self, script, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(script), *arguments],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout.strip()

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="agent-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.template = self.base / "template"
        self.build_template(self.template)

    def build_template(self, path):
        (path / ".agents/scripts").mkdir(parents=True)
        (path / ".agents/skills/demo").mkdir(parents=True)
        (path / ".claude/skills/demo").mkdir(parents=True)
        shutil.copy2(INSTALLER, path / ".agents/scripts/agent_home.py")
        (path / "AGENTS.md").write_text(TEMPLATE_AGENTS, encoding="utf-8")
        (path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (path / "PROJECT.md").write_text(
            "<!-- agent-home-template:uninitialized -->\n# 项目说明\n", encoding="utf-8"
        )
        (path / "README.md").write_text("# 模板自己的说明\n", encoding="utf-8")
        (path / ".agents/skills/demo/SKILL.md").write_text(
            "---\nname: demo\ndescription: 演示。\n---\n\n# 演示\n", encoding="utf-8"
        )
        (path / ".claude/skills/demo/SKILL.md").write_text(
            "---\nname: demo\ndescription: 演示。\n---\n\n发现包装层\n", encoding="utf-8"
        )
        self.git(path, "init", "--quiet", "-b", "main")
        self.git(path, "add", "-A")
        self.git(path, "commit", "--quiet", "-m", "template")

    def publish(self, message):
        self.git(self.template, "add", "-A")
        self.git(self.template, "commit", "--quiet", "-m", message)
        return self.git(self.template, "rev-parse", "HEAD")

    def install(self, name="my-project"):
        target = self.base / name
        target.mkdir()
        self.git(target, "clone", "--quiet", str(self.template), ".agent-home/upstream")
        self.run_installer(target / ".agent-home/upstream/.agents/scripts/agent_home.py", "init")
        return target

    def manifest(self, target):
        return json.loads((target / ".agent-home/manifest.json").read_text(encoding="utf-8"))

    def upgrade(self, target, *arguments, expected=0):
        return self.run_installer(
            target / ".agents/scripts/agent_home.py",
            "upgrade",
            "--target",
            str(target),
            *arguments,
            expected=expected,
        )

    def test_init_installs_managed_files_and_leaves_project_ownership(self):
        target = self.install()
        for relative in (
            "AGENTS.md",
            "CLAUDE.md",
            ".agents/scripts/agent_home.py",
            ".agents/skills/demo/SKILL.md",
            ".claude/skills/demo/SKILL.md",
        ):
            self.assertTrue((target / relative).is_file(), relative)
            self.assertEqual(
                (target / relative).read_bytes(), (self.template / relative).read_bytes()
            )
        self.assertTrue((target / "PROJECT.md").is_file())
        self.assertFalse((target / "README.md").exists())
        self.assertIn("/.code/", (target / ".gitignore").read_text())
        self.assertIn("/.agent-home/upstream/", (target / ".gitignore").read_text())
        self.assertEqual(self.git(target, "remote"), "")

        manifest = self.manifest(target)
        self.assertEqual(manifest["ref"], "main")
        self.assertEqual(manifest["commit"], self.git(self.template, "rev-parse", "HEAD"))
        self.assertIn("AGENTS.md", manifest["files"])
        self.assertEqual(
            manifest["files"]["AGENTS.md"]["sha256"],
            hashlib.sha256(TEMPLATE_AGENTS.encode("utf-8")).hexdigest(),
        )
        ignored = self.git(target, "status", "--porcelain", "--", ".agent-home/upstream")
        self.assertEqual(ignored, "")

    def test_init_refuses_to_overwrite_different_content(self):
        target = self.base / "occupied"
        target.mkdir()
        (target / "AGENTS.md").write_text("项目自己的规则\n", encoding="utf-8")
        self.git(target, "clone", "--quiet", str(self.template), ".agent-home/upstream")
        script = target / ".agent-home/upstream/.agents/scripts/agent_home.py"
        self.run_installer(script, "init", expected=2)
        self.assertEqual((target / "AGENTS.md").read_text(), "项目自己的规则\n")
        self.run_installer(script, "init", "--force")
        self.assertEqual((target / "AGENTS.md").read_text(), TEMPLATE_AGENTS)

    def test_upgrade_updates_untouched_files_and_merges_local_edits(self):
        target = self.install()
        (self.template / ".agents/skills/demo/SKILL.md").write_text(
            "---\nname: demo\ndescription: 演示。\n---\n\n# 演示\n\n上游新增说明。\n", encoding="utf-8"
        )
        (self.template / ".agents/skills/extra").mkdir(parents=True)
        (self.template / ".agents/skills/extra/SKILL.md").write_text(
            "---\nname: extra\ndescription: 新技能。\n---\n", encoding="utf-8"
        )
        (self.template / "AGENTS.md").write_text(TEMPLATE_AGENTS + "\n第四条\n", encoding="utf-8")
        published = self.publish("upstream update")

        local = (target / "AGENTS.md").read_text(encoding="utf-8")
        (target / "AGENTS.md").write_text("# 项目补充\n\n" + local, encoding="utf-8")

        preview = self.upgrade(target, "--dry-run")
        self.assertIn(".agents/skills/extra/SKILL.md", preview)
        self.assertFalse((target / ".agents/skills/extra/SKILL.md").exists())

        self.upgrade(target)
        self.assertTrue((target / ".agents/skills/extra/SKILL.md").is_file())
        self.assertIn("上游新增说明。", (target / ".agents/skills/demo/SKILL.md").read_text())
        merged = (target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# 项目补充", merged)
        self.assertIn("第四条", merged)
        self.assertNotIn("<<<<<<<", merged)
        self.assertEqual(self.manifest(target)["commit"], published)

    def test_upgrade_keeps_local_file_on_conflict(self):
        target = self.install()
        installed = self.manifest(target)["commit"]
        (self.template / "AGENTS.md").write_text(
            TEMPLATE_AGENTS.replace("第二条", "上游改写的第二条"), encoding="utf-8"
        )
        published = self.publish("upstream conflicting change")
        (target / "AGENTS.md").write_text(
            TEMPLATE_AGENTS.replace("第二条", "本地改写的第二条"), encoding="utf-8"
        )

        output = self.upgrade(target, expected=1)
        self.assertIn("冲突", output)
        self.assertIn("本地改写的第二条", (target / "AGENTS.md").read_text())
        conflict = target / f"AGENTS.md.agent-home-{published[:7]}.new"
        self.assertTrue(conflict.is_file())
        self.assertIn("上游改写的第二条", conflict.read_text())
        manifest = self.manifest(target)
        self.assertEqual(manifest["commit"], published)
        self.assertEqual(manifest["files"]["AGENTS.md"]["commit"], installed)

    def test_upgrade_removes_files_dropped_upstream_unless_locally_changed(self):
        target = self.install()
        (self.template / ".agents/skills/demo/SKILL.md").unlink()
        (self.template / ".claude/skills/demo/SKILL.md").unlink()
        self.publish("upstream removal")
        (target / ".claude/skills/demo/SKILL.md").write_text("本地改过的内容\n", encoding="utf-8")

        output = self.upgrade(target)
        self.assertFalse((target / ".agents/skills/demo/SKILL.md").exists())
        self.assertTrue((target / ".claude/skills/demo/SKILL.md").is_file())
        self.assertIn("上游已删除但本地有改动", output)
        self.assertNotIn(".agents/skills/demo/SKILL.md", self.manifest(target)["files"])

    def test_status_reports_local_drift(self):
        target = self.install()
        (target / "AGENTS.md").write_text(TEMPLATE_AGENTS + "\n本地追加。\n", encoding="utf-8")
        output = self.run_installer(
            target / ".agents/scripts/agent_home.py", "status", "--target", str(target)
        )
        self.assertIn("本地已改动：AGENTS.md", output)
        self.assertIn("本地缺失：无", output)


if __name__ == "__main__":
    unittest.main()
