"""Unit tests for verification rules, graph classification and RBAC."""
from __future__ import annotations

import json

import pytest

from backend.app.config import SAMPLE_DATA_DIR
from backend.app.models import Claim, ConflictRecord, KnowledgeEdge, KnowledgeNode, ProjectMember, SourceDocument, User
from backend.app.services.permissions import has_action, redact_forbidden_text, visible_claim_query, visible_source_query

pytestmark = pytest.mark.unit


def _member(db, email: str) -> ProjectMember:
    user = db.query(User).filter(User.email == email).first()
    return db.query(ProjectMember).filter(ProjectMember.user_id == user.id).first()


def test_explicit_supersession_and_unsupported_claim_are_detected(db, seeded_ids):
    project_id = seeded_ids["project_id"]
    outdated_refs = {
        c.external_ref
        for c in db.query(Claim).filter(
            Claim.project_id == project_id,
            Claim.is_active.is_(True),
            Claim.verification_status == "Outdated",
        ).all()
    }
    assert {"DEC-001", "RISK-002"} <= outdated_refs
    unsupported = db.query(Claim).filter(
        Claim.project_id == project_id,
        Claim.is_active.is_(True),
        Claim.external_ref == "F-301",
    ).first()
    assert unsupported is not None
    assert unsupported.verification_status == "Unsupported"
    assert unsupported.reliability_score >= 0
    assert any("not a calibrated probability" in line for line in unsupported.score_rationale)


def test_deliberate_conflict_keys_are_recorded_with_both_values(db, seeded_ids):
    gold = json.loads((SAMPLE_DATA_DIR / "gold_labels.json").read_text())
    records = db.query(ConflictRecord).filter(ConflictRecord.project_id == seeded_ids["project_id"]).all()
    keys = {record.normalized_key for record in records}
    assert set(gold["conflict_keys"]) <= keys
    for key in gold["conflict_keys"]:
        record = next(r for r in records if r.normalized_key == key)
        assert record.value_a != record.value_b
        assert record.rationale
        assert record.status in {"open", "resolved"}


def test_restricted_graph_relationship_is_classified_restricted(db, seeded_ids):
    project_id = seeded_ids["project_id"]
    source_node = db.query(KnowledgeNode).filter(KnowledgeNode.node_key == "task:KB-112").first()
    target_node = db.query(KnowledgeNode).filter(KnowledgeNode.node_key == "decision:DEC-900").first()
    assert source_node and target_node
    assert target_node.sensitivity == 3
    edge = db.query(KnowledgeEdge).filter(
        KnowledgeEdge.source_node_id == source_node.id,
        KnowledgeEdge.target_node_id == target_node.id,
        KnowledgeEdge.relation == "depends_on",
    ).first()
    assert edge is not None
    assert edge.sensitivity == 3


def test_permission_query_filters_restricted_claims_and_sources(db, seeded_ids):
    engineer = _member(db, "engineer@knowledgebridge.demo")
    analyst = _member(db, "analyst@knowledgebridge.demo")
    manager = _member(db, "manager@knowledgebridge.demo")
    assert engineer.max_clearance == 1 and analyst.max_clearance == 0 and manager.max_clearance == 3

    engineer_claims = {c.external_ref for c in visible_claim_query(db, seeded_ids["project_id"], engineer).all()}
    assert "F-900" not in engineer_claims
    assert "DEC-900" not in engineer_claims
    assert "KB-900" not in engineer_claims
    assert "KB-104" in engineer_claims

    analyst_sources = {s.metadata_json.get("source_ref") for s in visible_source_query(db, seeded_ids["project_id"], analyst).all()}
    assert "SRC-009" not in analyst_sources
    assert "SRC-008" in analyst_sources

    manager_sources = {s.metadata_json.get("source_ref") for s in visible_source_query(db, seeded_ids["project_id"], manager).all()}
    assert "SRC-009" in manager_sources


def test_restricted_phrase_guard_and_role_actions(db, seeded_ids):
    engineer = _member(db, "engineer@knowledgebridge.demo")
    manager = _member(db, "manager@knowledgebridge.demo")
    redacted, changed = redact_forbidden_text(
        db,
        seeded_ids["project_id"],
        engineer.max_clearance,
        "The demo signing key path is RESTRICTED-CANARY-9F3A.",
    )
    assert changed is True
    assert "RESTRICTED-CANARY-9F3A" not in redacted
    assert "[redacted]" in redacted
    assert has_action(manager, "review.approve") is True
    assert has_action(engineer, "review.approve") is False
    assert has_action(engineer, "handover.acknowledge") is True
    # Keep this explicit for readability: the source must exist for the guard to have something to protect.
    restricted_source = next(
        s for s in db.query(SourceDocument).filter(SourceDocument.project_id == seeded_ids["project_id"]).all()
        if s.metadata_json.get("source_ref") == "SRC-009"
    )
    assert restricted_source.sensitivity == 3
