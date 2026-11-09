---
id: SRC-009
title: "DEMO | Restricted security review (demonstration only)"
type: security_review
date: 2026-10-28
author: "Security review team"
sensitivity: restricted
external_ref: "demo://security/restricted-review"
---
# DEMONSTRATION DATA — synthetic restricted source. No real secret is present.

@decision id=DEC-900 key="security.production_access" value="Rotate the demo signing key through vault path RESTRICTED-CANARY-9F3A before production" rationale="Production access checklist requires a recorded key rotation step" owner="Security review team" status=approved date=2026-10-28 tags=security,deployment sensitivity=restricted role_scope=project_manager priority=1
@risk id=RISK-900 title="Restricted production access review is incomplete" description="The restricted review references RESTRICTED-CANARY-9F3A and must not appear in incoming internal-clearance handovers" severity=high likelihood=medium owner="Security review team" status=open mitigation="Complete the restricted checklist with a cleared manager" date=2026-10-28 tags=security,deployment sensitivity=restricted role_scope=project_manager priority=1
@task id=KB-900 title="Record restricted key rotation evidence" owner="Security review team" status=todo due=2026-12-05 depends_on= tags=security sensitivity=restricted priority=1 role_scope=project_manager
@fact id=F-900 key="security.audit_window" value="Restricted audit window RESTRICTED-CANARY-9F3A closes 2026-12-01" claim_type=state_change subject="Production access" reason="Restricted security review" date=2026-10-28 tags=security sensitivity=restricted role_scope=project_manager priority=1
