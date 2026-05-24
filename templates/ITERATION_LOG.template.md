# Acceleration Iteration Log — py-<PkgName>

> Append one block per Acceleration Agent step. Parsed by `engine/plot_evolution.py` to generate the two-plot evaluation in [EVALUATION.md](../EVALUATION.md). Schema is strict — keep the field names and the indented YAML block verbatim so the parser doesn't break.

---

## Baseline — <YYYY-MM-DD HH:MM:SS>

```yaml
iter: 0
status: baseline
action: null
admissibility: null
playbook_section: null
wall_clock_mean_s: <T0>
wall_clock_stddev_s: <S0>
wall_clock_runs_s: [<t1>, <t2>, <t3>]    # warmup-excluded
warmup_run_s: <w0>
parity_metric: <value>
parity_class: <ordinal | clustering | embedding | …>
parity_threshold: <from manifest>
parity_passes: true
notes: |
  Equivalence Agent's clean translation passes the gate at <metric>=<value>.
  This is the starting point for the Acceleration search.
```

---

## iter 1 — <YYYY-MM-DD HH:MM:SS>

```yaml
iter: 1
status: <ACCEPT | REJECT_GATE | REJECT_SLOW | REJECT_INADMISSIBLE>
action: <short-handle>                   # e.g., "cache_XtX"
playbook_section: "§1.1"                 # ACCELERATION_PLAYBOOK section
admissibility: <exact | bounded | containment>
admissibility_evidence: |
  One-paragraph proof or citation. For (B) ε-approximation MUST give the
  closed-form perturbation bound. For (C) MUST cite the theorem.
perturbation_bound: |
  (B-only) e.g.,  ‖W_new − W_old‖_F ≤ κ · n · K · ε,  κ = ‖X‖_∞ / δ_min,
                  with ε=1e-12 → bound = 3.4e-9 on this fixture.
wall_clock_mean_s: <T1>
wall_clock_stddev_s: <S1>
wall_clock_runs_s: [<t1>, <t2>, <t3>]
warmup_run_s: <w1>
speedup_vs_previous: <T_prev / T1>
speedup_vs_baseline: <T0 / T1>
parity_metric: <value>
parity_delta_vs_baseline: <value - baseline>
parity_passes: <bool>
math_reason_for_dip: |
  (only if parity dipped) Explain WHY the metric moved. This caption is
  rendered on Plot 2 next to the dip.
```

### Decision

<ACCEPT — keep this rewrite. Working tree's HEAD now embeds this change.>
<REJECT_GATE — parity dropped below threshold; rolled back.>
<REJECT_SLOW — accuracy held but wall-clock did not improve; rolled back.>
<REJECT_INADMISSIBLE — no admissibility proof produced; not run.>

### Commit / branch

```
branch: acceleration-iter-1-cache_XtX
commit: <sha>
```

---

## iter 2 — <YYYY-MM-DD HH:MM:SS>

```yaml
iter: 2
status: ...
action: ...
...
```

---

## Summary so far (auto-rendered)

| iter | action | admissibility | mean time (s) | speedup vs baseline | accuracy | status |
|---|---|---|---|---|---|---|
| 0 | (baseline) | — | <T0> | 1× | <a0> | — |
| 1 | <…> | E | <T1> | <a1/a0> | <p1> | ACCEPT |
| 2 | <…> | C | <T2> | … | … | … |

## Stop reason

<one of:>
- Playbook exhausted on this port's pattern.
- Last 3 attempts produced no measurable speedup.
- Diminishing returns: cumulative speedup > 50× and remaining candidates have low expected gain.
- Acceleration disabled in manifest (class-A translation-only port).
