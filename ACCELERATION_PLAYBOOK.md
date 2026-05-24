# Acceleration Playbook — Equivalence-Preserving Rewrites

> The **Acceleration Agent's action space**. Every rewrite below is a discrete action `a_t` with one of three admissibility proofs. The agent searches over this space, conditional on the parity gate still clearing.

## Reading the playbook

Each entry lists:
- **What the R reference does** (the inefficient pattern to look for).
- **The rewrite**.
- **Admissibility class**: (E) exact identity, (B) bounded ε-approximation, (C) class-containment theorem.
- **Cost change** (asymptotic).
- **When to apply** (preconditions).
- **Citation** (the theorem / paper the rewrite is grounded in).

A rewrite committed to the port must reference its playbook entry in code, e.g.:
```python
# acceleration: §1.2 Woodbury K×K Cholesky (E); valid when ridge ε > 0
# parity: pseudotime Pearson 0.9978 vs R Monocle 2 on Pancreas3.7k
```

---

## §1. Linear-algebra identities (exact)

### 1.1 Cache `X^T X` outside the loop  ·  (E)

**R pattern**: `for (iter in 1:max_iter) { ...; tmp <- t(X) %*% X %*% something; ... }`

**Rewrite**: compute `XtX = X.T @ X` once before the loop; reuse the result. Same for `X @ X.T` if that's what's inside.

**Cost**: `O(n d² · T)` → `O(n d²) + O(d³ · T)`.

**Precondition**: `X` is not modified inside the loop.

**Citation**: trivial memoisation.

---

### 1.2 Sherman–Morrison–Woodbury for `(I + λL)^{-1}`  ·  (E)

**R pattern**: `solve(diag(n) + lambda * L, b)` where `L = U Λ U^T` is rank-K with K ≪ n (typical: graph Laplacians, low-rank kernels).

**Rewrite**: use the Woodbury identity
```
(I_n + λ U Λ U^T)^{-1} = I_n − λ U (Λ^{-1} + λ U^T U)^{-1} U^T
```
which reduces the `n × n` Cholesky to a `K × K` one.

**Cost**: `O(n³)` → `O(n K² + K³)`.

**Precondition**: `Λ` is invertible (or use ridge: `Λ + ε I` with small ε; then the identity is exact on the nonzero eigenspace and ε-stable elsewhere).

**Citation**: Woodbury matrix identity; used in DDRTree port (`py-monocle2`).

---

### 1.3 Sherman–Morrison rank-1 update  ·  (E)

**R pattern**: `solve(A + u %*% t(v), ...)` recomputed for each new `(u, v)`.

**Rewrite**: maintain `A^{-1}` across updates via
```
(A + u v^T)^{-1} = A^{-1} − (A^{-1} u v^T A^{-1}) / (1 + v^T A^{-1} u)
```

**Cost**: `O(n³)` per update → `O(n²)`.

**Citation**: Sherman–Morrison formula.

---

### 1.4 Schur complement for block inverse  ·  (E)

When inverting `[[A, B], [C, D]]`, use Schur complement to avoid forming the full inverse.

**Citation**: standard.

---

### 1.5 Eigen vs SVD on small Gram matrix  ·  (E or B)

**R pattern**: `irlba(X, nv=k)` on tall X (`n ≫ d`).

**Rewrite**: compute the Gram matrix `G = X.T @ X` (size `d × d`, small), then `scipy.linalg.eigh(G)`; project to get singular vectors. Deterministic.

**Cost**: `O(n d²) + O(d³)` vs irlba's iterative `O(n d k)` — usually faster when `d ≪ n` and `k ≈ d`.

**Precondition**: numerical conditioning of `G` is acceptable. If not, fall back to `randomized_svd`.

**Citation**: classical Gram-matrix SVD; relative accuracy ≥ `1e-5` matches irlba in `py-monocle2`.

---

### 1.6 Cholesky / LDLT in-place vs explicit `solve`  ·  (E)

Prefer `scipy.linalg.cho_factor` + `cho_solve` over `np.linalg.solve` when the same LHS is reused with multiple RHS.

---

## §2. Sparsity-driven rewrites (bounded approximation)

### 2.1 Sparse soft-assignment row truncation  ·  (B)

**R pattern**: a dense soft-assignment / responsibility matrix `R ∈ R^{n × K}` where `R_{ij} = exp(−d²_{ij} / σ) / Σ_j exp(...)`. For small σ, almost all entries are ~0.

**Rewrite**: keep only the top-`K/5` entries per row (or threshold by `R_{ij} > ε`); zero the rest; renormalise rows.

**Admissibility**: bounded ε-approximation. Perturbation bound on downstream quantities (e.g., centres `W = X^T R · diag(R^T 1)^{-1}`):
```
‖W_new − W_old‖_F ≤ κ · n · K · ε,   κ = ‖X‖_∞ / δ
```
where δ is a lower bound on row sums after truncation. Derive κ in `MATH.md`.

**Cost**: `R^T R` drops from `O(K² n)` to `O((K/5)² n / K)`.

**Precondition**: σ is small relative to mean nearest-neighbour distance (i.e., the soft-assignment is concentrated). For σ = 0.001 in `py-monocle2`, entries below `1e-12` perturbed pseudotime Pearson by < `1e-3`.

**Citation**: same pattern as bounded sparsification in numerical clustering; bound is package-specific (must be derived per port).

---

### 2.2 Top-K kNN sparsification of pairwise distance matrix  ·  (B)

**R pattern**: dense `cellPairwiseDistances` = `as.matrix(dist(X))`. Memory `O(n²)`.

**Rewrite**: use `sklearn.neighbors.NearestNeighbors` with `k = O(log n)`; build a sparse CSR distance matrix.

**Admissibility**: bounded ε-approximation IF the downstream consumer is local-neighbourhood-bound (kNN classifier, MST, UMAP). For non-local consumers (full eigendecomposition), this is a different algorithm — not admissible.

**Precondition**: the downstream operation only consumes local distances. Verify by checking R source for any reduction that touches all `n²` entries.

**Cost**: `O(n²)` memory → `O(n k)`.

---

### 2.3 Subset before densify  ·  (E)

When the algorithm only consumes a fraction of features (e.g., "ordering genes"), subset the AnnData to those features *before* densifying. Saves `O(n · g_unused · 8 bytes)`.

**Precondition**: feature subset is decided before the loop. (Common.)

**Citation**: trivial; key for memory.

---

## §3. Graph-theoretic containments

### 3.1 MST ⊆ Delaunay (Euclidean point sets)  ·  (C)

**Theorem** (Preparata & Shamos 1985; Toussaint 1980): the Euclidean minimum spanning tree of a point set `P ⊂ R^d` is a subgraph of the Delaunay triangulation of `P`.

**R pattern**: `mst(dist(X))` on a dense pairwise distance matrix.

**Rewrite**:
```python
from scipy.spatial import Delaunay
from scipy.sparse.csgraph import minimum_spanning_tree
tri = Delaunay(P)
edges = extract_edges(tri.simplices)              # ~6n edges
sparse_dist = sparse_matrix(edges, euclidean(P[i], P[j]))
mst = minimum_spanning_tree(sparse_dist)
```

**Admissibility**: class-containment. The MST is **bit-identical** to running the full-graph MST.

**Cost**: `O(n²)` memory + `O(n² log n)` time → `O(n d)` memory + `O(n log n)` time (low-d).

**Precondition**: `d ≤ 4` or so (Delaunay scales badly in high d). Common for DDRTree-style centre spaces.

**Fallback**: if Qhull cannot triangulate (coplanar / degenerate input), fall back to a kNN graph (which is a (B) bounded approximation for MST).

**Citation**: Preparata & Shamos, *Computational Geometry* 1985; used in `py-monocle2` to enable 143k-cell trajectories (R reference OOMs at 164 GB).

---

### 3.2 kNN ⊆ relative-neighbourhood graph  ·  (C)

For some downstream graph reductions, the relative-neighbourhood graph (RNG) is a stricter superset of MST and a smaller intermediate than full kNN. Useful when MST itself is the target.

**Citation**: Toussaint 1980.

---

### 3.3 Connected-component reduction before global solve  ·  (E)

If a graph algorithm operates per-component, split first via `scipy.sparse.csgraph.connected_components`, solve each independently, recombine.

**Admissibility**: exact if the algorithm has no global term.

---

## §4. Loop fusion / vectorisation

### 4.1 Replace nested R `for` with NumPy vectorisation  ·  (E)

Identify accumulator patterns (`for i { acc <- acc + f(X[i]) }`) and replace with `f(X).sum(axis=...)` or `np.einsum`.

### 4.2 Use `scipy.sparse` primitives over hand-rolled matmul  ·  (E)

Bioconductor sometimes hand-codes sparse-dense products. `scipy.sparse.csr_matrix.dot` is faster and has fewer bugs.

### 4.3 `np.einsum` over `np.matmul` chains  ·  (E)

For chained contractions like `A @ B @ C @ x`, `einsum` picks an optimal contraction order. Use `optimize='optimal'`.

### 4.4 Numba-jitted hot inner loops  ·  (E)

For per-cell or per-iteration scalar loops that cannot be vectorised cleanly. Pure-Python fallback must remain available so the port works without numba.

---

## §5. Algorithm-class-specific shortcuts

### 5.1 (Ordinal / pseudotime) Skip ELBO recompute  ·  (E or B)

**R pattern**: every iteration of an alternating optimisation recomputes the full objective `‖X − W Z‖² + λ tr(Z^T L Z)`.

**Rewrite**: terminate on `‖ΔY‖_F / ‖Y‖_F < tol` instead. (E) iff `tol` is chosen to make the iteration count match (rare); (B) otherwise with bound on cumulative drift.

### 5.2 (Clustering) BIC-on-subsample, refine on full  ·  (B)

For Mclust-style model-selection, run BIC scan on a stratified subsample, then refit the winner on the full data.

### 5.3 (Statistical inference) Compute test statistic once, p-value on demand  ·  (E)

Skip computing p-values for genes that fail a pre-filter (e.g., zero variance).

### 5.4 (Embedding) Randomized SVD with deterministic seed  ·  (B)

For PCA / CCA inputs, `sklearn.utils.extmath.randomized_svd(seed=...)` with `n_iter ≥ 4` matches `irlba` to ~`1e-6` and is faster on tall matrices.

---

## §6. What is NOT in this playbook

These are **out of scope** because they change the algorithm rather than restructure it:

- Drop a step "to save time" (not admissible).
- Replace one model with another (different objective, different fixed point).
- Reduce iteration count below the R default without proof of convergence.
- Use a different initialisation that breaks Pearson with the R reference.

If you find yourself wanting to do these, you are no longer in the Acceleration Agent's action space — you are starting a different port.

---

## Search heuristic

The Acceleration Agent should try the playbook in roughly this order, since later rewrites depend on earlier ones being in place:

1. §3.3 (component split) — often free.
2. §1.1 (memoisation) — almost always applicable.
3. §1.5 (eigen vs irlba) — verify deterministic agreement.
4. §4.1–4.3 (vectorisation) — quick wins.
5. §2.3 (subset before densify) — large memory wins.
6. §1.2 (Woodbury) — when there's a `(I + λL)` solve.
7. §3.1 (MST ⊆ Delaunay) — when there's a dense-distance MST.
8. §2.1 (sparse soft-assignment) — last, requires the perturbation-bound derivation.

Track tried rewrites in a per-port `MATH.md` so subsequent ports can short-circuit.
