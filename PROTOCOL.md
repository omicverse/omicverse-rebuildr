# Omicverse-RebuildR Protocol — 6 Steps

> Port an R package to a pure-Python `py-<pkg>` mirror, validated by an executable parity gate.

## The loop in one sentence

Treat porting as: **agent reads R source → drafts Python → runs both on the same fixture → diffs outputs under a class-aware parity criterion → patches → repeat until gate clears → then search over equivalence-preserving rewrites for speed.**

Formally: given a reference `f_R` in source language S and target `f_T` in target language T, the goal is

```
f_T(x) ≈_C f_R(x)    for all x ∈ B
```

where `B` is the canonical fixture set and `≈_C` is the parity relation for algorithm class `C` (see [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md)).

This is **fixture-level equivalence**, not a proof of semantic equivalence over the full input domain.

---

## Step 0 — Discovery (avoid duplicate work)

> Inserted v2 (after the TSCAN port retroactively showed how essential this is).
> See [DISCOVERY.md](DISCOVERY.md) for the full protocol.

Before any scaffold work, run two checks against `github.com/omicverse`:

```bash
# 1. Is the target itself already ported? — if YES, STOP.
python -m engine.discover_omicverse_deps --check <PkgName>

# 2. Which upstream R deps already have py- mirrors? — reuse them as deps.
python -m engine.discover_omicverse_deps \
    --description <pkg>-ref/DESCRIPTION \
    --output DISCOVERY.md
```

Commit `DISCOVERY.md` to the port repo **before any algorithmic code**. The file records:

- Whether a sister port exists (if so, the protocol ends here — open an issue or PR on the existing repo instead).
- For each R dep: the matching `omicverse/py-<dep>` repo (if any), and the decision on how to use it (`hard dep`, `optional dep`, or `native Python equivalent`).

Concrete example from `py-TSCAN`: the dep audit flagged R's `mclust` → `omicverse/py-mclustR`. Adding `pymclustR>=0.1` to `pyproject.toml` saved ~3000 LOC and ~2 weeks of EM/HC engineering work that would otherwise have to be redone. This is how the **ecosystem** compounds.

If you publish a new port whose repo name doesn't follow the `py-<X>` rule (e.g., `Seurat → py-CCA`), append a row to `engine/discover_omicverse_deps.py::ALIAS_MAP` so subsequent ports find it automatically.

---

## Step 1 — Pick a shape template

Copy **layout only** from one prior successful port. Do NOT copy algorithmic code or parity thresholds.

Seed templates (in order of preference, by similarity to your target):

| Target algorithm class | Seed template | Why |
|---|---|---|
| Ordinal (pseudotime, trajectory) | [`py-monocle2`](https://github.com/omicverse/py-monocle2) | Same algorithm class, has Acceleration Agent examples |
| Classification (doublet / cell type) | [`py-DoubletFinder`](https://github.com/omicverse/py-DoubletFinder) | Clean translation-only port; smallest LOC |
| Clustering | [`py-mclustR`](https://github.com/omicverse/py-mclustR) | EM + model selection, ARI gate |
| Statistical inference | [`py-miloR`](https://github.com/omicverse/py-miloR) | -log10 p-value rank-corr gate |
| Continuous embedding | [`py-CCA`](https://github.com/omicverse/py-cca) | Procrustes gate |
| Deterministic numerical | [`rust-bandnorm`](https://github.com/omicverse/rust-bandnorm) | f64 element-wise tolerance |

What to copy from the template:
- repository layout (`pkg_name/`, `tests/`, `examples/`, `<pkg>-ref/`, `data/`, `dist/`)
- `pyproject.toml` skeleton (rename + adjust deps)
- `tests/` rig (`conftest.py`, `test_smoke.py`, `test_exact_match.py` if applicable)
- `README.md` structure (one section per: Install / Quick-start / R-parity test / Citation)
- `.gitignore`, `LICENSE` (match upstream R license unless incompatible)

What NOT to copy:
- the algorithmic Python code
- the package-specific parity threshold in `manifest.yaml`

See [TEMPLATE.md](TEMPLATE.md) for the canonical layout.

---

## Step 2 — Set up two side-by-side environments

The agent needs shell access to **both** environments and shared fixture files.

| Env | Conda env path | Used for |
|---|---|---|
| Target | `$PYTHON_TEST_ENV` | Python + in-progress port + pytest |
| Reference | `$R_TEST_ENV` | R 4.x + Bioconductor + the upstream R package |

Activate via:
```bash
conda activate $PYTHON_TEST_ENV   # Python target
conda activate $R_TEST_ENV      # R reference
```

The fixture lives under `data/` and is referenced by **both** the R `ref_runner.R` and the Python `parity_test.py`.

**Output policy**: this kit does not assume any specific filesystem layout. Choose a working tree under your own scratch / project area, set `$WORK_DIR` to it if you like, and never overwrite files outside your own working tree.

---

## Step 3 — The two-agent inner loop

Instantiate **two complementary agent roles** within the same coding-agent session. They run sequentially: Equivalence first, then Acceleration after the parity gate clears.

### 3a. Equivalence Agent

**Objective**: `f_T(x) ≈_C f_R(x)` on the canonical fixture.

**Loop**:
```
read  →  draft  →  run  →  parity-diff  →  patch  →  repeat
```

Concretely each iteration:
1. **read**: open the R reference for the next function in dependency order.
2. **draft**: translate to Python — match function name, argument order, default values, return shape, and naming conventions (NumPy / pandas / AnnData).
3. **run**: invoke `Rscript ref_runner.R fixture.<ext> -> reference_output.json` and `pytest tests/test_parity.py` which produces `candidate_output.json`.
4. **parity-diff**: load both JSONs, apply the class-`C` metric from [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md), compare to the threshold in `manifest.yaml`.
5. **patch**: if gate failed, diagnose (off-by-one, wrong default, transpose, log-base, base-1 vs base-0 indices, …) and re-draft. If gate passed: lock the test and move to next function.

**Exit condition**: the **pre-registered** gate in `manifest.yaml` clears on all required fixtures. Do not tighten or loosen the threshold to fit the candidate output.

### 3b. Acceleration Agent

Only runs **after** the Equivalence Agent's candidate clears the parity gate.

**Objective**: search over equivalence-preserving algebraic rewrites to minimise wall-clock on the canonical fixture, **conditional on the gate still clearing**. We do **not** try to improve the parity metric — the R reference is the ceiling, not the floor.

**Loop** (verifier-guided test-time search):
```
1. Propose action a_t       (rewrite drawn from ACCELERATION_PLAYBOOK.md)
2. Check admissibility φ(a_t) ∈ {0, 1}
     - exact algebraic identity, or
     - bounded ε-approximation with explicit perturbation bound, or
     - class-containment theorem
3. Apply the rewrite to a working branch
4. Re-run parity test           (gate still clearing?)
5. Run benchmark on fixture     (warmup discarded; 3-run mean ± stddev)
                                (see engine/benchmark.py and EVALUATION.md)
6. Reward  r_t = φ(a_t) · speedup(a_t)
7. If r_t > best-so-far → commit. Else → roll back.
8. Append one YAML block to ITERATION_LOG.md describing the attempt
   (action, admissibility, timing, accuracy, accept/reject, math reason for any dip).
9. Repeat until no admissible rewrite remains.
```

**Iteration log**: every step — accepted, rejected for gate failure, rejected for no speedup, or rejected for inadmissibility — gets one block in `ITERATION_LOG.md` per the schema in [templates/ITERATION_LOG.template.md](templates/ITERATION_LOG.template.md). The blocks render into the two evaluation plots ([EVALUATION.md](EVALUATION.md)).

Every rewrite committed to the final port must ship with an inline comment or docstring citing the admissibility evidence (e.g., `# Woodbury identity (exact); see ACCELERATION_PLAYBOOK §2`).

If the rewrite is a **bounded ε-approximation**, the perturbation bound must be derived and recorded in the port's `MATH.md` (or in the docstring) — not handwaved.

**Stop conditions**:
- no admissible rewrite from the playbook remains, OR
- last 3 attempts produced no measurable speedup, OR
- the port is class A (translation-only) — Acceleration is optional, not mandatory.

See [ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md) for the rewrite catalog and proof obligations.

---

## Step 4 — Validate against the pre-registered parity gate

The parity threshold in `manifest.yaml` is committed **before** any agent work in Step 3 begins. It is **read-only** during Steps 3 and 4.

The port is accepted iff:
- all required fixtures pass the class-`C` gate at the pre-registered threshold;
- `pip install .` succeeds in a fresh conda env;
- `pytest -q` is green;
- a smoke notebook in `examples/` runs end-to-end on the public fixture.

If the gate fails after the Acceleration Agent's rewrites, **roll back to the last commit that cleared it**. Never widen the gate.

---

## Step 5 — Release and become the next template

Each finished port:
- ships a fully-filled-in `RECONSTRUCTION_REPORT.md` (see [templates/RECONSTRUCTION_REPORT.template.md](templates/RECONSTRUCTION_REPORT.template.md)) including:
  - The R-function coverage audit (run `python -m engine.r_function_audit --r-source <pkg>-ref --py-package <pkgname>`);
  - Per-fixture parity values;
  - The two-plot evolution figure (`python -m engine.plot_evolution --port-dir .`);
  - Accepted-vs-rejected Acceleration rewrites with admissibility evidence;
- ships **all four** mandatory notebooks under `examples/` (see [NOTEBOOKS.md](NOTEBOOKS.md)):
  - **`compare_R_vs_Python.ipynb`** — pipeline-level parity vs R on the canonical fixture, with one visualisation per `manifest.yaml::outputs[]` block. Pre-executed, outputs committed.
  - **`tutorial_<dataset>.ipynb`** — Python-only walkthrough, one subsection per public function from §2.2 of the reconstruction report, plus class-API mirror and pitfalls. Pre-executed, outputs committed.
  - **`function_by_function_R_parity.ipynb`** — function-level R⇄Python dictionary on the same input, with a parameter table per function (every R param documented in R name / Py name / type / default / range / description), R-call markdown + Py-call code + numerical comparison + sub-verdict. Pre-executed, outputs committed.
  - **`evolution.ipynb`** — per-iteration narrative: one `## Iteration N — <title>` header per iteration, each with a markdown body describing what changed and a code cell producing a subplot for that iteration. Final cell renders the aggregate 2-panel `evolution.png` inline. Pre-executed, outputs committed. Minimum 2 iteration blocks (Baseline + at least one follow-up); the header count is a quality signal — a port claiming heavy work but showing only 2 headers should fail review.
  - None of the four is "deferrable" — if any is missing, the port is not released. TSCAN-v0.1 shipped without Notebooks 1+2; v0.2 added them; v0.3 added Notebook 3; the 9-port batch audit (2026-05-24) surfaced that 8/9 ports had no iteration record, so v7 of the protocol adds Notebook 4. The protocol now blocks all four from being skipped.
- gets a `omicverse/py-<pkg>` repository created;
- has its `pyproject.toml` version pinned to `0.1.0`;
- is published to PyPI under MIT or the upstream R package's license (whichever is more restrictive — match upstream when possible);
- becomes a candidate seed template for the next port (add it to the table in [TEMPLATE.md](TEMPLATE.md)).

Update [examples/ROADMAP_TRAJ.md](examples/ROADMAP_TRAJ.md) (or the relevant roadmap) to tick the package off.

---

## The 8 algorithm classes (cheatsheet — see PARITY_TAXONOMY.md)

| Class | Parity criterion |
|---|---|
| Deterministic numerical | element-wise tolerance |
| Stochastic numerical | KS / Wasserstein-1 |
| Combinatorial clustering | ARI / NMI / Fowlkes–Mallows |
| Continuous embedding | Procrustes similarity |
| Ranked output | top-K Jaccard / Spearman |
| Ordinal output (pseudotime) | Pearson / Spearman |
| Classification | label agreement / F1 |
| Statistical inference | rank corr on −log10 p + top-k overlap |

## The 3 admissibility proof types (cheatsheet — see ACCELERATION_PLAYBOOK.md)

1. **Exact algebraic identity** (e.g., Woodbury, Schur, memoisation): rewrite is provably bit-equivalent on the nonzero eigenspace (with ridge stabilisation otherwise).
2. **Bounded ε-approximation** with explicit perturbation bound (e.g., sparse soft-assignment): an inequality of the form `‖output_new − output_old‖ ≤ κ · ε` with κ derived in closed form.
3. **Class-containment theorem** (e.g., MST(P) ⊆ Delaunay(P)): a known theorem guarantees the rewrite produces the same output on the relevant input class.
