"""
2026-08-06 -- validation battery for the two-level homophily-gate hypothesis (docs/report
2026-08-02-delayed-moderate-conduit-pilot.md): p_u = structural gate (PE<->E follow-graph
connectivity), vcr = perceptual gate (comfort-ratio of PE content reaching E). Four checks, per the
project's own handoff-mandated validation practice (independent-pathway cross-validation,
split-seed-block direction-flip check -- the same checks that caught the prior postShare_b measurement
bug, commit 684d6fc) plus formal significance testing (nothing run today had a real test yet, only
means/diffs):

1. Formal test: is the PE<->E connectivity gap (N_silent - control) larger at p_u=0.15 than p_u=0.05?
2. Formal test: is the comfort-ratio (feedComfortClass/feedAuthorClass) lower under N_silent, per seed?
3. Split-seed-block robustness: seeds 8900000-8900007 vs 8900008-8900014.
4. Independent-pathway cross-check: GEXF connectivity-gap ranking vs feed-composition volume-gap
   ranking across the 8 cells.

2026-08-06 rewrite: the first version re-read each seed's full 40000-row results.csv from scratch on
every call (hundreds of times total) -- took 40+ min and still hadn't finished. This version caches
each (seed, subdir) CSV's trailing-window rows and each (seed, subdir, checkpoint) GEXF parse ONCE,
reused across all cells/checks.

Usage: python3 scripts/lmp_feedmech_validate.py
"""
import csv

import numpy as np
from scipy import stats

from lmp_feedmech_stage1 import CELLS, cell_name, result_dir, WINDOW, FULL_STEPS
from lmp_feedmech_stage1_gexf import parse_gexf_classes_and_edges, final_gexf_path, SUBDIR as GEXF_SUBDIR

STAGE1_SUBDIR = "2026-08-06_lmp_feedmech_stage1"
COMFORT_SEEDS = [8900000 + i for i in range(15)]
GEXF_SEEDS = [8900000 + i for i in range(15)]  # full n=15 GEXF batch now complete

_csv_cache = {}
_gexf_cache = {}


def cached_window_rows(seed, subdir, checkpoint=FULL_STEPS, window=WINDOW):
    key = (seed, subdir, checkpoint, window)
    if key not in _csv_cache:
        d = result_dir(seed, subdir)
        with open(d / "metrics" / "results.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        lo = checkpoint - window
        _csv_cache[key] = [r for r in rows if lo < int(r["step"]) <= checkpoint]
    return _csv_cache[key]


def cached_gexf(seed, subdir, checkpoint=FULL_STEPS):
    key = (seed, subdir, checkpoint)
    if key not in _gexf_cache:
        path = final_gexf_path(seed, subdir, checkpoint)
        _gexf_cache[key] = parse_gexf_classes_and_edges(path)
    return _gexf_cache[key]


def cross_class_density_cached(seed, subdir, class_a, class_b, checkpoint=FULL_STEPS):
    cls, tgt, edges = cached_gexf(seed, subdir, checkpoint)
    A = {n for n, c in cls.items() if c == class_a and not tgt[n]}
    B = {n for n, c in cls.items() if c == class_b and not tgt[n]}
    if not A or not B:
        return float("nan")
    count = sum(1 for s, t in edges if s in A and t in B)
    return count / (len(A) * len(B))


def per_seed_ratio(seed, subdir, reader_cls, author_cls):
    sel = cached_window_rows(seed, subdir)
    tot = sum(float(r[f"feedAuthorClass{author_cls}CountMean_{reader_cls}"]) for r in sel)
    com = sum(float(r[f"feedComfortClass{author_cls}CountMean_{reader_cls}"]) for r in sel)
    return com / tot if tot > 0 else float("nan")


def per_seed_author_class_mean(seed, subdir, reader_cls, author_cls):
    sel = cached_window_rows(seed, subdir)
    return np.mean([float(r[f"feedAuthorClass{author_cls}CountMean_{reader_cls}"]) for r in sel])


def connectivity_gap_array(seeds, pu, vcr, class_a, class_b):
    ctrl_subdir = f"{GEXF_SUBDIR}/{cell_name(pu, vcr)}/control"
    msil_subdir = f"{GEXF_SUBDIR}/{cell_name(pu, vcr)}/N_silent"
    c = np.array([cross_class_density_cached(s, ctrl_subdir, class_a, class_b) for s in seeds])
    m = np.array([cross_class_density_cached(s, msil_subdir, class_a, class_b) for s in seeds])
    return m - c


def check1_connectivity_gap_by_pu(seeds, label):
    print(f"\n=== Check 1 [{label}]: is the PE<->E connectivity gap bigger at p_u=0.15 than p_u=0.05? ===", flush=True)
    for side, ca, cb in (("E-/PE-", 0, 1), ("E+/PE+", 4, 3)):
        gaps05 = np.concatenate([connectivity_gap_array(seeds, 0.05, v, ca, cb) for v in (0.1, 0.15, 0.2, 0.3)])
        gaps15 = np.concatenate([connectivity_gap_array(seeds, 0.15, v, ca, cb) for v in (0.1, 0.15, 0.2, 0.3)])
        diff_of_gaps = gaps15 - gaps05
        t, p = stats.ttest_1samp(diff_of_gaps, 0.0)
        d = diff_of_gaps.mean() / diff_of_gaps.std(ddof=1)
        print(f"  {side}: mean(gap@pu0.15)={gaps15.mean():.5f}  mean(gap@pu0.05)={gaps05.mean():.5f}  "
              f"diff-of-gaps={diff_of_gaps.mean():+.5f}  t={t:+.2f}  p={p:.4f}  d={d:+.2f}  n={len(diff_of_gaps)}", flush=True)


def check2_comfort_ratio(seeds, label):
    print(f"\n=== Check 2 [{label}]: is the comfort ratio lower under N_silent, per seed (paired t-test)? ===", flush=True)
    for pu, vcr in CELLS:
        ctrl_subdir = f"{STAGE1_SUBDIR}/{cell_name(pu, vcr)}/control"
        msil_subdir = f"{STAGE1_SUBDIR}/{cell_name(pu, vcr)}/N_silent"
        for reader_cls, author_cls in ((0, 1), (4, 3)):
            c = np.array([per_seed_ratio(s, ctrl_subdir, reader_cls, author_cls) for s in seeds])
            m = np.array([per_seed_ratio(s, msil_subdir, reader_cls, author_cls) for s in seeds])
            valid = ~(np.isnan(c) | np.isnan(m))
            cv, mv = c[valid], m[valid]
            if len(cv) < 2:
                print(f"  p_u={pu} vcr={vcr} reader={reader_cls}: insufficient valid seeds ({len(cv)})", flush=True)
                continue
            t, p = stats.ttest_rel(mv, cv)
            d = (mv - cv).mean() / (mv - cv).std(ddof=1)
            print(f"  p_u={pu} vcr={vcr} reader={reader_cls}: control={cv.mean():.4f}  N_silent={mv.mean():.4f}  "
                  f"t={t:+.2f}  p={p:.4f}  d={d:+.2f}  n={len(cv)}", flush=True)


def check3_split_seed_block(gexf_seeds, comfort_seeds):
    print("\n=== Check 3: split-seed-block robustness (first half vs second half) ===", flush=True)
    half = len(gexf_seeds) // 2
    g1, g2 = gexf_seeds[:half], gexf_seeds[half:]
    print(f"  GEXF halves: {g1} | {g2}", flush=True)
    for label, seeds in (("half A", g1), ("half B", g2)):
        for side, ca, cb in (("E-/PE-", 0, 1), ("E+/PE+", 4, 3)):
            gaps05 = np.concatenate([connectivity_gap_array(seeds, 0.05, v, ca, cb) for v in (0.1, 0.15, 0.2, 0.3)])
            gaps15 = np.concatenate([connectivity_gap_array(seeds, 0.15, v, ca, cb) for v in (0.1, 0.15, 0.2, 0.3)])
            diff = (gaps15 - gaps05).mean()
            print(f"  connectivity gap-of-gaps [{label}, {side}]: {diff:+.5f}", flush=True)

    chalf = len(comfort_seeds) // 2
    c1, c2 = comfort_seeds[:chalf], comfort_seeds[chalf:]
    print(f"  Comfort-ratio halves: {c1} | {c2}", flush=True)
    for label, seeds in (("half A", c1), ("half B", c2)):
        diffs = []
        for pu, vcr in CELLS:
            ctrl_subdir = f"{STAGE1_SUBDIR}/{cell_name(pu, vcr)}/control"
            msil_subdir = f"{STAGE1_SUBDIR}/{cell_name(pu, vcr)}/N_silent"
            for reader_cls, author_cls in ((0, 1), (4, 3)):
                c = np.array([per_seed_ratio(s, ctrl_subdir, reader_cls, author_cls) for s in seeds])
                m = np.array([per_seed_ratio(s, msil_subdir, reader_cls, author_cls) for s in seeds])
                valid = ~(np.isnan(c) | np.isnan(m))
                if valid.sum() >= 2:
                    diffs.append((m[valid] - c[valid]).mean())
        print(f"  comfort-ratio mean diff (N_silent-control), pooled all cells [{label}]: {np.mean(diffs):+.4f}", flush=True)


def check4_independent_pathway(gexf_seeds, comfort_seeds):
    print("\n=== Check 4: independent-pathway cross-check (GEXF connectivity vs feed-composition volume) ===", flush=True)
    gexf_vals, feed_vals = [], []
    for pu, vcr in CELLS:
        g_side = np.concatenate([connectivity_gap_array(gexf_seeds, pu, vcr, 0, 1),
                                  connectivity_gap_array(gexf_seeds, pu, vcr, 4, 3)])
        gexf_vals.append(g_side.mean())

        ctrl_subdir = f"{STAGE1_SUBDIR}/{cell_name(pu, vcr)}/control"
        msil_subdir = f"{STAGE1_SUBDIR}/{cell_name(pu, vcr)}/N_silent"
        vol_diffs = []
        for reader_cls, author_cls in ((0, 1), (4, 3)):
            c_mean = np.mean([per_seed_author_class_mean(s, ctrl_subdir, reader_cls, author_cls) for s in comfort_seeds])
            m_mean = np.mean([per_seed_author_class_mean(s, msil_subdir, reader_cls, author_cls) for s in comfort_seeds])
            vol_diffs.append(m_mean - c_mean)
        feed_vals.append(np.mean(vol_diffs))

    rho, p = stats.spearmanr(gexf_vals, feed_vals)
    print(f"  8-cell GEXF connectivity-gap values: {[f'{v:.5f}' for v in gexf_vals]}", flush=True)
    print(f"  8-cell feed-volume-gap values:       {[f'{v:.3f}' for v in feed_vals]}", flush=True)
    print(f"  Spearman rho={rho:+.3f}  p={p:.4f}  (n=8 cells)", flush=True)


def main():
    print(f"GEXF_SEEDS (n={len(GEXF_SEEDS)}): {GEXF_SEEDS}", flush=True)
    print(f"COMFORT_SEEDS (n={len(COMFORT_SEEDS)}): {COMFORT_SEEDS}", flush=True)
    check1_connectivity_gap_by_pu(GEXF_SEEDS, f"n={len(GEXF_SEEDS)}")
    check2_comfort_ratio(COMFORT_SEEDS, f"n={len(COMFORT_SEEDS)}")
    check3_split_seed_block(GEXF_SEEDS, COMFORT_SEEDS)
    check4_independent_pathway(GEXF_SEEDS, COMFORT_SEEDS)


if __name__ == "__main__":
    main()
