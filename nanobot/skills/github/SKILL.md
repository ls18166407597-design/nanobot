---
name: github
description: "使用 `gh` CLI 与 GitHub 交互。支持管理 Issue、Pull Request、运行 Workflow 以及调用 GitHub API。"
metadata: {"nanobot":{"emoji":"🐙","requires":{"bins":["gh"]},"install":[{"id":"brew","kind":"brew","formula":"gh","bins":["gh"],"label":"安装 GitHub CLI (brew)"},{"id":"apt","kind":"apt","package":"gh","bins":["gh"],"label":"安装 GitHub CLI (apt)"}]}}
---

# GitHub 技能

使用 `gh` CLI 与 GitHub 交互。当不在 git 目录中时，请始终指定 `--repo owner/repo`，或者直接使用 URL。

## Pull Requests

查看 PR 的 CI 状态：
```bash
gh pr checks 55 --repo owner/repo
```

列出最近的工作流运行（Workflow runs）：
```bash
gh run list --repo owner/repo --limit 10
```

查看运行详情并确定失败的步骤：
```bash
gh run view <run-id> --repo owner/repo
```

仅查看失败步骤的日志：
```bash
gh run view <run-id> --repo owner/repo --log-failed
```

## 使用 API 进行高级查询

`gh api` 命令用于访问其他子命令无法获取的数据。

获取具有特定字段的 PR 详情：
```bash
gh api repos/owner/repo/pulls/55 --jq '.title, .state, .user.login'
```

## JSON 输出

大多数命令都支持 `--json` 以获取结构化输出。你可以使用 `--jq` 进行过滤：

```bash
gh issue list --repo owner/repo --json number,title --jq '.[] | "\(.number): \(.title)"'
```
