#!/usr/bin/env Rscript
# Per-function output dump for Notebook 3 (function_by_function_R_parity.ipynb).
#
# Calls each public R function in turn on the canonical fixture and saves
# its raw output to a per-function JSON file under examples/_r_outputs/.
# The Python notebook reads these and compares to its own calls.
#
# Run once before re-executing Notebook 3:
#   conda activate $R_TEST_ENV
#   Rscript examples/r_per_function_dump.R

suppressMessages({
  library(<UpstreamR>)
  library(jsonlite)
})

OUT_DIR <- "examples/_r_outputs"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

# ---- load fixture ---------------------------------------------------------
# Replace with your fixture loader; the path comes from data/manifest.yaml::fixture.path.
fixture <- readRDS("data/fixture_<dataset>.rds")
set.seed(<seed_from_manifest>)
cat("[r-dump] fixture dims:", dim(fixture), "\n")

# ---- one entry per public function from RECONSTRUCTION_REPORT §2.2 -------
# For each: call with sensible defaults (matching what Notebook 3 will call
# in Python), then dump the salient outputs to JSON keyed for easy ingest.

# Function 1: <r_fn_a>
result_a <- <r_fn_a>(fixture, <args>)
write_json(
  list(
    output1 = as.numeric(result_a$output1),
    output2 = as.integer(result_a$output2),
    # ... one entry per slot used by the Python comparison
    .args = list(<args you used so Notebook 3 can echo them>)
  ),
  file.path(OUT_DIR, "<r_fn_a>.json"),
  auto_unbox = TRUE, digits = NA, matrix = "rowmajor", na = "null", pretty = FALSE
)
cat("[r-dump] wrote", file.path(OUT_DIR, "<r_fn_a>.json"), "\n")

# Function 2: <r_fn_b>
result_b <- <r_fn_b>(result_a, <args>)
write_json(
  list(
    output1 = as.numeric(result_b$output1),
    .args = list(<args>)
  ),
  file.path(OUT_DIR, "<r_fn_b>.json"),
  auto_unbox = TRUE, digits = NA, na = "null", pretty = FALSE
)

# ... repeat for every public function

cat("[r-dump] done.\n")
