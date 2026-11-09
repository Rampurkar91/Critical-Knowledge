# Repository naming and publication note

Intended repository-ready name: **`knowledgebridge-ai-handover`**

Intended description:

> An intelligent AI-powered knowledge-handover platform that reconstructs project history, verifies evidence, detects risks and generates secure, role-specific handovers for seamless project continuity.

The current Arena working checkout is `Rampurkar91/Critical-Knowledge` on the
fixed branch `arena/9a4f48b4-critical-knowledge`. The original repository was
not overwritten or renamed. All code is repository-ready in this workspace and
is committed/pushed to that fixed branch.

A separate public repository with the intended name was requested during the
build, but repository creation returned `403 Resource not accessible by
integration` from the GitHub App installation token (both `gh api /user/repos`
and `gh repo create`). This token can push to the existing repository but cannot
create a new user-owned repository. To publish under
`knowledgebridge-ai-handover`, reconnect GitHub in Arena with
repository-creation permission, or have a maintainer create the empty repository
and push the same branch:

```bash
git remote add target https://github.com/Rampurkar91/knowledgebridge-ai-handover.git
git push target arena/9a4f48b4-critical-knowledge
```

No API keys, passwords, private documents or confidential information are
included. `.env.example` contains demo-only defaults and empty optional
credentials.
