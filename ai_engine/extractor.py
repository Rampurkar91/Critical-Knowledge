"""Deterministic, evidence-preserving knowledge extraction.

The default engine parses explicit project-activity records and also recognises
a small set of natural-language markers. Every generated claim carries an exact
character-offset evidence span. An unsupported claim is deliberately created
without a claim-to-evidence link; the engine never invents a citation.

This is not a trained probabilistic model. It is a transparent local extractor
so the demonstration and tests work without an API key. An optional LLM adapter
is provided separately for deployment, but is never required to produce claims.
"""
from __future__ import annotations

import hashlib
import re
import shlex
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.db import utcnow
from backend.app.models import (
    Claim,
    ClaimEvidence,
    EvidenceSpan,
    Risk,
    SourceDocument,
    Task,
)
from backend.app.services.permissions import sensitivity_value
from backend.app.utils import canonical, parse_datetime, parse_date

TRUE_VALUES = {"1", "true", "yes", "y", "on"}


@dataclass
class SourceMeta:
    source_ref: str
    title: str
    source_type: str
    author: str
    external_ref: str
    source_timestamp: datetime
    sensitivity: int


@dataclass
class ExtractedRecord:
    external_ref: str
    claim_type: str
    statement: str
    normalized_key: str
    normalized_value: str
    subject: str
    value: str
    owner: str
    status_label: str
    due_date: str | None
    depends_on: list[str]
    tags: list[str]
    role_scope: list[str]
    sensitivity: int
    source_timestamp: datetime
    rationale: str
    priority: int
    supersedes_ref: str
    unsupported: bool
    evidence_quote: str
    evidence_start: int
    evidence_end: int
    node_type: str
    node_key: str
    record_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    meta: SourceMeta
    records: list[ExtractedRecord]


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def parse_front_matter(content: str, fallback_title: str = "Uploaded source") -> dict[str, str]:
    meta: dict[str, str] = {}
    if not content.startswith("---"):
        return meta
    lines = content.splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = _strip_quotes(value)
    meta.setdefault("title", fallback_title)
    return meta


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUE_VALUES


def _int(value: str | None, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_fields(line: str) -> tuple[str, dict[str, str]]:
    tokens = shlex.split(line.strip(), posix=True)
    if not tokens or not tokens[0].startswith("@"):
        raise ValueError("Not a structured record line")
    kind = tokens[0][1:].strip().lower()
    fields: dict[str, str] = {}
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key.strip().lower()] = value.strip()
    return kind, fields


def _source_meta(content: str, fallback_title: str, fallback_type: str, fallback_sensitivity: int, fallback_timestamp: datetime, fallback_external_ref: str = "") -> SourceMeta:
    front = parse_front_matter(content, fallback_title)
    source_ref = front.get("id") or "SRC-" + hashlib.sha256(content.encode()).hexdigest()[:8].upper()
    return SourceMeta(
        source_ref=source_ref,
        title=front.get("title", fallback_title),
        source_type=front.get("type", fallback_type),
        author=front.get("author", ""),
        external_ref=front.get("external_ref", fallback_external_ref),
        source_timestamp=parse_datetime(front.get("date")) or fallback_timestamp,
        sensitivity=(
            sensitivity_value(front["sensitivity"], fallback_sensitivity)
            if front.get("sensitivity")
            else fallback_sensitivity
        ),
    )


def parse_source(
    content: str,
    *,
    fallback_title: str = "Uploaded source",
    fallback_type: str = "project_document",
    fallback_sensitivity: int = 1,
    fallback_timestamp: datetime | None = None,
    fallback_external_ref: str = "",
) -> ParseResult:
    base_time = fallback_timestamp or utcnow()
    meta = _source_meta(content, fallback_title, fallback_type, fallback_sensitivity, base_time, fallback_external_ref)
    records: list[ExtractedRecord] = []
    offset = 0
    for raw_line in content.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_start = offset
        offset += len(raw_line)
        stripped = line.strip()
        if not stripped.startswith("@"):
            continue
        try:
            kind, f = _parse_fields(stripped)
        except ValueError:
            continue
        external_ref = f.get("id") or f"{kind.upper()}-{hashlib.sha1(stripped.encode()).hexdigest()[:8].upper()}"
        record_time = parse_datetime(f.get("date")) or meta.source_timestamp
        sensitivity = max(meta.sensitivity, sensitivity_value(f.get("sensitivity"), meta.sensitivity))
        tags = _split_list(f.get("tags") or f.get("labels"))
        role_scope = _split_list(f.get("role_scope"))
        depends_on = _split_list(f.get("depends_on"))
        priority = _int(f.get("priority"), 3)
        unsupported = _bool(f.get("unsupported")) or _bool(f.get("evidence_false"))
        supersedes_ref = f.get("supersedes", "").strip()
        rationale = f.get("rationale") or f.get("reason") or f.get("description") or ""
        owner = f.get("owner", "").strip()
        status_label = f.get("status", "").strip()
        due_date = parse_date(f.get("due"))
        common = {
            "external_ref": external_ref,
            "owner": owner,
            "status_label": status_label,
            "due_date": due_date,
            "depends_on": depends_on,
            "tags": tags,
            "role_scope": role_scope,
            "sensitivity": sensitivity,
            "source_timestamp": record_time,
            "priority": priority,
            "supersedes_ref": supersedes_ref,
            "unsupported": unsupported,
            "evidence_quote": line,
            "evidence_start": line_start,
            "evidence_end": line_start + len(line),
            "record_kind": kind,
        }

        if kind == "task":
            title = f.get("title", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="task",
                statement=f"Task {external_ref}: {title}. Status: {status_label or 'unknown'}. Owner: {owner or 'unassigned'}.",
                normalized_key=f"task.{external_ref}.status",
                normalized_value=canonical(status_label or "unknown"),
                subject=external_ref,
                value=status_label or "unknown",
                rationale=rationale,
                node_type="task",
                node_key=f"task:{external_ref}",
                metadata={"title": title},
            ))
        elif kind == "decision":
            key = f.get("key", external_ref)
            value = f.get("value", "")
            records.append(ExtractedRecord(
                **common,
                claim_type="decision",
                statement=f"Decision {external_ref}: {key} = {value}. Reason: {rationale or 'not recorded'}.",
                normalized_key=key,
                normalized_value=canonical(value),
                subject=key,
                value=value,
                rationale=rationale,
                node_type="decision",
                node_key=f"decision:{external_ref}",
                metadata={"title": f"{key} — {value}", "decision_key": key},
            ))
        elif kind == "risk":
            title = f.get("title", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="risk",
                statement=f"Risk {external_ref}: {title}. Severity: {f.get('severity', 'medium')}. Status: {status_label or 'open'}.",
                normalized_key=f"risk.{external_ref}.status",
                normalized_value=canonical(status_label or "open"),
                subject=external_ref,
                value=status_label or "open",
                rationale=rationale,
                node_type="risk",
                node_key=f"risk:{external_ref}",
                metadata={
                    "title": title,
                    "description": f.get("description", ""),
                    "severity": f.get("severity", "medium"),
                    "likelihood": f.get("likelihood", "medium"),
                    "mitigation": f.get("mitigation", ""),
                },
            ))
        elif kind == "blocker":
            title = f.get("title", external_ref)
            blocked_task = f.get("blocked_task", "")
            records.append(ExtractedRecord(
                **common,
                claim_type="blocker",
                statement=f"Blocker {external_ref}: {title}. Blocks: {blocked_task or 'not recorded'}. Reason: {rationale}.",
                normalized_key=f"blocker.{external_ref}.status",
                normalized_value=canonical(status_label or "open"),
                subject=external_ref,
                value=status_label or "open",
                rationale=rationale,
                node_type="blocker",
                node_key=f"blocker:{external_ref}",
                metadata={"title": title, "blocked_task": blocked_task},
            ))
        elif kind == "question":
            question = f.get("question", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="unresolved_question",
                statement=f"Open question {external_ref}: {question}. Owner: {owner or 'unassigned'}.",
                normalized_key=f"question.{external_ref}.status",
                normalized_value=canonical(status_label or "open"),
                subject=external_ref,
                value=status_label or "open",
                rationale=rationale,
                node_type="question",
                node_key=f"question:{external_ref}",
                metadata={"title": question},
            ))
        elif kind == "contact":
            name = f.get("name", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="contact",
                statement=f"Contact {external_ref}: {name}, {f.get('role', 'team member')}. Expertise: {f.get('expertise', 'not recorded')}.",
                normalized_key=f"contact.{external_ref}.name",
                normalized_value=canonical(name),
                subject=external_ref,
                value=name,
                rationale=rationale,
                node_type="contact",
                node_key=f"contact:{external_ref}",
                metadata={"title": name, "channel": f.get("channel", ""), "expertise": f.get("expertise", ""), "contact_role": f.get("role", "")},
            ))
        elif kind == "change":
            key = f.get("key", external_ref)
            value = f.get("value", "")
            records.append(ExtractedRecord(
                **common,
                claim_type="state_change",
                statement=f"State change {external_ref}: {key} changed from {f.get('from', 'unknown')} to {value}. Reason: {rationale}.",
                normalized_key=f"state.{key}",
                normalized_value=canonical(value),
                subject=key,
                value=value,
                rationale=rationale,
                node_type="state",
                node_key=f"state:{external_ref}",
                metadata={"title": f"{key} → {value}", "state_key": key, "from_value": f.get("from", "")},
            ))
        elif kind == "fact":
            key = f.get("key", external_ref)
            value = f.get("value", "")
            records.append(ExtractedRecord(
                **common,
                claim_type=f.get("claim_type", "state_change"),
                statement=f"Recorded fact {external_ref}: {key} = {value}. Reason: {rationale}.",
                normalized_key=key,
                normalized_value=canonical(value),
                subject=f.get("subject", key),
                value=value,
                rationale=rationale,
                node_type="fact",
                node_key=f"fact:{external_ref}",
                metadata={"title": f"{key} — {value}", "fact_key": key},
            ))
        elif kind == "commit":
            message = f.get("message", "")
            sha = f.get("sha", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="state_change",
                statement=f"Commit {sha}: {message}. Author: {f.get('author', owner or 'unknown')}.",
                normalized_key=f"commit.{external_ref}.status",
                normalized_value=canonical(message),
                subject=sha,
                value=message,
                rationale=rationale,
                node_type="commit",
                node_key=f"commit:{external_ref}",
                metadata={"title": message, "sha": sha, "files": f.get("files", "")},
            ))
        elif kind == "issue":
            title = f.get("title", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="unresolved_question",
                statement=f"Repository issue {external_ref}: {title}. Status: {status_label or 'open'}. Owner: {owner or 'unassigned'}.",
                normalized_key=f"issue.{external_ref}.status",
                normalized_value=canonical(status_label or "open"),
                subject=external_ref,
                value=status_label or "open",
                rationale=rationale,
                node_type="issue",
                node_key=f"issue:{external_ref}",
                metadata={"title": title},
            ))
        elif kind == "unfinished":
            task_ref = f.get("task", "")
            detail = f.get("detail", "")
            records.append(ExtractedRecord(
                **common,
                claim_type="unfinished_work",
                statement=f"Unfinished work {external_ref}: {detail}. Task: {task_ref}. Status: {status_label or 'open'}.",
                normalized_key=f"unfinished.{external_ref}.status",
                normalized_value=canonical(status_label or "open"),
                subject=external_ref,
                value=status_label or "open",
                rationale=rationale,
                node_type="unfinished",
                node_key=f"unfinished:{external_ref}",
                metadata={"title": detail, "task": task_ref},
            ))
        elif kind == "next":
            title = f.get("title", external_ref)
            records.append(ExtractedRecord(
                **common,
                claim_type="next_action",
                statement=f"Recommended next action {external_ref}: {title}. Priority: {priority}.",
                normalized_key=f"next_action.{external_ref}.title",
                normalized_value=canonical(title),
                subject=external_ref,
                value=title,
                rationale=rationale,
                node_type="next_action",
                node_key=f"next_action:{external_ref}",
                metadata={"title": title},
            ))
        else:
            # Unknown structured record types are ignored rather than guessed.
            continue

    # Explicit dependency claims are derived only from recorded depends_on fields.
    sensitivity_by_ref = {r.external_ref: r.sensitivity for r in records}
    dependency_records: list[ExtractedRecord] = []
    for parent in list(records):
        for target_ref in parent.depends_on:
            target_sensitivity = sensitivity_by_ref.get(target_ref, parent.sensitivity)
            dep_ref = f"DEP-{parent.external_ref}-{target_ref}".replace("|", "-")
            dependency_records.append(ExtractedRecord(
                external_ref=dep_ref,
                claim_type="dependency",
                statement=f"{parent.external_ref} depends on {target_ref}.",
                normalized_key=f"dependency.{parent.external_ref}.{target_ref}",
                normalized_value=canonical(target_ref),
                subject=parent.external_ref,
                value=target_ref,
                owner=parent.owner,
                status_label="recorded",
                due_date=parent.due_date,
                depends_on=[],
                tags=parent.tags,
                role_scope=parent.role_scope,
                sensitivity=max(parent.sensitivity, target_sensitivity),
                source_timestamp=parent.source_timestamp,
                rationale=f"Explicit depends_on field in {parent.external_ref}.",
                priority=parent.priority,
                supersedes_ref="",
                unsupported=False,
                evidence_quote=parent.evidence_quote,
                evidence_start=parent.evidence_start,
                evidence_end=parent.evidence_end,
                node_type="dependency",
                node_key=f"dependency:{dep_ref}",
                record_kind="dependency",
                metadata={"parent_ref": parent.external_ref, "target_ref": target_ref},
            ))
    records.extend(dependency_records)
    return ParseResult(meta=meta, records=records)


def _upsert_task(db: Session, project_id: str, claim: Claim, rec: ExtractedRecord) -> None:
    task = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.external_ref == rec.external_ref)
        .first()
    )
    if task is None:
        task = Task(project_id=project_id, external_ref=rec.external_ref)
        db.add(task)
    task.claim_id = claim.id
    task.title = rec.metadata.get("title", rec.external_ref)
    task.owner = rec.owner
    task.status = rec.status_label or "open"
    task.priority = rec.priority
    task.due_date = rec.due_date
    task.depends_on = rec.depends_on
    task.tags = rec.tags
    task.sensitivity = rec.sensitivity
    task.source_timestamp = rec.source_timestamp
    task.continuation_status = "completed" if task.status == "done" else "not_started"
    task.completed_at = utcnow() if task.status == "done" else None


def _upsert_risk(db: Session, project_id: str, claim: Claim, rec: ExtractedRecord) -> None:
    risk = (
        db.query(Risk)
        .filter(Risk.project_id == project_id, Risk.external_ref == rec.external_ref)
        .first()
    )
    if risk is None:
        risk = Risk(project_id=project_id, external_ref=rec.external_ref)
        db.add(risk)
    risk.claim_id = claim.id
    risk.title = rec.metadata.get("title", rec.external_ref)
    risk.description = rec.metadata.get("description", rec.rationale)
    risk.severity = rec.metadata.get("severity", "medium")
    risk.likelihood = rec.metadata.get("likelihood", "medium")
    risk.owner = rec.owner
    risk.status = rec.status_label or "open"
    risk.mitigation = rec.metadata.get("mitigation", "")
    risk.sensitivity = rec.sensitivity
    risk.source_timestamp = rec.source_timestamp


def source_sensitivity_map(contents: list[str]) -> dict[str, int]:
    """Build a project-wide ref -> classification map from all active sources.

    Dependency references can cross source boundaries. Parsing each source in
    isolation would otherwise classify a dependency on a restricted record as
    internal, which could leak the restricted ref through a graph label.
    """
    result: dict[str, int] = {}
    for content in contents:
        front = parse_front_matter(content, "")
        base = sensitivity_value(front.get("sensitivity"), 1)
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("@"):
                continue
            try:
                _, fields = _parse_fields(stripped)
            except ValueError:
                continue
            ref = fields.get("id", "").strip()
            if not ref:
                continue
            level = max(base, sensitivity_value(fields.get("sensitivity"), base))
            result[ref] = max(result.get(ref, 0), level)
    return result


def materialize_source(
    db: Session,
    source: SourceDocument,
    actor_id: str | None,
    reprocess: bool = False,
    global_sensitivity_by_ref: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Turn one source document into claims, evidence links, tasks and risks."""
    if source.processed_at and not reprocess:
        return {"source_id": source.id, "skipped": True, "claims": 0}

    parsed = parse_source(
        source.content,
        fallback_title=source.title,
        fallback_type=source.source_type,
        fallback_sensitivity=source.sensitivity,
        fallback_timestamp=source.source_timestamp,
        fallback_external_ref=source.external_ref,
    )
    if global_sensitivity_by_ref:
        # Cross-source dependency targets inherit the highest known target
        # classification; their labels/evidence must not reveal a hidden ref.
        for record in parsed.records:
            if record.claim_type == "dependency":
                target_ref = record.metadata.get("target_ref")
                target_sensitivity = global_sensitivity_by_ref.get(target_ref, record.sensitivity)
                record.sensitivity = max(record.sensitivity, target_sensitivity)

    source_ref = source.metadata_json.get("source_ref") or parsed.meta.source_ref
    source.metadata_json = {
        **source.metadata_json,
        "source_ref": source_ref,
        "parsed_title": parsed.meta.title,
        "parsed_type": parsed.meta.source_type,
        "parsed_date": parsed.meta.source_timestamp.isoformat() + "Z",
        "record_count": len(parsed.records),
    }

    if reprocess:
        previous = db.query(Claim).filter(Claim.project_id == source.project_id).all()
        # JSON filtering is database-specific; filter in Python for portability.
        for old in previous:
            if old.metadata_json.get("source_id") == source.id:
                old.is_active = False
                old.verification_status = "Outdated"

    existing_versions: dict[str, int] = {}
    for claim in db.query(Claim).filter(Claim.project_id == source.project_id).all():
        existing_versions[claim.external_ref] = max(existing_versions.get(claim.external_ref, 0), claim.version)

    created = 0
    evidence_links = 0
    counts: dict[str, int] = {}
    for rec in parsed.records:
        version = existing_versions.get(rec.external_ref, 0) + 1
        existing_versions[rec.external_ref] = version
        status = "Unsupported" if rec.unsupported else "Needs Review"
        claim = Claim(
            project_id=source.project_id,
            external_ref=rec.external_ref,
            claim_type=rec.claim_type,
            statement=rec.statement,
            normalized_key=rec.normalized_key,
            normalized_value=rec.normalized_value,
            subject=rec.subject,
            value=rec.value,
            owner=rec.owner,
            status_label=rec.status_label,
            due_date=rec.due_date,
            depends_on=rec.depends_on,
            tags=rec.tags,
            role_scope=rec.role_scope,
            sensitivity=rec.sensitivity,
            source_timestamp=rec.source_timestamp,
            extracted_by=actor_id or "deterministic-extractor",
            review_status="pending",
            verification_status=status,
            reliability_score=0,
            score_rationale=["Awaiting verification run; no heuristic score has been assigned yet."],
            is_active=True,
            version=version,
            supersedes_ref=rec.supersedes_ref,
            rationale=rec.rationale,
            priority=rec.priority,
            metadata_json={
                **rec.metadata,
                "source_id": source.id,
                "source_ref": source_ref,
                "node_type": rec.node_type,
                "node_key": rec.node_key,
                "record_kind": rec.record_kind,
                "unsupported": rec.unsupported,
            },
        )
        db.add(claim)
        db.flush()
        created += 1
        counts[rec.claim_type] = counts.get(rec.claim_type, 0) + 1

        if not rec.unsupported:
            span = EvidenceSpan(
                source_id=source.id,
                start_char=rec.evidence_start,
                end_char=rec.evidence_end,
                quote=rec.evidence_quote,
                sensitivity=rec.sensitivity,
            )
            db.add(span)
            db.flush()
            db.add(ClaimEvidence(claim_id=claim.id, evidence_span_id=span.id, relation="supports", weight=100))
            evidence_links += 1

        if rec.claim_type == "task":
            _upsert_task(db, source.project_id, claim, rec)
        elif rec.claim_type == "risk":
            _upsert_risk(db, source.project_id, claim, rec)

    source.processed_at = utcnow()
    db.flush()
    return {
        "source_id": source.id,
        "source_ref": source_ref,
        "skipped": False,
        "claims": created,
        "evidence_links": evidence_links,
        "claim_type_counts": counts,
    }
