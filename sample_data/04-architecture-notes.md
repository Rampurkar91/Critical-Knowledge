---
id: SRC-004
title: "DEMO | Revised architecture and deployment notes"
type: project_document
date: 2026-10-12
author: "Neha Kulkarni"
sensitivity: internal
external_ref: "demo://docs/revised-architecture"
---
# DEMONSTRATION DATA — synthetic revised architecture note

@decision id=DEC-006 key="deployment.target" value="Use ap-south-1 for staging" rationale="Pune-based engineering and revised data residency review changed the latency assumption" owner="Neha Kulkarni" status=approved date=2026-10-12 supersedes=DEC-001 depends_on=Q-001 tags=deployment,architecture sensitivity=internal role_scope=project_manager,tech_lead,incoming_engineer priority=2
@decision id=DEC-007 key="beta.scope" value="Limit public beta to read-only reporting" rationale="Write-path reconciliation is still unfinished" owner="Meera Iyer" status=approved date=2026-10-12 tags=general,public sensitivity=public role_scope=incoming_analyst,incoming_engineer priority=2
@fact id=F-204 key="api.rate_limit" value="250 requests per minute" claim_type=state_change subject="Customer import API v2" reason="Revised gateway note after load test number 17" date=2026-10-12 tags=api,backend sensitivity=internal role_scope=incoming_engineer priority=2
@risk id=RISK-005 title="Vendor sandbox renewed until 2026-12-15" description="The earlier expiry date was replaced after the vendor confirmed a renewal" severity=low likelihood=low owner="Arjun Rao" status=mitigated mitigation="Track renewal again in December" date=2026-10-12 supersedes=RISK-002 tags=integration,security sensitivity=confidential role_scope=project_manager,tech_lead priority=3
@change id=CHG-003 key="deployment.target" from="eu-west-1" value="ap-south-1" reason="DEC-006 supersedes DEC-001 after data residency review" date=2026-10-12 tags=deployment sensitivity=internal
@next id=NA-002 title="Reconcile the two recorded API rate limits before release" owner="Incoming engineer" priority=1 depends_on=KB-105 tags=api,backend sensitivity=internal role_scope=incoming_engineer
