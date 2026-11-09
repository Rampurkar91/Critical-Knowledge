"""Project, workspace, member and dashboard routes."""
from __future__ import annotations

import secrets
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import (
    Claim,
    ConflictRecord,
    Handover,
    Project,
    ProjectMember,
    Risk,
    SourceDocument,
    Task,
    User,
)
from ..schemas import MemberCreate, MemberUpdate, ProjectCreate, ProjectUpdate
from ..security import hash_password
from ..services.permissions import (
    ROLE_POLICIES,
    assert_clearance,
    record_audit,
    require_action,
    require_project_manager,
    role_policy,
    sensitivity_label,
    visible_claim_query,
    visible_risk_query,
    visible_source_query,
    visible_task_query,
)
from ..utils import slugify
from .common import claim_dict, handover_basic, project_dict, risk_dict, task_dict, visible_refs

router = APIRouter(prefix="/api", tags=["projects"])


def _project_stats(db: Session, project_id: str, member: ProjectMember) -> dict[str, int]:
    return {
        "sources": visible_source_query(db, project_id, member).count(),
        "claims": visible_claim_query(db, project_id, member).count(),
        "tasks": visible_task_query(db, project_id, member).count(),
        "risks": visible_risk_query(db, project_id, member).count(),
    }


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    base_key = (payload.key or slugify(payload.name)[:10]).upper() or "PROJECT"
    key = base_key
    while db.query(Project).filter(Project.organization_id == current_user.organization_id, Project.key == key).first():
        key = f"{base_key[:8]}{secrets.token_hex(1).upper()}"
    project = Project(
        organization_id=current_user.organization_id,
        key=key,
        name=payload.name,
        description=payload.description,
        created_by=current_user.id,
        is_demo=payload.is_demo,
    )
    db.add(project)
    db.flush()
    policy = role_policy("project_manager")
    membership = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="project_manager",
        max_clearance=policy["clearance"],
        allowed_claim_types=policy["claim_types"],
        allowed_tags=policy["tags"],
    )
    db.add(membership)
    record_audit(
        db,
        user=current_user,
        project_id=project.id,
        action="project.create",
        resource_type="project",
        resource_id=project.id,
        details={"key": project.key, "is_demo": project.is_demo},
    )
    db.commit()
    return project_dict(db, project, membership)


@router.get("/projects")
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = (
        db.query(ProjectMember, Project)
        .join(Project, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == current_user.id, Project.organization_id == current_user.organization_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    results = []
    for member, project in rows:
        data = project_dict(db, project, member)
        data["stats"] = _project_stats(db, project.id, member)
        results.append(data)
    return results


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "project.view")
    project = db.get(Project, project_id)
    data = project_dict(db, project, member)
    data["stats"] = _project_stats(db, project_id, member)
    data["policy"] = role_policy(member.role)
    data["demo_notice"] = "Synthetic demonstration data" if project.is_demo else None
    return data


@router.patch("/projects/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "member.manage")
    project = db.get(Project, project_id)
    for field in ("name", "description", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(project, field, value)
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="project.update",
        resource_type="project",
        resource_id=project_id,
        details=payload.model_dump(exclude_none=True),
    )
    db.commit()
    return project_dict(db, project, member)


@router.get("/projects/{project_id}/dashboard")
def project_dashboard(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "project.view")
    project = db.get(Project, project_id)
    visible_claims = visible_claim_query(db, project_id, member).all()
    status_counts = Counter(c.verification_status for c in visible_claims)
    avg_score = round(sum(c.reliability_score for c in visible_claims) / len(visible_claims), 1) if visible_claims else 0
    claims_payload = [claim_dict(db, c, member, current_user) for c in visible_claims]
    claims_payload = [c for c in claims_payload if c]
    recent_claims = sorted(claims_payload, key=lambda c: c.get("source_timestamp") or "", reverse=True)[:6]

    handovers_query = db.query(Handover).filter(Handover.project_id == project_id)
    if member.role not in {"project_manager", "tech_lead", "auditor"}:
        handovers_query = handovers_query.filter(Handover.recipient_user_id == current_user.id)
    handovers = [handover_basic(h) for h in handovers_query.order_by(Handover.generated_at.desc()).all()]

    conflicts = db.query(ConflictRecord).filter(
        ConflictRecord.project_id == project_id,
        ConflictRecord.status == "open",
        ConflictRecord.sensitivity <= member.max_clearance,
    ).count()

    refs = visible_refs(db, project_id, member)
    tasks = [
        task_dict(db, t, member, current_user, refs)
        for t in visible_task_query(db, project_id, member).all()
    ]
    tasks = [t for t in tasks if t]
    risks = [
        risk_dict(db, r, member, current_user)
        for r in visible_risk_query(db, project_id, member).all()
    ]
    risks = [r for r in risks if r]

    return {
        "project": project_dict(db, project, member),
        "demo_notice": "Synthetic demonstration data" if project.is_demo else None,
        "stats": _project_stats(db, project_id, member),
        "verification_status_counts": dict(status_counts),
        "average_reliability_score": avg_score,
        "score_disclaimer": "Heuristic reliability score, not a calibrated probability.",
        "open_conflicts": conflicts,
        "recent_claims": recent_claims,
        "handovers": handovers,
        "task_status_counts": dict(Counter(t["status"] for t in tasks)),
        "risk_severity_counts": dict(Counter(r["severity"] for r in risks)),
        "high_priority_tasks": [t for t in tasks if t["priority"] <= 1][:5],
        "open_risks": [r for r in risks if r["status"] == "open"][:5],
    }


@router.get("/projects/{project_id}/members")
def list_members(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    require_project_manager(db, current_user, project_id)
    rows = (
        db.query(ProjectMember, User)
        .join(User, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at.asc())
        .all()
    )
    return [
        {
            "id": member.id,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": member.role,
            "role_label": role_policy(member.role)["label"],
            "clearance": member.max_clearance,
            "clearance_label": sensitivity_label(member.max_clearance),
            "allowed_claim_types": member.allowed_claim_types,
            "allowed_tags": member.allowed_tags,
            "policy": role_policy(member.role),
        }
        for member, user in rows
    ]


@router.post("/projects/{project_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: str,
    payload: MemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    manager = require_project_manager(db, current_user, project_id)
    if payload.role not in ROLE_POLICIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown project role")
    policy = role_policy(payload.role)
    clearance = payload.max_clearance if payload.max_clearance is not None else policy["clearance"]
    assert_clearance(manager, clearance)
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user and user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User belongs to a different organisation")
    if user is None:
        if not payload.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ask this person to register first, or provide a password for the new account",
            )
        user = User(
            organization_id=current_user.organization_id,
            email=email,
            full_name=payload.full_name or email.split("@")[0],
            password_hash=hash_password(payload.password),
            system_role="member",
        )
        db.add(user)
        db.flush()
    if db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a project member")
    member = ProjectMember(
        project_id=project_id,
        user_id=user.id,
        role=payload.role,
        max_clearance=clearance,
        allowed_claim_types=payload.allowed_claim_types or policy["claim_types"],
        allowed_tags=payload.allowed_tags or policy["tags"],
    )
    db.add(member)
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="member.add",
        resource_type="member",
        resource_id=member.id,
        details={"email": email, "role": payload.role, "clearance": clearance},
    )
    db.commit()
    return {"id": member.id, "user_id": user.id, "email": email, "role": member.role, "clearance": member.max_clearance}


@router.patch("/members/{member_id}")
def update_member(
    member_id: str,
    payload: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = db.get(ProjectMember, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    manager = require_project_manager(db, current_user, member.project_id)
    old = {
        "role": member.role,
        "clearance": member.max_clearance,
        "allowed_claim_types": member.allowed_claim_types,
        "allowed_tags": member.allowed_tags,
    }
    if payload.role:
        if payload.role not in ROLE_POLICIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown project role")
        member.role = payload.role
        policy = role_policy(payload.role)
        member.allowed_claim_types = payload.allowed_claim_types or policy["claim_types"]
        member.allowed_tags = payload.allowed_tags or policy["tags"]
        if payload.max_clearance is None:
            member.max_clearance = policy["clearance"]
    if payload.max_clearance is not None:
        member.max_clearance = payload.max_clearance
    if payload.allowed_claim_types is not None and not payload.role:
        member.allowed_claim_types = payload.allowed_claim_types
    if payload.allowed_tags is not None and not payload.role:
        member.allowed_tags = payload.allowed_tags
    assert_clearance(manager, member.max_clearance)
    record_audit(
        db,
        user=current_user,
        project_id=member.project_id,
        action="member.update",
        resource_type="member",
        resource_id=member.id,
        details={"before": old, "after": payload.model_dump(exclude_none=True)},
    )
    db.commit()
    return {
        "id": member.id,
        "role": member.role,
        "clearance": member.max_clearance,
        "clearance_label": sensitivity_label(member.max_clearance),
        "allowed_claim_types": member.allowed_claim_types,
        "allowed_tags": member.allowed_tags,
    }
