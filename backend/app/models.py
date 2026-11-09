"""SQLAlchemy data model for KnowledgeBridge.

Sensitivity is an integer classification level on every retrievable object:
0 public, 1 internal, 2 confidential, 3 restricted. Permission-aware queries
filter on it before any content is serialised.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow
from .utils import new_id


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("org"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("usr"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    system_role: Mapped[str] = mapped_column(String(40), default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("prj"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_project_key"),)


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("mem"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    max_clearance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allowed_claim_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        Index("ix_member_project_role", "project_id", "role"),
    )


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("src"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    author: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_timestamp: Mapped[Any] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    ingested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    processed_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(120), default="text/plain", nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "sha256", name="uq_source_hash"),
        Index("ix_source_project_type", "project_id", "source_type"),
    )


class EvidenceSpan(Base):
    __tablename__ = "evidence_spans"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("evd"))
    source_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("clm"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_ref: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    subject: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    status_label: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    depends_on: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    role_scope: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    source_timestamp: Mapped[Any] = mapped_column(DateTime, nullable=False)
    extracted_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    extracted_by: Mapped[str] = mapped_column(String(80), default="deterministic-extractor", nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="Needs Review", nullable=False, index=True)
    reliability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_rationale: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supersedes_claim_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_ref: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "external_ref", "version", name="uq_claim_version"),
        Index("ix_claim_project_status", "project_id", "verification_status", "is_active"),
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cle"))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    evidence_span_id: Mapped[str] = mapped_column(ForeignKey("evidence_spans.id"), index=True)
    relation: Mapped[str] = mapped_column(String(30), default="supports", nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    __table_args__ = (UniqueConstraint("claim_id", "evidence_span_id", name="uq_claim_span"),)


class ClaimReview(Base):
    __tablename__ = "claim_reviews"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rev"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    old_statement: Mapped[str] = mapped_column(Text, default="", nullable=False)
    new_statement: Mapped[str] = mapped_column(Text, default="", nullable=False)
    old_status: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    new_status: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)


class ConflictRecord(Base):
    __tablename__ = "conflict_records"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cnf"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    claim_a_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    claim_b_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    value_a: Mapped[str] = mapped_column(Text, nullable=False)
    value_b: Mapped[str] = mapped_column(Text, nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False, index=True)
    resolution_claim_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    detected_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "claim_a_id", "claim_b_id", name="uq_conflict_pair"),
    )


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("nod"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    node_key: Mapped[str] = mapped_column(String(240), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    valid_from: Mapped[Any] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "node_key", name="uq_node_key"),)


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("edg"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    edge_key: Mapped[str] = mapped_column(String(300), nullable=False)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), index=True)
    target_node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), index=True)
    relation: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(180), default="", nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    valid_from: Mapped[Any] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    evidence_span_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_spans.id"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "edge_key", name="uq_edge_key"),)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("tsk"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    external_ref: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    owner: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    depends_on: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    source_timestamp: Mapped[Any] = mapped_column(DateTime, nullable=False)
    continuation_status: Mapped[str] = mapped_column(String(40), default="not_started", nullable=False)
    completed_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "external_ref", name="uq_task_ref"),)


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rsk"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    external_ref: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="medium", nullable=False)
    likelihood: Mapped[str] = mapped_column(String(30), default="medium", nullable=False)
    owner: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False, index=True)
    mitigation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    source_timestamp: Mapped[Any] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "external_ref", name="uq_risk_ref"),)


class Handover(Base):
    __tablename__ = "handovers"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("hov"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_role: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    generated_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    shared_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clearance_applied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applied_filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    edit_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prep_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class HandoverItem(Base):
    __tablename__ = "handover_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("hit"))
    handover_id: Mapped[str] = mapped_column(ForeignKey("handovers.id"), index=True)
    claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    sensitivity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    acknowledged_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[Any | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), default="anonymous", nullable=False)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    resource_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), default="allowed", nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
