# tpuf-benchmark report — TODOs

Reference for "good viz": `/home/kshivendu/projects/memory/bench/comparison.html`
(Qdrant Edge vs sqlite-vec vs LanceDB). Interactive SVG plots, one metric
selector driving small-multiple panels, color=engine / shape=config, hover
tooltips, tables demoted below the plots.

Our report: `docs/tpuf-detailed-report.html` (turbopuffer vs Qdrant Cloud).

---

## 1. Viz overhaul — CURRENT FOCUS

Diagnosis (measured): report is ~19,800px (~20 screens), **18 static `<canvas>`
charts**, 16 tables, 25 wall-of-text callouts, ~0 interactivity, 0 SVG.
Every finding appears 3× (chart + table + callout). Edge bench shows the same
breadth in a fraction of the space.

Target architecture (inspired by edge bench):
- [ ] Build ONE reusable interactive SVG plot component (metric `<select>` +
      clickable engine legend + hover tooltip), replacing hand-drawn canvas.
- [ ] Single metric selector drives all panels. Metrics to expose:
      WPS, QPS, read p50/p90/p99, write p50/p90/p99, upload time, indexing
      time, total upload+index time, data storage size, bytes read/s, bytes
      write/s. (Flag metrics we don't have data for — e.g. bytes/s may be
      absent for Cloud engines.)
- [ ] **Lead with the interactive plots; move tables below them.**
- [ ] Small-multiples per dataset (DBpedia / H&M / Multi-Tenant) sharing axes,
      legend, and the metric selector.
- [ ] Frontier framing where sweeps exist: QPS-sweep (1→50), concurrency-sweep
      (1→64), pinned-1r vs 4r vs serverless, ef — connected lines not separate
      bars.
- [ ] Log axes for wide dynamic ranges (RPS 8→538, latency 1.9→1891ms).
- [ ] Extract all numbers into a JS data model (like edge bench's DB/HM/WIKI
      arrays) that the plots read from — single source of truth.
- [x] §4 DBpedia: bar explorer (13 metrics, incl. recall + SPFresh range) leads;
      QPS sweep line chart (latency + cost crossover) replaces 3 canvases.
- [x] §5 H&M: concurrency sweep (total/worker RPS, p50, p99) replaces p99 canvas.
- [x] §6 MT: concurrency sweep (both engines) replaces RPS canvas.
- [x] §7 Recall: interactive recall bars per scenario, zoomed 80–100% (Qdrant strength).
- [x] §8.2+8.3: merged into one RPS-vs-concurrency sweep (serverless/pinned-1r/4r).
- [x] Reusable initBarExplorer / initSweep / initRecall SVG components, shared tooltip.
- [ ] REMAINING canvases → interactive: §3 upload-timeline, §8.1 warmup curve,
      §8.7 contention, §8.9 write-read (4 charts, time-series), §8.10 disk cold/warm.
- [ ] Remove dead canvas draw JS (old functions no-op via setupCanvas guard but bloat file).
- [ ] Demote 25 callouts to one tight footnote per section; delete overlap.
- [ ] Reconsider hero: currently showcases pinned-4r warmup, a config §9 calls
      "strictly worse."
- [ ] Theme-awareness + charset (edge bench served without UTF-8 shows mojibake).

## 2. Report content / structure (deferred, after viz)
- [ ] Consolidate scattered cold-start numbers (893 / 100-1500 / 1891 / 617ms)
      into one mode×dataset matrix.
- [ ] Split §8: "tpuf internals" vs "storage-tier comparison" (disk mode isn't
      a tpuf internal).
- [ ] TL;DR / summary at the very top.
- [ ] Per-experiment hardware table (node specs differ across sections).
- [ ] Add trial counts (n=) to every headline number.

## 3. Experiments (backlog)
- [ ] H&M tpuf upload re-runs (3-4×) — validate/kill "always wins H&M" (n=1).
- [ ] Filter selectivity sweep on H&M (1% / 10% / 50%) — shape of recall gap.
- [ ] Scale-to-zero idle timing — how long until serverless goes cold.
- [ ] Eventual-consistency mode — test the 10ms-floor explanation.
- [ ] Larger Qdrant node at p=32 — verify asserted "restores 5× advantage."
- [ ] Re-upload Qdrant DBpedia (deleted by earlier --engine filter bug).
- [ ] H&M cold search, H&M write_read.
- [ ] Pinned-1r SPFresh with real index.status polling.

## Done
- [x] SPFresh completion via ns.metadata().index.status (commit 888daf0)
- [x] DBpedia tpuf range extended to 3.1–7.3 min / 5 trials (75f546d)
- [x] Stale text, billing-floor misattribution, break-even inconsistency (512c647)
- [x] Per-worker RPS vs wall-clock throughput split (2e9c731)
