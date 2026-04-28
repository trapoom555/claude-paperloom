---
type: finding
statement: "{{STATEMENT}}"
slug: {{SLUG}}
source-paper: "[[{{SOURCE_PAPER_SLUG}}]]"
source-ref: "{{SOURCE_REF}}"
fields: {{FIELDS_YAML}}
extracted-date: {{EXTRACTED_DATE}}
finding-type: {{FINDING_TYPE}}
hedging: {{HEDGING}}
relations:
  supports:    {{SUPPORTS_YAML}}
  contradicts: {{CONTRADICTS_YAML}}
  extends:     {{EXTENDS_YAML}}
  uses:        {{USES_YAML}}
  similar-to:  {{SIMILAR_TO_YAML}}
---

# {{STATEMENT}}

> {{QUOTE_OR_PARAPHRASE}}
— [[{{SOURCE_PAPER_SLUG}}]] ({{SOURCE_REF}})

## Evidence

{{EVIDENCE_BULLETS}}

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
FROM outgoing([[]]) OR [[]]
WHERE type = "finding"
```
