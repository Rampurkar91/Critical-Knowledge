---
id: SRC-006
title: "DEMO | Migration team chat export"
type: chat_export
date: 2026-10-04
author: "Migration team"
sensitivity: internal
external_ref: "demo://chat/migration-team-2026-10-04"
---
# DEMONSTRATION DATA — synthetic chat transcript

@fact id=F-202 key="task.KB-104.owner" value="Neha Kulkarni" claim_type=owner subject="KB-104" reason="Chat message reassigned the blocked adapter after Arjun went on leave" date=2026-10-04 tags=backend,integration sensitivity=internal role_scope=incoming_engineer priority=2
@question id=Q-003 question="Is the archived invoice import still in scope for the public beta?" owner="Neha Kulkarni" status=open date=2026-10-04 tags=data,analytics sensitivity=internal role_scope=incoming_analyst,incoming_engineer
@contact id=C-002 name="Arjun Rao" role="Outgoing backend engineer" channel="arjun@example.test" expertise="Event bridge adapter and rollback scripts" date=2026-10-04 tags=backend,integration sensitivity=internal role_scope=incoming_engineer
@change id=CHG-004 key="task.KB-104.assignment" from="Arjun Rao" value="Neha Kulkarni" reason="Temporary reassignment discussed in chat; task board was not updated" date=2026-10-04 tags=backend sensitivity=internal
@next id=NA-003 title="Ask the manager to resolve the KB-104 owner conflict in the task board" owner="Incoming engineer" priority=1 depends_on=KB-104 tags=backend,integration sensitivity=internal role_scope=incoming_engineer
@unfinished id=UF-004 task=KB-104 detail="Retry-safe adapter branch remains unmerged" owner="Neha Kulkarni" status=blocked date=2026-10-04 tags=backend,integration sensitivity=internal role_scope=incoming_engineer
