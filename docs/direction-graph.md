# 方向图：在依赖图上选择下一步

“方向图”是本仓的自定义名称，对应的标准概念是**有向无环图（DAG）**上的**最佳优先搜索**：图节点是候选
方向与它们的功能构成，`requires` 边是**前置依赖**，每次决策在**就绪集合（frontier）**上按评分选一个节点
展开，观察结果后更新图再重算——即**在线搜索**，而不是一次成型的计划。

## 解决什么问题

早期的 `next-action` 把候选保存成一张扁平列表，有三个结构性缺陷：

1. **依赖不可见**：无法表达“做 B 之前必须先确认 A”，容易在前置未定时就动手实施。
2. **构成不可见**：一个方向由哪些功能单元组成、缺哪一块，没有位置记录。
3. **放弃即遗忘**：被排除的方向从列表里消失，当时的排除理由和后来出现的新证据再也对不上。

图模型把这三件事变成可以机械检查的结构：拓扑约束挡住越级实施，`part-of` 边记录功能构成，被放弃的
节点留在图上并强制携带复活条件。

## 节点与边

节点保存在 `tasks/<task>/graph.json`：

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
`conflicts`（互斥）、`supersedes`（取代）。`{"from": "A", "to": "B", "kind": "requires"}` 读作“A 依赖 B”，
只有 B 变成 `confirmed`，A 才进入就绪集合。`requires` 边必须无环，`check` 会做深度优先检测。

## 与 Task / Loop / Run 的关系

| 层 | 职责 |
| --- | --- |
| 方向图 | 候选空间：有哪些方向、彼此什么依赖、各自处于什么状态 |
| Loop | 承载一个 `direction` 节点，把它推进到 `confirmed` 或 `falsified` |
| Run | 承载一次有边界的执行，通常对应一个 `component` 节点 |

图管**规划**，Loop 和 Run 管**执行**。执行侧仍然是单活动：一个 Task 同时只有一个活动 Loop，一个 Loop
同时只有一个活动 Run。图上可以同时存在多个就绪节点，但每次只选一个展开——并行的是候选，不是执行。

`open-loop --node <节点>` 会先校验前置全部 `confirmed`，再把节点标成 `active` 并记录承载关系；
`close-loop` 按判定把节点写回 `confirmed`、`falsified`、`blocked` 或 `abandoned`。

## 决策循环

```bash
python .agents/skills/task-loop-run/scripts/workflow.py frontier tasks/<task>
```

输出分六组：推进中、就绪、等待前置、外部阻塞、需要重新评估、已定论。选择规则：

1. 只在**就绪**组里选。等待前置的节点会显示缺哪些前置，先推进前置或修改依赖关系。
2. 排序参考解锁的后继数量（`解锁 N`）、对目标的关键性、信息增益、代价和可逆性。
3. 选中后绑定节点：`set-next-action --node <节点>`。图非空时 `probe`、`execute`、`decide`、`verify`
   必须绑定节点，或用 `--off-graph` 说明为什么这一步在图外。
4. 观察结果 → `set-node` 更新状态与证据 → 重算前沿。新发现随时 `add-node` / `link` / `unlink`。

`frontier --format mermaid` 输出可视化图，`--format json` 供程序消费。

## 放弃不等于遗忘

转为 `deferred` 或 `abandoned` 时必须提供 `--revisit-when`，命令会拒绝没有复活条件的放弃：

```bash
python .agents/skills/task-loop-run/scripts/workflow.py set-node tasks/<task> N002 \
  --status abandoned \
  --reason "自研代价远高于复用，且不解决当前瓶颈" \
  --revisit-when "出现现成的可复用前端，或复用路线在动态 shape 上被证伪" \
  --why "首轮调研显示复用路线足够"
```

这些节点不会从图上消失。每次 `frontier` 都会把它们连同复活条件与当时的理由列在“需要重新评估”组，
决策时必须逐条对照最新证据判断当时的理由是否仍然成立。发现机会时用
`set-node --status open --evidence-ref <新证据>` 让它重新进入候选。

机制上的要点是：**放弃条件必须写成可对照的事实，而不是感受**。写不出复活条件，说明这个方向要么其实
没被真正评估过，要么应该用 `superseded` 记录它被谁取代。

## 图的演化与审计

`add-node`、`link`、`unlink`、`set-node`、`open-loop`、`close-loop` 都要求 `--why`（生命周期命令用目标或
结论代替），每次改动追加一行到 `tasks/<task>/graph-events.jsonl`。恢复或交接时回放这个文件，可以看到
判断是怎么随证据变化的，而不是只看到最终形态。

## 校验

`workflow.py check` 对图执行：节点 ID 唯一、类型与状态取值合法、边两端存在且不自环、`requires` 无环、
`deferred` 与 `abandoned` 必须有复活条件、`active` 节点必须有承载它的 Loop 或 Run。

## 边界

- 工具只做机械部分：拓扑约束、就绪计算、解锁计数、复活项的强制展示。**排序与取舍由模型和人判断**，
  不做自动打分或自动规划。
- 不引入并行执行。图上多个节点同时就绪，仍然只选一个展开。
- 不自动增删节点。图的每次变化都要有理由并留下审计。
- 没有 Task 的一次性请求不需要建图；图只在长期、多方向的 Task 里有价值。
