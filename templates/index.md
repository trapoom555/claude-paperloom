# PaperLoom — Index

This page is the catalog of the vault. Generated/maintained by `/paperloom:ingest`. Dataview queries refresh automatically.

## All papers (most recently ingested first)

```dataview
TABLE publication-date AS "Published", ingested-date AS "Ingested", authors AS "Authors", quality.overall AS "Overall", ingest-mode AS "Mode"
FROM "papers"
SORT ingested-date DESC
```

## Pre-built views

- [[views/recent-papers]]
- [[views/by-field]]
- [[views/by-author]]
- [[views/contradictions]]
- [[views/high-credibility]]
- [[views/paper-graph]] — paper-level KG (cites, builds-on, supports, contradicts, extends)
- [[views/graph-config]] — color groups + typed-edge viz

## Stats

```dataview
TABLE length(rows) AS "Count"
FROM "papers" OR "claims" OR "authors" OR "fields"
GROUP BY type
```

## Navigation

- `papers/` — one page per paper (9-section summary + metadata).
- `claims/` — one page per atomic claim. The **knowledge graph** lives here: see `relations` in each claim's frontmatter.
- `authors/`, `fields/` — entity pages. Open one to see all backlinks.
- `log.md` — timeline of vault actions.
- `CLAUDE.md` — schema.
