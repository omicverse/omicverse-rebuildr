# Trajectory-Inference R-Package Roadmap

> Ranked candidates for the next series of `py-<pkg>` ports under `github.com/omicverse`. Ordered by **citation density (citations/year) × benchmark importance**, excluding anything already published under `omicverse/`.

## Status legend

- ✅ done (under `omicverse/`)
- 🟡 in progress
- ⬜ not started
- ⛔ skip (already has a Python implementation OR is integrated in scanpy)

## Already-done at omicverse (do NOT re-port)

| Package | Repo | Algorithm class |
|---|---|---|
| Monocle 2 | [`py-monocle2`](https://github.com/omicverse/py-monocle2) | ordinal (pseudotime) |
| Slingshot | `omicverse.single._pyslingshot` | ordinal |
| Palantir | `omicverse.externel.palantir` | ordinal |
| VIA | `omicverse.via` | ordinal |
| Diffusion map (homebrew) | `omicverse.single._diffusionmap` | ordinal |
| CytoTRACE 2 | `omicverse.single._cytotrace2` | ordinal |
| CellFateGenie | `omicverse.single._cellfategenie` | inference |
| STT | `omicverse.externel.STT` | ordinal |
| scdiffusion | `omicverse.externel.scdiffusion` | ordinal |

## Tier 1 — Highest priority (must-port for any TI benchmark)

| Rank | R package | Year | Citations | cites/yr | Algorithm class | Status | Seed template |
|---|---|---|---|---|---|---|---|
| 1 | **tradeSeq** | 2020 | ~911 | ~152 | inference | ⬜ | `py-miloR` |
| 2 | **URD** | 2018 | ~982 | ~123 | ordinal | ⬜ | `py-monocle2` |
| 3 | **TSCAN** | 2016 | ~547 | ~55 | ordinal | ⬜ | `py-monocle2` |
| 4 | **destiny** (DPT) | 2016 | ~341 | ~34 | ordinal | ⬜ | `py-monocle2` |

Notes on Tier 1:
- **tradeSeq** is the highest-ROI port — DE-along-trajectory is the standard companion to every TI method. Pairs with Slingshot which is already in omicverse.
- **URD** has the highest citation count (Science 2018) but most are biological applications; method-method citations are ~30% of total.
- **TSCAN** is the simplest port (PCA + Mclust + MST + principal curve) — best for verifying the engineering loop.
- **destiny** is the canonical DPT reference; scanpy's DPT is an independent reimplementation, not a port — a real `py-destiny` would be valuable.

## Tier 2 — Strongly recommended

| Rank | R package | Year | Citations | cites/yr | Algorithm class | Status | Seed template |
|---|---|---|---|---|---|---|---|
| 5 | **SCORPIUS** | 2016 | ~165 | ~17 | ordinal | ⬜ | `py-monocle2` |
| 6 | **condiments** | 2024 | ~38 | ~19 | inference | ⬜ | `py-miloR` |

Notes:
- **SCORPIUS** is the dynbenchmark linear-trajectory winner; same authors as Slingshot/tradeSeq team.
- **condiments** is the 2024 Nat Commun multi-condition trajectory framework — "occupy" while citations are still building.

## Tier 3 — Optional (specialised topologies / specific use cases)

| Rank | R package | Year | Citations | cites/yr | Algorithm class | Status |
|---|---|---|---|---|---|---|
| 7 | **SLICER** | 2016 | ~184 | ~18 | ordinal | ⬜ |
| 8 | **psupertime** | 2022 | ~44 | ~11 | ordinal | ⬜ |
| 9 | **Totem** | 2023 | ~17 | ~6 | ordinal | ⬜ |
| 10 | **Mpath** | 2016 | ~91 | ~9 | ordinal | ⬜ |
| 11 | **PhenoPath** | — | — | — | ordinal | ⬜ |
| 12 | **ouija** | — | — | — | ordinal | ⬜ |
| 13 | **CellTrails** | — | — | — | ordinal | ⬜ |
| 14 | **reCAT** | — | — | — | ordinal (cell-cycle) | ⬜ |
| 15 | **FateID** | — | — | — | ordinal | ⬜ |
| 16 | **RaceID / StemID** | — | — | — | clustering + ordinal | ⬜ |

## Already-Python (do NOT re-port)

- ⛔ PAGA — native to scanpy
- ⛔ scVelo — Python
- ⛔ CellRank — Python
- ⛔ scFates — Python
- ⛔ Wishbone — Python
- ⛔ Wanderlust — Python
- ⛔ elPiGraph — has a Python implementation (`ElPiGraph.P`)

## Suggested execution order

For a Trajectory benchmark that complements omicverse's existing TI methods:

```
1. py-TSCAN        (Equivalence test the loop end-to-end on a simple port)
2. py-tradeSeq     (Highest-ROI; needed by every benchmark)
3. py-destiny      (DPT canonical reference)
4. py-URD          (Branching tree topology)
5. py-SCORPIUS     (Linear SOTA; dynbenchmark winner)
6. py-condiments   (Multi-condition extensions)
```

Each port should follow [PROTOCOL.md](../PROTOCOL.md) verbatim and tick through [CHECKLIST.md](../CHECKLIST.md). Update this file's status column after each release.

## Source

Citation counts: Google Scholar (May 2026). TSCAN cite from Semantic Scholar. Selection criteria: dynbenchmark top performers + post-2019 high-impact additions + multi-condition / supervised extensions. See the conversation transcript in `omicverse-rebuildr/` for the audit trail.
