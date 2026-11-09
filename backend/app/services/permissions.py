"""Central RBAC/ABAC policy and tamper-evident audit helpers.

Security boundary:
1. the user must be an active member of the project;
2. the action must be allowed for that project role;
3. every retrieved object must satisfy the member's classification clearance;
4. handovers are additionally scoped to their recipient;
5. all generated text is passed through a server-side restricted-phrase guard.

Scores and tags are relevance signals, never substitutes for clearance.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models import (
    AuditLog,
    Claim,
    ClaimEvidence,
    ConflictRecord,
    EvidenceSpan,
    Handover,
    HandoverItem,
    KnowledgeEdge,
    KnowledgeNode,
    Project,
    ProjectMember,
    Risk,
    SourceDocument,
    Task,
    User,
)
from ..utils import canonical, json_safe, new_id

SENSITIVITY_LABELS = {0: "public", 1: "internal", 2: "confidential", 3: "restricted"}
SENSITIVITY_BY_NAME = {v: k for k, v in SENSITIVITY_LABELS.items()}

CLAIM_TYPES = [
    "decision",
    "task",
    "owner",
    "risk",
    "blocker",
    "dependency",
    "unfinished_work",
    "unresolved_question",
    "contact",
    "next_action",
    "state_change",
]

STATUS_CATEGORIES = ["Verified", "Needs Review", "Conflicting", "Unsupported", "Outdated"]

ROLE_POLICIES: dict[str, dict[str, Any]] = {
    "project_manager": {
        "label": "Project Manager",
        "clearance": 3,
        "actions": ["*"],
        "claim_types": ["*"],
        "tags": ["*"],
        "description": "Creates projects, integrates sources, resolves conflicts, approves knowledge and shares handovers.",
    },
    "tech_lead": {
        "label": "Technical Lead",
        "clearance": 2,
        "actions": [
            "project.view", "source.view", "source.ingest", "source.connect",
            "knowledge.view", "knowledge.extract", "graph.view", "verification.view",
            "verification.run", "review.approve", "review.correct", "risk.manage",
            "task.update", "handover.view", "search", "ask", "export",
        ],
        "claim_types": ["*"],
        "tags": ["*"],
        "description": "Reviews technical evidence and manages risks without member administration.",
    },
    "incoming_engineer": {
        "label": "Incoming Engineer",
        "clearance": 1,
        "actions": [
            "project.view", "source.view", "knowledge.view", "graph.view",
            "verification.view", "handover.view", "handover.acknowledge",
            "task.update", "search", "ask", "export",
        ],
        "claim_types": CLAIM_TYPES,
        "tags": ["backend", "api", "deployment", "testing", "integration", "general"],
        "description": "Receives an internal-clearance engineering handover and continuation checklist.",
    },
    "incoming_analyst": {
        "label": "Incoming Analyst",
        "clearance": 0,
        "actions": [
            "project.view", "source.view", "knowledge.view", "graph.view",
            "handover.view", "handover.acknowledge", "search", "ask", "export",
        ],
        "claim_types": ["decision", "task", "risk", "unresolved_question", "next_action", "state_change"],
        "tags": ["public", "analytics", "general"],
        "description": "Receives a public-clearance, summary-oriented handover.",
    },
    "auditor": {
        "label": "Auditor",
        "clearance": 2,
        "actions": [
            "project.view", "source.view", "knowledge.view", "verification.view",
            "handover.view", "audit.view", "search", "export",
        ],
        "claim_types": ["*"],
        "tags": ["*"],
        "description": "Reads verification and audit history but cannot modify project knowledge.",
    },
    "observer": {
        "label": "Observer",
        "clearance": 0,
        "actions": ["project.view", "source.view", "knowledge.view", "graph.view", "search"],
        "claim_types": ["decision", "task", "risk", "unresolved_question"],
        "tags": ["public", "general"],
        "description": "Read-only access to public project knowledge.",
    },
}


def role_policy(role: str) -> dict[str, Any]:
    return ROLE_POLICIES.get(role, ROLE_POLICIES["observer"])


def member_claim_types(member: ProjectMember) -> list[str]:
    """Return persisted per-member claim-type overrides, falling back to role defaults."""
    policy = role_policy(member.role)
    configured = member.allowed_claim_types
    return list(configured) if configured is not None else list(policy["claim_types"])


def member_allowed_tags(member: ProjectMember) -> list[str]:
    """Return persisted per-member tag overrides, falling back to role defaults."""
    policy = role_policy(member.role)
    configured = member.allowed_tags
    return list(configured) if configured is not None else list(policy["tags"])


def claim_allowed(member: ProjectMember, claim: Claim) -> bool:
    """Post-retrieval ABAC check mirroring visible_claim_query's SQL filters."""
    if claim.sensitivity > member.max_clearance:
        return False
    types = member_claim_types(member)
    if types and "*" not in types and claim.claim_type not in types:
        return False
    tags = member_allowed_tags(member)
    if "*" not in tags:
        if not tags:
            return False
        claim_tags = claim.tags or []
        if claim_tags and not set(claim_tags).intersection(tags):
            return False
    return True


def claim_tags_allowed_query(query, member: ProjectMember):
    """Apply persisted ABAC tags to a Claim query before any results are fetched."""
    tags = member_allowed_tags(member)
    if "*" in tags:
        return query
    if not tags:
        return query.filter(False)
    conditions = [Claim.tags.is_(None), Claim.tags == []]
    for tag in tags:
        # JSON is stored as a canonical JSON array. A quoted substring match is
        # portable to the default SQLite deployment and PostgreSQL deployments.
        conditions.append(Claim.tags.like(f'%"{tag}"%'))
    return query.filter(or_(*conditions))


def sensitivity_value(value: str | int | None, default: int = 1) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return min(3, max(0, value))
    return SENSITIVITY_BY_NAME.get(str(value).strip().lower(), default)


def sensitivity_label(value: int) -> str:
    return SENSITIVITY_LABELS.get(int(value), "internal")


def has_action(member: ProjectMember, action: str) -> bool:
    actions = role_policy(member.role)["actions"]
    return "*" in actions or action in actions


def get_membership(db: Session, user: User, project_id: str) -> ProjectMember:
    project = db.get(Project, project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        .first()
    )
    if member is None:
        record_audit(
            db,
            user=user,
            project_id=project_id,
            action="project.access",
            resource_type="project",
            resource_id=project_id,
            outcome="denied",
            details={"reason": "no_project_membership"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return member


def require_action(db: Session, user: User, project_id: str, action: str) -> ProjectMember:
    member = get_membership(db, user, project_id)
    if not has_action(member, action):
        record_audit(
            db,
            user=user,
            project_id=project_id,
            action=action,
            resource_type="policy",
            outcome="denied",
            details={"role": member.role, "reason": "action_not_allowed"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Action not permitted for this role")
    return member


def require_project_manager(db: Session, user: User, project_id: str) -> ProjectMember:
    member = require_action(db, user, project_id, "member.manage")
    if member.role != "project_manager":
        record_audit(
            db,
            user=user,
            project_id=project_id,
            action="member.manage",
            resource_type="policy",
            outcome="denied",
            details={"role": member.role},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project manager role required")
    return member


def record_audit(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    actor_email: str | None = None,
    organization_id: str | None = None,
    project_id: str | None = None,
    resource_type: str = "",
    resource_id: str = "",
    outcome: str = "allowed",
    details: dict[str, Any] | None = None,
    commit: bool = False,
) -> AuditLog:
    previous = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = previous.event_hash if previous else ""
    created_at = utcnow()
    payload = {
        "nonce": new_id("evt"),
        "organization_id": organization_id or (user.organization_id if user else None),
        "project_id": project_id,
        "actor_id": user.id if user else None,
        "actor_email": actor_email or (user.email if user else "anonymous"),
        "action": action,
        "resource_type": resource_type,
        "resource_id": str(resource_id or ""),
        "outcome": outcome,
        "details": json_safe(details or {}),
        "created_at": created_at.isoformat() + "Z",
        "prev_hash": prev_hash,
    }
    event_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    entry = AuditLog(
        organization_id=payload["organization_id"],
        project_id=project_id,
        actor_id=payload["actor_id"],
        actor_email=payload["actor_email"],
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        outcome=outcome,
        details=payload["details"],
        prev_hash=prev_hash,
        event_hash=event_hash,
        created_at=created_at,
    )
    db.add(entry)
    db.flush()
    if commit:
        db.commit()
    return entry


def visible_claim_query(db: Session, project_id: str, member: ProjectMember):
    query = db.query(Claim).filter(
        Claim.project_id == project_id,
        Claim.is_active.is_(True),
        Claim.sensitivity <= member.max_clearance,
    )
    allowed = member_claim_types(member)
    if "*" not in allowed:
        if not allowed:
            return query.filter(False)
        query = query.filter(Claim.claim_type.in_(allowed))
    return claim_tags_allowed_query(query, member)


def visible_source_query(db: Session, project_id: str, member: ProjectMember):
    return db.query(SourceDocument).filter(
        SourceDocument.project_id == project_id,
        SourceDocument.is_active.is_(True),
        SourceDocument.sensitivity <= member.max_clearance,
    )


def _visible_claim_ids(db: Session, project_id: str, member: ProjectMember) -> set[str]:
    return {claim.id for claim in visible_claim_query(db, project_id, member).all()}


def visible_task_query(db: Session, project_id: str, member: ProjectMember):
    claim_ids = _visible_claim_ids(db, project_id, member)
    query = db.query(Task).filter(
        Task.project_id == project_id,
        Task.sensitivity <= member.max_clearance,
    )
    return query.filter(or_(Task.claim_id.is_(None), Task.claim_id.in_(claim_ids)))


def visible_risk_query(db: Session, project_id: str, member: ProjectMember):
    claim_ids = _visible_claim_ids(db, project_id, member)
    query = db.query(Risk).filter(
        Risk.project_id == project_id,
        Risk.sensitivity <= member.max_clearance,
    )
    return query.filter(or_(Risk.claim_id.is_(None), Risk.claim_id.in_(claim_ids)))


def visible_evidence_query(db: Session, project_id: str, member: ProjectMember):
    return (
        db.query(EvidenceSpan)
        .join(SourceDocument, EvidenceSpan.source_id == SourceDocument.id)
        .filter(
            SourceDocument.project_id == project_id,
            SourceDocument.is_active.is_(True),
            EvidenceSpan.sensitivity <= member.max_clearance,
            SourceDocument.sensitivity <= member.max_clearance,
        )
    )


def visible_node_query(db: Session, project_id: str, member: ProjectMember):
    claim_ids = _visible_claim_ids(db, project_id, member)
    return db.query(KnowledgeNode).filter(
        KnowledgeNode.project_id == project_id,
        KnowledgeNode.sensitivity <= member.max_clearance,
        or_(KnowledgeNode.claim_id.is_(None), KnowledgeNode.claim_id.in_(claim_ids)),
    )


def visible_edge_query(db: Session, project_id: str, member: ProjectMember, visible_node_ids: set[str] | None = None):
    claim_ids = _visible_claim_ids(db, project_id, member)
    query = db.query(KnowledgeEdge).filter(
        KnowledgeEdge.project_id == project_id,
        KnowledgeEdge.sensitivity <= member.max_clearance,
        or_(KnowledgeEdge.claim_id.is_(None), KnowledgeEdge.claim_id.in_(claim_ids)),
    )
    if visible_node_ids is not None:
        if not visible_node_ids:
            return query.filter(False)
        query = query.filter(
            KnowledgeEdge.source_node_id.in_(visible_node_ids),
            KnowledgeEdge.target_node_id.in_(visible_node_ids),
        )
    return query


def _restricted_phrases(db: Session, project_id: str, clearance: int) -> list[str]:
    phrases: set[str] = set()
    text_rows: list[str] = []
    for model, columns in (
        (SourceDocument, [SourceDocument.content, SourceDocument.title]),
        (Claim, [Claim.statement, Claim.value, Claim.rationale]),
        (Task, [Task.title]),
        (Risk, [Risk.title, Risk.description, Risk.mitigation]),
    ):
        rows = (
            db.query(*columns)
            .filter(model.project_id == project_id, model.sensitivity > clearance)
            .all()
        )
        for row in rows:
            for value in row:
                if isinstance(value, str) and value.strip():
                    text_rows.append(value)

    # Explicit identifiers of every object above the member's clearance. This
    # catches short references such as DEC-900 that the long-token heuristic
    # below would miss, including generated dependency labels.
    for model, column in (
        (Claim, Claim.external_ref),
        (Task, Task.external_ref),
        (Risk, Risk.external_ref),
    ):
        for (ref,) in (
            db.query(column)
            .filter(model.project_id == project_id, model.sensitivity > clearance)
            .distinct()
            .all()
        ):
            if isinstance(ref, str) and ref.strip():
                phrases.add(ref.strip())

    hidden_sources = (
        db.query(SourceDocument)
        .filter(
            SourceDocument.project_id == project_id,
            SourceDocument.sensitivity > clearance,
        )
        .all()
    )
    for source in hidden_sources:
        source_ref = source.metadata_json.get("source_ref") if source.metadata_json else None
        if isinstance(source_ref, str) and source_ref.strip():
            phrases.add(source_ref.strip())

    # Evidence spans inherit their parent source's project and classification.
    evidence_rows = (
        db.query(EvidenceSpan.quote)
        .join(SourceDocument, EvidenceSpan.source_id == SourceDocument.id)
        .filter(
            SourceDocument.project_id == project_id,
            EvidenceSpan.sensitivity > clearance,
        )
        .all()
    )
    for (quote,) in evidence_rows:
        if isinstance(quote, str) and quote.strip():
            text_rows.append(quote)

    for text in text_rows:
        for line in text.splitlines():
            line = re.sub(r"^[@#\-\s]+", "", line).strip()
            if len(line) >= 12:
                phrases.add(line)
        # Unique identifiers and explicit canaries are redacted even if paraphrased
        # around them; common short words are deliberately not included.
        for token in re.findall(r"\b[A-Z][A-Z0-9_-]{7,}\b", text):
            phrases.add(token)
    return sorted(phrases, key=len, reverse=True)


def redact_forbidden_text(
    db: Session, project_id: str, clearance: int, text: str
) -> tuple[str, bool]:
    """Defence-in-depth guard for generated/extracted free text.

    It removes exact restricted phrases, explicit hidden object identifiers and
    long uppercase identifiers; it does not replace query-level filtering,
    which remains the primary control.
    """
    redacted = text
    changed = False
    for phrase in _restricted_phrases(db, project_id, clearance):
        # Explicit refs such as F-900 are deliberately protected despite being
        # short; generic phrase lines are already filtered to >=12 characters.
        if len(phrase) < 4:
            continue
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(redacted):
            redacted = pattern.sub("[redacted]", redacted)
            changed = True
    return redacted, changed


def assert_clearance(member: ProjectMember, sensitivity: int) -> None:
    if int(sensitivity) > int(member.max_clearance):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requested classification exceeds the member's clearance",
        )


def serialize_claim_basic(claim: Claim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "external_ref": claim.external_ref,
        "claim_type": claim.claim_type,
        "statement": claim.statement,
        "normalized_key": claim.normalized_key,
        "value": claim.value,
        "subject": claim.subject,
        "owner": claim.owner,
        "status": claim.status_label,
        "verification_status": claim.verification_status,
        "review_status": claim.review_status,
        "reliability_score": claim.reliability_score,
        "score_rationale": claim.score_rationale,
        "sensitivity": sensitivity_label(claim.sensitivity),
        "sensitivity_level": claim.sensitivity,
        "tags": claim.tags,
        "role_scope": claim.role_scope,
        "depends_on": claim.depends_on,
        "due_date": claim.due_date,
        "source_timestamp": claim.source_timestamp.isoformat() + "Z" if claim.source_timestamp else None,
        "rationale": claim.rationale,
        "priority": claim.priority,
        "version": claim.version,
        "is_active": claim.is_active,
    }


def evidence_citations(db: Session, claim_id: str, member: ProjectMember) -> list[dict[str, Any]]:
    claim = db.get(Claim, claim_id)
    if claim is None or not claim_allowed(member, claim):
        return []
    rows = (
        db.query(ClaimEvidence, EvidenceSpan, SourceDocument)
        .join(EvidenceSpan, ClaimEvidence.evidence_span_id == EvidenceSpan.id)
        .join(SourceDocument, EvidenceSpan.source_id == SourceDocument.id)
        .filter(
            ClaimEvidence.claim_id == claim_id,
            EvidenceSpan.sensitivity <= member.max_clearance,
            SourceDocument.sensitivity <= member.max_clearance,
            SourceDocument.is_active.is_(True),
        )
        .all()
    )
    return [
        {
            "claim_evidence_id": link.id,
            "evidence_id": span.id,
            "relation": link.relation,
            "source_id": source.id,
            "source_ref": source.metadata_json.get("source_ref") or source.id,
            "source_title": source.title,
            "source_type": source.source_type,
            "external_ref": source.external_ref,
            "source_timestamp": source.source_timestamp.isoformat() + "Z" if source.source_timestamp else None,
            "quote": span.quote,
            "start_char": span.start_char,
            "end_char": span.end_char,
            "sensitivity": sensitivity_label(span.sensitivity),
        }
        for link, span, source in rows
    ]
