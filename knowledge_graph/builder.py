"""Temporal project knowledge graph construction.

Nodes and edges are bitemporal-lite: each has `valid_from` and an optional
`valid_to`. Classification is propagated with a max() rule, so an internal task
that depends on a restricted decision produces a restricted edge — the edge is
not visible to a lower-clearance user.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import (
    Claim,
    ClaimEvidence,
    EvidenceSpan,
    KnowledgeEdge,
    KnowledgeNode,
    SourceDocument,
)
from backend.app.utils import parse_datetime


def _person_key(name: str) -> str:
    return f"person:{name.strip()}"


def _node_for_ref(ref: str, nodes_by_ref: dict[str, KnowledgeNode]) -> KnowledgeNode | None:
    return nodes_by_ref.get(ref)


def _infer_node_key(ref: str) -> str:
    prefixes = {
        "KB-": "task",
        "DEC-": "decision",
        "RISK-": "risk",
        "BLK-": "blocker",
        "Q-": "question",
        "C-": "contact",
        "CHG-": "state",
        "GIT-": "commit",
        "GH-": "issue",
        "UF-": "unfinished",
        "NA-": "next_action",
        "F-": "fact",
    }
    for prefix, node_type in prefixes.items():
        if ref.startswith(prefix):
            return f"{node_type}:{ref}"
    return f"unknown:{ref}"


def rebuild_graph(db: Session, project_id: str) -> dict[str, int]:
    db.query(KnowledgeEdge).filter(KnowledgeEdge.project_id == project_id).delete(synchronize_session=False)
    db.query(KnowledgeNode).filter(KnowledgeNode.project_id == project_id).delete(synchronize_session=False)
    db.flush()

    sources = (
        db.query(SourceDocument)
        .filter(SourceDocument.project_id == project_id, SourceDocument.is_active.is_(True))
        .all()
    )
    claims = (
        db.query(Claim)
        .filter(Claim.project_id == project_id, Claim.is_active.is_(True))
        .order_by(Claim.source_timestamp.asc(), Claim.external_ref.asc())
        .all()
    )
    links = (
        db.query(ClaimEvidence, EvidenceSpan, SourceDocument)
        .join(EvidenceSpan, ClaimEvidence.evidence_span_id == EvidenceSpan.id)
        .join(SourceDocument, EvidenceSpan.source_id == SourceDocument.id)
        .filter(SourceDocument.project_id == project_id)
        .all()
    )
    evidence_by_claim: dict[str, list[tuple[ClaimEvidence, EvidenceSpan, SourceDocument]]] = {}
    for link, span, source in links:
        evidence_by_claim.setdefault(link.claim_id, []).append((link, span, source))

    nodes_by_key: dict[str, KnowledgeNode] = {}
    nodes_by_ref: dict[str, KnowledgeNode] = {}
    source_node_by_id: dict[str, KnowledgeNode] = {}
    source_ref_by_id: dict[str, str] = {}
    person_edges_by_claim: dict[str, list[tuple[KnowledgeNode, KnowledgeNode, str]]] = {}
    reason_edges_by_claim: dict[str, list[tuple[KnowledgeNode, KnowledgeNode]]] = {}

    def ensure_node(
        *,
        node_key: str,
        node_type: str,
        label: str,
        description: str,
        sensitivity: int,
        valid_from: datetime,
        valid_to: datetime | None = None,
        claim_id: str | None = None,
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeNode:
        existing = nodes_by_key.get(node_key)
        if existing:
            existing.sensitivity = max(existing.sensitivity, sensitivity)
            existing.valid_to = (
                None if existing.valid_to is None or valid_to is None else max(existing.valid_to, valid_to)
            )
            return existing
        node = KnowledgeNode(
            project_id=project_id,
            node_key=node_key,
            node_type=node_type,
            label=label,
            description=description,
            sensitivity=sensitivity,
            valid_from=valid_from,
            valid_to=valid_to,
            claim_id=claim_id,
            source_id=source_id,
            metadata_json=metadata or {},
        )
        db.add(node)
        db.flush()
        nodes_by_key[node_key] = node
        return node

    for source in sources:
        source_ref = source.metadata_json.get("source_ref") or source.id
        source_ref_by_id[source.id] = source_ref
        node = ensure_node(
            node_key=f"source:{source_ref}",
            node_type="source",
            label=source.title,
            description=f"{source.source_type} ingested from {source.external_ref or 'local upload'}",
            sensitivity=source.sensitivity,
            valid_from=source.source_timestamp,
            source_id=source.id,
            metadata={"source_type": source.source_type, "external_ref": source.external_ref, "is_demo": source.is_demo},
        )
        source_node_by_id[source.id] = node

    for claim in claims:
        meta = claim.metadata_json or {}
        node_key = meta.get("node_key") or f"{claim.claim_type}:{claim.external_ref}"
        valid_to = parse_datetime(meta.get("superseded_at"))
        node = ensure_node(
            node_key=node_key,
            node_type=meta.get("node_type") or claim.claim_type,
            label=meta.get("title") or claim.external_ref,
            description=claim.statement,
            sensitivity=claim.sensitivity,
            valid_from=claim.source_timestamp,
            valid_to=valid_to,
            claim_id=claim.id,
            source_id=meta.get("source_id"),
            metadata={
                "external_ref": claim.external_ref,
                "claim_type": claim.claim_type,
                "verification_status": claim.verification_status,
                "review_status": claim.review_status,
                "source_timestamp": claim.source_timestamp.isoformat() + "Z",
                "state_key": meta.get("state_key"),
                "from_value": meta.get("from_value"),
                "tags": claim.tags,
            },
        )
        nodes_by_ref[claim.external_ref] = node

        if claim.owner:
            person = ensure_node(
                node_key=_person_key(claim.owner),
                node_type="person",
                label=claim.owner,
                description=f"Project participant referenced by {claim.external_ref}",
                sensitivity=claim.sensitivity,
                valid_from=claim.source_timestamp,
                metadata={"owner_name": claim.owner},
            )
            if claim.claim_type == "decision":
                relation = "decided_by"
            elif claim.claim_type == "task":
                relation = "assigned_to"
            else:
                relation = "owned_by"
            # Person edges are added below with the shared edge helper.
            person_edges_by_claim.setdefault(claim.id, []).append((node, person, relation))

        if claim.claim_type == "decision" and claim.rationale:
            reason = ensure_node(
                node_key=f"reason:{claim.external_ref}",
                node_type="reason",
                label=f"Why: {claim.external_ref}",
                description=claim.rationale,
                sensitivity=claim.sensitivity,
                valid_from=claim.source_timestamp,
                metadata={"decision_ref": claim.external_ref},
            )
            reason_edges_by_claim.setdefault(claim.id, []).append((node, reason))

    edges_by_key: dict[str, KnowledgeEdge] = {}

    def ensure_edge(
        *,
        edge_key: str,
        source_node: KnowledgeNode,
        target_node: KnowledgeNode,
        relation: str,
        label: str,
        sensitivity: int,
        valid_from: datetime,
        valid_to: datetime | None = None,
        claim_id: str | None = None,
        evidence_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        effective = max(sensitivity, source_node.sensitivity, target_node.sensitivity)
        existing = edges_by_key.get(edge_key)
        if existing:
            existing.sensitivity = max(existing.sensitivity, effective)
            return
        edge = KnowledgeEdge(
            project_id=project_id,
            edge_key=edge_key,
            source_node_id=source_node.id,
            target_node_id=target_node.id,
            relation=relation,
            label=label,
            sensitivity=effective,
            valid_from=valid_from,
            valid_to=valid_to,
            claim_id=claim_id,
            evidence_span_id=evidence_span_id,
            metadata_json=metadata or {},
        )
        db.add(edge)
        db.flush()
        edges_by_key[edge_key] = edge

    for claim in claims:
        claim_node = nodes_by_ref.get(claim.external_ref)
        if claim_node is None:
            continue
        meta = claim.metadata_json or {}
        valid_to = parse_datetime(meta.get("superseded_at"))

        for link, span, source in evidence_by_claim.get(claim.id, []):
            source_node = source_node_by_id.get(source.id)
            if source_node:
                ensure_edge(
                    edge_key=f"supported_by:{claim_node.node_key}:{source_node.node_key}:{link.id}",
                    source_node=claim_node,
                    target_node=source_node,
                    relation="supported_by",
                    label="supported by source evidence",
                    sensitivity=max(claim.sensitivity, source.sensitivity, span.sensitivity),
                    valid_from=claim.source_timestamp,
                    valid_to=valid_to,
                    claim_id=claim.id,
                    evidence_span_id=span.id,
                    metadata={"quote": span.quote, "source_ref": source_ref_by_id.get(source.id)},
                )

        for src, person, relation in person_edges_by_claim.get(claim.id, []):
            ensure_edge(
                edge_key=f"{relation}:{src.node_key}:{person.node_key}",
                source_node=src,
                target_node=person,
                relation=relation,
                label=relation.replace("_", " "),
                sensitivity=max(src.sensitivity, person.sensitivity),
                valid_from=claim.source_timestamp,
                valid_to=valid_to,
                claim_id=claim.id,
            )

        for src, reason in reason_edges_by_claim.get(claim.id, []):
            ensure_edge(
                edge_key=f"supported_by_reason:{src.node_key}:{reason.node_key}",
                source_node=src,
                target_node=reason,
                relation="supported_by_reason",
                label="why it happened",
                sensitivity=max(src.sensitivity, reason.sensitivity),
                valid_from=claim.source_timestamp,
                valid_to=valid_to,
                claim_id=claim.id,
            )

        if claim.claim_type == "dependency":
            src_ref = meta.get("parent_ref")
            tgt_ref = meta.get("target_ref")
            src_node = nodes_by_ref.get(src_ref) if src_ref else None
            tgt_node = nodes_by_ref.get(tgt_ref) if tgt_ref else None
            if src_node is None and src_ref:
                src_node = nodes_by_key.get(_infer_node_key(src_ref))
            if tgt_node is None and tgt_ref:
                guessed = _infer_node_key(tgt_ref)
                tgt_node = nodes_by_key.get(guessed) or ensure_node(
                    node_key=guessed,
                    node_type="unknown",
                    label="Withheld or unknown reference",
                    description="A referenced record was not available to this graph build.",
                    sensitivity=3,
                    valid_from=claim.source_timestamp,
                    metadata={"external_ref": tgt_ref},
                )
            if src_node and tgt_node:
                ensure_edge(
                    edge_key=f"depends_on:{src_node.node_key}:{tgt_node.node_key}",
                    source_node=src_node,
                    target_node=tgt_node,
                    relation="depends_on",
                    label="depends on",
                    sensitivity=claim.sensitivity,
                    valid_from=claim.source_timestamp,
                    valid_to=valid_to,
                    claim_id=claim.id,
                    metadata={"source_ref": src_ref, "target_ref": tgt_ref},
                )

        if claim.claim_type == "blocker" and meta.get("blocked_task"):
            target_ref = meta["blocked_task"]
            target_node = nodes_by_ref.get(target_ref) or nodes_by_key.get(_infer_node_key(target_ref))
            if target_node:
                ensure_edge(
                    edge_key=f"blocks:{claim_node.node_key}:{target_node.node_key}",
                    source_node=claim_node,
                    target_node=target_node,
                    relation="blocks",
                    label="blocks",
                    sensitivity=claim.sensitivity,
                    valid_from=claim.source_timestamp,
                    valid_to=valid_to,
                    claim_id=claim.id,
                )

        if claim.claim_type == "unfinished_work" and meta.get("task"):
            target_ref = meta["task"]
            target_node = nodes_by_ref.get(target_ref) or nodes_by_key.get(_infer_node_key(target_ref))
            if target_node:
                ensure_edge(
                    edge_key=f"tracks:{claim_node.node_key}:{target_node.node_key}",
                    source_node=claim_node,
                    target_node=target_node,
                    relation="tracks",
                    label="tracks unfinished work",
                    sensitivity=claim.sensitivity,
                    valid_from=claim.source_timestamp,
                    valid_to=valid_to,
                    claim_id=claim.id,
                )

        if claim.supersedes_ref:
            target_node = nodes_by_ref.get(claim.supersedes_ref)
            if target_node:
                ensure_edge(
                    edge_key=f"supersedes:{claim_node.node_key}:{target_node.node_key}",
                    source_node=claim_node,
                    target_node=target_node,
                    relation="supersedes",
                    label="supersedes",
                    sensitivity=max(claim_node.sensitivity, target_node.sensitivity),
                    valid_from=claim.source_timestamp,
                    claim_id=claim.id,
                )

    db.flush()
    return {"nodes": len(nodes_by_key), "edges": len(edges_by_key), "claims": len(claims), "sources": len(sources)}
