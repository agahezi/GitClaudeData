# Codex-only architecture

Codex is the sole supported coding-agent client. `AGENTS.md` is the repository instruction
authority. The three canonical global skills are source-controlled below
`catalog/codex-global/skills/`; `scripts/deploy.py` maps their regular files to
`HOME/.agents/skills/` with create-only semantics.

Project discovery uses `<repo>/.agents/skills/`. Eventual global installation uses
`~/.agents/skills/`. A successful discovery probe proves only that a skill can be located;
separate behavioral fixtures prove planning, execution, and verification contracts.

The deployer validates an explicit catalog allowlist, rejects symlinks and protected artifact
names, and preflights every destination. It never deletes or overwrites a pre-existing
destination. During a failed create-only transaction, it may remove only files and empty
directories created by that same transaction. Plan and verify are non-mutating. Apply refuses
the real home unless the operator explicitly acknowledges it.

Real-home deployment is forbidden until every compatibility gate passes. Installed state from
previous clients is outside this repository migration and remains untouched.
