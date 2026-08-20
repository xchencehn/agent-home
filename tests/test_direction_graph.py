import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".agents/skills/task-loop-run/scripts/workflow.py"


class DirectionGraphTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.task = self.run_workflow(
            "open-task", "compiler", "--title", "图编译", "--objective", "找到可落地的原型方向"
        )

    def run_workflow(self, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(WORKFLOW), "--root", str(self.root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout.strip()

    def add_node(self, title, *arguments):
        return self.run_workflow(
            "add-node", self.task, "--title", title, "--why", "测试", *arguments
        )

    def frontier(self):
        return json.loads(self.run_workflow("frontier", self.task, "--format", "json"))["groups"]

    def graph(self):
        return json.loads((self.root / self.task / "graph.json").read_text(encoding="utf-8"))

    def node(self, node_id):
        return {item["id"]: item for item in self.graph()["nodes"]}[node_id]

    def test_open_task_creates_an_empty_graph(self):
        graph = self.graph()
        self.assertEqual(graph["kind"], "direction_graph")
        self.assertEqual(graph["task_id"], Path(self.task).name)
        self.assertEqual(graph["nodes"], [])
        self.assertTrue((self.root / self.task / "graph-events.jsonl").is_file())

    def test_requires_edges_gate_the_ready_set(self):
        probe = self.add_node("IR 探针", "--kind", "component")
        rules = self.add_node("融合规则", "--kind", "component", "--requires", probe)
        partition = self.add_node("子图划分", "--kind", "component", "--requires", rules)
        groups = self.frontier()
        self.assertEqual([item["id"] for item in groups["ready"]], [probe])
        waiting = {item["id"]: item["missing"] for item in groups["waiting"]}
        self.assertEqual(waiting[rules], [probe])
        self.assertEqual(waiting[partition], [rules])
        self.assertEqual(groups["ready"][0]["unlocks"], 1)

        self.run_workflow(
            "set-next-action", self.task, "--node", partition, "--kind", "probe",
            "--action", "先做划分", "--target", "划分", "--done-when", "有结果",
            "--why-now", "越级", "--source-ref", "PROJECT.md", expected=2,
        )
        self.run_workflow(
            "set-next-action", self.task, "--node", probe, "--kind", "probe",
            "--action", "捕获前后 IR", "--target", "IR", "--done-when", "两份 IR 可比较",
            "--why-now", "解锁数最高", "--source-ref", "PROJECT.md",
        )
        record = json.loads((self.root / self.task / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(record["navigation"]["candidates"][-1]["node_id"], probe)

    def test_graph_bound_actions_require_a_node(self):
        self.add_node("某个方向")
        self.run_workflow(
            "set-next-action", self.task, "--kind", "probe", "--action", "随便试",
            "--target", "未知", "--done-when", "有结果", "--why-now", "没有绑定节点",
            "--source-ref", "PROJECT.md", expected=2,
        )
        self.run_workflow(
            "set-next-action", self.task, "--kind", "probe", "--action", "读取环境信息",
            "--target", "环境", "--done-when", "确认工具链版本", "--why-now", "属于图外的准备工作",
            "--source-ref", "PROJECT.md", "--off-graph", "环境确认不属于任何候选方向",
        )

    def test_loop_lifecycle_drives_node_status(self):
        probe = self.add_node("IR 探针", "--kind", "component")
        fusion = self.add_node("融合闭环", "--kind", "direction", "--requires", probe)
        self.run_workflow(
            "open-loop", self.task, "fusion", "--node", fusion, "--goal", "闭环",
            "--hypothesis", "融合有收益", "--acceptance", "端到端收益", "--falsification", "无收益",
            expected=2,
        )
        loop = self.run_workflow(
            "open-loop", self.task, "probe", "--node", probe, "--goal", "拿到前后 IR",
            "--hypothesis", "工具链能导出", "--acceptance", "两份 IR", "--falsification", "无法导出",
        )
        self.assertEqual(self.node(probe)["status"], "active")
        self.assertEqual(self.node(probe)["realized_as"], f"loops/{Path(loop).name}")

        run = self.run_workflow(
            "open-run", loop, "capture", "--objective", "导出 IR", "--acceptance", "文件存在"
        )
        self.run_workflow(
            "checkpoint", run, "--kind", "validation", "--summary", "已导出",
            "--result", "两份 IR 可比较", "--evidence-ref", "artifacts/before.mlir",
            "--limitation", "只覆盖一个用例",
        )
        self.run_workflow("close-run", run, "--verdict", "passed", "--summary", "探针可用")
        self.run_workflow("close-loop", loop, "--verdict", "confirmed", "--summary", "可以导出")
        self.assertEqual(self.node(probe)["status"], "confirmed")
        self.assertEqual([item["id"] for item in self.frontier()["ready"]], [fusion])

    def test_abandoned_node_needs_a_revisit_condition_and_stays_listed(self):
        frontend = self.add_node("自研完整前端", "--kind", "direction")
        self.run_workflow(
            "set-node", self.task, frontend, "--status", "abandoned", "--why", "代价过高", expected=2
        )
        self.run_workflow(
            "set-node", self.task, frontend, "--status", "abandoned",
            "--reason", "自研代价远高于复用", "--revisit-when", "复用路线在动态 shape 上被证伪",
            "--why", "首轮调研显示复用足够",
        )
        groups = self.frontier()
        self.assertEqual([item["id"] for item in groups["review"]], [frontend])
        self.assertEqual(groups["review"][0]["revisit_when"], "复用路线在动态 shape 上被证伪")
        self.assertNotIn(frontend, [item["id"] for item in groups["ready"]])
        text = self.run_workflow("frontier", self.task)
        self.assertIn("需要重新评估", text)
        self.assertIn("复活条件：复用路线在动态 shape 上被证伪", text)

        self.run_workflow(
            "set-node", self.task, frontend, "--status", "open",
            "--evidence-ref", "reports/frontend-survey.md",
            "--why", "复用路线在动态 shape 上出现硬伤",
        )
        self.assertEqual([item["id"] for item in self.frontier()["ready"]], [frontend])
        self.assertIn("reports/frontend-survey.md", self.node(frontend)["evidence_refs"])

    def test_new_dependency_moves_a_ready_node_back_to_waiting(self):
        rules = self.add_node("融合规则", "--kind", "component")
        guard = self.add_node("guard 语义", "--kind", "question")
        self.assertEqual({item["id"] for item in self.frontier()["ready"]}, {rules, guard})
        self.run_workflow(
            "link", self.task, "--from", rules, "--to", guard, "--kind", "requires",
            "--why", "实验发现融合规则依赖 guard 语义",
        )
        groups = self.frontier()
        self.assertEqual([item["id"] for item in groups["ready"]], [guard])
        self.assertEqual([item["id"] for item in groups["waiting"]], [rules])
        self.run_workflow(
            "unlink", self.task, "--from", rules, "--to", guard, "--why", "依赖判断有误"
        )
        self.assertEqual({item["id"] for item in self.frontier()["ready"]}, {rules, guard})

    def test_requires_cycle_is_rejected(self):
        first = self.add_node("A", "--kind", "component")
        second = self.add_node("B", "--kind", "component", "--requires", first)
        self.run_workflow(
            "link", self.task, "--from", first, "--to", second, "--kind", "requires",
            "--why", "制造环", expected=2,
        )
        self.assertEqual(len(self.graph()["edges"]), 1)

    def test_check_rejects_broken_graphs(self):
        node = self.add_node("方向", "--kind", "direction")
        path = self.root / self.task / "graph.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        broken = json.loads(json.dumps(original))
        broken["nodes"][0]["status"] = "unknown"
        path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        self.run_workflow("check", expected=2)

        broken = json.loads(json.dumps(original))
        broken["nodes"][0]["status"] = "abandoned"
        path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        self.run_workflow("check", expected=2)

        broken = json.loads(json.dumps(original))
        broken["edges"] = [{"from": node, "to": "N999", "kind": "requires", "note": None}]
        path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        self.run_workflow("check", expected=2)

        path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.run_workflow("check"), "通过")

    def test_mermaid_rendering_orders_prerequisites_first(self):
        probe = self.add_node("IR 探针", "--kind", "component")
        fusion = self.add_node("融合闭环", "--kind", "direction", "--requires", probe)
        diagram = self.run_workflow("frontier", self.task, "--format", "mermaid")
        self.assertIn("graph TD", diagram)
        self.assertIn(f"{probe} --> {fusion}", diagram)
        self.assertIn(f'{probe}["{probe} IR 探针<br/>open"]:::ready', diagram)

    def test_graph_events_record_every_change(self):
        node = self.add_node("方向", "--kind", "direction")
        self.run_workflow(
            "set-node", self.task, node, "--status", "confirmed", "--evidence-ref", "tests/",
            "--why", "实验通过",
        )
        events = [
            json.loads(line)
            for line in (self.root / self.task / "graph-events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual([item["event"] for item in events], ["add_node", "set_node"])
        self.assertEqual(events[1]["detail"]["changes"]["status"], ["open", "confirmed"])
        self.assertEqual(events[1]["why"], "实验通过")


if __name__ == "__main__":
    unittest.main()
