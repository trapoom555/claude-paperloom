---
description: Scan the vault for orphan pages, frontmatter schema drift, duplicate findings, unmarked contradictions, and stale wikilinks. Reports issues without auto-fixing.
---

# /paperloom:lint

Read-only health check of the vault. All six checks run in `scripts/lint.py`.

## Step 0 — greet the user

Before doing anything else, print this message exactly:

> 🔍 Running a vault health check — just a moment while everything gets tidied up ✨

Then proceed.

## Steps

1. Resolve the vault path from `${CLAUDE_PLUGIN_CONFIG:vault_path}` (default `~/PaperLoom`) — pass it raw to the script, which expands it.

2. Run:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/lint.py" "<vault-path>"
   ```

   The script performs:
   - Frontmatter schema drift (required keys, enum values)
   - Orphan pages (no inbound and no outbound wikilinks)
   - Duplicate findings — **new-vs-all only**. A pair is flagged only if at least one member is "new" (default: `extracted-date ≥ today`; override with `--new-slugs` or `--since`). Old-vs-old pairs are ignored.
   - Asymmetric contradicts / similar-to
   - Stale wikilinks (target file missing)
   - Date sanity (ISO format, `ingested-date ≥ publication-date`)

   For any dup pair found, the script by default creates a bidirectional `similar-to` edge between the two findings (dedupe via linking, not by forcing the user to merge). Pass `--no-link-similar` to keep the run strictly read-only.

   Then appends a `lint` line to `<vault>/log.md`.

3. When called from `/paperloom:ingest`, pass `--new-slugs <slug1,slug2,...>` so the dedup check focuses exactly on the freshly-written findings (don't rely on the date fallback — an earlier session could bump the "today" window).

4. Relay the script's stdout to the user verbatim. Non-zero exit means issues exist — that is expected output, not a failure. Don't retry.

## After the report

Offer — but do not auto-run — suggested fixes for the remaining issue categories (dup linking is already applied). The user drives remediation for schema drift, orphans, asymmetric edges, etc.

## Guardrails

- The *only* write lint performs is creating `similar-to` edges between duplicates. Schema / orphan / stale-link fixes are left to the user.
- Pass `--no-link-similar` if you want a strict read-only run.
- Use `--json` for machine-readable output.
