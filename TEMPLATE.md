# Standard `py-<pkg>` Repo Layout

> Mirrors `py-DoubletFinder` / `py-monocle2`. Copy this layout for every new port; never re-derive.

## Top-level tree

```
py-<pkg>/
├── README.md                  # User-facing — install, quickstart, R-parity table
├── LICENSE                    # Match upstream R package (CC0 / GPL / MIT / Artistic)
├── pyproject.toml             # Build + deps + metadata
├── .gitignore                 # Standard Python + ignore data/raw
│
├── <pkg_modulename>/          # The actual Python package (lower snake_case)
│   ├── __init__.py            # Public API surface (class + function exports)
│   ├── core.py                # Main class / orchestrator
│   ├── <algorithm_a>.py       # One file per algorithmic step
│   ├── <algorithm_b>.py
│   ├── preprocessing.py
│   └── utils.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # pytest fixtures (load reference outputs)
│   ├── test_smoke.py          # "does it run at all" — fastest test
│   ├── test_exact_match.py    # The parity gate against the R reference
│   ├── test_<feature>.py      # Per-feature tests
│   └── r_reference_driver.R   # The R reference runner invoked by test_exact_match
│
├── examples/                            # MANDATORY: all 3 notebooks below per NOTEBOOKS.md
│   ├── compare_R_vs_Python.ipynb        # Notebook 1 — pipeline-level parity (6-section schema)
│   ├── tutorial_<dataset>.ipynb         # Notebook 2 — Python-only function tutorial
│   ├── function_by_function_R_parity.ipynb  # Notebook 3 — R⇄Python per-function parameter dictionary
│   ├── r_per_function_dump.R            # R driver dumping per-function outputs (consumed by Notebook 3)
│   ├── *.executed.ipynb                 # Pre-executed copies for GitHub preview (optional)
│   ├── evolution.png                    # Two-panel acceleration plot (auto-rendered)
│   ├── r_driver_<dataset>.R             # R driver for Notebook 1 (if not already in tests/)
│   └── data/                            # Small fixture copies (or .gitignore'd if large)
│
├── data/                      # Reference fixtures (small — gitignored if large)
│   └── manifest.yaml          # Pre-registered parity gate (see engine/manifest.template.yaml)
│
├── <pkg>-ref/                 # Cloned upstream R source for inspection (gitignored)
│   ├── R/
│   ├── DESCRIPTION
│   ├── NAMESPACE
│   └── R_README_original.md
│
├── dist/                      # Build artefacts (gitignored)
│
└── MATH.md                    # Acceleration Agent's derivations (perturbation bounds, identities used)
```

## Module file conventions

### `<pkg_modulename>/__init__.py`

Exports the public API — both class-based and function-based, to match Seurat / scanpy idiom side-by-side:

```python
from .core import <PkgName>           # Class API
from .<algorithm_a> import <fn_a>     # Functional API (mirror R one-to-one)
from .<algorithm_b> import <fn_b>
...

__all__ = ["<PkgName>", "<fn_a>", "<fn_b>", ...]
__version__ = "0.1.0"
```

### `<pkg_modulename>/core.py`

A class that owns the `AnnData` and provides method-chaining:

```python
class <PkgName>:
    def __init__(self, adata: anndata.AnnData, ...):
        self.adata = adata
        ...

    def step_a(self, **kwargs) -> "<PkgName>":
        ...
        return self

    def step_b(self, **kwargs) -> "<PkgName>":
        ...
        return self
```

Each method writes results back into `self.adata.obs / .obsm / .uns / .layers`.

### `<pkg_modulename>/<algorithm>.py`

One R function ⇄ one Python function. Function names match R **up to PEP-8** (`paramSweep` → `param_sweep`). Argument names and defaults match R verbatim.

Each module-level function is callable without instantiating the class, for users who want the R-style functional API.

## `pyproject.toml` (skeleton)

See [templates/pyproject.template.toml](templates/pyproject.template.toml).

## `manifest.yaml` (pre-registered parity gate)

See [engine/manifest.template.yaml](engine/manifest.template.yaml).

Committed to the repo **before** Step 3 (the agent loop) begins.

## `tests/test_exact_match.py` (the parity gate as a unit test)

The test that decides "is this port done?":

```python
def test_parity_against_R(canonical_fixture, r_reference_output):
    import <pkg_modulename> as P
    candidate = P.<entry_point>(canonical_fixture)
    metric = compute_parity(
        reference=r_reference_output,
        candidate=candidate,
        algorithm_class=manifest["algorithm_class"],
    )
    assert metric >= manifest["parity_threshold"], (
        f"Parity gate failed: {metric:.4f} < {manifest['parity_threshold']:.4f}"
    )
```

`compute_parity` and `<class>_threshold` are imported from [engine/parity_metrics.py](engine/parity_metrics.py).

## `tests/r_reference_driver.R`

A tiny R script:

```r
#!/usr/bin/env Rscript
# Reference runner — invoked by tests/test_exact_match.py via Rscript.
# Loads the canonical fixture, runs the upstream R package, writes JSON.

suppressMessages({
  library(<UpstreamR>)
})
args <- commandArgs(trailingOnly = TRUE)
fixture_path <- args[1]
output_path  <- args[2]

# load fixture
input <- readRDS(fixture_path)

# run reference
set.seed(42)
result <- <UpstreamR>::<entry_point>(input, ...)

# serialise to JSON
jsonlite::write_json(result, output_path, auto_unbox = TRUE, digits = NA)
```

Invoked under the R reference conda env (`$R_TEST_ENV`).

## `examples/benchmark_vs_R.ipynb`

A side-by-side notebook:
1. Load the canonical fixture (or a public one like `scanpy.datasets.paul15`).
2. Run R reference via `subprocess.run(['Rscript', 'r_driver_<dataset>.R'])`.
3. Run Python port.
4. Compute the parity metric live; print the threshold + value.
5. Plot wall-clock comparison.

This notebook is **pre-executed** and committed (the `.executed.ipynb` variant) so GitHub renders it without re-running.

## `README.md` (user-facing)

Skeleton (see [templates/README.template.md](templates/README.template.md)):

1. One-paragraph blurb describing what the package does + provenance.
2. Install (`pip install py-<pkg>`).
3. Quickstart (class API).
4. Low-level functional API (R one-to-one mirror).
5. **What's included** table (Python ⇄ R function map).
6. **Reproducing R results exactly** — a code block that runs the parity test from the user's side.
7. Relationship to omicverse.
8. Citation.
9. License.

## Naming conventions

| Where | Convention | Example |
|---|---|---|
| GitHub repo | `py-<PkgName>` (matches R casing) | `py-DoubletFinder` |
| PyPI distribution | `py<pkgname>` lowercase | `pydoubletfinder` |
| Python module / import | `<pkgname>` snake_case | `pydoubletfinder` |
| Public class | `<PkgName>` PascalCase | `DoubletFinder` |
| Public functions | `<r_fn>` → `<r_fn>` snake_case | `paramSweep` → `param_sweep` |

## What goes in `.gitignore`

```
# Build
dist/
build/
*.egg-info/
__pycache__/
*.pyc

# Upstream R clone
<pkg>-ref/

# Large fixtures
data/*.h5ad
data/*.rds
data/raw/

# IDE
.vscode/
.idea/

# Tests
.pytest_cache/
.coverage
htmlcov/
```

## License decision matrix

| Upstream R package license | Python port license |
|---|---|
| GPL-2 / GPL-3 | GPL-3 (must match) |
| MIT / BSD / Apache | MIT (recommended) |
| Artistic | Artistic-2.0 |
| CC0 | CC0 |
| LGPL | LGPL or MIT (compatible) |
| Custom / "academic use only" | Mirror the upstream restriction; flag for legal review before publishing to PyPI |

## Recommended seed templates per algorithm class

(From [PROTOCOL.md](PROTOCOL.md) Step 1.)

| Class | Seed template |
|---|---|
| Ordinal / trajectory | `py-monocle2` |
| Classification | `py-DoubletFinder` |
| Clustering | `py-mclustR` |
| Statistical inference | `py-miloR` |
| Embedding | `py-CCA` |
| Deterministic | `rust-bandnorm` |
| Multi-stage pipeline with a Seurat dependency | [`py-spatialecotyper`](https://github.com/omicverse/py-spatialecotyper) |

`py-spatialecotyper` is the seed to copy when the upstream package is a
*pipeline* rather than a single algorithm, and especially when it leans on
Seurat or on R's RNG. What to lift from it:

* `tests/r_reference_driver.R` — a stage-by-stage dump (one artefact per
  pipeline step) so a parity failure localises to one function instead of
  propagating. Portable dump conventions: sparse -> MatrixMarket + two dimname
  files, dense -> gzipped TSV + dimname files, data.frame -> TSV with a
  `.rowname` column, everything else -> `jsonlite::write_json(..., digits = NA)`.
* `tests/stage_check.py` — the development harness that feeds each Python
  function *R's own input for that stage*.
* `pyspatialecotyper/rrandom.py` — R's Mersenne-Twister, `R_unif_index`
  rejection sampler and inversion `rnorm`, verified bit-identical. Copy this
  verbatim for any port whose R original calls `sample()`, `runif()` or
  `rnorm()`; it converts stochastic outputs into deterministic, diffable ones.
* `pyspatialecotyper/_modularity.py` — Seurat's `ComputeSNN` and
  `ModularityOptimizer.cpp` (including its `JavaRandom` LCG), so `FindClusters`
  reproduces Seurat's Louvain exactly rather than approximately.
* The habit of measuring **R against itself** before gating: four of this
  port's outputs turned out to be irreproducible run-to-run in R, and knowing
  that changed which gate was honest.
