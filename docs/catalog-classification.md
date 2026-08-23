# Catalog classification and migration boundaries

This Git repository is the source of truth for the artifacts covered by this migration. Files deployed elsewhere are derived copies and do not supersede the tracked repository state.

The classifications below are exhaustive for the currently tracked functional artifacts. Each tracked artifact appears exactly once.

| Tracked artifact | Classification | Migration boundary |
| --- | --- | --- |
| `catalog/claude-global/agents/qa_tester.md` | Claude-only agent | Depends on Claude agent and dispatch semantics. |
| `catalog/claude-global/commands/proxy-setup/proxy-setup.md` | Claude-only command | Retains Claude command and slash-command assumptions. |
| `deploy.sh` | Claude legacy deployment | Existing deployment behavior is outside the shared catalog migration and must not be treated as Codex deployment. |
| `catalog/claude-global/skills/auth-token-manager/README.md` | Claude-only skill documentation | Documents the Claude-oriented authentication workflow. |
| `catalog/claude-global/skills/auth-token-manager/SKILL.md` | Claude-only skill | Depends on Claude OAuth and Claude-oriented tooling. |
| `catalog/claude-global/skills/auth-token-manager/references/claude-oauth.md` | Claude-only reference | Describes Claude OAuth. |
| `catalog/claude-global/skills/auth-token-manager/references/cliproxyapi.md` | Claude-only reference | Describes CLIProxyAPI integration used by the Claude-oriented authentication workflow. |
| `catalog/claude-global/skills/auth-token-manager/scripts/cliproxyapi_manager.sh` | Claude-only support script | Manages CLIProxyAPI for the Claude-oriented authentication workflow. |
| `catalog/claude-global/skills/auth-token-manager/scripts/install.sh` | Claude-only support script | Installs dependencies for the Claude-oriented authentication workflow. |
| `catalog/claude-global/skills/auth-token-manager/scripts/refresh_token.py` | Claude-only support script | Implements token refresh for the Claude-oriented authentication workflow. |
| `catalog/shared-global/skills/managed-workflow-execute/SKILL.md` | Global portability candidate | Candidate for global shared ownership; not a validated shared skill and not approved for Codex deployment. |
| `catalog/shared-global/skills/managed-workflow-execute/format-stream.py` | Currently Claude-dependent support script | Consumes Claude stream format and requires compatibility work before any Codex use. |
| `catalog/shared-global/skills/managed-workflow-plan/SKILL.md` | Global portability candidate | Candidate for global shared ownership; not a validated shared skill and not approved for Codex deployment. |
| `catalog/shared-global/skills/managed-workflow-verify/SKILL.md` | Global portability candidate | Candidate for global shared ownership; not a validated shared skill and not approved for Codex deployment. |
| `catalog/claude-global/legacy/skills/managed-workflow.md` | Claude legacy skill | Legacy Claude workflow entry point; it is not a validated Codex skill. |

The planned `catalog/shared-global` area will represent intended shared ownership only. Placement there will not prove behavioral compatibility with either client. In particular, `managed-workflow-plan`, `managed-workflow-execute`, and `managed-workflow-verify` remain global portability candidates—not validated shared skills—until the compatibility gates in `docs/codex-compatibility.md` pass.

Claude-only and Claude legacy artifacts remain outside the shared migration boundary unless a later approved commit explicitly changes their classification. This includes auth-token-manager, proxy-setup, Claude OAuth, CLIProxyAPI, `qa_tester`, Claude commands, Claude agents, and `managed-workflow.md`.
