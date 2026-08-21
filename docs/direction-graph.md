# 方向图：记录格式与图上游走

“方向图”是本仓的自定义名称，对应的标准概念是**有向无环图（DAG）**上的**最佳优先搜索**：节点是候选
方向与它们的功能构成，`requires` 边是**前置依赖**，每次决策在**就绪集合**上按评分选一个节点展开，
观察结果后更新图再重算——即**在线搜索**，而不是一次成型的计划。

图是一份记录格式加一套游走方法，由 Agent 直接编辑 `tasks/<task>/graph.json`。`workflow.py` 只做两件
机械的事：**前置门禁**与**结构校验**。分组、排序、取舍都由 Agent 判断。

## 解决什么问题

早期把候选保存成一张扁平列表，有三个结构性缺陷：

1. **依赖不可见**：无法表达“做 B 之前必须先确认 A”，容易在前置未定时就动手实施。
2. **构成不可见**：一个方向由哪些功能单元组成、缺哪一块，没有位置记录。
3. **放弃即遗忘**：被排除的方向从列表里消失，当时的排除理由和后来出现的新证据再也对不上。

## 记录格式

`open-task` 会创建空图，之后直接编辑它：

```json
{
  "schema_version": 1,
  "kind": "direction_graph",
  "task_id": "001_compiler",
  "created_at": "2026-08-20T10:13:00+00:00",
  "updated_at": "2026-08-20T11:02:00+00:00",
  "nodes": [
    {
      "id": "N001",
      "kind": "component",
      "title": "捕获前后 IR 的最小探针",
      "status": "confirmed",
      "hypothesis": null,
      "value": "所有方向都要读 IR",
      "cost": "小",
      "evidence_refs": ["tasks/001_compiler/loops/001_probe/runs/001_capture/result.json"],
      "reason": "工具链可以导出前后 IR",
      "revisit_when": null,
      "realized_as": "loops/001_probe",
      "created_at": "2026-08-20T10:13:00+00:00",
      "updated_at": "2026-08-20T10:41:00+00:00"
    },
    {
      "id": "N002",
      "kind": "direction",
      "title": "动态 shape 感知的融合与划分闭环",
      "status": "open",
      "hypothesis": "在动态 shape 下融合加划分能带来端到端收益",
      "value": "直接对准目标",
      "cost": "中",
      "evidence_refs": [],
      "reason": null,
      "revisit_when": null,
      "realized_as": null,
      "created_at": "2026-08-20T10:13:00+00:00",
      "updated_at": "2026-08-20T10:13:00+00:00"
    },
    {
      "id": "N003",
      "kind": "direction",
      "title": "自研完整前端",
      "status": "abandoned",
      "hypothesis": "自研前端比复用更可控",
      "value": "长期可控",
      "cost": "高",
      "evidence_refs": ["reports/frontend-survey.md"],
      "reason": "自研代价远高于复用，且不解决当前瓶颈",
      "revisit_when": "出现现成的可复用前端，或复用路线在动态 shape 上被证伪",
      "realized_as": null,
      "created_at": "2026-08-20T10:13:00+00:00",
      "updated_at": "2026-08-20T10:52:00+00:00"
    }
  ],
  "edges": [{ "from": "N002", "to": "N001", "kind": "requires", "note": null }]
}
```

节点字段：

| 字段 | 含义 |
| --- | --- |
| `kind` | `direction`（可证伪方向）、`component`（功能构成）、`question`（未知问题） |
| `status` | `open`、`active`、`confirmed`、`falsified`、`blocked`、`deferred`、`abandoned`、`superseded` |
| `hypothesis` | 方向节点的可证伪假设 |
| `value` / `cost` | 为什么值得做、粗估代价 |
| `evidence_refs` | 支撑当前状态的证据指针 |
| `reason` | 当前状态的理由 |
| `revisit_when` | 什么新事实会让暂缓或放弃的节点重新值得考虑 |
| `realized_as` | 承载它的 Loop 或 Run |

边有五种：`requires`（前置依赖，构成拓扑约束）、`part-of`（功能构成）、`informs`（证据相关但不阻塞）、
`conflicts`（互斥）、`supersedes`（取代）。`{"from": "N002", "to": "N001", "kind": "requires"}` 读作
“N002 依赖 N001”，只有 N001 变成 `confirmed`，N002 才进入就绪集合。

## 图上游走

每次决策前把节点分成六组，只在**就绪**组里选：

| 组 | 判定 |
| --- | --- |
| 推进中 | `active` |
| 就绪 | `open` 且所有 `requires` 前置都是 `confirmed` |
| 等待前置 | `open` 但仍有前置未 `confirmed` |
| 外部阻塞 | `blocked` |
| 需要重新评估 | `deferred`、`abandoned` |
| 已定论 | `confirmed`、`falsified`、`superseded` |

排序参考解锁的后继数量、对目标的关键性、信息增益、代价和可逆性。选中后用
`set-next-action --node <节点>` 绑定；观察结果后更新节点状态与证据，再重算。新发现随时加节点、加边，
依赖判断有误就删边。

## 与 Task / Loop / Run 的关系

| 层 | 职责 |
| --- | --- |
| 方向图 | 候选空间：有哪些方向、彼此什么依赖、各自处于什么状态 |
| Loop | 承载一个 `direction` 节点，把它推进到 `confirmed` 或 `falsified` |
| Run | 承载一次有边界的执行，通常对应一个 `component` 节点 |

图管**规划**，Loop 和 Run 管**执行**。图上可以同时有多个就绪节点，但每次只选一个展开——并行的是
候选，不是执行。

## 工具只做两件事

**前置门禁**（实时拒绝）：

```bash
$ workflow.py set-next-action tasks/001_compiler --node N002 --kind probe ...
错误：节点 N002 不在就绪集合里（状态 open）：先满足它的前置，或先复核它的状态
```

`open-loop --node` 同样校验前置，并把节点标成 `active` 记录承载关系；`close-loop` 按判定写回节点状态，
判定为 `abandoned` 时要求 `--revisit-when`。图非空时 `probe`、`execute`、`decide`、`verify` 必须绑定
节点或用 `--off-graph` 说明理由。

**结构校验**（`workflow.py check`）：节点 ID 唯一、类型与状态取值合法、边两端存在且不自环、`requires`
无环、`deferred` 与 `abandoned` 必须有 `revisit_when`、`active` 节点必须有承载它的 Loop 或 Run。

其余都不做：不渲染视图、不分配 ID、不自动增删节点、不打分排序、不写变更日志。这些要么是 Agent 自己
该完成的判断，要么是没有价值的仪式。

## 放弃不等于遗忘

`deferred` 与 `abandoned` 的节点留在图上，并且必须带 `revisit_when`。每次重算都要把这一组连同复活
条件与当时的理由逐条对照最新证据：当时的放弃理由是否仍然成立？发现机会时把状态改回 `open` 并补上
新的 `evidence_refs`。

要点是：**放弃条件必须写成可对照的事实，而不是感受**。写不出复活条件，说明这个方向要么其实没被真正
评估过，要么应该用 `superseded` 记录它被谁取代。

## 边界

- 没有 Task 的一次性请求不需要建图；图只在长期、多方向的 Task 里有价值。
- 图不是待办清单。节点是候选方向与构成，不是工序步骤。
- 不引入并行执行。图上多个节点同时就绪，仍然只选一个展开。
