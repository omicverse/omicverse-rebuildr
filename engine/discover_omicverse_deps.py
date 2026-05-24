"""Discover existing omicverse packages that a new port can reuse.

Two main use cases:

1. **Avoid duplicate work**: before porting R package X, check if `omicverse/py-X`
   already exists.

2. **Find reusable upstream dependencies**: parse the R package's DESCRIPTION
   (`Imports`, `Depends`, `LinkingTo`) and report which of those R deps already
   have a Python mirror under github.com/omicverse — so the new port can
   `pip install` them instead of re-implementing.

Usage:

    # Quick check: is `tradeSeq` already done?
    python -m engine.discover_omicverse_deps --check tradeSeq

    # Full audit: which of TSCAN's R deps already have py- ports?
    python -m engine.discover_omicverse_deps \\
        --description /path/to/TSCAN-ref/DESCRIPTION

    # Refresh the cache (otherwise reuse cached results up to 24h old)
    python -m engine.discover_omicverse_deps --refresh

Cache file: `engine/omicverse_repos.cache.json` — list of {name, description}.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

# Which GitHub org hosts the existing Python ports. Override with the
# REBUILDR_ORG env var if you maintain ports under a different account.
ORG_NAME = os.environ.get("REBUILDR_ORG", "omicverse")

CACHE_PATH = Path(__file__).resolve().parent / f"{ORG_NAME}_repos.cache.json"
CACHE_TTL_S = 24 * 3600    # 24 hours


# ----------------------------------------------------------------------------- #
# Fetching                                                                      #
# ----------------------------------------------------------------------------- #

def fetch_omicverse_repos(*, force_refresh: bool = False) -> list[dict]:
    """Return list of {name, description, updatedAt, isArchived} dicts for ORG_NAME."""
    if not force_refresh and CACHE_PATH.exists():
        age = time.time() - CACHE_PATH.stat().st_mtime
        if age < CACHE_TTL_S:
            data = json.loads(CACHE_PATH.read_text())
            print(f"[discover] using cached repo list ({len(data)} repos, "
                  f"age {age/60:.0f} min)", file=sys.stderr)
            return data

    print(f"[discover] fetching {ORG_NAME} repo list via gh CLI...",
          file=sys.stderr)
    proc = subprocess.run(
        ["gh", "repo", "list", ORG_NAME, "--limit", "300",
         "--json", "name,description,updatedAt,isArchived"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"`gh repo list {ORG_NAME}` failed:\n{proc.stderr}\n"
            "Hint: run `gh auth status` to verify GitHub auth, "
            f"or override the org via REBUILDR_ORG=<your-org>."
        )
    data = json.loads(proc.stdout)
    CACHE_PATH.write_text(json.dumps(data, indent=2))
    print(f"[discover] cached {len(data)} repos to {CACHE_PATH}",
          file=sys.stderr)
    return data


# ----------------------------------------------------------------------------- #
# R-name → omicverse-repo matching                                              #
# ----------------------------------------------------------------------------- #

# Curated alias map for cases where the omicverse repo name doesn't directly
# follow `py-<R_package_name>` (case-insensitive) — append here as new ports land.
ALIAS_MAP: dict[str, list[str]] = {
    # Seurat sub-functions
    "seurat":          ["py-cca"],            # py-CCA ports Seurat::RunCCA
    "monocle":         ["py-monocle2"],        # Monocle 2 specifically
    "matrix":          [],                     # too generic — skip
    "ggplot2":         [],                     # plotting — skip
    "shiny":           [],                     # GUI — skip
    "knitr":           [],                     # docs — skip
    "biocgenerics":    [],
    "s4vectors":       [],
    "iranges":         [],
    "genomicranges":   [],
    "summarizedexperiment": [],
    "singlecellexperiment": [],
    "anndata":         ["anndata-oom", "mudata-oom"],
    "miloR":           ["py-miloR"],
    "scDblFinder":     ["py-scDblFinder"],
    "DoubletFinder":   ["py-DoubletFinder"],
    "DESeq2":          [],                     # not yet ported
    "edgeR":           ["py-edgeR"],
    "limma":           ["py-limma"],
    "WGCNA":           ["py-hdWGCNA"],         # hdWGCNA covers WGCNA usage
    "TSCAN":           [],                     # to be added once py-TSCAN releases
}


def _norm(name: str) -> str:
    return name.strip().lower().replace(".", "").replace("-", "").replace("_", "")


def match_r_package(r_name: str, repos: list[dict]) -> list[dict]:
    """Return omicverse repo dicts that likely port the given R package."""
    rn = _norm(r_name)
    matches: list[dict] = []

    # 1. ALIAS_MAP (curated overrides)
    for repo_name in ALIAS_MAP.get(r_name, []) + ALIAS_MAP.get(rn, []):
        for r in repos:
            if r["name"].lower() == repo_name.lower():
                matches.append(r)

    # 2. py-<r_name> / rust-<r_name> direct mirror
    for r in repos:
        rn2 = _norm(r["name"])
        if rn2 == "py" + rn or rn2 == "rust" + rn:
            if r not in matches:
                matches.append(r)
        elif rn2 == "py" + rn + "r":   # e.g., py-mclustR for mclust
            if r not in matches:
                matches.append(r)

    # 3. Substring match in description (looser)
    pat = re.compile(rf"\b{re.escape(r_name)}\b", re.IGNORECASE)
    for r in repos:
        desc = r.get("description") or ""
        if pat.search(desc) and r not in matches:
            matches.append(r)

    return matches


# ----------------------------------------------------------------------------- #
# R DESCRIPTION parsing                                                         #
# ----------------------------------------------------------------------------- #

DEP_FIELD_PAT = re.compile(
    r"^(Imports|Depends|LinkingTo|Suggests):\s*(.+?)(?=^\S|\Z)",
    re.M | re.S,
)

def parse_description(path: Path) -> dict[str, list[str]]:
    """Parse a CRAN/Bioconductor DESCRIPTION into {field: [pkg, ...]}."""
    text = path.read_text(errors="replace")
    out: dict[str, list[str]] = {}
    for m in DEP_FIELD_PAT.finditer(text):
        field = m.group(1)
        body = m.group(2)
        # split on commas, strip version constraints and whitespace
        names = []
        for chunk in body.split(","):
            name = chunk.strip().split("(")[0].strip()
            name = re.sub(r"\s+", "", name)
            if name and name != "R":   # `Depends: R(>=3.6)` → skip R itself
                names.append(name)
        out[field] = names
    return out


# ----------------------------------------------------------------------------- #
# Output                                                                        #
# ----------------------------------------------------------------------------- #

def report_check(name: str, repos: list[dict]) -> str:
    matches = match_r_package(name, repos)
    out = [f"## Discovery — `{name}`", ""]
    if not matches:
        out.append(f"**No existing {ORG_NAME} port found.** Safe to start a new port.")
    else:
        out.append(f"**{len(matches)} match(es)** under `github.com/{ORG_NAME}`:")
        out.append("")
        out.append("| Repo | Description | Last update |")
        out.append("|---|---|---|")
        for m in matches:
            desc = (m.get("description") or "").replace("|", "\\|")
            up = (m.get("updatedAt") or "").split("T", 1)[0]
            out.append(f"| [`{m['name']}`](https://github.com/{ORG_NAME}/{m['name']}) | {desc} | {up} |")
    return "\n".join(out)


def report_dependencies(
    desc_path: Path,
    repos: list[dict],
    skip_suggests: bool = True,
) -> str:
    """Walk an R DESCRIPTION's deps; report which already have py- ports."""
    fields = parse_description(desc_path)
    out = [
        f"## Discovery — dependencies of `{desc_path.parent.name}`",
        "",
        f"Reusing {ORG_NAME}-org Python ports avoids duplicating upstream work.",
        "",
    ]

    for field in ("Imports", "Depends", "LinkingTo", "Suggests"):
        if skip_suggests and field == "Suggests":
            continue
        deps = fields.get(field, [])
        if not deps:
            continue
        out.append(f"### {field}\n")
        out.append(f"| R dep | {ORG_NAME} match | Description |")
        out.append("|---|---|---|")
        for dep in deps:
            matches = match_r_package(dep, repos)
            if not matches:
                out.append(f"| `{dep}` | — | (none) |")
            else:
                links = []
                descs = []
                for m in matches[:2]:    # show at most 2 per dep
                    links.append(f"[`{m['name']}`](https://github.com/{ORG_NAME}/{m['name']})")
                    desc = (m.get("description") or "").replace("|", "\\|")
                    descs.append(desc[:80] + ("…" if len(desc) > 80 else ""))
                out.append(f"| `{dep}` | {' / '.join(links)} | {'; '.join(descs)} |")
        out.append("")

    # Summary action items
    out.append("### Action items\n")
    found_count = sum(
        1
        for field in ("Imports", "Depends", "LinkingTo")
        for dep in fields.get(field, [])
        if match_r_package(dep, repos)
    )
    total_count = sum(
        len(fields.get(f, [])) for f in ("Imports", "Depends", "LinkingTo")
    )
    out.append(f"- **{found_count}** of **{total_count}** R Imports/Depends/LinkingTo "
               f"have a {ORG_NAME}-org Python mirror.")
    out.append(f"- Add each match to `pyproject.toml::dependencies`.")
    out.append(f"- For deps **without** a mirror: either pure-Python equivalent in "
               f"scipy/sklearn/statsmodels, OR scope as a future {ORG_NAME} port.")

    return "\n".join(out)


# ----------------------------------------------------------------------------- #
# CLI                                                                           #
# ----------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", metavar="R_PKG",
                    help="Check if a single R package is already ported.")
    ap.add_argument("--description", metavar="PATH", type=Path,
                    help="Path to an R DESCRIPTION; audit all its deps.")
    ap.add_argument("--refresh", action="store_true",
                    help="Force refresh of the omicverse repo cache.")
    ap.add_argument("--output", metavar="PATH", type=Path,
                    help="Write report to this file (default stdout).")
    args = ap.parse_args()

    if not args.check and not args.description:
        ap.error("Pass --check <R_pkg> or --description <DESCRIPTION>")

    repos = fetch_omicverse_repos(force_refresh=args.refresh)

    if args.check:
        report = report_check(args.check, repos)
    else:
        report = report_dependencies(args.description, repos)

    if args.output:
        args.output.write_text(report)
        print(f"[discover] wrote {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
