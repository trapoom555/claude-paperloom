---
type: paper
ingest-mode: lite
title: Flash Attention
slug: 2022-05-flash-attention
authors:
- "[[Dao, Tri]]"
fields:
- "[[nlp]]"
- "[[attention-mechanism]]"
- "[[efficient-attention]]"
publication-date: '2022-05-27'
ingested-date: '2026-04-23'
source-url: https://arxiv.org/abs/2205.14135
arxiv-id: '2205.14135'
doi: null
venue: NeurIPS 2022
quality:
  credibility: 5
  experimental-rigor: 4
  reproducibility: code-released
  overall: 4.7
  rationale: Widely adopted; official CUDA kernels released.
findings: []
relations:
  cites: []
  builds-on: []
  supports: []
  contradicts: []
  extends: []
  similar-to: []
---

# Flash Attention

## Key Takeaways

- IO-aware attention kernel — huge speedup.

## Background

- Attention is memory-bound on GPUs (§1).

## Main Idea & Summary

- Tile attention to avoid materializing the full O(n²) matrix in HBM (§3).

## Critique

- Only benchmarked on A100 (§4).

## Paper relations

*`cites` = bibliography matched against vault. Others are aggregated from this paper's finding edges at ingest. Edit in the YAML `relations` block above.*

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
