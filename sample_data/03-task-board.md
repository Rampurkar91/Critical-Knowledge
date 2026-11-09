---
id: SRC-003
title: "DEMO | Atlas Migration task board export"
type: task_export
date: 2026-09-28
author: "Neha Kulkarni"
sensitivity: internal
external_ref: "demo://tasks/atlas-migration-2026-09-28"
---
# DEMONSTRATION DATA — synthetic task board export

@task id=KB-103 title="Complete legacy-to-canonical field mapping" owner="Priya Nair" status=in_progress due=2026-10-17 depends_on=KB-102 tags=data,integration sensitivity=internal priority=1 role_scope=incoming_engineer
@task id=KB-104 title="Build retry-safe event bridge adapter" owner="Arjun Rao" status=blocked due=2026-10-24 depends_on=KB-102,DEC-002 tags=backend,integration sensitivity=internal priority=1 role_scope=incoming_engineer
@task id=KB-105 title="Implement customer import API v2" owner="Neha Kulkarni" status=in_progress due=2026-11-14 depends_on=KB-103,KB-104 tags=api,backend sensitivity=internal priority=1 role_scope=incoming_engineer
@task id=KB-106 title="Add reconciliation report for finance" owner="Priya Nair" status=todo due=2026-11-21 depends_on=KB-105 tags=analytics,data sensitivity=internal priority=2 role_scope=incoming_analyst,incoming_engineer
@task id=KB-107 title="Write rollback runbook" owner="Arjun Rao" status=in_progress due=2026-11-12 depends_on=DEC-005 tags=deployment,testing sensitivity=internal priority=1 role_scope=incoming_engineer
@task id=KB-108 title="Run production rollback rehearsal" owner="Meera Iyer" status=blocked due=2026-11-20 depends_on=KB-107 tags=deployment,testing sensitivity=internal priority=1 role_scope=project_manager,tech_lead
@task id=KB-109 title="Document support escalation path" owner="Meera Iyer" status=todo due=2026-11-28 depends_on= tags=general,support sensitivity=public priority=3 role_scope=incoming_analyst,incoming_engineer
@task id=KB-110 title="Configure staging observability dashboards" owner="Neha Kulkarni" status=done due=2026-09-30 depends_on=KB-101 tags=deployment,testing sensitivity=internal priority=3 role_scope=incoming_engineer
@task id=KB-111 title="Validate vendor sandbox credentials" owner="Arjun Rao" status=blocked due=2026-10-03 depends_on=RISK-002 tags=integration,security sensitivity=confidential priority=1 role_scope=project_manager,tech_lead
@task id=KB-112 title="Finalise restricted production access checklist" owner="Meera Iyer" status=todo due=2026-12-02 depends_on=KB-111,DEC-900 tags=deployment,security sensitivity=internal priority=2 role_scope=project_manager,tech_lead
@task id=KB-113 title="Publish public beta status page" owner="Neha Kulkarni" status=todo due=2026-11-30 depends_on= tags=general,public sensitivity=public priority=3 role_scope=incoming_analyst
@fact id=F-201 key="task.KB-104.owner" value="Arjun Rao" claim_type=owner subject="KB-104" reason="Task board assignee at the September export" date=2026-09-28 tags=backend,integration sensitivity=internal role_scope=incoming_engineer priority=2
@fact id=F-203 key="api.rate_limit" value="100 requests per minute" claim_type=state_change subject="Customer import API v2" reason="Initial gateway configuration in the task board comment" date=2026-09-28 tags=api,backend sensitivity=internal role_scope=incoming_engineer priority=2
@blocker id=BLK-001 title="Event bridge sandbox quota exhausted" blocked_task=KB-104 reason="Vendor has not approved the quota increase" owner="Arjun Rao" status=open date=2026-09-28 tags=integration,backend sensitivity=internal role_scope=incoming_engineer priority=1
@blocker id=BLK-002 title="Rollback rehearsal environment not reserved" blocked_task=KB-108 reason="Platform team requires five business days notice" owner="Meera Iyer" status=open date=2026-09-28 tags=deployment,testing sensitivity=internal role_scope=project_manager,tech_lead,incoming_engineer priority=1
@next id=NA-001 title="Confirm the current owner of KB-104 before resuming adapter work" owner="Incoming engineer" priority=1 depends_on=KB-104 tags=backend,integration sensitivity=internal role_scope=incoming_engineer
@unfinished id=UF-002 task=KB-105 detail="Import API v2 endpoint is unmerged and lacks contract tests" owner="Neha Kulkarni" status=in_progress date=2026-09-28 tags=api,backend sensitivity=internal role_scope=incoming_engineer
