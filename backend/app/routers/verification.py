"""Verification, conflict, review, audit and continuity routes."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from knowledge_graph.builder import rebuild_graph
from verification_engine.engine import (
    approve_eligible_claims,
    resolve_conflict,
    review_claim,
    run_verification,
)

from ..db import get_db, utcnow
from ..deps import get_current_user
from ..models import (
    AuditLog,
    Claim,
    ClaimReview,
    ConflictRecord,
    Handover,
    HandoverItem,
    Task,
    User,
)
from ..schemas import ResolveConflictRequest, ReviewRequest
from ..services.permissions import record_audit, require_action, visible_claim_query, visible_task_query
from .common import audit_dict, claim_dict, conflict_dict, handover_basic

router = APIRouter(prefix="/api", tags=["verification"])


@router.get("/projects/{project_id}/verification/summary")
def verification_summary(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "verification.view")
    claims = visible_claim_query(db, project_id, member).all()
    counts = Counter(c.verification_status for c in claims)
    average = round(sum(c.reliability_score for c in claims) / len(claims), 1) if claims else 0
    issues = [claim_dict(db, c, member, current_user) for c in claims if c.verification_status != "Verified"]
    issues = [item for item in issues if item]
    return {
        "status_counts": dict(counts),
        "claims_evaluated": len(claims),
        "average_reliability_score": average,
        "score_disclaimer": "Heuristic reliability score (0–100), not a statistically calibrated probability.",
        "unsupported_claim_rate": round(counts.get("Unsupported", 0) / len(claims), 4) if claims else 0,
        "issues": sorted(issues, key=lambda item: item["reliability_score"])[:20],
        "status_categories": ["Verified", "Needs Review", "Conflicting", "Unsupported", "Outdated"],
    }


@router.post("/projects/{project_id}/verification/run")
def run_verification_route(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_action(db, current_user, project_id, "verification.run")
    result = run_verification(db, project_id)
    graph = rebuild_graph(db, project_id)
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="verification.run",
        resource_type="project",
        resource_id=project_id,
        details=result,
    )
    db.commit()
    return {"verification": result, "graph": graph}


@router.get("/projects/{project_id}/conflicts")
def list_conflicts(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "verification.view")
    rows = db.query(ConflictRecord).filter(
        ConflictRecord.project_id == project_id,
        ConflictRecord.sensitivity <= member.max_clearance,
    ).order_by(ConflictRecord.detected_at.desc()).all()
    items = []
    for conflict in rows:
        payload = conflict_dict(db, conflict, member, current_user)
        if not payload:
            continue
        claim_a = db.get(Claim, conflict.claim_a_id)
        claim_b = db.get(Claim, conflict.claim_b_id)
        payload["claim_a"] = claim_dict(db, claim_a, member, current_user) if claim_a else None
        payload["claim_b"] = claim_dict(db, claim_b, member, current_user) if claim_b else None
        items.append(payload)
    return {"items": items, "total": len(items)}


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict_route(
    conflict_id: str,
    payload: ResolveConflictRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    conflict = db.get(ConflictRecord, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found")
    member = require_action(db, current_user, conflict.project_id, "review.approve")
    if conflict.sensitivity > member.max_clearance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found")
    result = resolve_conflict(db, conflict_id, payload.resolution_claim_id, current_user.id, payload.note)
    rebuild_graph(db, conflict.project_id)
    record_audit(
        db,
        user=current_user,
        project_id=conflict.project_id,
        action="conflict.resolve",
        resource_type="conflict",
        resource_id=conflict.id,
        details={"resolution_claim_id": payload.resolution_claim_id, "note": payload.note[:240]},
    )
    db.commit()
    return result


@router.get("/projects/{project_id}/outdated")
def outdated_claims(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "verification.view")
    rows = visible_claim_query(db, project_id, member).filter(Claim.verification_status == "Outdated").all()
    items = [claim_dict(db, c, member, current_user) for c in rows]
    return {"items": [item for item in items if item], "total": len([item for item in items if item])}


@router.get("/projects/{project_id}/unsupported")
def unsupported_claims(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "verification.view")
    rows = visible_claim_query(db, project_id, member).filter(Claim.verification_status == "Unsupported").all()
    items = [claim_dict(db, c, member, current_user) for c in rows]
    return {"items": [item for item in items if item], "total": len([item for item in items if item])}


@router.get("/projects/{project_id}/review/pending")
def pending_review(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "verification.view")
    rows = visible_claim_query(db, project_id, member).filter(Claim.review_status == "pending").order_by(Claim.priority.asc()).all()
    items = [claim_dict(db, c, member, current_user) for c in rows]
    return {"items": [item for item in items if item], "total": len([item for item in items if item])}


@router.post("/projects/{project_id}/review/approve-eligible")
def approve_eligible(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_action(db, current_user, project_id, "review.approve")
    result = approve_eligible_claims(
        db,
        project_id,
        current_user.id,
        note="Manager bulk-approved evidence-backed claims that have no detected issue",
    )
    graph = rebuild_graph(db, project_id)
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="review.approve_eligible",
        resource_type="project",
        resource_id=project_id,
        details={"approved": result["approved"]},
    )
    db.commit()
    return {**result, "graph": graph}


@router.post("/claims/{claim_id}/review")
def review_claim_route(
    claim_id: str,
    payload: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    action_name = "review.correct" if payload.action == "correct" else "review.approve"
    member = require_action(db, current_user, claim.project_id, action_name)
    if claim.sensitivity > member.max_clearance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    result = review_claim(
        db,
        claim_id,
        current_user.id,
        payload.action,
        corrected_statement=payload.corrected_statement,
        note=payload.note,
    )
    rebuild_graph(db, claim.project_id)
    record_audit(
        db,
        user=current_user,
        project_id=claim.project_id,
        action="claim.review",
        resource_type="claim",
        resource_id=claim.id,
        details={"review_action": payload.action, "note": payload.note[:240]},
    )
    db.commit()
    return result


@router.get("/projects/{project_id}/reviews")
def review_history(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "verification.view")
    visible_ids = {c.id for c in visible_claim_query(db, project_id, member).all()}
    rows = (
        db.query(ClaimReview, User)
        .join(User, ClaimReview.actor_id == User.id)
        .filter(ClaimReview.project_id == project_id, ClaimReview.claim_id.in_(visible_ids))
        .order_by(ClaimReview.created_at.desc())
        .limit(200)
        .all()
    )
    items = []
    for review, actor in rows:
        text = " ".join([review.old_statement, review.new_statement, review.note])
        from .common import guard_text
        redacted, changed = guard_text(db, project_id, member, current_user, text, "review.statement")
        if changed:
            continue
        items.append({
            "id": review.id,
            "claim_id": review.claim_id,
            "actor": actor.full_name,
            "actor_email": actor.email,
            "action": review.action,
            "old_statement": review.old_statement,
            "new_statement": review.new_statement,
            "old_status": review.old_status,
            "new_status": review.new_status,
            "note": review.note,
            "created_at": review.created_at.isoformat() + "Z" if review.created_at else None,
        })
    return {"items": items, "total": len(items)}


@router.get("/projects/{project_id}/audit")
def audit_history(
    project_id: str,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "audit.view")
    rows = db.query(AuditLog).filter(AuditLog.project_id == project_id).order_by(AuditLog.id.desc()).limit(limit).all()
    all_rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    chain_valid = True
    previous_hash = ""
    for entry in all_rows:
        if entry.prev_hash != previous_hash:
            chain_valid = False
            break
        previous_hash = entry.event_hash
    items = [audit_dict(db, entry, member, current_user) for entry in rows]
    return {
        "items": items,
        "total": len(items),
        "hash_chain_continuity_valid": chain_valid,
        "chain_check": "Verifies prev_hash links across the append-only log; payload hashes include a non-stored nonce and are not recomputed here.",
    }


@router.get("/projects/{project_id}/continuity")
def continuity_dashboard(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "project.view")
    query = db.query(Handover).filter(Handover.project_id == project_id)
    if member.role not in {"project_manager", "tech_lead", "auditor"}:
        query = query.filter(Handover.recipient_user_id == current_user.id)
    handovers = query.all()
    handover_payloads = [handover_basic(h) for h in handovers]
    all_items = db.query(HandoverItem).filter(HandoverItem.handover_id.in_([h.id for h in handovers])).all() if handovers else []
    acknowledged = len([i for i in all_items if i.acknowledged_at])
    completed = len([i for i in all_items if i.status == "completed"])
    open_questions = visible_claim_query(db, project_id, member).filter(
        Claim.claim_type == "unresolved_question",
        Claim.status_label == "open",
    ).count()
    reviews = db.query(ClaimReview).filter(ClaimReview.project_id == project_id).all()
    corrections = len([r for r in reviews if r.action == "correct"])
    task_status_counts = dict(Counter(
        t.continuation_status
        for t in visible_task_query(db, project_id, member).all()
    ))
    today = utcnow().date().isoformat()
    overdue = len([i for i in all_items if i.due_date and i.due_date < today and i.status != "completed"])
    prep_times = [h.prep_seconds for h in handovers]
    return {
        "handovers": handover_payloads,
        "handover_status_counts": dict(Counter(h.status for h in handovers)),
        "items_total": len(all_items),
        "items_acknowledged": acknowledged,
        "items_completed": completed,
        "acknowledgement_rate": round(acknowledged / len(all_items), 4) if all_items else 0,
        "completion_rate": round(completed / len(all_items), 4) if all_items else 0,
        "overdue_items": overdue,
        "open_questions": open_questions,
        "human_correction_rate": round(corrections / len(reviews), 4) if reviews else 0,
        "corrections": corrections,
        "reviews_total": len(reviews),
        "task_continuation_counts": task_status_counts,
        "handover_prep_seconds": {
            "average": round(sum(prep_times) / len(prep_times), 1) if prep_times else 0,
            "maximum": max(prep_times) if prep_times else 0,
            "measurement": "Wall-clock from first seeded/ingested source to handover generation; automated run, not a human time study.",
        },
        "incoming_member_task_understanding": {
            "measured": False,
            "value": None,
            "note": "Requires a human-in-the-loop study with incoming members; no value is invented.",
        },
    }
