"""Read-only GitHub API integration.

A token may be supplied through the GITHUB_TOKEN environment variable. It is
never accepted from the request body, never persisted and never logged.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from ..config import settings
from ..utils import parse_datetime
from .permissions import sensitivity_label


def _q(value: Any) -> str:
    return json.dumps(str(value or "").replace("\n", " ").replace("\r", " "), ensure_ascii=False)


def parse_repository(value: str) -> tuple[str, str]:
    text = value.strip()
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    elif "://" in text:
        parsed = urlparse(text)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only github.com repository URLs are supported")
        text = parsed.path.strip("/")
    text = text.removesuffix(".git").strip("/")
    match = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", text)
    if not match:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use owner/repository or a GitHub repository URL")
    return match.group(1), match.group(2)


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "KnowledgeBridge-Hackathon-Demo",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _get(path: str, params: dict[str, Any]) -> Any:
    url = settings.github_api_base.rstrip("/") + path
    try:
        response = httpx.get(url, params=params, headers=_headers(), timeout=20.0, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"GitHub API is unreachable: {exc}") from exc
    if response.status_code != 200:
        message = response.text[:200].replace("\n", " ")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub API returned {response.status_code}: {message}",
        )
    return response.json()


def _extract_refs(text: str) -> list[str]:
    refs = re.findall(r"\b(?:KB|DEC|RISK|BLK|Q|UF|NA|GH|GIT)-[A-Z0-9]+\b", text or "", flags=re.IGNORECASE)
    seen: list[str] = []
    for ref in refs:
        upper = ref.upper()
        if upper not in seen:
            seen.append(upper)
    return seen[:6]


def fetch_github_activity(
    repository: str,
    branch: str,
    max_commits: int,
    max_issues: int,
    sensitivity: int = 1,
) -> list[dict[str, Any]]:
    owner, repo = parse_repository(repository)
    label = sensitivity_label(sensitivity)
    commits = _get(f"/repos/{owner}/{repo}/commits", {"sha": branch, "per_page": max_commits})
    issues = _get(f"/repos/{owner}/{repo}/issues", {"state": "all", "per_page": max_issues}) if max_issues else []
    documents: list[dict[str, Any]] = []

    for commit in commits if isinstance(commits, list) else []:
        sha = str(commit.get("sha", ""))[:12]
        if not sha:
            continue
        commit_data = commit.get("commit") or {}
        message = commit_data.get("message", "")
        author_data = commit_data.get("author") or {}
        author = author_data.get("name") or (commit.get("author") or {}).get("login") or "unknown"
        timestamp = parse_datetime(author_data.get("date")) or datetime.utcnow()
        source_ref = f"GHSRC-{sha[:8].upper()}"
        external_ref = commit.get("html_url") or f"https://github.com/{owner}/{repo}/commit/{sha}"
        content = "\n".join([
            "---",
            f"id: {source_ref}",
            f"title: {_q(f'GitHub commit {sha[:7]}: {message.splitlines()[0] if message else sha[:7]}')}",
            "type: github_commit",
            f"date: {timestamp.date().isoformat()}",
            f"author: {_q(author)}",
            f"sensitivity: {label}",
            f"external_ref: {_q(external_ref)}",
            "---",
            "",
            "# Live GitHub API evidence",
            "",
            f"@commit id=GIT-{sha[:7]} sha={_q(sha)} message={_q(message)} author={_q(author)} date={timestamp.date().isoformat()} files={_q('')} tags=repository,commit sensitivity={label}",
        ])
        documents.append({
            "title": f"GitHub commit {sha[:7]}: {(message.splitlines() or [sha[:7]])[0][:120]}",
            "content": content,
            "source_type": "github_commit",
            "external_ref": external_ref,
            "author": author,
            "source_timestamp": timestamp,
            "sensitivity": sensitivity,
            "metadata": {"source_ref": source_ref, "kind": "commit", "sha": sha},
        })

    for issue in issues if isinstance(issues, list) else []:
        if issue.get("pull_request"):
            continue  # GitHub returns PRs in the issues endpoint; skip duplicates.
        number = issue.get("number")
        if number is None:
            continue
        title = issue.get("title", f"Issue {number}")
        body = issue.get("body") or ""
        state = issue.get("state", "open")
        author = (issue.get("user") or {}).get("login", "unknown")
        timestamp = parse_datetime(issue.get("created_at")) or datetime.utcnow()
        source_ref = f"GHSRC-ISSUE-{number}"
        external_ref = issue.get("html_url") or f"https://github.com/{owner}/{repo}/issues/{number}"
        labels = ",".join(label_item.get("name", "") for label_item in issue.get("labels", []) if isinstance(label_item, dict))
        refs = _extract_refs(f"{title} {body}")
        depends_on = ",".join(refs)
        content = "\n".join([
            "---",
            f"id: {source_ref}",
            f"title: {_q(f'GitHub issue #{number}: {title}')}",
            "type: github_issue",
            f"date: {timestamp.date().isoformat()}",
            f"author: {_q(author)}",
            f"sensitivity: {label}",
            f"external_ref: {_q(external_ref)}",
            "---",
            "",
            "# Live GitHub API evidence",
            "",
            f"Issue body: {body[:1200].replace(chr(10), ' ')}",
            "",
            f"@issue id=GH-{number} title={_q(title)} status={state} owner={_q(author)} labels={_q(labels or 'repository')} date={timestamp.date().isoformat()} depends_on={_q(depends_on)} tags=repository,issue sensitivity={label}",
        ])
        documents.append({
            "title": f"GitHub issue #{number}: {title}"[:240],
            "content": content,
            "source_type": "github_issue",
            "external_ref": external_ref,
            "author": author,
            "source_timestamp": timestamp,
            "sensitivity": sensitivity,
            "metadata": {"source_ref": source_ref, "kind": "issue", "number": number},
        })
    return documents
