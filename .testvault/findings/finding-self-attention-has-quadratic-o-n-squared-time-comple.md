---
type: finding
statement: Self attention has quadratic O n squared time complexity in sequence length
slug: finding-self-attention-has-quadratic-o-n-squared-time-comple
source-paper: "[[2022-05-flash-attention]]"
source-ref: §3.2
fields:
- "[[nlp]]"
- "[[efficient-attention]]"
extracted-date: '2026-04-23'
finding-type: theoretical
hedging: asserted
relations:
  supports: []
  contradicts: []
  extends: []
  uses: []
  similar-to:
  - "[[finding-self-attention-has-o-n-squared-time-complexity-in-se]]"
---

# Self attention has quadratic O n squared time complexity in sequence length

> quadratic in n
— [[2022-05-flash-attention]] (§3.2)

## Evidence

- From [[2022-05-flash-attention]] (§3.2)

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
