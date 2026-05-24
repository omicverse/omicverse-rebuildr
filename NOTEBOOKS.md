# Notebooks — Required Deliverables

> Every port ships **three pre-executed notebooks** under `examples/`. These are NOT optional. The protocol started with two (v2), then a third was added (v3) after the py-TSCAN port surfaced that the first two don't cover users migrating R code line-by-line.

## Why three are required

A port has four audiences:

| Audience | What they need | Where they look |
|---|---|---|
| **Reviewer / scientist** evaluating whether to trust the port | Visual side-by-side proof that Python ≡ R numerically at the pipeline level | Notebook 1 |
| **End user** new to the algorithm, wants a Python walkthrough | A copy-pastable tour of every public function | Notebook 2 |
| **R user porting their existing code** to Python | A function-level dictionary: every R parameter → Python parameter, with worked side-by-side calls | Notebook 3 |
| **CI / automation** | The pre-registered parity gate | `tests/test_exact_match.py` |

The parity test gives a numerical PASS/FAIL. The reviewer can't audit it by eye. The notebooks make the parity **visible**, the API **legible**, and the **R→Python translation** mechanical.

## Notebook 1 — `compare_R_vs_Python.ipynb`

**Purpose**: a human-readable, side-by-side parity validation against R, on the canonical fixture.

**Required sections** (skip any → port not done):

1. **Setup**
   - Load `data/manifest.yaml`; print the pre-registered algorithm class + threshold.
   - Load the canonical fixture (path from manifest).
   - Pin BLAS thread count (see `engine/benchmark.py::lock_blas_threads`).

2. **R reference run**
   - Invoke `tests/r_reference_driver.R` via `subprocess.run([conda run -p $R_TEST_ENV Rscript ...])`.
   - Print wall-clock + log the R version + upstream package version.

3. **Python candidate run**
   - Invoke `tests/_run_candidate.py` (or import directly).
   - Print wall-clock.

4. **Per-output parity** — one subsection per `manifest.yaml::outputs[]` block. Pattern by class:

   | algorithm_class | Visual |
   |---|---|
   | `deterministic` | line plot R vs Py overlay + max abs err |
   | `clustering` | confusion-matrix heatmap (R rows, Py cols) + ARI |
   | `embedding` | side-by-side scatter (first 2 PCs) + Procrustes |
   | `ordinal` | scatter (x=R pseudotime, y=Py pseudotime) + Pearson + Spearman |
   | `classification` | confusion-matrix heatmap + F1 |
   | `ranked` | top-K Venn / Jaccard table |
   | `inference` | -log10(p) scatter + top-K overlap |
   | `stochastic` | KDE overlay + KS statistic |

5. **Wall-clock comparison**
   - Bar chart: R reference vs Py default vs Py acceleration (if class B/C).
   - Note the speedup factor.

6. **Verdict**
   - Render the pre-registered gate from `manifest.yaml` with each output's measured value.
   - Final line: "PASS — all outputs cleared the pre-registered gate" or "FAIL — see ...".

**Pre-execution requirement**: the committed `.ipynb` must contain executed outputs. Re-run before each release via:

```bash
jupyter nbconvert --to notebook --execute examples/compare_R_vs_Python.ipynb \
    --output compare_R_vs_Python.ipynb
```

## Notebook 2 — `tutorial_<dataset>.ipynb`

**Purpose**: a walkthrough of every public function on a real dataset.

**Required sections** (skip any → port not done):

1. **What this package does** (1 paragraph)
   - Cite the upstream paper.
   - Say what input it expects (AnnData? gene×cell DataFrame?).
   - Say what output it produces.

2. **Install + import** (1 short cell)
   - `pip install py<pkg>`.
   - `from <pkg> import ...`.

3. **Load demo data**
   - Use the same fixture as Notebook 1 if appropriate, OR a public scanpy/AnnData dataset (`scanpy.datasets.paul15`, `scanpy.datasets.pbmc3k`, etc.) for variety.
   - Print shape, cell types, expected workflow length.

4. **One subsection per public function** — the audit's "exported R algorithmic functions" list (§2.2 of the reconstruction report). Each must:
   - State what the function does (1–2 sentences).
   - Show R one-liner equivalent in a `markdown` cell for users coming from R.
   - Call the function with sensible defaults.
   - Show return type + shape.
   - Plot or print the result (one figure per function minimum).

5. **Class-API mirror**
   - Same workflow re-written as a method chain on the AnnData-native class.
   - Show how results land in `adata.obs / .obsm / .uns`.

6. **Common pitfalls / FAQ** — at least 3 items, drawn from the parity-failure suspicion list in [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md):
   - Row vs column convention (genes×cells vs cells×genes).
   - Base-1 vs base-0 indexing.
   - Seed handling for the stochastic step (if any).
   - Any (B) bounded-approximation knobs (cite `MATH.md`).

7. **Where to go next**
   - Link to the package's `README.md`, `RECONSTRUCTION_REPORT.md`, and the upstream R package URL.

**Pre-execution requirement**: same as Notebook 1. Re-run before each release.

## Notebook 3 — `function_by_function_R_parity.ipynb`

**Purpose**: a function-level R⇄Python dictionary for users migrating existing R code. For **every public R function** in `RECONSTRUCTION_REPORT §2.2`, side-by-side R and Python calls on the **same input** with **parameter-by-parameter documentation**.

This is different from Notebooks 1 and 2:
- Notebook 1 is **pipeline-level** parity (compare the full output of running everything end-to-end).
- Notebook 2 is **Python-only** function tutorial (no R code shown).
- Notebook 3 is **function-level** parity (each function called in isolation, R and Python, on the same input, with every parameter explained).

**Required sections** (skip any → port not done):

1. **Intro + setup**
   - One paragraph: who this notebook is for ("R users porting code to Python").
   - Load the canonical fixture into Python.
   - Pre-dump per-function R outputs via a single R driver script (`r_per_function_dump.R`) → JSON, then the Python cells compare against it.

2. **One subsection per public function**, each with:

   a. **Function name** as section heading.

   b. **What it does**: one-paragraph summary, citing the upstream R help page.

   c. **Parameter table** — every parameter from the R function:

      | R name | Python name | Type | Default | Range / values | Description |
      |---|---|---|---|---|---|
      | `data` | `data` | matrix or DataFrame | — | genes × cells | the input expression matrix |
      | `clusternum` | `clusternum` | int or iterable[int] | `2:9` | `≥ 2` | candidate G values for Mclust |
      | … | … | … | … | … | … |

      Every R parameter MUST have a row, even if the Python equivalent is `**kwargs` or computed internally. Differences (renames, type changes, removed-because-defaulted) must be explicitly called out in the **Description** column.

   d. **R one-liner** in a markdown code block — exactly what an R user would write:

      ```r
      procdata <- preprocess(lpsdata, takelog=TRUE, logbase=2, minexpr_value=1,
                             minexpr_percent=0.5, cvcutoff=1)
      ```

   e. **Python equivalent** in a code cell:

      ```python
      procdata = pytscan.preprocess(lpsdata, takelog=True, logbase=2,
                                    minexpr_value=1.0, minexpr_percent=0.5, cvcutoff=1.0)
      ```

   f. **Output comparison** — load the dumped R output, compare to Python's, print parity:
      - For matrix outputs: `np.allclose` + max-abs-err.
      - For label outputs: ARI or accuracy.
      - For tables: per-column metric.

   g. **Sub-verdict**: `✅ exact` / `✅ ARI=...` / `❌ diverges (see MATH.md)`.

3. **Aggregate verdict table** at the end — one row per function × output:

      | Function | Output | Class | Metric | Value | Pass |
      |---|---|---|---|---|---|
      | `preprocess` | filtered data | deterministic | max abs err | 0.0 | ✅ |
      | `exprmclust` | pcareduceres | embedding | Procrustes | 1.0000 | ✅ |
      | `exprmclust` | clusterid | clustering | ARI | 1.0000 | ✅ |
      | … | … | … | … | … | … |

**Important conventions**:

- The R one-liner is rendered as a **markdown code block**, not actually executed inside the notebook (since it can't be without rpy2 / shell out). Execution happens in `r_per_function_dump.R` which runs once at the top via `subprocess.run([...])`.
- Side-by-side framing: ideal layout is markdown(R) + code(Python) + code(comparison), so a reader scrolling through sees R-call → Py-call → match.
- Every parameter documented — even if Python's default matches R's, list the row.
- If Python adds a parameter that R doesn't have (e.g., `seed=12345`), append a row marked "**new in Python**" with rationale.

**Pre-execution requirement**: same as Notebooks 1 and 2. Re-run before each release.

## Optional extra notebooks

For larger ports (class C or multi-feature like Monocle 2):

- `tutorial_<larger_dataset>.ipynb` — same content as Notebook 2 but on a more realistic dataset, demonstrating scale (e.g., paul15 → pancreas → neuroectoderm).
- `acceleration_walkthrough.ipynb` — for class C ports, a notebook showing each Acceleration Agent rewrite with timing + parity diff at every step (i.e., a richer version of `ITERATION_LOG.md` with plots).

These are nice-to-haves; the three above are **mandatory**.

## File-naming convention

```
examples/
├── compare_R_vs_Python.ipynb              ← Notebook 1 — pipeline parity
├── tutorial_<dataset>.ipynb               ← Notebook 2 — Python function tutorial
├── function_by_function_R_parity.ipynb    ← Notebook 3 — R⇄Python per-function dictionary
├── r_per_function_dump.R                  ← R driver that dumps per-function outputs for Notebook 3
├── *.executed.ipynb                       ← pre-executed copies for GitHub preview (optional)
├── data/                                  ← small fixture copies
└── r_driver_<dataset>.R                   ← (R driver for Notebook 1 if not already in tests/)
```

The `.executed.ipynb` variant is committed with all outputs intact so users browsing GitHub see results without running. The bare `.ipynb` (with outputs cleared) can also be committed for clean `nbdiff` reviews.

## Helper skeletons

See:
- [templates/compare_R_vs_Python.template.ipynb](templates/compare_R_vs_Python.template.ipynb) — Notebook 1
- [templates/tutorial.template.ipynb](templates/tutorial.template.ipynb) — Notebook 2
- [templates/function_by_function_R_parity.template.ipynb](templates/function_by_function_R_parity.template.ipynb) — Notebook 3
- [templates/r_per_function_dump.template.R](templates/r_per_function_dump.template.R) — R driver for Notebook 3

## What CHECKLIST.md must enforce

Phase 4 has these as **non-skippable** ticks:

- [ ] `examples/compare_R_vs_Python.ipynb` exists AND has been executed end-to-end in a fresh kernel AND every parity sub-gate clears AND outputs are committed.
- [ ] `examples/tutorial_<dataset>.ipynb` exists AND covers every public function from RECONSTRUCTION_REPORT §2.2 AND has been executed AND outputs are committed.
- [ ] `examples/function_by_function_R_parity.ipynb` exists AND has one subsection per public R function AND every R parameter is in a documented table AND R and Python outputs are numerically compared per function AND has been executed AND outputs are committed.

If any of the three is missing, the port is **not released**. No "deferred" exception.

## Anti-patterns

The py-TSCAN-v0.1 port marked Notebooks 1 and 2 as `⏳ deferred` in §5 of its first reconstruction report. This was the protocol failing — `deferred` should not have been a valid state for these items in Phase 4. v0.2 added them retroactively.

Then v0.2 still didn't have Notebook 3 — the protocol was missing the R⇄Python function-level dictionary entirely. v0.3 adds it. Lesson: every audience identified in [§Why three are required] must have a deliverable, or the protocol leaks.
