"""Sources, extraction, graph, decisions, risks, search and AI answers."""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ai_engine.llm import LLMUnavailable, grounded_answer, llm_configured
from ai_engine.retrieval import retrieve
from knowledge_graph.builder import rebuild_graph

from ..db import get_db
from ..deps import get_current_user
from ..models import (
    Claim,
    EvidenceSpan,
    Handover,
    HandoverItem,
    KnowledgeEdge,
    KnowledgeNode,
    Risk,
    SourceDocument,
    Task,
    User,
)
from ..schemas import (
    AskRequest,
    ExtractRequest,
    GitHubConnectRequest,
    RiskUpdate,
    SourceTextCreate,
    TaskUpdate,
)
from ..services.ingestion import create_github_sources, create_text_source, create_upload_source
from ..services.orchestrator import run_full_reconstruction
from ..services.permissions import (
    assert_clearance,
    evidence_citations,
    member_allowed_tags,
    member_claim_types,
    record_audit,
    require_action,
    role_policy,
    visible_claim_query,
    visible_edge_query,
    visible_node_query,
    visible_risk_query,
    visible_source_query,
    visible_task_query,
)
from ..utils import json_safe
from .common import (
    claim_dict,
    edge_dict,
    guard_text,
    node_dict,
    parse_as_of,
    risk_dict,
    source_dict,
    task_dict,
    visible_refs,
)

router = APIRouter(prefix="/api", tags=["knowledge"])


def _snippet(text: str, query: str, width: int = 220) -> str:
    lowered = text.lower()
    index = lowered.find(query.lower())
    start = max(0, index - 70) if index >= 0 else 0
    return text[start:start + width].replace("\n", " ")


@router.get("/projects/{project_id}/sources")
def list_sources(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "source.view")
    rows = visible_source_query(db, project_id, member).order_by(SourceDocument.source_timestamp.desc()).all()
    items = [source_dict(db, source, member, current_user) for source in rows]
    return {"items": [item for item in items if item], "total": len([item for item in items if item])}


@router.get("/sources/{source_id}/content")
def source_content(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    source = db.get(SourceDocument, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    member = require_action(db, current_user, source.project_id, "source.view")
    if source.sensitivity > member.max_clearance or not source.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    data = source_dict(db, source, member, current_user, include_content=True)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    spans = (
        db.query(EvidenceSpan)
        .filter(EvidenceSpan.source_id == source.id, EvidenceSpan.sensitivity <= member.max_clearance)
        .order_by(EvidenceSpan.start_char.asc())
        .all()
    )
    evidence = []
    for span in spans:
        quote, changed = guard_text(db, source.project_id, member, current_user, span.quote, "source.evidence")
        if changed:
            continue
        evidence.append({
            "id": span.id,
            "quote": quote,
            "start_char": span.start_char,
            "end_char": span.end_char,
            "sensitivity": span.sensitivity,
        })
    data["evidence_spans"] = evidence
    record_audit(
        db,
        user=current_user,
        project_id=source.project_id,
        action="source.view_content",
        resource_type="source",
        resource_id=source.id,
        commit=True,
    )
    return data


@router.get("/evidence/{evidence_id}")
def evidence_detail(
    evidence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    span = db.get(EvidenceSpan, evidence_id)
    if span is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    source = db.get(SourceDocument, span.source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    member = require_action(db, current_user, source.project_id, "knowledge.view")
    if span.sensitivity > member.max_clearance or source.sensitivity > member.max_clearance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    quote, changed = guard_text(db, source.project_id, member, current_user, span.quote, "evidence.quote")
    if changed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    excerpt = source.content[max(0, span.start_char - 120):span.end_char + 120]
    excerpt, _ = guard_text(db, source.project_id, member, current_user, excerpt, "evidence.excerpt")
    return {
        "id": span.id,
        "source": source_dict(db, source, member, current_user),
        "quote": quote,
        "start_char": span.start_char,
        "end_char": span.end_char,
        "excerpt": excerpt,
        "verified_offset": source.content[span.start_char:span.end_char] == span.quote,
    }


@router.post("/projects/{project_id}/sources/text", status_code=status.HTTP_201_CREATED)
def add_text_source(
    project_id: str,
    payload: SourceTextCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "source.ingest")
    assert_clearance(member, payload.sensitivity)
    source = create_text_source(db, project_id, current_user.id, payload)
    db.commit()
    return {
        "source": source_dict(db, source, member, current_user),
        "next_action": "Run POST /api/projects/{id}/extract to reconstruct knowledge.",
    }


@router.post("/projects/{project_id}/sources/upload", status_code=status.HTTP_201_CREATED)
async def upload_source(
    project_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    source_type: str = Form("project_document"),
    author: str = Form(""),
    sensitivity: int = Form(1),
    source_date: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "source.ingest")
    assert_clearance(member, sensitivity)
    data = await file.read()
    source = create_upload_source(
        db,
        project_id,
        current_user.id,
        filename=file.filename or "upload.txt",
        data=data,
        title=title,
        source_type=source_type,
        author=author,
        sensitivity=sensitivity,
        source_date=source_date,
    )
    db.commit()
    return {
        "source": source_dict(db, source, member, current_user),
        "next_action": "Run POST /api/projects/{id}/extract to reconstruct knowledge.",
    }


@router.post("/projects/{project_id}/sources/github/connect")
def connect_github(
    project_id: str,
    payload: GitHubConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "source.connect")
    result = create_github_sources(db, project_id, current_user.id, member, payload)
    db.commit()
    return {**result, "next_action": "Run POST /api/projects/{id}/extract to include the new GitHub evidence."}


@router.post("/projects/{project_id}/extract")
def extract_project(
    project_id: str,
    payload: ExtractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_action(db, current_user, project_id, "knowledge.extract")
    result = run_full_reconstruction(db, project_id, current_user.id, reprocess=payload.reprocess)
    db.commit()
    return result


@router.get("/projects/{project_id}/claims")
def list_claims(
    project_id: str,
    verification_status: str | None = Query(None),
    review_status: str | None = Query(None),
    claim_type: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "knowledge.view")
    query = visible_claim_query(db, project_id, member)
    if verification_status:
        query = query.filter(Claim.verification_status == verification_status)
    if review_status:
        query = query.filter(Claim.review_status == review_status)
    if claim_type:
        query = query.filter(Claim.claim_type == claim_type)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Claim.statement.ilike(like),
            Claim.value.ilike(like),
            Claim.normalized_key.ilike(like),
            Claim.rationale.ilike(like),
        ))
    rows = query.order_by(Claim.priority.asc(), Claim.source_timestamp.desc()).limit(limit).all()
    items = [claim_dict(db, claim, member, current_user) for claim in rows]
    return {"items": [item for item in items if item], "total": len([item for item in items if item])}


@router.get("/claims/{claim_id}/evidence")
def claim_evidence(
    claim_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    member = require_action(db, current_user, claim.project_id, "knowledge.view")
    visible = visible_claim_query(db, claim.project_id, member).filter(Claim.id == claim_id).first()
    if visible is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    citations = evidence_citations(db, claim.id, member)
    safe_citations = []
    for citation in citations:
        quote, changed = guard_text(db, claim.project_id, member, current_user, citation["quote"], "claim.evidence")
        if not changed:
            safe_citations.append({**citation, "quote": quote})
    return {
        "claim": claim_dict(db, claim, member, current_user),
        "evidence": safe_citations,
        "evidence_count": len(safe_citations),
        "score_rationale": claim.score_rationale,
        "score_disclaimer": "Heuristic reliability score, not a calibrated probability.",
    }


@router.get("/projects/{project_id}/graph")
def graph_view(
    project_id: str,
    as_of: str | None = Query(None),
    node_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "graph.view")
    as_of_dt = parse_as_of(as_of)
    node_query = visible_node_query(db, project_id, member).filter(
        KnowledgeNode.valid_from <= as_of_dt,
        or_(KnowledgeNode.valid_to.is_(None), KnowledgeNode.valid_to >= as_of_dt),
    )
    if node_type:
        node_query = node_query.filter(KnowledgeNode.node_type == node_type)
    nodes_rows = node_query.order_by(KnowledgeNode.valid_from.asc()).all()
    nodes = [node_dict(db, node, member, current_user) for node in nodes_rows]
    nodes = [node for node in nodes if node]
    visible_ids = {node["id"] for node in nodes}

    edge_query = visible_edge_query(db, project_id, member, visible_ids).filter(
        KnowledgeEdge.valid_from <= as_of_dt,
        or_(KnowledgeEdge.valid_to.is_(None), KnowledgeEdge.valid_to >= as_of_dt),
    )
    edges = [edge_dict(db, edge, member, current_user) for edge in edge_query.all()]
    edges = [edge for edge in edges if edge and edge["source"] in visible_ids and edge["target"] in visible_ids]

    timeline = [
        {
            "id": node["id"],
            "date": node["valid_from"],
            "label": node["label"],
            "type": node["node_type"],
            "valid_to": node["valid_to"],
        }
        for node in nodes
        if node["node_type"] in {"state", "decision", "task", "risk", "source", "commit", "issue"}
    ]
    timeline.sort(key=lambda item: item["date"] or "")
    authorized_claim_ids = {claim.id for claim in visible_claim_query(db, project_id, member).all()}
    hidden_nodes = db.query(KnowledgeNode).filter(
        KnowledgeNode.project_id == project_id,
        or_(
            KnowledgeNode.sensitivity > member.max_clearance,
            and_(KnowledgeNode.claim_id.isnot(None), KnowledgeNode.claim_id.notin_(authorized_claim_ids)),
        ),
    ).count()
    hidden_edges = db.query(KnowledgeEdge).filter(
        KnowledgeEdge.project_id == project_id,
        or_(
            KnowledgeEdge.sensitivity > member.max_clearance,
            and_(KnowledgeEdge.claim_id.isnot(None), KnowledgeEdge.claim_id.notin_(authorized_claim_ids)),
        ),
    ).count()
    return {
        "as_of": as_of_dt.isoformat() + "Z",
        "nodes": nodes,
        "edges": edges,
        "timeline": timeline,
        "relationship_counts": dict(Counter(edge["relation"] for edge in edges)),
        "hidden_by_policy": {"nodes": hidden_nodes, "edges": hidden_edges},
        "clearance": member.max_clearance,
    }


@router.get("/projects/{project_id}/graph/nodes/{node_id}")
def graph_node_detail(
    project_id: str,
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "graph.view")
    visible_ids = {n.id for n in visible_node_query(db, project_id, member).all()}
    node = visible_node_query(db, project_id, member).filter(KnowledgeNode.id == node_id).first()
    if node is None or node.id not in visible_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    payload = node_dict(db, node, member, current_user)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    citations = evidence_citations(db, node.claim_id, member) if node.claim_id else []
    edges = (
        visible_edge_query(db, project_id, member, visible_ids)
        .filter(or_(KnowledgeEdge.source_node_id == node.id, KnowledgeEdge.target_node_id == node.id))
        .all()
    )
    edge_payloads = [edge_dict(db, edge, member, current_user) for edge in edges]
    edge_payloads = [edge for edge in edge_payloads if edge]
    return {"node": payload, "evidence": citations, "edges": edge_payloads, "evidence_count": len(citations)}


@router.get("/projects/{project_id}/decisions")
def decision_history(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "knowledge.view")
    claims = (
        visible_claim_query(db, project_id, member)
        .filter(Claim.claim_type == "decision")
        .order_by(Claim.source_timestamp.asc())
        .all()
    )
    items = []
    for claim in claims:
        payload = claim_dict(db, claim, member, current_user)
        if not payload:
            continue
        payload["why"] = payload["rationale"]
        payload["supersedes"] = claim.supersedes_ref or None
        payload["superseded_by"] = claim.metadata_json.get("superseded_by")
        payload["dependencies"] = claim.depends_on
        items.append(payload)
    return {"items": items, "total": len(items)}


@router.get("/projects/{project_id}/timeline")
def project_timeline(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "graph.view")
    rows = (
        visible_node_query(db, project_id, member)
        .filter(KnowledgeNode.node_type.in_(["state", "decision", "task", "risk", "commit", "issue", "source"]))
        .order_by(KnowledgeNode.valid_from.asc())
        .all()
    )
    events = [node_dict(db, node, member, current_user) for node in rows]
    return {"items": [event for event in events if event], "total": len([event for event in events if event])}


@router.get("/projects/{project_id}/risks")
def risk_manager(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "knowledge.view")
    risks = [risk_dict(db, r, member, current_user) for r in visible_risk_query(db, project_id, member).order_by(Risk.source_timestamp.desc()).all()]
    blockers = [claim_dict(db, c, member, current_user) for c in visible_claim_query(db, project_id, member).filter(Claim.claim_type == "blocker").all()]
    dependencies = [claim_dict(db, c, member, current_user) for c in visible_claim_query(db, project_id, member).filter(Claim.claim_type == "dependency").all()]
    refs = visible_refs(db, project_id, member)
    tasks = [task_dict(db, t, member, current_user, refs) for t in visible_task_query(db, project_id, member).all()]
    return {
        "risks": [r for r in risks if r],
        "blockers": [b for b in blockers if b],
        "dependencies": [d for d in dependencies if d],
        "tasks": [t for t in tasks if t],
    }


@router.patch("/risks/{risk_id}")
def update_risk(
    risk_id: str,
    payload: RiskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    member = require_action(db, current_user, risk.project_id, "risk.manage")
    if visible_risk_query(db, risk.project_id, member).filter(Risk.id == risk.id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    before = {"status": risk.status, "severity": risk.severity, "owner": risk.owner, "mitigation": risk.mitigation}
    for field in ("status", "severity", "mitigation", "owner"):
        value = getattr(payload, field)
        if value is not None:
            setattr(risk, field, value)
    record_audit(
        db,
        user=current_user,
        project_id=risk.project_id,
        action="risk.update",
        resource_type="risk",
        resource_id=risk.id,
        details={"before": before, "after": payload.model_dump(exclude_none=True)},
    )
    db.commit()
    return risk_dict(db, risk, member, current_user)


@router.get("/projects/{project_id}/tasks")
def list_tasks(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "knowledge.view")
    refs = visible_refs(db, project_id, member)
    rows = visible_task_query(db, project_id, member).order_by(Task.priority.asc()).all()
    items = [task_dict(db, t, member, current_user, refs) for t in rows]
    return {"items": [item for item in items if item], "total": len([item for item in items if item])}


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    member = require_action(db, current_user, task.project_id, "task.update")
    if visible_task_query(db, task.project_id, member).filter(Task.id == task.id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if member.role not in {"project_manager", "tech_lead"}:
        linked = (
            db.query(HandoverItem)
            .join(Handover, HandoverItem.handover_id == Handover.id)
            .filter(
                HandoverItem.task_id == task.id,
                Handover.recipient_user_id == current_user.id,
                Handover.status.in_(["shared", "acknowledged", "in_progress", "completed"]),
            )
            .first()
        )
        if linked is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Task is not part of your shared handover")
    before = {"status": task.status, "owner": task.owner, "priority": task.priority}
    for field in ("status", "owner", "priority"):
        value = getattr(payload, field)
        if value is not None:
            setattr(task, field, value)
    if task.status == "done":
        task.continuation_status = "completed"
    record_audit(
        db,
        user=current_user,
        project_id=task.project_id,
        action="task.update",
        resource_type="task",
        resource_id=task.id,
        details={"before": before, "after": payload.model_dump(exclude_none=True)},
    )
    db.commit()
    refs = visible_refs(db, task.project_id, member)
    return task_dict(db, task, member, current_user, refs)


@router.get("/projects/{project_id}/search")
def search_project(
    project_id: str,
    q: str = Query(..., min_length=2, max_length=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "search")
    safe_query, query_guard_applied = guard_text(db, project_id, member, current_user, q, "search.query")
    like = f"%{safe_query}%"
    unrestricted_abac = "*" in member_claim_types(member) and "*" in member_allowed_tags(member)
    # Members with claim-type/tag restrictions never get raw full-document
    # snippets: those can contain claims outside their ABAC policy. They see
    # authorised source metadata and separately filtered claim results only.
    source_condition = (
        or_(SourceDocument.title.ilike(like), SourceDocument.content.ilike(like))
        if unrestricted_abac
        else SourceDocument.title.ilike(like)
    )
    source_rows = visible_source_query(db, project_id, member).filter(
        source_condition
    ).limit(20).all()
    claim_rows = visible_claim_query(db, project_id, member).filter(
        or_(
            Claim.statement.ilike(like),
            Claim.value.ilike(like),
            Claim.normalized_key.ilike(like),
            Claim.rationale.ilike(like),
        )
    ).limit(30).all()
    source_results = []
    for source in source_rows:
        base = source_dict(db, source, member, current_user)
        if not base:
            continue
        snippet_text = _snippet(source.content, safe_query) if unrestricted_abac else f"Authorised source: {base['title']}"
        snippet, changed = guard_text(db, project_id, member, current_user, snippet_text, "search.source_snippet")
        if changed:
            continue
        source_results.append({**base, "snippet": snippet})
    claim_results = [claim_dict(db, claim, member, current_user) for claim in claim_rows]
    claim_results = [item for item in claim_results if item]
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="search",
        resource_type="project",
        resource_id=project_id,
        details={
            "query_prefix": safe_query[:80],
            "source_results": len(source_results),
            "claim_results": len(claim_results),
            "query_guard_applied": query_guard_applied,
        },
        commit=True,
    )
    return {
        "query": safe_query,
        "sources": source_results,
        "claims": claim_results,
        "clearance": member.max_clearance,
        "query_guard_applied": query_guard_applied,
    }


@router.post("/projects/{project_id}/ask")
def ask_project(
    project_id: str,
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    member = require_action(db, current_user, project_id, "ask")
    safe_question, question_guard_applied = guard_text(db, project_id, member, current_user, payload.question, "ask.question")
    results = retrieve(db, project_id, member, safe_question, payload.top_k)
    safe_results = []
    for result in results:
        quote, changed = guard_text(db, project_id, member, current_user, result["quote"], "ask.evidence")
        statement, statement_changed = guard_text(db, project_id, member, current_user, result["statement"], "ask.statement")
        if changed or statement_changed:
            continue
        safe_results.append({**result, "quote": quote, "statement": statement})

    if not safe_results:
        answer = "I do not have authorised evidence for that question. No answer was generated without supporting sources."
        provider = "deterministic-local"
    else:
        lines = ["Based on the authorised evidence:"]
        for item in safe_results[:3]:
            lines.append(f"- {item['statement']} (source {item['source_ref']}).")
        statuses = {item["verification_status"] for item in safe_results}
        if "Conflicting" in statuses:
            lines.append("Uncertainty: conflicting authorised records were detected and require manager resolution.")
        if any(status in {"Needs Review", "Unsupported", "Outdated"} for status in statuses):
            lines.append("Uncertainty: some retrieved evidence is not approved, is unsupported, or is outdated.")
        deterministic = "\n".join(lines)
        if llm_configured():
            try:
                answer = grounded_answer(safe_question, safe_results)
                answer += "\n\nThe optional LLM received only the authorised evidence above; verify every statement against the citations."
                provider = settings_llm_model()
            except LLMUnavailable:
                answer = deterministic
                provider = "deterministic-fallback"
        else:
            answer = deterministic
            provider = "deterministic-local"

    answer, leakage_guard = guard_text(db, project_id, member, current_user, answer, "ask.answer")
    citations = [
        {
            "claim_id": item["claim_id"],
            "external_ref": item["external_ref"],
            "source_id": item["source_id"],
            "source_ref": item["source_ref"],
            "source_title": item["source_title"],
            "quote": item["quote"],
            "start_char": item["start_char"],
            "end_char": item["end_char"],
            "verification_status": item["verification_status"],
            "retrieval_score": item["retrieval_score"],
        }
        for item in safe_results
    ]
    record_audit(
        db,
        user=current_user,
        project_id=project_id,
        action="ask",
        resource_type="ai_response",
        details={
            "provider": provider,
            "question_prefix": safe_question[:80],
            "evidence_count": len(citations),
            "leakage_guard_applied": leakage_guard or question_guard_applied,
        },
        commit=True,
    )
    return {
        "answer": answer,
        "provider": provider,
        "citations": citations,
        "clearance": member.max_clearance,
        "leakage_guard_applied": leakage_guard or question_guard_applied,
        "question_guard_applied": question_guard_applied,
        "uncertainty": "Answers are extractive and evidence-linked; review statuses are shown rather than hidden.",
        "score_disclaimer": "Retrieval scores and reliability scores are heuristics, not calibrated probabilities.",
    }


def settings_llm_model() -> str:
    from ..config import settings
    return f"openai-compatible:{settings.llm_model}"
