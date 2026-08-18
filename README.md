# Agent Home Template

一个不需要安装插件的本地项目模板。仓库本身就是 Agent Home：项目规则、项目说明和可复用 Skill 都随
Git 一起分发。

## 开始使用

```bash
git clone <template-url> agent-home-template
mv agent-home-template my-project
cd my-project
codex
# 或
claude
```

也可以在 clone 时直接指定新目录名：

```bash
git clone <template-url> my-project
cd my-project
codex
```

启动后直接描述要做的项目。首次会话会把目录名作为项目名候选，并根据你的目标初始化 `PROJECT.md`。
不需要 marketplace、插件缓存、安装脚本或额外 Python 依赖。

例如：

```text
把这里初始化成一个用于分析编译日志的项目，然后实现第一个日志解析器。
```

<!-- project-summary:start -->
## 当前项目

这是尚未初始化的模板。项目身份与目标见 `PROJECT.md`。
<!-- project-summary:end -->

## 仓库结构

- `AGENTS.md`：Codex 与其他兼容 Agent 的根规则。
- `CLAUDE.md`：Claude Code 入口，导入同一份 `AGENTS.md`。
- `PROJECT.md`：项目身份、目标、范围与常用命令。
- `.agents/skills/`：Codex 使用的仓库级 Skills，也是 Skill 工作流的唯一源码。
- `.claude/skills/`：Claude Code 的薄发现 wrapper，只转读 `.agents/skills/`，不复制工作流。
- `docs/`：面向使用者的设计和说明。
- `reports/`：需要长期保留、且有证据支持的工程结论。
- `tests/`：机器可复验的项目判据。

## Git 边界

普通 clone 会保留模板仓库为 `origin`。首次初始化不会擅自删除或改写 remote，也不会自动 push；准备把
项目发布到新仓库时，再明确要求 Agent 配置目标 remote。
