---
id: SRC-007
title: "DEMO | Synthetic GitHub repository activity"
type: github_export
date: 2026-10-15
author: "github.com/acme-demo/atlas-migration"
sensitivity: internal
external_ref: "demo://github/acme-demo/atlas-migration"
---
# DEMONSTRATION DATA — synthetic commits and issues, not a live repository

@commit id=GIT-C1 sha="a1b2c3d" message="Add canonical customer schema contract" author="Priya Nair" date=2026-07-19 files="contracts/customer-v2.yaml" tags=api,backend sensitivity=internal role_scope=incoming_engineer
@commit id=GIT-C2 sha="e4f5g6h" message="Add event bridge retry skeleton" author="Arjun Rao" date=2026-08-05 files="src/bridge/retry.py" tags=backend,integration sensitivity=internal role_scope=incoming_engineer
@commit id=GIT-C3 sha="i7j8k9l" message="Update rollback checklist after review" author="Arjun Rao" date=2026-10-15 files="docs/rollback.md" tags=deployment,testing sensitivity=internal role_scope=incoming_engineer
@issue id=GH-201 title="Contract tests fail for archived customer tiers" status=open owner="Neha Kulkarni" labels=bug,api date=2026-10-11 depends_on=KB-105 tags=api,testing sensitivity=internal role_scope=incoming_engineer
@issue id=GH-202 title="Decide whether invoice history belongs in reporting store" status=open owner="Priya Nair" labels=question,data date=2026-10-12 depends_on=Q-001 tags=data,analytics sensitivity=internal role_scope=incoming_analyst,incoming_engineer
@change id=CHG-005 key="repository.customer_contract" from="draft" value="merged" reason="Commit a1b2c3d added the schema contract" date=2026-07-19 tags=api sensitivity=internal
