import json
import os
from typing import Any

from github import Auth, Github

from nanobot.agent.tools.base import Tool

from nanobot.config.loader import get_data_dir


class GitHubTool(Tool):
    """Tool for interacting with GitHub (issues, PRs, repos)."""

    name = "github"
    description = """
    Interact with GitHub to manage issues, PRs, and repositories.
    Capabilities:
    - Issues: List, read, create, comment.
    - PRs: List, get diff.
    - Repos: List my repos.

    Setup:
    Requires 'github_config.json' in your nanobot home with:
    { "token": "ghp_..." }
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_issues",
                    "get_issue",
                    "create_issue",
                    "comment_issue",
                    "list_prs",
                    "get_pr_diff",
                    "list_repos",
                    "list_commits",
                    "setup",
                ],
                "description": "The action to perform.",
            },
            "repo": {"type": "string", "description": "Repository name (e.g. 'owner/repo')."},
            "issue_number": {"type": "integer", "description": "Issue or PR number."},
            "title": {"type": "string", "description": "Title for new issue."},
            "body": {"type": "string", "description": "Body content for issue/comment."},
            "limit": {"type": "integer", "description": "Limit results (default 10)."},
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "description": "State for filtering issues/PRs (default 'open').",
            },
            "setup_token": {"type": "string", "description": "GitHub PAT for setup."},
        },
        "required": ["action"],
    }

    def _load_config(self):
        config_path = get_data_dir() / "github_config.json"
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_config(self, token):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({"token": token}, f)

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "setup":
            token = kwargs.get("setup_token")
            if not token:
                return "Error: 'setup_token' is required for setup."
            self._save_config(token)
            return "GitHub configuration saved successfully."

        config = self._load_config()
        if not config or "token" not in config:
            return "Error: GitHub not configured. Please action='setup' with setup_token."

        try:
            auth = Auth.Token(config["token"])
            g = Github(auth=auth)

            if action == "list_issues":
                repo_name = kwargs.get("repo")
                if not repo_name:
                    return "Error: 'repo' is required."
                return self._list_issues(
                    g, repo_name, kwargs.get("state", "open"), kwargs.get("limit", 10)
                )

            elif action == "get_issue":
                repo_name = kwargs.get("repo")
                number = kwargs.get("issue_number")
                if not repo_name or not number:
                    return "Error: 'repo' and 'issue_number' required."
                return self._get_issue(g, repo_name, number)

            elif action == "create_issue":
                repo_name = kwargs.get("repo")
                title = kwargs.get("title")
                body = kwargs.get("body", "")
                if not repo_name or not title:
                    return "Error: 'repo' and 'title' required."
                return self._create_issue(g, repo_name, title, body)

            elif action == "comment_issue":
                repo_name = kwargs.get("repo")
                number = kwargs.get("issue_number")
                body = kwargs.get("body")
                if not repo_name or not number or not body:
                    return "Error: 'repo', 'issue_number', 'body' required."
                return self._comment_issue(g, repo_name, number, body)

            elif action == "list_prs":
                repo_name = kwargs.get("repo")
                if not repo_name:
                    return "Error: 'repo' is required."
                return self._list_prs(
                    g, repo_name, kwargs.get("state", "open"), kwargs.get("limit", 10)
                )

            elif action == "get_pr_diff":
                repo_name = kwargs.get("repo")
                number = kwargs.get("issue_number")
                if not repo_name or not number:
                    return "Error: 'repo' and 'issue_number' required."
                return self._get_pr_diff(g, repo_name, number)

            elif action == "list_repos":
                return self._list_repos(g, kwargs.get("limit", 10))

            elif action == "list_commits":
                repo_name = kwargs.get("repo")
                if not repo_name:
                    return "Error: 'repo' is required."
                return self._list_commits(g, repo_name, kwargs.get("limit", 10))

            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"GitHub Tool Error: {str(e)}"

    def _list_issues(self, g, repo_name, state, limit):
        repo = g.get_repo(repo_name)
        issues = repo.get_issues(state=state)
        output = [f"Issues in {repo_name} ({state}):"]
        count = 0
        for issue in issues:
            if count >= limit:
                break
            if issue.pull_request:
                continue  # Skip PRs
            output.append(f"#{issue.number} {issue.title} (by {issue.user.login})")
            count += 1
        return "\n".join(output)

    def _get_issue(self, g, repo_name, number):
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number)
        comments = list(issue.get_comments())
        output = [
            f"#{issue.number} {issue.title}",
            f"State: {issue.state}",
            f"Author: {issue.user.login}",
            f"\nBody:\n{issue.body}\n",
            f"Comments ({len(comments)}):",
        ]
        for c in comments[-5:]:  # Last 5 comments (PyGithub paginates, list() forces fetch)
            output.append(f"[{c.user.login}]: {c.body[:200]}...")
        return "\n".join(output)

    def _create_issue(self, g, repo_name, title, body):
        repo = g.get_repo(repo_name)
        issue = repo.create_issue(title=title, body=body)
        return f"Issue created: #{issue.number} {issue.html_url}"

    def _comment_issue(self, g, repo_name, number, body):
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number)
        comment = issue.create_comment(body)
        return f"Comment added: {comment.html_url}"

    def _list_prs(self, g, repo_name, state, limit):
        repo = g.get_repo(repo_name)
        prs = repo.get_pulls(state=state)
        output = [f"PRs in {repo_name} ({state}):"]
        count = 0
        for pr in prs:
            if count >= limit:
                break
            output.append(f"#{pr.number} {pr.title} (by {pr.user.login})")
            count += 1
        return "\n".join(output)

    def _get_pr_diff(self, g, repo_name, number):
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(number)
        # PyGithub doesn't wrap raw diff easily, use requests on diff_url for raw patch
        import requests

        resp = requests.get(pr.diff_url)
        return f"Diff for PR #{number}:\n{resp.text[:5000]}"  # Truncate

    def _list_repos(self, g, limit):
        output = ["My Repositories:"]
        count = 0
        for repo in g.get_user().get_repos(sort="updated", direction="desc"):
            if count >= limit:
                break
            output.append(
                f"{repo.full_name} ({repo.stargazers_count}★) - {repo.description or 'No desc'}"
            )
            count += 1
        return "\n".join(output)

    def _list_commits(self, g, repo_name, limit):
        repo = g.get_repo(repo_name)
        commits = repo.get_commits()
        output = [f"Recent commits in {repo_name}:"]
        count = 0
        for commit in commits:
            if count >= limit:
                break
            msg = commit.commit.message.split("\n")[0]
            author = commit.commit.author.name
            date = commit.commit.author.date.strftime("%Y-%m-%d")
            output.append(f"[{date}] {commit.sha[:7]} {msg} (by {author})")
            count += 1
        return "\n".join(output)
