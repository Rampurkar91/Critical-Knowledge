# Security model

KnowledgeBridge implements a layered role-based / attribute-based access-control
model inspired by NIST SP 800-162 ABAC guidance and NIST SP 800-207 zero-trust
principles, without claiming formal certification.

## Enforcement order

1. `get_current_user` validates the JWT and active user.
2. `get_membership` requires an active `ProjectMember` row in the same organisation.
3. `require_action` checks the project role's action allowlist; denials are audited.
4. `visible_*_query` functions apply classification clearance, persisted `allowed_claim_types` and persisted `allowed_tags` **before** results are fetched.
5. Handovers are additionally scoped to `recipient_user_id` unless the actor is a manager, technical lead or auditor.
6. Every serialised object is passed through a restricted-phrase guard; objects containing hidden identifiers are omitted.
7. Exports reapply the guard at the recipient's clearance.

## Classification matrix

`0 public / 1 internal / 2 confidential / 3 restricted`. Every source, claim,
evidence span, graph node, graph edge, task, risk, handover and handover item
carries a level. Graph builder and dependency claims propagate the maximum
endpoint classification, so a lower-classification source cannot reveal a hidden
target through a relationship label.

## Role policies

| Role | Clearance | Example actions |
| --- | ---: | --- |
| `project_manager` | 3 | All actions, member management, conflict resolution, approval, sharing. |
| `tech_lead` | 2 | Technical review, verification, risk management, task updates. |
| `incoming_engineer` | 1 | View authorised graph/claims, acknowledge and continue handover items. |
| `incoming_analyst` | 0 | Public summary-oriented view, acknowledgement, search/ask. |
| `auditor` | 2 | Read verification and audit history; no mutation. |
| `observer` | 0 | Read-only public knowledge. |

Individual `max_clearance`, `allowed_claim_types` and `allowed_tags` values can be
overridden per member and are enforced by the same query helpers used across
claims, search/RAG, graph, tasks, risks, handovers and exports.

## Audit trail

`AuditLog` rows form a hash chain via `prev_hash` and `event_hash`. Payloads
include a non-stored nonce; the API verifies chain continuity but does not
recompute payload hashes. Ingestion, extraction, review, approval, sharing,
exports, denials, redactions and acknowledgements are recorded.

## Explicit limitations

- This is an application-level policy layer, not a replacement for network segmentation, TLS, SSO, key rotation or database encryption.
- The default JWT secret and demo password in `.env.example` are development-only.
- Passwords are PBKDF2-HMAC-SHA256 hashed; no plaintext password is stored or logged.
- No real API keys, private documents or confidential data are included. Optional GitHub/LLM credentials are read from environment variables only.
- Automated tests check policy enforcement; no independent penetration test or formal verification was performed.
