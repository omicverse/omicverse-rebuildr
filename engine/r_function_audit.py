"""R-function-coverage audit — verifies the Python port covers every
upstream R-exported function.

Parses:
1. `<pkg>-ref/NAMESPACE` to get the list of exported functions.
2. `<pkg>-ref/R/*.R` to find internal helpers reachable from exports.

Then checks the Python package (`<pkgname>/*.py`) for matching function names,
applying snake_case normalization. Produces a markdown table for §2 of
RECONSTRUCTION_REPORT.md.

Usage:
    python -m engine.r_function_audit \
        --r-source <pkg>-ref/ \
        --py-package <pkgname>/ \
        --output AUDIT.md
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path


# ----------------------------------------------------------------------------- #
# NAMESPACE parsing                                                            #
# ----------------------------------------------------------------------------- #

EXPORT_PATTERNS = (
    re.compile(r"^\s*export\(\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*\)", re.M),
    # exportPattern("^abc.*") — rare; we ignore it (audit by hand if used)
    re.compile(r"^\s*S3method\(\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*,", re.M),
    re.compile(r"^\s*exportMethods\(\s*([A-Za-z_.][A-Za-z0-9_.]*)", re.M),
    re.compile(r"^\s*exportClasses\(\s*([A-Za-z_.][A-Za-z0-9_.]*)", re.M),
)


def parse_namespace(ns_path: Path) -> set[str]:
    """Return the set of exported names from R's NAMESPACE file."""
    if not ns_path.exists():
        raise FileNotFoundError(f"No NAMESPACE at {ns_path}")
    text = ns_path.read_text()
    exports: set[str] = set()
    for pat in EXPORT_PATTERNS:
        exports.update(pat.findall(text))
    return exports


# ----------------------------------------------------------------------------- #
# R source parsing                                                             #
# ----------------------------------------------------------------------------- #

R_DEF_PAT = re.compile(
    r"^\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*(?:<-|=)\s*function\s*\(",
    re.M,
)
R_CALL_PAT = re.compile(r"\b([A-Za-z_.][A-Za-z0-9_.]*)\s*\(")


def parse_r_source(r_dir: Path) -> dict:
    """Return: {fn_name: {file: str, calls: set[str]}}.

    Heuristic — works for ~95% of CRAN/Bioc package layouts. Will miss
    functions assigned via `assign()`, dynamic dispatch, S4 setMethod, etc.
    """
    defs: dict[str, dict] = {}
    for r_file in sorted(r_dir.glob("*.R")):
        text = r_file.read_text(errors="replace")
        for m in R_DEF_PAT.finditer(text):
            name = m.group(1)
            body_start = m.end()
            # Crude: take the rest of the file from the definition; good enough
            # to find called names. (R functions can span hundreds of lines and
            # full parsing would require an R AST.)
            body = text[body_start:]
            # Stop at the next top-level function definition
            next_def = R_DEF_PAT.search(body, pos=1)
            if next_def is not None:
                body = body[: next_def.start()]
            calls = set(R_CALL_PAT.findall(body))
            calls.discard(name)
            defs[name] = {"file": r_file.name, "calls": calls}
    return defs


def reachable_helpers(
    exports: set[str],
    defs: dict,
) -> set[str]:
    """BFS from exports through call graph, restricted to in-package names."""
    in_pkg = set(defs)
    visited: set[str] = set()
    frontier = list(in_pkg & exports)
    while frontier:
        cur = frontier.pop()
        if cur in visited:
            continue
        visited.add(cur)
        if cur not in defs:
            continue
        for callee in defs[cur]["calls"]:
            if callee in in_pkg and callee not in visited:
                frontier.append(callee)
    return visited


# ----------------------------------------------------------------------------- #
# Python package parsing                                                       #
# ----------------------------------------------------------------------------- #

PY_DEF_PAT = re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)
PY_CLASS_METHOD_PAT = re.compile(r"^\s{4}def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.M)
# Module-level aliases (`old_name = new_name`) are a normal way to expose a
# second spelling of a ported function -- e.g. the literal transliteration of an
# R name alongside the idiomatic Python one. Without this, such aliases
# false-negative in the coverage table.
PY_ALIAS_PAT = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[A-Za-z_][A-Za-z0-9_.]*\s*(?:#.*)?$", re.M)


def parse_py_package(py_dir: Path) -> set[str]:
    """Return the set of top-level + class-method function names in the Python port."""
    names: set[str] = set()
    for py_file in sorted(py_dir.rglob("*.py")):
        if any(part.startswith(".") for part in py_file.parts):
            continue
        text = py_file.read_text(errors="replace")
        names.update(PY_DEF_PAT.findall(text))
        names.update(PY_CLASS_METHOD_PAT.findall(text))
        names.update(PY_ALIAS_PAT.findall(text))
    return names


def r_name_to_py_candidates(r_name: str) -> list[str]:
    """Generate plausible Python-style equivalents for an R name."""
    # camelCase → snake_case
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", r_name).lower()
    # acronym-aware camelCase → snake_case: keep runs of capitals together, so
    # SNF2 → snf2, PreprocessST → preprocess_st, NMFGenerateW → nmf_generate_w.
    # Without this, every R name containing an acronym false-negatives.
    acr = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", r_name)
    acr = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", acr).lower()
    acr_nodigit = re.sub(r"_(?=\d)", "", acr)
    # dot → underscore
    snake_dot = r_name.replace(".", "_")
    # numeric suffix _v3 etc.
    no_suffix = re.sub(r"_v\d+$", "", snake)
    return list({r_name, r_name.lower(), snake, acr, acr_nodigit, snake_dot,
                 no_suffix, snake.replace(".", "_"), acr.replace(".", "_")})


# ----------------------------------------------------------------------------- #
# Report                                                                       #
# ----------------------------------------------------------------------------- #

def audit(
    r_source: Path,
    py_package: Path,
) -> dict:
    namespace = r_source / "NAMESPACE"
    r_dir = r_source / "R"
    exports = parse_namespace(namespace)
    defs = parse_r_source(r_dir)
    reachable = reachable_helpers(exports, defs)
    internal = reachable - exports

    py_names = parse_py_package(py_package)

    rows_exported = []
    for r_fn in sorted(exports):
        cands = r_name_to_py_candidates(r_fn)
        matched = next((c for c in cands if c in py_names), None)
        rows_exported.append(
            {
                "r": r_fn,
                "py": matched,
                "status": "ported" if matched else "MISSING",
                "candidates_checked": cands,
            }
        )

    rows_internal = []
    for r_fn in sorted(internal):
        cands = r_name_to_py_candidates(r_fn)
        matched = next((c for c in cands if c in py_names), None)
        rows_internal.append(
            {
                "r": r_fn,
                "py": matched,
                "status": "ported" if matched else "missing-or-inlined",
                "file": defs.get(r_fn, {}).get("file", "?"),
            }
        )

    return {
        "exports": rows_exported,
        "internal": rows_internal,
        "totals": {
            "exported": len(exports),
            "exported_ported": sum(1 for r in rows_exported if r["status"] == "ported"),
            "internal_reachable": len(internal),
            "internal_ported": sum(1 for r in rows_internal if r["status"] == "ported"),
            "py_names": len(py_names),
        },
    }


def to_markdown(report: dict) -> str:
    t = report["totals"]
    out: list[str] = []
    out.append("## R function coverage audit\n")
    out.append("### Coverage summary\n")
    out.append("| Category | Ported | Total | % |\n|---|---|---|---|")
    out.append(
        f"| Exported R functions | {t['exported_ported']} | {t['exported']} | "
        f"{(100*t['exported_ported']/max(t['exported'],1)):.1f}% |"
    )
    out.append(
        f"| Internal helpers (reachable) | {t['internal_ported']} | {t['internal_reachable']} | "
        f"{(100*t['internal_ported']/max(t['internal_reachable'],1)):.1f}% |"
    )
    out.append(f"\n_Python package exposes {t['py_names']} unique names._\n")

    out.append("### Exported R functions\n")
    out.append("| R function | Python equivalent | Status |\n|---|---|---|")
    for r in report["exports"]:
        emoji = "✅" if r["status"] == "ported" else "❌"
        py = r["py"] or "—"
        out.append(f"| `{r['r']}` | `{py}` | {emoji} {r['status']} |")

    out.append("\n### Internal helpers reachable from exports\n")
    out.append("| R helper | File | Python equivalent | Status |\n|---|---|---|---|")
    for r in report["internal"]:
        emoji = "✅" if r["status"] == "ported" else "🔸"
        py = r["py"] or "—"
        out.append(f"| `{r['r']}` | `{r['file']}` | `{py}` | {emoji} {r['status']} |")

    out.append("")
    return "\n".join(out)


# ----------------------------------------------------------------------------- #
# CLI                                                                          #
# ----------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--r-source", required=True, type=Path,
                    help="Path to the cloned upstream R package directory (containing NAMESPACE + R/)")
    ap.add_argument("--py-package", required=True, type=Path,
                    help="Path to the Python module directory (containing *.py)")
    ap.add_argument("--output", type=Path, default=None,
                    help="Write the markdown report to this file (default: stdout)")
    args = ap.parse_args()

    report = audit(args.r_source, args.py_package)
    md = to_markdown(report)
    if args.output:
        args.output.write_text(md)
        print(f"[audit] wrote {args.output}")
    else:
        print(md)


if __name__ == "__main__":
    main()
