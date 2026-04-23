---
type: field
name: {{NAME}}
parent-field: {{PARENT_FIELD}}
---

# {{NAME}}

## Papers

```dataview
TABLE publication-date AS "Date", authors AS "Authors", quality.credibility AS "Cred."
FROM "papers"
WHERE contains(fields, [[{{NAME}}]])
SORT publication-date DESC
```

## Claims

```dataview
TABLE source-paper AS "Paper", hedging AS "Hedging", claim-type AS "Type"
FROM "claims"
WHERE contains(fields, [[{{NAME}}]])
SORT extracted-date DESC
```
