"""Role-aware adaptive handover and continuation engine.

Access control is applied in the SQL query BEFORE any summary is assembled.
Additional role scope, hidden-dependency checks and a restricted-phrase guard
prevent inference through relationships, exports or generated prose.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import utcnow
from backend.app.models import (
    Claim,
    Handover,
    HandoverItem,
    Project,
    ProjectMember,
    Risk,
    SourceDocument,
    Task,
    User,
)
from backend.app.services.permissions import (
    evidence_citations,
    member_allowed_tags,
    member_claim_types,
    redact_forbidden_text,
    role_policy,
    sensitivity_label,
    visible_claim_query,
    visible_risk_query,
    visible_task_query,
)
from backend.app.utils import json_safe


def _role_visible(claim: Claim, role: str) -> bool:
    scopes = claim.role_scope or []
    return not scopes or "*" in scopes or role in scopes


def _claim_payload(db: Session, claim: Claim, member: ProjectMember) -> dict[str, Any] | None:
    text = " ".join([claim.statement, claim.value, claim.rationale, " ".join(claim.tags or [])])
    _, changed = redact_forbidden_text(db, claim.project_id, member.max_clearance, text)
    if changed:
        return None
    citations = evidence_citations(db, claim.id, member)
    if not citations:
        return None
    return {
        "claim_id": claim.id,
        "external_ref": claim.external_ref,
        "claim_type": claim.claim_type,
        "statement": claim.statement,
        "rationale": claim.rationale,
        "owner": claim.owner,
        "status": claim.status_label,
        "priority": claim.priority,
        "due_date": claim.due_date,
        "verification_status": claim.verification_status,
        "reliability_score": claim.reliability_score,
        "score_note": "Heuristic reliability score, not a calibrated probability.",
        "sensitivity": sensitivity_label(claim.sensitivity),
        "evidence": citations,
    }


def _guard_content(db: Session, project_id: str, clearance: int, content: dict[str, Any]) -> None:
    serialized = json.dumps(json_safe(content), ensure_ascii=False)
    _, changed = redact_forbidden_text(db, project_id, clearance, serialized)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permission guard blocked a handover containing an unauthorised phrase. Generation was aborted.",
        )


def generate_handover(
    db: Session,
    project_id: str,
    recipient_user_id: str,
    manager_id: str,
    title: str | None = None,
    role_key: str | None = None,
) -> Handover:
    project = db.get(Project, project_id)
    recipient = db.get(User, recipient_user_id)
    if project is None or recipient is None or recipient.organization_id != project.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient or project not found")
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == recipient_user_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient has no project role")
    if role_key and role_key != member.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role_key must match the recipient's assigned project role; clearance is never overridden",
        )

    policy = role_policy(member.role)
    clearance = member.max_clearance
    allowed_types = member_claim_types(member)
    allowed_tags = member_allowed_tags(member)

    # The same pre-retrieval ABAC query used by claims, search, graph and RAG is
    # the source of truth. Review/verification and role scope are additional
    # handover-specific gates applied before any content is assembled.
    authorized_claims = visible_claim_query(db, project_id, member).all()
    authorized_claim_ids = {claim.id for claim in authorized_claims}
    claims = [
        claim for claim in authorized_claims
        if claim.review_status == "approved"
        and claim.verification_status == "Verified"
        and _role_visible(claim, member.role)
    ]
    visible_refs = {claim.external_ref for claim in claims}
    selected_claim_ids = {claim.id for claim in claims}

    # Every ref excluded by clearance, ABAC, verification, review or role scope
    # is treated as hidden; it is never mentioned in a checklist or dependency.
    hidden_refs = {
        claim.external_ref
        for claim in db.query(Claim).filter(
            Claim.project_id == project_id,
            Claim.is_active.is_(True),
        ).all()
        if claim.id not in selected_claim_ids
    }

    payload_by_id: dict[str, dict[str, Any]] = {}
    for claim in claims:
        payload = _claim_payload(db, claim, member)
        if payload:
            payload_by_id[claim.id] = payload

    tasks = (
        visible_task_query(db, project_id, member)
        .filter(Task.status != "done")
        .order_by(Task.priority.asc(), Task.due_date.asc(), Task.external_ref.asc())
        .all()
    )
    visible_tasks: list[dict[str, Any]] = []
    for task in tasks:
        if task.claim_id and task.claim_id not in authorized_claim_ids:
            continue
        if task.external_ref in hidden_refs:
            continue
        deps = [dep for dep in (task.depends_on or []) if dep in visible_refs and dep not in hidden_refs]
        if any(dep not in visible_refs or dep in hidden_refs for dep in (task.depends_on or [])):
            continue
        _, changed = redact_forbidden_text(db, project_id, clearance, task.title)
        if changed:
            continue
        linked_claim = db.get(Claim, task.claim_id) if task.claim_id else None
        payload = payload_by_id.get(linked_claim.id) if linked_claim else None
        visible_tasks.append({
            "task_id": task.id,
            "external_ref": task.external_ref,
            "title": task.title,
            "owner": task.owner,
            "status": task.status,
            "priority": task.priority,
            "due_date": task.due_date,
            "dependencies": deps,
            "evidence": payload["evidence"] if payload else [],
        })

    risks = (
        visible_risk_query(db, project_id, member)
        .filter(Risk.status != "closed")
        .order_by(Risk.source_timestamp.desc())
        .all()
    )
    visible_risks = []
    for risk in risks:
        if risk.claim_id and risk.claim_id not in authorized_claim_ids:
            continue
        if risk.external_ref in hidden_refs:
            continue
        _, changed = redact_forbidden_text(db, project_id, clearance, " ".join([risk.title, risk.description, risk.mitigation]))
        if changed:
            continue
        linked_payload = payload_by_id.get(risk.claim_id) if risk.claim_id else None
        visible_risks.append({
            "risk_id": risk.id,
            "external_ref": risk.external_ref,
            "title": risk.title,
            "severity": risk.severity,
            "status": risk.status,
            "owner": risk.owner,
            "mitigation": risk.mitigation,
            "evidence": linked_payload["evidence"] if linked_payload else [],
        })

    def by_priority(claim_type: str, limit: int) -> list[dict[str, Any]]:
        selected = [p for p in payload_by_id.values() if p["claim_type"] == claim_type]
        selected.sort(key=lambda p: (p["priority"], p["external_ref"]))
        return selected[:limit]

    def by_recent(claim_type: str, limit: int) -> list[dict[str, Any]]:
        selected = [p for p in payload_by_id.values() if p["claim_type"] == claim_type]
        selected.sort(key=lambda p: p["external_ref"], reverse=True)
        return selected[:limit]

    next_actions = [p for p in payload_by_id.values() if p["claim_type"] == "next_action"]
    next_actions.sort(key=lambda p: (p["priority"], p["external_ref"]))
    next_actions = next_actions[:5]
    if len(next_actions) < 5:
        for task in visible_tasks:
            if len(next_actions) >= 5:
                break
            next_actions.append({
                "claim_id": None,
                "external_ref": task["external_ref"],
                "claim_type": "generated_next_action",
                "statement": f"Continue {task['external_ref']}: {task['title']}",
                "rationale": "Generated from an authorised high-priority unfinished task.",
                "priority": task["priority"],
                "due_date": task["due_date"],
                "evidence": task["evidence"],
            })

    checklist: list[dict[str, Any]] = []
    for action in next_actions:
        checklist.append({
            "title": action.get("statement") or action.get("value", ""),
            "item_type": "next_action",
            "priority": action["priority"],
            "claim_id": action.get("claim_id"),
            "task_id": None,
            "due_date": action.get("due_date"),
            "sensitivity": clearance,
        })
    for task in visible_tasks[:5]:
        checklist.append({
            "title": f"{task['external_ref']}: {task['title']}",
            "item_type": "task",
            "priority": task["priority"],
            "claim_id": None,
            "task_id": task["task_id"],
            "due_date": task["due_date"],
            "sensitivity": clearance,
        })
    for decision in by_priority("decision", 3):
        checklist.append({
            "title": f"Review decision {decision['external_ref']}",
            "item_type": "decision_acknowledgement",
            "priority": max(3, decision["priority"]),
            "claim_id": decision["claim_id"],
            "task_id": None,
            "due_date": None,
            "sensitivity": clearance,
        })
    for question in by_priority("unresolved_question", 2):
        checklist.append({
            "title": f"Resolve open question {question['external_ref']}",
            "item_type": "question_acknowledgement",
            "priority": max(3, question["priority"]),
            "claim_id": question["claim_id"],
            "task_id": None,
            "due_date": None,
            "sensitivity": clearance,
        })

    all_evidence: dict[str, dict[str, Any]] = {}
    for payload in payload_by_id.values():
        for citation in payload["evidence"]:
            all_evidence[citation["evidence_id"]] = citation

    earliest_source = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == project_id, SourceDocument.is_active.is_(True))
        .order_by(SourceDocument.ingested_at.asc())
        .first()
    )
    now = utcnow()
    prep_seconds = 0
    if earliest_source and earliest_source.ingested_at:
        prep_seconds = max(0, int((now - earliest_source.ingested_at).total_seconds()))

    content_json: dict[str, Any] = {
        "current_state": by_recent("state_change", 6),
        "responsibilities": visible_tasks[:8],
        "key_decisions": by_priority("decision", 8),
        "risks_and_dependencies": {
            "risks": visible_risks[:8],
            "dependency_claims": by_priority("dependency", 8),
            "blockers": by_priority("blocker", 6),
        },
        "open_questions": by_priority("unresolved_question", 6),
        "next_actions": next_actions,
        "checklist": checklist,
        "evidence": list(all_evidence.values()),
        "uncertainty": {
            "excluded_by_clearance": "Objects above the recipient's clearance were not retrieved.",
            "excluded_by_status": "Conflicting, unsupported and outdated claims were excluded.",
            "unresolved_questions": [q["external_ref"] for q in by_priority("unresolved_question", 6)],
            "missing_evidence": "Claims without linked evidence are not included.",
        },
        "metadata": {
            "project_id": project_id,
            "recipient_role": member.role,
            "recipient_role_label": policy["label"],
            "clearance": sensitivity_label(clearance),
            "clearance_level": clearance,
            "generated_from_claim_ids": sorted(payload_by_id.keys()),
            "demo_data": bool(project.is_demo),
            "score_note": "Reliability scores are explainable heuristics, not calibrated probabilities.",
            "permission_boundary": "SQL clearance, persisted claim-type and tag filters were applied before generation.",
        },
    }
    _guard_content(db, project_id, clearance, content_json)

    handover = Handover(
        project_id=project_id,
        recipient_user_id=recipient_user_id,
        recipient_role=member.role,
        title=title or f"{policy['label']} handover — {project.name}",
        status="draft",
        version=1,
        generated_by=manager_id,
        generated_at=now,
        content_json=content_json,
        sensitivity=clearance,
        clearance_applied=clearance,
        applied_filters={
            "max_clearance": clearance,
            "claim_types": allowed_types,
            "allowed_tags": allowed_tags,
            "role_scope": member.role,
            "review_status": "approved",
            "verification_status": "Verified",
        },
        prep_seconds=prep_seconds,
    )
    db.add(handover)
    db.flush()

    items: list[HandoverItem] = []
    for index, entry in enumerate(checklist):
        item = HandoverItem(
            handover_id=handover.id,
            claim_id=entry.get("claim_id"),
            task_id=entry.get("task_id"),
            title=entry["title"],
            item_type=entry["item_type"],
            priority=entry["priority"],
            status="pending",
            sensitivity=clearance,
            due_date=entry.get("due_date"),
        )
        db.add(item)
        db.flush()
        entry["item_id"] = item.id
        items.append(item)
    handover.content_json = {**content_json, "checklist": checklist}
    _guard_content(db, project_id, clearance, handover.content_json)
    db.flush()
    return handover


def serialize_handover(db: Session, handover: Handover, member: ProjectMember) -> dict[str, Any]:
    serialized = json.dumps(json_safe(handover.content_json), ensure_ascii=False)
    redacted, changed = redact_forbidden_text(db, handover.project_id, member.max_clearance, serialized)
    if changed:
        try:
            content = json.loads(redacted)
        except json.JSONDecodeError:
            content = {"error": "A permission guard redacted generated content before display."}
    else:
        content = handover.content_json
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
        "applied_filters": handover.applied_filters,
        "prep_seconds": handover.prep_seconds,
        "content": content,
        "leakage_guard_applied": changed,
    }


def export_markdown(db: Session, handover: Handover, member: ProjectMember) -> str:
    data = serialize_handover(db, handover, member)
    content = data["content"]
    lines = [
        f"# {handover.title}",
        "",
        f"Status: **{handover.status}**  |  Role: **{handover.recipient_role}**  |  Clearance: **{data['clearance']}**",
        "",
        "> Demonstration data. Every statement below is generated from authorised, approved evidence.",
        "",
        "## Next five actions",
    ]
    for index, action in enumerate(content.get("next_actions", [])[:5], start=1):
        lines.append(f"{index}. {action.get('statement')}")
        for citation in action.get("evidence", [])[:1]:
            lines.append(f"   - Evidence: {citation['source_title']} — “{citation['quote']}”")
    lines.extend(["", "## Responsibilities and outstanding work"])
    for task in content.get("responsibilities", []):
        lines.append(f"- **{task['external_ref']}** — {task['title']} ({task['status']}, priority {task['priority']})")
    lines.extend(["", "## Key decisions"])
    for decision in content.get("key_decisions", []):
        lines.append(f"- **{decision['external_ref']}** — {decision['statement']}")
        if decision.get("rationale"):
            lines.append(f"  - Why: {decision['rationale']}")
    lines.extend(["", "## Open questions and uncertainty"])
    for question in content.get("open_questions", []):
        lines.append(f"- {question['statement']}")
    lines.extend(["", "## Evidence register"])
    for citation in content.get("evidence", []):
        lines.append(
            f"- `{citation['source_ref'] if 'source_ref' in citation else citation['source_id']}` "
            f"{citation['source_title']} [{citation['start_char']}:{citation['end_char']}] — “{citation['quote']}”"
        )
    text = "\n".join(lines)
    redacted, _ = redact_forbidden_text(db, handover.project_id, member.max_clearance, text)
    return redacted


def update_item(db: Session, item: HandoverItem, action: str, actor_id: str, note: str = "") -> dict[str, Any]:
    handover = db.get(Handover, item.handover_id)
    if handover is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found")
    now = utcnow()
    if action == "acknowledge":
        item.acknowledged_at = item.acknowledged_at or now
        item.acknowledged_by = item.acknowledged_by or actor_id
        if item.status == "pending":
            item.status = "acknowledged"
    elif action == "start":
        item.acknowledged_at = item.acknowledged_at or now
        item.acknowledged_by = item.acknowledged_by or actor_id
        item.status = "in_progress"
    elif action == "complete":
        item.acknowledged_at = item.acknowledged_at or now
        item.acknowledged_by = item.acknowledged_by or actor_id
        item.status = "completed"
        item.completed_at = item.completed_at or now
        if item.task_id:
            task = db.get(Task, item.task_id)
            if task:
                task.status = "done"
                task.continuation_status = "completed"
                task.completed_at = task.completed_at or now
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown item action")
    if note:
        item.notes = note

    items = db.query(HandoverItem).filter(HandoverItem.handover_id == handover.id).all()
    if all(i.status == "completed" for i in items):
        handover.status = "completed"
    elif all(i.acknowledged_at is not None for i in items):
        handover.status = "acknowledged"
    elif item.status in {"in_progress", "completed"}:
        handover.status = "in_progress"
    db.flush()
    return {"item_id": item.id, "status": item.status, "handover_status": handover.status}
