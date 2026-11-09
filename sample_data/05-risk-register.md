---
id: SRC-005
title: "DEMO | Migration risk register"
type: risk_register
date: 2026-09-05
author: "Meera Iyer"
sensitivity: internal
external_ref: "demo://risks/atlas-migration"
---
# DEMONSTRATION DATA — synthetic risk register

@risk id=RISK-001 title="Unmapped legacy customer tiers may silently drop discounts" description="Three legacy tiers are absent from the canonical mapping" severity=high likelihood=medium owner="Priya Nair" status=open mitigation="Complete KB-103 and add a discount parity test" date=2026-09-05 tags=data,integration sensitivity=internal role_scope=incoming_engineer,incoming_analyst priority=1
@risk id=RISK-002 title="Vendor invoice API sandbox expires 2026-09-30" description="Original sandbox expiry recorded before the October renewal" severity=high likelihood=high owner="Arjun Rao" status=open mitigation="Request a sandbox renewal" date=2026-08-20 tags=integration,security sensitivity=confidential role_scope=project_manager,tech_lead priority=1
@risk id=RISK-003 title="Rollback runbook has no tested vendor-failure path" description="KB-107 is in progress and KB-108 is blocked" severity=high likelihood=medium owner="Arjun Rao" status=open mitigation="Reserve the rehearsal environment and complete KB-107" date=2026-09-05 tags=deployment,testing sensitivity=internal role_scope=incoming_engineer priority=1
@risk id=RISK-004 title="Finance reconciliation report depends on unconfirmed import API" description="KB-106 cannot start until KB-105 is merged" severity=medium likelihood=high owner="Priya Nair" status=open mitigation="Confirm the API contract with the incoming engineer" date=2026-09-05 tags=analytics,data sensitivity=internal role_scope=incoming_analyst,incoming_engineer priority=2
@fact id=F-301 key="environment.staging.cluster" value="Migrated to cluster KB-STAGE-2" claim_type=state_change subject="Staging cluster" reason="Unverified hallway statement with no linked source" unsupported=true date=2026-09-05 tags=deployment sensitivity=internal role_scope=project_manager,tech_lead priority=3
@question id=Q-002 question="Who approves the December production access window?" owner="Meera Iyer" status=open date=2026-09-05 tags=deployment,security sensitivity=confidential role_scope=project_manager,tech_lead
@unfinished id=UF-003 task=KB-107 detail="Rollback runbook lacks vendor failure and retry steps" owner="Arjun Rao" status=in_progress date=2026-09-05 tags=deployment,testing sensitivity=internal role_scope=incoming_engineer
