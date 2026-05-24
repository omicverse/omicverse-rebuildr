"""omicverse-rebuildr engine — parity metrics + the Omicverse-RebuildR loop, as code."""

from .parity_metrics import (  # noqa: F401
    DEFAULT_THRESHOLD,
    VALID_CLASSES,
    compute_parity,
    default_threshold,
    is_pass,
    parity_classification,
    parity_clustering,
    parity_deterministic,
    parity_embedding,
    parity_inference,
    parity_ordinal,
    parity_ranked,
    parity_ranked_spearman,
    parity_stochastic,
)
