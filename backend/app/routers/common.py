"""Shared API serialisers and permission-aware response helpers."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import utcnow
from ..models import (
    AuditLog,
    Claim,
    ConflictRecord,
    EvidenceSpan,
    Handover,
    KnowledgeEdge,
    KnowledgeNode,
    Project,
    ProjectMember,
    Risk,
    SourceDocument,
    Task,
    User,
)
from ..security import create_access_token
from ..services.permissions import (
    ROLE_POLICIES,
    STATUS_CATEGORIES,
    SENSITIVITY_LABELS,
    claim_allowed,
    evidence_citations,
    redact_forbidden_text,
    record_audit,
    role_policy,
    serialize_claim_basic,
    sensitivity_label,
    visible_claim_query,
)
from ..utils import json_safe, parse_datetime


def auth_response(user: User) -> dict[str, Any]:
    return {
        "access_token": create_access_token(user.id, user.email, user.system_role),
        "token_type": "bearer",
        "user": user_dict(user),
    }


def user_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "system_role": user.system_role,
        "organization_id": user.organization_id,
        "is_active": user.is_active,
    }


def guard_text(
    db: Session,
    project_id: str,
    member: ProjectMember,
    user: User,
    text: str,
    channel: str,
) -> tuple[str, bool]:
    redacted, changed = redact_forbidden_text(db, project_id, member.max_clearance, text)
    if changed:
        record_audit(
            db,
            user=user,
            project_id=project_id,
            action="permission.guard",
            resource_type="text",
            outcome="blocked",
            details={"channel": channel, "reason": "restricted_phrase_removed"},
            commit=True,
        )
    return redacted, changed


def visible_refs(db: Session, project_id: str, member: ProjectMember) -> set[str]:
    return {c.external_ref for c in visible_claim_query(db, project_id, member).all()}


def source_dict(
    db: Session,
    source: SourceDocument,
    member: ProjectMember,
    user: User,
    *,
    include_content: bool = False,
) -> dict[str, Any] | None:
    if source.sensitivity > member.max_clearance or not source.is_active:
        return None
    data: dict[str, Any] = {
        "id": source.id,
        "source_ref": source.metadata_json.get("source_ref") or source.id,
        "title": source.title,
        "source_type": source.source_type,
        "external_ref": source.external_ref,
        "author": source.author,
        "source_timestamp": source.source_timestamp.isoformat() + "Z" if source.source_timestamp else None,
        "ingested_at": source.ingested_at.isoformat() + "Z" if source.ingested_at else None,
        "processed_at": source.processed_at.isoformat() + "Z" if source.processed_at else None,
        "sensitivity": sensitivity_label(source.sensitivity),
        "sensitivity_level": source.sensitivity,
        "is_demo": source.is_demo,
        "mime_type": source.mime_type,
        "byte_size": source.byte_size,
        "sha256": source.sha256,
    }
    preview, changed = guard_text(db, source.project_id, member, user, source.title, "source.title")
    if changed:
        return None
    data["title"] = preview
    if include_content:
        content, changed = guard_text(db, source.project_id, member, user, source.content, "source.content")
        data["content"] = content
        data["redacted"] = changed
    return data if _payload_allowed(db, source.project_id, member, user, data, "source.payload") else None


def claim_dict(db: Session, claim: Claim, member: ProjectMember, user: User) -> dict[str, Any] | None:
    if not claim_allowed(member, claim):
        return None
    data = serialize_claim_basic(claim)
    refs = visible_refs(db, claim.project_id, member)
    raw_dependencies = list(data.get("depends_on") or [])
    data["depends_on"] = [ref for ref in raw_dependencies if ref in refs]
    data["hidden_dependency_count"] = len([ref for ref in raw_dependencies if ref not in refs])
    data["supersedes"] = claim.supersedes_ref or None
    data["superseded_by"] = claim.metadata_json.get("superseded_by")
    data["superseded_at"] = claim.metadata_json.get("superseded_at")
    for key in ("supersedes", "superseded_by", "superseded_at"):
        if data[key] and data[key] not in refs:
            data[key] = None
    # Any hidden identifier embedded in a serialised field or citation causes
    # the whole claim to be omitted rather than partially redacted.
    _, changed = guard_text(db, claim.project_id, member, user, json.dumps(json_safe(data)), "claim.payload")
    if changed:
        return None
    citations = evidence_citations(db, claim.id, member)
    _, citations_changed = guard_text(db, claim.project_id, member, user, json.dumps(json_safe(citations)), "claim.evidence")
    if citations_changed:
        return None
    data["evidence"] = citations
    data["score_rationale"] = list(claim.score_rationale or [])
    return data


def _linked_claim_allowed(db: Session, claim_id: str | None, member: ProjectMember) -> bool:
    if not claim_id:
        return True
    claim = db.get(Claim, claim_id)
    return claim is None or claim_allowed(member, claim)


def _payload_allowed(
    db: Session,
    project_id: str,
    member: ProjectMember,
    user: User,
    payload: dict[str, Any],
    channel: str,
) -> bool:
    """Reject an entire object if any serialised field contains a hidden phrase."""
    _, changed = guard_text(
        db,
        project_id,
        member,
        user,
        json.dumps(json_safe(payload), ensure_ascii=False),
        channel,
    )
    return not changed


def task_dict(db: Session, task: Task, member: ProjectMember, user: User, allowed_refs: set[str] | None = None) -> dict[str, Any] | None:
    if task.sensitivity > member.max_clearance or not _linked_claim_allowed(db, task.claim_id, member):
        return None
    refs = allowed_refs if allowed_refs is not None else visible_refs(db, task.project_id, member)
    title, changed = guard_text(db, task.project_id, member, user, task.title, "task.title")
    if changed:
        return None
    payload = {
        "id": task.id,
        "external_ref": task.external_ref,
        "title": title,
        "owner": task.owner,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date,
        "dependencies": [dep for dep in (task.depends_on or []) if dep in refs],
        "hidden_dependency_count": len([dep for dep in (task.depends_on or []) if dep not in refs]),
        "tags": task.tags,
        "sensitivity": sensitivity_label(task.sensitivity),
        "continuation_status": task.continuation_status,
        "completed_at": task.completed_at.isoformat() + "Z" if task.completed_at else None,
    }
    return payload if _payload_allowed(db, task.project_id, member, user, payload, "task.payload") else None


def risk_dict(db: Session, risk: Risk, member: ProjectMember, user: User) -> dict[str, Any] | None:
    if risk.sensitivity > member.max_clearance or not _linked_claim_allowed(db, risk.claim_id, member):
        return None
    text = " ".join([risk.title, risk.description, risk.mitigation])
    _, changed = guard_text(db, risk.project_id, member, user, text, "risk.text")
    if changed:
        return None
    payload = {
        "id": risk.id,
        "external_ref": risk.external_ref,
        "title": risk.title,
        "description": risk.description,
        "severity": risk.severity,
        "likelihood": risk.likelihood,
        "owner": risk.owner,
        "status": risk.status,
        "mitigation": risk.mitigation,
        "sensitivity": sensitivity_label(risk.sensitivity),
        "source_timestamp": risk.source_timestamp.isoformat() + "Z" if risk.source_timestamp else None,
    }
    return payload if _payload_allowed(db, risk.project_id, member, user, payload, "risk.payload") else None


def node_dict(db: Session, node: KnowledgeNode, member: ProjectMember, user: User) -> dict[str, Any] | None:
    if node.sensitivity > member.max_clearance or not _linked_claim_allowed(db, node.claim_id, member):
        return None
    label, label_changed = guard_text(db, node.project_id, member, user, node.label, "graph.node.label")
    description, desc_changed = guard_text(db, node.project_id, member, user, node.description, "graph.node.description")
    if label_changed or desc_changed:
        return None
    payload = {
        "id": node.id,
        "node_key": node.node_key,
        "node_type": node.node_type,
        "label": label,
        "description": description,
        "sensitivity": sensitivity_label(node.sensitivity),
        "valid_from": node.valid_from.isoformat() + "Z" if node.valid_from else None,
        "valid_to": node.valid_to.isoformat() + "Z" if node.valid_to else None,
        "claim_id": node.claim_id,
        "source_id": node.source_id,
        "metadata": node.metadata_json,
    }
    return payload if _payload_allowed(db, node.project_id, member, user, payload, "graph.node.payload") else None


def edge_dict(db: Session, edge: KnowledgeEdge, member: ProjectMember, user: User) -> dict[str, Any] | None:
    if edge.sensitivity > member.max_clearance or not _linked_claim_allowed(db, edge.claim_id, member):
        return None
    label, changed = guard_text(db, edge.project_id, member, user, edge.label, "graph.edge.label")
    if changed:
        return None
    payload = {
        "id": edge.id,
        "source": edge.source_node_id,
        "target": edge.target_node_id,
        "relation": edge.relation,
        "label": label,
        "sensitivity": sensitivity_label(edge.sensitivity),
        "valid_from": edge.valid_from.isoformat() + "Z" if edge.valid_from else None,
        "valid_to": edge.valid_to.isoformat() + "Z" if edge.valid_to else None,
        "claim_id": edge.claim_id,
        "evidence_id": edge.evidence_span_id,
    }
    return payload if _payload_allowed(db, edge.project_id, member, user, payload, "graph.edge.payload") else None


def conflict_dict(db: Session, conflict: ConflictRecord, member: ProjectMember, user: User) -> dict[str, Any] | None:
    if conflict.sensitivity > member.max_clearance:
        return None
    for claim_id in (conflict.claim_a_id, conflict.claim_b_id):
        claim = db.get(Claim, claim_id) if claim_id else None
        if claim is not None and not claim_allowed(member, claim):
            return None
    text = " ".join([conflict.normalized_key, conflict.value_a, conflict.value_b, conflict.rationale])
    _, changed = guard_text(db, conflict.project_id, member, user, text, "conflict.text")
    if changed:
        return None
    payload = {
        "id": conflict.id,
        "normalized_key": conflict.normalized_key,
        "value_a": conflict.value_a,
        "value_b": conflict.value_b,
        "claim_a_id": conflict.claim_a_id,
        "claim_b_id": conflict.claim_b_id,
        "conflict_type": conflict.conflict_type,
        "rationale": conflict.rationale,
        "status": conflict.status,
        "resolution_claim_id": conflict.resolution_claim_id,
        "resolution_note": conflict.resolution_note,
        "detected_at": conflict.detected_at.isoformat() + "Z" if conflict.detected_at else None,
        "resolved_at": conflict.resolved_at.isoformat() + "Z" if conflict.resolved_at else None,
        "sensitivity": sensitivity_label(conflict.sensitivity),
    }
    return payload if _payload_allowed(db, conflict.project_id, member, user, payload, "conflict.payload") else None


def audit_dict(db: Session, entry: AuditLog, member: ProjectMember, user: User) -> dict[str, Any]:
    details_json = json.dumps(json_safe(entry.details), ensure_ascii=False)
    redacted, changed = guard_text(db, entry.project_id or "", member, user, details_json, "audit.details")
    if changed:
        details: Any = {"redacted": True}
    else:
        try:
            details = json.loads(redacted)
        except json.JSONDecodeError:
            details = entry.details
    return {
        "id": entry.id,
        "actor_email": entry.actor_email,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "outcome": entry.outcome,
        "details": details,
        "created_at": entry.created_at.isoformat() + "Z" if entry.created_at else None,
        "prev_hash": entry.prev_hash,
        "event_hash": entry.event_hash,
    }


def handover_basic(handover: Handover) -> dict[str, Any]:
    return {
        "id": handover.id,
        "project_id": handover.project_id,
        "recipient_user_id": handover.recipient_user_id,
        "recipient_role": handover.recipient_role,
        "title": handover.title,
        "status": handover.status,
        "version": handover.version,
        "generated_at": handover.generated_at.isoformat() + "Z" if handover.generated_at else None,
        "approved_at": handover.approved_at.isoformat() + "Z" if handover.approved_at else None,
        "shared_at": handover.shared_at.isoformat() + "Z" if handover.shared_at else None,
        "clearance": sensitivity_label(handover.clearance_applied),
        "clearance_level": handover.clearance_applied,
        "prep_seconds": handover.prep_seconds,
    }


def project_dict(db: Session, project: Project, member: ProjectMember | None = None) -> dict[str, Any]:
    return {
        "id": project.id,
        "organization_id": project.organization_id,
        "key": project.key,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_at": project.created_at.isoformat() + "Z" if project.created_at else None,
        "is_demo": project.is_demo,
        "role": member.role if member else None,
        "clearance": sensitivity_label(member.max_clearance) if member else None,
        "clearance_level": member.max_clearance if member else None,
    }


def parse_as_of(value: str | None) -> datetime:
    if not value:
        return utcnow()
    parsed = parse_datetime(value)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="as_of must be an ISO date or datetime")
    return parsed


def meta_payload(current_user: User | None = None) -> dict[str, Any]:
    return {
        "app_name": settings.app_name,
        "tagline": "Preserve Knowledge. Empower Continuity.",
        "environment": settings.environment,
        "demo_mode": settings.is_demo_mode,
        "demo_accounts": [
            {"email": "manager@knowledgebridge.demo", "role": "project_manager"},
            {"email": "lead@knowledgebridge.demo", "role": "tech_lead"},
            {"email": "engineer@knowledgebridge.demo", "role": "incoming_engineer"},
            {"email": "analyst@knowledgebridge.demo", "role": "incoming_analyst"},
            {"email": "auditor@knowledgebridge.demo", "role": "auditor"},
        ],
        "demo_password_hint": "Use DEMO_PASSWORD from .env.example, or the development-only demo login buttons.",
        "roles": ROLE_POLICIES,
        "sensitivity_labels": SENSITIVITY_LABELS,
        "verification_statuses": STATUS_CATEGORIES,
        "score_disclaimer": "Reliability scores are explainable heuristics, not statistically calibrated probabilities.",
        "optional_llm_configured": bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model),
        "github_token_configured": bool(settings.github_token),
        "authenticated": current_user is not None,
    }
