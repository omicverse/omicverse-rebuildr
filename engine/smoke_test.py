"""Smoke test for a fresh `omicverse-rebuildr` install.

Verifies that:
1. All engine modules import cleanly (no missing Python deps).
2. The 8 parity metrics from `parity_metrics.py` compute correctly on toy inputs.
3. `benchmark.time_callable` works.
4. `r_function_audit` parses a tiny synthetic NAMESPACE.
5. `plot_evolution` parses a tiny synthetic ITERATION_LOG.

Does NOT test:
- gh CLI auth (run `gh auth status` separately)
- conda env paths (run `conda info --envs` separately)
- R installation (run `Rscript --version` separately)
- internet access (the omicverse-repo cache is mocked here)

Usage:
    python -m engine.smoke_test          # from omicverse-rebuildr/
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def check(name: str, fn) -> bool:
    try:
        fn()
        print(f"  [PASS] {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return False


# --- 1. imports --------------------------------------------------------------

def t_imports():
    import parity_metrics  # noqa
    import benchmark  # noqa
    import r_function_audit  # noqa
    import plot_evolution  # noqa
    import discover_omicverse_deps  # noqa
    import loop  # noqa


# --- 2. parity metrics -------------------------------------------------------

def t_parity_metrics():
    import numpy as np
    from parity_metrics import compute_parity, is_pass, default_threshold, VALID_CLASSES

    assert len(VALID_CLASSES) == 8, f"expected 8 algorithm classes, got {len(VALID_CLASSES)}"

    rng = np.random.default_rng(42)

    # deterministic — bit-equivalent
    a = rng.normal(0, 1, 100); b = a + 1e-15
    m = compute_parity(a, b, "deterministic"); assert is_pass(m, "deterministic"), m

    # stochastic — same distribution
    a = rng.normal(0, 1, 200); b = rng.normal(0, 1, 200)
    m = compute_parity(a, b, "stochastic"); assert is_pass(m, "stochastic"), m

    # clustering — identical labels
    la = rng.integers(0, 3, 50); lb = la.copy()
    m = compute_parity(la, lb, "clustering"); assert m == 1.0, m

    # embedding — rotation
    M = rng.normal(0, 1, (40, 3))
    Q = np.linalg.qr(rng.normal(0, 1, (3, 3)))[0]
    m = compute_parity(M, M @ Q, "embedding"); assert is_pass(m, "embedding"), m

    # ordinal — perfect correlation
    x = np.arange(50.0); y = 2 * x + 3
    m = compute_parity(x, y, "ordinal"); assert m > 0.999, m

    # classification — identical
    y = rng.integers(0, 2, 100)
    m = compute_parity(y, y, "classification"); assert m == 1.0, m

    # ranked — same top-K
    a = list(range(50)); b = list(range(50))
    m = compute_parity(a, b, "ranked"); assert m == 1.0, m

    # inference — identical p-values
    p = np.clip(rng.uniform(0, 1, 80), 1e-10, 1)
    m = compute_parity(p, p, "inference")
    assert m["spearman_neglog10p"] > 0.99 and m["top50_jaccard"] == 1.0, m

    # default_threshold returns a sensible float for every class
    for c in VALID_CLASSES:
        t = default_threshold(c)
        assert isinstance(t, float), (c, t)


# --- 3. benchmark ------------------------------------------------------------

def t_benchmark():
    from benchmark import time_callable
    def workload():
        return sum(i * i for i in range(10_000))
    r = time_callable(workload, warmup_runs=1, measured_runs=3)
    assert len(r.wall_clock_runs_s) == 3
    assert r.mean_s > 0


# --- 4. r_function_audit on a synthetic upstream -----------------------------

def t_r_function_audit():
    from r_function_audit import audit

    with tempfile.TemporaryDirectory() as tmp:
        ref = Path(tmp) / "ref"; ref.mkdir()
        (ref / "NAMESPACE").write_text(textwrap.dedent("""\
            export(foo)
            export(barBaz)
        """))
        rdir = ref / "R"; rdir.mkdir()
        (rdir / "code.R").write_text(textwrap.dedent("""\
            foo <- function(x) x + 1
            barBaz <- function(y) foo(y) * 2
            internal_helper <- function() NULL
        """))

        py = Path(tmp) / "pypkg"; py.mkdir()
        (py / "core.py").write_text(textwrap.dedent("""\
            def foo(x): return x + 1
            def bar_baz(y): return foo(y) * 2
        """))

        report = audit(ref, py)
        n_ported = report["totals"]["exported_ported"]
        n_total = report["totals"]["exported"]
        assert n_total == 2, n_total
        assert n_ported >= 1, n_ported  # foo definitely; barBaz depends on heuristic


# --- 5. plot_evolution parses a tiny synthetic log ---------------------------

def t_plot_evolution():
    from plot_evolution import parse_log

    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "ITERATION_LOG.md"
        log.write_text(textwrap.dedent("""\
            # Acceleration Iteration Log — py-Demo

            ## Baseline — 2026-01-01 00:00:00

            ```yaml
            iter: 0
            status: baseline
            wall_clock_mean_s: 1.0
            wall_clock_stddev_s: 0.0
            parity_metric: 1.0
            parity_passes: true
            ```

            ## iter 1 — 2026-01-01 00:01:00

            ```yaml
            iter: 1
            status: ACCEPT
            action: skip_uv
            playbook_section: "section-1.5"
            admissibility: exact
            wall_clock_mean_s: 0.5
            wall_clock_stddev_s: 0.01
            parity_metric: 1.0
            parity_passes: true
            ```
        """))
        entries = parse_log(log)
        assert len(entries) == 2, len(entries)
        assert entries[0].status == "baseline"
        assert entries[1].action == "skip_uv"


def main() -> int:
    print("[smoke] Running omicverse-rebuildr engine smoke test...\n")
    results = [
        check("1. all engine modules import",          t_imports),
        check("2. 8 parity metrics compute correctly", t_parity_metrics),
        check("3. benchmark.time_callable works",      t_benchmark),
        check("4. r_function_audit parses NAMESPACE",  t_r_function_audit),
        check("5. plot_evolution parses ITERATION_LOG", t_plot_evolution),
    ]
    n_pass = sum(results)
    n_total = len(results)
    print()
    if n_pass == n_total:
        print(f"[smoke] OK -- {n_pass}/{n_total} checks passed. Kit is installed and runnable.")
        print("[smoke] Still to verify manually:")
        print("        - `gh auth status`  (Discovery step needs GitHub auth)")
        print("        - $PYTHON_TEST_ENV / $R_TEST_ENV exported")
        print("        - `Rscript --version` and `jupyter nbconvert --version`")
        return 0
    print(f"[smoke] FAIL -- {n_pass}/{n_total} checks passed.")
    print("[smoke] Re-check `pip install -r requirements.txt` in your Python env.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
