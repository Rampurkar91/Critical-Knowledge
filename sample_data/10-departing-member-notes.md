---
id: SRC-010
title: "DEMO | Departing member handover notes"
type: handover_note
date: 2026-11-02
author: "Meera Iyer"
sensitivity: internal
external_ref: "demo://handover/meera-iyer-notes"
---
# DEMONSTRATION DATA — synthetic departing member notes

@contact id=C-004 name="Priya Nair" role="Data lead" channel="priya@example.test" expertise="Canonical schema and finance reconciliation" date=2026-11-02 tags=data,analytics sensitivity=internal role_scope=incoming_engineer,incoming_analyst
@question id=Q-005 question="Which archived invoice fields are required for the December reconciliation?" owner="Priya Nair" status=open date=2026-11-02 tags=data,analytics sensitivity=internal role_scope=incoming_analyst,incoming_engineer
@unfinished id=UF-005 task=KB-106 detail="Reconciliation report has no owner handover notes" owner="Priya Nair" status=todo date=2026-11-02 tags=analytics,data sensitivity=internal role_scope=incoming_analyst
@risk id=RISK-006 title="Reconciliation report knowledge is held by one departing data lead" description="Handover notes for KB-106 are incomplete while archived invoice scope remains open" severity=medium likelihood=medium owner="Priya Nair" status=open mitigation="Schedule the data lead walkthrough in NA-005" date=2026-11-02 tags=analytics,data sensitivity=internal role_scope=incoming_analyst,incoming_engineer priority=2
@next id=NA-005 title="Meet the data lead to resolve archived invoice scope" owner="Incoming engineer" priority=2 depends_on=Q-005 tags=data,analytics,integration sensitivity=internal role_scope=incoming_engineer,incoming_analyst
@next id=NA-006 title="Complete the rollback runbook before the rehearsal booking" owner="Incoming engineer" priority=1 depends_on=KB-107 tags=deployment,testing sensitivity=internal role_scope=incoming_engineer
@change id=CHG-006 key="project.ownership" from="Meera Iyer" value="Handover pending" reason="Outgoing manager recorded continuity actions" date=2026-11-02 tags=general sensitivity=internal
