"""Idempotent synthetic demonstration seed.

All seeded records are clearly marked `is_demo=True`. No API keys, real customer
documents or private credentials are included.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ai_engine.extractor import parse_source

from .config import SAMPLE_DATA_DIR, settings
from .db import utcnow
from .models import Claim, Organization, Project, ProjectMember, SourceDocument, User
from .security import hash_password
from .services.orchestrator import run_full_reconstruction
from .services.permissions import record_audit, role_policy
from .utils import slugify

MANIFEST_PATH = SAMPLE_DATA_DIR / "manifest.json"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def seed_demo(db: Session) -> dict[str, Any]:
    manifest = _manifest()
    org = db.query(Organization).filter(Organization.slug == "knowledgebridge-demo").first()
    if org:
        project = db.query(Project).filter(Project.organization_id == org.id, Project.key == "ATLAS").first()
        manager = db.query(User).filter(User.email == "manager@knowledgebridge.demo").first()
        if project and manager:
            return {"already_seeded": True, "organization_id": org.id, "project_id": project.id, "manager_id": manager.id}

    org = Organization(
        name="KnowledgeBridge Demonstration Org",
        slug="knowledgebridge-demo",
    )
    db.add(org)
    db.flush()

    users: dict[str, User] = {}
    for spec in manifest["demo_users"]:
        user = User(
            organization_id=org.id,
            email=spec["email"],
            full_name=spec["full_name"],
            password_hash=hash_password(settings.demo_password),
            system_role="org_admin" if spec["role"] == "project_manager" else "member",
        )
        db.add(user)
        db.flush()
        users[spec["email"]] = user

    manager = users["manager@knowledgebridge.demo"]
    project_spec = manifest["project"]
    project = Project(
        organization_id=org.id,
        key=project_spec["key"],
        name=project_spec["name"],
        description=project_spec["description"],
        status=project_spec["status"],
        created_by=manager.id,
        is_demo=True,
    )
    db.add(project)
    db.flush()

    for spec in manifest["demo_users"]:
        policy = role_policy(spec["role"])
        db.add(ProjectMember(
            project_id=project.id,
            user_id=users[spec["email"]].id,
            role=spec["role"],
            max_clearance=spec.get("clearance", policy["clearance"]),
            allowed_claim_types=policy["claim_types"],
            allowed_tags=policy["tags"],
        ))

    for item in manifest["sources"]:
        path: Path = SAMPLE_DATA_DIR / item["file"]
        content = path.read_text(encoding="utf-8")
        parsed = parse_source(
            content,
            fallback_title=path.stem,
            fallback_type=item["type"],
            fallback_sensitivity=1,
            fallback_timestamp=utcnow(),
        )
        source = SourceDocument(
            project_id=project.id,
            title=parsed.meta.title,
            source_type=parsed.meta.source_type,
            external_ref=parsed.meta.external_ref,
            author=parsed.meta.author,
            content=content,
            source_timestamp=parsed.meta.source_timestamp,
            ingested_at=utcnow(),
            ingested_by=manager.id,
            sensitivity=parsed.meta.sensitivity,
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            is_demo=True,
            mime_type="text/markdown",
            byte_size=len(content.encode("utf-8")),
            metadata_json={
                "source_ref": parsed.meta.source_ref,
                "demo": True,
                "dataset_notice": manifest["notice"],
                "manifest_file": item["file"],
            },
        )
        db.add(source)
        db.flush()
        record_audit(
            db,
            user=manager,
            project_id=project.id,
            action="source.ingest",
            resource_type="source",
            resource_id=source.id,
            details={
                "title": source.title,
                "source_type": source.source_type,
                "sensitivity": source.sensitivity,
                "is_demo": True,
                "external_ref": source.external_ref[:240],
            },
        )

    record_audit(
        db,
        user=manager,
        project_id=project.id,
        action="demo.seed",
        resource_type="project",
        resource_id=project.id,
        details={"notice": manifest["notice"], "sources": len(manifest["sources"]), "users": len(manifest["demo_users"])},
    )
    db.flush()
    return {"already_seeded": False, "organization_id": org.id, "project_id": project.id, "manager_id": manager.id}


def bootstrap_demo(db: Session) -> dict[str, Any]:
    if not settings.seed_demo_data:
        return {"skipped": True, "reason": "SEED_DEMO_DATA=false"}
    seeded = seed_demo(db)
    claims = db.query(Claim).filter(Claim.project_id == seeded["project_id"]).count()
    if claims == 0:
        reconstruction = run_full_reconstruction(db, seeded["project_id"], seeded["manager_id"])
        seeded["reconstruction"] = reconstruction
    else:
        seeded["reconstruction"] = {"skipped": True, "reason": "claims already exist"}
    return seeded
