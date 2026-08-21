import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".agents/skills/task-loop-run/scripts/workflow.py"


class DirectionGraphTest(unittest.TestCase):
    """方向图由 Agent 直接编辑 graph.json；工具只负责前置门禁与结构校验。"""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.task = self.run_workflow(
            "open-task", "compiler", "--title", "图编译", "--objective", "找到可落地的原型方向"
        )
        self.graph_path = self.root / self.task / "graph.json"

    def run_workflow(self, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(WORKFLOW), "--root", str(self.root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout.strip()

    def write_graph(self, nodes, edges=()):
        graph = json.loads(self.graph_path.read_text(encoding="utf-8"))
        graph["nodes"] = [
            {
                "id": node["id"],
                "kind": node.get("kind", "component"),
                "title": node.get("title", node["id"]),
                "status": node.get("status", "open"),
                "hypothesis": node.get("hypothesis"),
                "value": node.get("value"),
                "cost": node.get("cost"),
                "evidence_refs": node.get("evidence_refs", []),
                "reason": node.get("reason"),
                "revisit_when": node.get("revisit_when"),
                "realized_as": node.get("realized_as"),
                "created_at": graph["created_at"],
                "updated_at": graph["created_at"],
            }
            for node in nodes
        ]
        graph["edges"] = [
            {"from": source, "to": target, "kind": kind, "note": None}
            for source, target, kind in edges
        ]
        self.graph_path.write_text(
            json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def node(self, node_id):
        graph = json.loads(self.graph_path.read_text(encoding="utf-8"))
        return {item["id"]: item for item in graph["nodes"]}[node_id]

    def select(self, *arguments, expected=0):
        return self.run_workflow(
            "set-next-action", self.task, "--kind", "probe", "--action", "试一步",
            "--target", "目标", "--done-when", "有结果", "--why-now", "测试",
            "--source-ref", "PROJECT.md", *arguments, expected=expected,
        )

    def test_open_task_creates_an_empty_graph_and_no_event_log(self):
        graph = json.loads(self.graph_path.read_text(encoding="utf-8"))
        self.assertEqual(graph["kind"], "direction_graph")
        self.assertEqual(graph["task_id"], Path(self.task).name)
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["edges"], [])
        self.assertFalse((self.root / self.task / "graph-events.jsonl").exists())

    def test_requires_edges_gate_the_next_action(self):
        self.write_graph(
            [{"id": "N001", "title": "IR 探针"}, {"id": "N002", "title": "融合规则"}],
            [("N002", "N001", "requires")],
        )
        self.select("--node", "N002", expected=2)
        self.select("--node", "N001")
        record = json.loads((self.root / self.task / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(record["navigation"]["candidates"][-1]["node_id"], "N001")

        self.write_graph(
            [
                {"id": "N001", "title": "IR 探针", "status": "confirmed"},
                {"id": "N002", "title": "融合规则"},
            ],
            [("N002", "N001", "requires")],
        )
        self.select("--node", "N002")

    def test_unknown_and_settled_nodes_cannot_be_selected(self):
        self.write_graph([{"id": "N001", "title": "已经证伪的方向", "status": "falsified"}])
        self.select("--node", "N404", expected=2)
        self.select("--node", "N001", expected=2)

    def test_graph_bound_actions_require_a_node_or_an_explicit_reason(self):
        self.write_graph([{"id": "N001", "title": "某个方向"}])
        self.select(expected=2)
        self.select("--off-graph", "环境确认不属于任何候选方向")

    def test_open_loop_checks_prerequisites_and_marks_the_node_active(self):
        self.write_graph(
            [
                {"id": "N001", "title": "IR 探针"},
                {"id": "N002", "title": "融合闭环", "kind": "direction"},
            ],
            [("N002", "N001", "requires")],
        )
        self.run_workflow(
            "open-loop", self.task, "fusion", "--node", "N002", "--goal", "闭环",
            "--hypothesis", "融合有收益", "--acceptance", "端到端收益", "--falsification", "无收益",
            expected=2,
        )
        loop = self.run_workflow(
            "open-loop", self.task, "probe", "--node", "N001", "--goal", "拿到前后 IR",
            "--hypothesis", "工具链能导出", "--acceptance", "两份 IR", "--falsification", "无法导出",
        )
        self.assertEqual(self.node("N001")["status"], "active")
        self.assertEqual(self.node("N001")["realized_as"], f"loops/{Path(loop).name}")
        return loop

    def test_close_loop_writes_the_verdict_back_to_the_node(self):
        loop = self.test_open_loop_checks_prerequisites_and_marks_the_node_active()
        self.run_workflow("close-loop", loop, "--verdict", "confirmed", "--summary", "可以导出")
        self.assertEqual(self.node("N001")["status"], "confirmed")
        self.select("--node", "N002")

    def test_close_loop_refuses_to_abandon_without_a_revisit_condition(self):
        loop = self.test_open_loop_checks_prerequisites_and_marks_the_node_active()
        self.run_workflow(
            "close-loop", loop, "--verdict", "abandoned", "--summary", "代价过高", expected=2
        )
        self.run_workflow(
            "close-loop", loop, "--verdict", "abandoned", "--summary", "代价过高",
            "--revisit-when", "出现现成的导出工具",
        )
        node = self.node("N001")
        self.assertEqual(node["status"], "abandoned")
        self.assertEqual(node["revisit_when"], "出现现成的导出工具")

    def test_check_requires_a_revisit_condition_on_abandoned_nodes(self):
        self.write_graph([{"id": "N001", "title": "自研完整前端", "status": "abandoned"}])
        self.run_workflow("check", expected=2)
        self.write_graph(
            [
                {
                    "id": "N001",
                    "title": "自研完整前端",
                    "status": "abandoned",
                    "reason": "代价远高于复用",
                    "revisit_when": "复用路线在动态 shape 上被证伪",
                }
            ]
        )
        self.assertEqual(self.run_workflow("check"), "通过")

    def test_check_rejects_cycles_dangling_edges_and_bad_values(self):
        self.write_graph(
            [{"id": "N001", "title": "A"}, {"id": "N002", "title": "B"}],
            [("N001", "N002", "requires"), ("N002", "N001", "requires")],
        )
        self.run_workflow("check", expected=2)

        self.write_graph([{"id": "N001", "title": "A"}], [("N001", "N404", "requires")])
        self.run_workflow("check", expected=2)

        self.write_graph([{"id": "N001", "title": "A", "status": "unknown"}])
        self.run_workflow("check", expected=2)

        self.write_graph([{"id": "N001", "title": "A"}, {"id": "N001", "title": "重复"}])
        self.run_workflow("check", expected=2)

        self.write_graph([{"id": "N001", "title": "A", "status": "active"}])
        self.run_workflow("check", expected=2)

    def test_check_accepts_a_graph_that_records_a_settled_direction(self):
        self.write_graph(
            [
                {"id": "N001", "title": "IR 探针", "status": "confirmed"},
                {"id": "N002", "title": "融合闭环", "kind": "direction"},
                {
                    "id": "N003",
                    "title": "自研前端",
                    "kind": "direction",
                    "status": "deferred",
                    "revisit_when": "复用路线被证伪",
                },
                {"id": "N004", "title": "guard 语义", "kind": "question"},
            ],
            [("N002", "N001", "requires"), ("N002", "N004", "informs")],
        )
        self.assertEqual(self.run_workflow("check"), "通过")


if __name__ == "__main__":
    unittest.main()
