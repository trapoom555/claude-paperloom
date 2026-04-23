# High Credibility Papers

Papers with `quality.overall` ≥ 4.0, sorted by score descending.

```dataview
TABLE publication-date AS "Published", authors AS "Authors", quality.credibility AS "Credibility", quality.experimental-rigor AS "Rigor", quality.reproducibility AS "Repro", quality.overall AS "Overall"
FROM "papers"
WHERE quality.overall >= 4.0
SORT quality.overall DESC
```
