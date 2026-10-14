"""R-function-coverage audit — verifies the Python port covers every
upstream R-exported function.

Parses:
1. `<pkg>-ref/NAMESPACE` to get the list of exported functions.
2. `<pkg>-ref/R/*.R` to find internal helpers reachable from exports.

Then checks the Python package (`<pkgname>/*.py`) for matching function names,
applying snake_case normalization. Produces a markdown table for §2 of
RECONSTRUCTION_REPORT.md and, optionally, the `port.yaml` manifest consumed by
the omicverse.org R-port catalog (https://omicverse.org/ports.html).

Usage:
    python -m engine.r_function_audit \
        --r-source <pkg>-ref/ \
        --py-package <pkgname>/ \
        --output AUDIT.md \
        --port-yaml port.yaml          # write / refresh the catalog manifest

`--port-yaml` is idempotent: when `port.yaml` already exists its hand-written
fields (notes, parity, tests, aliases, skipped/partial statuses, upstream
metadata) are preserved; only newly discovered R exports are appended and
`planned` entries are promoted to `ported` once a Python match appears.
"""

from __future__ import annotations

import argparse
import datetime as _dt
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


def parse_description(r_source: Path) -> dict:
    """Package / Version / License / URL from the upstream DESCRIPTION (if present)."""
    desc = r_source / "DESCRIPTION"
    out: dict = {}
    if not desc.exists():
        return out
    cur_key = None
    for line in desc.read_text(errors="replace").splitlines():
        if re.match(r"^[A-Za-z][A-Za-z0-9/_.-]*:", line):
            cur_key, _, val = line.partition(":")
            out[cur_key.strip()] = val.strip()
        elif cur_key and line[:1].isspace():
            out[cur_key] = (out[cur_key] + " " + line.strip()).strip()
    return out


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


def parse_pyproject(path: Path) -> dict:
    """name / version / license / import name from pyproject.toml (regex; no tomllib dependency)."""
    out: dict = {}
    if not path.exists():
        return out
    text = path.read_text(errors="replace")
    m = re.search(r"^\s*name\s*=\s*\"([^\"]+)\"", text, re.M)
    out["pypi"] = m.group(1) if m else None
    m = re.search(r"^\s*version\s*=\s*\"([^\"]+)\"", text, re.M)
    out["version"] = m.group(1) if m else None
    m = re.search(r"^\s*license\s*=\s*(?:\{\s*text\s*=\s*)?\"([^\"]+)\"", text, re.M)
    out["license"] = m.group(1) if m else None
    m = re.search(r"^\s*(?:packages|include)\s*=\s*\[\s*\"([A-Za-z_][A-Za-z0-9_]*)\*?\"", text, re.M)
    out["import_name"] = m.group(1) if m else None
    return out


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
# port.yaml (omicverse.org catalog manifest)                                   #
# ----------------------------------------------------------------------------- #

PORT_SCHEMA = "omicverse-port/v1"
PORT_KEY_ORDER = (
    "schema", "package", "pypi", "import_name", "language", "domain",
    "upstream", "omicverse", "parity", "artifacts", "functions", "classes",
)
# Hand-written per-function fields that a refresh must never clobber.
_KEEP_FN_FIELDS = ("aliases", "parity", "note", "test")


def _blank_port(meta: dict) -> dict:
    return {
        "schema": PORT_SCHEMA,
        "package": meta.get("package"),
        "pypi": meta.get("pypi"),
        "import_name": meta.get("import_name"),
        "language": meta.get("language", "python"),
        "domain": meta.get("domain", "other"),
        "upstream": {
            "name": meta.get("upstream_name"),
            "source": meta.get("upstream_source"),
            "version": meta.get("upstream_version"),
            "url": meta.get("upstream_url"),
            "license": meta.get("upstream_license"),
            "citation": None,
        },
        "omicverse": {"module": None, "since": None},
        "parity": {
            "status": "unverified",
            "algorithm_class": meta.get("algorithm_class"),
            "metric": meta.get("metric"),
            "threshold": meta.get("threshold"),
            "value": None,
            "fixture": meta.get("fixture"),
            "test": "tests/test_exact_match.py",
        },
        "artifacts": {
            "audit": "AUDIT.md",
            "report": "RECONSTRUCTION_REPORT.md",
            "compare_notebook": "examples/compare_R_vs_Python.ipynb",
            "function_notebook": "examples/function_by_function_R_parity.ipynb",
        },
        "functions": [],
        "classes": [],
    }


def build_port_yaml(report: dict, existing: dict | None, meta: dict) -> tuple[dict, dict]:
    """Merge the audit result into `existing` (or a fresh manifest).

    Returns (manifest, stats) where stats = {added, promoted, kept, total}.
    """
    data = dict(existing) if existing else _blank_port(meta)
    data.setdefault("schema", PORT_SCHEMA)
    for k, v in _blank_port(meta).items():
        if k not in data or data[k] is None:
            data[k] = v
        elif isinstance(v, dict) and isinstance(data[k], dict):
            for kk, vv in v.items():
                data[k].setdefault(kk, vv)
    # fill upstream fields that are still empty from DESCRIPTION / pyproject
    up = data["upstream"]
    for key in ("name", "source", "version", "url", "license"):
        if not up.get(key) and meta.get(f"upstream_{key}"):
            up[key] = meta[f"upstream_{key}"]
    for key in ("pypi", "import_name"):
        if not data.get(key) and meta.get(key):
            data[key] = meta[key]

    import_name = data.get("import_name")
    by_r = {str(f.get("r")): f for f in data.get("functions") or [] if isinstance(f, dict) and f.get("r")}
    stats = {"added": 0, "promoted": 0, "kept": 0}
    for row in report["exports"]:
        py_path = f"{import_name}.{row['py']}" if (row["py"] and import_name) else row["py"]
        entry = by_r.get(row["r"])
        if entry is None:
            entry = {
                "r": row["r"],
                "py": py_path,
                "status": "ported" if row["py"] else "planned",
                "parity": None,
                "note": None,
            }
            data["functions"].append(entry)
            by_r[row["r"]] = entry
            stats["added"] += 1
            continue
        # existing entry: never downgrade a hand-set status; fill gaps only
        if not entry.get("py") and py_path:
            entry["py"] = py_path
        if entry.get("status") in (None, "planned") and row["py"]:
            entry["status"] = "ported"
            stats["promoted"] += 1
        else:
            stats["kept"] += 1
        for key in _KEEP_FN_FIELDS:
            entry.setdefault(key, None if key != "aliases" else [])
    # drop empty optional keys for a tidy file
    for f in data["functions"]:
        for key in list(f):
            if f[key] in (None, [], "") and key not in ("r", "py", "status"):
                del f[key]
    stats["total"] = len(data["functions"])
    ordered = {k: data[k] for k in PORT_KEY_ORDER if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered})
    return ordered, stats


def dump_port_yaml(data: dict, path: Path, meta: dict) -> None:
    try:
        import yaml  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("--port-yaml needs PyYAML: pip install pyyaml") from e
    header = (
        "# port.yaml — machine-readable manifest read by omicverse.org/ports\n"
        "# Spec: https://github.com/omicverse/omicverse-org-home/blob/main/docs/PORT_MANIFEST.md\n"
        f"# functions[] refreshed by `python -m engine.r_function_audit --port-yaml` on {_dt.date.today().isoformat()};\n"
        "# hand-written fields (notes, parity, tests, aliases, skipped/partial statuses) are preserved on refresh.\n"
    )
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
    path.write_text(header + body)


def load_port_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    import yaml  # type: ignore
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"{path} is not a YAML mapping")
    return data


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
    ap.add_argument("--port-yaml", type=Path, default=None,
                    help="Write / refresh the omicverse.org catalog manifest at this path (usually port.yaml)")
    ap.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"),
                    help="pyproject.toml used to fill pypi / import_name (default: ./pyproject.toml)")
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.yaml"),
                    help="pre-registered parity gate used to fill parity.* (default: data/manifest.yaml)")
    ap.add_argument("--package", default=None, help="repo name, e.g. py-DoubletFinder (default: cwd name)")
    ap.add_argument("--domain", default=None,
                    help="single-cell | spatial | trajectory | bulk | proteomics | metabolomics | genetics | "
                         "immune | microbiome | hic | stats | visualization | other")
    ap.add_argument("--upstream-source", default=None, help="CRAN | Bioconductor | GitHub | other")
    ap.add_argument("--upstream-url", default=None)
    args = ap.parse_args()

    report = audit(args.r_source, args.py_package)
    md = to_markdown(report)
    if args.output:
        args.output.write_text(md)
        print(f"[audit] wrote {args.output}")
    else:
        print(md)

    if args.port_yaml:
        desc = parse_description(args.r_source)
        pp = parse_pyproject(args.pyproject)
        meta = {
            "package": args.package or Path.cwd().name,
            "pypi": pp.get("pypi"),
            "import_name": pp.get("import_name") or args.py_package.name,
            "language": "python",
            "domain": args.domain or "other",
            "upstream_name": desc.get("Package"),
            "upstream_version": desc.get("Version"),
            "upstream_license": desc.get("License"),
            "upstream_source": args.upstream_source,
            "upstream_url": args.upstream_url or (desc.get("URL") or "").split(",")[0].strip() or None,
        }
        if args.manifest.exists():
            try:
                import yaml  # type: ignore
                man = yaml.safe_load(args.manifest.read_text()) or {}
                meta["algorithm_class"] = man.get("algorithm_class")
                meta["threshold"] = man.get("parity_threshold")
                outs = man.get("outputs") or []
                if outs and isinstance(outs[0], dict):
                    meta["metric"] = outs[0].get("metric")
                    meta["threshold"] = outs[0].get("threshold", meta["threshold"])
                fx = man.get("fixture")
                if isinstance(fx, dict):
                    meta["fixture"] = fx.get("description")
                mu = man.get("upstream")
                if isinstance(mu, dict):
                    meta["upstream_name"] = meta["upstream_name"] or mu.get("name")
                    meta["upstream_version"] = meta["upstream_version"] or (str(mu["version"]) if mu.get("version") else None)
                    src = str(mu.get("source") or "")
                    if src and not src.startswith("http"):
                        meta["upstream_source"] = meta["upstream_source"] or src
                    elif src:
                        meta["upstream_url"] = meta["upstream_url"] or src
            except Exception as e:  # noqa: BLE001
                print(f"[audit] warning: could not read {args.manifest}: {e}")
        existing = load_port_yaml(args.port_yaml)
        data, stats = build_port_yaml(report, existing, meta)
        dump_port_yaml(data, args.port_yaml, meta)
        verb = "refreshed" if existing else "wrote"
        print(f"[audit] {verb} {args.port_yaml}: {stats['total']} functions "
              f"(+{stats['added']} new, {stats['promoted']} promoted to ported, {stats['kept']} kept)")


if __name__ == "__main__":
    main()
