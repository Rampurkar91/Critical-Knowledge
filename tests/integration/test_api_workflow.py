"""End-to-end API workflow test for the hackathon demonstration."""
from __future__ import annotations

import json

import pytest

from backend.app.config import SAMPLE_DATA_DIR

pytestmark = pytest.mark.integration

RESTRICTED_MARKERS = ["RESTRICTED-CANARY-9F3A", "DEC-900", "SRC-009", "F-900", "KB-900", "RISK-900"]


def _no_leak(payload: object, markers=RESTRICTED_MARKERS) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for marker in markers:
        assert marker not in text, f"restricted marker leaked: {marker}"


def test_complete_handover_workflow(
    client,
    seeded_ids,
    manager_headers,
    engineer_headers,
    analyst_headers,
    auditor_headers,
):
    project_id = seeded_ids["project_id"]
    gold = json.loads((SAMPLE_DATA_DIR / "gold_labels.json").read_text())

    # Stage 1–2: authenticated project and authorised source list.
    projects = client.get("/api/projects", headers=manager_headers)
    assert projects.status_code == 200
    assert any(p["key"] == "ATLAS" for p in projects.json())
    sources = client.get(f"/api/projects/{project_id}/sources", headers=manager_headers)
    assert sources.status_code == 200
    assert sources.json()["total"] >= 10

    # Stage 3–5: extraction and verification endpoints.
    extraction = client.post(f"/api/projects/{project_id}/extract", json={"reprocess": False}, headers=manager_headers)
    assert extraction.status_code == 200
    assert "verification" in extraction.json()
    verification = client.get(f"/api/projects/{project_id}/verification/summary", headers=manager_headers)
    assert verification.status_code == 200
    assert "not a statistically calibrated probability" in verification.json()["score_disclaimer"]
    conflicts = client.get(f"/api/projects/{project_id}/conflicts", headers=manager_headers)
    assert conflicts.status_code == 200
    assert conflicts.json()["total"] >= 2
    for conflict in conflicts.json()["items"]:
        if conflict["status"] != "open":
            continue
        candidates = [c for c in [conflict["claim_a"], conflict["claim_b"]] if c]
        selected = max(candidates, key=lambda c: c.get("source_timestamp") or "")["id"]
        resolved = client.post(
            f"/api/conflicts/{conflict['id']}/resolve",
            json={"resolution_claim_id": selected, "note": "Newer primary-source record confirmed by manager."},
            headers=manager_headers,
        )
        assert resolved.status_code == 200, resolved.text

    # Stage 6: human review and approval.
    approval = client.post(f"/api/projects/{project_id}/review/approve-eligible", json={}, headers=manager_headers)
    assert approval.status_code == 200
    assert approval.json()["approved"] > 0

    # Stage 7–8: generate, review/correct, approve and share a role-specific handover.
    generated = client.post(
        f"/api/projects/{project_id}/handovers/generate",
        json={"recipient_user_id": seeded_ids["engineer_id"]},
        headers=manager_headers,
    )
    assert generated.status_code == 201, generated.text
    handover = generated.json()
    handover_id = handover["id"]
    assert handover["status"] == "draft"
    assert handover["clearance"] == "internal"
    _no_leak(handover["content"])
    action_refs = [a["external_ref"] for a in handover["content"]["next_actions"]]
    assert action_refs == gold["next_action_refs_for_incoming_engineer"]
    assert len(handover["content"]["next_actions"]) == 5

    edited_content = json.loads(json.dumps(handover["content"]))
    edited_content.setdefault("metadata", {})["manager_reviewed"] = True
    edited = client.patch(
        f"/api/handovers/{handover_id}",
        json={
            "title": "Incoming Engineer Handover — manager reviewed",
            "edit_note": "Manager checked priority order before approval.",
            "content_json": edited_content,
        },
        headers=manager_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == 2
    approved = client.post(f"/api/handovers/{handover_id}/approve", json={}, headers=manager_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    shared = client.post(f"/api/handovers/{handover_id}/share", json={}, headers=manager_headers)
    assert shared.status_code == 200
    assert shared.json()["status"] == "shared"
    manager_export = client.get(f"/api/handovers/{handover_id}/export", headers=manager_headers)
    assert manager_export.status_code == 200
    for marker in RESTRICTED_MARKERS:
        assert marker not in manager_export.text

    # Stage 9: incoming member receives only authorised information.
    mine = client.get("/api/handovers/mine", headers=engineer_headers)
    assert mine.status_code == 200
    assert any(item["id"] == handover_id for item in mine.json()["items"])
    incoming = client.get(f"/api/handovers/{handover_id}", headers=engineer_headers)
    assert incoming.status_code == 200
    assert incoming.json()["status"] == "shared"
    _no_leak(incoming.json())

    engineer_graph = client.get(f"/api/projects/{project_id}/graph?as_of=2026-11-09", headers=engineer_headers)
    assert engineer_graph.status_code == 200
    _no_leak(engineer_graph.json())
    assert engineer_graph.json()["hidden_by_policy"]["nodes"] > 0
    assert engineer_graph.json()["hidden_by_policy"]["edges"] > 0

    analyst_graph = client.get(f"/api/projects/{project_id}/graph?as_of=2026-11-09", headers=analyst_headers)
    assert analyst_graph.status_code == 200
    _no_leak(analyst_graph.json())
    assert analyst_graph.json()["hidden_by_policy"]["nodes"] >= engineer_graph.json()["hidden_by_policy"]["nodes"]

    manager_graph = client.get(f"/api/projects/{project_id}/graph?as_of=2026-11-09", headers=manager_headers)
    assert manager_graph.status_code == 200
    manager_graph_text = json.dumps(manager_graph.json())
    assert "DEC-900" in manager_graph_text and "SRC-009" in manager_graph_text

    search = client.get(
        f"/api/projects/{project_id}/search",
        params={"q": "RESTRICTED-CANARY-9F3A"},
        headers=engineer_headers,
    )
    assert search.status_code == 200
    assert search.json()["sources"] == []
    assert search.json()["claims"] == []
    _no_leak({"sources": search.json()["sources"], "claims": search.json()["claims"]})

    ask = client.post(
        f"/api/projects/{project_id}/ask",
        json={"question": "What is the restricted production key rotation path?", "top_k": 5},
        headers=engineer_headers,
    )
    assert ask.status_code == 200
    _no_leak(ask.json())
    assert ask.json()["provider"] in {"deterministic-local", "deterministic-fallback"}

    engineer_claims = client.get(f"/api/projects/{project_id}/claims?limit=500", headers=engineer_headers)
    assert engineer_claims.status_code == 200
    _no_leak(engineer_claims.json())
    engineer_tasks = client.get(f"/api/projects/{project_id}/tasks", headers=engineer_headers)
    assert engineer_tasks.status_code == 200
    _no_leak(engineer_tasks.json())
    engineer_export = client.get(f"/api/handovers/{handover_id}/export", headers=engineer_headers)
    assert engineer_export.status_code == 200
    for marker in RESTRICTED_MARKERS:
        assert marker not in engineer_export.text

    # Stage 10: acknowledgement, continuation and completion tracking.
    items = client.get(f"/api/handovers/{handover_id}/items", headers=engineer_headers)
    assert items.status_code == 200
    assert items.json()["total"] > 0
    item_id = items.json()["items"][0]["id"]
    for action in ["acknowledge", "start", "complete"]:
        result = client.post(
            f"/api/handover-items/{item_id}/action",
            json={"action": action, "note": "Continuation workflow test."},
            headers=engineer_headers,
        )
        assert result.status_code == 200, result.text
    continuity = client.get(f"/api/projects/{project_id}/continuity", headers=engineer_headers)
    assert continuity.status_code == 200
    assert continuity.json()["acknowledgement_rate"] > 0
    manager_continuity = client.get(f"/api/projects/{project_id}/continuity", headers=manager_headers)
    assert manager_continuity.status_code == 200
    assert manager_continuity.json()["incoming_member_task_understanding"]["measured"] is False

    # Governance: audit chain and access management.
    audit = client.get(f"/api/projects/{project_id}/audit", headers=auditor_headers)
    assert audit.status_code == 200
    assert audit.json()["hash_chain_continuity_valid"] is True
    members = client.get(f"/api/projects/{project_id}/members", headers=manager_headers)
    assert members.status_code == 200
    analyst_member = next(m for m in members.json() if m["email"] == "analyst@knowledgebridge.demo")
    updated = client.patch(
        f"/api/members/{analyst_member['id']}",
        json={"max_clearance": 1},
        headers=manager_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["clearance"] == 1
    restored = client.patch(
        f"/api/members/{analyst_member['id']}",
        json={"max_clearance": 0},
        headers=manager_headers,
    )
    assert restored.status_code == 200
    assert restored.json()["clearance"] == 0

    # External user in a different organisation cannot enumerate the project.
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "external@knowledgebridge.test",
            "password": "ExternalPass!2026",
            "full_name": "External User",
            "organization_name": "External Test Org",
        },
    )
    assert registration.status_code == 201
    external_headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    denied = client.get(f"/api/projects/{project_id}", headers=external_headers)
    assert denied.status_code == 404
