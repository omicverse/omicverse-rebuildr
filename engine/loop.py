"""The Omicverse-RebuildR loop, as runnable code.

This is the explicit, runnable form of the two-agent inner loop described
in PROTOCOL.md §3. It is the **structure** the LLM coding agent fills in —
not an autonomous orchestrator. Each step is a callable hook that the agent
implements while iterating in a coding-agent session.

Why expose this as code at all? Because committing the loop's shape to a
Python module makes it inspectable, testable, and reproducible across
ports — instead of re-deriving the same workflow from a markdown doc.

Run as a CLI to score an in-progress port against its manifest:

    python -m omicverse_rebuild.engine.loop \
        --port-dir <path-to-your-port>/py-<pkg> \
        --phase equivalence | acceleration | release

The agent calls the same functions from within its tool-use loop.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import yaml

# Local import (this file lives in engine/ next to parity_metrics.py)
sys.path.insert(0, str(Path(__file__).parent))
from parity_metrics import compute_parity, is_pass  # noqa: E402


# ----------------------------------------------------------------------------- #
# Data classes                                                                  #
# ----------------------------------------------------------------------------- #

@dataclasses.dataclass
class Manifest:
    package: str
    upstream: dict
    algorithm_class: str
    parity_threshold: float
    fixture_path: str
    reference_command: str
    seed: int
    outputs: list
    acceleration_enabled: bool

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls(
            package=raw["package"],
            upstream=raw["upstream"],
            algorithm_class=raw["algorithm_class"],
            parity_threshold=raw["parity_threshold"],
            fixture_path=raw["fixture"]["path"],
            reference_command=raw["reference_command"],
            seed=raw["seed"],
            outputs=raw.get("outputs", []),
            acceleration_enabled=raw.get("acceleration", {}).get("enabled", True),
        )


@dataclasses.dataclass
class TrialResult:
    """One Equivalence- or Acceleration-Agent attempt."""
    label: str
    metric_value: Any
    passed: bool
    wall_clock_s: float
    notes: str = ""

    def __str__(self) -> str:
        passmark = "PASS" if self.passed else "FAIL"
        return (
            f"[{passmark}] {self.label}: "
            f"metric={self.metric_value} "
            f"time={self.wall_clock_s:.2f}s "
            f"{self.notes}"
        )


# ----------------------------------------------------------------------------- #
# Phase implementations                                                         #
# ----------------------------------------------------------------------------- #

def run_r_reference(
    manifest: Manifest,
    port_dir: Path,
    r_conda_env: str = os.environ.get("R_TEST_ENV", "/path/to/your/R/env"),
) -> Path:
    """Invoke the R reference runner; return the path to reference_output.json."""
    ref_script = port_dir / manifest.reference_command
    fixture = port_dir / manifest.fixture_path
    out_path = port_dir / "data" / "reference_output.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "conda", "run", "-p", r_conda_env,
        "Rscript", str(ref_script),
        str(fixture),
        str(out_path),
    ]
    print(f"[ref] {' '.join(cmd)}")
    t0 = time.time()
    subprocess.run(cmd, check=True)
    print(f"[ref] done in {time.time() - t0:.2f}s -> {out_path}")
    return out_path


def run_candidate(
    manifest: Manifest,
    port_dir: Path,
    py_conda_env: str = os.environ.get("PYTHON_TEST_ENV", "/path/to/your/python/env"),
) -> Path:
    """Invoke the candidate Python port on the same fixture.

    The candidate must produce candidate_output.json with the same JSON-path
    keys as the reference (see manifest.outputs[*].location_reference /
    .location_candidate).
    """
    candidate_script = port_dir / "tests" / "_run_candidate.py"
    if not candidate_script.exists():
        raise FileNotFoundError(
            f"Expected candidate runner at {candidate_script}. "
            "Each port must ship one — a small script that loads the fixture, "
            "calls the entry point, and dumps outputs to JSON."
        )
    fixture = port_dir / manifest.fixture_path
    out_path = port_dir / "data" / "candidate_output.json"
    cmd = [
        "conda", "run", "-p", py_conda_env,
        "python", str(candidate_script),
        str(fixture),
        str(out_path),
    ]
    print(f"[cand] {' '.join(cmd)}")
    t0 = time.time()
    subprocess.run(cmd, check=True)
    print(f"[cand] done in {time.time() - t0:.2f}s -> {out_path}")
    return out_path


def parity_diff(
    manifest: Manifest,
    reference_path: Path,
    candidate_path: Path,
) -> TrialResult:
    """Apply manifest.algorithm_class metric to (reference, candidate)."""
    with open(reference_path) as f:
        ref = json.load(f)
    with open(candidate_path) as f:
        cand = json.load(f)

    # If the manifest declares multiple outputs, ALL must pass.
    if not manifest.outputs:
        # fallback: compare whole files as flat arrays
        metric = compute_parity(ref, cand, manifest.algorithm_class)
        passed = is_pass(metric, manifest.algorithm_class, manifest.parity_threshold)
        return TrialResult(
            label=manifest.package,
            metric_value=metric,
            passed=passed,
            wall_clock_s=0.0,
        )

    results = []
    for output_spec in manifest.outputs:
        name = output_spec["name"]
        ref_value = _extract(ref, output_spec["location_reference"])
        cand_value = _extract(cand, output_spec["location_candidate"])
        cls = output_spec.get("metric", manifest.algorithm_class)
        threshold = output_spec.get("threshold", manifest.parity_threshold)
        metric = compute_parity(ref_value, cand_value, cls)
        passed = is_pass(metric, cls, threshold)
        results.append((name, metric, passed))

    all_passed = all(p for _, _, p in results)
    summary = "; ".join(f"{n}={m} {'OK' if p else 'FAIL'}" for n, m, p in results)
    return TrialResult(
        label=manifest.package,
        metric_value={n: m for n, m, _ in results},
        passed=all_passed,
        wall_clock_s=0.0,
        notes=summary,
    )


def _extract(blob: dict, location: str):
    """Tiny JSON-path extractor; supports $.a.b.c and adata.obs['x']-style hints.

    For 'adata.obs[...]' style on the candidate side, the candidate script
    must have flattened it into a plain JSON key already.
    """
    if location.startswith("$"):
        cur = blob
        for tok in location.lstrip("$.").split("."):
            cur = cur[tok]
        return cur
    # Candidate hint — strip framework noise; assume the candidate runner
    # already flattened the field to a top-level key matching the obs/obsm name.
    bracket = location.find("[")
    if bracket >= 0:
        key = location[bracket:].strip("[]'\"")
        return blob[key]
    return blob[location.rsplit(".", 1)[-1]]


def equivalence_phase(manifest: Manifest, port_dir: Path) -> TrialResult:
    """Step 3a — verify f_T(x) ≈_C f_R(x) on the canonical fixture."""
    ref = run_r_reference(manifest, port_dir)
    cand = run_candidate(manifest, port_dir)
    return parity_diff(manifest, ref, cand)


# ----------------------------------------------------------------------------- #
# Acceleration phase — verifier-guided test-time search                         #
# ----------------------------------------------------------------------------- #

@dataclasses.dataclass
class RewriteCandidate:
    """One discrete action a_t from the Acceleration Playbook."""
    name: str                            # e.g., "woodbury_kxk"
    playbook_section: str                # e.g., "§1.2"
    admissibility: str                   # "exact" | "bounded" | "containment"
    apply: Callable[[], None]            # mutates the working tree
    rollback: Callable[[], None]         # restores the working tree
    perturbation_bound: str | None = None  # derivation for bounded ε rewrites


def acceleration_phase(
    manifest: Manifest,
    port_dir: Path,
    candidates: list[RewriteCandidate],
    max_iterations: int = 20,
) -> list[TrialResult]:
    """Step 3b — search over equivalence-preserving rewrites for speed.

    For each candidate:
        1. Apply it.
        2. Re-run parity test.
        3. If gate breaks, roll back and skip.
        4. Else measure wall-clock; if improved, commit.

    Each `RewriteCandidate.apply` is provided by the agent — typically as
    a git stash apply, or an `Edit` call sequence. This loop just orchestrates.
    """
    if not manifest.acceleration_enabled:
        print("[accel] disabled in manifest; skipping")
        return []

    results = []
    baseline = equivalence_phase(manifest, port_dir)
    if not baseline.passed:
        raise RuntimeError(
            "Acceleration phase cannot start — Equivalence phase failed. "
            f"Fix that first. Got: {baseline}"
        )
    baseline_time = _stopwatch_run_candidate(manifest, port_dir)
    print(f"[accel] baseline parity={baseline.metric_value} time={baseline_time:.2f}s")
    best_time = baseline_time

    for it, cand in enumerate(candidates[:max_iterations], start=1):
        print(f"\n[accel] iter {it}: trying {cand.name} ({cand.playbook_section}, {cand.admissibility})")
        cand.apply()
        trial = equivalence_phase(manifest, port_dir)
        t = _stopwatch_run_candidate(manifest, port_dir)
        speedup = best_time / max(t, 1e-9)
        reward = (1.0 if trial.passed else 0.0) * speedup
        trial.notes = (
            f"action={cand.name} admissibility={cand.admissibility} "
            f"time={t:.2f}s speedup={speedup:.2f}x reward={reward:.2f}"
        )
        if trial.passed and t < best_time:
            print(f"[accel]   ACCEPT (speedup {speedup:.2f}x)")
            best_time = t
        else:
            print(f"[accel]   REJECT (passed={trial.passed}, speedup={speedup:.2f}x); rolling back")
            cand.rollback()
        results.append(trial)
    return results


def _stopwatch_run_candidate(manifest: Manifest, port_dir: Path) -> float:
    t0 = time.time()
    run_candidate(manifest, port_dir)
    return time.time() - t0


# ----------------------------------------------------------------------------- #
# CLI                                                                           #
# ----------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port-dir", required=True, help="Path to py-<pkg> directory")
    ap.add_argument("--phase", choices=["equivalence", "acceleration"], default="equivalence")
    args = ap.parse_args()

    port_dir = Path(args.port_dir).resolve()
    manifest = Manifest.load(port_dir / "data" / "manifest.yaml")
    print(f"[loop] port={manifest.package} class={manifest.algorithm_class} "
          f"threshold={manifest.parity_threshold}")

    if args.phase == "equivalence":
        result = equivalence_phase(manifest, port_dir)
        print(result)
        sys.exit(0 if result.passed else 1)
    else:
        # Acceleration phase needs candidates injected — usually by an agent.
        # For CLI use, just run equivalence-then-stopwatch.
        result = equivalence_phase(manifest, port_dir)
        print(result)
        t = _stopwatch_run_candidate(manifest, port_dir)
        print(f"[accel] candidate wall-clock on fixture: {t:.2f}s")
        sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
