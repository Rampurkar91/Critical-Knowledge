"""Read-only GitHub API integration.

A token may be supplied through the GITHUB_TOKEN environment variable. It is
never accepted from the request body, never persisted and never logged.

Imported per repository: README, recent commits, issues and pull requests.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
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


def _plain(text: str, limit: int) -> str:
    """Trim free text and make sure no line can be read as an @record or front matter."""
    cleaned = re.sub(r"(?m)^\s*@", "at ", text or "")
    cleaned = re.sub(r"(?m)^\s*-{3,}\s*$", "***", cleaned)
    return cleaned[:limit]


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
        # Preserve 404 so optional resources such as a missing README can be
        # skipped without hiding rate-limit, authentication or server failures.
        error_status = (
            status.HTTP_404_NOT_FOUND
            if response.status_code == 404
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=error_status,
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


def _repository_key(owner: str, repo: str) -> str:
    """Short stable namespace so issue/PR IDs cannot collide across repos."""
    identity = f"{owner.strip().lower()}/{repo.strip().lower()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10].upper()


def _readme_document(owner: str, repo: str, branch: str, label: str, sensitivity: int) -> dict[str, Any] | None:
    """README as a plain-text source. A repository without a README is not an error."""
    try:
        data = _get(f"/repos/{owner}/{repo}/readme", {"ref": branch})
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return None
        raise
    if not isinstance(data, dict):
        return None
    try:
        text = base64.b64decode(data.get("content") or "").decode("utf-8", errors="replace")
    except (binascii.Error, ValueError):
        return None
    if not text.strip():
        return None

    repository_key = _repository_key(owner, repo)
    source_ref = f"GHSRC-README-{repository_key}"
    external_ref = data.get("html_url") or f"https://github.com/{owner}/{repo}#readme"
    timestamp = datetime.utcnow()
    title = f"GitHub README: {owner}/{repo}"
    content = "\n".join([
        "---",
        f"id: {source_ref}",
        f"title: {_q(title)}",
        "type: project_document",
        # Do not embed today's date in the content: source deduplication hashes
        # the full document, so an unchanged README should remain a duplicate.
        f"author: {_q(owner)}",
        f"sensitivity: {label}",
        f"external_ref: {_q(external_ref)}",
        "---",
        "",
        "# Live GitHub API evidence: README",
        "",
        _plain(text, 6000),
    ])
    return {
        "title": title,
        "content": content,
        "source_type": "project_document",
        "external_ref": external_ref,
        "author": owner,
        "source_timestamp": timestamp,
        "sensitivity": sensitivity,
        "metadata": {"source_ref": source_ref, "kind": "readme"},
    }


def fetch_github_activity(
    repository: str,
    branch: str,
    max_commits: int,
    max_issues: int,
    sensitivity: int = 1,
) -> list[dict[str, Any]]:
    owner, repo = parse_repository(repository)
    repository_key = _repository_key(owner, repo)
    label = sensitivity_label(sensitivity)
    commits = _get(f"/repos/{owner}/{repo}/commits", {"sha": branch, "per_page": max_commits})
    issues = _get(f"/repos/{owner}/{repo}/issues", {"state": "all", "per_page": max_issues}) if max_issues else []
    pulls = _get(f"/repos/{owner}/{repo}/pulls", {"state": "all", "per_page": max_issues}) if max_issues else []

    documents: list[dict[str, Any]] = []

    readme = _readme_document(owner, repo, branch, label, sensitivity)
    if readme:
        documents.append(readme)

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
            continue  # GitHub returns PRs in the issues endpoint; they are imported from /pulls below.
        number = issue.get("number")
        if number is None:
            continue
        title = issue.get("title", f"Issue {number}")
        body = issue.get("body") or ""
        state = issue.get("state", "open")
        author = (issue.get("user") or {}).get("login", "unknown")
        timestamp = parse_datetime(issue.get("created_at")) or datetime.utcnow()
        source_ref = f"GHSRC-ISSUE-{repository_key}-{number}"
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
            f"Issue body: {_plain(body, 1200).replace(chr(10), ' ')}",
            "",
            f"@issue id=GH-{repository_key}-{number} title={_q(title)} status={state} owner={_q(author)} labels={_q(labels or 'repository')} date={timestamp.date().isoformat()} depends_on={_q(depends_on)} tags=repository,issue sensitivity={label}",
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

    # Pull requests reuse the issue record format so the existing extractor, graph and
    # verification code handle them unchanged. The repository key keeps record IDs
    # distinct when multiple repositories are imported into the same project.
    for pull in pulls if isinstance(pulls, list) else []:
        number = pull.get("number")
        if number is None:
            continue
        title = pull.get("title", f"Pull request {number}")
        body = pull.get("body") or ""
        merged = bool(pull.get("merged_at"))
        state = "closed" if merged or pull.get("state") == "closed" else "open"
        author = (pull.get("user") or {}).get("login", "unknown")
        timestamp = parse_datetime(pull.get("created_at")) or datetime.utcnow()
        source_ref = f"GHSRC-PR-{repository_key}-{number}"
        external_ref = pull.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{number}"
        base_ref = (pull.get("base") or {}).get("ref", branch)
        head_ref = (pull.get("head") or {}).get("ref", "")
        label_names = [item.get("name", "") for item in pull.get("labels", []) if isinstance(item, dict)]
        labels = ",".join(["pull-request"] + (["merged"] if merged else []) + [name for name in label_names if name])
        refs = _extract_refs(f"{title} {body}")
        depends_on = ",".join(refs)
        content = "\n".join([
            "---",
            f"id: {source_ref}",
            f"title: {_q(f'GitHub pull request #{number}: {title}')}",
            "type: github_issue",
            f"date: {timestamp.date().isoformat()}",
            f"author: {_q(author)}",
            f"sensitivity: {label}",
            f"external_ref: {_q(external_ref)}",
            "---",
            "",
            "# Live GitHub API evidence: pull request",
            "",
            f"Branches: {head_ref} into {base_ref}. Merged: {'yes' if merged else 'no'}.",
            f"Pull request body: {_plain(body, 1200).replace(chr(10), ' ')}",
            "",
            f"@issue id=GH-{repository_key}-{number} title={_q(title)} status={state} owner={_q(author)} labels={_q(labels)} date={timestamp.date().isoformat()} depends_on={_q(depends_on)} tags=repository,pull_request sensitivity={label}",
        ])
        documents.append({
            "title": f"GitHub pull request #{number}: {title}"[:240],
            "content": content,
            "source_type": "github_issue",
            "external_ref": external_ref,
            "author": author,
            "source_timestamp": timestamp,
            "sensitivity": sensitivity,
            "metadata": {"source_ref": source_ref, "kind": "pull_request", "number": number},
        })

    return documents
