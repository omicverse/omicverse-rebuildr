# Discovery — Reuse Before Rebuild

> Before writing any new port, check whether `github.com/omicverse` already has it (or has its upstream dependencies). The goal is an **ecosystem**, not 50 isolated rewrites.

## The two questions to answer

1. **Is the target package itself already ported?**
   If `omicverse/py-<X>` exists, do NOT start a duplicate. Open an issue on the existing repo, or PR an improvement.

2. **Are any of the upstream R/Bioc dependencies already ported?**
   Reuse them via `pip install` instead of re-implementing. This is how `py-TSCAN` got `py-mclustR` essentially for free.

Both questions are answered by one tool: `engine/discover_omicverse_deps.py`.

## When in the protocol

Discovery runs **immediately after Phase 0** (parity gate decision) and **before Phase 1** (scaffold). The agent must produce a `DISCOVERY.md` artefact in the port directory before any scaffolding code is written.

## Usage

### Quick check: is `<R_pkg>` already ported?

```bash
python -m engine.discover_omicverse_deps --check TSCAN
```

Output:
```
## Discovery — `TSCAN`

**No existing omicverse port found.** Safe to start a new port.
```

Or, if it IS already ported:
```
## Discovery — `mclust`

**1 match(es)** under `github.com/omicverse`:

| Repo | Description | Last update |
|---|---|---|
| [`py-mclustR`](https://github.com/omicverse/py-mclustR) | A pure-Python re-implementation of CRAN mclust... | 2026-05-21 |
```

If you see your target package here: **stop**. Use it. Don't duplicate.

### Full dep audit: which of `<X>`'s R deps are already ported?

```bash
python -m engine.discover_omicverse_deps \
    --description /path/to/<pkg>-ref/DESCRIPTION \
    --output DISCOVERY.md
```

Output is a markdown table — paste into the port's `DISCOVERY.md` and into §X of `RECONSTRUCTION_REPORT.md`.

### Cache

Repo list is cached in `engine/omicverse_repos.cache.json` for 24 hours. Override with `--refresh` if you just published a new port and want it to show up.

## The mapping rules

The tool uses three heuristics to map an R package name to an omicverse repo:

1. **Curated alias map** for non-obvious cases (`Seurat → py-CCA`, `WGCNA → py-hdWGCNA`). Append new entries to `engine/discover_omicverse_deps.py::ALIAS_MAP` when you publish a port whose name doesn't directly match.

2. **Auto-mirror naming**: `R::<X>` → `omicverse/py-<X>` (case-insensitive). Also covers `py-<X>R` for R-suffix CRAN names like `mclust → py-mclustR` and `rust-<X>` for performance kernels.

3. **Description substring match** (looser fallback): word-boundary regex on the repo's description text.

When you publish a new port whose name doesn't fit rule 2, **add an alias** so future ports find it.

## What to do with each kind of match

| Kind of match | Action |
|---|---|
| Direct mirror of target package | **Stop the port.** Reuse the existing repo. |
| Direct mirror of an `Imports:` dep | Add to `pyproject.toml::dependencies`. Reuse, don't reimplement. |
| Mirror of a `Suggests:` dep | Add as optional dep (`[project.optional-dependencies]`). |
| Mirror of a `LinkingTo:` dep (C++ link target) | Usually means a Rust port exists (e.g., `rust-NMF`) — use as a hard dep. |
| Description-substring match only | Lower confidence — read the description before depending. Some matches are spurious. |
| No match at all | Either (a) the dep has a native Python equivalent (scipy/sklearn/statsmodels/networkx) — fine; or (b) it's a future omicverse port worth scoping. Add a TODO to the roadmap. |

## What goes in the port's `DISCOVERY.md`

```markdown
# Discovery — py-<PkgName>

## Direct check
[paste output of --check <PkgName>]

## Dependency audit
[paste output of --description <pkg>-ref/DESCRIPTION]

## Decisions
- `mclust` → reuse `py-mclustR` as a hard dep.
- `mgcv` → use `pygam` (native Python equivalent, no omicverse mirror).
- `igraph` → use `networkx` (native Python equivalent).
- `ggplot2` / `gplots` / `shiny` / `grid` → out of scope (plotting + GUI).
- ...
```

Commit this file before any algorithmic code.

## What goes in the `RECONSTRUCTION_REPORT.md`

Add a section to the report template (§2.5 already references this):

```markdown
### Dependencies reused from omicverse

| R dep | omicverse port | Reused as | Saved work |
|---|---|---|---|
| `mclust` | `py-mclustR` | hard dep in pyproject.toml | ~3000 LOC, ~2 weeks of work |
```

This is how we **measure ecosystem ROI** — each reused dep is a port we didn't have to write twice.

## When to add a new entry to `ALIAS_MAP`

After releasing `omicverse/py-<X>` whose repo name doesn't follow rule 2:

```python
# in engine/discover_omicverse_deps.py
ALIAS_MAP = {
    ...
    "<lowercase R name>": ["py-<NewRepoName>"],
}
```

Submit a PR to `omicverse-rebuildr` so the next agent's discovery step picks it up.

## Anti-patterns

- **Don't skip the discovery step** because "I'm sure nothing exists yet." TSCAN's port would have re-implemented Mclust from scratch (a multi-week effort) if I hadn't found `py-mclustR` mid-Phase-2. Discovery is a 30-second tool call — always run it.

- **Don't reuse something that isn't actually parity-validated**. Check the candidate omicverse port's own `RECONSTRUCTION_REPORT.md` (or README) for its parity gate status. A port with `xfail` against R isn't always safe to depend on for *your* port's parity.

- **Don't re-export omicverse ports' internals** from your port. Depend on their public API only — otherwise you couple to internal layout that may shift between releases.
