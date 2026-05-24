"""Plot the two-panel evolution figure from ITERATION_LOG.md.

Top panel:    wall-clock vs iteration  (lower is better)
Bottom panel: accuracy   vs iteration  (must stay ≥ threshold; dips annotated)

Run after the Acceleration loop terminates:

    python -m engine.plot_evolution \
        --port-dir <path-to-your-port> \
        --output examples/evolution.png

Parses YAML blocks inside markdown headers like "## iter 1 — ...".
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ----------------------------------------------------------------------------- #
# Log parsing                                                                   #
# ----------------------------------------------------------------------------- #

ITER_BLOCK = re.compile(
    r"##\s+(iter\s+\d+|Baseline)\s*—[^\n]*\n+```yaml\n(.*?)\n```",
    re.S | re.I,
)


@dataclass
class IterEntry:
    iter: int
    status: str
    action: str | None
    admissibility: str | None
    playbook_section: str | None
    wall_clock_mean_s: float | None
    wall_clock_stddev_s: float | None
    parity_metric: float | None
    parity_passes: bool | None
    math_reason_for_dip: str | None
    raw: dict[str, Any] = field(default_factory=dict)


def parse_log(log_path: Path) -> list[IterEntry]:
    text = log_path.read_text()
    entries: list[IterEntry] = []
    for m in ITER_BLOCK.finditer(text):
        body = yaml.safe_load(m.group(2))
        if not isinstance(body, dict):
            continue
        entries.append(IterEntry(
            iter=body.get("iter", -1),
            status=body.get("status", "?"),
            action=body.get("action"),
            admissibility=body.get("admissibility"),
            playbook_section=body.get("playbook_section"),
            wall_clock_mean_s=body.get("wall_clock_mean_s"),
            wall_clock_stddev_s=body.get("wall_clock_stddev_s"),
            parity_metric=_extract_metric(body.get("parity_metric")),
            parity_passes=body.get("parity_passes"),
            math_reason_for_dip=body.get("math_reason_for_dip"),
            raw=body,
        ))
    entries.sort(key=lambda e: e.iter)
    return entries


def _extract_metric(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        # multi-output: use the worst (most pessimistic) value
        floats = [x for x in v.values() if isinstance(x, (int, float))]
        return float(min(floats)) if floats else None
    return None


# ----------------------------------------------------------------------------- #
# Plot                                                                          #
# ----------------------------------------------------------------------------- #

def plot(entries: list[IterEntry], output: Path, threshold: float | None = None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    accepted = [e for e in entries if e.status in ("baseline", "ACCEPT")]
    if not accepted:
        raise RuntimeError("No baseline or accepted iterations in the log.")

    iters = [e.iter for e in accepted]
    times = [e.wall_clock_mean_s or float("nan") for e in accepted]
    stds = [e.wall_clock_stddev_s or 0.0 for e in accepted]
    accs = [e.parity_metric for e in accepted]

    fig, (ax_t, ax_a) = plt.subplots(
        2, 1, figsize=(8, 6), sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.15},
    )

    # Top: wall-clock
    ax_t.errorbar(iters, times, yerr=stds, marker="o", color="#0078d4",
                  capsize=3, linewidth=1.5, markersize=7)
    ax_t.set_ylabel("Wall-clock (s)\nmean of 3 runs, warmup excluded")
    ax_t.set_title("Acceleration trajectory")
    ax_t.set_yscale("log")
    ax_t.grid(True, which="both", alpha=0.25)

    # Annotate each accepted action
    for e, t in zip(accepted, times):
        if e.action:
            label = f"{e.playbook_section or ''} {e.action}".strip()
            ax_t.annotate(label, (e.iter, t),
                          textcoords="offset points", xytext=(6, 6),
                          fontsize=7, color="#333")

    # Bottom: accuracy
    valid = [(i, a) for i, a in zip(iters, accs) if a is not None]
    if valid:
        xi, ya = zip(*valid)
        ax_a.plot(xi, ya, marker="o", color="#107c10",
                  linewidth=1.5, markersize=7)
        ax_a.set_ylim(min(min(ya), (threshold or 0.99)) - 0.005,
                      max(ya) + 0.002)
    ax_a.set_ylabel("Parity metric")
    ax_a.set_xlabel("Iteration")
    ax_a.grid(True, alpha=0.25)
    if threshold is not None:
        ax_a.axhline(threshold, color="red", linestyle="--", linewidth=1,
                     label=f"threshold = {threshold}")
        ax_a.legend(loc="lower left", fontsize=8)

    # Annotate every accuracy dip with its math reason
    prev_a = None
    for e in accepted:
        if e.parity_metric is None:
            continue
        if prev_a is not None and e.parity_metric < prev_a - 1e-6:
            note = (e.math_reason_for_dip or "").strip().split("\n", 1)[0]
            if note:
                ax_a.annotate(
                    f"↓ {note}",
                    (e.iter, e.parity_metric),
                    textcoords="offset points",
                    xytext=(8, -14),
                    fontsize=7,
                    color="#a4262c",
                    arrowprops=dict(arrowstyle="->", color="#a4262c", lw=0.7),
                )
        prev_a = e.parity_metric

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    print(f"[plot] wrote {output}")


# ----------------------------------------------------------------------------- #
# CLI                                                                          #
# ----------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port-dir", required=True, type=Path)
    ap.add_argument("--log", type=Path, default=None,
                    help="Path to ITERATION_LOG.md (default: <port-dir>/ITERATION_LOG.md)")
    ap.add_argument("--output", type=Path, default=None,
                    help="Output PNG path (default: <port-dir>/examples/evolution.png)")
    ap.add_argument("--threshold", type=float, default=None,
                    help="Parity threshold from manifest.yaml (drawn as red dashed line)")
    args = ap.parse_args()

    log_path = args.log or (args.port_dir / "ITERATION_LOG.md")
    output_path = args.output or (args.port_dir / "examples" / "evolution.png")

    entries = parse_log(log_path)
    threshold = args.threshold
    if threshold is None:
        # try to read from manifest
        manifest_path = args.port_dir / "data" / "manifest.yaml"
        if manifest_path.exists():
            mf = yaml.safe_load(manifest_path.read_text())
            threshold = mf.get("parity_threshold")
    plot(entries, output_path, threshold=threshold)


if __name__ == "__main__":
    main()
