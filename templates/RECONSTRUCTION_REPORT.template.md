# Reconstruction Report — py-<PkgName>

> Generated **after** the port clears the parity gate and the Acceleration loop terminates. This is the structured "is the port complete?" audit.

## 1. Identity

| Field | Value |
|---|---|
| Python package | `py<pkgname>` |
| Upstream R package | `<UpstreamR>` v`<pinned-version>` |
| Upstream source | <CRAN / Bioconductor / GitHub URL> |
| Algorithm class | <ordinal / clustering / …> |
| Parity threshold (pre-registered) | <value> |
| Final parity value | <value> |
| Audit class | <A / B / C> |
| Total LOC (target language, excluding tests) | <count> |
| Wall-clock speedup vs R reference | <Nx> on `<fixture>` |
| Memory tractability gain | <yes/no> + details |

## 2. R function coverage audit

> Auto-populated by `engine/r_function_audit.py` from the upstream's `NAMESPACE` + `R/*.R`. Every exported R function must be in the table. Internal helpers used by exports are also listed.

### 2.1 Exported R functions (from NAMESPACE)

| R function | Python equivalent | Status | Tests | Notes |
|---|---|---|---|---|
| `paramSweep` | `pydoubletfinder.param_sweep` | ✅ ported | `test_param_sweep_parity.py` | bit-equivalent given matching PCA |
| `summarizeSweep` | `pydoubletfinder.summarize_sweep` | ✅ ported | `test_smoke.py::test_summary` | — |
| `find.pK` | `pydoubletfinder.find_pK` | ✅ ported | `test_find_pK.py` | — |
| `doubletFinder_v3` | `pydoubletfinder.doublet_finder` | ✅ ported (renamed) | `test_exact_match.py` | name change documented |
| `modelHomotypic` | `pydoubletfinder.model_homotypic` | ✅ ported | — | trivial |
| `<rare_export>` | — | ⛔ skipped | — | dead code in upstream / never called |

### 2.2 Internal R helpers (R/*.R, not exported)

| R helper | Used by | Python equivalent | Status |
|---|---|---|---|
| `.bcMetric` | `find.pK` | inlined into `_bimodality_coefficient` | ✅ |
| `.kde_smooth` | `find.pK` | `pydoubletfinder.kde.bkde` | ✅ |
| `<other>` | — | — | — |

### 2.3 Coverage summary

| Category | Count | Coverage |
|---|---|---|
| Exported R functions in NAMESPACE | <N_export> | <N_ported> / <N_export> = <%> |
| Internal helpers reachable from exports | <N_internal> | <N_ported_internal> / <N_internal> = <%> |
| Total R LOC (R/*.R) | <N_r_loc> | — |
| Total Python LOC (`<pkg>/*.py`) | <N_py_loc> | ratio = <r> |

A complete port has ≥ 95% of exported functions ported AND every internal helper that's transitively reachable from a ported export.

### 2.4 Deliberately skipped

| R function | Reason for skipping |
|---|---|
| `<r_fn>` | <e.g., "wrapper around defunct biocLite()", "interactive plotting only", "only used by removed function X"> |

### 2.5 Dependencies reused from omicverse (ecosystem audit)

From [DISCOVERY.md](DISCOVERY.md). This is how the **ecosystem** compounds — each reused dep is a port we didn't write twice.

| R dep | omicverse port reused | Reused as | Approx. LOC saved |
|---|---|---|---|
| `mclust` | `py-mclustR` v0.x | hard dep (pyproject.toml) | ~3000 |
| `<dep>` | `py-<X>` | optional dep | ~XXX |

**Total saved by reuse**: ~YYYY LOC.

R deps **without** an omicverse mirror, replaced by native-Python equivalents:

| R dep | Python replacement | Reason for no port |
|---|---|---|
| `mgcv` | `pygam` | mature native equivalent |
| `igraph` | `networkx` | mature native equivalent |
| `ggplot2`, `shiny`, `grid`, etc. | matplotlib (planned) | plotting/GUI, out of algorithmic scope |

## 3. Parity evidence

### 3.1 Per-output parity (from manifest.yaml::outputs)

| Output | Class | Threshold | Final value | Pass |
|---|---|---|---|---|
| `Pseudotime` | ordinal | 0.99 | 0.9978 | ✅ |
| `State` | classification | 0.95 | 0.99 | ✅ |
| `branch_points` | ranked | 0.80 | 1.00 | ✅ |

### 3.2 Per-fixture parity

| Fixture | Pseudotime Pearson | Wall-clock (Py) | Wall-clock (R) | Speedup |
|---|---|---|---|---|
| paul15 (2730 × 3451) | 0.9978 | 0.4 s | 3.2 s | 8× |
| HSMM (271 × 47k) | 0.999 | 0.1 s | 3.0 s | 30× |
| Pancreas (3.7k × 28k) | 0.9900 | 0.9 s | 92 s | **102×** |
| Neuro (143k × 24k) | 0.99 | 102 s | OOM (164 GB) | tractability gain |

### 3.3 Reference command (reproducible)

```bash
conda activate $R_TEST_ENV
Rscript tests/r_reference_driver.R data/fixture.h5ad data/reference_output.json

conda activate $PYTHON_TEST_ENV
python tests/_run_candidate.py data/fixture.h5ad data/candidate_output.json
pytest tests/test_exact_match.py -v
```

## 4. Acceleration evidence

### 4.1 Two-plot evaluation

![evolution](examples/evolution.png)

- **Plot 1 (top)**: wall-clock vs iteration. Each dot is one Acceleration Agent commit.
- **Plot 2 (bottom)**: parity metric vs iteration. Dips are annotated with math reason.

### 4.2 Accepted rewrites

| Iter | Section | Admissibility | Speedup | Accuracy delta |
|---|---|---|---|---|
| 0 | (baseline) | — | 1× | — |
| 1 | §1.1 cache X^T X | E (memoisation) | 1.4× | 0.0000 |
| 2 | §1.5 eigh on Gram | E (algebraic) | 2.1× | 0.0000 |
| 3 | §1.2 Woodbury K×K | E (Woodbury identity) | 8.3× | 0.0000 |
| 4 | §3.1 MST ⊆ Delaunay | C (Toussaint 1980) | 12.7× | 0.0000 |
| 5 | §2.1 sparse R | B (κ·n·K·ε bound) | 28.4× | -0.0022 |
| **Final** | — | — | **102×** | -0.0022 |

### 4.3 Rejected rewrites

| Iter | Section | Reason for rejection |
|---|---|---|
| 6 | §2.2 kNN distance | downstream eigendecomp touches all entries — inadmissible |
| 7 | §5.4 randomized SVD | accuracy dropped to 0.94 < 0.99 threshold |

## 5. Code quality audit

All items below are **mandatory** for release. "Deferred" is not a valid status.

| Check | Status |
|---|---|
| `pip install -e .` in fresh env | ✅ |
| `pytest -q` green | ✅ <N>/<N> tests pass |
| `examples/compare_R_vs_Python.ipynb` (6-section schema; outputs committed) | ✅ |
| `examples/tutorial_<dataset>.ipynb` (one subsection per public function; outputs committed) | ✅ |
| `examples/function_by_function_R_parity.ipynb` (R⇄Python param dictionary + per-function parity; outputs committed) | ✅ |
| `examples/r_per_function_dump.R` (R driver for Notebook 3) | ✅ |
| `examples/evolution.png` rendered from `ITERATION_LOG.md` | ✅ |
| `README.md` has all required sections | ✅ |
| `MATH.md` has perturbation bounds for every (B) rewrite | ✅ |
| `ITERATION_LOG.md` complete and parseable | ✅ |
| `DISCOVERY.md` committed (Phase 0.5 artefact) | ✅ |
| `AUDIT.md` produced by `engine.r_function_audit` | ✅ |
| License compatible with upstream | ✅ <license> |
| Version pinned to 0.1.0 | ✅ |
| GitHub repo created under `omicverse/` | ✅ <URL> |
| PyPI release passed CI | ✅ <URL> |

## 6. Known limitations

- Fixture-level equivalence only — not proved over full input domain.
- <e.g., specific edge cases not yet handled>
- <e.g., S4 / Bioconductor-specific features not supported>
- <e.g., upstream R bugs we did NOT replicate, by design — list them>

## 7. Integration into omicverse main package

- Vendored at: `omicverse/external/<pkgname>/` (or `omicverse/single/_<pkgname>.py`)
- Exposed as: `omicverse.<subpackage>.<PkgName>`
- Tutorial added at: `omicverse-guide/tutorial_<pkg>.ipynb`

## 8. Sign-off

| Field | Value |
|---|---|
| Author | <handle> |
| Date | <YYYY-MM-DD> |
| Total port duration (active) | <hours/days> |
| Total Acceleration iterations | <N> (accepted) / <M> (proposed) |
