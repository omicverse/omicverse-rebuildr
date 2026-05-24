"""Candidate runner — invoked under conda env `$PYTHON_TEST_ENV`.

Usage: python _run_candidate.py <fixture.h5ad> <output.json>

Loads the canonical fixture, runs the in-progress port's entry point,
dumps outputs to JSON. The JSON keys must match
`manifest.yaml::outputs[*].location_candidate`.

This script is read by engine/loop.py via subprocess; keep it tiny.
"""

import json
import sys

import anndata as ad
import numpy as np

# Replace with your port's actual import
from <pkgname> import <PkgName>


def main():
    if len(sys.argv) != 3:
        print("Usage: python _run_candidate.py <fixture.h5ad> <output.json>")
        sys.exit(2)
    fixture_path, output_path = sys.argv[1], sys.argv[2]

    adata = ad.read_h5ad(fixture_path)

    # set the same seed as ref_runner.R
    np.random.seed(42)

    # run the port — class API style
    obj = <PkgName>(adata)
    obj.run()  # adjust to your entry point

    # flatten the candidate outputs into a JSON-friendly dict keyed
    # to match manifest.yaml::outputs[*].location_candidate.
    out = {
        "Pseudotime": obj.adata.obs["Pseudotime"].astype(float).tolist(),
        # add more keys as declared in the manifest
    }

    with open(output_path, "w") as f:
        json.dump(out, f)
    print(f"[cand] wrote: {output_path}")


if __name__ == "__main__":
    main()
