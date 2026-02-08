---
name: github
description: "使用 `gh` CLI 与 GitHub 交互。支持管理 Issue、Pull Request、运行 Workflow 以及调用 GitHub API。"
metadata:
  {
    "openclaw":
      {
        "emoji": "🐙",
        "requires": { "bins": ["gh"] },
        "install":
          [
            {
              "id": "brew",
              "kind": "brew",
              "formula": "gh",
              "bins": ["gh"],
              "label": "Install GitHub CLI (brew)",
            },
            {
              "id": "apt",
              "kind": "apt",
              "package": "gh",
              "bins": ["gh"],
              "label": "Install GitHub CLI (apt)",
            },
          ],
      },
  }
---

# GitHub 技能

使用 `gh` CLI 与 GitHub 交互。在非 git 目录中时请务必指定 `--repo owner/repo`，或者直接使用 URL。

## Pull Request

检查 PR 的 CI 状态：

```bash
gh pr checks 55 --repo owner/repo
```

列出最近的工作流运行 (workflow runs)：

```bash
gh run list --repo owner/repo --limit 10
```

查看某次运行并查看失败的步骤：

```bash
gh run view <run-id> --repo owner/repo
```

仅查看失败步骤的日志：

```bash
gh run view <run-id> --repo owner/repo --log-failed
```

## 用于高级查询的 API

`gh api` 命令对于访问其他子命令无法获取的数据非常有用。

获取带有特定字段的 PR：

```bash
gh api repos/owner/repo/pulls/55 --jq '.title, .state, .user.login'
```

## JSON 输出

大多数命令支持使用 `--json` 进行结构化输出。您可以使用 `--jq` 进行过滤：

```bash
gh issue list --repo owner/repo --json number,title --jq '.[] | "\(.number): \(.title)"'
```
