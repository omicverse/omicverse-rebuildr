# Worked Example — porting `TSCAN` end-to-end

> A concrete walkthrough of the Omicverse-RebuildR protocol on a small ordinal-output package, so future-you can pattern-match.

## Phase 0 — Decide the gate

1. Look up TSCAN's canonical entry point: `TSCAN::exprmclust()` followed by `TSCAN::TSCANorder()`. Returns a per-cell pseudotime vector.
2. Output type: **1-D float vector (pseudotime)** → algorithm class **ordinal** ([PARITY_TAXONOMY.md](../PARITY_TAXONOMY.md) class 6).
3. Default threshold for ordinal: Pearson ≥ 0.99.
4. Canonical fixture: `scanpy.datasets.paul15()` (n=2730 cells, hematopoietic differentiation). Public, small, deterministic with seed.
5. Seed: 42.

Write `data/manifest.yaml`:

```yaml
package: py-TSCAN
upstream:
  name: TSCAN
  version: "1.40.0"
  source: Bioconductor
  url: https://bioconductor.org/packages/TSCAN/

algorithm_class: ordinal
parity_threshold: 0.99
fixture:
  path: data/fixture_paul15.h5ad
  source: scanpy.datasets.paul15()
  description: "Mouse myeloid differentiation; paul15 from scanpy"
  expected_shape: [2730, 3451]
reference_command: tests/r_reference_driver.R
seed: 42
outputs:
  - name: pseudotime
    type: "1d vector"
    location_reference: "$.Pseudotime"
    location_candidate: "adata.obs['Pseudotime']"
    metric: ordinal
    threshold: 0.99
acceleration:
  enabled: true
  max_iterations: 10
```

Commit this. **No further edits until release.**

## Phase 1 — Scaffold

Seed template: `py-monocle2` (same algorithm class).

```bash
cd <your-working-tree>/
mkdir py-TSCAN && cd py-TSCAN
git init

# Copy LAYOUT ONLY from py-monocle2
cp -r ../omicverse_dev/py-monocle2/{pyproject.toml,LICENSE,.gitignore} .
mkdir -p tscan tests examples data
touch tscan/__init__.py tscan/core.py tscan/clustering.py tscan/ordering.py
touch tests/__init__.py tests/conftest.py tests/test_smoke.py tests/test_exact_match.py
```

Rewrite `pyproject.toml` package name and deps. Clone TSCAN R source into `TSCAN-ref/`:

```bash
git clone https://github.com/zji90/TSCAN TSCAN-ref
echo "TSCAN-ref/" >> .gitignore
```

Install TSCAN in R reference env:

```bash
conda activate $R_TEST_ENV
R -e 'BiocManager::install("TSCAN")'
```

## Phase 2 — Equivalence Agent loop

TSCAN's R code (`TSCAN/R/exprmclust.R`):

```r
exprmclust <- function(data, clusternum=2:9, modelNames="VVV", reduce=T) {
  if (reduce) {
    data <- princomp(t(data))$scores[, 1:2]
  }
  res <- Mclust(data, G=clusternum, modelNames=modelNames)
  clusterid <- res$classification
  clucenter <- res$parameters$mean
  ...
}
```

Translate to `tscan/clustering.py`:

```python
import numpy as np
from sklearn.decomposition import PCA
# Re-use py-mclustR if available; otherwise fall back to sklearn.mixture
from pymclustr import Mclust

def exprmclust(data, clusternum=range(2, 10), model_names="VVV", reduce=True):
    if reduce:
        data = PCA(n_components=2).fit_transform(data.T)
    res = Mclust(data, G=clusternum, modelNames=model_names)
    return {
        "clusterid": res.classification,
        "clucenter": res.parameters_mean,
        ...
    }
```

Run parity diff after each function:

```bash
conda activate $PYTHON_TEST_ENV
python -m omicverse_rebuild.engine.loop \
    --port-dir <your-working-tree>/py-TSCAN \
    --phase equivalence
```

Iterate until `[PASS] py-TSCAN: metric={'pseudotime': 0.998} ...`.

Common gotchas for TSCAN specifically:
- `princomp` in R uses N-1 denominator; sklearn `PCA` uses N. Verify.
- `Mclust` cluster IDs are not sign-stable; use ARI on the intermediate cluster step rather than label agreement.
- TSCAN `TSCANorder` builds an MST on cluster centres, then walks longest path. The MST is on a **dense** matrix even for thousands of cells — this is fine here since `K ≤ 9`.

When `pytest tests/test_exact_match.py` passes at Pearson ≥ 0.99 on paul15, **Phase 2 is done**.

## Phase 3 — Acceleration Agent (optional for TSCAN)

TSCAN is tiny — `K ≤ 9` cluster centres, no `(I + λL)` solve, no soft-assignment matrix. The only worthwhile rewrites from the [playbook](../ACCELERATION_PLAYBOOK.md):

- §1.5 Eigen on Gram matrix vs `princomp` — saves ~30% on the PCA step.
- §3.3 Connected-component reduction in the MST walk — saves no measurable time at K=9.

Mark the audit as class **A** (translation-only) in the manifest after release. Don't force-fit speedups that aren't there.

## Phase 4 — Release

```bash
# Fresh-env install check
conda create -n tscan-test python=3.10 -y && conda activate tscan-test
pip install -e .
pytest -q                       # green
jupyter nbconvert --to notebook --execute examples/benchmark_vs_R.ipynb

# Push
gh repo create omicverse/py-TSCAN --public --description "Pure-Python port of TSCAN — pseudo-time reconstruction via Mclust + MST"
git remote add origin git@github.com:omicverse/py-TSCAN.git
git add . && git commit -m "Initial release v0.1.0 — Pearson ≥ 0.99 vs R on paul15"
git push -u origin main

# PyPI release via the omicverse release workflow
```

## Phase 5 — Integrate into omicverse

Vendor into `omicverse/external/pytscan/` and expose `omicverse.single.TSCAN`. Add to `omicverse-guide`.

Mark `examples/ROADMAP_TRAJ.md` as ✅ done.

## Total time budget

A first-time port of TSCAN under this protocol takes ~3–5 working days for the Equivalence phase (most of the time is on the Mclust dependency), ~1 day for Phase 4–5. Subsequent trajectory ports inherit the Mclust resolution and `py-monocle2`-style packaging, so the next 5 ports should take ~2 days each on average.
