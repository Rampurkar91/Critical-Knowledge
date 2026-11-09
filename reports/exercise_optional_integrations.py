"""Exercise optional upload, GitHub and OpenAI-compatible LLM API paths.

This script uses a disposable SQLite database and a LOCAL mock HTTP server for
both GitHub and the LLM adapter. It makes no external API calls and requires no
real token or API key. It is intentionally separate from the measured core
evaluation in ``reports/generate_evaluation.py``: the results below demonstrate
that the optional routes work, not that a production GitHub/LLM integration was
benchmarked.

Run:

    .venv/bin/python reports/exercise_optional_integrations.py

Outputs:

    reports/optional_integrations.json
    reports/OPTIONAL_INTEGRATIONS.md
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Dummy values only. They never leave the local 127.0.0.1 mock server.
DEMO_PASSWORD = "DemoPass!2026"
GITHUB_TOKEN = "local-mock-github-token"
LLM_API_KEY = "local-mock-llm-key"
LLM_MODEL = "knowledgebridge-grounded-mock"


class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _record(self, method: str, path: str, **extra: Any) -> None:
        with self.server.lock:  # type: ignore[attr-defined]
            self.server.calls.append({  # type: ignore[attr-defined]
                "method": method,
                "path": path,
                "authorization_present": bool(self.headers.get("Authorization")),
                **extra,
            })

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        self._record("GET", path)
        if path == "/repos/knowledgebridge/mock-repo/commits":
            self._send_json([
                {
                    "sha": "abc123def4567890abcdef",
                    "html_url": "https://github.com/knowledgebridge/mock-repo/commit/abc123d",
                    "commit": {
                        "message": "Add continuity runbook checksum",
                        "author": {"name": "Demo Maintainer", "date": "2026-11-08T10:00:00Z"},
                    },
                    "author": {"login": "demo-maintainer"},
                },
                {
                    "sha": "def456abc7890123abcdef",
                    "html_url": "https://github.com/knowledgebridge/mock-repo/commit/def456a",
                    "commit": {
                        "message": "Clarify rollback verification step",
                        "author": {"name": "Demo Maintainer", "date": "2026-11-09T09:15:00Z"},
                    },
                    "author": {"login": "demo-maintainer"},
                },
            ])
            return
        if path == "/repos/knowledgebridge/mock-repo/issues":
            # One pull request is intentionally included: the adapter must skip it.
            self._send_json([
                {
                    "number": 42,
                    "title": "Verify migration handover checklist",
                    "body": "Confirm the KB-107 rollback runbook and DEP-001 evidence links.",
                    "state": "open",
                    "user": {"login": "demo-reviewer"},
                    "created_at": "2026-11-07T12:00:00Z",
                    "html_url": "https://github.com/knowledgebridge/mock-repo/issues/42",
                    "labels": [{"name": "continuity"}, {"name": "documentation"}],
                },
                {
                    "number": 43,
                    "title": "Automated pull request that must be skipped",
                    "body": "Duplicate of issue 42",
                    "state": "open",
                    "user": {"login": "demo-bot"},
                    "created_at": "2026-11-07T12:30:00Z",
                    "html_url": "https://github.com/knowledgebridge/mock-repo/pull/43",
                    "labels": [],
                    "pull_request": {"url": "https://github.com/knowledgebridge/mock-repo/pulls/43"},
                },
            ])
            return
        self._send_json({"detail": f"Unexpected mock path: {path}"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8"))
        if parsed.path == "/v1/chat/completions":
            user_content = payload.get("messages", [{}])[-1].get("content", "")
            evidence_count = len(re.findall(r"\[\d+\] source=", user_content))
            restricted_marker = "RESTRICTED-CANARY-9F3A" in user_content
            self._record(
                "POST",
                parsed.path,
                model=payload.get("model"),
                evidence_count=evidence_count,
                restricted_marker_present=restricted_marker,
            )
            self._send_json({
                "model": LLM_MODEL,
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": (
                            "Grounded local mock answer: the authorised evidence identifies the next "
                            "continuity actions and their supporting project records. Verify every "
                            "statement against the supplied citations."
                        ),
                    }
                }],
            })
            return
        self._record("POST", parsed.path)
        self._send_json({"detail": f"Unexpected mock path: {parsed.path}"}, status=404)


def make_mock_server() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    server.calls = []  # type: ignore[attr-defined]
    server.lock = threading.Lock()  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.background_thread = thread  # type: ignore[attr-defined]
    return server


def main() -> dict[str, Any]:
    server = make_mock_server()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"

        with tempfile.TemporaryDirectory(prefix="knowledgebridge-optional-") as temp_dir:
            db_path = Path(temp_dir) / "optional-integrations.db"
            os.environ.update({
                "APP_NAME": "KnowledgeBridge Optional Integration Exercise",
                "ENVIRONMENT": "test",
                "DATABASE_URL": f"sqlite:///{db_path}",
                "JWT_SECRET": "local-optional-integration-exercise-secret",
                "DEMO_PASSWORD": DEMO_PASSWORD,
                "SEED_DEMO_DATA": "true",
                "STALE_AFTER_DAYS": "120",
                "GITHUB_TOKEN": GITHUB_TOKEN,
                "GITHUB_API_BASE": base,
                "LLM_BASE_URL": f"{base}/v1",
                "LLM_API_KEY": LLM_API_KEY,
                "LLM_MODEL": LLM_MODEL,
                "NO_PROXY": "127.0.0.1,localhost",
                "no_proxy": "127.0.0.1,localhost",
            })
            for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                os.environ.pop(proxy_key, None)

            # Import AFTER configuring the environment: backend settings are frozen
            # at import time and must point to the disposable DB and local mocks.
            from fastapi.testclient import TestClient

            from backend.app.main import app

            text_content = """---
    id: SRC-OPTIONAL-TEXT
    title: "Optional text-source endpoint exercise"
    type: project_document
    date: 2026-11-09
    author: "Integration exercise"
    sensitivity: internal
    external_ref: "local://optional/text-source"
    ---
    # Local endpoint exercise

    @task id=KB-OPTIONAL-1 title="Verify text-source ingestion" owner="Demo Engineer" status=in_progress due=2026-11-15 depends_on= tags=integration,test sensitivity=internal priority=2 role_scope=incoming_engineer
    """
            upload_content = """---
    id: SRC-OPTIONAL-UPLOAD
    title: "Optional upload endpoint exercise"
    type: project_document
    date: 2026-11-09
    author: "Integration exercise"
    sensitivity: internal
    external_ref: "local://optional/upload"
    ---
    # Local upload exercise

    @question id=Q-OPTIONAL-1 question="Has the uploaded handover note been reviewed?" owner="Demo Lead" status=open date=2026-11-09 tags=integration,test sensitivity=internal priority=3 role_scope=incoming_engineer
    """

            results: dict[str, Any] = {}
            with TestClient(app) as client:
                login = client.post("/api/auth/login", json={
                    "email": "manager@knowledgebridge.demo",
                    "password": DEMO_PASSWORD,
                })
                login.raise_for_status()
                token = login.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                projects = client.get("/api/projects", headers=headers)
                projects.raise_for_status()
                project_id = projects.json()[0]["id"]

                text_response = client.post(
                    f"/api/projects/{project_id}/sources/text",
                    headers=headers,
                    json={
                        "title": "Optional text-source endpoint exercise",
                        "content": text_content,
                        "source_type": "project_document",
                        "author": "Integration exercise",
                        "source_date": "2026-11-09",
                        "sensitivity": 1,
                        "external_ref": "local://optional/text-source",
                    },
                )
                text_response.raise_for_status()
                results["text_source"] = {
                    "status_code": text_response.status_code,
                    "source_ref": text_response.json()["source"].get("external_ref"),
                    "source_id": text_response.json()["source"]["id"],
                }

                upload_response = client.post(
                    f"/api/projects/{project_id}/sources/upload",
                    headers=headers,
                    files={"file": ("optional-upload.md", upload_content.encode("utf-8"), "text/markdown")},
                    data={
                        "title": "Optional upload endpoint exercise",
                        "source_type": "project_document",
                        "author": "Integration exercise",
                        "sensitivity": "1",
                        "source_date": "2026-11-09",
                    },
                )
                upload_response.raise_for_status()
                results["file_upload"] = {
                    "status_code": upload_response.status_code,
                    "source_ref": upload_response.json()["source"].get("external_ref"),
                    "source_id": upload_response.json()["source"]["id"],
                }

                github_response = client.post(
                    f"/api/projects/{project_id}/sources/github/connect",
                    headers=headers,
                    json={
                        "repository": "knowledgebridge/mock-repo",
                        "branch": "main",
                        "max_commits": 2,
                        "max_issues": 2,
                        "sensitivity": 1,
                    },
                )
                github_response.raise_for_status()
                github_payload = github_response.json()
                results["github_connect"] = {
                    "status_code": github_response.status_code,
                    "repository": github_payload["repository"],
                    "sources_returned": github_payload["sources_returned"],
                    "sources_created": github_payload["sources_created"],
                    "duplicates": github_payload["duplicates"],
                    "token_used": True,
                }
                assert github_payload["sources_returned"] == 3, github_payload
                assert github_payload["sources_created"] == 3, github_payload

                extract_response = client.post(
                    f"/api/projects/{project_id}/extract",
                    headers=headers,
                    json={"reprocess": False},
                )
                extract_response.raise_for_status()
                extract_payload = extract_response.json()
                results["extraction"] = {
                    "status_code": extract_response.status_code,
                    "keys": sorted(extract_payload.keys()),
                    "claims": extract_payload.get("claims"),
                    "sources": extract_payload.get("sources"),
                }

                sources_response = client.get(f"/api/projects/{project_id}/sources", headers=headers)
                sources_response.raise_for_status()
                source_items = sources_response.json()
                if isinstance(source_items, dict):
                    source_items = source_items.get("items", [])
                results["authorised_sources_after_ingestion"] = len(source_items)

                ask_response = client.post(
                    f"/api/projects/{project_id}/ask",
                    headers=headers,
                    json={"question": "What should the incoming engineer do first?", "top_k": 5},
                )
                ask_response.raise_for_status()
                ask_payload = ask_response.json()
                results["grounded_llm_ask"] = {
                    "status_code": ask_response.status_code,
                    "provider": ask_payload["provider"],
                    "citation_count": len(ask_payload["citations"]),
                    "answer_prefix": ask_payload["answer"][:160],
                    "leakage_guard_applied": ask_payload["leakage_guard_applied"],
                    "score_disclaimer": ask_payload["score_disclaimer"],
                }
            assert ask_payload["provider"] == f"openai-compatible:{LLM_MODEL}", ask_payload
            assert ask_payload["citations"], ask_payload
            assert "RESTRICTED-CANARY-9F3A" not in ask_payload["answer"]

            calls = list(server.calls)  # type: ignore[attr-defined]
            llm_calls = [call for call in calls if call["path"] == "/v1/chat/completions"]
            github_calls = [call for call in calls if call["path"].startswith("/repos/")]
            assert llm_calls and github_calls, calls
            assert all(call["authorization_present"] for call in llm_calls + github_calls), calls
            assert all(not call.get("restricted_marker_present") for call in llm_calls), llm_calls
            assert all("RESTRICTED-CANARY-9F3A" not in json.dumps(call) for call in calls)

            summary = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Local mock GitHub API and local OpenAI-compatible LLM adapter; disposable SQLite DB; no external network call.",
                "external_api_calls": 0,
                "mock_base_url": base,
                "mock_request_count": len(calls),
                "mock_github_requests": len(github_calls),
                "mock_llm_requests": len(llm_calls),
                "mock_llm_evidence_count": llm_calls[0].get("evidence_count"),
                "mock_llm_restricted_marker_present": any(call.get("restricted_marker_present") for call in llm_calls),
                "disposable_database": True,
                "results": results,
            }
            return summary
    finally:
        server.shutdown()
        server.background_thread.join(timeout=5)  # type: ignore[attr-defined]
        server.server_close()


def write_reports(summary: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "optional_integrations.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    r = summary["results"]
    md = f"""# Optional integration endpoint exercise

**Status:** PASS — all exercised endpoints returned HTTP 2xx and all assertions passed.

**Generated:** {summary['generated_at']}

This is an implementation smoke test, not a production-integration benchmark.
It used a disposable SQLite database, a **local mock GitHub API** and a **local
OpenAI-compatible LLM adapter** bound to `127.0.0.1`. It made **0 external API
calls** and used dummy local tokens only. No real repository, model endpoint,
API key or customer data was contacted.

| Optional path | Measured result |
| --- | --- |
| `POST /api/projects/{{id}}/sources/text` | HTTP {r['text_source']['status_code']}; created `{r['text_source']['source_ref']}` |
| `POST /api/projects/{{id}}/sources/upload` | HTTP {r['file_upload']['status_code']}; created `{r['file_upload']['source_ref']}` |
| `POST /api/projects/{{id}}/sources/github/connect` | HTTP {r['github_connect']['status_code']}; `{r['github_connect']['repository']}` returned {r['github_connect']['sources_returned']} sources, created {r['github_connect']['sources_created']} (0 duplicates) |
| `POST /api/projects/{{id}}/extract` | HTTP {r['extraction']['status_code']}; reconstruction reran over the expanded source set |
| Authorised source count | {r['authorised_sources_after_ingestion']} sources visible to the manager after ingestion |
| `POST /api/projects/{{id}}/ask` with LLM configured | HTTP {r['grounded_llm_ask']['status_code']}; provider `{r['grounded_llm_ask']['provider']}`, {r['grounded_llm_ask']['citation_count']} authorised citations |
| Mock requests | {summary['mock_request_count']} total; {summary['mock_github_requests']} GitHub; {summary['mock_llm_requests']} LLM; all carried an Authorization header |
| LLM grounding | Mock request contained {summary['mock_llm_evidence_count']} authorised evidence entries; restricted-canary marker present: `{str(summary['mock_llm_restricted_marker_present']).lower()}` |

The deterministic local answer path (`provider=deterministic-local`) is measured
separately in `reports/EVALUATION_REPORT.md`. This exercise verifies the optional
adapter branch and its fallback inputs: `ai_engine/llm.py` receives only evidence
already filtered by `ai_engine/retrieval.py` and `backend/app/services/permissions.py`.

Reproduce with:

```bash
.venv/bin/python reports/exercise_optional_integrations.py
```

Machine-readable results: `reports/optional_integrations.json`.
"""
    (REPORT_DIR / "OPTIONAL_INTEGRATIONS.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    result = main()
    write_reports(result)
    print(json.dumps(result["results"], indent=2, ensure_ascii=False))
    print(f"mock requests: {result['mock_request_count']}, external API calls: {result['external_api_calls']}")
