#!/usr/bin/env python3
"""Figures for the opinion-distance sweep (scripts/distance_sweep_run.py).  Usage: python3 scripts/plot_distance_sweep.py OUTDIR
Per run (last 2,000 steps for time series, final graph for structure):
  Q_sign      sign-modularity of the follow graph: partition = {X<0, X>=0}; 0 = no camp structure, ~0.5 = two disconnected camps
  own-side    share of follow edges whose two ends have the same sign of intrinsic X (0.5 = sign unrelated to ties, 1 = fully sorted)
  disag_norm  mean over follow edges of (X_i - X_j)^2 / (2 Var X); 1 = X unrelated across ties, 0 = identical"""
import sys, glob, os
import numpy as np, pandas as pd, networkx as nx
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
BETAS = [0, 1, 3, 6]; DISTS = [0.3, 1.0, 2.0]; NETS = [("random", "Random start"), ("hkshuf", "HK degrees, shuffled wiring")]
CH = [(0, 2.0), (3, 1.0), (6, 0.3)]

def load(net, b, d, feed):
    out = []
    for r in sorted(glob.glob(f"results/rsearch/dsw_{net}_b{b}_d{d}_{feed}/run_*")):
        try:
            s = pd.read_csv(r + "/degrees/agent_snapshot_final.csv").set_index("agentId")
            e = pd.read_csv(r + "/degrees/edges_final.csv"); res = pd.read_csv(r + "/metrics/results.csv"); res = res[res.step > res.step.max() - 2000]
            mq = pd.read_csv(r + "/metrics/modularity.csv")
        except Exception: continue
        x = s.intrinsicOpinion; sg = (x >= 0).values
        same = (sg[e.follower.values] == sg[e.followee.values]).mean()
        out.append(dict(q=mq.Q_sign.iloc[-1], own=same, dn=res.disagreement.mean() / (2 * x.var()), assort=res.opinionAssortativity.mean(),
                        s=s, e=e, mix=res[["actionShare_post", "actionShare_like", "actionShare_reshare", "actionShare_rewire"]].mean().values))
    return out

DATA = {(n, b, d, "foryou"): load(n, b, d, "foryou") for n, _ in NETS for b in BETAS for d in DISTS}
DATA.update({(n, b, d, "chrono"): load(n, b, d, "chrono") for n, _ in NETS for b, d in CH})
mean = lambda k, key: np.mean([r[key] for r in DATA[k]]) if DATA[k] else np.nan
rows = [dict(net=k[0], beta_h=k[1], like_max_dist=k[2], feed=k[3], n=len(v), Q_sign=mean(k, "q"), own_side=mean(k, "own"), disag_norm=mean(k, "dn"), assort=mean(k, "assort"),
             p_post=mean(k, "mix")[0] if v else np.nan) if False else dict(net=k[0], beta_h=k[1], like_max_dist=k[2], feed=k[3], n=len(v), Q_sign=mean(k, "q"), own_side=mean(k, "own"),
             disag_norm=mean(k, "dn"), assort=mean(k, "assort")) for k, v in DATA.items()]
pd.DataFrame(rows).to_csv(f"{OUT}/distance_sweep_table.csv", index=False)

# Fig 1: heat-maps (rows beta_h, cols like_max_dist), one row of panels per net, columns = metric
MET = [("q", "Q_sign (0 = no camps, ~0.5 = two camps)", "viridis", 0, 0.5), ("own", "own-side share of follow edges (0.5 = none)", "viridis", 0.5, 1.0), ("dn", "disagreement, normalised (1 = none)", "viridis_r", 0, 1.05)]
fig, axs = plt.subplots(2, 3, figsize=(13, 7))
for i, (net, nm) in enumerate(NETS):
    for j, (key, ttl, cm, lo, hi) in enumerate(MET):
        ax = axs[i, j]; M = np.array([[mean((net, b, d, "foryou"), key) for d in DISTS] for b in BETAS])
        im = ax.imshow(M, cmap=cm, vmin=lo, vmax=hi, aspect="auto")
        for a in range(len(BETAS)):
            for c in range(len(DISTS)):
                ax.text(c, a, f"{M[a, c]:.2f}", ha="center", va="center", color="white" if (M[a, c] - lo) / (hi - lo) < .6 else "black", fontsize=10)
        ax.set_xticks(range(3)); ax.set_xticklabels(["0.3", "1.0", "none"]); ax.set_yticks(range(4)); ax.set_yticklabels(BETAS)
        ax.set_xlabel("like range  like_max_dist"); ax.set_ylabel("distance weight  beta_h")
        ax.set_title(f"{nm} — {ttl}", fontsize=8)
        plt.colorbar(im, ax=ax, fraction=.046)
fig.suptitle("For You 100 %, rewire ON, 20,000 steps, mean of 3 seeds. less distance influence = lower beta_h (up) and wider like range (right)", fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/distance_sweep_heatmaps.png", dpi=150); plt.close(fig)

# Fig 2: Chrono control vs For You at the same cells
fig, axs = plt.subplots(1, 3, figsize=(13, 3.8))
for j, (key, ttl, *_ ) in enumerate(MET):
    ax = axs[j]; w = .38
    for i, (net, nm) in enumerate(NETS):
        for f, hatch in (("foryou", ""), ("chrono", "//")):
            v = [mean((net, b, d, f), key) for b, d in CH]
            ax.bar(np.arange(3) + (i - .5) * w * 1.0 + (0.19 if f == "chrono" else -0.19) * 0.9, v, width=.17, color=["#d62728", "#1f77b4"][i], hatch=hatch, alpha=.9 if f == "foryou" else .5, label=f"{nm}, {f}")
    ax.set_xticks(range(3)); ax.set_xticklabels([f"beta_h {b}, range {'none' if d >= 2 else d}" for b, d in CH], fontsize=7); ax.set_title(ttl, fontsize=8)
    if j == 0: ax.legend(fontsize=6)
fig.suptitle("Control: For You (solid) vs Chrono (hatched) at weakest / baseline / strongest distance influence", fontsize=9)
fig.tight_layout(); fig.savefig(f"{OUT}/distance_sweep_chrono_control.png", dpi=150); plt.close(fig)

# Fig 3: network snapshots (seed 0), one figure per net
for net, nm in NETS:
    fig, axs = plt.subplots(4, 3, figsize=(11, 14.5))
    for a, b in enumerate(BETAS):
        for c, d in enumerate(DISTS):
            ax = axs[a, c]; ax.axis("off"); rs = DATA[(net, b, d, "foryou")]
            if not rs: continue
            r = rs[0]; G = nx.Graph(); G.add_nodes_from(r["s"].index); G.add_edges_from(zip(r["e"].follower, r["e"].followee))
            pos = nx.spring_layout(G, seed=1, iterations=60, k=0.12); xy = np.array([pos[i] for i in r["s"].index])
            nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.04, width=0.3)
            ax.scatter(xy[:, 0], xy[:, 1], c=r["s"].intrinsicOpinion, cmap="coolwarm", vmin=-1, vmax=1, s=4, edgecolors="none")
            ax.set_title(f"beta_h {b}, range {'none' if d >= 2 else d}\nQ_sign {r['q']:.2f}, own-side {r['own']:.2f}", fontsize=8)
    fig.suptitle(f"{nm}: For You follow graph at step 20,000, seed 0 (colour = intrinsic X, blue -1 ... red +1)", fontsize=10)
    fig.tight_layout(); fig.savefig(f"{OUT}/distance_sweep_snapshots_{net}.png", dpi=110); plt.close(fig)
print(pd.DataFrame(rows).round(3).to_string())
