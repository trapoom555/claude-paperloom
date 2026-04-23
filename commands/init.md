---
description: Scaffold a new Research Librarian vault at the configured path (or at an optional path argument). Idempotent — fills missing files without clobbering existing ones.
argument-hint: "[vault-path]"
---

# /research-librarian:init

Scaffold the Obsidian vault that the Research Librarian uses. All filesystem work is done by `scripts/init_vault.py` — this command just resolves the path and shells out.

## Inputs

- `$ARGUMENTS` — optional vault path. Precedence: argument > `${CLAUDE_PLUGIN_CONFIG:vault_path}` > `~/ResearchLibrarian`.

## Steps

1. Pick the vault path per the precedence above. Pass the raw path to the script — the script expands `~` and env vars itself.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init_vault.py" "<vault-path>"
   ```

   The script:
   - Resolves the absolute path, prints it ("Using vault: /Users/...").
   - Creates `papers/ findings/ authors/ fields/ views/ .sources/`.
   - Copies `CLAUDE.md`, `index.md`, `log.md` and the five view pages from `templates/` if missing. Never overwrites.
   - Appends one line to `log.md`.
   - Prints a created/skipped report.

3. Relay the script's stdout to the user verbatim, plus the reminder:
   > Install the **Dataview** community plugin in Obsidian to activate the view pages.

## Guardrails

- Do NOT write to the vault yourself. The script is the single writer.
- If the script exits non-zero, surface its stderr and stop.
