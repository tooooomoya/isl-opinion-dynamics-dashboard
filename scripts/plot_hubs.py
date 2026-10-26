#!/usr/bin/env python3
"""Hub analysis figure for the baseline runs (10 seeds, 4 start networks, 3 feeds).
Usage: python3 scripts/plot_hubs.py OUT.png [N=20]
 A  Which opinion classes the top-N hubs (by in-degree) belong to: initial network and the final network of each feed.
 B  Tables (For You): % of a reader's reactions (likes + reshares, last 5,000 steps) that go to one hub of a class, by reader group (neutral / moderate / extreme) x hub class; number of hubs per class written in the row labels."""
import glob, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 20
NETS = [("hk", "Holme–Kim"), ("random", "Random"), ("sbm", "SBM"), ("ws", "Watts–Strogatz")]
FEEDS = [("chrono", "Chrono"), ("foryou", "For You"), ("trend", "Trend")]
CLS = ["−1…−0.6", "−0.6…−0.2", "−0.2…0.2", "0.2…0.6", "0.6…1"]
CCOL = ["#2c5aa0", "#8fb4e3", "#bdbdbd", "#f0a38a", "#c0392b"]
GRP = ["Neutral\n|X|<1/3", "Moderate\n1/3≤|X|<2/3", "Extreme\n|X|≥2/3"]
CONV = 5000


def klass(x):
    return np.minimum(((np.asarray(x) + 1.0) / 0.4).astype(int), 4)


def runs(net, feed):
    return sorted(glob.glob(f"results/rsearch/baseline_{net}_{feed}/run_*"))


def composition(net, feed, n, initial=False):
    out = []
    for d in runs(net, feed):
        s = pd.read_csv(d + "/degrees/agent_snapshot_final.csv"); s0 = pd.read_csv(d + "/degrees/agent_snapshot_t0.csv")
        top = (s0 if initial else s).followerCount.values.argsort(kind="stable")[::-1][:n]
        out.append(np.bincount(klass(s.intrinsicOpinion.values[top]), minlength=5))
    return np.mean(out, axis=0)


def hub_table(net, feed, n):
    """rows = hub class, cols = reader group; value = mean over readers of (% of the reader's reactions that go to the hubs of the class) / (number of hubs in the class)."""
    cells = [[[] for _ in range(3)] for _ in range(5)]; nh = []
    for d in runs(net, feed):
        s = pd.read_csv(d + "/degrees/agent_snapshot_final.csv"); x = s.intrinsicOpinion.values; c = klass(x)
        top = s.followerCount.values.argsort(kind="stable")[::-1][:n]; nk = np.bincount(c[top], minlength=5); nh.append(nk)
        ishub = np.zeros(len(x), bool); ishub[top] = True
        grp = np.where(np.abs(x) < 1 / 3, 0, np.where(np.abs(x) < 2 / 3, 1, 2))
        rc = pd.read_csv(d + "/metrics/reactions_conv.csv"); R = rc[rc["type"].isin(["like", "reshare"])]
        tot = np.bincount(R.actor.values, weights=R["count"].values, minlength=len(x))
        to = np.zeros((len(x), 5))
        m = ishub[R.author.values]
        np.add.at(to, (R.actor.values[m], c[R.author.values[m]]), R["count"].values[m])
        ok = tot > 0
        for k in range(5):
            if nk[k] == 0: continue
            for g in range(3):
                sel = ok & (grp == g)
                cells[k][g].append((to[sel, k] / tot[sel] * 100 / nk[k]).mean())
    val = np.array([[np.mean(cells[k][g]) if len(cells[k][g]) >= 5 else np.nan for g in range(3)] for k in range(5)])
    return val, np.mean(nh, axis=0)


fig = plt.figure(figsize=(16, 13))
gs = fig.add_gridspec(2, 4, hspace=0.55, wspace=0.28, left=0.07, right=0.985, top=0.88, bottom=0.43)
gsb = fig.add_gridspec(1, 4, wspace=0.62, left=0.1, right=0.985, top=0.25, bottom=0.04)


def head(ax, text, dy=0.045):
    fig.text(0.01, ax.get_position().y1 + dy, text, fontsize=11, weight="bold", ha="left")

fig.text(0.01, 0.985, f"Hub analysis  |  baseline runs, 10 seeds, hubs = the {N} agents with the most followers (in-degree)", fontsize=14, ha="left", va="top")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in CCOL]

# A: composition of the top-N hubs -------------------------------------------------------------------------------
for j, (net, nlab) in enumerate(NETS):
    ax = fig.add_subplot(gs[0, j])
    cols = [("initial\nnetwork", composition(net, "chrono", N, initial=True))] + [(lab + "\nfinal", composition(net, f, N)) for f, lab in FEEDS]
    for i, (lab, comp) in enumerate(cols):
        left = 0
        for k in range(5):
            ax.barh(len(cols) - 1 - i, comp[k], left=left, color=CCOL[k], edgecolor="white", height=0.78)
            if comp[k] >= 1.5: ax.text(left + comp[k] / 2, len(cols) - 1 - i, f"{comp[k]:.1f}", ha="center", va="center", fontsize=8, color="white" if k in (0, 4) else "black")
            left += comp[k]
    ax.set_yticks(range(len(cols))); ax.set_yticklabels([c[0] for c in cols][::-1], fontsize=8); ax.set_xlim(0, N); ax.tick_params(axis="x", labelsize=8)
    ax.set_title(nlab, fontsize=12); ax.set_xlabel(f"number of the top-{N} hubs in each author opinion class", fontsize=8)
    if j == 3: ax.legend(handles, CLS, title="author opinion class", ncol=5, fontsize=7, title_fontsize=7, loc="lower right", bbox_to_anchor=(1.0, 1.17), frameon=False, columnspacing=0.8, handlelength=1.2)
    if j == 0: head(ax, f"A  Opinion classes of the top-{N} hubs (mean over 10 seeds): initial network vs the final network of each feed")

# A2: same with the top-50 so the hub definition can be compared ---------------------------------------------------
N2 = 50
for j, (net, nlab) in enumerate(NETS):
    ax = fig.add_subplot(gs[1, j])
    cols = [("initial\nnetwork", composition(net, "chrono", N2, initial=True))] + [(lab + "\nfinal", composition(net, f, N2)) for f, lab in FEEDS]
    for i, (lab, comp) in enumerate(cols):
        left = 0
        for k in range(5):
            ax.barh(len(cols) - 1 - i, comp[k], left=left, color=CCOL[k], edgecolor="white", height=0.78)
            if comp[k] >= 3: ax.text(left + comp[k] / 2, len(cols) - 1 - i, f"{comp[k]:.1f}", ha="center", va="center", fontsize=8, color="white" if k in (0, 4) else "black")
            left += comp[k]
    ax.set_yticks(range(len(cols))); ax.set_yticklabels([c[0] for c in cols][::-1], fontsize=8); ax.set_xlim(0, N2); ax.tick_params(axis="x", labelsize=8)
    ax.set_xlabel(f"number of the top-{N2} hubs in each author opinion class", fontsize=8)
    if j == 0: head(ax, f"A2  Same for the top-{N2} hubs", 0.015)

# B: reaction tables (For You) --------------------------------------------------------------------------------------
for j, (net, nlab) in enumerate(NETS):
    ax = fig.add_subplot(gsb[0, j]); val, nh = hub_table(net, "foryou", N)
    vmax = np.nanmax(val) if np.isfinite(val).any() else 1
    ax.imshow(np.nan_to_num(val), cmap="Blues", vmin=0, vmax=vmax * 1.15, aspect="auto")
    for k in range(5):
        for g in range(3):
            ax.text(g, k, "–" if np.isnan(val[k, g]) else f"{val[k, g]:.1f}", ha="center", va="center", fontsize=10, color="black" if np.isnan(val[k, g]) or val[k, g] < vmax * 0.6 else "white")
    ax.set_xticks(range(3)); ax.set_xticklabels(GRP, fontsize=8); ax.xaxis.tick_top()
    ax.set_yticks(range(5)); ax.set_yticklabels([f"{CLS[k]}\nn = {nh[k]:.1f} hubs" for k in range(5)], fontsize=8)
    ax.set_title(nlab, fontsize=12, pad=38)
    if j == 0: head(ax, f"B  For You: % of a reader's reactions (likes + reshares, last {CONV:,} steps) that go to ONE hub of the class, by reader group (columns) x hub class (rows), top-{N} hubs", 0.09)
    if j == 0: fig.text(0.01, ax.get_position().y1 + 0.06, "n = mean number of top hubs in the class; '–' = fewer than 5 of the 10 seeds have a hub in that class", fontsize=9, ha="left")

plt.savefig(OUT, dpi=200); print("ok")
