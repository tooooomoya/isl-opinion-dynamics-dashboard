#!/usr/bin/env python3
"""dead_after (L) sweep figure. Columns = Chrono / For You / Trend (hkshuf, standing config). Rows: AE1 CCDF of extra life t = lifetime - (L+1) (seeds pooled),
AE1 again with t / L on the x-axis, AE2 CCDF of reactions received per agent (reshares received, seeds pooled). Dashed = log-normal MLE fit of the extra-life tail.
Usage: python3 scripts/plot_dead_sweep.py OUT.png OUT_table.csv"""
import sys, glob
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm

LS = [10, 25, 50, 100, 200, 400]; FEEDS = [("chrono", "Chrono 100%"), ("foryou", "For You 100%"), ("trend", "Trend 100%")]
CM = plt.get_cmap("viridis"); COL = {L: CM(i / (len(LS) - 1) * 0.9) for i, L in enumerate(LS)}

def runs(L, f):
    return sorted(glob.glob(f"results/rsearch/dsL_hkshuf_L{L}_{f}/run_*"))

def life_hist(L, f):
    tot = {}
    for d in runs(L, f):
        h = pd.read_csv(d + "/metrics/post_life_hist.csv"); h = h[h.kind == "orig"]
        for v, c in zip(h.value.values - (L + 1), h.life.values): tot[v] = tot.get(v, 0) + c
    return tot

def ccdf_from_hist(tot, lo=1):
    v = np.array(sorted(tot)); c = np.array([tot[x] for x in v], float); N = c.sum()
    y = 1 - (np.cumsum(c) - c) / N; s = v >= lo
    return v[s], y[s], v, c

def lognormal_fit(v, c):   # MLE on t >= 1 (discrete values treated as continuous)
    s = v >= 1; x = v[s]; w = c[s]
    if w.sum() < 10: return np.nan, np.nan
    lx = np.log(x); mu = (w * lx).sum() / w.sum(); sd = np.sqrt((w * (lx - mu) ** 2).sum() / w.sum()); return mu, sd

fig, axs = plt.subplots(3, 3, figsize=(15, 12)); rows = []
for j, (f, fl) in enumerate(FEEDS):
    for L in LS:
        if not runs(L, f): continue
        tot = life_hist(L, f); xs, ys, v, c = ccdf_from_hist(tot)
        if len(xs) == 0: continue
        if xs[0] > 1: xs = np.concatenate([[1], xs]); ys = np.concatenate([[ys[0]], ys])
        axs[0, j].loglog(xs, ys, color=COL[L], lw=1.4, drawstyle="steps-pre", label=f"L = {L}")
        axs[1, j].loglog(xs / L, ys, color=COL[L], lw=1.4, drawstyle="steps-pre")
        mu, sd = lognormal_fit(v, c)
        if mu == mu:
            t = np.logspace(0, np.log10(xs.max()), 60); p1 = 1 - norm.cdf((np.log(0.5) - mu) / sd)
            axs[0, j].loglog(t, (1 - norm.cdf((np.log(t) - mu) / sd)) / p1 * ys[0], color=COL[L], lw=.8, ls="--")
        z = c[v == 0].sum() / c.sum() if (v == 0).any() else 0
        rows.append(dict(feed=f, L=L, n_posts=int(c.sum()), frac_no_reaction=round(z, 3), max_extra_life=int(v.max()), lognorm_mu=round(mu, 2), lognorm_sigma=round(sd, 2)))
        recv = []
        for d in runs(L, f):
            rc = pd.read_csv(d + "/metrics/reactions_conv.csv"); n = len(pd.read_csv(d + "/degrees/agent_snapshot_final.csv"))
            a = rc[rc.type == "reshare"].groupby("author")["count"].sum().reindex(range(n), fill_value=0).values; recv.append(a)
        a = np.concatenate(recv); u, n_ = np.unique(a[a > 0], return_counts=True)
        if len(u):
            y2 = (n_.sum() - np.cumsum(n_) + n_) / len(a); x2 = u
            if x2[0] > 1: x2 = np.concatenate([[1], x2]); y2 = np.concatenate([[y2[0]], y2])
            axs[2, j].loglog(x2, y2, color=COL[L], lw=1.4, drawstyle="steps-pre")
    axs[0, j].set_title(fl); axs[0, j].set_xlabel("extra life t = lifetime − (L+1)  (steps)"); axs[1, j].set_xlabel("t / L"); axs[2, j].set_xlabel("reshares received by an agent (last 5,000 steps)")
    if j == 0:
        axs[0, j].set_ylabel("AE1  P(extra life ≥ t)"); axs[1, j].set_ylabel("AE1 rescaled  P(extra life ≥ t)"); axs[2, j].set_ylabel("AE2  P(reshares received ≥ x)"); axs[0, j].legend(fontsize=8)
for r_ in range(3):
    for lim in ("ylim",):
        lo = min(a.get_ylim()[0] for a in axs[r_]); hi = max(a.get_ylim()[1] for a in axs[r_]); [a.set_ylim(lo, hi) for a in axs[r_]]
    lo = min(a.get_xlim()[0] for a in axs[r_]); hi = max(a.get_xlim()[1] for a in axs[r_]); [a.set_xlim(lo, hi) for a in axs[r_]]
fig.suptitle("dead_after (L) sweep, hkshuf: post lifetime and reactions received (solid = data pooled over seeds, dashed = log-normal MLE fit of extra life)", fontsize=11)
plt.tight_layout(); plt.savefig(sys.argv[1], dpi=160); pd.DataFrame(rows).to_csv(sys.argv[2], index=False); print("ok")
