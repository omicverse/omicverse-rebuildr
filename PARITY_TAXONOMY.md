# Parity Taxonomy — 8 Algorithm Classes

> Pick the class **before** writing any agent code. The class fixes the parity metric, which fixes the pass/fail threshold in `manifest.yaml`. The threshold is committed before agent work begins and is read-only during the agent loop.

## The table

| # | Algorithm class | Parity criterion | Default threshold | Example R packages |
|---|---|---|---|---|
| 1 | **Deterministic numerical** (3 sub-tiers — see below) | element-wise: `max abs err < tol` (optionally `rtol`-scaled) | **standard: `1e-8`**; strict: `1e-13`; bounded: `1e-6` | BandNorm, scHiCluster kernels |
| 2 | **Stochastic numerical** | distributional: Kolmogorov–Smirnov ≤ τ or Wasserstein-1 ≤ τ | KS-p ≥ 0.05 *or* W₁ ≤ 1% of scale | MCMC draws, Bayesian posteriors |
| 3 | **Combinatorial clustering** | label-invariant: ARI / NMI / Fowlkes–Mallows | ARI ≥ 0.95 | mclust, scDblFinder clusters, sc3 |
| 4 | **Continuous embedding** | rotation-invariant: Procrustes similarity (1 − min‖.‖² after best rotation/translation/scaling) | Procrustes ≥ 0.95 | Seurat CCA, PCA, UMAP, t-SNE |
| 5 | **Ranked output** | top-K Jaccard / Spearman correlation of the ranking | top-50 Jaccard ≥ 0.8; Spearman ≥ 0.9 | COSG marker genes, DE rankings |
| 6 | **Ordinal output (pseudotime)** | Pearson / Spearman correlation of per-cell values | Pearson ≥ 0.99 (treats ≥ `1 − 1e-12` as exact — `pearsonr` is itself f64-noisy) | Monocle 2 pseudotime, Slingshot |
| 7 | **Classification (binary / multi)** | label agreement / F1 | Agreement ≥ 0.95 | DoubletFinder, scDblFinder labels |
| 8 | **Statistical inference** | rank correlation on −log10 p + top-k overlap | Spearman ≥ 0.90 on −log10 p; top-50 Jaccard ≥ 0.7 | miloR DA test, limma/DESeq2, tradeSeq |

### Deterministic sub-tiers (class 1)

The class-1 threshold needs to absorb two independent error sources:

| Source | Typical magnitude |
|---|---|
| f64 rounding + BLAS divergence (R uses one BLAS, Python uses another) | `eps · √N` ≈ `1e-14` to `1e-10` |
| Any (B) bounded ε-approximation introduced by an Acceleration rewrite | per-rewrite, typically `1e-9` to `1e-6` (sum of admitted rewrites, derived in `MATH.md`) |

So a single fixed threshold is the wrong abstraction. Pick a sub-tier per port:

| Sub-tier (`manifest.yaml::algorithm_class`) | Default `atol` | Default `rtol` | Hard ceiling | When to use |
|---|---|---|---|---|
| `deterministic-strict` | `1e-13` | `1e-15` | `1e-13` | element-wise / single-pass / same BLAS. Example: rust-bandnorm. |
| `deterministic` **(alias)** / `deterministic-standard` | **`1e-8`** | — | `1e-8` | Default. One or two matmul / PCA, cross-BLAS R↔Py is fine. |
| `deterministic-bounded` | `1e-6` | — | `1e-6` | Contains (B) ε-approximation rewrites. `MATH.md` must derive `Σ bound ≤ atol`. |

**Hard ceiling rule**: any `deterministic-*` threshold above `1e-6` is rejected by `is_pass()` — at that scale "deterministic" has lost meaning and the port should switch to `ordinal` (Pearson) or `embedding` (Procrustes) instead. This is non-negotiable; widening the gate is the cardinal sin the protocol forbids.

**Relative-tolerance mode**: when output values span many orders of magnitude (p-values, abundance counts, eigenvalues), set `parity_rtol` in the manifest:

```yaml
algorithm_class: deterministic-standard
parity_threshold: 1.0          # required when rtol > 0; pass iff returned-value < 1
parity_rtol: 1e-8              # error scaled by rtol·|reference|
parity_atol: 1e-10             # small absolute floor for values near zero
```

`parity_deterministic(..., rtol=...)` then returns `max(|ref - cand| / (rtol·|ref| + tiny))`, and `parity_threshold` caps that normalised quantity (typically `1.0`).

**Why ordinal treats `1.0` as `≥ 1 − 1e-12`**: `scipy.stats.pearsonr` accumulates f64 rounding internally. Even on bit-identical inputs the returned `r` is typically `0.9999999999999999`, not literal `1.0`. The `is_pass` helper subtracts `1e-12` from the ordinal threshold before the comparison so a perfect port doesn't fail by one ulp.

## How to pick the class

Ask one question: **what does the R function return?**

- A vector / matrix of floats meant to be compared bit-by-bit → **(1) Deterministic**.
- Samples from a posterior or any RNG-driven simulation → **(2) Stochastic**.
- A vector of cluster IDs (integer labels with no canonical ordering) → **(3) Clustering**.
- A coordinate matrix where the absolute basis is meaningless (PCA, CCA, MDS) → **(4) Embedding**.
- A ranked list of features (gene names, top-K) → **(5) Ranked**.
- A continuous monotonic per-cell ordering (pseudotime, latent time, z) → **(6) Ordinal**.
- A binary or multi-class label per cell (where the labels HAVE canonical meaning, e.g., "Doublet"/"Singlet") → **(7) Classification**.
- A vector of p-values or effect sizes from a statistical test → **(8) Inference**.

If the R function returns **multiple outputs** with different classes (e.g., embedding + clustering + DE table), give each its own gate in `manifest.yaml::outputs:` and require all to pass.

## Why class-aware (not uniform)

A naive "element-wise equality with tolerance" works only for class 1. For clustering, `[0,1,1,0]` and `[1,0,0,1]` encode the same partition — needs ARI. For embeddings, two coordinate matrices differing by an orthogonal rotation are the same up to basis choice — needs Procrustes. Empirically (Omicverse-RebuildR §3.2), applying a uniform element-wise gate to all 10 packages false-fails 2 of them (one clustering, one embedding port); the class-aware gate passes all 10.

## The metrics, with the canonical implementation to use

| Class | Use this | Notes |
|---|---|---|
| 1 Deterministic | `np.allclose(a, b, rtol=0, atol=tol)` + `scipy.stats.pearsonr(a.ravel(), b.ravel())` | Demand both: element-wise + Pearson |
| 2 Stochastic | `scipy.stats.ks_2samp(a, b)` or `scipy.stats.wasserstein_distance(a, b)` | Use seed-locked R reference |
| 3 Clustering | `sklearn.metrics.adjusted_rand_score(labels_r, labels_py)` | Always ARI; NMI as secondary |
| 4 Embedding | `scipy.spatial.procrustes(M_r, M_py)` returns `(_, _, disparity)`; similarity = `1 - disparity` | Sign-flip ambiguity is absorbed |
| 5 Ranked | `len(set(top_k_r) & set(top_k_py)) / len(set(top_k_r) \| set(top_k_py))` + `scipy.stats.spearmanr` | top-50 is the conventional K |
| 6 Ordinal | `scipy.stats.pearsonr(pseudotime_r, pseudotime_py)` + `spearmanr` | Pearson is the primary; demand ≥0.99 |
| 7 Classification | `sklearn.metrics.f1_score(y_r, y_py, average='binary' or 'macro')` + `(y_r == y_py).mean()` | If labels are "Doublet" / "Singlet", keep that — don't relabel to 0/1 |
| 8 Inference | `scipy.stats.spearmanr(-np.log10(p_r), -np.log10(p_py))` + top-K Jaccard | Use −log10 p to weight small p-values more |

All of these are implemented in [engine/parity_metrics.py](engine/parity_metrics.py) — import from there to avoid re-deriving thresholds across ports.

## What about Bonferroni-on-thresholds?

Don't. Each port has **one** algorithm-class gate at one threshold, fixed before agent work. No multiple-comparison correction; no per-fixture adjustment. The gate either clears or it doesn't.

## Stochastic packages — how to make them deterministic-enough to test

For class 2 / 3 / 7 / 8 algorithms with internal RNG:

1. Pin the seed in `manifest.yaml::seed:` (default 42).
2. In both `ref_runner.R` and `parity_test.py`, set the seed **immediately before** calling the algorithm. R uses `set.seed(42)`; Python uses `np.random.seed(42)` and `random.seed(42)`.
3. If the R RNG and Python RNG produce different streams (they will), the comparison degrades from element-wise to distributional (class 2) or label-invariant (class 3) — that's the point of the taxonomy.

Document any unavoidable stochastic divergence in the port's `MATH.md` so future maintainers know which numerical agreements are bit-exact vs distributional.

## When the gate fails in Step 3

Order of suspicion (in decreasing frequency on real ports):

1. **Off-by-one indexing**: R is base-1, Python is base-0.
2. **Transposed input**: R is column-major; many R packages take `genes × cells` while Python tools default to `cells × genes`.
3. **Default argument drift**: e.g., R's `range(...)` literal `1:9` ≠ Python `range(1, 9)` (which is `[1..8]`).
4. **Log base**: R `log()` is base-e; some R functions silently use `log2`. Check.
5. **Sparse vs dense intermediates**: R's `Matrix::sparseMatrix` ⇄ `dgCMatrix` vs SciPy CSR — verify symmetry, row vs col order.
6. **Numerical solver default tol**: `eigen`, `svd`, `qr` ship with different default tolerances.
7. **Cluster ID stability**: Mclust ordering differs run-to-run unless seeded — use ARI, not label agreement, for clustering.
8. **NA handling**: R silently drops `NA`; numpy/pandas behaviour differs.

Ablate each in order. Do not loosen the gate.
