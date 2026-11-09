"""Pydantic request schemas. Responses are intentionally explicit dictionaries
so permission-filtered payloads can be assembled by the API layer."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class KBModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterRequest(KBModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    organization_name: str | None = Field(default=None, max_length=160)
    organization_id: str | None = None


class LoginRequest(KBModel):
    email: str
    password: str


class OrganizationCreate(KBModel):
    name: str = Field(min_length=2, max_length=160)


class ProjectCreate(KBModel):
    name: str = Field(min_length=2, max_length=180)
    key: str | None = Field(default=None, max_length=24)
    description: str = ""
    is_demo: bool = False


class ProjectUpdate(KBModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class MemberCreate(KBModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: str = "observer"
    max_clearance: int | None = Field(default=None, ge=0, le=3)
    allowed_claim_types: list[str] | None = None
    allowed_tags: list[str] | None = None


class MemberUpdate(KBModel):
    role: str | None = None
    max_clearance: int | None = Field(default=None, ge=0, le=3)
    allowed_claim_types: list[str] | None = None
    allowed_tags: list[str] | None = None


class SourceTextCreate(KBModel):
    title: str = Field(min_length=2, max_length=240)
    content: str = Field(min_length=1)
    source_type: str = "project_document"
    author: str = ""
    source_date: str | None = None
    sensitivity: int = Field(default=1, ge=0, le=3)
    external_ref: str = ""


class GitHubConnectRequest(KBModel):
    repository: str = Field(min_length=3, max_length=240)
    branch: str = "main"
    max_commits: int = Field(default=10, ge=1, le=50)
    max_issues: int = Field(default=10, ge=0, le=50)
    sensitivity: int = Field(default=1, ge=0, le=3)


class ExtractRequest(KBModel):
    reprocess: bool = False


class ReviewRequest(KBModel):
    action: Literal["approve", "correct", "reject"]
    corrected_statement: str | None = None
    note: str = ""


class ResolveConflictRequest(KBModel):
    resolution_claim_id: str
    note: str = Field(min_length=3)


class RiskUpdate(KBModel):
    status: str | None = None
    severity: str | None = None
    mitigation: str | None = None
    owner: str | None = None


class TaskUpdate(KBModel):
    status: str | None = None
    owner: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class HandoverGenerateRequest(KBModel):
    recipient_user_id: str
    role_key: str | None = None
    title: str | None = None


class HandoverUpdateRequest(KBModel):
    content_json: dict[str, Any] | None = None
    title: str | None = None
    edit_note: str = ""


class HandoverItemUpdate(KBModel):
    action: Literal["acknowledge", "start", "complete"]
    note: str = ""


class AskRequest(KBModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)
