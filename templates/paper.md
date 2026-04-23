---
type: paper
title: "{{TITLE}}"
slug: {{SLUG}}
authors: {{AUTHORS_YAML}}
fields: {{FIELDS_YAML}}
publication-date: {{PUBLICATION_DATE}}
ingested-date: {{INGESTED_DATE}}
source-url: {{SOURCE_URL}}
arxiv-id: {{ARXIV_ID}}
doi: {{DOI}}
venue: {{VENUE}}
quality:
  credibility: {{CREDIBILITY}}
  experimental-rigor: {{EXPERIMENTAL_RIGOR}}
  reproducibility: {{REPRODUCIBILITY}}
  overall: {{QUALITY_OVERALL}}
  rationale: "{{QUALITY_RATIONALE}}"
claims: {{CLAIMS_YAML}}
relations:
  cites:        {{CITES_YAML}}
  builds-on:    {{BUILDS_ON_YAML}}
  supports:     {{PAPER_SUPPORTS_YAML}}
  contradicts:  {{PAPER_CONTRADICTS_YAML}}
  extends:     {{PAPER_EXTENDS_YAML}}
  similar-to:  {{PAPER_SIMILAR_TO_YAML}}
---

# {{TITLE}}

## Key Takeaways

{{KEY_TAKEAWAYS}}

## Background & Motivation

{{BACKGROUND}}

## Related Work & Gaps

{{RELATED_WORK}}

## Core Idea & Contributions

{{CORE_IDEA}}

## Method

{{METHOD}}

## Experimental Setup

{{EXPERIMENTAL_SETUP}}

## Results & Analysis

{{RESULTS}}

## Discussion & Implications

{{DISCUSSION}}

## Limitations & Open Questions

{{LIMITATIONS}}

## Critique

{{CRITIQUE}}

## Paper relations

*Edit edges in the YAML `relations` block above — these auto-render from it. `cites` = bibliography; the rest are aggregated from this paper's claim edges at ingest.*

- **Cites →** `= this.relations.cites`
- **Builds on 🔧** `= this.relations["builds-on"]`
- **Supports ✓** `= this.relations.supports`
- **Contradicts ⚡** `= this.relations.contradicts`
- **Extends ↗** `= this.relations.extends`
- **Similar to ≈** `= this.relations["similar-to"]`

### Cited by (papers in the vault that cite this one)

```dataview
LIST
FROM "papers"
WHERE contains(relations.cites, this.file.link) AND file.path != this.file.path
```
