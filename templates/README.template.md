# py-<PkgName>

A **pure-Python re-implementation of [<UpstreamR>](https://github.com/upstream/repo)** (<First author> et al., *<Journal>* <Year>) for <one-line of what it does>.

- AnnData-native — drop-in for the scanpy ecosystem
- **No `rpy2`**, no R install — implemented directly in NumPy/SciPy
- Same function surface as the R workflow (`<r_fn_a>` → `<r_fn_b>` → `<r_fn_c>`)
- <Algorithm class metric ≥ threshold> against the R reference on the canonical fixture (see `tests/test_exact_match.py`)

> This is a **standalone mirror** of the canonical implementation that lives in [`omicverse`](https://github.com/Starlitnightly/omicverse) (`omicverse.<subpackage>.<PkgName>`). All algorithmic work is developed upstream in omicverse and synced here for users who want <UpstreamR> without the full omicverse stack.

## Install

```bash
pip install py<pkgname>
```

## Quick-start (class API)

```python
import anndata as ad
from <pkgname> import <PkgName>

adata = ad.read_h5ad("mydata.h5ad")          # cells × genes

obj = <PkgName>(adata)

# pipeline
obj.<step_a>(...)
obj.<step_b>(...)
obj.<step_c>(...)

adata.obs["<output_field>"]                  # results land in AnnData
```

## Low-level functional API (mirrors R one-to-one)

```python
from <pkgname> import <fn_a>, <fn_b>, <fn_c>

result = <fn_a>(adata, ...)
...
```

## What's included

| Python | R counterpart | Purpose |
|---|---|---|
| `<PkgName>` class | — | AnnData-native lifecycle wrapper |
| `<fn_a>` | `<rFnA>` | <what it does> |
| `<fn_b>` | `<rFnB>` | <what it does> |
| `<fn_c>` | `<rFnC>` | <what it does> |

## Reproducing R results exactly

```python
# pip install py<pkgname>
# requires R + R reference conda env with <UpstreamR> installed

import anndata as ad
from <pkgname> import <PkgName>

adata = ad.read_h5ad("tests/data/fixture.h5ad")

obj = <PkgName>(adata)
obj.run()

# Pearson(obj.adata.obs['Pseudotime'], R Monocle 2 Pseudotime) ≥ 0.99
```

`tests/test_exact_match.py` runs the R reference under the `$R_TEST_ENV` and asserts the pre-registered parity gate.

## Acceleration notes (optional — class-C ports only)

If this port committed algebraic rewrites for speed (per [omicverse-rebuildr's ACCELERATION_PLAYBOOK](https://github.com/omicverse/omicverse-rebuildr)), they are documented in `MATH.md` with the admissibility proof (exact identity, bounded ε-approximation with explicit perturbation bound, or class-containment theorem).

## Relationship to omicverse

Developed **upstream** in [`omicverse`](https://github.com/Starlitnightly/omicverse):

- Canonical implementation: `omicverse.<subpackage>.<PkgName>`
- Standalone mirror (this repo): same code, same API, minus the omicverse packaging

## Citation

If you use this package, please cite the original <UpstreamR> paper:

> <First author>, <co-authors>. **<Title>** *<Journal>* <volume>, <pages> (<Year>).

and acknowledge omicverse / this repo for the Python port.

## License

<License from upstream R package — see omicverse-rebuildr's TEMPLATE §License decision matrix>
