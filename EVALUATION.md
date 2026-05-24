# Evaluation — Two-Plot Paradigm

> **Reconstruction is NOT metric optimization.** We never tune the algorithm to improve its biological metric. We only restructure for **speed**, and we accept tiny accuracy losses only when a math approximation makes a justified speed/quality tradeoff. Every accuracy drop must be annotated with the math reason.

## Why two plots (not one)

Traditional evolutionary search plots `iteration vs metric` because the policy searches *for better metric*. That wastes tokens on a reconstruction task — there is no "better" output than the R reference. We want **identical** outputs (or provably-bounded-near-identical).

So we plot two orthogonal axes against the same iteration index:

### Plot 1 — `wall-clock vs iteration`
- **x**: iteration number (each Acceleration Agent step)
- **y**: wall-clock seconds on the canonical fixture
- **Goal**: monotonically decreasing (or non-increasing).
- **What good looks like**: stepped descent — each commit drops the runtime; rejected rewrites are not shown (rolled back).

### Plot 2 — `accuracy vs iteration`
- **x**: same iteration number as Plot 1
- **y**: the algorithm-class parity metric (Pearson for ordinal, ARI for clustering, Procrustes for embedding, …)
- **Goal**: stay above the pre-registered threshold; ideally flat at the maximum.
- **What good looks like**: a flat horizontal line at ~1.0. Every dip must be a deliberate `(B) bounded ε-approximation` and the dip is annotated with the math reason (e.g., "row truncation at ε=1e-12 → Pearson 1.000 → 0.998").

## Three rules

1. **Only commit a rewrite if accuracy ≥ threshold.** Anything below the manifest's parity threshold is rolled back, full stop.
2. **The reference output is the ceiling, not the floor.** We never beat the R metric — beating it means our algorithm has drifted.
3. **Every accuracy drop is captioned.** A dip from 1.000 → 0.998 with no math-approximation justification is a bug, not an optimization.

## How to measure wall-clock

To keep the time plot meaningful:

1. **Warmup**: discard the first run. Reasons:
   - BLAS / OpenBLAS thread pool spin-up
   - JIT compilation (numba, scipy lazy imports)
   - Filesystem page cache (fixture data not yet in RAM)
   - Python module import overhead
2. **Then run 3 times**, sequentially, in the same process.
3. **Report mean** ± stddev. If stddev > 10% of mean, run 5× instead and report median.
4. **Fix BLAS thread count** to a known value before benchmarking:
   ```python
   import os
   os.environ["OMP_NUM_THREADS"] = "8"
   os.environ["OPENBLAS_NUM_THREADS"] = "8"
   os.environ["MKL_NUM_THREADS"] = "8"
   ```
5. Use `time.perf_counter()`, not `time.time()`.

See [engine/benchmark.py](engine/benchmark.py) for the canonical implementation.

## How to measure accuracy

Use the per-class metric from [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md) — same metric on every iteration so the plot's y-axis is comparable across the run.

## Iteration log format

Every Acceleration Agent step appends one block to `ITERATION_LOG.md` in the port directory. See [templates/ITERATION_LOG.template.md](templates/ITERATION_LOG.template.md) for the schema.

A typical entry:

```markdown
## iter 4 — 2026-05-24 12:34:01

- **action**: §3.1 MST ⊆ Delaunay (class-containment)
- **admissibility evidence**: Preparata & Shamos 1985; Toussaint 1980. Euclidean MST(P) ⊆ Delaunay(P) for P ⊂ R^d when d ≤ 4.
- **wall-clock (mean of 3, warmup excluded)**: 12.4 s ± 0.2 s
- **previous wall-clock**: 248 s ± 5 s
- **speedup**: 20.0×
- **accuracy (Pearson)**: 1.0000  (unchanged — exact equivalence by containment)
- **outcome**: ACCEPT
```

A dip-causing entry:

```markdown
## iter 7 — 2026-05-24 14:02:14

- **action**: §2.1 sparse soft-assignment row truncation (bounded ε)
- **admissibility evidence**: ‖W̃ − W‖_F ≤ κ · n · K · ε with κ = ‖X‖_∞ / δ_min. ε=1e-12 → bound = 3.4e-9 on this fixture.
- **wall-clock**: 0.92 s ± 0.03 s
- **previous wall-clock**: 12.4 s
- **speedup**: 13.5×
- **accuracy (Pearson)**: 0.9978  (was 1.0000)
- **why the dip**: thresholding R_{ij} ≤ 1e-12 then renormalising rows. The dropped mass redistributes on the surviving K/5 entries; this is the perturbation bound's empirical tail, well within Pearson ≥ 0.99.
- **outcome**: ACCEPT
```

A reject:

```markdown
## iter 8 — 2026-05-24 14:18:33

- **action**: kNN truncate pairwise distance matrix to k=10 (proposed §2.2 (B))
- **admissibility evidence**: bound holds only when downstream is local-neighbourhood; this port's downstream eigendecomposition touches all entries — NOT admissible.
- **outcome**: REJECT (admissibility check failed before running benchmark)
```

The log is parsed by [engine/plot_evolution.py](engine/plot_evolution.py) to produce the two plots.

## Generating the plots

```bash
python -m engine.plot_evolution \
    --port-dir <path-to-your-port>/py-TSCAN \
    --output examples/evolution.png
```

Output: a 2-panel figure with `time vs iteration` on top, `accuracy vs iteration` on bottom, x-axes aligned, accuracy dips annotated with the math reason inline.

## What the plots tell the reader

- Plot 1 (time): shows the **search trajectory** — which rewrites paid off (steep drop) vs marginal ones (flat).
- Plot 2 (accuracy): shows the **fidelity cost** — flat at 1.0 means the port is exact (class A or class B with only (E) and (C) rewrites); each dip is a deliberate, documented numerical sacrifice.

A "good" reconstruction has Plot 1 dropping 10×–100× while Plot 2 stays at 0.99–1.00. A "bad" reconstruction has Plot 2 wandering — meaning we drifted from the reference algorithm without admissibility evidence.

## Difference from RL benchmarks

| RL paper (e.g., AlphaDev) | omicverse-rebuildr |
|---|---|
| y = reward (better metric) | y₁ = time (lower is better), y₂ = accuracy (must stay ≥ threshold) |
| reward shapes the policy update | accuracy gates admissibility; time ranks admissible candidates |
| weight updates after each iter | no weight updates — in-context only |
| many iterations searching plateaus | one or two-digit iterations; stop when playbook exhausts |
| metric = ground truth | metric = parity with the R reference (the reference IS the spec) |

This is **verifier-guided test-time search**, not policy learning.
