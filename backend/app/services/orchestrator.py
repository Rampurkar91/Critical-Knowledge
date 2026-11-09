"""Coordinates extraction → graph reconstruction → verification."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ai_engine.extractor import materialize_source, source_sensitivity_map
from knowledge_graph.builder import rebuild_graph
from verification_engine.engine import run_verification

from ..models import SourceDocument, User
from .permissions import record_audit


def run_full_reconstruction(
    db: Session,
    project_id: str,
    actor_id: str | None,
    reprocess: bool = False,
) -> dict[str, Any]:
    all_sources = (
        db.query(SourceDocument)
        .filter(
            SourceDocument.project_id == project_id,
            SourceDocument.is_active.is_(True),
        )
        .all()
    )
    sensitivity_map = source_sensitivity_map([source.content for source in all_sources])
    query = db.query(SourceDocument).filter(
        SourceDocument.project_id == project_id,
        SourceDocument.is_active.is_(True),
    )
    if not reprocess:
        query = query.filter(SourceDocument.processed_at.is_(None))
    sources = query.order_by(SourceDocument.source_timestamp.asc(), SourceDocument.title.asc()).all()

    results = [
        materialize_source(
            db,
            source,
            actor_id,
            reprocess=reprocess,
            global_sensitivity_by_ref=sensitivity_map,
        )
        for source in sources
    ]
    first_graph = rebuild_graph(db, project_id)
    verification = run_verification(db, project_id)
    # A second build propagates validation results (e.g. superseded valid_to).
    graph = rebuild_graph(db, project_id)
    actor = db.get(User, actor_id) if actor_id else None
    record_audit(
        db,
        user=actor,
        project_id=project_id,
        action="knowledge.extract",
        resource_type="project",
        resource_id=project_id,
        details={
            "sources_processed": len([r for r in results if not r.get("skipped")]),
            "claims_created": sum(r.get("claims", 0) for r in results),
            "reprocess": reprocess,
            "graph_nodes": graph["nodes"],
            "graph_edges": graph["edges"],
            "verification": verification,
        },
    )
    db.flush()
    return {
        "sources_processed": len([r for r in results if not r.get("skipped")]),
        "sources_total": len(sources),
        "claims_created": sum(r.get("claims", 0) for r in results),
        "evidence_links": sum(r.get("evidence_links", 0) for r in results),
        "source_results": results,
        "graph": graph,
        "graph_before_verification": first_graph,
        "verification": verification,
    }
