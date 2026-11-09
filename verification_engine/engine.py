"""Evidence-based knowledge reliability, conflict and freshness engine.

`reliability_score` is an explainable heuristic on a 0–100 scale. It is NOT a
statistically calibrated probability and is never presented as one. Status
rules are deterministic and source-grounded: no citation means `Unsupported`;
different recorded values on the same key mean `Conflicting`; an explicit
superseding record marks the older record `Outdated`.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db import utcnow
from backend.app.models import (
    Claim,
    ClaimEvidence,
    ClaimReview,
    ConflictRecord,
    EvidenceSpan,
    SourceDocument,
)

ISSUE_STATUSES = {"Conflicting", "Unsupported", "Outdated"}
PRIMARY_SOURCE_TYPES = {"decision_log", "task_export", "github_commit", "github_issue", "risk_register", "security_review"}


def _evidence_map(db: Session, project_id: str) -> tuple[dict[str, int], dict[str, list[str]]]:
    counts_rows = (
        db.query(ClaimEvidence.claim_id, func.count(ClaimEvidence.id))
        .join(Claim, ClaimEvidence.claim_id == Claim.id)
        .filter(Claim.project_id == project_id, Claim.is_active.is_(True))
        .group_by(ClaimEvidence.claim_id)
        .all()
    )
    counts = {claim_id: int(count) for claim_id, count in counts_rows}
    type_rows = (
        db.query(ClaimEvidence.claim_id, SourceDocument.source_type)
        .join(EvidenceSpan, ClaimEvidence.evidence_span_id == EvidenceSpan.id)
        .join(SourceDocument, EvidenceSpan.source_id == SourceDocument.id)
        .join(Claim, ClaimEvidence.claim_id == Claim.id)
        .filter(Claim.project_id == project_id, Claim.is_active.is_(True))
        .all()
    )
    types: dict[str, list[str]] = defaultdict(list)
    for claim_id, source_type in type_rows:
        types[claim_id].append(source_type)
    return counts, types


def _score_claim(claim: Claim, evidence_count: int, source_types: list[str]) -> tuple[int, list[str]]:
    score = 40
    rationale = [
        "Heuristic reliability score (0–100); not a calibrated probability.",
        "Base 40 for a structured claim awaiting corroboration.",
    ]
    if evidence_count >= 1:
        score += 20
        rationale.append(f"+20: {evidence_count} exact evidence span(s) linked to the original source.")
    else:
        score -= 40
        rationale.append("-40: no supporting evidence span is linked.")
    if evidence_count >= 2:
        score += 10
        rationale.append("+10: two or more independent evidence spans.")
    if any(source_type in PRIMARY_SOURCE_TYPES for source_type in source_types):
        score += 10
        rationale.append("+10: at least one primary project-system source type is linked.")
    if claim.source_timestamp:
        score += 5
        rationale.append("+5: the source has an explicit timestamp.")
    if claim.review_status == "approved":
        score += 10
        rationale.append("+10: an authorised reviewer approved the claim.")
    elif claim.review_status == "rejected":
        score -= 10
        rationale.append("-10: an authorised reviewer rejected the claim.")
    if evidence_count == 1 and "chat_export" in source_types:
        score -= 8
        rationale.append("-8: the only evidence is a chat export, which is treated as lower provenance.")
    if claim.verification_status == "Conflicting":
        score -= 30
        rationale.append("-30: an unresolved contradictory record was detected.")
    elif claim.verification_status == "Outdated":
        score -= 20
        rationale.append("-20: an explicit newer record supersedes this claim.")
    elif claim.verification_status == "Unsupported":
        score -= 15
        rationale.append("-15: the claim is unsupported by linked evidence.")
    elif claim.verification_status == "Needs Review":
        score -= 5
        rationale.append("-5: human review is still pending.")
    score = max(0, min(100, score))
    rationale.append(f"Clamped final heuristic score: {score}.")
    return score, rationale


def run_verification(db: Session, project_id: str) -> dict[str, Any]:
    claims = (
        db.query(Claim)
        .filter(Claim.project_id == project_id, Claim.is_active.is_(True))
        .order_by(Claim.source_timestamp.asc(), Claim.external_ref.asc())
        .all()
    )
    active_ids = {c.id for c in claims}
    evidence_counts, source_types = _evidence_map(db, project_id)
    by_ref = {c.external_ref: c for c in claims}

    # Close conflicts that reference claims deactivated by a correction/re-upload.
    for conflict in db.query(ConflictRecord).filter(
        ConflictRecord.project_id == project_id,
        ConflictRecord.status == "open",
    ).all():
        if conflict.claim_a_id not in active_ids or conflict.claim_b_id not in active_ids:
            conflict.status = "closed_auto"

    # Explicit supersession is stronger evidence of staleness than an age threshold.
    outdated_ids: set[str] = set()
    for claim in claims:
        # Preserve human conflict resolutions and correction supersessions across
        # later verification runs.
        if claim.verification_status == "Outdated" and (
            claim.metadata_json.get("superseded_by")
            or claim.metadata_json.get("conflict_resolution")
            or claim.review_status == "corrected"
        ):
            outdated_ids.add(claim.id)
    for newer in claims:
        if not newer.supersedes_ref:
            continue
        older = by_ref.get(newer.supersedes_ref)
        if not older or older.id == newer.id:
            continue
        older.verification_status = "Outdated"
        older.metadata_json = {
            **older.metadata_json,
            "superseded_by": newer.external_ref,
            "superseded_at": newer.source_timestamp.isoformat() + "Z",
        }
        newer.metadata_json = {**newer.metadata_json, "supersedes_validated": True}
        outdated_ids.add(older.id)

    groups: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        if not claim.normalized_key:
            continue
        if claim.verification_status in {"Unsupported", "Outdated"}:
            continue
        groups[claim.normalized_key].append(claim)

    conflicting_ids: set[str] = set()
    open_conflict_keys: set[str] = set()
    for normalized_key, group in groups.items():
        eligible = [c for c in group if c.normalized_value]
        distinct_values = {c.normalized_value for c in eligible}
        if len(eligible) < 2 or len(distinct_values) < 2:
            continue
        for i, left in enumerate(eligible):
            for right in eligible[i + 1:]:
                if left.normalized_value == right.normalized_value:
                    continue
                if left.supersedes_ref == right.external_ref or right.supersedes_ref == left.external_ref:
                    continue
                a, b = sorted([left, right], key=lambda c: (c.source_timestamp, c.external_ref))
                existing = (
                    db.query(ConflictRecord)
                    .filter(
                        ConflictRecord.project_id == project_id,
                        ConflictRecord.claim_a_id == a.id,
                        ConflictRecord.claim_b_id == b.id,
                    )
                    .first()
                )
                if existing and existing.status == "resolved":
                    continue
                if existing is None:
                    existing = ConflictRecord(
                        project_id=project_id,
                        claim_a_id=a.id,
                        claim_b_id=b.id,
                        normalized_key=normalized_key,
                        value_a=a.value,
                        value_b=b.value,
                        conflict_type="value_mismatch",
                        rationale=(
                            f"Two active records describe '{normalized_key}' with different values: "
                            f"'{a.value}' and '{b.value}'. Source timestamps and exact evidence are attached."
                        ),
                        status="open",
                        sensitivity=max(a.sensitivity, b.sensitivity),
                    )
                    db.add(existing)
                    db.flush()
                conflicting_ids.update({a.id, b.id})
                open_conflict_keys.add(normalized_key)

    status_counts: dict[str, int] = defaultdict(int)
    for claim in claims:
        count = evidence_counts.get(claim.id, 0)
        types = source_types.get(claim.id, [])
        if count == 0:
            claim.verification_status = "Unsupported"
        elif claim.id in conflicting_ids:
            claim.verification_status = "Conflicting"
        elif claim.id in outdated_ids:
            claim.verification_status = "Outdated"
        elif claim.review_status == "approved":
            claim.verification_status = "Verified"
        else:
            claim.verification_status = "Needs Review"

        score, rationale = _score_claim(claim, count, types)
        claim.reliability_score = score
        claim.score_rationale = rationale
        status_counts[claim.verification_status] += 1

    db.flush()
    return {
        "claims_evaluated": len(claims),
        "status_counts": dict(status_counts),
        "conflicts_open": len(open_conflict_keys),
        "outdated": len(outdated_ids),
        "unsupported": status_counts.get("Unsupported", 0),
        "score_type": "explainable heuristic, not a calibrated probability",
    }


def resolve_conflict(
    db: Session,
    conflict_id: str,
    resolution_claim_id: str,
    actor_id: str,
    note: str,
) -> dict[str, Any]:
    conflict = db.get(ConflictRecord, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found")
    if conflict.status == "resolved":
        return {"id": conflict.id, "status": "resolved", "already_resolved": True}
    if resolution_claim_id not in {conflict.claim_a_id, conflict.claim_b_id}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolution must select one of the conflicting claims")
    selected = db.get(Claim, resolution_claim_id)
    other_id = conflict.claim_b_id if resolution_claim_id == conflict.claim_a_id else conflict.claim_a_id
    other = db.get(Claim, other_id)
    if selected is None or other is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A conflicting claim is no longer available")

    other.verification_status = "Outdated"
    other.metadata_json = {
        **other.metadata_json,
        "superseded_by": selected.external_ref,
        "superseded_at": utcnow().isoformat() + "Z",
        "conflict_resolution": conflict.id,
    }
    selected.verification_status = "Needs Review"
    selected.review_status = "pending"
    selected.metadata_json = {**selected.metadata_json, "conflict_resolution_pending_approval": conflict.id}
    conflict.status = "resolved"
    conflict.resolution_claim_id = selected.id
    conflict.resolved_by = actor_id
    conflict.resolved_at = utcnow()
    conflict.resolution_note = note
    db.flush()
    result = run_verification(db, conflict.project_id)
    return {"id": conflict.id, "status": "resolved", "selected_claim_id": selected.id, "verification": result}


def review_claim(
    db: Session,
    claim_id: str,
    actor_id: str,
    action: str,
    corrected_statement: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    claim = db.get(Claim, claim_id)
    if claim is None or not claim.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active claim not found")
    old_status = claim.verification_status
    old_statement = claim.statement
    new_statement = old_statement
    replacement_id = claim.id

    if action == "approve":
        claim.review_status = "approved"
        claim.metadata_json = {**claim.metadata_json, "last_review_note": note}
    elif action == "reject":
        claim.review_status = "rejected"
        claim.is_active = False
        claim.verification_status = "Unsupported"
        claim.metadata_json = {**claim.metadata_json, "rejection_reason": note}
    elif action == "correct":
        if not corrected_statement or len(corrected_statement.strip()) < 5:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A corrected statement is required")
        new_statement = corrected_statement.strip()
        evidence_rows = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
        max_version = (
            db.query(func.max(Claim.version))
            .filter(Claim.project_id == claim.project_id, Claim.external_ref == claim.external_ref)
            .scalar()
            or 0
        )
        replacement = Claim(
            project_id=claim.project_id,
            external_ref=claim.external_ref,
            claim_type=claim.claim_type,
            statement=new_statement,
            normalized_key=claim.normalized_key,
            normalized_value=claim.normalized_value,
            subject=claim.subject,
            value=claim.value,
            owner=claim.owner,
            status_label=claim.status_label,
            due_date=claim.due_date,
            depends_on=claim.depends_on,
            tags=claim.tags,
            role_scope=claim.role_scope,
            sensitivity=claim.sensitivity,
            source_timestamp=claim.source_timestamp,
            extracted_by=actor_id,
            review_status="pending",
            verification_status="Needs Review",
            reliability_score=0,
            score_rationale=["New corrected version awaiting verification."],
            is_active=True,
            version=int(max_version) + 1,
            supersedes_claim_id=claim.id,
            supersedes_ref=claim.external_ref,
            rationale=claim.rationale,
            priority=claim.priority,
            metadata_json={
                **claim.metadata_json,
                "corrected_from_claim_id": claim.id,
                "corrected_from_version": claim.version,
                "last_review_note": note,
            },
        )
        db.add(replacement)
        db.flush()
        replacement_id = replacement.id
        for row in evidence_rows:
            db.add(ClaimEvidence(
                claim_id=replacement.id,
                evidence_span_id=row.evidence_span_id,
                relation=row.relation,
                weight=row.weight,
            ))
        claim.review_status = "corrected"
        claim.is_active = False
        claim.verification_status = "Outdated"
        claim.metadata_json = {**claim.metadata_json, "corrected_by_claim_id": replacement.id}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown review action")

    db.add(ClaimReview(
        project_id=claim.project_id,
        claim_id=claim.id,
        actor_id=actor_id,
        action=action,
        old_statement=old_statement,
        new_statement=new_statement,
        old_status=old_status,
        new_status=claim.verification_status,
        note=note,
    ))
    db.flush()
    result = run_verification(db, claim.project_id)
    return {
        "claim_id": claim_id,
        "replacement_claim_id": replacement_id,
        "action": action,
        "verification": result,
    }


def approve_eligible_claims(db: Session, project_id: str, actor_id: str, note: str = "Bulk approval of eligible evidence-backed claims") -> dict[str, Any]:
    counts, _ = _evidence_map(db, project_id)
    candidates = (
        db.query(Claim)
        .filter(
            Claim.project_id == project_id,
            Claim.is_active.is_(True),
            Claim.review_status == "pending",
            Claim.verification_status.notin_(list(ISSUE_STATUSES)),
        )
        .all()
    )
    approved = 0
    for claim in candidates:
        if counts.get(claim.id, 0) < 1:
            continue
        claim.review_status = "approved"
        claim.metadata_json = {**claim.metadata_json, "last_review_note": note}
        db.add(ClaimReview(
            project_id=project_id,
            claim_id=claim.id,
            actor_id=actor_id,
            action="approve",
            old_statement=claim.statement,
            new_statement=claim.statement,
            old_status=claim.verification_status,
            new_status="Verified",
            note=note,
        ))
        approved += 1
    db.flush()
    result = run_verification(db, project_id)
    return {"approved": approved, "verification": result}
