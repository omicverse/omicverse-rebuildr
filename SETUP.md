# Setup — first-time install

> Walks a new user from `git clone` to "the kit runs on my machine and I can start porting". Should take ~30 minutes.

## 1. Prerequisites

The kit shells out to several CLI tools — none ship with it. Install before continuing:

| Tool | Used for | Install |
|---|---|---|
| **Python 3.9+** | the agent + engine scripts | `conda` / system Python |
| **R 4.x** | reference runs of the upstream R package | `conda install -c conda-forge r-base` / system |
| **conda** (or mamba) | provisioning the two side-by-side envs | https://conda.io |
| **gh** (GitHub CLI) | `engine/discover_omicverse_deps.py` calls `gh repo list omicverse`; release helpers call `gh repo create` / `gh release create` | https://cli.github.com |
| **Jupyter** | rendering the three mandatory notebooks | comes with `requirements.txt` |
| **git** | everything | system |

Run a quick check:

```bash
python --version   # ≥ 3.9
R --version        # ≥ 4.0
conda --version
gh --version
git --version
```

The kit assumes a POSIX shell (bash/zsh). On Windows use WSL2.

## 2. Provision two conda envs

Two side-by-side envs let the agent run Python and R against the same fixture without polluting either.

### Python target env

```bash
# Pick any name you like. Examples: 'rebuild-py', 'porting', 'omicverse-dev'.
conda create -n rebuild-py python=3.10 -y
conda activate rebuild-py
pip install -r omicverse-rebuildr/requirements.txt
```

### R reference env

```bash
conda create -n rebuild-r -c conda-forge r-base=4.3 r-essentials -y
conda activate rebuild-r
# Add upstream-R-package installs as you do each port, e.g.:
#   R -e 'if (!requireNamespace("BiocManager", quietly=TRUE)) install.packages("BiocManager", repos="https://cloud.r-project.org")'
#   R -e 'BiocManager::install("TSCAN")'
```

### Tell the kit where they live

The agent scripts read two env vars. Add to your shell config (`~/.bashrc`, `~/.zshrc`, …):

```bash
export PYTHON_TEST_ENV=/path/to/your/rebuild-py     # `conda info --envs` → look up the path
export R_TEST_ENV=/path/to/your/rebuild-r
```

The default fallbacks in `engine/loop.py` and `templates/test_exact_match.template.py` use literal `/path/to/your/<X>/env` placeholders, so if you don't export the vars the agent will exit with a clear error rather than silently use the wrong env.

## 3. Authenticate `gh` (one-time)

The Discovery step (Phase 0.5) and the Release step (Phase 5) both call `gh`. Without auth they error out.

```bash
gh auth login
# Then verify:
gh api user --jq .login           # should print your GitHub handle
gh repo list omicverse --limit 1  # should print one omicverse repo
```

## 4. (Optional) Authenticate `twine` for PyPI

Only needed if you plan to publish to PyPI under your own org. Edit `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-<your-API-token>
```

If you're not the maintainer of `pypi.org/project/<pkg>`, the Phase 5 `twine upload` will reject your push — you can still ship the wheel + tarball as GitHub release assets.

## 5. Smoke-test the kit

A 30-second check that the engine modules import cleanly and the parity metrics work:

```bash
cd omicverse-rebuildr
python -m engine.smoke_test
```

Expected output: `[smoke] OK — all engine modules import and 8 parity metrics compute correctly.`

If you see import errors, re-check `pip install -r requirements.txt`.

## 6. Pick a target R package

```bash
# Phase 0.5 — check if it's already ported:
python -m engine.discover_omicverse_deps --check <YourTargetRPackage>
```

If the output says **"No existing omicverse port found"**, you're ready. Continue with [PROTOCOL.md](PROTOCOL.md) Step 1.

## Assumptions and conventions

- **Working tree**: pick any directory under your scratch / project area. The kit doesn't write outside the port directory you create.
- **GitHub org**: the kit refers to `github.com/omicverse` throughout because that's the parent ecosystem. If you're porting under a different org, do a one-time find-replace: `s/omicverse/<your-org>/g` across the docs (the engine scripts read the org from `engine/discover_omicverse_deps.py::ORG_NAME` — see below to change).
- **Operating system**: tested on Linux. macOS should work. Windows requires WSL2.
- **Internet access**: required for `gh repo list omicverse` (cached for 24h after first call) and for `pip install` from PyPI.

## Pointing the kit at a different GitHub org

Open `engine/discover_omicverse_deps.py` and change one line near the top:

```python
ORG_NAME = "omicverse"   # ← rename to your org
```

The docs themselves still say "omicverse" in narrative paragraphs; the protocol works regardless of where ports are published.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `gh: command not found` | gh CLI not installed | `brew install gh` / `conda install -c conda-forge gh` |
| `gh: not authenticated` | step 3 skipped | `gh auth login` |
| `R: command not found` from a test | `R_TEST_ENV` not exported, or env path wrong | re-run `conda info --envs`, paste the right path |
| `ModuleNotFoundError: pyreadr` | missing dep | `pip install pyreadr` (it's in requirements.txt; check that you activated the right env) |
| `jupyter nbconvert ... failed` | kernel mismatch | run `python -m ipykernel install --user --name rebuild-py` |
| `Permission denied` writing under `/home` | shared HPC with quotas | the kit doesn't require `/home`; use your scratch tree |
