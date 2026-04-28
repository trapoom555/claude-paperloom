---
description: Lite ingest — fetch a paper and write a short 4-section triage summary (Key Takeaways, Background, Main Idea & Summary, Critique). No figures, fast.
argument-hint: "<url | arxiv-id | doi | pdf-path>"
---

# /paperloom:ingest

Fast, triage-grade ingest. `$ARGUMENTS` is the paper reference.

**Division of labor**: the deterministic steps (fetch, parse, template fill, edge aggregation, logging, stub creation, citation matching) are done by Python scripts in `${CLAUDE_PLUGIN_ROOT}/scripts/`. The LLM is used only for the three remaining semantic subagents: `lite-drafter`, `finding-extractor`, `metadata-extractor`. Per-item LLM loops are forbidden — if you find yourself running an agent N times for N items, stop and shell out to a script.

## Step 0 — greet the user

Print exactly:
> 📖 Ingesting your paper — this will take a moment. Sit back, get cozy, and maybe grab a coffee ☕️

## Step 1 — fetch + extract

Shell out. The script validates the vault, classifies the input, caches the raw file, and produces full + brief text:

```bash
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/fetch_paper.py" "<vault-path>" "$ARGUMENTS"
```

Parse the JSON result.

**Early exit — duplicate paper.** If the result has `"already_exists": true`, the paper is already in the vault (matched by arxiv-id, doi, or source-url). Do not run any further steps. Print a short message naming the existing slug, e.g.:

> ⏭️ This paper is already in your vault as `papers/<existing.slug>.md` — skipping ingest.

Then stop.

Otherwise, keep `full_text_path`, `brief_text_path`, `findings_text_path`, `meta_text_path`, `source_url`, `arxiv_id`, `doi` for later steps.

## Step 2 — scan vault for context

Run these in parallel (they're independent reads):

```bash
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" fields  "<vault-path>"
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" papers  "<vault-path>"
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" authors "<vault-path>"
```

Hold the outputs: `existing_fields`, `vault_papers`, `existing_authors`.

## Step 3 — fan-out: 2 LLM subagents (semantic-only)

Launch in **one parallel message**:

| Agent | Model | Input | Purpose |
|---|---|---|---|
| `lite-drafter` | `model_reasoning` | `brief_text_path` | returns the 4 sections JSON |
| `finding-extractor` | `model_normal` | `findings_text_path` | returns atomic findings JSON. Fed the abstract + intro + method + results + conclusion slice, not the full paper — saves tokens while keeping theoretical / empirical / definitional claims reachable. |

**Do not spawn a citation-linker agent** — bibliographic matching is deterministic and runs in step 6 via `citation_match.py`.

## Step 4 — metadata (after lite-drafter)

Once `lite-drafter` returns, spawn `metadata-extractor` (`model_normal`) with:
- `paper_text_path` = `meta_text_path` (first 2 pages — enough for title/authors/date/venue/quality)
- `summary_text` = the concatenated markdown returned by `lite-drafter` (for `fields`)
- `existing_fields` = list from step 2
- `source_url`, `arxiv_id`, `doi` = from step 1

The agent returns metadata JSON. It does NOT compute `quality.overall` or the slug — the assembly script does both.

## Step 5 — assemble the paper page

**Before writing any `/tmp/*.json` payload in this step or step 6/7**, first clear stale files from prior runs in a single Bash call:

```bash
rm -f /tmp/paper_payload.json /tmp/findings_payload.json /tmp/stubs_payload.json /tmp/edges_payload.json
```

Without this, the `Write` tool refuses to overwrite a `/tmp/*.json` file it has not Read in the current conversation, and the ingest stalls.

Write the payload to `/tmp/paper_payload.json` with this **exact shape** (note `metadata` is a nested key — flat layouts will fail with `KeyError: 'metadata'`):

```json
{
  "vault_path": "<vault-path>",
  "source_url": "<source_url from step 1>",
  "metadata": {
    "title": "...",
    "authors": ["Surname, Given", "..."],
    "publication-date": "YYYY-MM-DD",
    "venue": "...",
    "fields": ["nlp", "..."],
    "arxiv-id": "..." ,
    "doi": null,
    "quality": {
      "credibility": 5,
      "experimental-rigor": 5,
      "reproducibility": "code-released",
      "rationale": "..."
    }
  },
  "sections": {
    "key_takeaways": "...",
    "background": "...",
    "main_idea_and_summary": "...",
    "critique": "..."
  },
  "findings": [],
  "relations": {}
}
```

Then pipe it in:

```bash
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/assemble_paper.py" --input /tmp/paper_payload.json
```

The script computes `quality.overall`, generates `slug` if absent, fills `templates/paper-lite.md`, and writes `<vault>/papers/<slug>.md`. It refuses to overwrite unless `overwrite: true` is set in the payload — ask the user first.

Capture the returned `slug`.

## Step 6 — in parallel: findings, citations, candidates, stubs

`/tmp/findings_payload.json` shape (note `source_paper`, not `paper_slug`):

```json
{
  "vault_path": "<vault-path>",
  "source_paper": "<slug from step 5>",
  "fields": ["nlp", "..."],
  "findings": [ { "statement": "...", "source-ref": "...", "finding-type": "empirical", "hedging": "asserted", "quote": "..." } ]
}
```

`/tmp/stubs_payload.json` shape:

```json
{ "vault_path": "<vault-path>", "authors": ["Surname, Given", "..."], "fields": ["nlp", "..."] }
```

Launch all four at once — they're independent. **6c uses `--exclude-paper <slug>` to keep the just-written findings (from 6a) out of the candidate set, so ordering between 6a and 6c doesn't matter.**

```bash
# 6a. Write finding files in one script call.
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/assemble_finding.py" --input /tmp/findings_payload.json

# 6b. Deterministic citation matching. Feed vault_papers from step 2.
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/citation_match.py" \
    "<full_text_path>" <(echo "$VAULT_PAPERS_JSON") \
    --own-slug "<slug>"

# 6c. Candidate finding shortlist for finding-linker.
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/vault_scan.py" findings-candidates "<vault-path>" \
    --fields <metadata.fields joined by ,> \
    --authors "<metadata.authors joined by ;>" \
    --exclude-paper "<slug>" \
    --cap 30

# 6d. Missing author/field stubs.
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/create_stubs.py" --input /tmp/stubs_payload.json
```

Now update the paper page's `findings:` frontmatter with the new slugs:

```bash
# Re-run assemble_paper.py with overwrite:true and findings: [...] populated.
```

(Or, equivalently, edit just the frontmatter via a targeted Edit on `<vault>/papers/<slug>.md`.)

## Step 7 — finding-linker (the last LLM step)

Spawn **`finding-linker`** (`model_normal`) **once**, with:
- `new_findings` = the slugs + statements + fields written in 6a
- `candidate_existing_findings` = output of 6c

It returns typed-edge proposals. Write `/tmp/edges_payload.json` with this **exact shape** (note the keys are `new_paper` and `linker_output`, not `source_paper`/`edges`):

```json
{
  "vault_path": "<vault-path>",
  "new_paper": "<slug from step 5>",
  "linker_output": [ { "from": "<new-finding-slug>", "to": "<existing-finding-slug>", "type": "supports|contradicts|extends|uses|similar-to", "rationale": "..." } ],
  "cites": ["<paper-slug>", "..."]
}
```

If finding-linker returned zero edges (e.g. empty candidate set), still call the script with `"linker_output": []` so paper-level `cites` from 6b get merged in.

```bash
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/apply_edges.py" --input /tmp/edges_payload.json
```

The script:
- writes edges into each new finding's `relations.*`,
- mirrors `contradicts` / `similar-to` onto target findings,
- aggregates finding edges to paper-level relations (`uses→builds-on`, `supports`, `extends`, `contradicts`, `similar-to`),
- mirrors bidirectional paper edges onto target papers,
- merges with `cites` from 6b into the new paper's `relations.cites`.

## Step 8 — log

```bash
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/log.py" "<vault-path>" ingest-lite "<slug>" \
    "<n> findings, <e> edges"
```

## Step 9 — lint

Invoke lint scoped to the findings just written, so the dedup check only considers the new set against the existing vault (not all-pairs):

```bash
"${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/lint.py" "<vault-path>" \
    --new-slugs "<finding-slug-1>,<finding-slug-2>,..."
```

`--link-similar` is on by default — any near-duplicate pairs found get bidirectional `similar-to` edges automatically. Display the report inline.

## Step 10 — open (optional)

If `${CLAUDE_PLUGIN_CONFIG:open_in_obsidian}` is truthy, print (don't auto-run):

```
open "obsidian://open?vault=<vault-basename>&file=papers/<slug>"
```

## Report back

End-of-run summary:
- paper slug + `quality.overall`
- finding count
- new vs existing field/author stubs (from 6d output)
- edge counts by type (from apply_edges)

## Guardrails

- **Scripts do the writing.** The LLM only produces JSON payloads for the scripts to consume.
- **Clear `/tmp/*.json` payloads at the start of step 5** (see the `rm -f` line). The `Write` tool will not overwrite a file it has not Read in the current conversation, so leftover files from a prior ingest run will block the pipeline.
- **No per-item LLM loops.** If you catch yourself iterating an agent over a list, stop and script it.
- **Do not embed figures.** Lite mode is text-only.
- **Do not overwrite** an existing `papers/<slug>.md` without asking.
- If `finding-extractor` returns zero findings, warn the user — the paper may have been abstract-only.
