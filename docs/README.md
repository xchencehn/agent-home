# 文档

这里保存面向使用者的设计、架构和操作说明。只有内容比源码与测试更适合解释问题时才新增文档。

- [用 agent-home 管理项目](agent-home-usage.md)：安装到项目目录、受管理文件与项目内容的边界、
  一句话同步模板新版本的语义与冲突处理。
- [方向图：在依赖图上选择下一步](direction-graph.md)：候选方向的有向无环图模型、就绪集合计算、
  与 Loop/Run 的分工，以及放弃方向的复活机制。
- [代码仓与并行工作区](code-workspace.md)：`.code/` 的所有权边界、一个 Task 一个分支、并行 Task 的
  Git 工作树隔离，以及完成后如何合入。
- [Agent Home：项目自有的持久工作环境](home-engineering.md)：简洁说明 Agent Home 的核心定义、
  Model/Harness/Home 边界、七类项目能力，以及当前仓库与 Task/Loop/Run 等参考机制的关系。
