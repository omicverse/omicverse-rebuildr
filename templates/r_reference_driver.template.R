#!/usr/bin/env Rscript
# Reference runner — invoked under conda env `$R_TEST_ENV`.
#
# Usage: Rscript r_reference_driver.R <fixture.{h5ad,rds}> <output.json>
#
# Loads the canonical fixture, runs <UpstreamR>, writes JSON.
# The JSON keys must match `manifest.yaml::outputs[*].location_reference`.

suppressMessages({
  library(jsonlite)
  library(<UpstreamR>)
  # add other upstream deps here, e.g.:
  # library(Seurat)
  # library(SingleCellExperiment)
})

args <- commandArgs(trailingOnly = TRUE)
fixture_path <- args[1]
output_path  <- args[2]

if (is.na(fixture_path) || is.na(output_path)) {
  stop("Usage: Rscript r_reference_driver.R <fixture> <output.json>")
}

# -- load fixture ------------------------------------------------------------

ext <- tools::file_ext(fixture_path)
if (ext == "h5ad") {
  # Read AnnData via anndata or zellkonverter
  ad <- anndata::read_h5ad(fixture_path)
  counts <- t(as.matrix(ad$X))   # genes x cells
  meta   <- ad$obs
} else if (ext == "rds") {
  obj <- readRDS(fixture_path)
  counts <- obj$counts
  meta   <- obj$meta
} else {
  stop(paste("Unknown fixture extension:", ext))
}

# -- run reference -----------------------------------------------------------

set.seed(42)
result <- <UpstreamR>::<entry_point>(
  counts,
  # pinned defaults — match `manifest.yaml::seed:` and any documented param
  ...
)

# -- shape into a flat JSON-friendly list -----------------------------------
# Match the location_reference paths declared in manifest.yaml::outputs.

out <- list(
  # example: ordinal pseudotime
  Pseudotime = as.numeric(result$Pseudotime),
  # example: cluster labels
  cluster    = as.integer(result$cluster),
  # example: -log10(p) statistical inference
  pvalue     = as.numeric(result$pvalue)
)

write_json(out, output_path, auto_unbox = TRUE, digits = NA, na = "null")
cat("[ref] wrote:", output_path, "\n")
