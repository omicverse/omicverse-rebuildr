"""The parity gate, as a pytest test.

Runs the R reference and the candidate port on the same fixture,
applies the class-aware metric from PARITY_TAXONOMY, asserts pass.

This test FAILS the build if the pre-registered gate fails. Do not
loosen the threshold to fit the candidate — fix the candidate.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

# Vendored copy of engine/parity_metrics.py — every port ships its own copy
# rather than depending on the omicverse-rebuildr kit at runtime.
from .parity_metrics import compute_parity, is_pass

HERE = Path(__file__).parent
PORT_DIR = HERE.parent
MANIFEST_PATH = PORT_DIR / "data" / "manifest.yaml"
R_CONDA_ENV = os.environ.get("R_TEST_ENV", "/path/to/your/R/env")
PY_CONDA_ENV = os.environ.get("PYTHON_TEST_ENV", "/path/to/your/python/env")


@pytest.fixture(scope="session")
def manifest():
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def reference_output(manifest, tmp_path_factory):
    """Run the R reference once per session; cache the JSON."""
    cache = PORT_DIR / "data" / "reference_output.json"
    if cache.exists():
        return json.loads(cache.read_text())

    fixture = PORT_DIR / manifest["fixture"]["path"]
    ref_script = PORT_DIR / manifest["reference_command"]
    cmd = [
        "conda", "run", "-p", R_CONDA_ENV,
        "Rscript", str(ref_script),
        str(fixture), str(cache),
    ]
    subprocess.run(cmd, check=True)
    return json.loads(cache.read_text())


@pytest.fixture(scope="session")
def candidate_output(manifest):
    """Run the candidate port once per session; cache the JSON."""
    cache = PORT_DIR / "data" / "candidate_output.json"
    fixture = PORT_DIR / manifest["fixture"]["path"]
    runner = HERE / "_run_candidate.py"
    cmd = [
        "conda", "run", "-p", PY_CONDA_ENV,
        "python", str(runner),
        str(fixture), str(cache),
    ]
    subprocess.run(cmd, check=True)
    return json.loads(cache.read_text())


def test_parity_against_R(manifest, reference_output, candidate_output):
    """The pre-registered numerical parity gate."""
    outputs = manifest.get("outputs", [])
    if not outputs:
        metric = compute_parity(
            reference_output,
            candidate_output,
            manifest["algorithm_class"],
        )
        passed = is_pass(metric, manifest["algorithm_class"], manifest["parity_threshold"])
        assert passed, (
            f"Parity gate failed for {manifest['package']}: "
            f"metric={metric} threshold={manifest['parity_threshold']}"
        )
        return

    failures = []
    for spec in outputs:
        name = spec["name"]
        ref_key = spec["location_reference"].lstrip("$.")
        cand_key = (
            spec["location_candidate"].split("[")[-1].strip("]'\"")
            if "[" in spec["location_candidate"]
            else spec["location_candidate"].rsplit(".", 1)[-1]
        )
        cls = spec.get("metric", manifest["algorithm_class"])
        threshold = spec.get("threshold", manifest["parity_threshold"])
        metric = compute_parity(
            reference_output[ref_key],
            candidate_output[cand_key],
            cls,
        )
        if not is_pass(metric, cls, threshold):
            failures.append((name, metric, threshold))
        print(f"[parity] {name}: metric={metric} threshold={threshold}")

    if failures:
        raise AssertionError(
            f"Parity gate failed: {failures}"
        )
