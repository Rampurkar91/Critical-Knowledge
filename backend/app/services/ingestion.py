"""Authorised source ingestion for text, uploads and GitHub."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ai_engine.extractor import parse_source

from ..db import utcnow
from ..models import SourceDocument, User
from ..schemas import GitHubConnectRequest, SourceTextCreate
from ..utils import parse_datetime
from .github import fetch_github_activity, parse_repository
from .permissions import record_audit, sensitivity_value


def extract_upload_text(filename: str, data: bytes) -> tuple[str, str]:
    lower = filename.lower()
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency declared in requirements
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF support requires pypdf") from exc
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No extractable text found in PDF")
        return text, "application/pdf"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload must be UTF-8 text or a text-based PDF") from exc
    if lower.endswith(".json"):
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        mime = "application/json"
    elif lower.endswith(".csv"):
        mime = "text/csv"
    else:
        mime = "text/plain"
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded source is empty")
    return text, mime


def create_source_document(
    db: Session,
    *,
    project_id: str,
    title: str,
    content: str,
    source_type: str,
    author: str,
    external_ref: str,
    sensitivity: int,
    source_timestamp: datetime | None,
    actor_id: str | None,
    is_demo: bool = False,
    mime_type: str = "text/plain",
    metadata_extra: dict[str, Any] | None = None,
    audit_action: str = "source.ingest",
) -> SourceDocument:
    fallback_timestamp = source_timestamp or utcnow()
    actor = db.get(User, actor_id) if actor_id else None
    parsed = parse_source(
        content,
        fallback_title=title,
        fallback_type=source_type,
        fallback_sensitivity=sensitivity,
        fallback_timestamp=fallback_timestamp,
        fallback_external_ref=external_ref,
    )
    declared = sensitivity_value(parsed.meta.sensitivity, sensitivity)
    if declared > sensitivity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document declares a higher classification than selected; choose the correct authorised level",
        )
    effective_sensitivity = max(sensitivity, declared)
    effective_timestamp = parsed.meta.source_timestamp or fallback_timestamp
    sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == project_id, SourceDocument.sha256 == sha256)
        .first()
    )
    if existing:
        setattr(existing, "_kb_created", False)
        record_audit(
            db,
            user=actor,
            project_id=project_id,
            action=audit_action,
            resource_type="source",
            resource_id=existing.id,
            outcome="duplicate",
            details={"title": title, "source_type": source_type},
        )
        return existing

    source = SourceDocument(
        project_id=project_id,
        title=parsed.meta.title or title,
        source_type=parsed.meta.source_type or source_type,
        external_ref=parsed.meta.external_ref or external_ref,
        author=parsed.meta.author or author,
        content=content,
        source_timestamp=effective_timestamp,
        ingested_by=actor_id,
        sensitivity=effective_sensitivity,
        sha256=sha256,
        is_demo=is_demo,
        mime_type=mime_type,
        byte_size=len(content.encode("utf-8")),
        metadata_json={
            "source_ref": parsed.meta.source_ref,
            "sensitivity": effective_sensitivity,
            "declared_source_type": parsed.meta.source_type,
            **(metadata_extra or {}),
        },
    )
    db.add(source)
    db.flush()
    setattr(source, "_kb_created", True)
    record_audit(
        db,
        user=actor,
        project_id=project_id,
        action=audit_action,
        resource_type="source",
        resource_id=source.id,
        details={
            "title": source.title,
            "source_type": source.source_type,
            "sensitivity": effective_sensitivity,
            "is_demo": is_demo,
            "external_ref": source.external_ref[:240],
        },
    )
    return source


def create_text_source(db: Session, project_id: str, actor_id: str, payload: SourceTextCreate) -> SourceDocument:
    return create_source_document(
        db,
        project_id=project_id,
        title=payload.title,
        content=payload.content,
        source_type=payload.source_type,
        author=payload.author,
        external_ref=payload.external_ref,
        sensitivity=payload.sensitivity,
        source_timestamp=parse_datetime(payload.source_date),
        actor_id=actor_id,
        mime_type="text/plain",
    )


def create_upload_source(
    db: Session,
    project_id: str,
    actor_id: str,
    *,
    filename: str,
    data: bytes,
    title: str | None,
    source_type: str,
    author: str,
    sensitivity: int,
    source_date: str | None,
) -> SourceDocument:
    text, mime_type = extract_upload_text(filename, data)
    return create_source_document(
        db,
        project_id=project_id,
        title=title or filename,
        content=text,
        source_type=source_type,
        author=author,
        external_ref=f"upload://{filename}",
        sensitivity=sensitivity,
        source_timestamp=parse_datetime(source_date),
        actor_id=actor_id,
        mime_type=mime_type,
        metadata_extra={"original_filename": filename},
    )


def create_github_sources(
    db: Session,
    project_id: str,
    actor_id: str,
    member,
    payload: GitHubConnectRequest,
) -> dict[str, Any]:
    owner, repo = parse_repository(payload.repository)
    if payload.sensitivity > member.max_clearance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Selected classification exceeds the project member's clearance",
        )
    documents = fetch_github_activity(
        payload.repository,
        payload.branch,
        payload.max_commits,
        payload.max_issues,
        payload.sensitivity,
    )
    created = 0
    duplicates = 0
    for document in documents:
        source = create_source_document(
            db,
            project_id=project_id,
            title=document["title"],
            content=document["content"],
            source_type=document["source_type"],
            author=document["author"],
            external_ref=document["external_ref"],
            sensitivity=document["sensitivity"],
            source_timestamp=document["source_timestamp"],
            actor_id=actor_id,
            mime_type="text/markdown",
            metadata_extra=document["metadata"],
            audit_action="source.github_ingest",
        )
        if getattr(source, "_kb_created", False):
            created += 1
        else:
            duplicates += 1
    record_audit(
        db,
        project_id=project_id,
        action="source.github_connect",
        resource_type="integration",
        details={
            "repository": f"{owner}/{repo}",
            "branch": payload.branch,
            "sources_returned": len(documents),
            "sources_created": created,
            "token_used": bool(os.getenv("GITHUB_TOKEN")),
        },
    )
    return {"repository": f"{owner}/{repo}", "sources_returned": len(documents), "sources_created": created, "duplicates": duplicates}
