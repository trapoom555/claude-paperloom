# Recent Papers

Papers sorted by ingestion date, most recent first.

```dataview
TABLE publication-date AS "Published", ingested-date AS "Ingested", authors AS "Authors", fields AS "Fields", quality.overall AS "Overall"
FROM "papers"
SORT ingested-date DESC
LIMIT 20
```
