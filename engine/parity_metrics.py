"""Parity metrics — one per Omicverse-RebuildR algorithm class.

Importable from any port's tests/. Picks the right metric from the
manifest's `algorithm_class` field so per-port test_exact_match.py
doesn't have to hard-code metric math.

Usage:
    from omicverse_rebuild.engine.parity_metrics import compute_parity, default_threshold

    metric = compute_parity(reference, candidate, algorithm_class="ordinal")
    assert metric >= default_threshold("ordinal")
"""

from __future__ import annotations

from typing import Any

import numpy as np


# ----------------------------------------------------------------------------- #
# Class table — defaults from PARITY_TAXONOMY.md
# ----------------------------------------------------------------------------- #

DEFAULT_THRESHOLD = {
    # Deterministic-numerical: three tiers from strict bit-equivalence to
    # bounded-approximation. See PARITY_TAXONOMY.md §Deterministic sub-tiers.
    # The bare alias "deterministic" maps to the **standard** tier (1e-8) —
    # tight enough to catch real divergence, loose enough to absorb cross-BLAS
    # rounding and a single matmul / decomposition on real data.
    "deterministic":          1e-8,    # alias for the standard tier
    "deterministic-strict":   1e-13,   # element-wise, same BLAS, no chained ops
    "deterministic-standard": 1e-8,    # one or two matmul/PCA; cross-BLAS OK
    "deterministic-bounded":  1e-6,    # contains (B) ε-approx rewrites; MATH.md
                                       # must derive Σ bound ≤ this value
    "stochastic":             0.05,    # KS p-value floor
    "clustering":             0.95,    # ARI
    "embedding":              0.95,    # Procrustes similarity
    "ranked":                 0.80,    # top-50 Jaccard
    "ordinal":                0.99,    # Pearson (NOT bit-exact 1.0 — see is_pass)
    "classification":         0.95,    # F1
    "inference":              0.90,    # Spearman on -log10 p
}

# Hard ceiling: any threshold above this is rejected for the deterministic
# family because it stops being "deterministic" — the user should switch to
# ordinal (Pearson) or embedding (Procrustes) instead.
DETERMINISTIC_HARD_CEILING = 1e-6

# Set of all algorithm-class names valid in manifest.yaml.
VALID_CLASSES = set(DEFAULT_THRESHOLD)

# Map every deterministic sub-tier to the same metric function.
_DETERMINISTIC_ALIASES = {
    "deterministic", "deterministic-strict",
    "deterministic-standard", "deterministic-bounded",
}


def default_threshold(algorithm_class: str) -> float:
    if algorithm_class not in VALID_CLASSES:
        raise ValueError(
            f"Unknown algorithm_class={algorithm_class!r}. "
            f"Expected one of {sorted(VALID_CLASSES)}"
        )
    return DEFAULT_THRESHOLD[algorithm_class]


# ----------------------------------------------------------------------------- #
# Per-class metric implementations
# ----------------------------------------------------------------------------- #

def parity_deterministic(
    reference: np.ndarray,
    candidate: np.ndarray,
    *,
    rtol: float = 0.0,
) -> float:
    """Element-wise tolerance; returns the worst-case error.

    Without ``rtol``: returns ``max |reference - candidate|`` (absolute).
    With ``rtol > 0``: returns ``max |reference - candidate| / (rtol·|reference| + tiny)``
    — a relative max-error. Pass condition (in ``is_pass``) is
    ``returned_value < threshold``.

    Use the absolute mode (default) when all output values are O(1).
    Use ``rtol`` when values span many orders of magnitude.
    """
    reference = np.asarray(reference, dtype=np.float64).ravel()
    candidate = np.asarray(candidate, dtype=np.float64).ravel()
    if reference.shape != candidate.shape:
        raise ValueError(
            f"shape mismatch: {reference.shape} vs {candidate.shape}"
        )
    abs_err = np.abs(reference - candidate)
    if rtol <= 0.0:
        return float(np.max(abs_err))
    # tiny floor so rtol-mode on a reference of all zeros doesn't blow up
    scale = rtol * np.abs(reference) + np.finfo(np.float64).tiny
    return float(np.max(abs_err / scale))


def parity_stochastic(reference: np.ndarray, candidate: np.ndarray) -> float:
    """KS-test p-value; returns p in [0, 1].

    Higher is better; pass iff p ≥ threshold (default 0.05).
    """
    from scipy.stats import ks_2samp
    reference = np.asarray(reference).ravel()
    candidate = np.asarray(candidate).ravel()
    _, p = ks_2samp(reference, candidate)
    return float(p)


def parity_clustering(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Adjusted Rand Index between two label vectors. Returns ARI in [-1, 1]."""
    from sklearn.metrics import adjusted_rand_score
    return float(adjusted_rand_score(np.asarray(reference), np.asarray(candidate)))


def parity_embedding(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Procrustes similarity = 1 - disparity. Returns value in [0, 1]; 1 = identical up to rotation/scale."""
    from scipy.spatial import procrustes
    reference = np.asarray(reference)
    candidate = np.asarray(candidate)
    if reference.shape != candidate.shape:
        raise ValueError(
            f"shape mismatch: {reference.shape} vs {candidate.shape}"
        )
    _, _, disparity = procrustes(reference, candidate)
    return float(1.0 - disparity)


def parity_ranked(reference: list, candidate: list, k: int = 50) -> float:
    """Top-K Jaccard. Treat reference/candidate as ordered lists of IDs."""
    top_r = set(reference[:k])
    top_c = set(candidate[:k])
    if not top_r and not top_c:
        return 1.0
    return float(len(top_r & top_c) / len(top_r | top_c))


def parity_ranked_spearman(reference: list, candidate: list) -> float:
    """Spearman rank correlation between two rankings of the same item set."""
    from scipy.stats import spearmanr
    items = list(set(reference) & set(candidate))
    if len(items) < 2:
        return 0.0
    rank_r = {x: i for i, x in enumerate(reference)}
    rank_c = {x: i for i, x in enumerate(candidate)}
    rho, _ = spearmanr([rank_r[x] for x in items], [rank_c[x] for x in items])
    return float(rho)


def parity_ordinal(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Pearson correlation between two per-cell ordinal values (pseudotime, z).

    Returns r in [-1, 1]; pass iff |r| ≥ threshold (default 0.99).
    """
    from scipy.stats import pearsonr
    reference = np.asarray(reference).ravel()
    candidate = np.asarray(candidate).ravel()
    if reference.shape != candidate.shape:
        raise ValueError(
            f"shape mismatch: {reference.shape} vs {candidate.shape}"
        )
    mask = np.isfinite(reference) & np.isfinite(candidate)
    if mask.sum() < 2:
        return 0.0
    r, _ = pearsonr(reference[mask], candidate[mask])
    return float(abs(r))


def parity_classification(
    reference: np.ndarray,
    candidate: np.ndarray,
    average: str = "binary",
) -> float:
    """F1 score between two label vectors. If labels are strings, encodes them.

    `average='binary'` for 2-class; `'macro'` for multi-class.
    """
    from sklearn.metrics import f1_score
    reference = np.asarray(reference)
    candidate = np.asarray(candidate)
    if reference.dtype.kind in "UO" or candidate.dtype.kind in "UO":
        # encode string labels deterministically
        labels = sorted(set(reference) | set(candidate))
        encode = {lab: i for i, lab in enumerate(labels)}
        reference = np.array([encode[x] for x in reference])
        candidate = np.array([encode[x] for x in candidate])
        if len(labels) > 2:
            average = "macro"
    return float(f1_score(reference, candidate, average=average))


def parity_inference(
    reference_p: np.ndarray,
    candidate_p: np.ndarray,
    top_k: int = 50,
) -> dict:
    """Returns both the Spearman rank-corr on -log10 p AND top-K Jaccard.

    Pass iff Spearman ≥ 0.90 AND top-K Jaccard ≥ 0.7.
    """
    from scipy.stats import spearmanr
    reference_p = np.clip(np.asarray(reference_p).ravel(), 1e-300, 1.0)
    candidate_p = np.clip(np.asarray(candidate_p).ravel(), 1e-300, 1.0)
    if reference_p.shape != candidate_p.shape:
        raise ValueError(
            f"shape mismatch: {reference_p.shape} vs {candidate_p.shape}"
        )
    neg_log_r = -np.log10(reference_p)
    neg_log_c = -np.log10(candidate_p)
    rho, _ = spearmanr(neg_log_r, neg_log_c)
    top_r = set(np.argsort(reference_p)[:top_k].tolist())
    top_c = set(np.argsort(candidate_p)[:top_k].tolist())
    jacc = (len(top_r & top_c) / len(top_r | top_c)) if (top_r | top_c) else 1.0
    return {
        "spearman_neglog10p": float(rho),
        f"top{top_k}_jaccard": float(jacc),
    }


# ----------------------------------------------------------------------------- #
# Dispatcher
# ----------------------------------------------------------------------------- #

_DISPATCH = {
    "deterministic":          parity_deterministic,
    "deterministic-strict":   parity_deterministic,
    "deterministic-standard": parity_deterministic,
    "deterministic-bounded":  parity_deterministic,
    "stochastic":             parity_stochastic,
    "clustering":             parity_clustering,
    "embedding":              parity_embedding,
    "ranked":                 parity_ranked,
    "ordinal":                parity_ordinal,
    "classification":         parity_classification,
    "inference":              parity_inference,
}


def compute_parity(
    reference: Any,
    candidate: Any,
    algorithm_class: str,
    **kwargs,
) -> Any:
    """Run the right parity metric for `algorithm_class`.

    Returns:
        - float for {deterministic, stochastic, clustering, embedding,
                     ranked, ordinal, classification};
        - dict with two keys for {inference}.

    For the float return, compare to `default_threshold(class)` to get pass/fail.
    For inference, demand BOTH `spearman_neglog10p ≥ 0.90`
    AND `top50_jaccard ≥ 0.7`.
    """
    if algorithm_class not in _DISPATCH:
        raise ValueError(
            f"Unknown algorithm_class={algorithm_class!r}. "
            f"Valid: {sorted(_DISPATCH)}"
        )
    return _DISPATCH[algorithm_class](reference, candidate, **kwargs)


def is_pass(metric_value: Any, algorithm_class: str, threshold: float | None = None) -> bool:
    """Apply the per-class pass direction.

    - Deterministic family: lower is better; pass iff metric_value < threshold.
      A hard ceiling of `DETERMINISTIC_HARD_CEILING` (= 1e-6) is enforced — if
      a port needs more than this for "deterministic" parity, the algorithm
      class is wrong; switch to `ordinal` (Pearson) or `embedding` (Procrustes).

    - Inference: dict with two keys; pass iff BOTH clear their own thresholds.

    - Everything else: higher is better; pass iff metric_value >= threshold.
    """
    threshold = threshold if threshold is not None else default_threshold(algorithm_class)

    if algorithm_class in _DETERMINISTIC_ALIASES:
        if threshold > DETERMINISTIC_HARD_CEILING:
            raise ValueError(
                f"deterministic threshold {threshold:.2e} exceeds hard ceiling "
                f"{DETERMINISTIC_HARD_CEILING:.2e}. "
                "At this scale 'deterministic' has lost meaning — switch to "
                "'ordinal' (Pearson) for monotonic / per-cell outputs or "
                "'embedding' (Procrustes) for coordinate outputs."
            )
        return float(metric_value) < threshold

    if algorithm_class == "inference":
        return (
            metric_value["spearman_neglog10p"] >= 0.90
            and metric_value["top50_jaccard"] >= 0.7
        )

    # Ordinal: Pearson is bit-noisy on bit-equivalent inputs (~1 - 1e-15).
    # Treat any value within 1e-12 of 1.0 as effectively perfect to avoid
    # spurious failures from `pearsonr` internal rounding.
    if algorithm_class == "ordinal":
        return float(metric_value) >= threshold - 1e-12

    return float(metric_value) >= threshold
