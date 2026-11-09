"""Generate the measured KnowledgeBridge evaluation report.

This script creates a disposable SQLite database, seeds the labelled synthetic
dataset, exercises the API workflow and computes metrics from the actual
resulting rows and responses. It never uses an LLM or external GitHub call.
Run: .venv/bin/python reports/generate_evaluation.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(tempfile.mkdtemp(prefix="knowledgebridge-eval-"))
EVAL_DB = EVAL_DIR / "evaluation.db"
os.environ["DATABASE_URL"] = f"sqlite:///{EVAL_DB}"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["ENVIRONMENT"] = "evaluation"
os.environ["JWT_SECRET"] = "evaluation-only-jwt-secret"
os.environ["DEMO_PASSWORD"] = "EvalDemoPass!2026"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_MODEL"] = ""
os.environ["GITHUB_TOKEN"] = ""

sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from ai_engine.retrieval import retrieve  # noqa: E402
from backend.app.config import SAMPLE_DATA_DIR, settings  # noqa: E402
from backend.app.db import SessionLocal, init_db, session_scope  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import (  # noqa: E402
    AuditLog,
    Claim,
    ClaimReview,
    ConflictRecord,
    EvidenceSpan,
    Handover,
    KnowledgeEdge,
    KnowledgeNode,
    Project,
    ProjectMember,
    SourceDocument,
    User,
)
from backend.app.seed import seed_demo  # noqa: E402
from backend.app.services.orchestrator import run_full_reconstruction  # noqa: E402
from backend.app.utils import json_safe  # noqa: E402

GOLD = json.loads((SAMPLE_DATA_DIR / "gold_labels.json").read_text(encoding="utf-8"))
RESTRICTED_MARKERS = [
    *GOLD["restricted_sentinels"],
    "DEC-900",
    "SRC-009",
    "F-900",
    "KB-900",
    "RISK-900",
]


def safe_div(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def marker_hits(payload: Any) -> list[str]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    return [marker for marker in RESTRICTED_MARKERS if marker in text]


def bootstrap() -> dict[str, str]:
    init_db()
    with session_scope() as db:
        seeded = seed_demo(db)
    with session_scope() as db:
        run_full_reconstruction(db, seeded["project_id"], seeded["manager_id"])
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.key == "ATLAS").first()
        users = {u.email: u for u in db.query(User).all()}
        return {
            "project_id": project.id,
            "manager_id": users["manager@knowledgebridge.demo"].id,
            "engineer_id": users["engineer@knowledgebridge.demo"].id,
            "analyst_id": users["analyst@knowledgebridge.demo"].id,
            "auditor_id": users["auditor@knowledgebridge.demo"].id,
            "demo_password": settings.demo_password,
        }
    finally:
        db.close()


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def database_metrics(db, ids: dict[str, str]) -> dict[str, Any]:
    project_id = ids["project_id"]
    gold = GOLD
    claims = db.query(Claim).filter(Claim.project_id == project_id, Claim.is_active.is_(True)).all()
    expected_pairs = {
        (claim_type, ref)
        for claim_type, refs in gold["extraction"].items()
        for ref in refs
    }
    actual_pairs = {(claim.claim_type, claim.external_ref) for claim in claims if claim.claim_type != "dependency"}
    extraction_tp = len(expected_pairs & actual_pairs)
    extraction = prf(
        extraction_tp,
        len(actual_pairs - expected_pairs),
        len(expected_pairs - actual_pairs),
    )
    extraction["expected_labels"] = len(expected_pairs)
    extraction["actual_non_dependency_claims"] = len(actual_pairs)
    extraction["derived_dependency_claims"] = len([c for c in claims if c.claim_type == "dependency"])
    extraction["missing_labels"] = sorted(f"{t}:{r}" for t, r in expected_pairs - actual_pairs)
    extraction["unexpected_labels"] = sorted(f"{t}:{r}" for t, r in actual_pairs - expected_pairs)

    spans = db.query(EvidenceSpan).all()
    exact_offsets = 0
    for span in spans:
        source = db.get(SourceDocument, span.source_id)
        if source and source.content[span.start_char:span.end_char] == span.quote:
            exact_offsets += 1
    evidence = {
        "spans": len(spans),
        "exact_offset_matches": exact_offsets,
        "exact_offset_accuracy": safe_div(exact_offsets, len(spans)),
        "active_claims": len(claims),
        "claims_with_evidence_links": db.query(Claim).join(
            __import__("backend.app.models", fromlist=["ClaimEvidence"]).ClaimEvidence,
            Claim.id == __import__("backend.app.models", fromlist=["ClaimEvidence"]).ClaimEvidence.claim_id,
        ).filter(Claim.project_id == project_id, Claim.is_active.is_(True)).distinct().count(),
    }

    manager_member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == ids["manager_id"])
        .first()
    )
    engineer_member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == ids["engineer_id"])
        .first()
    )
    retrieval_rows = []
    for item in gold["retrieval_queries"]:
        results = retrieve(db, project_id, manager_member, item["query"], top_k=5)
        returned = [result["source_ref"] for result in results]
        relevant = set(item["relevant_sources"])
        hits = len(set(returned) & relevant)
        retrieval_rows.append({
            "query": item["query"],
            "returned_sources": returned,
            "relevant_sources": sorted(relevant),
            "precision_at_5": safe_div(hits, len(returned)),
            "recall_at_5": safe_div(hits, len(relevant)),
        })
    restricted_docs = retrieve(db, project_id, engineer_member, GOLD["restricted_sentinels"][0], top_k=5)
    restricted_hits = marker_hits(restricted_docs)
    retrieval = {
        "queries": len(retrieval_rows),
        "mean_precision_at_5": safe_div(sum(r["precision_at_5"] for r in retrieval_rows), len(retrieval_rows)),
        "mean_recall_at_5": safe_div(sum(r["recall_at_5"] for r in retrieval_rows), len(retrieval_rows)),
        "rows": retrieval_rows,
        "restricted_query_docs_returned_to_engineer": len(restricted_docs),
        "restricted_query_returned_source_refs": [doc["source_ref"] for doc in restricted_docs],
        "restricted_query_marker_hits": restricted_hits,
        "restricted_query_note": "A lexical match on the generic word 'restricted' may return an authorised internal document; the exact canary and hidden identifiers must not appear in its payload.",
        "definition": "TF-IDF lexical retrieval over authorised claim/evidence documents, source-deduplicated, top_k=5.",
    }

    detected_conflicts = {
        row.normalized_key
        for row in db.query(ConflictRecord).filter(ConflictRecord.project_id == project_id).all()
    }
    expected_conflicts = set(gold["conflict_keys"])
    conflict_metrics = prf(
        len(detected_conflicts & expected_conflicts),
        len(detected_conflicts - expected_conflicts),
        len(expected_conflicts - detected_conflicts),
    )
    conflict_metrics["detected_keys"] = sorted(detected_conflicts)

    outdated_detected = {c.external_ref for c in claims if c.verification_status == "Outdated"}
    expected_outdated = set(gold["outdated_refs"])
    outdated_metrics = prf(
        len(outdated_detected & expected_outdated),
        len(outdated_detected - expected_outdated),
        len(expected_outdated - outdated_detected),
    )
    outdated_metrics["detected_refs"] = sorted(outdated_detected)

    unsupported_detected = {c.external_ref for c in claims if c.verification_status == "Unsupported"}
    expected_unsupported = set(gold["unsupported_refs"])
    unsupported_metrics = prf(
        len(unsupported_detected & expected_unsupported),
        len(unsupported_detected - expected_unsupported),
        len(expected_unsupported - unsupported_detected),
    )
    unsupported_metrics["unsupported_claim_rate"] = safe_div(len(unsupported_detected), len(claims))
    unsupported_metrics["detected_refs"] = sorted(unsupported_detected)

    status_counts = dict(Counter(c.verification_status for c in claims))
    score_disclaimer = all(
        any("not a calibrated probability" in line for line in (c.score_rationale or []))
        for c in claims
    )

    nodes = db.query(KnowledgeNode).filter(KnowledgeNode.project_id == project_id).all()
    node_map = {node.id: node.node_key for node in nodes}
    edges = db.query(KnowledgeEdge).filter(KnowledgeEdge.project_id == project_id).all()
    actual_edge_triples = {
        (node_map.get(edge.source_node_id), node_map.get(edge.target_node_id), edge.relation)
        for edge in edges
    }
    expected_edge_triples = {
        (item["source_key"], item["target_key"], item["relation"])
        for item in gold["graph_edges"]
    }
    matched_edges = actual_edge_triples & expected_edge_triples
    dependency_claims = [c for c in claims if c.claim_type == "dependency"]
    actual_dependency_pairs = {
        f"{c.metadata_json.get('parent_ref')}|{c.metadata_json.get('target_ref')}"
        for c in dependency_claims
    }
    expected_dependency_pairs = set(gold["dependency_pairs"])
    dependency_metrics = prf(
        len(actual_dependency_pairs & expected_dependency_pairs),
        len(actual_dependency_pairs - expected_dependency_pairs),
        len(expected_dependency_pairs - actual_dependency_pairs),
    )
    graph = {
        "nodes": len(nodes),
        "edges": len(edges),
        "relation_counts": dict(Counter(edge.relation for edge in edges)),
        "depends_on_edges": len([edge for edge in edges if edge.relation == "depends_on"]),
        "restricted_nodes": len([node for node in nodes if node.sensitivity == 3]),
        "restricted_edges": len([edge for edge in edges if edge.sensitivity == 3]),
        "representative_gold_edges": len(expected_edge_triples),
        "representative_gold_edges_found": len(matched_edges),
        "representative_gold_edge_recall": safe_div(len(matched_edges), len(expected_edge_triples)),
        "all_edge_exact_match_rate": safe_div(len(matched_edges), len(actual_edge_triples)),
        "dependency_pair_metrics": dependency_metrics,
        "note": "gold graph_edges is a representative subset, not an exhaustive edge annotation; all_edge_exact_match_rate is not precision.",
    }

    return {
        "dataset": "synthetic demonstration dataset (Atlas Migration)",
        "extraction": extraction,
        "evidence": evidence,
        "retrieval": retrieval,
        "conflict_detection": conflict_metrics,
        "outdated_detection": outdated_metrics,
        "unsupported_detection": unsupported_metrics,
        "verification_status_counts": status_counts,
        "score_disclaimer_present_on_all_claims": score_disclaimer,
        "graph": graph,
    }


def api_metrics(ids: dict[str, str]) -> dict[str, Any]:
    project_id = ids["project_id"]
    password = ids["demo_password"]
    with TestClient(app) as client:
        manager = login(client, "manager@knowledgebridge.demo", password)
        engineer = login(client, "engineer@knowledgebridge.demo", password)
        analyst = login(client, "analyst@knowledgebridge.demo", password)

        conflicts = client.get(f"/api/projects/{project_id}/conflicts", headers=manager)
        assert conflicts.status_code == 200, conflicts.text
        resolutions = 0
        for conflict in conflicts.json()["items"]:
            if conflict["status"] != "open":
                continue
            candidates = [c for c in [conflict["claim_a"], conflict["claim_b"]] if c]
            selected = max(candidates, key=lambda c: c.get("source_timestamp") or "")["id"]
            response = client.post(
                f"/api/conflicts/{conflict['id']}/resolve",
                json={"resolution_claim_id": selected, "note": "Evaluation: newer primary-source record selected."},
                headers=manager,
            )
            assert response.status_code == 200, response.text
            resolutions += 1
        approval = client.post(f"/api/projects/{project_id}/review/approve-eligible", json={}, headers=manager)
        assert approval.status_code == 200, approval.text
        approved_claims = approval.json()["approved"]

        generated = client.post(
            f"/api/projects/{project_id}/handovers/generate",
            json={"recipient_user_id": ids["engineer_id"]},
            headers=manager,
        )
        assert generated.status_code == 201, generated.text
        generated_data = generated.json()
        handover_id = generated_data["id"]
        content = generated_data["content"]
        edited_content = json.loads(json.dumps(content))
        edited_content.setdefault("metadata", {})["manager_reviewed"] = True
        edited = client.patch(
            f"/api/handovers/{handover_id}",
            json={
                "title": "Incoming Engineer Handover — reviewed",
                "edit_note": "Evaluation: manager checked priority order.",
                "content_json": edited_content,
            },
            headers=manager,
        )
        assert edited.status_code == 200, edited.text
        approved = client.post(f"/api/handovers/{handover_id}/approve", json={}, headers=manager)
        assert approved.status_code == 200, approved.text
        shared = client.post(f"/api/handovers/{handover_id}/share", json={}, headers=manager)
        assert shared.status_code == 200, shared.text

        mine = client.get("/api/handovers/mine", headers=engineer)
        incoming = client.get(f"/api/handovers/{handover_id}", headers=engineer)
        engineer_export = client.get(f"/api/handovers/{handover_id}/export", headers=engineer)
        manager_export = client.get(f"/api/handovers/{handover_id}/export", headers=manager)
        assert all(r.status_code == 200 for r in [mine, incoming, engineer_export, manager_export])

        engineer_graph = client.get(f"/api/projects/{project_id}/graph?as_of=2026-11-09", headers=engineer)
        analyst_graph = client.get(f"/api/projects/{project_id}/graph?as_of=2026-11-09", headers=analyst)
        manager_graph = client.get(f"/api/projects/{project_id}/graph?as_of=2026-11-09", headers=manager)
        assert all(r.status_code == 200 for r in [engineer_graph, analyst_graph, manager_graph])
        manager_graph_text = json.dumps(manager_graph.json(), ensure_ascii=False)

        search = client.get(
            f"/api/projects/{project_id}/search",
            params={"q": GOLD["restricted_sentinels"][0]},
            headers=engineer,
        )
        ask = client.post(
            f"/api/projects/{project_id}/ask",
            json={"question": "What is the restricted production key rotation path?", "top_k": 5},
            headers=engineer,
        )
        engineer_claims = client.get(f"/api/projects/{project_id}/claims?limit=500", headers=engineer)
        engineer_tasks = client.get(f"/api/projects/{project_id}/tasks", headers=engineer)
        assert all(r.status_code == 200 for r in [search, ask, engineer_claims, engineer_tasks])

        denied = client.post(f"/api/handovers/{handover_id}/approve", json={}, headers=engineer)
        external_registration = client.post(
            "/api/auth/register",
            json={
                "email": "external@knowledgebridge.test",
                "password": "ExternalPass!2026",
                "full_name": "External User",
                "organization_name": "External Test Org",
            },
        )
        assert external_registration.status_code == 201, external_registration.text
        external_headers = {"Authorization": f"Bearer {external_registration.json()['access_token']}"}
        external_project = client.get(f"/api/projects/{project_id}", headers=external_headers)

        items = client.get(f"/api/handovers/{handover_id}/items", headers=engineer)
        assert items.status_code == 200, items.text
        item_actions = 0
        if items.json()["items"]:
            item_id = items.json()["items"][0]["id"]
            for action in ["acknowledge", "start", "complete"]:
                response = client.post(
                    f"/api/handover-items/{item_id}/action",
                    json={"action": action, "note": "Evaluation continuation workflow."},
                    headers=engineer,
                )
                assert response.status_code == 200, response.text
                item_actions += 1
        engineer_continuity = client.get(f"/api/projects/{project_id}/continuity", headers=engineer)
        manager_continuity = client.get(f"/api/projects/{project_id}/continuity", headers=manager)
        assert engineer_continuity.status_code == 200 and manager_continuity.status_code == 200
        audit = client.get(f"/api/projects/{project_id}/audit", headers=manager)
        assert audit.status_code == 200, audit.text

        low_clearance_channels = {
            "engineer_graph": engineer_graph.json(),
            "analyst_graph": analyst_graph.json(),
            "engineer_search": search.json(),
            "engineer_ask": ask.json(),
            "engineer_handover": incoming.json(),
            "engineer_export": engineer_export.text,
            "manager_export": manager_export.text,
            "engineer_claims": engineer_claims.json(),
            "engineer_tasks": engineer_tasks.json(),
        }
        channel_leaks = {name: marker_hits(payload) for name, payload in low_clearance_channels.items()}
        total_leaks = sum(len(hits) for hits in channel_leaks.values())

        db = SessionLocal()
        try:
            guard_events = db.query(AuditLog).filter(
                AuditLog.action == "permission.guard",
                AuditLog.outcome == "blocked",
            ).count()
            denied_events = db.query(AuditLog).filter(AuditLog.outcome == "denied").count()
            reviews = db.query(ClaimReview).filter(ClaimReview.project_id == project_id).all()
            corrections = len([review for review in reviews if review.action == "correct"])
            handover_rows = db.query(Handover).filter(Handover.project_id == project_id).all()
        finally:
            db.close()

        required_sections = GOLD["handover_required_sections"]
        present_sections = [section for section in required_sections if section in content]
        statement_sections = [
            *content.get("current_state", []),
            *content.get("responsibilities", []),
            *content.get("key_decisions", []),
            *content.get("open_questions", []),
            *content.get("next_actions", []),
            *content.get("risks_and_dependencies", {}).get("risks", []),
            *content.get("risks_and_dependencies", {}).get("dependency_claims", []),
            *content.get("risks_and_dependencies", {}).get("blockers", []),
        ]
        linked_statements = len([item for item in statement_sections if item.get("evidence")])
        action_refs = [item.get("external_ref") for item in content.get("next_actions", [])]
        expected_actions = GOLD["next_action_refs_for_incoming_engineer"]
        action_set = set(action_refs)
        expected_set = set(expected_actions)
        recommendation = prf(
            len(action_set & expected_set),
            len(action_set - expected_set),
            len(expected_set - action_set),
        )
        recommendation["exact_order_match"] = action_refs == expected_actions
        recommendation["returned_actions"] = action_refs
        recommendation["expected_actions"] = expected_actions
        recommendation["definition"] = "Priority-ranked next actions compared with hand-authored expected labels; not a human relevance study."

        continuity = manager_continuity.json()
        incoming_understanding = continuity.get("incoming_member_task_understanding", {})
        handover_quality = {
            "required_sections": len(required_sections),
            "sections_present": len(present_sections),
            "section_coverage": safe_div(len(present_sections), len(required_sections)),
            "statement_items_examined": len(statement_sections),
            "statement_items_with_evidence": linked_statements,
            "evidence_link_rate": safe_div(linked_statements, len(statement_sections)),
            "evidence_register_entries": len(content.get("evidence", [])),
            "uncertainty_fields": sorted(content.get("uncertainty", {}).keys()),
            "next_action_count": len(content.get("next_actions", [])),
            "checklist_count": len(content.get("checklist", [])),
            "generated_from_claim_ids": len(content.get("metadata", {}).get("generated_from_claim_ids", [])),
            "applied_filters": generated_data.get("applied_filters"),
            "definition": "Structural coverage and evidence-link checks on the generated handover; no human quality score.",
        }

        return {
            "workflow": {
                "open_conflicts_resolved": resolutions,
                "claims_bulk_approved": approved_claims,
                "handover_versions": edited.json()["version"],
                "handover_status": shared.json()["status"],
                "handover_items_available": items.json()["total"],
                "continuation_actions_performed": item_actions,
                "handovers_generated": len(handover_rows),
            },
            "handover_quality": handover_quality,
            "recommendation_relevance": recommendation,
            "continuity": {
                "acknowledgement_rate": engineer_continuity.json()["acknowledgement_rate"],
                "completion_rate": engineer_continuity.json()["completion_rate"],
                "items_total": engineer_continuity.json()["items_total"],
                "items_acknowledged": engineer_continuity.json()["items_acknowledged"],
                "items_completed": engineer_continuity.json()["items_completed"],
                "overdue_items": engineer_continuity.json()["overdue_items"],
                "open_questions": engineer_continuity.json()["open_questions"],
                "handover_prep_seconds": continuity.get("handover_prep_seconds"),
                "human_correction_rate": continuity.get("human_correction_rate"),
                "corrections": continuity.get("corrections"),
                "reviews_total": continuity.get("reviews_total"),
                "incoming_member_task_understanding": incoming_understanding,
                "definition": "Workflow telemetry from the actual generated handover and audit/review tables.",
            },
            "permission_enforcement": {
                "channels_in_gold": GOLD["permission_channels"],
                "channels_tested": len(low_clearance_channels),
                "restricted_marker_leaks": total_leaks,
                "channel_leaks": channel_leaks,
                "hidden_by_policy_engineer": engineer_graph.json()["hidden_by_policy"],
                "hidden_by_policy_analyst": analyst_graph.json()["hidden_by_policy"],
                "manager_can_see_restricted_graph": "DEC-900" in manager_graph_text and "SRC-009" in manager_graph_text,
                "search_query_guard_applied": search.json().get("query_guard_applied"),
                "ask_question_guard_applied": ask.json().get("question_guard_applied"),
                "ask_provider": ask.json()["provider"],
                "permission_guard_audit_events": guard_events,
                "denied_audit_events": denied_events,
                "engineer_approve_status": denied.status_code,
                "external_project_access_status": external_project.status_code,
                "hash_chain_continuity_valid": audit.json()["hash_chain_continuity_valid"],
                "chain_check": audit.json()["chain_check"],
                "correct_review_actions": corrections,
                "total_review_actions": len(reviews),
            },
            "api_observations": {
                "health": client.get("/api/health").json(),
                "verification_status_categories": client.get(
                    f"/api/projects/{project_id}/verification/summary", headers=manager
                ).json()["status_categories"],
            },
        }


def test_suite_metrics() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout.strip() + result.stderr.strip()
    first_line = output.splitlines()[0] if output else ""
    dot_match = re.match(r"^([.F]+)", first_line)
    passed = dot_match.group(1).count(".") if dot_match else 0
    failed = dot_match.group(1).count("F") if dot_match else 0
    return {
        "command": ".venv/bin/python -m pytest -q",
        "returncode": result.returncode,
        "passed": passed,
        "failed": failed,
        "output_tail": output[-500:],
    }


def build_report(results: dict[str, Any]) -> str:
    dbm = results["database_metrics"]
    apim = results["api_metrics"]
    tests = results["test_suite"]
    generated_at = results["generated_at"]
    lines = [
        "# KnowledgeBridge — measured evaluation report",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope and honesty statement",
        "",
        "This report contains **actual measurements** from a fresh disposable SQLite database seeded with the labelled synthetic Atlas Migration demonstration dataset. It is not a claim of production accuracy or worldwide novelty. The official attached PDF was not present in the workspace, so no PDF-specific findings were invented. No live LLM, GitHub, PostgreSQL, FAISS/ChromaDB or human-subject evaluation was performed.",
        "",
        "Reliability and retrieval values are explainable heuristics, **not statistically calibrated probabilities**. Gold labels are hand-authored expected annotations for the synthetic dataset, not measured outcomes.",
        "",
        "## Test suite",
        "",
        f"- Command: `{tests['command']}`",
        f"- Result: **{tests['passed']} passed, {tests['failed']} failed**, exit code {tests['returncode']}.",
        f"- Output tail: `{tests['output_tail']}`",
        "",
        "## Extraction and evidence",
        "",
        "| Metric | Measured value |",
        "| --- | ---: |",
        f"| Expected non-dependency labels | {dbm['extraction']['expected_labels']} |",
        f"| Actual non-dependency claims | {dbm['extraction']['actual_non_dependency_claims']} |",
        f"| Derived dependency claims | {dbm['extraction']['derived_dependency_claims']} |",
        f"| Extraction label precision | {dbm['extraction']['precision']:.4f} |",
        f"| Extraction label recall | {dbm['extraction']['recall']:.4f} |",
        f"| Extraction label F1 | {dbm['extraction']['f1']:.4f} |",
        f"| Evidence spans | {dbm['evidence']['spans']} |",
        f"| Exact character-offset matches | {dbm['evidence']['exact_offset_matches']} |",
        f"| Exact evidence-offset accuracy | {dbm['evidence']['exact_offset_accuracy']:.4f} |",
        f"| Active claims | {dbm['evidence']['active_claims']} |",
        f"| Claims with evidence links | {dbm['evidence']['claims_with_evidence_links']} |",
        "",
        "Extraction precision uses active non-dependency claims because dependency claims are deterministically derived from `depends_on` fields and are evaluated separately below.",
        "",
        f"Restricted-query note: {dbm['retrieval']['restricted_query_note']} Returned source refs: `{json.dumps(dbm['retrieval']['restricted_query_returned_source_refs'])}`.",
        "",
        "## Retrieval, verification and graph",
        "",
        "| Metric | Measured value |",
        "| --- | ---: |",
        f"| Retrieval queries | {dbm['retrieval']['queries']} |",
        f"| Mean precision@5 | {dbm['retrieval']['mean_precision_at_5']:.4f} |",
        f"| Mean recall@5 | {dbm['retrieval']['mean_recall_at_5']:.4f} |",
        f"| Restricted-query authorised documents returned to engineer | {dbm['retrieval']['restricted_query_docs_returned_to_engineer']} (marker hits: {len(dbm['retrieval']['restricted_query_marker_hits'])}) |",
        f"| Conflict precision / recall / F1 | {dbm['conflict_detection']['precision']:.4f} / {dbm['conflict_detection']['recall']:.4f} / {dbm['conflict_detection']['f1']:.4f} |",
        f"| Outdated precision / recall / F1 | {dbm['outdated_detection']['precision']:.4f} / {dbm['outdated_detection']['recall']:.4f} / {dbm['outdated_detection']['f1']:.4f} |",
        f"| Unsupported precision / recall / F1 | {dbm['unsupported_detection']['precision']:.4f} / {dbm['unsupported_detection']['recall']:.4f} / {dbm['unsupported_detection']['f1']:.4f} |",
        f"| Unsupported claim rate | {dbm['unsupported_detection']['unsupported_claim_rate']:.4f} |",
        f"| Dependency-pair F1 | {dbm['graph']['dependency_pair_metrics']['f1']:.4f} |",
        f"| Graph nodes / edges | {dbm['graph']['nodes']} / {dbm['graph']['edges']} |",
        f"| `depends_on` edges | {dbm['graph']['depends_on_edges']} |",
        f"| Representative gold-edge recall | {dbm['graph']['representative_gold_edge_recall']:.4f} |",
        f"| Restricted nodes / edges in graph | {dbm['graph']['restricted_nodes']} / {dbm['graph']['restricted_edges']} |",
        f"| Score disclaimer on every claim | {dbm['score_disclaimer_present_on_all_claims']} |",
        "",
        f"Verification status counts: `{json.dumps(dbm['verification_status_counts'], sort_keys=True)}`.",
        "",
        f"Graph relationship counts: `{json.dumps(dbm['graph']['relation_counts'], sort_keys=True)}`.",
        "",
        "The representative gold edge set is a 12-edge subset used as a regression check; `all_edge_exact_match_rate` is reported in JSON but is **not** a precision estimate because the gold set is not exhaustive.",
        "",
        "## Handover quality and continuation",
        "",
        "| Metric | Measured value |",
        "| --- | ---: |",
        f"| Required sections present | {apim['handover_quality']['sections_present']}/{apim['handover_quality']['required_sections']} ({apim['handover_quality']['section_coverage']:.4f}) |",
        f"| Statement items with evidence | {apim['handover_quality']['statement_items_with_evidence']}/{apim['handover_quality']['statement_items_examined']} ({apim['handover_quality']['evidence_link_rate']:.4f}) |",
        f"| Evidence register entries | {apim['handover_quality']['evidence_register_entries']} |",
        f"| Next actions / checklist items | {apim['handover_quality']['next_action_count']} / {apim['handover_quality']['checklist_count']} |",
        f"| Recommendation precision / recall / F1 | {apim['recommendation_relevance']['precision']:.4f} / {apim['recommendation_relevance']['recall']:.4f} / {apim['recommendation_relevance']['f1']:.4f} |",
        f"| Exact priority-order match | {apim['recommendation_relevance']['exact_order_match']} |",
        f"| Acknowledgement rate after workflow | {apim['continuity']['acknowledgement_rate']:.4f} |",
        f"| Completion rate after workflow | {apim['continuity']['completion_rate']:.4f} |",
        f"| Handover preparation time (average / maximum) | {apim['continuity']['handover_prep_seconds']['average']}s / {apim['continuity']['handover_prep_seconds']['maximum']}s |",
        f"| Human correction rate | {apim['continuity']['human_correction_rate']:.4f} ({apim['continuity']['corrections']}/{apim['continuity']['reviews_total']} automated review events) |",
        f"| Incoming-member task understanding | **Not measured** — {apim['continuity']['incoming_member_task_understanding'].get('note', 'requires a human study')} |",
        "",
        "Handover preparation time is elapsed wall-clock seconds from the first source ingestion timestamp to generation in this automated run. It is **not** a measured reduction in human preparation time. Human correction rate is computed from recorded review events and is not a human-factors study.",
        "",
        "## Permission enforcement",
        "",
        "| Check | Measured value |",
        "| --- | ---: |",
        f"| Low-clearance channels tested | {apim['permission_enforcement']['channels_tested']} |",
        f"| Restricted marker leaks | {apim['permission_enforcement']['restricted_marker_leaks']} |",
        f"| Engineer hidden nodes / edges | {apim['permission_enforcement']['hidden_by_policy_engineer']['nodes']} / {apim['permission_enforcement']['hidden_by_policy_engineer']['edges']} |",
        f"| Analyst hidden nodes / edges | {apim['permission_enforcement']['hidden_by_policy_analyst']['nodes']} / {apim['permission_enforcement']['hidden_by_policy_analyst']['edges']} |",
        f"| Manager can see restricted graph | {apim['permission_enforcement']['manager_can_see_restricted_graph']} |",
        f"| Search query guard applied | {apim['permission_enforcement']['search_query_guard_applied']} |",
        f"| Ask question guard applied | {apim['permission_enforcement']['ask_question_guard_applied']} |",
        f"| Permission-guard audit events | {apim['permission_enforcement']['permission_guard_audit_events']} |",
        f"| Denied audit events | {apim['permission_enforcement']['denied_audit_events']} |",
        f"| Engineer approve attempt status | {apim['permission_enforcement']['engineer_approve_status']} |",
        f"| External project access status | {apim['permission_enforcement']['external_project_access_status']} |",
        f"| Audit hash-chain continuity valid | {apim['permission_enforcement']['hash_chain_continuity_valid']} |",
        "",
        f"Per-channel restricted-marker hits: `{json.dumps(apim['permission_enforcement']['channel_leaks'], sort_keys=True)}`.",
        "",
        "## What is not measured",
        "",
        "- Incoming-member task understanding: requires a human-subject study.",
        "- Real reduction in handover preparation time: requires comparison against a manual baseline.",
        "- Neural/LLM extraction accuracy: no live LLM was configured; deterministic extraction was measured.",
        "- PostgreSQL, FAISS/ChromaDB, live GitHub and cloud deployment behaviour: not exercised in this evaluation.",
        "- Production security/penetration testing: automated policy checks only.",
        "- PDF analysis: the official attached PDF was not present in the workspace.",
        "",
        "Separate runtime smoke checks are documented in `reports/OPTIONAL_INTEGRATIONS.md`",
        "(local mock GitHub/LLM adapters, 0 external API calls) and",
        "`reports/UI_ROUTE_CHECK.md` / `reports/ui_route_check.json` (17 UI routes,",
        "0 runtime errors/failed API responses). They are implementation checks and",
        "do not change the measured metrics above; no live external service was evaluated.",
        "",
        "## Reproduce",
        "",
        "```bash",
        ".venv/bin/python -m pytest -q",
        ".venv/bin/python reports/generate_evaluation.py",
        "```",
        "",
        "Machine-readable results: `reports/evaluation.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ids = bootstrap()
    db = SessionLocal()
    try:
        database = database_metrics(db, ids)
    finally:
        db.close()
    api = api_metrics(ids)
    tests = test_suite_metrics()
    results = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dataset": GOLD["description"],
        "test_suite": tests,
        "database_metrics": database,
        "api_metrics": api,
    }
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation.json").write_text(
        json.dumps(json_safe(results), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "EVALUATION_REPORT.md").write_text(build_report(results), encoding="utf-8")
    print("evaluation written:", out_dir / "EVALUATION_REPORT.md")
    print("test result:", tests["passed"], "passed,", tests["failed"], "failed")
    print("permission leaks:", api["permission_enforcement"]["restricted_marker_leaks"])
    shutil.rmtree(EVAL_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
