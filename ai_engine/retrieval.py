"""Permission-aware sparse-vector retrieval.

The default index uses deterministic TF-IDF vectors (sparse lexical embeddings)
with a small domain synonym map. It is deliberately transparent and offline; it
is not a neural semantic embedding model. FAISS/ChromaDB can replace this class
without changing the permission-aware API.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models import Claim, ClaimEvidence, EvidenceSpan, SourceDocument
from backend.app.services.permissions import redact_forbidden_text, visible_claim_query

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "what",
    "which", "who", "with", "current", "please", "show", "me", "about", "any",
}
SYNONYMS = {
    "owner": ["assignee", "assigned", "owned", "responsible"],
    "assignee": ["owner", "assigned"],
    "target": ["region", "deployment", "staging"],
    "expiry": ["expires", "expiration", "renewal", "renewed"],
    "limit": ["rate", "throttle", "requests"],
    "rollback": ["rehearsal", "runbook", "failure"],
    "blocker": ["blocked", "blocks", "quota"],
    "current": ["latest", "supersedes", "revised"],
    "question": ["unresolved", "open", "issue"],
}


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)?", str(text).lower())
    tokens: list[str] = []
    for token in raw:
        parts = re.split(r"[-_]", token)
        for part in [token, *parts]:
            if len(part) < 2 or part in STOPWORDS or part.isdigit():
                continue
            tokens.append(part)
            for synonym in SYNONYMS.get(part, []):
                tokens.append(synonym)
    return tokens


@dataclass
class Document:
    id: str
    text: str
    payload: dict[str, Any]


class TfidfVectorStore:
    def __init__(self, documents: list[Document]):
        self.documents = documents
        self.idf: dict[str, float] = {}
        self.vectors: list[dict[str, float]] = []
        self._fit()

    def _fit(self) -> None:
        n = max(1, len(self.documents))
        df: Counter[str] = Counter()
        tokenized: list[list[str]] = []
        for doc in self.documents:
            tokens = tokenize(doc.text)
            tokenized.append(tokens)
            df.update(set(tokens))
        self.idf = {term: math.log((n + 1) / (count + 1)) + 1.0 for term, count in df.items()}
        for tokens in tokenized:
            tf = Counter(tokens)
            vector = {
                term: (1.0 + math.log(freq)) * self.idf.get(term, 1.0)
                for term, freq in tf.items()
            }
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
            self.vectors.append({term: value / norm for term, value in vector.items()})

    def query(self, text: str, top_k: int = 5) -> list[tuple[Document, float]]:
        tokens = tokenize(text)
        tf = Counter(tokens)
        qvec = {
            term: (1.0 + math.log(freq)) * self.idf.get(term, 1.0)
            for term, freq in tf.items()
        }
        qnorm = math.sqrt(sum(value * value for value in qvec.values())) or 1.0
        qvec = {term: value / qnorm for term, value in qvec.items()}
        results: list[tuple[Document, float]] = []
        for doc, dvec in zip(self.documents, self.vectors):
            score = sum(value * dvec.get(term, 0.0) for term, value in qvec.items())
            phrase_boost = 0.0
            lowered = doc.text.lower()
            for token in set(tokens):
                if len(token) >= 5 and token in lowered:
                    phrase_boost += 0.02
            score += min(phrase_boost, 0.12)
            if score > 0:
                results.append((doc, round(score, 6)))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]


def authorized_documents(db: Session, project_id: str, member) -> list[Document]:
    # The claim ABAC query is the single source of truth: clearance, persisted
    # claim-type allowlist and persisted tag allowlist are applied before the
    # evidence join, so no unauthorised claim text enters the ranking index.
    visible_ids = {claim.id for claim in visible_claim_query(db, project_id, member).all()}
    if not visible_ids:
        return []
    rows = (
        db.query(Claim, EvidenceSpan, SourceDocument)
        .join(ClaimEvidence, ClaimEvidence.claim_id == Claim.id)
        .join(EvidenceSpan, ClaimEvidence.evidence_span_id == EvidenceSpan.id)
        .join(SourceDocument, EvidenceSpan.source_id == SourceDocument.id)
        .filter(
            Claim.id.in_(visible_ids),
            Claim.project_id == project_id,
            Claim.is_active.is_(True),
            Claim.sensitivity <= member.max_clearance,
            EvidenceSpan.sensitivity <= member.max_clearance,
            SourceDocument.sensitivity <= member.max_clearance,
            SourceDocument.is_active.is_(True),
        )
    )

    documents: list[Document] = []
    for claim, span, source in rows.all():
        source_ref = source.metadata_json.get("source_ref") or source.id
        text = " ".join([
            claim.external_ref,
            claim.claim_type,
            claim.normalized_key,
            claim.statement,
            claim.value,
            claim.owner,
            claim.rationale,
            " ".join(claim.tags or []),
            span.quote,
            source.title,
            source_ref,
        ])
        # Defence in depth: a lower-classification source can quote a hidden
        # identifier (e.g. an internal task line referring to a restricted
        # decision). Such documents are excluded before indexing/serialisation.
        _, text_changed = redact_forbidden_text(db, project_id, member.max_clearance, text)
        quote, quote_changed = redact_forbidden_text(db, project_id, member.max_clearance, span.quote)
        if text_changed or quote_changed:
            continue
        documents.append(Document(
            id=f"{claim.id}:{span.id}",
            text=text,
            payload={
                "claim_id": claim.id,
                "external_ref": claim.external_ref,
                "claim_type": claim.claim_type,
                "statement": claim.statement,
                "verification_status": claim.verification_status,
                "review_status": claim.review_status,
                "reliability_score": claim.reliability_score,
                "quote": quote,
                "start_char": span.start_char,
                "end_char": span.end_char,
                "source_id": source.id,
                "source_ref": source_ref,
                "source_title": source.title,
                "source_type": source.source_type,
                "source_timestamp": source.source_timestamp.isoformat() + "Z" if source.source_timestamp else None,
                "sensitivity": claim.sensitivity,
            },
        ))
    return documents


def retrieve(db: Session, project_id: str, member, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    docs = authorized_documents(db, project_id, member)
    if not docs:
        return []
    store = TfidfVectorStore(docs)
    ranked = store.query(query, top_k=max(top_k * 4, 10))
    seen_sources: set[str] = set()
    unique: list[dict[str, Any]] = []
    for doc, score in ranked:
        payload = dict(doc.payload)
        if payload["source_id"] in seen_sources:
            continue
        seen_sources.add(payload["source_id"])
        payload["retrieval_score"] = score
        unique.append(payload)
        if len(unique) >= top_k:
            break
    if len(unique) < top_k:
        for doc, score in ranked:
            payload = dict(doc.payload)
            if any(item["claim_id"] == payload["claim_id"] for item in unique):
                continue
            payload["retrieval_score"] = score
            unique.append(payload)
            if len(unique) >= top_k:
                break
    return unique
