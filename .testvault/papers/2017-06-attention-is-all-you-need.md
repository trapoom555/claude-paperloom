---
type: paper
ingest-mode: lite
title: Attention Is All You Need
slug: 2017-06-attention-is-all-you-need
authors:
- "[[Vaswani, Ashish]]"
- "[[Shazeer, Noam]]"
fields:
- "[[nlp]]"
- "[[attention-mechanism]]"
- "[[transformer]]"
publication-date: '2017-06-12'
ingested-date: '2026-04-23'
source-url: https://arxiv.org/abs/1706.03762
arxiv-id: '1706.03762'
doi: null
venue: NeurIPS 2017
quality:
  credibility: 5
  experimental-rigor: 5
  reproducibility: code-released
  overall: 5.0
  rationale: Large-scale ablations, full training code released.
findings: []
relations:
  cites: []
  builds-on: []
  supports: []
  contradicts: []
  extends: []
  similar-to: []
---

# Attention Is All You Need

## Key Takeaways

- Attention alone suffices — no recurrence, no convolutions.
- Parallelizable training, large speedups on WMT.

## Background

- Sequence transduction relied on RNNs (§1). 
- RNNs are inherently sequential (§1).

## Main Idea & Summary

- Replace recurrence with multi-head self-attention (§3.2).
- Add sinusoidal positional encodings (§3.5).
- Beat SoTA on WMT'14 EN-DE with 28.4 BLEU (§6.1).

## Critique

- Single-seed runs (§6.1, Table 2).
- Compute cost high — 8 P100 GPUs for 3.5 days.

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
