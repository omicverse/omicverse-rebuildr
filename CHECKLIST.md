# Per-Port Checklist

> Copy this file into the new `py-<pkg>/` repo as `CHECKLIST.md` (or just `PORT_CHECKLIST.md`); tick boxes as you go. The Acceleration Agent's items are optional — skip if class A (translation-only) is acceptable.

## Phase 0 — Decide the gate (1 hour)

- [ ] Identify the **canonical R entry point** — the user-facing function returned by the upstream README quickstart.
- [ ] Identify the **output type** of that entry point (vector? matrix? cluster labels? p-values? AnnData fields?).
- [ ] Look up the **algorithm class** in [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md). Record one of: deterministic / stochastic / clustering / embedding / ranked / ordinal / classification / inference.
- [ ] If the entry point returns **multiple outputs** of different classes, write a `manifest.yaml::outputs:` block with one gate per output.
- [ ] Decide the **parity threshold** from PARITY_TAXONOMY.md defaults (Pearson ≥ 0.99 for ordinal, ARI ≥ 0.95 for clustering, etc.).
- [ ] Decide the **canonical fixture** — a small, public, deterministic dataset (PBMC3k, paul15, HSMM, …).
- [ ] Decide the **seed** (default 42).
- [ ] Commit `data/manifest.yaml` with `algorithm_class`, `parity_threshold`, `fixture_path`, `reference_command`, `seed`. **This is read-only after this step.**

## Phase 0.5 — Discovery (avoid duplicate work)

> See [DISCOVERY.md](DISCOVERY.md) for the protocol.

- [ ] Run `python -m engine.discover_omicverse_deps --check <PkgName>`.
  - If a sister port already exists: **STOP** the port. Open an issue / PR on the existing repo.
  - If none: proceed.
- [ ] Clone the upstream R source into `<pkg>-ref/` (needed for the DESCRIPTION parse — done early so we can scan deps).
- [ ] Run `python -m engine.discover_omicverse_deps --description <pkg>-ref/DESCRIPTION --output DISCOVERY.md`.
- [ ] For each R dep with an omicverse match: decide `hard dep` / `optional dep` / `out of scope`. Record in DISCOVERY.md.
- [ ] For each R dep WITHOUT an omicverse match: decide which native-Python library replaces it (scipy / sklearn / networkx / pygam / etc.). Record in DISCOVERY.md.
- [ ] If you discover a missing-but-valuable upstream R package during this audit, add it to `examples/ROADMAP_TRAJ.md` (or relevant roadmap) as a future port.
- [ ] Commit `DISCOVERY.md` BEFORE writing any algorithmic code.

## Phase 1 — Set up the scaffold (1–2 hours)

- [ ] `mkdir py-<PkgName>` under your chosen working tree.
- [ ] Copy layout from one of the seed templates listed in [TEMPLATE.md](TEMPLATE.md) (don't copy algorithmic code).
- [ ] (`<pkg>-ref/` already cloned in Phase 0.5.) Add it to `.gitignore`.
- [ ] Skim the R `R/*.R` files; sketch a dependency DAG of internal R functions on paper / in a comment block at the top of `core.py`.
- [ ] Set up the two conda envs (`$PYTHON_TEST_ENV` for Python; `$R_TEST_ENV` for R). Verify `Rscript --version` and `python --version`.
- [ ] Install the upstream R package in the R reference env (e.g., `R -e "BiocManager::install('<UpstreamR>')"`).
- [ ] Write `tests/r_reference_driver.R`. Run it on the fixture; commit the resulting `reference_output.json` as a gitignored cache.
- [ ] Write `tests/test_smoke.py` (just "import + instantiate + don't crash"). Make sure it runs.

## Phase 2 — Equivalence Agent loop (the bulk of the work)

Iterate in **dependency order** — leaf R functions first, then the orchestrator.

For each R function in the topological order:

- [ ] Open the R source side-by-side with the in-progress Python file.
- [ ] Translate the function. Match name (snake_case), argument order, default values.
- [ ] Add a small unit test that runs the R function and the Python function on a probe input and parity-diffs them under the algorithm class metric.
- [ ] Run the test. If it fails, walk the suspicion list in [PARITY_TAXONOMY.md §When the gate fails](PARITY_TAXONOMY.md#when-the-gate-fails-in-step-3) in order. Do not loosen the gate.
- [ ] Lock the test (commit it as `tests/test_<function>_parity.py`).

When all leaf functions parity-clear:

- [ ] Translate the top-level orchestrator (the canonical entry point).
- [ ] Run `tests/test_exact_match.py` against the fixture.
- [ ] **Gate clears at the pre-registered threshold?** If yes, you have a class-A port. If no, fix and iterate. Do not loosen the threshold.

At the end of Phase 2: `pytest -q` is green; `pip install -e .` works; `examples/benchmark_vs_R.ipynb` runs to the bottom.

## Phase 3 — Acceleration Agent loop (optional, but encouraged for ordinal / embedding ports)

Before starting:

- [ ] Create `ITERATION_LOG.md` in the port directory, copied from [templates/ITERATION_LOG.template.md](templates/ITERATION_LOG.template.md).
- [ ] Run the benchmark on the Equivalence-Agent baseline (one warmup, 3 measured runs); record the YAML block as `iter: 0` (baseline).

For each rewrite in the search heuristic order ([ACCELERATION_PLAYBOOK §Search heuristic](ACCELERATION_PLAYBOOK.md#search-heuristic)):

- [ ] Check the rewrite's **precondition** in the playbook — does it apply to this port?
- [ ] If applicable, produce the **admissibility proof** (E / B / C). For (B), derive the perturbation bound in closed form and record it in `MATH.md`.
- [ ] Apply the rewrite on a working branch (`acceleration-<rewrite_name>`).
- [ ] Re-run `tests/test_exact_match.py`. Gate still clears?
- [ ] If yes, run `engine/benchmark.py` (or its CLI equivalent): warmup-excluded 3-run mean. Record speedup.
- [ ] If parity dropped at all, write a one-line **`math_reason_for_dip`** in the iteration log explaining *why* (it will be annotated on Plot 2).
- [ ] If speedup > 1.05× and gate clears, merge. Otherwise roll back.
- [ ] Add a comment in the modified code citing the playbook entry (e.g., `# acceleration: §3.1 MST ⊆ Delaunay (C)`).
- [ ] Append one YAML block to `ITERATION_LOG.md` (accepted OR rejected — log everything for the plot's denominator).

Stop when:
- [ ] No admissible rewrite from the playbook remains, OR
- [ ] Last 3 attempts produced no measurable speedup, OR
- [ ] You're satisfied with the wall-clock.

After stopping:

- [ ] Run `python -m engine.plot_evolution --port-dir <port>` to render `examples/evolution.png` (the two-panel figure).
- [ ] Spot-check the plot: time should be monotone-non-increasing on accepted iters; accuracy should be flat at ≈1.0 with annotated dips only where (B) ε-approximations fired.

## Phase 4 — Release

- [ ] `pip install -e .` in a **fresh** conda env succeeds.
- [ ] `pytest -q` is green in that fresh env.
- [ ] `README.md` has: Install / Quickstart / Function-map table / Reproducing-R section / Citation / License.
- [ ] `MATH.md` lists every (B) bounded-approximation rewrite with its perturbation bound.
- [ ] Version pinned in `pyproject.toml` to `0.1.0`.
- [ ] License chosen per [TEMPLATE.md §License decision matrix](TEMPLATE.md#license-decision-matrix).

### Mandatory notebooks (see [NOTEBOOKS.md](NOTEBOOKS.md))

These items are **non-skippable**. "Deferred" is not a valid status in Phase 4.

- [ ] `examples/compare_R_vs_Python.ipynb` exists, follows the 6-section schema, runs end-to-end in a fresh kernel, every parity sub-gate clears, executed outputs committed.
- [ ] `examples/tutorial_<dataset>.ipynb` exists, has one subsection per public function from RECONSTRUCTION_REPORT §2.2, includes the class-API mirror + pitfalls + next-steps sections, executed outputs committed.
- [ ] `examples/function_by_function_R_parity.ipynb` exists, has one subsection per public R function with a parameter table (R name → Py name → type → default → range → description for EVERY parameter), R-call markdown + Py-call code + numerical comparison + sub-verdict, plus an aggregate verdict table; executed outputs committed.
- [ ] `examples/evolution.ipynb` exists, has **one `## Iteration N — <title>` header per iteration** (N ≥ 2; class A still needs Baseline + at least one follow-up). Every iteration block contains a markdown narrative (≥ 3 sentences) describing what changed and why, AND a code cell that produces a subplot for that iteration. Final cell renders the aggregate 2-panel `examples/evolution.png`. Executed outputs committed.
- [ ] `examples/r_per_function_dump.R` exists, dumps per-function R outputs to JSON for Notebook 3 to consume.
- [ ] Re-execute all four notebooks immediately before release: `jupyter nbconvert --to notebook --execute examples/*.ipynb --output {}`.

### Reconstruction report (the structured "done" artefact)

- [ ] Copy [templates/RECONSTRUCTION_REPORT.template.md](templates/RECONSTRUCTION_REPORT.template.md) into the port as `RECONSTRUCTION_REPORT.md`.
- [ ] Run `python -m engine.r_function_audit --r-source <pkg>-ref --py-package <pkgname> --output AUDIT.md`; paste §2 R-function coverage table into the report.
- [ ] Fill §1 Identity (versions, audit class A/B/C, final parity).
- [ ] Fill §3 Parity evidence — list every output's metric and threshold; one row per fixture.
- [ ] Embed `examples/evolution.png` in §4.1 AND link to `examples/evolution.ipynb` for the per-iteration narrative.
- [ ] Fill §4.2 Accepted rewrites table from `ITERATION_LOG.md`; §4.3 Rejected rewrites with reasons.
- [ ] Confirm §5 Code-quality checks are all ✅.
- [ ] List §6 Known limitations honestly.
- [ ] Sign §8 with date + active-time spent.

### Release artefacts

- [ ] Add the new port to [examples/ROADMAP_TRAJ.md](examples/ROADMAP_TRAJ.md) (or relevant roadmap) as ✅ done.
- [ ] Add the new port to [TEMPLATE.md §Recommended seed templates](TEMPLATE.md#recommended-seed-templates-per-algorithm-class) if it sets a new template for its class.
- [ ] Push to `github.com/omicverse/py-<PkgName>`. Trigger the PyPI release workflow.

## Phase 5 — Integrate into omicverse main package

- [ ] Vendor the port into `omicverse/external/<pkgname>/` (or `omicverse/single/_<pkgname>.py` for a small port).
- [ ] Expose at the top-level `omicverse.<subpackage>.<PkgName>` matching the existing pattern (cf. `ov.single.Monocle`).
- [ ] Add to the `omicverse-guide` tutorials.

## Audit retrospective (write up after release)

- [ ] Classify the port as A (translation-only) / B (minor optimisation) / C (major algorithmic change with proof).
- [ ] If B or C, note which playbook entries fired and at what speedup.
- [ ] Note any new rewrite that should be added to the playbook for future ports.
