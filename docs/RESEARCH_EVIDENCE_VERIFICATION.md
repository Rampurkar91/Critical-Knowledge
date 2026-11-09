# Innovation 2 — Evidence-Based Knowledge Reliability & Conflict Detection Engine

## Research problem

A handover statement is only useful if the incoming member can see what supports
it, whether it conflicts with another record, whether it is outdated, and whether
a human approved it. Free-form generative summaries can hide uncertainty or
invent citations; a wiki page may be marked verified without claim-level evidence
links.

## Existing approaches

- **FEVER** (Thorne et al., 2018) introduced 185,445 Wikipedia-derived claims
  with Supported / Refuted / NotEnoughInfo labels and evidence sentences. It
  established the importance of joint claim verification and evidence retrieval.
- **RAG** (Lewis et al., 2020) combines parametric generation with a
  non-parametric dense index and explicit retrieved passages, improving
  provenance and updatability. It does not by itself guarantee that a generated
  claim is correct or that every sentence is cited.
- **Fact-verification and RAG systems** typically evaluate against public
  encyclopaedic corpora, not private project records with classification levels,
  reviewer approval and deliberate contradictions.
- **Notion verified pages** provide page-level verification with owners and
  expiry (public docs), not per-claim contradictions, unsupported markers or
  character-offset citations.

## Limitations and gap

Enterprise handovers need more than a supported/refuted label. They need exact
status categories, explicit missing evidence, stale/superseded records,
conflicting values for the same normalised key, human correction history, and
permission-aware evidence. A confidence-looking number must not be presented as
a calibrated probability.

## Proposed solution

`verification_engine/engine.py` implements:

- statuses exactly `Verified`, `Needs Review`, `Conflicting`, `Unsupported`, `Outdated`;
- evidence-link checks and unsupported detection;
- conflict detection on distinct values for the same `normalized_key`;
- explicit supersession and freshness rules for outdated records;
- explainable 0–100 heuristic scores with rationales and a persistent disclaimer;
- approve / reject / correct with versioned replacement claims and copied evidence;
- conflict resolution preserving human decisions;
- review history and bulk approval of eligible evidence-backed claims.

`ai_engine/retrieval.py` builds a TF-IDF lexical index only over claims whose
clearance, claim type and tags are authorised, and excludes evidence quotes
containing hidden identifiers. `ai_engine/llm.py` is an optional
OpenAI-compatible grounded adapter; without configuration the system returns a
deterministic extractive answer with citations. No neural embedding index,
FAISS or ChromaDB is required.

## Architecture and methodology

1. Extract claim + exact evidence span links.
2. Normalise keys/values and source timestamps.
3. Detect unsupported claims, distinct-value conflicts, explicit supersessions and stale records.
4. Assign heuristic score with human-readable rationale; never describe it as a calibrated probability.
5. Present verification, conflict, outdated, unsupported and review queues in the UI.
6. Record every approval/correction/resolution in `ClaimReview` and the audit hash chain.
7. Generate handovers only from active, approved, `Verified`, authorised claims with citations.

## Expected contribution

The integration of claim-level evidence, exact status categories, deterministic
conflict/freshness rules, human correction history and permission-aware retrieval
in one handover pipeline. It is not a new fact-verification model and does not
claim worldwide novelty.

## Evaluation metrics and measured results

Metrics: conflict/outdated/unsupported precision/recall/F1, unsupported-claim
rate, retrieval precision@5/recall@5, evidence-link rate, score-disclaimer
coverage, citation presence in handover statements.

From `reports/EVALUATION_REPORT.md`:

- Conflict F1 = 1.0 (2/2 deliberate keys).
- Outdated F1 = 1.0 (2/2 records).
- Unsupported F1 = 1.0 (1/1 record); unsupported-claim rate = 0.0106 (1/94).
- Retrieval mean precision@5 = 0.44, mean recall@5 = 1.0 over 5 gold queries.
- Evidence spans with exact offsets = 93/93.
- Handover statement items with evidence = 35/35; evidence register = 57 entries.
- Score disclaimer present on all 94 active claims.

Retrieval precision is limited because the source-deduplicated top-5 list often
returns additional authorised sources; recall is complete on the labelled
queries. Heuristic scores are not probabilities.
