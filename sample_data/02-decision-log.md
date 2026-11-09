---
id: SRC-002
title: "DEMO | Architecture decision log"
type: decision_log
date: 2026-08-14
author: "Arjun Rao"
sensitivity: internal
external_ref: "demo://docs/decision-log"
---
# DEMONSTRATION DATA — synthetic decision log

@decision id=DEC-002 key="integration.pattern" value="Use an event bridge for legacy exports" rationale="Point-to-point adapters would duplicate retry logic across six jobs" owner="Arjun Rao" status=approved date=2026-07-22 depends_on=KB-101 tags=architecture,backend sensitivity=internal role_scope=project_manager,tech_lead,incoming_engineer priority=2
@decision id=DEC-003 key="api.versioning" value="Freeze v1 after the October beta" rationale="Two mobile clients cannot migrate before the beta window" owner="Priya Nair" status=approved date=2026-08-02 tags=api,backend sensitivity=internal role_scope=project_manager,tech_lead,incoming_engineer priority=2
@decision id=DEC-004 key="data.retention" value="Retain migration audit logs for 180 days" rationale="Finance reconciliation requires one full quarterly cycle" owner="Neha Kulkarni" status=approved date=2026-08-14 tags=data,governance sensitivity=confidential role_scope=project_manager,tech_lead priority=3
@decision id=DEC-005 key="release.gate" value="Require a manual rollback rehearsal before production" rationale="The previous export migration had an untested rollback path" owner="Meera Iyer" status=approved date=2026-08-14 depends_on=KB-108 tags=deployment,testing sensitivity=internal role_scope=project_manager,tech_lead,incoming_engineer priority=1
@change id=CHG-002 key="architecture.eventing" from="Not selected" value="Event bridge selected" reason="DEC-002 approved adapter consolidation" date=2026-08-14 tags=architecture sensitivity=internal
