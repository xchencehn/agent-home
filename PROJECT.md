<!-- agent-home-template:uninitialized -->
# 项目说明

- 名称：未初始化（首次启动时使用当前目录名作为候选）
- 目标：由首次项目请求确定
- 当前范围：包含零安装项目骨架，以及 Task/Loop/Run、Grill、next_action 和 evidence checkpoint 工作协议
- 非目标：不提供插件安装、marketplace、全局缓存、外部服务或强制治理流程
- 常用命令：`python -m unittest discover -s tests -v`
- 约束：首次初始化不修改 Git remote、不 push、不创建外部资源

初始化后删除顶部的 `agent-home-template:uninitialized` 标记，并把本页改成项目当前、稳定的说明。
