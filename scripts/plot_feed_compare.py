#!/usr/bin/env python3
"""One-page comparison of the three feeds (chrono / For You / Trend), rewire + cost on.
Rows: (1) action mix by follower group, (2) action mix by |X| group x follower group, (3) follow-network snapshot (seed 0, colour = X, size = in-degree),
(4) network statistics (in-degree CCDF, follow-edge |dx| distribution, summary table). Converged window = last 5,000 steps; equal agent weight, equal seed weight.
Usage: python3 scripts/plot_feed_compare.py OUT.png [on|off|nogate|noise=SD]   (off reads fcoff_*, noise=SD reads fcn<SD>_*)"""
import sys, glob
import numpy as np, pandas as pd
import networkx as nx
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

FEEDS = [("chrono", "Chrono 100%"), ("foryou", "For You 100%"), ("trend", "Trend 100%")]
A = ["nPost", "nLike", "nReshare", "nRewire"]; NAMES = ["POST", "LIKE", "RESHARE", "REWIRE"]
COL = ["#2878b5", "#e69f00", "#17866b", "#b279a2"]
FB = [(0, 0, "0 followers"), (1, 4, "1–4"), (5, 19, "5–19"), (20, 49, "20–49"), (50, 10**9, "50+")]
XB = [("Neutral", "|X|<1/3", 0, 1/3), ("Moderate", "1/3≤|X|<2/3", 1/3, 2/3), ("Extreme", "|X|≥2/3", 2/3, 9)]
FCOL = {"chrono": "#555555", "foryou": "#d62728", "trend": "#1f77b4"}

MODE = sys.argv[2] if len(sys.argv) > 2 else "on"
SD = MODE.split("=")[1] if MODE.startswith("noise=") else "0.3"
EXCESS = MODE.startswith("std:")
NETNAME = {"hk": "HOLME-KIM", "random": "RANDOM", "sbm": "SBM"}.get(MODE.split(":")[1] if EXCESS else "", "")
STDNET = MODE.split(":")[1] if EXCESS else None
MODE = "noise" if MODE.startswith("noise") else ("std" if EXCESS else MODE)
PFX, REWTXT = {"std": (f"stdh_{STDNET}", f"{NETNAME} start network, standing config + For You hop term (λ=0.5); identity fit = excess over random expectation"), "on": ("fc", "rewire ON, cost ON (post 0.5 / reshare 0.25 / rewire 1.0)"), "off": ("fcoff", "rewire OFF (static network), cost ON (post 0.5 / reshare 0.25)"),
               "nogate": ("fcng", "rewire ON without the similarity gate, cost ON (post 0.5 / reshare 0.25 / rewire 1.0)"),
               "nogate:random": ("fcng_random", "RANDOM start network, standing config (no gate, cost on)"),
               "nogate:sbm": ("fcng_sbm", "SBM start network (K=4, mean degree 15), standing config (no gate, cost on)"),
               "noise": (f"fcn{SD}", f"rewire ON, cost ON (post 0.5 / reshare 0.25 / rewire 1.0), noisy posts sd {SD}")}[MODE]

def runs(fid):
    out = []
    for d in sorted(glob.glob(f"results/rsearch/{PFX}_{fid}/run_*")):
        a = pd.read_csv(d + "/metrics/agent_actions.csv"); a = a[a.step > a.step.max() - 5000]
        a = a.groupby("agentId")[A].sum(); a = a[a.sum(axis=1) > 0]; a = a.div(a.sum(axis=1), axis=0)
        s = pd.read_csv(d + "/degrees/agent_snapshot_final.csv").set_index("agentId")
        s0 = pd.read_csv(d + "/degrees/agent_snapshot_t0.csv").set_index("agentId")
        e = pd.read_csv(d + "/degrees/edges_final.csv")
        a["x"] = s.loc[a.index, "intrinsicOpinion"].abs(); a["f"] = s.loc[a.index, "followerCount"]
        out.append({"a": a, "s": s, "s0": s0, "e": e})
    return out

def mix(rs, fsel, xsel=None):
    v = []; n = []
    for r in rs:
        a = r["a"]; m = (a.f >= fsel[0]) & (a.f <= fsel[1])
        if xsel: m &= (a.x >= xsel[0]) & (a.x < xsel[1])
        v.append(a[m][A].mean().values if m.sum() else np.full(4, np.nan)); n.append(m.sum() / 10)
    return np.nanmean(v, axis=0), np.mean(n)

def bars(ax, rows, labels):
    for i, v in enumerate(rows):
        y = len(rows) - 1 - i; left = 0
        for k in range(4):
            ax.barh(y, v[k] * 100, left=left, color=COL[k], edgecolor="white", height=0.8)
            if v[k] >= .07: ax.text(left + v[k] * 50, y, f"{v[k]*100:.0f}", ha="center", va="center", color="white", fontsize=7)
            left += v[k] * 100
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(labels[::-1] if labels else [], fontsize=7); ax.set_xlim(0, 100); ax.tick_params(axis="x", labelsize=7)

def gini(v):
    v = np.sort(np.asarray(v, float)); n = len(v); return (2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * v.sum()) if v.sum() > 0 else 0

D = {f: runs(f) for f, _ in FEEDS}
fig = plt.figure(figsize=(16, 31))
gs = GridSpec(8, 3, figure=fig, height_ratios=[1.15, 1, 1, 1, 1.15, 1.15, 3.6, 2.5], hspace=0.42, wspace=0.2, left=0.16, right=0.98, top=0.935, bottom=0.03)
for j, (f, lab) in enumerate(FEEDS):
    ax = fig.add_subplot(gs[0, j]); rows = [mix(D[f], (lo, hi)) for lo, hi, _ in FB]
    bars(ax, [r[0] for r in rows], [f"{l}\n{r[1]:.1f}% of pop." for (_, _, l), r in zip(FB, rows)] if j == 0 else None)
    ax.set_title(lab, fontsize=12)
    if j == 0: ax.text(-0.62, 1.28, "A  Action mix by follower group (last 5,000 steps)", transform=ax.transAxes, fontsize=12, weight="bold")
    for i, (nm, rng, lo, hi) in enumerate(XB):
        ax = fig.add_subplot(gs[1 + i, j]); rows = [mix(D[f], (flo, fhi), (lo, hi)) for flo, fhi, _ in FB]
        bars(ax, [r[0] for r in rows], [f"{l}\n{r[1]:.1f}%" for (_, _, l), r in zip(FB, rows)] if j == 0 else None)
        if j == 0: ax.set_ylabel(f"{nm}\n{rng}", fontsize=9, rotation=0, labelpad=88, va="center")
        if i == 0 and j == 0: ax.text(-0.62, 1.15, "B  Action mix by |X| group × follower group", transform=ax.transAxes, fontsize=12, weight="bold")
        if i == 2: ax.set_xlabel("Action share (%)", fontsize=8)
    for row, (col, ttl) in enumerate([("identityFit", "Identity fit − expected" if EXCESS else "Identity fit"), ("recognition", "Recognition")]):
        ax = fig.add_subplot(gs[4 + row, j]); data = []
        for lo, hi, _ in FB:
            def vals(r):
                q = r["s"][(r["s"].followerCount >= lo) & (r["s"].followerCount <= hi)]
                return q[col].values - (1.0 - (1.0 + q.intrinsicOpinion.values ** 2) / 4.0) if (EXCESS and col == "identityFit") else q[col].values
            data.append(np.concatenate([vals(r) for r in D[f]]))
        bp = ax.boxplot(data, showfliers=False, patch_artist=True, widths=0.6, medianprops={"color": "black"})
        for b in bp["boxes"]: b.set_facecolor(FCOL[f]); b.set_alpha(.45)
        ax.set_xticks(range(1, 6)); ax.set_xticklabels([l.replace(" followers", "") for _, _, l in FB], fontsize=7)
        if EXCESS and col == "identityFit": ax.set_ylim(-0.6, 0.6); ax.axhline(0, color="black", lw=0.6, ls="--")
        else: ax.set_ylim(0, 1)
        ax.tick_params(axis="y", labelsize=7)
        if j == 0:
            ax.set_ylabel(ttl, fontsize=9)
            if row == 0: ax.text(-0.3, 1.12, "B2  Identity fit and recognition by follower group (final snapshot; box = IQR, all seeds pooled)", transform=ax.transAxes, fontsize=12, weight="bold")
        if row == 1: ax.set_xlabel("followers (in-degree)", fontsize=8)
    # network snapshot, seed 0
    r = D[f][0]; G = nx.Graph(); G.add_nodes_from(r["s"].index); G.add_edges_from(zip(r["e"].follower, r["e"].followee))
    pos = nx.spring_layout(G, seed=1, iterations=60, k=0.12)
    ax = fig.add_subplot(gs[6, j]); ind = r["s"].followerCount
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.04, width=0.3)
    xy = np.array([pos[i] for i in r["s"].index])
    ax.scatter(xy[:, 0], xy[:, 1], c=r["s"].intrinsicOpinion, cmap="coolwarm", vmin=-1, vmax=1, s=3 + 4 * np.sqrt(ind), edgecolors="none")
    ax.set_axis_off()
    if j == 0: ax.text(-0.1, 1.02, "C  Follow network, seed 0 (colour = X, size = followers)", transform=ax.transAxes, fontsize=12, weight="bold")
# network stats
ax1 = fig.add_subplot(gs[7, 0]); ax2 = fig.add_subplot(gs[7, 1]); ax3 = fig.add_subplot(gs[7, 2]); ax3.axis("off")
t0 = D["chrono"][0]["s0"].followerCount.values
xs = np.sort(t0)[::-1]; ax1.loglog(np.arange(1, len(xs) + 1) / len(xs), np.maximum(xs, .5), color="#aaaaaa", ls="--", label="initial")
table = []
for f, lab in FEEDS:
    cc = []
    for r in D[f]:
        d_ = np.sort(r["s"].followerCount.values)[::-1]; ax1.loglog(np.arange(1, len(d_) + 1) / len(d_), np.maximum(d_, .5), color=FCOL[f], alpha=.35, lw=1)
    d_ = np.mean([np.sort(r["s"].followerCount.values)[::-1] for r in D[f]], axis=0)
    ax1.loglog(np.arange(1, len(d_) + 1) / len(d_), np.maximum(d_, .5), color=FCOL[f], lw=2, label=lab)
    dx = np.concatenate([np.abs(r["s"].intrinsicOpinion.loc[r["e"].follower].values - r["s"].intrinsicOpinion.loc[r["e"].followee].values) for r in D[f]])
    ax2.hist(dx, bins=40, range=(0, 2), density=True, histtype="step", color=FCOL[f], lw=2, label=lab)
    asr = np.mean([np.corrcoef(r["s"].intrinsicOpinion.loc[r["e"].follower].values, r["s"].intrinsicOpinion.loc[r["e"].followee].values)[0, 1] for r in D[f]])
    table.append([lab.replace(" 100%",""), f"{asr:.2f}", f"{dx.mean():.2f}", f"{np.mean([r['s'].followerCount.max() for r in D[f]]):.0f}", f"{np.mean([gini(r['s'].followerCount) for r in D[f]]):.2f}",
                  f"{np.mean([(r['s'].followerCount - r['s0'].followerCount.loc[r['s'].index]).abs().mean() for r in D[f]]):.1f}"])
ax1.set_xlabel("rank / N", fontsize=8); ax1.set_ylabel("followers (in-degree)", fontsize=8); ax1.legend(fontsize=7); ax1.set_title("D  In-degree by rank (bold = seed mean)", fontsize=10)
ax2.set_xlabel("|X_follower − X_followee| over follow edges", fontsize=8); ax2.set_ylabel("density", fontsize=8); ax2.legend(fontsize=7); ax2.set_title("E  Follow-edge opinion distance", fontsize=10)
tb = ax3.table(cellText=table, colLabels=["feed", "X-assort.", "mean\n|Δx|", "max\nin-deg", "in-deg\nGini", "mean |Δ|\nin-deg vs t0"], loc="center", cellLoc="center")
tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1.05, 2.6); ax3.set_title("F  Follow-network summary (seed mean, final)", fontsize=10)
h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COL]
fig.legend(h, NAMES, ncol=4, loc="upper right", fontsize=10, frameon=False, bbox_to_anchor=(0.98, 0.972))
fig.suptitle(f"Feed algorithm comparison  |  {REWTXT}, α=0.5, 10 seeds", x=0.01, ha="left", fontsize=14, y=0.985)
plt.savefig(sys.argv[1], dpi=110); print("ok")
