# Omicverse-RebuildR

**A fixed, reproducible protocol for porting R / Bioconductor packages to pure-Python `py-<pkg>` standalones, with cryptographic-grade numerical parity against the R reference.**

🇨🇳 **中文版**: [README.zh.md](README.zh.md)

---

## What this is

Single-cell genomics, statistical genetics, proteomics and adjacent fields have hundreds of canonical algorithms that exist **only in R / Bioconductor**: TSCAN, tradeSeq, Slingshot, DESeq2, edgeR, mclust, miloR, DoubletFinder, WGCNA, gsMap, condiments, …

When a Python user needs one of these, their options today are bad:

1. **Shell out via rpy2 / reticulate** — adds R install + serialisation overhead + GPU-runtime fragmentation; agent workflows hate it.
2. **Use a "close-enough" Python alternative** — silently a different algorithm with different statistical behaviour.
3. **Manually re-port** — weeks to months of specialist effort; usually the result diverges from R and the divergence isn't measured.

Omicverse-RebuildR is the **engineering recipe** that takes a port from "I want this in Python" to "the wheel is on PyPI and provably matches R on the canonical fixture" — in a small number of agent-driven iterations, with the proof of parity shipped alongside the wheel.

Three core ideas:

1. **The R source is the executable spec.** No reverse-engineering from papers. The agent runs the R reference on a fixed input and compares its own draft to that output, every iteration.
2. **Parity is class-aware.** "Same output" means different things for an embedding (rotation-invariant), a clustering (label-permutation-invariant), or a pseudotime (correlation-invariant). The protocol pre-registers which numerical metric applies to which output and locks the threshold before any agent code is written.
3. **Reconstruction is not metric optimization.** We never tune the algorithm to "look better" — we tune it to be **identical** to R, then search for speed under provably-equivalent algebraic rewrites.

What ships at the end of every port:

- A pip-installable wheel on PyPI.
- A `RECONSTRUCTION_REPORT.md` with full R-function coverage audit, per-output parity values, two-panel time-vs-accuracy plot, and ecosystem-reuse accounting.
- Three pre-executed notebooks: pipeline parity, Python tutorial, R⇄Python function dictionary.
- A reproducible parity gate as a pytest test.

---

## Quick start

```bash
# 1. Clone the kit
git clone <your-repo-url> omicverse-rebuildr
cd omicverse-rebuildr

# 2. Provision Python + R conda envs (see SETUP.md for full instructions)
conda create -n rebuild-py python=3.10 -y
conda activate rebuild-py
pip install -r requirements.txt

conda create -n rebuild-r -c conda-forge r-base=4.3 r-essentials -y

# 3. Export the two paths the kit needs
export PYTHON_TEST_ENV=$(conda info --envs | awk '/rebuild-py/ {print $NF}')
export R_TEST_ENV=$(conda info --envs | awk '/rebuild-r/ {print $NF}')

# 4. Authenticate GitHub CLI (needed for Discovery step)
gh auth login

# 5. Verify the kit installs cleanly (30 seconds)
python -m engine.smoke_test
# Expected: [smoke] OK -- 5/5 checks passed.

# 6. Check if your target R package is already ported
python -m engine.discover_omicverse_deps --check <YourRPackage>
```

If the smoke test passes and the discovery says "no existing port", you're ready to start a port — follow [PROTOCOL.md](PROTOCOL.md).

📖 **Full setup walkthrough**: [SETUP.md](SETUP.md) (~30 minutes including conda env provisioning).

---

## How to invoke the protocol in a session

Point an agent (Claude Code, Cursor, etc.) at this folder and say:

```
Port R package X. Follow omicverse-rebuildr/README.md.
```

The agent will execute the 6-step protocol end-to-end and produce, at the end:

- a `omicverse/py-X` repository (or under your `$REBUILDR_ORG`) with installable wheel,
- the pre-registered numerical parity gate clearing on the canonical fixture,
- a structured `RECONSTRUCTION_REPORT.md`,
- three mandatory pre-executed notebooks (pipeline parity, Python tutorial, R⇄Python function dictionary),
- a PyPI release.

---

## The protocol — 6 steps

```
┌─ 0.5 Discovery ─────┐
│ • Is target already │ ← if YES: stop, reuse existing repo
│   ported?           │
│ • Which R deps      │ ← matches added to pyproject.toml as
│   already have      │   hard / optional deps
│   py-mirrors?       │
└─────────────────────┘
         ↓
┌─ 1 Shape template ──┐
│ Copy layout from a  │
│ prior port matching │
│ the algorithm class │
└─────────────────────┘
         ↓
┌─ 2 Dual envs ───────┐
│ Python target env   │
│ R reference env     │
│ Both see same data  │
└─────────────────────┘
         ↓
┌─ 3 Two-agent inner loop ─────────────────────────────────────────────┐
│                                                                       │
│  ┌─ Equivalence Agent ────┐    ┌─ Acceleration Agent ──────────────┐ │
│  │ Translate R → Python   │ →  │ Search algebraic rewrites for     │ │
│  │ Iterate until parity   │    │ speed; each requires admissibility│ │
│  │ gate clears (Pearson,  │    │ proof: exact / bounded-ε /        │ │
│  │ ARI, Procrustes, etc.) │    │ class-containment. Reject if it   │ │
│  │                        │    │ breaks parity.                    │ │
│  └────────────────────────┘    └───────────────────────────────────┘ │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
         ↓
┌─ 4 Validate ────────┐
│ Re-confirm gate.    │
│ Threshold is read-  │
│ only; never widened │
└─────────────────────┘
         ↓
┌─ 5 Release ─────────┐
│ Publish to PyPI +   │
│ GitHub. Become a    │
│ seed template for   │
│ the next port.      │
└─────────────────────┘
```

Each step is documented in detail:

| Step | What happens | Document |
|---|---|---|
| **0.5 Discovery** | Check whether the target itself is already ported; check whether each R dep already has a py-mirror under `github.com/<org>`. STOP if duplicate; reuse deps as `pyproject.toml` deps if found. | [DISCOVERY.md](DISCOVERY.md) |
| **1 Shape template** | Copy directory layout + test scaffold from a prior port (e.g., `py-DoubletFinder` for classification, `py-monocle2` for ordinal). Do NOT copy algorithmic code. | [TEMPLATE.md](TEMPLATE.md) |
| **2 Dual environments** | Provision a Python target env (Python + in-progress port) and an R reference env (R 4.x + Bioconductor + upstream reference). Both see the same fixture files. | [SETUP.md](SETUP.md) |
| **3 Two-agent inner loop** | (a) **Equivalence Agent**: translate R → Python, iterate until the pre-registered class-aware parity gate clears. (b) **Acceleration Agent**: verifier-guided test-time search over algebraic rewrites for speed, each requiring one of three admissibility proofs. | [PROTOCOL.md](PROTOCOL.md), [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md), [ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md) |
| **4 Validate** | Re-confirm the gate. The threshold is committed before agent work begins — never tightened or loosened. | [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md) |
| **5 Release** | Ship the wheel to PyPI, publish the repo under `github.com/<org>/py-X`, complete the structured `RECONSTRUCTION_REPORT.md` + three mandatory notebooks. | [NOTEBOOKS.md](NOTEBOOKS.md) |

---

## The 8 algorithm classes (parity taxonomy)

Different algorithms have different invariance structures, so "same output" needs different metrics. The protocol pre-registers one class per port output:

| # | Class | Parity criterion | Default threshold | Example R packages |
|---|---|---|---|---|
| 1 | **Deterministic numerical** (3 sub-tiers — see [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md#deterministic-sub-tiers-class-1)) | element-wise `max_abs_err < tol`, optional `rtol`-scaled | **standard `1e-8`** / strict `1e-13` / bounded `1e-6`; **hard ceiling `1e-6`** | BandNorm, scHiCluster kernels |
| 2 | **Stochastic numerical** | Kolmogorov–Smirnov ≤ τ or Wasserstein-1 ≤ τ | KS-p ≥ 0.05 | MCMC draws, Bayesian posteriors |
| 3 | **Combinatorial clustering** | label-invariant: ARI / NMI / Fowlkes–Mallows | ARI ≥ 0.95 | mclust, scDblFinder, sc3 |
| 4 | **Continuous embedding** | rotation-invariant: Procrustes similarity | Procrustes ≥ 0.95 | Seurat CCA, PCA, UMAP, t-SNE |
| 5 | **Ranked output** | top-K Jaccard / Spearman correlation | top-50 Jaccard ≥ 0.8 | COSG markers, DE rankings |
| 6 | **Ordinal output (pseudotime)** | Pearson / Spearman correlation | Pearson ≥ 0.99 (≥ `1 − 1e-12` treated as exact) | Monocle 2, Slingshot, TSCAN |
| 7 | **Classification** | label agreement / F1 | F1 ≥ 0.95 | DoubletFinder, scDblFinder labels |
| 8 | **Statistical inference** | rank corr on −log10 p + top-K Jaccard | Spearman ≥ 0.90 | miloR DA, limma, DESeq2, tradeSeq |

If the R function returns multiple outputs of different classes, the manifest declares one gate per output and ALL must pass.

The 8 metric implementations live in [`engine/parity_metrics.py`](engine/parity_metrics.py) — import from there rather than redefining.

📖 Full taxonomy: [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md) — includes "when the gate fails: ordered suspicion list" (off-by-one, transpose, log base, sparse-vs-dense, NA handling, …).

---

## Acceleration: 3 admissibility proof classes

Every algebraic rewrite the Acceleration Agent commits must carry one of these proofs:

| Proof class | Meaning | Examples |
|---|---|---|
| **(E) Exact identity** | The rewrite produces bit-equivalent output by mathematical identity. | `X^T X` cached outside a loop; Woodbury `(I + λ U Λ U^T)^{-1}`; Schur complement; Cholesky vs LU. |
| **(B) Bounded ε-approximation** | The rewrite introduces an error bounded by a closed-form expression in some small ε; the bound is derived in `MATH.md`, not handwaved. | Sparse soft-assignment via row truncation at ε = 1e-12 (with `‖W_new − W‖_F ≤ κ n K ε`); top-K kNN truncation of pairwise-distance matrix when downstream is local. |
| **(C) Class-containment theorem** | A known theorem guarantees the rewrite produces the same output for the relevant input class. | Euclidean MST ⊆ Delaunay triangulation (Preparata-Shamos 1985, Toussaint 1980); MST ⊆ relative-neighbourhood graph. |

📖 Full catalog: [ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md). The Acceleration Agent searches the playbook in a heuristic order; rejected rewrites are still logged for the per-port `ITERATION_LOG.md`.

---

## Evaluation: two plots, not one

Traditional evolutionary search plots `iteration vs metric` because the policy searches *for better metric*. **That's the wrong model here** — reconstruction's goal is **identical** output to the R reference, not "better" output.

So every port produces two plots against the same iteration axis:

```
 wall-clock (s)
  │
  │  ●─┐
  │    │  ●─┐
  │       │    ●──●
  │ baseline → iter 1 → iter 2 → iter 3 → iter 4
  │
  └────────────────────────────────────────────────→ iteration

 parity metric (e.g. Pearson)
  │ ●──●──●──●─┐
  │              \
  │               ●──●   ← annotated: "row truncation at ε=1e-12"
  │  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ threshold (red dashed line)
  │
  └────────────────────────────────────────────────→ iteration
```

- **Plot 1 (top, log scale)**: wall-clock should monotonically decrease as rewrites land. Error bars = stddev over 3 warmup-excluded runs.
- **Plot 2 (bottom)**: parity metric should stay flat at the ceiling. Every dip must be annotated with the math approximation that caused it.

Wall-clock measurement rules:
- **Warmup**: discard the first run (BLAS thread spin-up, Python imports, page cache).
- **3 measured runs** in the same process; report mean ± stddev.
- **CV > 10% → auto-extend to 5 runs**, report median + IQR.
- **Fix BLAS threads** via `OMP_NUM_THREADS=8` etc. before any imports.

📖 Full spec + iteration-log schema: [EVALUATION.md](EVALUATION.md).

---

## Three mandatory notebooks per release

A finished port serves **four audiences**, each with a different need:

| Audience | What they need | Where they look |
|---|---|---|
| **Reviewer / scientist** evaluating whether to trust the port | Pipeline-level proof Python ≡ R numerically | [`compare_R_vs_Python.ipynb`](templates/compare_R_vs_Python.template.ipynb) |
| **End user** new to the algorithm | A copy-pastable Python tour of every public function | [`tutorial_<dataset>.ipynb`](templates/tutorial.template.ipynb) |
| **R user porting their existing code line-by-line** | A function-level dictionary — every R parameter ↔ Python parameter, side-by-side calls on identical input | [`function_by_function_R_parity.ipynb`](templates/function_by_function_R_parity.template.ipynb) |
| **CI / automation** | The pre-registered parity gate as a pytest assertion | `tests/test_exact_match.py` |

All three notebooks ship **pre-executed** so GitHub renders them without re-running. Phase 4 of the protocol blocks the port from being released if any one is missing.

📖 Schemas + section-by-section requirements: [NOTEBOOKS.md](NOTEBOOKS.md).

---

## Kit contents

### Top-level documents

| File | What it does |
|---|---|
| [SETUP.md](SETUP.md) | **First-time install** — prerequisites, two-env provisioning, env vars, gh auth, smoke test, troubleshooting. |
| [PROTOCOL.md](PROTOCOL.md) | **The 6-step protocol** + the two-agent inner loop. Read this in a session before starting a port. |
| [DISCOVERY.md](DISCOVERY.md) | Phase 0.5 — reuse before rebuild. Find existing org-mirror ports for the target and its R deps. |
| [PARITY_TAXONOMY.md](PARITY_TAXONOMY.md) | 8-class algorithm taxonomy → which numerical-parity metric applies. |
| [ACCELERATION_PLAYBOOK.md](ACCELERATION_PLAYBOOK.md) | Catalog of algebraic rewrites with the 3 admissibility proof types. |
| [EVALUATION.md](EVALUATION.md) | Two-plot evaluation (`time vs iter` + `accuracy vs iter`), warmup excluded, accuracy dips annotated. |
| [NOTEBOOKS.md](NOTEBOOKS.md) | **Three mandatory** pre-executed notebooks per release. Non-skippable in Phase 4. |
| [TEMPLATE.md](TEMPLATE.md) | Standard `py-<pkg>` repo layout + naming conventions + license decision matrix. |
| [CHECKLIST.md](CHECKLIST.md) | Per-port checklist to tick through, Phase 0–5. |

### Engine (runnable code) — `engine/`

| File | What it does | Typical invocation |
|---|---|---|
| `smoke_test.py` | 30-second sanity check — verifies the kit installs and all 8 parity metrics + audit / plot / benchmark / loop helpers work. | `python -m engine.smoke_test` |
| `discover_omicverse_deps.py` | Lists existing org repos via `gh repo list <org>` (default `omicverse`, override with `REBUILDR_ORG`); parses R `DESCRIPTION`; reports which deps already have py-mirrors. Cached 24h. | `python -m engine.discover_omicverse_deps --check <RPkg>` |
| `parity_metrics.py` | The 8 parity-class metric functions (Pearson, ARI, Procrustes, KS, top-K Jaccard, …) + class dispatcher. | `from parity_metrics import compute_parity, is_pass` |
| `benchmark.py` | Wall-clock timer with warmup-exclusion + 3-run averaging; auto-extends to 5 runs + median when CV > 10%. | `from benchmark import time_callable` |
| `r_function_audit.py` | Parses R `NAMESPACE` + `R/*.R`, audits Python coverage, produces `AUDIT.md`. | `python -m engine.r_function_audit --r-source <pkg>-ref --py-package <pkg>` |
| `plot_evolution.py` | Renders the two-panel evolution PNG from `ITERATION_LOG.md`, annotates accuracy dips with their math reason. | `python -m engine.plot_evolution --port-dir <path>` |
| `loop.py` | The Omicverse-RebuildR loop as runnable code — equivalence + acceleration phases as Python callables. | `python -m engine.loop --port-dir <path> --phase equivalence` |
| `manifest.template.yaml` | Pre-registered parity gate spec — copy into each new port's `data/manifest.yaml`. | (file template) |

### File-level templates — `templates/`

Every new port copies these as starting scaffolding; nothing is generated from scratch.

| Template | Becomes |
|---|---|
| `pyproject.template.toml` | The port's `pyproject.toml` (build + deps + metadata) |
| `README.template.md` | The port's user-facing `README.md` |
| `r_reference_driver.template.R` | `tests/r_reference_driver.R` — invokes the R package, dumps JSON |
| `_run_candidate.template.py` | `tests/_run_candidate.py` — invokes the Python port, dumps JSON |
| `test_exact_match.template.py` | `tests/test_exact_match.py` — pytest test that asserts the gate |
| `DISCOVERY.template.md` | The port's `DISCOVERY.md` artefact (Phase 0.5) |
| `ITERATION_LOG.template.md` | The port's `ITERATION_LOG.md` (Phase 3 acceleration log) |
| `RECONSTRUCTION_REPORT.template.md` | The port's `RECONSTRUCTION_REPORT.md` (8-section final report) |
| `compare_R_vs_Python.template.ipynb` | Notebook 1 — pipeline parity |
| `tutorial.template.ipynb` | Notebook 2 — Python tutorial |
| `function_by_function_R_parity.template.ipynb` | Notebook 3 — R⇄Python function dictionary |
| `r_per_function_dump.template.R` | R driver feeding Notebook 3 |

### Examples & roadmaps — `examples/`

| File | What it does |
|---|---|
| [ROADMAP_TRAJ.md](examples/ROADMAP_TRAJ.md) | Ranked trajectory-inference R packages awaiting ports (TSCAN ✅, tradeSeq, destiny, URD, SCORPIUS, condiments, …) with citation counts + cites/year. |
| [EXAMPLE_WALKTHROUGH.md](examples/EXAMPLE_WALKTHROUGH.md) | TSCAN end-to-end walkthrough — Phase 0 → Phase 5 narrative with concrete commands and intermediate outputs. |

---

## What the agent does in a session

A typical agent session opens with:

```
Port R package X. Follow omicverse-rebuildr/README.md.
```

The agent then executes:

1. **(Phase 0.5 — Discovery)** Run `engine/discover_omicverse_deps.py` to check:
   - Is `omicverse/py-X` (or `<your-org>/py-X`) already published? → if yes, **STOP**, report the existing repo.
   - Which of X's R deps already have py-mirrors? → record matches in `DISCOVERY.md`, add to `pyproject.toml`.
2. **(Phase 0)** Look up X's algorithm class in `PARITY_TAXONOMY.md`. Write and commit `data/manifest.yaml` with the algorithm class, threshold, canonical fixture path, seed, and per-output gate blocks. **The gate is read-only after this.**
3. **(Phase 1)** Copy the layout from `TEMPLATE.md` (seed shape chosen by algorithm class — e.g., `py-monocle2` for ordinal trajectories).
4. **(Phase 2 — Equivalence Agent)** Translate each R function in dependency order. After each function, run the per-function parity diff. Iterate until the top-level gate clears at the pre-registered threshold.
5. **(Phase 3 — Acceleration Agent)** For each candidate rewrite from `ACCELERATION_PLAYBOOK.md`:
   - Check precondition + produce admissibility proof (E / B / C).
   - Apply on a working branch; re-run parity test (gate still clearing?); re-benchmark.
   - Accept if speedup > 1.05× and gate clears; else roll back.
   - Append one YAML block to `ITERATION_LOG.md` per attempt.
6. **(Phase 4 — release artefacts)** Tick `CHECKLIST.md` end-to-end; produce all mandatory deliverables:
   - `RECONSTRUCTION_REPORT.md` (8 sections, populated from per-phase artefacts)
   - `MATH.md` (perturbation bounds for any (B) rewrites)
   - `AUDIT.md` (R-function coverage, auto-generated by `engine.r_function_audit`)
   - `examples/evolution.png` (two-panel time + accuracy plot, auto-generated by `engine.plot_evolution`)
   - **`examples/compare_R_vs_Python.ipynb`** — pipeline parity
   - **`examples/tutorial_<dataset>.ipynb`** — Python-only function tutorial
   - **`examples/function_by_function_R_parity.ipynb`** — R⇄Python function dictionary
7. **(Phase 5 — release)** Build wheel, push to PyPI; create GitHub repo + release; add the port as a seed template for future ports.

**Always-first invariant**: Phase 0.5 (Discovery) is non-skippable. If discovery is skipped, the protocol fails — we risk re-implementing upstream work that already exists. The TSCAN port saved ~3000 LOC of Mclust code by finding `py-mclustR` mid-port; the next port should hit that win at Step 1, not by accident.

**No deferred items in Phase 4**: every artefact above is mandatory. The TSCAN-v0.1 port deferred Notebooks 1 + 2 and shipped without; v0.2 added them retroactively; v0.3 added Notebook 3. The protocol now blocks all three from being skipped.

---

## When to use this kit (and when not to)

Use this kit when:

- ✅ The target is an R / Bioconductor package with a clear numerical output (vector, matrix, table, cluster IDs, p-values).
- ✅ You can construct a canonical input fixture small enough for fast iteration (< 1 minute end-to-end for the R reference).
- ✅ The upstream R package is open-source under a permissive or copyleft license you can match.
- ✅ You're prepared to commit time on the order of 1–5 working days for a clean port (less for class A, more for class C with acceleration).

Don't use it when:

- ❌ The "R package" you want is closed-source or only described in a paper without runnable code — no executable spec means no parity oracle.
- ❌ The algorithm depends critically on R-only C++ extensions or S4-heavy Bioconductor classes — the protocol works on functional algorithms, not framework-coupled ones.
- ❌ You want a Python algorithm that's *better* than R, not identical. This kit refuses to widen the gate; if you want to improve the algorithm, fork after the port lands.
- ❌ You're targeting GPU-only kernels with no CPU reference — the parity oracle won't have anything to compare against.

---

## The evolutionary-RL analogy (in one paragraph)

The acceleration loop is **verifier-guided test-time search**, not weight-update RL — and importantly **not metric optimization**:

| Component | Mapping |
|---|---|
| **Policy** | The LLM in-context (no fine-tune, no weight updates). |
| **Action** | One algebraic rewrite drawn from `ACCELERATION_PLAYBOOK.md` (Woodbury, X⊤X memoisation, sparse-row truncation, MST ⊆ Delaunay, …). |
| **Environment** | The parity test + a 3-run-mean stopwatch on the canonical fixture (see [EVALUATION.md](EVALUATION.md)). |
| **Reward** | `r_t = φ(a_t) · speedup(a_t)` — gate must still clear (`φ = 1`), then wall-clock speedup ranks admissible candidates. |
| **Best-so-far register** | The last commit on the in-progress port. Roll back if a later rewrite breaks parity. |

> **What we don't do**: improve the algorithm's biological metric. Reconstruction's goal is **identical** outputs to the R reference, not "better" ones. Two evaluation plots come out of every port:
>
> - `time vs iteration` — monotonically decreasing as rewrites land.
> - `accuracy vs iteration` — flat at the maximum; every dip annotated with the math approximation that caused it.

No model weights change. Search occurs inside one coding-agent session, with the parity test as oracle and the wall-clock as cost function.

---

## Final artefact — reconstruction report

After the parity gate clears and the Acceleration loop terminates, the agent fills out [`RECONSTRUCTION_REPORT.md`](templates/RECONSTRUCTION_REPORT.template.md). The 8 sections:

1. **Identity** — package, upstream version, algorithm class, threshold, final parity value, audit class A/B/C, LOC, speedup vs R.
2. **R function coverage audit** — every exported R function from `NAMESPACE` is in the table (ported / skipped with reason). Auto-populated by `engine.r_function_audit`. Also lists **dependencies reused from omicverse** (ecosystem audit — how many LOC saved by reusing upstream py-mirrors).
3. **Parity evidence** — per-output metric values, per-fixture wall-clock + parity, reproducible reference command.
4. **Acceleration evidence** — two-panel evolution figure embedded, accepted-vs-rejected rewrites with admissibility proofs.
5. **Code quality audit** — `pip install` + `pytest` green + three mandatory notebooks executed + license compatible + version pinned. **All non-skippable.**
6. **Known limitations** — honest list of what the port doesn't do; never used as an excuse to widen the gate.
7. **Integration into omicverse** — vendor location, public-API exposure, tutorial slot.
8. **Sign-off** — author, date, active time spent, final audit class.

This is what we present as "the port is done".

---

## Evolution — how the protocol got here

The protocol grew by patching anti-patterns surfaced during real ports. Each version maps to a real port's failure mode; the kit grows by closing them, not by speculation.

| Version | What changed | Why |
|---|---|---|
| v1 | Initial 5-step protocol + parity-class taxonomy + acceleration playbook | Reference-driven cross-language synthesis baseline. |
| v2 | Added [`EVALUATION.md`](EVALUATION.md) (two-plot eval, warmup-excluded timing) + [`ITERATION_LOG.md`](templates/ITERATION_LOG.template.md) + structured [`RECONSTRUCTION_REPORT.md`](templates/RECONSTRUCTION_REPORT.template.md) | User clarified that reconstruction is "preserve accuracy, search for speed" — not metric optimisation. |
| v3 | Added [`DISCOVERY.md`](DISCOVERY.md) (Phase 0.5) + `engine/discover_omicverse_deps.py` | py-TSCAN discovered `py-mclustR` mid-port by luck; protocol now forces this check at Step 1. |
| v4 | Added [`NOTEBOOKS.md`](NOTEBOOKS.md) — two mandatory notebooks (`compare_R_vs_Python`, `tutorial_<dataset>`) | py-TSCAN-v0.1 deferred them and shipped without; v0.2 added them retroactively. |
| v5 | Added Notebook 3 (`function_by_function_R_parity`) — R⇄Python parameter dictionary | The first two notebooks didn't cover R users line-by-line porting their own code. |
| v6 (now) | Genericised env names (`PYTHON_TEST_ENV` / `R_TEST_ENV`) + `REBUILDR_ORG` env var + [`SETUP.md`](SETUP.md) + [`engine/smoke_test.py`](engine/smoke_test.py) + `requirements.txt` + portable-paths sweep | Portability audit surfaced that a second user couldn't clone-and-go without grepping the kit for hardcoded paths. |

---

## Ports shipped under this protocol

See [`examples/ROADMAP_TRAJ.md`](examples/ROADMAP_TRAJ.md) for the full ranked trajectory-inference list.

| Status | Port | Date | Audit | Speedup | Notes |
|---|---|---|---|---|---|
| ✅ | [py-monocle2](https://github.com/omicverse/py-monocle2) | 2026-04 | C | 102× | MST ⊆ Delaunay + Woodbury + X⊤X cache + sparse R |
| ✅ | [py-mclustR](https://github.com/omicverse/py-mclustR) v0.2.0 | 2026-05 | A | — | Fixed Fraley 1998 hcVVV bug surfaced by TSCAN |
| ✅ | [py-TSCAN](https://github.com/omicverse/py-TSCAN) | 2026-05 | A | ~28× | Class A + 3 notebooks + full discovery + reuse of py-mclustR |
| ⬜ next | py-tradeSeq | — | TBD | TBD | Highest cite density (~152/yr); DE-along-trajectory companion to Slingshot |
| ⬜ | py-destiny | — | TBD | TBD | Canonical DPT reference |
| ⬜ | py-URD | — | TBD | TBD | Branching developmental trees |
| ⬜ | py-SCORPIUS | — | TBD | TBD | dynbenchmark linear-trajectory winner |
| ⬜ | py-condiments | — | TBD | TBD | Multi-condition trajectory comparison (Nat Commun 2024) |

---

## FAQ

**Q: How long does a typical port take?**
A: Class A (translation-only): 1–3 days. Class B (minor optimisation): 2–5 days. Class C (major algorithmic restructuring with acceleration): 1–2 weeks. py-TSCAN was a class A done in ~6 hours; py-monocle2 was a class C done in ~2 weeks.

**Q: What if my target R package has no Python equivalent in scipy / sklearn / pygam for its dependencies?**
A: Either (a) port that dep first (and add it to the ecosystem) or (b) document it as "out of scope, deferred to a future minor release" in the reconstruction report. The TSCAN port did (a) for `mclust` (became `py-mclustR`) and (b) for `ggplot2` (plotting deferred to v0.2).

**Q: Can I publish to a different GitHub org?**
A: Yes. Export `REBUILDR_ORG=<your-org>` before running `engine.discover_omicverse_deps`. The kit doesn't push anything anywhere automatically — Phase 5's `gh repo create` and `twine upload` are explicit and you control where they go.

**Q: Does this work on Windows?**
A: Tested on Linux; macOS should work. Windows requires WSL2 because the kit shells out to bash for some pipe operations.

**Q: What if R Mclust / R rand / R any-stochastic function gives different results on my machine?**
A: That's why the manifest pins a seed AND the class taxonomy degrades to distributional metrics (KS / Wasserstein) for stochastic outputs. If you're seeing platform-specific divergence beyond what KS allows, file an issue on the upstream R package — that's a non-determinism bug in R, not in your port.

**Q: My port's `difftest` p-values don't match R because `pygam` ≠ `mgcv`. What now?**
A: Honest answer (see py-TSCAN Notebook 3): GAM implementations have meaningfully different fits at small df. Document it in `MATH.md`, switch to Spearman-on-`-log10(p)` + top-K Jaccard as the inference-class metric, and call it out as a known limitation in the reconstruction report. **Never widen the gate to make the p-values "pass" element-wise.**

**Q: What happens if my Acceleration Agent rewrite gets a 1.2× speedup but breaks Pearson from 1.0000 to 0.9970, still above the threshold?**
A: Reject. The accuracy is allowed to dip ONLY for (B) bounded-ε rewrites where the perturbation bound is derived in closed form. A "small" empirical accuracy drop with no closed-form bound is a bug, not an optimisation.

---

## License

The kit itself is MIT. Each individual port matches its upstream R package's license (GPL-3 if upstream is GPL ≥ 2; MIT if upstream is MIT / BSD / Apache; etc.). See `TEMPLATE.md §License decision matrix`.

---

## Provenance

This protocol distils experience from porting ~10 canonical bioinformatics R / Bioconductor packages to Python under reference-driven parity gates. The reference for the underlying methodology is the "PolyPort" recipe (reference-driven cross-language library synthesis via LLM agents). All case-study ports live under `github.com/omicverse/py-*`; this folder factors out the recipe so each subsequent port follows the same engineering loop without re-deriving it from scratch.
