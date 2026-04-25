---
description: Ask a question of the research vault. Searches papers and findings, synthesizes an answer with wikilink citations.
argument-hint: "<question>"
---

# /paperloom:query

`$ARGUMENTS` is a natural-language question about the vault's contents.

## Vault path

Read `vault_path` from `${CLAUDE_PLUGIN_CONFIG:vault_path}` (default `~/PaperLoom`), expand `~` to an absolute path, and use that for every Read/Grep/Glob.

## Steps

1. **Plan the search**. Identify likely fields/authors/claim types from the question (e.g. "transformer complexity" → field `nlp`, `complexity-analysis`). Note key entities.
2. **Scan**:
   - grep `<vault>/papers/` and `<vault>/findings/` for the key terms (titles, statements, frontmatter values).
   - Read the top candidates (papers: Key Takeaways + relevant sections; findings: statement + evidence).
3. **Synthesize**. Answer the question. **Cite** every factual statement with a wikilink — e.g. `[[2017-06-attention-is-all-you-need]]` or `[[finding-self-attention-is-O-n2]]`. If findings conflict, say so and cite both sides.
4. **Log** via the shared script:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python3" "${CLAUDE_PLUGIN_ROOT}/scripts/log.py" "<vault-path>" query "<one-line question>" "cited <n> files"
   ```

## Guardrails

- Never fabricate a citation. If you can't find evidence, say so and suggest which paper to ingest.
- Prefer finding-level wikilinks over paper-level when a specific finding is relevant.
- Keep answers tight. The user drills into the vault via the citations.
