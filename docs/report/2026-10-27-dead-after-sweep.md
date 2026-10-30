# 2026-10-27 dead_after (L) sweep and AE CCDF redraw

## Decisions
- AE2 (reactions received per agent) is now drawn as a CCDF P(count ≥ x) like AE1 (`plot_std.py`, `plot_mix.py`); agents with 0 reactions stay in the denominator.
- `HIST_MAX` (post lifetime histogram cap in `OpinionDynamics.java`) raised 3000 → 20000: the old cap lumped long-lived posts into the 3000 bin, so AE1 tails were truncated for For You / mix. Only For You and mix runs hit the cap; Chrono and Trend never did.
- Re-run of capped runs started and **stopped part-way** (user wanted the L sweep first): regenerated = For You on hk, random, sbm; **not** regenerated (old capped folders deleted) = For You on ws and hkshuf, gauss_{random,hkshuf} For You, mix on hkshuf/random. Published figures still use the old data. Backup index: `results/rsearch/summary.jsonl.bak_before_ccdf`.
- New sweep `scripts/dead_sweep_run.py`: hkshuf, standing config, L ∈ {10,25,50,100,200,400}, 3 feeds, 3 seeds, 20,000 steps. Plot `scripts/plot_dead_sweep.py` → `figures/dead-after-sweep/`.

## Findings (hkshuf, 3 seeds pooled; extra life t = lifetime − (L+1))
- Chrono: extra life ≤ ~50 for every L; the tail is thin and nearly L-independent.
- For You: tail grows with L up to L=100 (max extra life 426 → 3963); the t/L-rescaled curves for L ≤ 100 nearly collapse. At L ≥ 200 the regime changes: 82–86% of posts get no reaction (vs 42–60% for L ≤ 100) and the tail ends at ~4500, i.e. the end of the 5,000-step window (right-censoring), not a natural cutoff.
- Trend: tail scales with L; ~90% of posts get no reaction at all L.
- Log-normal MLE overlay (σ 0.5–0.7 Chrono/Trend, 1.2–1.5 For You) follows the bulk but overshoots the far tail; no goodness-of-fit test run. Shortening L rescales the curves but does not remove the curved log-log shape.
- AE2: insensitive to L for Chrono / Trend; For You at L=400 differs (cutoff ~500 vs ~3000).

## Decision (user, 2026-10-27): standing config now uses dead_after L = 50
- Rationale: at L = 200 For You is in a regime where 82–86% of posts get no reaction and the AE1 tail is censored by the window end; L = 50 is before that change.
- Supersedes L = 200 for all published figure sets. `standard_run.COMMON` now sets `dead_after=50`; `plot_std.py` / `plot_mix.py` use `DEAD = 50` for the grace offset.
- Old L = 200 runs of baseline_{hk,hkshuf,random,sbm,ws}_{chrono,foryou,trend}, gauss_{random,hkshuf}_*, baseline_{hkshuf,random}_mix deleted (index backup `summary.jsonl.bak_L200`); all re-run with 10 seeds (230 runs) via `logs/L50_rerun.out`, then figures in `figures/uniform-start`, `gaussian-start`, `mix-feed` are redrawn.

## 2026-10-27 No-rewire runs (new topic follow-up)
- `scripts/norewire_run.py`: standing config (L = 50) with `rewire=false`, Chrono / For You / Trend, 10 seeds, 20,000 steps on random (ER), sbm, ws, hkshuf (120 runs, ids `norewire_<net>_<feed>`).
- Figures `figures/no-rewire/norewire_<net>.png` via `plot_std.py OUT.png <net> norewire` (fit baseline analytic; EMPIRICAL_FIT now only for `gauss*` prefixes).
