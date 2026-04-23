# Papers by Author

Papers grouped by author.

```dataview
TABLE rows.file.link AS "Papers", rows.publication-date AS "Published", rows.fields AS "Fields"
FROM "papers"
GROUP BY authors
SORT rows.ingested-date DESC
```
