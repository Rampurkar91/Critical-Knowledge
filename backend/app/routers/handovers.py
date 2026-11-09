"""Handover generation, human approval, controlled sharing and continuation."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from handover_engine.generator import (
    export_markdown,
    generate_handover,
    serialize_handover,
    update_item,
)

from ..db import get_db, utcnow
from ..deps import get_current_user
from ..models import Claim, Handover, HandoverItem, ProjectMember, Task, User
from ..schemas import HandoverGenerateRequest, HandoverItemUpdate, HandoverUpdateRequest
from ..services.permissions import (
    SENSITIVITY_BY_NAME,
    record_audit,
    redact_forbidden_text,
    require_action,
    require_project_manager,
    role_policy,
    visible_claim_query,
    visible_task_query,
)
from ..utils import json_safe
from .common import guard_text, handover_basic

router = APIRouter(prefix="/api", tags=["handovers"])

PRIVILEGED_ROLES = {"project_manager", "tech_lead", "auditor"}


def _recipient_member(db: Session, handover: Handover) -> ProjectMember:
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == handover.project_id, ProjectMember.user_id == handover.recipient_user_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recipient no longer has a project role")
    return member


def _content_claim_ids(value: object, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "claim_id" and isinstance(item, str) and item:
                found.add(item)
            elif key == "generated_from_claim_ids" and isinstance(item, list):
                found.update(str(entry) for entry in item if entry)
            else:
                _content_claim_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _content_claim_ids(item, found)


def _content_sensitivity_levels(value: object, found: set[int]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"sensitivity", "clearance_level"} and isinstance(item, int):
                found.add(item)
            elif key == "clearance" and isinstance(item, str):
                level = SENSITIVITY_BY_NAME.get(item.lower())
                if level is not None:
                    found.add(level)
            elif key == "sensitivity" and isinstance(item, str):
                level = SENSITIVITY_BY_NAME.get(item.lower())
                if level is not None:
                    found.add(level)
            else:
                _content_sensitivity_levels(item, found)
    elif isinstance(value, list):
        for item in value:
            _content_sensitivity_levels(item, found)


def _validate_content(db: Session, handover: Handover, recipient: ProjectMember) -> None:
    serialized = json.dumps(json_safe(handover.content_json), ensure_ascii=False)
    _, changed = redact_forbidden_text(db, handover.project_id, recipient.max_clearance, serialized)
    if changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handover content contains a phrase above the recipient's clearance. Edit rejected.",
        )
    claim_ids: set[str] = set()
    _content_claim_ids(handover.content_json, claim_ids)
    if claim_ids:
        allowed_ids = {
            claim.id
            for claim in visible_claim_query(db, handover.project_id, recipient)
            .filter(Claim.id.in_(claim_ids))
            .all()
        }
        if claim_ids - allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Handover content references claims outside the recipient's ABAC policy. Edit rejected.",
            )
    levels: set[int] = set()
    _content_sensitivity_levels(handover.content_json, levels)
    levels.add(handover.clearance_applied)
    if any(level > recipient.max_clearance for level in levels):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handover content contains a classification above the recipient's clearance. Edit rejected.",
        )


def _item_authorized(db: Session, project_id: str, item: HandoverItem, member: ProjectMember) -> bool:
    if item.sensitivity > member.max_clearance:
        return False
    if item.claim_id and visible_claim_query(db, project_id, member).filter(Claim.id == item.claim_id).first() is None:
        return False
    if item.task_id and visible_task_query(db, project_id, member).filter(Task.id == item.task_id).first() is None:
        return False
    return True


def _access(
    db: Session,
    user: User,
    handover_id: str,
    action: str,
    *,
    manager_only: bool = False,
) -> tuple[Handover, ProjectMember]:
    handover = db.get(Handover, handover_id)
    if handover is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found")
    member = require_action(db, user, handover.project_id, action)
    if manager_only:
        require_project_manager(db, user, handover.project_id)
    privileged = member.role in PRIVILEGED_ROLES
    if handover.clearance_applied > member.max_clearance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found")
    if user.id != handover.recipient_user_id and not privileged:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found")
    if action in {"handover.view", "export", "handover.acknowledge"} and not privileged and handover.status == "draft":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover not found")
    return handover, member


@router.post("/projects/{project_id}/handovers/generate", status_code=status.HTTP_201_CREATED)
def generate_handover_route(
    project_id: str,
    payload: HandoverGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_action(db, current_user, project_id, "handover.generate")
    require_project_manager(db, current_user, project_id)
    try:
        handover = generate_handover(
            db,
            project_id,
            payload.recipient_user_id,
            current_user.id,
            title=payload.title,
            role_key=payload.role_key,
        )
    except HTTPException:
        record_audit(
            db,
            user=current_user,
            project_id=project_id,
            action="handover.generate",
            resource_type="handover",
            outcome="blocked",
            details={"recipient_user_id": payload.recipient_user_id, "reason": "permission_guard_or_validation"},
            commit=True,
        )
        raise
    recipient = _recipient_member(db, handover)
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="handover.generate",
        resource_type="handover",
        resource_id=handover.id,
        details={
            "recipient_role": handover.recipient_role,
            "clearance_applied": handover.clearance_applied,
            "claim_count": len(handover.content_json.get("metadata", {}).get("generated_from_claim_ids", [])),
        },
    )
    db.commit()
    return serialize_handover(db, handover, recipient)


@router.get("/projects/{project_id}/handovers")
def list_handovers(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "handover.view")
    query = db.query(Handover).filter(Handover.project_id == project_id)
    if member.role not in PRIVILEGED_ROLES:
        query = query.filter(Handover.recipient_user_id == current_user.id, Handover.status != "draft")
    rows = query.order_by(Handover.generated_at.desc()).all()
    return {"items": [handover_basic(h) for h in rows], "total": len(rows)}


@router.get("/handovers/mine")
def my_handovers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(Handover)
        .filter(Handover.recipient_user_id == current_user.id, Handover.status != "draft")
        .order_by(Handover.generated_at.desc())
        .all()
    )
    items = []
    for handover in rows:
        try:
            require_action(db, current_user, handover.project_id, "handover.view")
            recipient = _recipient_member(db, handover)
            items.append(serialize_handover(db, handover, recipient))
        except HTTPException:
            continue
    record_audit(
        db,
        user=current_user,
        action="handover.view_mine",
        resource_type="handover",
        details={"count": len(items)},
        commit=True,
    )
    return {"items": items, "total": len(items)}


@router.get("/handovers/{handover_id}")
def get_handover(
    handover_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    handover, _ = _access(db, current_user, handover_id, "handover.view")
    recipient = _recipient_member(db, handover)
    record_audit(
        db,
        user=current_user,
        project_id=handover.project_id,
        action="handover.view",
        resource_type="handover",
        resource_id=handover.id,
        commit=True,
    )
    return serialize_handover(db, handover, recipient)


@router.patch("/handovers/{handover_id}")
def edit_handover(
    handover_id: str,
    payload: HandoverUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    handover, _ = _access(db, current_user, handover_id, "handover.approve", manager_only=True)
    recipient = _recipient_member(db, handover)
    before_version = handover.version
    if payload.title:
        handover.title = payload.title
    if payload.content_json is not None:
        handover.content_json = payload.content_json
    handover.edit_note = payload.edit_note
    handover.version = before_version + 1
    _validate_content(db, handover, recipient)
    record_audit(
        db,
        user=current_user,
        project_id=handover.project_id,
        action="handover.edit",
        resource_type="handover",
        resource_id=handover.id,
        details={"before_version": before_version, "after_version": handover.version, "note": payload.edit_note[:240]},
    )
    db.commit()
    return serialize_handover(db, handover, recipient)


@router.post("/handovers/{handover_id}/approve")
def approve_handover(
    handover_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    handover, _ = _access(db, current_user, handover_id, "handover.approve", manager_only=True)
    recipient = _recipient_member(db, handover)
    _validate_content(db, handover, recipient)
    handover.status = "approved"
    handover.approved_by = current_user.id
    handover.approved_at = utcnow()
    record_audit(
        db,
        user=current_user,
        project_id=handover.project_id,
        action="handover.approve",
        resource_type="handover",
        resource_id=handover.id,
        details={"clearance": handover.clearance_applied, "version": handover.version},
    )
    db.commit()
    return serialize_handover(db, handover, recipient)


@router.post("/handovers/{handover_id}/share")
def share_handover(
    handover_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    handover, _ = _access(db, current_user, handover_id, "handover.share", manager_only=True)
    recipient = _recipient_member(db, handover)
    _validate_content(db, handover, recipient)
    if handover.status == "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approve the handover before sharing")
    if handover.status == "approved":
        handover.status = "shared"
    if handover.shared_at is None:
        handover.shared_at = utcnow()
    record_audit(
        db,
        user=current_user,
        project_id=handover.project_id,
        action="handover.share",
        resource_type="handover",
        resource_id=handover.id,
        details={
            "recipient_user_id": handover.recipient_user_id,
            "clearance": handover.clearance_applied,
            "role": handover.recipient_role,
            "status": handover.status,
        },
    )
    db.commit()
    return serialize_handover(db, handover, recipient)


@router.get("/handovers/{handover_id}/export")
def export_handover(
    handover_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    handover, _ = _access(db, current_user, handover_id, "export")
    recipient = _recipient_member(db, handover)
    markdown = export_markdown(db, handover, recipient)
    record_audit(
        db,
        user=current_user,
        project_id=handover.project_id,
        action="handover.export",
        resource_type="handover",
        resource_id=handover.id,
        details={"format": "markdown", "clearance": handover.clearance_applied},
        commit=True,
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="knowledgebridge-{handover.id}.md"'},
    )


@router.get("/handovers/{handover_id}/items")
def handover_items(
    handover_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    handover, member = _access(db, current_user, handover_id, "handover.view")
    rows = db.query(HandoverItem).filter(
        HandoverItem.handover_id == handover.id,
        HandoverItem.sensitivity <= member.max_clearance,
    ).order_by(HandoverItem.priority.asc(), HandoverItem.created_at.asc()).all()
    items = []
    for item in rows:
        if not _item_authorized(db, handover.project_id, item, member):
            continue
        title, changed = guard_text(db, handover.project_id, member, current_user, item.title, "handover.item")
        if changed:
            continue
        items.append({
            "id": item.id,
            "title": title,
            "item_type": item.item_type,
            "priority": item.priority,
            "status": item.status,
            "due_date": item.due_date,
            "task_id": item.task_id,
            "claim_id": item.claim_id,
            "acknowledged_at": item.acknowledged_at.isoformat() + "Z" if item.acknowledged_at else None,
            "completed_at": item.completed_at.isoformat() + "Z" if item.completed_at else None,
            "notes": item.notes,
        })
    return {"items": items, "total": len(items), "handover_status": handover.status}


@router.post("/handover-items/{item_id}/action")
def handover_item_action(
    item_id: str,
    payload: HandoverItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(HandoverItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover item not found")
    handover, member = _access(db, current_user, item.handover_id, "handover.acknowledge")
    if not _item_authorized(db, handover.project_id, item, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handover item not found")
    result = update_item(db, item, payload.action, current_user.id, payload.note)
    record_audit(
        db,
        user=current_user,
        project_id=handover.project_id,
        action="handover.item_action",
        resource_type="handover_item",
        resource_id=item.id,
        details={"action": payload.action, "handover_id": handover.id},
    )
    db.commit()
    return result
