---
name: agent-home-sync
description: 用 agent-home 模板初始化项目结构，或把模板的新版本同步到当前项目。当用户要求用 agent-home 管理这个项目、升级或同步 agent-home 的规则与技能、模板仓有新提交，或需要检查本地对受管理文件的改动时使用。项目自身的业务代码变更不要使用。
---

# 模板安装与同步

`AGENTS.md`、`CLAUDE.md`、`.agents/` 和 `.claude/skills/` 由模板仓管理，通过清单
`.agent-home/manifest.json` 追踪版本；`PROJECT.md`、`tasks/`、`docs/`、`reports/` 和 `.code/` 归项目所有。

## 在空目录安装

1. 确认当前目录不是别的项目，再取得模板仓：

   ```bash
   git clone <模板仓 URL> .agent-home/upstream
   python3 .agent-home/upstream/.agents/scripts/agent_home.py init
   ```

2. `init` 会写入受管理文件、种子 `PROJECT.md`、`.gitignore` 区块和清单，目标不是 Git 仓库时执行
   `git init`。目标已经有同名文件且内容不同时命令会中止，确认可以覆盖后再加 `--force`。
3. 安装后读取 `AGENTS.md`，再用 `bootstrap-project` 完成 `PROJECT.md` 初始化。

## 同步新版本

1. 先看当前版本和本地改动：

   ```bash
   python3 .agents/scripts/agent_home.py status --fetch
   ```

2. 有新提交时先预演，确认影响范围：

   ```bash
   python3 .agents/scripts/agent_home.py upgrade --dry-run
   python3 .agents/scripts/agent_home.py upgrade
   ```

3. 同步器按文件判断：本地没改过的直接更新；本地改过而模板未变的保留；两侧都改的做三方合并。
4. 合并冲突时命令退出码为 1，本地内容保留，新模板版本写在同名 `.agent-home-<commit>.new` 文件里。
   逐个人工合并后删除 `.new` 文件，不要直接用 `.new` 覆盖本地规则。
5. 同步后运行项目自己的测试与检查，确认规则与技能可用，再检查 `git diff` 并提交。

## 边界

- 不修改 `PROJECT.md`、`tasks/`、`docs/`、`reports/` 和 `.code/`，同步不会覆盖项目自己的内容。
- 不把 `.agent-home/upstream/` 提交进项目；清单 `.agent-home/manifest.json` 要提交。
- 不因为同步失败就手工复制模板文件，那会让清单与实际内容脱节。
- 未经用户明确授权不推送、不改写远端、不修改模板仓。
