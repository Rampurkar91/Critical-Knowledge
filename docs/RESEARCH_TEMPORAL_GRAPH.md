# Innovation 1 — Temporal Project Knowledge Graph & Decision Reconstruction

## Research problem

Project knowledge is scattered across meeting notes, task boards, chat exports,
documents, commits and issue histories. When a person leaves, a static document
often records *what* was written but not why a decision was made, who owned it,
which tasks depended on it, how the state changed, or which work is unfinished.
Employee turnover can interrupt knowledge continuity and organisational memory
(Urbancová & Linhartová, 2011; Pee et al., 2014).

## Existing approaches

- **Temporal knowledge graph research** studies facts valid over time and
  representation-learning/completion methods. Cai, Mao, Zhou, Long, Wu and Lan
  (2024) survey temporal KG representation learning, datasets and metrics;
  Wang et al. (2023) survey interpolation/extrapolation completion; Cai, Xiang,
  Gao, Zhang, Li and Li (IJCAI 2023) review problem definitions, benchmarks,
  metrics and timestamp-aware TKGC methods. These surveys emphasise that static
  KGC misses facts whose validity changes over time.
- **Knowledge graphs in products** connect entities, but public documentation
  for Confluence/Jira and GitHub describes pages, issues, commits and links; it
  does not provide a handover-oriented decision/reason/dependency graph with
  exact source evidence per node.
- **Project repositories and task boards** preserve artefacts, but reasons,
  superseded decisions and unfinished-work relationships often remain implicit.

## Limitations and gap

TKG surveys focus heavily on learned embeddings and missing-fact prediction on
benchmark datasets. They do not by themselves provide: (a) click-through to the
exact character offsets in an authorised source; (b) human-readable decision
rationale, owner, dependency and unfinished-work output for a departing-member
handover; (c) classification propagation through cross-source dependency edges;
or (d) pre-retrieval filtering that prevents a hidden target from being inferred
through a relationship label.

## Proposed solution

KnowledgeBridge uses a deterministic, evidence-preserving extractor and a
rebuildable temporal graph rather than a neural completion model. Each structured
record becomes a claim with exact source offsets, timestamp, owner, tags, role
scope, classification and rationale. `knowledge_graph/builder.py` creates nodes
for decisions, tasks, risks, people, reasons, sources, state changes, commits,
issues, questions and unfinished work; edges include `supported_by`,
`supported_by_reason`, `decided_by`, `owned_by`, `assigned_to`, `depends_on`,
`blocks`, `tracks` and `supersedes`. Nodes/edges carry `valid_from`/`valid_to`
and the maximum endpoint classification. The React graph explorer supports an
as-of timeline, filters, pan/zoom and an evidence drawer.

Cross-source dependency classification is computed from all active sources
before materialisation, so an internal task that depends on a restricted decision
does not leak the restricted identifier through a graph label.

## Architecture and methodology

1. Ingest sources with front-matter classification and SHA-256.
2. Parse explicit `@record` lines; generate exact-offset evidence spans.
3. Derive dependency claims from `depends_on` fields using a project-wide ref→classification map.
4. Materialise claims, tasks, risks and evidence links idempotently.
5. Rebuild graph twice: before and after verification, so superseded nodes receive `valid_to`.
6. Serve only nodes/edges whose classification, claim type, tag allowlist and linked claim are authorised.

The optional LLM adapter is not used for graph construction; this avoids
fabricated relationships and citations.

## Expected contribution

An auditable, offline-reproducible integration of temporal project
reconstruction, decision rationale, dependency classification propagation and
evidence click-through inside a handover workflow. We do not claim a new TKG
algorithm or worldwide novelty.

## Evaluation metrics and measured results

Metrics: extraction label precision/recall/F1, exact evidence-offset accuracy,
dependency-pair precision/recall/F1, graph node/edge counts, `depends_on` edge
count, representative gold-edge recall, restricted node/edge counts and
low-clearance graph leak checks.

From `reports/EVALUATION_REPORT.md`:

- Extraction labels: 70/70, precision/recall/F1 = 1.0.
- Exact evidence offsets: 93/93, accuracy = 1.0.
- Dependency pairs: 24/24, F1 = 1.0.
- Graph: 120 nodes, 210 edges, 24 `depends_on` edges.
- Representative gold edges: 12/12 found, recall = 1.0.
- Restricted nodes/edges: 9 / 23; engineer graph hidden-by-policy: 31 nodes / 87 edges; zero restricted marker leaks.

The 12-edge gold set is a regression subset, not an exhaustive graph annotation.
