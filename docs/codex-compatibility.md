# Codex compatibility gates

## Verified discovery paths

Codex discovery has already been verified at these locations:

- `~/.agents/skills` for global skills
- `<repo>/.agents/skills` for project skills

Discovery means that Codex can locate a skill at a supported path. It does not establish that the skill can be selected correctly, execute safely, resolve its dependencies, or behave equivalently across clients. Behavioral compatibility must be demonstrated separately through every gate below.

## Required compatibility gates

A managed-workflow candidate is Codex-compatible only after all of these gates pass:

1. **Valid `SKILL.md` schema:** the skill metadata and instruction structure are accepted by Codex.
2. **Automatic and explicit skill selection:** both implicit task matching and explicit skill invocation select the intended skill.
3. **Client-neutral instructions:** operational instructions do not assume a specific client unless a tested client-specific branch is explicitly defined.
4. **No unresolved client-specific assumptions:** there are no unresolved Claude-only tools, slash commands, model names, paths, stream formats, or agent assumptions.
5. **Dependency resolution:** every referenced skill, agent, tool, script, and fallback is available and compatible in the target environment.
6. **Benign plan test:** planning succeeds on a harmless fixture without causing unintended mutations.
7. **Isolated execute/verify test:** execution and verification succeed in an isolated fixture with bounded effects and expected results.
8. **Claude regression test:** the migration does not break the supported Claude behavior.

Codex deployment of the managed-workflow candidates remains disabled until every gate passes. Being discoverable, or being placed under a future shared catalog path, is insufficient to enable deployment.

## Currently unresolved dependencies

- `superpowers:brainstorming`
- `gsd-code-reviewer`
- `qa_tester` dispatch
- Claude Agent/tool semantics
- `CLAUDE.md`-only fallback
- `format-stream.py` Claude stream format
- Slash-command invocation assumptions
