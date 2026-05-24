"""Wall-clock benchmarking with warmup-exclusion + 3-run averaging.

Used by:
- the Acceleration Agent, to time each iteration
- engine/loop.py, to populate ITERATION_LOG.md entries

The convention (per EVALUATION.md):
1. Lock BLAS thread count via env vars BEFORE importing numpy/scipy.
2. Run the target once as warmup → discard.
3. Run it 3 more times → record `wall_clock_runs_s`.
4. Report mean and stddev.
5. If stddev > 10% of mean, re-run 5×, report median + IQR.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


# ----------------------------------------------------------------------------- #
# Environment locks (call BEFORE importing numpy/scipy in the candidate process)
# ----------------------------------------------------------------------------- #

def lock_blas_threads(n: int = 8) -> None:
    """Pin BLAS thread pools to a known size so timings are reproducible.

    Must be called before any numpy/scipy import. In a subprocess-launching
    benchmark, set these env vars on the subprocess Popen, not in the host.
    """
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[key] = str(n)


# ----------------------------------------------------------------------------- #
# Result container
# ----------------------------------------------------------------------------- #

@dataclass
class TimingResult:
    """Mirrors the YAML schema in ITERATION_LOG.template.md."""
    warmup_run_s: float
    wall_clock_runs_s: list[float] = field(default_factory=list)

    @property
    def mean_s(self) -> float:
        return float(statistics.mean(self.wall_clock_runs_s))

    @property
    def stddev_s(self) -> float:
        return (
            float(statistics.stdev(self.wall_clock_runs_s))
            if len(self.wall_clock_runs_s) >= 2
            else 0.0
        )

    @property
    def median_s(self) -> float:
        return float(statistics.median(self.wall_clock_runs_s))

    @property
    def cv(self) -> float:
        m = self.mean_s
        return self.stddev_s / m if m > 0 else 0.0

    def to_yaml_block(self) -> dict:
        block = {
            "warmup_run_s": round(self.warmup_run_s, 4),
            "wall_clock_runs_s": [round(t, 4) for t in self.wall_clock_runs_s],
            "wall_clock_mean_s": round(self.mean_s, 4),
            "wall_clock_stddev_s": round(self.stddev_s, 4),
        }
        if self.cv > 0.10:
            block["wall_clock_median_s"] = round(self.median_s, 4)
            block["high_variance_warning"] = (
                f"CV={self.cv:.1%} > 10% — consider re-running 5× and using median"
            )
        return block

    def to_human(self) -> str:
        return f"{self.mean_s:.3f}s ± {self.stddev_s:.3f}s  (warmup {self.warmup_run_s:.3f}s)"


# ----------------------------------------------------------------------------- #
# In-process timing (for code that can be called as a Python function)         #
# ----------------------------------------------------------------------------- #

def time_callable(
    fn: Callable,
    *args,
    warmup_runs: int = 1,
    measured_runs: int = 3,
    high_var_runs: int = 5,
    high_var_threshold: float = 0.10,
    **kwargs,
) -> TimingResult:
    """Time `fn(*args, **kwargs)` per the EVALUATION.md convention.

    Returns:
        TimingResult with `warmup_run_s` and `wall_clock_runs_s = [t1, t2, t3]`.
        If CV > high_var_threshold, re-runs to `high_var_runs` and reports median.
    """
    # Warmup
    t0 = time.perf_counter()
    for _ in range(warmup_runs):
        _ = fn(*args, **kwargs)
    warmup_s = time.perf_counter() - t0

    # Measured runs
    runs: list[float] = []
    for _ in range(measured_runs):
        t0 = time.perf_counter()
        _ = fn(*args, **kwargs)
        runs.append(time.perf_counter() - t0)

    result = TimingResult(warmup_run_s=warmup_s, wall_clock_runs_s=runs)

    # High-variance auto-retry
    if result.cv > high_var_threshold and measured_runs < high_var_runs:
        extra = high_var_runs - measured_runs
        for _ in range(extra):
            t0 = time.perf_counter()
            _ = fn(*args, **kwargs)
            runs.append(time.perf_counter() - t0)
        result = TimingResult(warmup_run_s=warmup_s, wall_clock_runs_s=runs)

    return result


# ----------------------------------------------------------------------------- #
# Subprocess timing (for running the candidate runner script)                  #
# ----------------------------------------------------------------------------- #

def time_subprocess(
    cmd: Sequence[str],
    cwd: Path | None = None,
    env: dict | None = None,
    warmup_runs: int = 1,
    measured_runs: int = 3,
) -> TimingResult:
    """Time a subprocess invocation per the EVALUATION.md convention.

    Use this for the canonical workflow: `python tests/_run_candidate.py …`
    invoked under a specific conda env. The first run also pays
    process-start + Python-import overhead; that's why we discard it.
    """
    def _one_run():
        t0 = time.perf_counter()
        subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True)
        return time.perf_counter() - t0

    warmup_s = _one_run()
    runs = [_one_run() for _ in range(measured_runs)]
    return TimingResult(warmup_run_s=warmup_s, wall_clock_runs_s=runs)


# ----------------------------------------------------------------------------- #
# Self-test                                                                    #
# ----------------------------------------------------------------------------- #

if __name__ == "__main__":
    import math
    def workload(n=200000):
        s = 0.0
        for i in range(n):
            s += math.sqrt(i)
        return s

    r = time_callable(workload, n=200000)
    print(f"Workload: {r.to_human()}")
    print(f"YAML block: {r.to_yaml_block()}")
