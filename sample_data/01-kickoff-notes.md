---
id: SRC-001
title: "DEMO | Atlas Migration kickoff meeting notes"
type: meeting_note
date: 2026-07-03
author: "Meera Iyer"
sensitivity: internal
external_ref: "demo://meetings/2026-07-03-kickoff"
---
# DEMONSTRATION DATA — synthetic meeting notes

@decision id=DEC-001 key="deployment.target" value="Use eu-west-1 for staging" rationale="Initial latency estimate favoured the existing European test network" owner="Meera Iyer" status=approved date=2026-07-03 tags=deployment,architecture sensitivity=internal role_scope=project_manager,tech_lead priority=3
@task id=KB-101 title="Inventory legacy export jobs" owner="Arjun Rao" status=done due=2026-07-10 depends_on= tags=backend,integration sensitivity=internal priority=3 role_scope=incoming_engineer
@task id=KB-102 title="Define canonical customer schema" owner="Priya Nair" status=done due=2026-07-18 depends_on=KB-101 tags=api,data sensitivity=internal priority=3 role_scope=incoming_engineer,incoming_analyst
@change id=CHG-001 key="project.phase" from="Discovery" value="Build" reason="Kickoff approved the migration backlog" date=2026-07-03 tags=general sensitivity=internal
@question id=Q-001 question="Should archived invoices be imported into the new reporting store?" owner="Priya Nair" status=open date=2026-07-03 tags=data,analytics sensitivity=internal role_scope=incoming_analyst,incoming_engineer
@contact id=C-001 name="Meera Iyer" role="Outgoing project manager" channel="meera@example.test" expertise="Migration scope and vendor contracts" date=2026-07-03 tags=general sensitivity=internal role_scope=incoming_engineer,incoming_analyst
@unfinished id=UF-001 task=KB-103 detail="Schema mapping spreadsheet is only half complete" owner="Priya Nair" status=in_progress date=2026-07-03 tags=data,integration sensitivity=internal role_scope=incoming_engineer
