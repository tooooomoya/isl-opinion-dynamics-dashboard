"""
2026-08-01 -- Follower-count (in-degree) concentration: CCDF plot + top-1%/5%/10% and
max-hub share of total followers, WSSIT-era (870b318) vs current HEAD. Extends the Gini
finding from docs/report/2026-07-31-wssit-era-vs-current-model-diff.md with the shape of the
distribution, not just its summary inequality statistic.

Follow-network in-degree comes straight from degrees/degree_result_40000.csv (both eras have
this file). Repost-network in-degree: current HEAD has repost_degree_result_40000.csv directly;
WSSIT-era has no such file (the mechanism didn't exist), so it's computed from the exported
repost GEXF's in-degree instead (same approach as the second analysis pass).
"""
import csv
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TAG = "ext-NONE_nmod-0_size-LARGEST_ch-BOTH"
WSSIT_DIR = "/private/tmp/claude-503/-Users-tomoyatakeda-Documents-polarized-vocal-minority-model/c5867d67-821c-4a23-9e79-41106f81b807/scratchpad/wssit_era_worktree/results"
CUR_DIR = "/Users/tomoyatakeda/Documents/polarized-vocal-minority-model/results"
WSSIT_SEEDS = [0, 1, 2, 3, 4]
CUR_SEEDS = [100, 101, 102, 103, 104]

# validated categorical palette (dataviz skill references/palette.md), slots 1 (blue) & 2 (orange)
COLOR_CURRENT = "#2a78d6"
COLOR_WSSIT = "#eb6834"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def load_indeg_csv(path):
    with open(path) as f:
        return np.array([int(r["inDegree"]) for r in csv.DictReader(f)])


def load_indeg_gexf(path):
    G = nx.read_gexf(path)
    return np.array(list(dict(G.in_degree()).values()))


def follow_indeg(base, seed):
    return load_indeg_csv(f"{base}/run_{seed}_{TAG}/degrees/degree_result_40000.csv")


def repost_indeg_current(seed):
    return load_indeg_csv(f"{CUR_DIR}/run_{seed}_{TAG}/degrees/repost_degree_result_40000.csv")


def repost_indeg_wssit(seed):
    return load_indeg_gexf(f"{WSSIT_DIR}/run_{seed}_{TAG}/GEXF/repostNW/repost_step_40000.gexf")


def top_shares(indeg):
    n = len(indeg)
    s = np.sort(indeg)[::-1]
    total = s.sum()
    def share(pct):
        k = max(1, round(n * pct))
        return s[:k].sum() / total
    return dict(top1=share(0.01), top5=share(0.05), top10=share(0.10), max_hub=s[0] / total)


def print_share_table(per_seed_shares, label):
    print(f"\n=== {label} : top-k share of total followers (n={len(per_seed_shares)} seeds) ===")
    for k in ["top1", "top5", "top10", "max_hub"]:
        vals = np.array([s[k] for s in per_seed_shares])
        print(f"  {k:10s}: mean={vals.mean()*100:6.2f}%  std={vals.std()*100:5.2f}%  "
              f"(per-seed %: {['%.1f' % (v*100) for v in vals]})")


def ccdf(pooled):
    s = np.sort(pooled)[::-1]
    n = len(s)
    y = np.arange(1, n + 1) / n
    return s, y


def main():
    wssit_follow = [follow_indeg(WSSIT_DIR, s) for s in WSSIT_SEEDS]
    cur_follow = [follow_indeg(CUR_DIR, s) for s in CUR_SEEDS]
    wssit_repost = [repost_indeg_wssit(s) for s in WSSIT_SEEDS]
    cur_repost = [repost_indeg_current(s) for s in CUR_SEEDS]

    print_share_table([top_shares(d) for d in wssit_follow], "WSSIT-era follow network")
    print_share_table([top_shares(d) for d in cur_follow], "Current HEAD follow network")
    print_share_table([top_shares(d) for d in wssit_repost], "WSSIT-era repost network")
    print_share_table([top_shares(d) for d in cur_repost], "Current HEAD repost network")

    # --- CCDF plot: pooled in-degree across 5 seeds, follow network, both eras ---
    fig, ax = plt.subplots(figsize=(7, 5.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for label, pooled, color in [
        ("WSSIT-era (870b318)", np.concatenate(wssit_follow), COLOR_WSSIT),
        ("current HEAD", np.concatenate(cur_follow), COLOR_CURRENT),
    ]:
        x, y = ccdf(pooled[pooled > 0])
        ax.plot(x, y, color=color, linewidth=2, label=label, solid_capstyle="round")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("follower count (in-degree)", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("P(follower count ≥ x)", color=INK_SECONDARY, fontsize=10)
    ax.set_title("Follower-count CCDF: WSSIT-era vs current model\n(follow network, pooled 5 seeds, step 40000, n=1000/seed)",
                 color=INK, fontsize=11, loc="left")
    ax.grid(True, which="major", color=GRID, linewidth=0.8, zorder=0)
    ax.grid(True, which="minor", color=GRID, linewidth=0.4, alpha=0.6, zorder=0)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#c3c2b7")
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    legend = ax.legend(frameon=False, loc="lower left", fontsize=9, labelcolor=INK_SECONDARY)

    fig.tight_layout()
    out_path = "/Users/tomoyatakeda/Documents/polarized-vocal-minority-model/docs/report/2026-08-01-followdist-ccdf.png"
    fig.savefig(out_path, facecolor=SURFACE)
    print(f"\nCCDF plot saved to {out_path}")


if __name__ == "__main__":
    main()
