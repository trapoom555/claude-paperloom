---
type: finding
statement: Multi-head attention outperforms single-head attention on WMT14
slug: finding-multi-head-attention-outperforms-single-head-attenti
source-paper: "[[2017-06-attention-is-all-you-need]]"
source-ref: §6.2, Table 3
fields:
- "[[nlp]]"
- "[[attention-mechanism]]"
extracted-date: '2026-04-23'
finding-type: empirical
hedging: asserted
relations:
  supports: []
  contradicts: []
  extends: []
  uses: []
  similar-to: []
---

# Multi-head attention outperforms single-head attention on WMT14

> 8-head model improves BLEU by 0.9 over single head
— [[2017-06-attention-is-all-you-need]] (§6.2, Table 3)

## Evidence

- From [[2017-06-attention-is-all-you-need]] (§6.2, Table 3)

## Relations

*Edit edges in the YAML `relations` block above — these auto-render from it.*

- **Supports →** `= this.relations.supports`
- **Contradicts ⚡** `= this.relations.contradicts`
- **Extends ↗** `= this.relations.extends`
- **Uses 🔧** `= this.relations.uses`
- **Similar to ≈** `= this.relations["similar-to"]`

## Incoming edges (backlinks from other findings)

Findings that reference this one — grouped by the edge type on the *other* side.

```dataview
TABLE WITHOUT ID
  file.link AS "Finding",
  (choice(contains(relations.supports, this.file.link), "supports →", "") +
   choice(contains(relations.contradicts, this.file.link), "contradicts ⚡", "") +
   choice(contains(relations.extends, this.file.link), "extends ↗", "") +
   choice(contains(relations.uses, this.file.link), "uses 🔧", "") +
   choice(contains(relations["similar-to"], this.file.link), "similar to ≈", "")) AS "Edge type"
FROM "findings"
WHERE file.path != this.file.path AND (
  contains(relations.supports, this.file.link) OR
  contains(relations.contradicts, this.file.link) OR
  contains(relations.extends, this.file.link) OR
  contains(relations.uses, this.file.link) OR
  contains(relations["similar-to"], this.file.link)
)
```

## One-hop neighborhood (combined)

```dataview
LIST
FROM outgoing([[]]) OR inlinks([[]])
WHERE type = "finding"
```
