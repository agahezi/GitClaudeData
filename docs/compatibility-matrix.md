# Compatibility matrix

Every catalog artifact present at migration start is resolved below. CONVERT means useful policy
was rewritten into the Codex-native catalog; DELETE means the repository-managed artifact was
removed; KEEP means it remains active without conversion. There are no unresolved items.

| Starting artifact | Decision | Resolution |
| --- | --- | --- |
| `catalog/shared-global/skills/managed-workflow-plan/SKILL.md` | CONVERT | Codex-native planning contract |
| `catalog/shared-global/skills/managed-workflow-execute/SKILL.md` | CONVERT | Codex-native execution contract |
| `catalog/shared-global/skills/managed-workflow-execute/format-stream.py` | DELETE | Client-specific stream parser removed |
| `catalog/shared-global/skills/managed-workflow-verify/SKILL.md` | CONVERT | Read-only review plus useful QA policy |
| Former-client `agents/qa_tester.md` | CONVERT | Useful skeptical QA policy incorporated into verification skill; agent file removed |
| Former-client `commands/proxy-setup/proxy-setup.md` | DELETE | Proxy command removed |
| Former-client `legacy/skills/managed-workflow.md` | DELETE | Legacy workflow removed |
| Former-client auth-token-manager `README.md` | DELETE | Authentication workflow removed |
| Former-client auth-token-manager `SKILL.md` | DELETE | Authentication workflow removed |
| Former-client auth-token-manager OAuth reference | DELETE | OAuth reference removed |
| Former-client auth-token-manager `references/cliproxyapi.md` | DELETE | Proxy integration reference removed |
| Former-client auth-token-manager `scripts/cliproxyapi_manager.sh` | DELETE | Proxy manager removed |
| Former-client auth-token-manager `scripts/install.sh` | DELETE | Installer removed |
| Former-client auth-token-manager `scripts/refresh_token.py` | DELETE | Token refresh script removed |

The final catalog contains exactly the three converted skill files and no other deployable
artifact.
