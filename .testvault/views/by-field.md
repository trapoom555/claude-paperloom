# Papers by Field

Papers grouped by research field.

```dataview
TABLE rows.file.link AS "Papers", rows.publication-date AS "Published", rows.quality.overall AS "Overall"
FROM "papers"
GROUP BY fields
SORT rows.ingested-date DESC
```
