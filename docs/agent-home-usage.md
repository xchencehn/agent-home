# 用 agent-home 管理项目

本仓既是可以直接克隆的项目骨架，也是一个可以安装进任意项目目录、之后持续同步的模板。这里说明安装、
同步的语义与边界。

## 两种使用方式

| 方式 | 命令 | `origin` | 升级 |
| --- | --- | --- | --- |
| 安装（推荐） | `git clone <URL> .agent-home/upstream` + `agent_home.py init` | 项目自己决定 | `agent_home.py upgrade` |
| 直接克隆 | `git clone <URL> <项目名>` | 指向模板仓 | 手工合并模板历史 |

安装方式下模板不进入项目的 Git 历史，项目历史从第一次提交开始就是项目自己的。

## 安装做了什么

```bash
mkdir my-project && cd my-project
git clone https://github.com/xchencehn/agent-home .agent-home/upstream
python3 .agent-home/upstream/.agents/scripts/agent_home.py init
```

1. 写入受管理文件：`AGENTS.md`、`CLAUDE.md`、`.agents/`、`.claude/skills/`。
2. 缺失时写入种子文件 `PROJECT.md`（带 `agent-home-template:uninitialized` 标记，交给 `bootstrap-project`）。
3. 维护 `.gitignore` 中的 `# agent-home:start` … `# agent-home:end` 区块，忽略 `/.code/` 和
   `/.agent-home/upstream/`。
4. 目标不是 Git 仓库时执行 `git init`（`--no-git` 可跳过）。
5. 写入清单 `.agent-home/manifest.json`：模板来源、分支、commit，以及每个受管理文件的 sha256 与它对应
   的模板 commit。

目标目录已有同名文件且内容与模板不同时，命令会列出这些文件并中止，确认可以覆盖后再加 `--force`。

## 所有权边界

| 归属 | 内容 | 升级行为 |
| --- | --- | --- |
| 模板管理 | `AGENTS.md`、`CLAUDE.md`、`.agents/`、`.claude/skills/` | 按三方合并更新 |
| 一次性种子 | `PROJECT.md` | 只在缺失时写入，之后不再改动 |
| 项目所有 | `tasks/`、`docs/`、`reports/`、`.code/`、`README.md`、测试与源码 | 永不改动 |

`.agent-home/manifest.json` 要提交进项目仓，`.agent-home/upstream/` 是本地缓存，不提交。

## 同步语义

```bash
python3 .agents/scripts/agent_home.py status --fetch
python3 .agents/scripts/agent_home.py upgrade --dry-run
python3 .agents/scripts/agent_home.py upgrade
```

同步器逐文件比较三方状态：清单记录的模板旧版本（base）、本地当前内容（ours）、模板新版本（theirs）。

| 本地 | 模板 | 结果 |
| --- | --- | --- |
| 未修改 | 有更新 | 直接更新 |
| 已修改 | 无更新 | 保留本地 |
| 已修改 | 有更新，可自动合并 | 三方合并写入 |
| 已修改 | 有更新，同处冲突 | 保留本地，新版本写入 `<文件>.agent-home-<commit>.new`，退出码 1 |
| 不存在 | 新增文件 | 写入 |
| 未修改 | 已删除 | 删除 |
| 已修改 | 已删除 | 保留并在报告中列出 |

冲突文件在清单里保留上一次成功同步的 commit，所以人工处理后，下一次同步仍然以那一版为 base 做三方
合并，不会因为一次冲突丢掉后续更新。

同步器自己也是受管理文件。`upgrade` 会先检查模板里的同步器是否更新，若有更新则切换到新版本执行
（`--no-reexec` 可关闭），保证升级逻辑始终跟着模板走。

## 从直接克隆迁移到安装

先确认工作树干净并已提交，便于回滚：

```bash
git status --short
git clone https://github.com/xchencehn/agent-home .agent-home/upstream
python3 .agent-home/upstream/.agents/scripts/agent_home.py init --force
git remote set-url origin <项目自己的远端>   # 或 git remote remove origin
```

`--force` 会用模板版本覆盖受管理文件，提交后可以用 `git diff` 逐条找回本地改动。`PROJECT.md`、`tasks/`
等项目内容不受影响。

## 常见问题

- **改了受管理文件会怎样**：允许改，同步时按三方合并保留。项目专属的稳定规则更适合写进 `PROJECT.md`
  或项目自己的 Skill，减少与模板冲突。
- **想跟踪模板的其它分支**：`upgrade --ref <分支>`，清单会记住该分支。
- **换模板来源**：`upgrade --source <URL>`，同步器会更新缓存仓的 `origin`。
- **离线**：`upgrade` 需要访问模板仓；只想看本地状态用 `status`（不加 `--fetch`）。
- **模板仓自身**：本仓不安装自己，直接在仓内开发，用 `python -m unittest discover -s tests -v` 验证。
