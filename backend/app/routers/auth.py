"""Authentication, organisation and public metadata routes."""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db, utcnow
from ..deps import get_current_user
from ..models import Organization, Project, ProjectMember, User
from ..schemas import LoginRequest, OrganizationCreate, RegisterRequest
from ..security import hash_password, verify_password
from ..services.permissions import record_audit, role_policy
from ..utils import slugify
from .common import auth_response, meta_payload, user_dict

router = APIRouter(prefix="/api", tags=["auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DemoLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


def _create_organization(db: Session, name: str) -> Organization:
    base = slugify(name)
    slug = base
    suffix = 2
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base}-{suffix}"
        suffix += 1
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.flush()
    return org


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    return meta_payload()


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = payload.email.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    created_org = False
    if payload.organization_id:
        org = db.get(Organization, payload.organization_id)
        if org is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    else:
        org = _create_organization(db, payload.organization_name or f"{payload.full_name}'s Organisation")
        created_org = True

    user = User(
        organization_id=org.id,
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        system_role="org_admin" if created_org else "member",
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        user=user,
        organization_id=org.id,
        action="auth.register",
        resource_type="user",
        resource_id=user.id,
        details={"organization_created": created_org},
    )
    db.commit()
    return auth_response(user)


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_audit(
            db,
            actor_email=email,
            action="auth.login",
            resource_type="session",
            outcome="denied",
            details={"reason": "invalid_credentials"},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user.last_login_at = utcnow()
    record_audit(
        db,
        user=user,
        action="auth.login",
        resource_type="session",
        resource_id=user.id,
    )
    db.commit()
    return auth_response(user)


@router.post("/auth/demo-login")
def demo_login(payload: DemoLoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if settings.environment.lower() not in {"development", "dev", "local"} or not settings.seed_demo_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo login is disabled")
    email = payload.email.strip().lower()
    if not email.endswith("@knowledgebridge.demo"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a demonstration account")
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demonstration account not found")
    user.last_login_at = utcnow()
    record_audit(
        db,
        user=user,
        action="auth.demo_login",
        resource_type="session",
        resource_id=user.id,
        details={"warning": "development-only passwordless demo login"},
    )
    db.commit()
    return auth_response(user)


@router.get("/auth/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    memberships = (
        db.query(ProjectMember, Project)
        .join(Project, ProjectMember.project_id == Project.id)
        .filter(ProjectMember.user_id == current_user.id)
        .all()
    )
    return {
        **user_dict(current_user),
        "memberships": [
            {
                "project_id": project.id,
                "project_name": project.name,
                "project_key": project.key,
                "role": member.role,
                "role_label": role_policy(member.role)["label"],
                "clearance": member.max_clearance,
                "allowed_claim_types": member.allowed_claim_types,
                "allowed_tags": member.allowed_tags,
            }
            for member, project in memberships
        ],
    }


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    org = _create_organization(db, payload.name)
    record_audit(
        db,
        user=current_user,
        organization_id=org.id,
        action="organization.create",
        resource_type="organization",
        resource_id=org.id,
    )
    db.commit()
    return {"id": org.id, "name": org.name, "slug": org.slug}


@router.get("/organizations")
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    orgs = db.query(Organization).filter(Organization.id == current_user.organization_id).all()
    return [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs]
