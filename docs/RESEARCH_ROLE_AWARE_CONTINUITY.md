# Innovation 3 — Role-Aware Adaptive Handover & Project Continuity Engine

## Research problem

An incoming member needs a report scoped to their role and clearance, with
prioritised next actions, responsibilities, risks, unresolved questions,
acknowledgement tracking and a shared-information audit trail. A generic
document dump can expose restricted information or leave the successor unsure
what to do first.

## Existing approaches

- **NIST SP 800-162** defines ABAC as authorisation by subject, object,
  operation and environment attributes against policy. **NIST SP 800-207**
  describes zero trust as moving defences from static network perimeters to
  users, assets and resources; it states that no implicit trust is granted from
  physical/network location or asset ownership, and that authentication and
  authorisation are discrete functions performed before a session.
- **RBAC/ABAC products and wikis** provide page/space permissions, audit logs
  and exports. Confluence public guidance describes page restrictions; Notion
  public guidance describes page verification and workspace permissions; Slack
  public guidance describes exports and audit logs.
- **Offboarding workflows** often combine surveys, transcripts and a knowledge
  base. Public stack guides describe diagnosis/capture/publish steps, but the
  resulting artefacts are usually static pages rather than permission-aware,
  evidence-linked, interactive continuation plans.
- **Turnover research** (Urbancová & Linhartová, 2011; Pee et al., 2014)
  motivates succession planning, repositories and orientation. Urbancová and
  Linhartová explicitly frame labour turnover as a threat to knowledge
  continuity and describe structured transfer of critical knowledge as a way to
  preserve organisational memory and shorten successor onboarding. They do not
  provide a software architecture that enforces per-claim access control before
  every summary, search, AI answer, graph view and export.

## Limitations and gap

Page-level permissions are too coarse for a generated summary assembled from
many claims. Post-generation redaction alone is insufficient: hidden
information can leak through dependency labels, search snippets, AI citations,
graph edges, exports or audit details. A successor also needs acknowledgement
and completion telemetry, not just a document.

## Proposed solution

`handover_engine/generator.py` and `backend/app/services/permissions.py`
implement:

- six role policies plus per-member clearance, claim-type and tag overrides;
- pre-retrieval SQL filtering for sources, claims, evidence, graph nodes/edges, tasks, risks and retrieval documents;
- recipient-scoped handovers with `draft → approved → shared` lifecycle;
- manager edit/correction/approval before sharing;
- role-specific sections, next five actions, priority checklist, responsibilities, risks/dependencies, open questions and evidence register;
- uncertainty fields for excluded clearance/status, missing evidence and unresolved questions;
- acknowledgement, start, complete actions and continuity rates;
- hash-chained audit history and restricted-phrase guards on every output channel.

The same `visible_claim_query` is the source of truth across claims, search,
RAG, graph, tasks, risks and handovers, reducing policy drift.

## Architecture and methodology

1. Resolve actor membership, role action, clearance, claim-type and tag policy.
2. Select only active, approved, `Verified`, authorised claims with permitted evidence.
3. Mask hidden dependency refs; omit tasks/risks tied to hidden claims.
4. Build role-specific content and apply a JSON-wide restricted-phrase guard.
5. Persist draft, versioned edits, approval, share timestamp and checklist items.
6. Restrict views/exports to recipient or privileged roles and reapply guards.
7. Record item acknowledgement/completion and compute continuity telemetry.

## Expected contribution

An end-to-end integration of ABAC-style pre-retrieval filtering, human-approved
role-specific handovers, continuation actions and auditability. It is an
applied systems integration, not a claim of novel access-control theory or
worldwide novelty.

## Evaluation metrics and measured results

Metrics: permission enforcement leak count, hidden-by-policy counts, denied
actions, external-project access status, audit-chain validity, handover section
coverage, evidence-link rate, recommendation precision/recall/F1 against
hand-authored expected next actions, acknowledgement/completion rates, human
correction rate, handover preparation time, incoming-member task understanding.

From `reports/EVALUATION_REPORT.md`:

- 9 low-clearance channels tested; **0 restricted marker leaks**.
- Engineer hidden-by-policy: 31 nodes / 87 edges; analyst: 113 nodes / 202 edges.
- Manager could see restricted graph identifiers; engineer approve attempt = 403; external project access = 404; hash chain valid.
- Required handover sections = 8/8; evidence-linked statements = 35/35.
- Recommendation precision/recall/F1 = 1.0 / 1.0 / 1.0; exact priority-order match = true.
- Acknowledgement/completion rate after one item workflow = 0.0714 each.
- Human correction rate = 0.0 (0/89 automated review events).
- Handover preparation time = 1.0s average / 1s maximum in this automated run.
- Incoming-member task understanding = **not measured**; requires a human study.

Preparation time and correction rate are workflow telemetry, not measured
human-productivity outcomes. No independent penetration test was performed.
