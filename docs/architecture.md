# How this repository manages skills

## Layout

```
skills/<name>/SKILL.md   one folder per skill (custom or downloaded)
skills/<name>/.skill.json  optional: targets and, for downloaded skills, where it came from
plugins.json             optional: Claude Code plugins to install
scripts/skills.py        add | install | update | verify | plan
```

A skill without `.skill.json` is installed for both tools. `.skill.json` may limit it, for
example `{"targets": ["claude"]}` for a skill that depends on Claude Code-only features.

## Commands (Windows and Linux, Python 3.8+ and Git)

| Command | What it does |
| --- | --- |
| `python scripts/skills.py add <link>` | Copies a skill into `skills/`. Accepts a GitHub repo/folder/`SKILL.md` link, a web page that links to GitHub, a zip link or file, or a local folder. |
| `python scripts/skills.py install` | Installs every skill into `~/.agents/skills` (Codex) and `~/.claude/skills` (Claude Code), installs plugins, then offers newer versions and verifies. |
| `python scripts/skills.py update` | Checks downloaded skills and plugins for newer versions, applies the ones you accept, reinstalls, and verifies. |
| `python scripts/skills.py verify` | Checks every installed file and plugin; exits non-zero if anything is missing or different. |
| `python scripts/skills.py plan` | Shows what `install` would do without changing anything. |

`--yes` answers every question with its default (no version upgrades, no plugin updates, back up
and replace conflicting copies). After `add` or `update`, review with `git status` and commit.

## Rules

- **Byte-exact install.** `.gitattributes` keeps `skills/**` free of line-ending conversion, so
  every OS installs identical files.
- **Ownership.** Installed fingerprints are kept in `~/.skill-manager/state.json`. The script
  updates only copies it installed and that nobody changed. Anything else is a conflict: it asks,
  and when you agree it moves the old copy to `~/.skill-manager/backups/<time>/` first.
- **Removal.** A skill deleted from the repo is uninstalled only if its installed copy is unchanged.
- **Links.** It never writes through a symlink or junction; a linked tool folder blocks install.
- **Downloads.** Only `https://` sources. Git sources record the exact commit; zip sources record a
  SHA-256. Symlinks, secrets-like files, and bytecode are dropped on import. Zip paths escaping
  the archive are refused. Nothing from a download is executed.
- **Claude Code-only features.** `add` scans for markers such as `allowed-tools`, `hooks`,
  `${CLAUDE_PLUGIN_ROOT}`, `TodoWrite`, and asks whether to install the skill for Claude Code only.
- **Plugins.** If a downloaded repository is a Claude Code plugin, `add` offers to register it in
  `plugins.json` (preferring the official marketplace) and copy its skills for Codex only, so they
  do not appear twice. Commands in `plugins.json` must start with `claude` and are editable if the
  Claude Code CLI changes. A plugin counts as installed when it appears in
  `~/.claude/plugins/installed_plugins.json` or in `claude plugin list` output.
- **Local copies.** Skills added from a local folder get no update checks; add them from their web
  link instead to get them.
