---
description: Scaffold a new PaperLoom at the configured path (or at an optional path argument). Idempotent — fills missing files without clobbering existing ones.
argument-hint: "[vault-path]"
---

# /paperloom:init

Scaffold the Obsidian vault that PaperLoom uses. All filesystem work is done by `scripts/init_vault.py` — this command just resolves the path and shells out.

## Inputs

- `$ARGUMENTS` — optional vault path. Precedence: argument > `${CLAUDE_PLUGIN_CONFIG:vault_path}` > `~/PaperLoom`.

## Steps

1. Pick the vault path per the precedence above. Pass the raw path to the script — the script expands `~` and env vars itself.

2. Bootstrap the plugin venv if it doesn't already exist, then run the scaffolder:

   ```bash
   if [ ! -x "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" ]; then
     python3 -m venv "${CLAUDE_PLUGIN_ROOT}/.venv" \
       && "${CLAUDE_PLUGIN_ROOT}/.venv/bin/pip" install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"
   fi
   "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/init_vault.py" "<vault-path>"
   ```

   The script:
   - Resolves the absolute path, prints it ("Using vault: /Users/...").
   - Creates `papers/ findings/ authors/ fields/ views/ .sources/`.
   - Copies `CLAUDE.md`, `index.md`, `log.md` and the five view pages from `templates/` if missing. Never overwrites.
   - Seeds `.obsidian/` from the bundled `templates/dot-obsidian/` (Dataview plugin files + `community-plugins.json` pre-enabling it, plus baseline `app.json` / `appearance.json` / `core-plugins.json`). Existing files are never overwritten.
   - Appends one line to `log.md`.
   - Prints a created/skipped report.

3. Relay the script's stdout to the user verbatim. Remind them to turn off Obsidian's Restricted Mode once on first vault open so the bundled Dataview plugin can load.

## Guardrails

- Do NOT write to the vault yourself. The script is the single writer.
- If the script exits non-zero, surface its stderr and stop.
