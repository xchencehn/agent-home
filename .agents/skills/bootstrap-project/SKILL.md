---
name: bootstrap-project
description: 把刚克隆或改名的 Agent Home 仓库模板初始化成具体项目。当 `PROJECT.md` 仍含 `agent-home-template:uninitialized`、用户要求初始化或改造模板，或全新克隆尚未开始第一次实质修改时使用。标记删除后处理日常工作时不要使用。
---

# 初始化项目

无需安装程序或单独的引导命令，直接把新模板变成用户的项目。

## 工作流程

1. 确定 Git 根目录，读取 `AGENTS.md`、`PROJECT.md`、`README.md`（若有），并检查
   `git status --short --branch` 与 `git remote -v`。存在 `.agent-home/manifest.json` 时是安装式项目：
   `origin` 属于项目自己，模板版本由清单追踪，不要把 `origin` 当成模板仓。
2. 使用根目录名称作为项目名称候选，不要自行修改目录名。
3. 从用户请求中提取目标和初始范围。若请求没有提供目标，只问一个必要问题；得到回答前暂停初始化。
4. 在 `PROJECT.md` 中写入项目名称、目标、当前范围、非目标、已发现的验证命令和稳定约束，并删除
   `agent-home-template:uninitialized` 标记。
5. 已有 `README.md` 且含 `project-summary:start` 与 `project-summary:end` 标记时，只替换这两个标记
   之间的内容，写入项目名称、用途和最短启动命令，并保留可复用的 Agent 工作空间说明；安装式项目还
   没有 `README.md` 时，只在用户需要时新建一份简短的项目 README。
6. 只有已经明确且始终适用的项目规则才写入 `AGENTS.md`。条件性工作流应写成新的仓库级 Skill，不要
   持续扩大根规则。
7. 以 `.agents/skills/` 作为工作流唯一真值。`.claude/skills/bootstrap-project/SKILL.md` 只作为
   Claude Code 的发现包装层，指向本文件，不复制工作流。
8. 用户已经指明目标代码仓时，用 `add-repo` 把它放进 `.code/`，不要复制源码进本仓，也不要在本仓
   提交代码仓的文件。目标代码仓尚未确定时不要创建 `.code/`。
9. 运行 `python -m unittest discover -s tests -v`，再运行初始化过程中发现的项目原生检查。
10. 若同一请求开始了长期或多阶段目标，初始化完成后转入 `task-loop-run`。
11. 报告初始化后的项目身份、剩余未知项、验证结果和当前远端归属。

## 边界

- 不要仅因模板完成初始化就创建 Task、Loop 或 Run。只有实质请求需要持久恢复、假设验证或多次有边界
  的执行时才使用 `task-loop-run`。
- 不创建会话日志、插件清单、marketplace 条目、安装缓存、生成状态视图或强制治理记录。
- 未经用户明确授权，不删除或改写 Git 历史，不删除或替换远端，不创建外部仓库，不 push 或发布。
- 不臆造构建或测试命令。仓库没有提供证据前，把未知命令明确记为未知。
- 不把机器专属路径、凭据、个人设置或模板的历史实现复制进新项目。
