---
id: SRC-008
title: "DEMO | Public onboarding brief"
type: project_document
date: 2026-10-20
author: "Meera Iyer"
sensitivity: public
external_ref: "demo://docs/public-onboarding-brief"
---
# DEMONSTRATION DATA — synthetic public onboarding brief

@decision id=DEC-008 key="beta.communication" value="Publish a weekly public beta status summary" rationale="Stakeholders need a predictable update cadence" owner="Meera Iyer" status=approved date=2026-10-20 tags=general,public sensitivity=public role_scope=incoming_analyst,incoming_engineer,observer priority=3
@task id=KB-114 title="Draft the first weekly beta status summary" owner="Incoming analyst" status=todo due=2026-11-16 depends_on= tags=general,public sensitivity=public priority=3 role_scope=incoming_analyst
@contact id=C-003 name="KnowledgeBridge demo desk" role=" Hackathon support contact" channel="demo-desk@example.test" expertise="Demonstration walkthrough" date=2026-10-20 tags=general,public sensitivity=public role_scope=incoming_analyst,incoming_engineer,observer
@question id=Q-004 question="Should the beta status page show import job counts?" owner="Incoming analyst" status=open date=2026-10-20 tags=general,public,analytics sensitivity=public role_scope=incoming_analyst
@next id=NA-004 title="Publish the first weekly beta status summary" owner="Incoming analyst" priority=3 depends_on=KB-114 tags=general,public sensitivity=public role_scope=incoming_analyst
