# Research validation overview

This document coordinates the three innovation research notes:

1. `docs/RESEARCH_TEMPORAL_GRAPH.md` — Temporal Project Knowledge Graph & Decision Reconstruction.
2. `docs/RESEARCH_EVIDENCE_VERIFICATION.md` — Evidence-Based Knowledge Reliability & Conflict Detection Engine.
3. `docs/RESEARCH_ROLE_AWARE_CONTINUITY.md` — Role-Aware Adaptive Handover & Project Continuity Engine.

## Position statement

KnowledgeBridge does **not** claim worldwide novelty for temporal knowledge
graphs, claim verification, retrieval-augmented generation, RBAC/ABAC, task
boards or knowledge bases. Those areas have substantial prior art. The precise
integrated contribution of this project is a single hackathon-scale workflow
that combines:

- evidence-preserving extraction from heterogeneous project artefacts;
- a temporal, as-of queryable decision/dependency graph with click-through to original evidence;
- claim-level verification statuses, conflict/outdated/unsupported detection and human correction history;
- pre-retrieval classification/role/claim-type/tag filtering applied consistently to graph, search, AI answers, handovers and exports;
- reviewer-approved, role-specific handovers with acknowledgements and continuity telemetry.

We claim an **integration and evaluation contribution on a labelled synthetic
dataset**, not a new general algorithm or a production accuracy claim.

## Existing product landscape (public documentation only)

| Product / source | What exists | Documented limitation relevant to this challenge |
| --- | --- | --- |
| Atlassian Confluence | Pages/spaces, version history, page restrictions, Jira embeds. | Public guidance describes page-level restrictions and Jira integration, not a claim-level temporal decision graph with evidence offsets and conflict statuses. [Atlassian](https://www.atlassian.com/software/confluence/resources/guides/best-practices/project-collaboration) |
| Notion | Flexible wiki/database, page verification with owners and expiry. | Public docs describe page-level verification, not per-claim evidence links, contradiction detection or permission-aware handover exports. [Notion](https://www.notion.com/help/wikis-and-verified-pages) |
| GitHub REST API | Issues, pull requests, commits, comments and timelines. | Provides raw project activity, not reconstructed decisions/reasons or successor-specific handovers. [GitHub Docs](https://docs.github.com/en/rest/pulls/pulls) |
| Slack exports / audit logs | Message-history exports and search-query audit logs. | Provides raw conversation history and audit data, not verification of each extracted claim. [Slack export](https://slack.com/help/articles/220556107-How-to-read-Slack-data-exports), [audit logs](https://slack.com/help/articles/360000394286-Audit-logs-in-Slack) |

These comparisons are based on public product documentation, not an independent
benchmark. KnowledgeBridge's optional GitHub adapter is read-only. Its API path
was exercised with a local mock in `reports/OPTIONAL_INTEGRATIONS.md`; no live
token or external repository was used in the core measured evaluation.

## Shared research references

- L. Cai, X. Mao, Y. Zhou, Z. Long, C. Wu, M. Lan (2024). *A Survey on Temporal Knowledge Graph: Representation Learning and Applications*. arXiv:2403.04782. https://arxiv.org/abs/2403.04782
- J. Wang et al. (2023). *A Survey on Temporal Knowledge Graph Completion: Taxonomy, Progress, and Prospects*. arXiv:2308.02457. https://arxiv.org/abs/2308.02457
- B. Cai, Y. Xiang, L. Gao, H. Zhang, Y. Li, J. Li (2023). *Temporal Knowledge Graph Completion: A Survey*. Proceedings of the Thirty-Second International Joint Conference on Artificial Intelligence, pp. 6545–6553; arXiv:2201.08236. https://arxiv.org/abs/2201.08236 , doi:10.24963/ijcai.2023/734
- P. Lewis et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020; arXiv:2005.11401. https://arxiv.org/abs/2005.11401
- J. Thorne, A. Vlachos, C. Christodoulopoulos, A. Mittal (2018). *FEVER: a Large-scale Dataset for Fact Extraction and VERification*. NAACL-HLT 2018, pp. 809–819. https://aclanthology.org/N18-1074/ , doi:10.18653/v1/N18-1074
- V. C. Hu, D. F. Ferraiolo, D. R. Kuhn, A. Schnitzer, K. Sandlin, R. Miller, K. Scarfone (2019 update). *NIST SP 800-162: Guide to Attribute Based Access Control (ABAC) Definition and Considerations*. https://www.nist.gov/publications/guide-attribute-based-access-control-abac-definition-and-considerations-1
- S. Rose, O. Borchert, S. Mitchell, S. Connelly (2020, updated 2021). *NIST SP 800-207: Zero Trust Architecture*. NIST, published 10 August 2020. https://www.nist.gov/publications/zero-trust-architecture , doi:10.6028/NIST.SP.800-207
- L. G. Pee, A. Kankanhalli, G. W. Tan, G. Z. Tham (2014). *Mitigating the Impact of Member Turnover in Information Systems Development Projects*. IEEE Transactions on Engineering Management, 61(4), 702–716. doi:10.1109/TEM.2014.2332339
- H. Urbancová, L. Linhartová (2011). *Staff Turnover as a Possible Threat to Knowledge Loss*. Journal of Competitiveness, 3(3), 84–98. The article frames labour turnover as a threat to knowledge continuity and identifies structured continuity programmes as a mitigation. https://www.cjournal.cz/files/69.pdf
