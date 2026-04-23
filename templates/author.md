---
type: author
name: "{{NAME}}"
affiliation: {{AFFILIATION}}
orcid: {{ORCID}}
---

# {{NAME}}

## Papers in this vault

```dataview
TABLE publication-date AS "Date", venue AS "Venue", quality.credibility AS "Cred."
FROM "papers"
WHERE contains(authors, [[{{NAME}}]])
SORT publication-date DESC
```

## Claims associated

```dataview
LIST
FROM "claims"
WHERE contains(file.inlinks, [[{{NAME}}]])
```
