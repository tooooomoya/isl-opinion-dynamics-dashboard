#!/usr/bin/env python3
"""One-page results figure for the standing configuration (runs baseline_<net>_<feed>, 3 seeds, columns = Chrono / For You / Trend).
Sections: A/B action mix, B2 identity fit (excess over random expectation) and recognition by follower group, P post share by 5 opinion
classes (accumulated over the last 5,000 steps), AE attention economy (post lifetime, reactions received per agent, attention breadth),
C follow network (initial, mid-run, final) and R repost network of the converged window (edges filtered by weight), D-F network statistics.
Variant of plot_std.py for the mixed feed (50 % For You + 50 % Trend, runs baseline_<net>_mix): columns = start networks (HK degree-matched, ER), same sections.
Usage: python3 scripts/plot_mix.py OUT.png"""
import sys, glob
import numpy as np, pandas as pd
import networkx as nx
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

FEEDS = [("hkshuf", "HK degree-matched start"), ("random", "Random (ER) start")]   # columns; ids baseline_<net>_mix
A = ["nPost", "nLike", "nReshare", "nRewire"]; NAMES = ["POST", "LIKE", "RESHARE", "REWIRE"]
COL = ["#2878b5", "#e69f00", "#17866b", "#b279a2"]
FB = [(0, 0, "0 followers"), (1, 4, "1–4"), (5, 19, "5–19"), (20, 49, "20–49"), (50, 10**9, "50+")]
XB = [("Neutral", "|X|<1/3", 0, 1/3), ("Moderate", "1/3≤|X|<2/3", 1/3, 2/3), ("Extreme", "|X|≥2/3", 2/3, 9)]
FCOL = {"hkshuf": "#8e44ad", "random": "#e67e22"}
CLASS_LABELS = ["−1…−0.6", "−0.6…−0.2", "−0.2…0.2", "0.2…0.6", "0.6…1"]
CLASS_COL = ["#2c5aa0", "#8fb4e3", "#bdbdbd", "#f0a38a", "#c0392b"]
CONV = 5000
DEAD = 50   # dead_after of the standing config (since 2026-10-27; 200 before): a post with no reaction lives DEAD + 1 steps


EMPIRICAL_FIT = False   # non-uniform start (gauss_*): expected fit of a random feed = mean similarity to the whole population


def expected_fit(x, pop=None):
    x = np.asarray(x)
    if EMPIRICAL_FIT:
        return 1.0 - np.abs(x[:, None] - np.asarray(pop)[None, :]).mean(axis=1) / 2.0
    return 1.0 - (1.0 + x ** 2) / 4.0


def klass(x):
    return np.minimum(((np.asarray(x) + 1.0) / 0.4).astype(int), 4)


def load(fid):
    runs = []
    for d in sorted(glob.glob(f"results/rsearch/baseline_{fid}_mix/run_*")):
        r = {"dir": d}
        a = pd.read_csv(d + "/metrics/agent_actions.csv")
        r["steps"] = a.step.max()
        a = a[a.step > a.step.max() - CONV].groupby("agentId")[A + (["nLikeGated"] if "nLikeGated" in a.columns else [])].sum()
        r["counts"] = a
        gated = a["nLikeGated"] if "nLikeGated" in a.columns else pd.Series(0, index=a.index)
        shares = a[A][a[A].sum(axis=1) > 0]; r["a"] = shares.div(shares.sum(axis=1), axis=0); r["a"]["gated"] = (gated.loc[shares.index] / shares.sum(axis=1))
        r["s"] = pd.read_csv(d + "/degrees/agent_snapshot_final.csv").set_index("agentId")
        r["s0"] = pd.read_csv(d + "/degrees/agent_snapshot_t0.csv").set_index("agentId")
        r["e0"] = pd.read_csv(d + "/degrees/edges_t0.csv")
        r["em"] = pd.read_csv(d + "/degrees/edges_mid.csv")
        r["ef"] = pd.read_csv(d + "/degrees/edges_final.csv")
        r["rc"] = pd.read_csv(d + "/metrics/reactions_conv.csv")
        r["ph"] = pd.read_csv(d + "/metrics/post_life_hist.csv")
        r["a"]["x"] = r["s"].loc[r["a"].index, "intrinsicOpinion"].abs(); r["a"]["f"] = r["s"].loc[r["a"].index, "followerCount"]
        runs.append(r)
    return runs


def mix(rs, fsel, xsel=None):
    v, n = [], []
    for r in rs:
        a = r["a"]; m = (a.f >= fsel[0]) & (a.f <= fsel[1])
        if xsel: m &= (a.x >= xsel[0]) & (a.x < xsel[1])
        v.append(a[m][A + ["gated"]].mean().values if m.sum() else np.full(5, np.nan)); n.append(m.sum() / 10)
    return np.nanmean(v, axis=0), np.mean(n)


def bars(ax, rows, labels):
    for i, v in enumerate(rows):
        y = len(rows) - 1 - i; left = 0
        for k in range(4):
            ax.barh(y, v[k] * 100, left=left, color=COL[k], edgecolor="white", height=0.8)
            if k == 1 and v[4] > 0:   # gated likes: the part of the LIKE area where the like did nothing (drawn post out of the like range)
                ax.barh(y, v[4] * 100, left=left + (v[1] - v[4]) * 100, color=COL[1], edgecolor="white", height=0.8, hatch="////", alpha=0.55)
            if v[k] >= .07:
                lab = f"{v[k]*100:.0f}" + (f" ({v[4]*100:.0f})" if k == 1 and v[4] >= .02 else "")
                ax.text(left + v[k] * 50, y, lab, ha="center", va="center", color="white", fontsize=7)
            left += v[k] * 100
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(labels[::-1] if labels else [], fontsize=7); ax.set_xlim(0, 100); ax.tick_params(axis="x", labelsize=7)


def gini(v):
    v = np.sort(np.asarray(v, float)); n = len(v); return (2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * v.sum()) if v.sum() > 0 else 0


def graph_of(edges, nodes):
    G = nx.Graph(); G.add_nodes_from(nodes); G.add_edges_from(zip(edges.follower, edges.followee)); return G


def draw(ax, G, pos, x, indeg, alpha=0.04):
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=alpha, width=0.3)
    xy = np.array([pos[i] for i in G.nodes]); xs = np.array([x[i] for i in G.nodes]); sz = np.array([indeg.get(i, 0) for i in G.nodes])
    ax.scatter(xy[:, 0], xy[:, 1], c=xs, cmap="coolwarm", vmin=-1, vmax=1, s=3 + 4 * np.sqrt(sz), edgecolors="none"); ax.set_axis_off()


def indegree(edges):
    return edges.followee.value_counts().to_dict()


def attention_stats(r):
    """Per agent: reactions k, distinct authors, entropy over authors (nats), entropy over the authors' opinion classes (bits)."""
    rc = r["rc"].groupby(["actor", "author"])["count"].sum().reset_index()
    cls = klass(r["s"]["intrinsicOpinion"].values)
    rows = []
    for actor, g in rc.groupby("actor"):
        c = g["count"].values.astype(float); k = c.sum(); p = c / k
        h_auth = -(p * np.log(p)).sum()
        cc = np.bincount(cls[g["author"].values], weights=c, minlength=5); pc = cc[cc > 0] / k
        rows.append((actor, k, len(c), h_auth, -(pc * np.log2(pc)).sum()))
    return pd.DataFrame(rows, columns=["agent", "k", "authors", "H_author", "H_class"]).set_index("agent")


D = {f: load(f) for f, _ in FEEDS}
NSEED = len(D["hkshuf"])
fig = plt.figure(figsize=(15, 80))
hx = lambda a: (0.012 - a.get_position().x0) / a.get_position().width   # axes-fraction x that puts a section header at the figure's left edge
cs = lambda j: slice(3 * j, 3 * j + 3)   # a main panel spans 3 of the 6 grid columns (AE5 split needs 3 sub-panels per 2 columns)
ATTALL = {}
gs = GridSpec(21, 6, figure=fig, height_ratios=[1.15, 1, 1, 1, 1.15, 1.15, 1.9, 1.25, 1.25, 1.25, 1.25, 1.45, 0.5, 1.45, 1.45, 3.6, 3.6, 3.6, 3.6, 2.5, 1.6],
              hspace=0.55, wspace=1.0, left=0.17, right=0.98, top=0.972, bottom=0.01)
fig.text(0.01, 0.992, f"Mixed feed (50 % For You + 50 % Trend)  |  standing config, {NSEED} seeds, converged window = last {CONV:,} steps",
         fontsize=14, ha="left")

LEG_H = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COL] + [plt.Rectangle((0, 0), 1, 1, facecolor=COL[1], alpha=0.55, hatch="////", edgecolor="white")]
LEG_N = NAMES + ["LIKE gated (nothing happens)"]
def rowlegend(ax, y):   # colour legend at the top right of each A / B row so any 3-panel screenshot carries it
    ax.legend(LEG_H, LEG_N, ncol=5, loc="lower right", bbox_to_anchor=(1.0, y), fontsize=6.5, frameon=False, columnspacing=0.8, handlelength=1.2, handletextpad=0.4)

HEAD = dict(fontsize=9.5, weight="bold")
for j, (f, lab) in enumerate(FEEDS):
    R = D[f]
    # A ------------------------------------------------------------------------------------------------
    ax = fig.add_subplot(gs[0, cs(j)]); rows = [mix(R, (lo, hi)) for lo, hi, _ in FB]
    bars(ax, [x[0] for x in rows], [f"{l}\n{x[1]:.1f}% of pop. (final)" for (_, _, l), x in zip(FB, rows)]); ax.set_title(lab, fontsize=12)
    if j == 1: rowlegend(ax, 1.13)
    if j == 0: ax.text(hx(ax), 1.42, f"A  Action mix by follower group (executed actions, last {CONV:,} steps only = converged window)\nhatched = gated likes (post out of range, nothing happened; in brackets)\n% of pop. = share of agents in the group at the final snapshot (step 20,000), specific to each feed", transform=ax.transAxes, **HEAD)
    # B ------------------------------------------------------------------------------------------------
    for i, (nm, rng, lo, hi) in enumerate(XB):
        ax = fig.add_subplot(gs[1 + i, cs(j)]); rows = [mix(R, (flo, fhi), (lo, hi)) for flo, fhi, _ in FB]
        bars(ax, [x[0] for x in rows], [f"{l}\n{x[1]:.1f}%" for (_, _, l), x in zip(FB, rows)])
        if j == 0: ax.set_ylabel(f"{nm}\n{rng}", fontsize=9, rotation=0, labelpad=88, va="center")
        if i == 0 and j == 0: ax.text(hx(ax), 1.15, f"B  Action mix by |X| group × follower group, executed actions in the last {CONV:,} steps only (the converged window)", transform=ax.transAxes, **HEAD)
        if j == 1: rowlegend(ax, 1.02)
        if i == 2: ax.set_xlabel("Action share (%)", fontsize=8)
    # B2 -----------------------------------------------------------------------------------------------
    for row, (col, ttl) in enumerate([("identityFit", "Identity fit − expected"), ("recognition", "Recognition")]):
        ax = fig.add_subplot(gs[4 + row, cs(j)]); data = []
        for lo, hi, _ in FB:
            vs = []
            for r in R:
                q = r["s"][(r["s"].followerCount >= lo) & (r["s"].followerCount <= hi)]
                vs.append(q[col].values - expected_fit(q.intrinsicOpinion.values, r["s"].intrinsicOpinion.values) if col == "identityFit" else q[col].values)
            data.append(np.concatenate(vs))
        bp = ax.boxplot(data, showfliers=False, patch_artist=True, widths=0.6, medianprops={"color": "black"})
        for b in bp["boxes"]: b.set_facecolor(FCOL[f]); b.set_alpha(.45)
        ax.set_xticks(range(1, 6)); ax.set_xticklabels([l.replace(" followers", "") for _, _, l in FB], fontsize=7)
        if col == "identityFit": ax.set_ylim(-0.6, 0.6); ax.axhline(0, color="black", lw=0.6, ls="--")
        else: ax.set_ylim(0, 1)
        ax.tick_params(axis="y", labelsize=7)
        if j == 0:
            ax.set_ylabel(ttl, fontsize=9)
            if row == 0: ax.text(hx(ax), 1.12, "B2  Identity fit and recognition by follower group (final snapshot; box = IQR, seeds pooled)", transform=ax.transAxes, **HEAD)
        if row == 1: ax.set_xlabel("followers (in-degree)", fontsize=8)
    # P  post share by 5 opinion classes: pie charts + composition + apparent polarization -------------------------
    sub = gs[6, cs(j)].subgridspec(1, 2, width_ratios=[1.6, 1], wspace=0.05)
    ax = fig.add_subplot(sub[0]); sh = []; tot_o = []; tot_r = []; ap = []
    for r in R:
        cls = klass(r["s"].loc[r["counts"].index, "intrinsicOpinion"].values)
        c = np.bincount(cls, weights=r["counts"]["nPost"].values, minlength=5); sh.append(c); tot_o.append(c.sum()); tot_r.append(r["counts"]["nReshare"].sum())
        res = pd.read_csv(r["dir"] + "/metrics/results.csv"); res = res[res.step > res.step.max() - CONV]
        ap.append((res.exposureOpinionVar / res.opinionVar).mean())
    shm = np.mean(sh, axis=0)
    ax.pie(shm, colors=CLASS_COL, autopct=lambda v: f"{v:.0f}%", pctdistance=0.72, textprops={"fontsize": 7}, startangle=90, counterclock=False, wedgeprops={"edgecolor": "white"})
    ax.set_title(f"original posts by author class\n(n = {np.mean(tot_o):,.0f})", fontsize=8)
    if j == 0: ax.legend(CLASS_LABELS, title="author's X", fontsize=6.5, title_fontsize=7, loc="center right", bbox_to_anchor=(0.0, 0.5), frameon=False)
    ax2_ = fig.add_subplot(sub[1]); comp = np.array([np.mean(tot_o), np.mean(tot_r)]); tot = comp.sum()
    ax2_.pie(comp, colors=["#2878b5", "#17866b"], autopct=lambda v: f"{v:.0f}%", pctdistance=0.6, textprops={"fontsize": 7, "color": "white"}, startangle=90, counterclock=False,
             wedgeprops={"edgecolor": "white"})
    ax2_.set_title(f"all posts: {tot:,.0f}", fontsize=8)
    if j == 0: ax2_.legend(["original", "reshare"], fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 0.02), frameon=False, ncol=2)
    ax2_.text(0.5, -0.32, f"apparent polarization\n= {np.mean(ap):.2f}", transform=ax2_.transAxes, ha="center", va="top", fontsize=8, weight="bold")
    if j == 0:
        ax.text(hx(ax), 1.42, f"P  Post share by 5 opinion classes of the author, accumulated over the last {CONV:,} steps (pie), original vs reshared posts, and apparent polarization", transform=ax.transAxes, **HEAD)
        ax.text(hx(ax), 1.27, "apparent polarization = exposureOpinionVar / opinionVar = variance of the posts in agents' feeds ÷ variance of agents' opinions (1 = feeds as spread as the population), mean over the window", transform=ax.transAxes, fontsize=8)
    # AE1 post lifetime ------------------------------------------------------------------------------------
    ax = fig.add_subplot(gs[7, cs(j)])
    for kind, ls in (("orig", "-"), ("copy", "--")):
        for r in R:
            h = r["ph"][r["ph"].kind == kind]; v = h.value.values - (DEAD + 1); c = h.life.values.astype(float)   # a post lives DEAD + 1 steps with no reaction; subtract that
            if c.sum() == 0: continue
            ccdf = 1 - (np.cumsum(c) - c) / c.sum(); sel = v >= 1
            xs, ys = v[sel], ccdf[sel]
            if len(xs) == 0: continue
            if xs[0] > 1: xs = np.concatenate([[1], xs]); ys = np.concatenate([[ys[0]], ys])   # P(extra life >= t) is flat from t = 1 up to the first observed value
            ax.loglog(xs, ys, color=FCOL[f], ls=ls, alpha=.8, lw=1, drawstyle="steps-pre")
    ax.plot([], [], color="black", ls="-", label="original posts"); ax.plot([], [], color="black", ls="--", label="reshared copies"); ax.legend(fontsize=7)
    ax.set_xlabel(f"extra life t = lifetime − {DEAD + 1} (steps a post survives thanks to likes / reshares)", fontsize=8); ax.tick_params(labelsize=7)
    z = np.mean([r["ph"][(r["ph"].kind == "orig") & (r["ph"].value <= DEAD + 1)].life.sum() / max(1, r["ph"][r["ph"].kind == "orig"].life.sum()) for r in R])
    ax.text(0.03, 0.05, f"{z*100:.0f}% of original posts never got a reaction (extra life 0)", transform=ax.transAxes, fontsize=7)
    if j == 0:
        ax.set_ylabel("P(extra life ≥ t)", fontsize=8)
        ax.text(hx(ax), 1.12, f"AE1  Post lifetime beyond the grace period (posts created in the converged window; a post dies once {DEAD} steps pass without a like or reshare)", transform=ax.transAxes, **HEAD)
    # AE2 reactions received per agent -----------------------------------------------------------------------
    ax = fig.add_subplot(gs[8, cs(j)])
    for typ, ls, nm in (("reshare", "-", "reshares received"), ("like", ":", "likes received")):
        for r in R:
            c = r["rc"][r["rc"].type == typ].groupby("author")["count"].sum().reindex(range(len(r["s"])), fill_value=0).values
            u, n = np.unique(c[c > 0], return_counts=True)   # CCDF P(reactions received >= x) over all agents (agents with 0 stay in the denominator)
            if len(u):
                ys = (n.sum() - np.cumsum(n) + n) / len(r["s"]); xs = u
                if xs[0] > 1: xs = np.concatenate([[1], xs]); ys = np.concatenate([[ys[0]], ys])   # flat from x = 1 up to the first observed value
                ax.loglog(xs, ys, color=FCOL[f], ls=ls, alpha=.8, lw=1, drawstyle="steps-pre")
    ax.plot([], [], color="black", ls="-", label="reshares received"); ax.plot([], [], color="black", ls=":", label="likes received"); ax.legend(fontsize=7)
    zero = np.mean([(r["rc"][r["rc"].type == "reshare"].groupby("author")["count"].sum().reindex(range(len(r["s"])), fill_value=0) == 0).mean() for r in R])
    ax.text(0.03, 0.05, f"{zero*100:.0f}% of agents received no reshare", transform=ax.transAxes, fontsize=7)
    ax.set_xlabel("reactions received by an agent (last 5,000 steps)", fontsize=8); ax.tick_params(labelsize=7)
    if j == 0:
        ax.set_ylabel("P(reactions received ≥ x)", fontsize=8)
        ax.text(hx(ax), 1.12, "AE2  Reactions received per agent (a post by the agent that was reshared / liked)", transform=ax.transAxes, **HEAD)
    # AE3/AE4 attention breadth ---------------------------------------------------------------------------
    att = [attention_stats(r) for r in R]
    ATTALL[f] = att
    ax = fig.add_subplot(gs[9, cs(j)]); data = []
    for lo, hi, _ in FB:
        vs = []
        for r, at in zip(R, att):
            fol = r["s"].loc[at.index, "followerCount"]
            vs.append(at.H_author[(fol >= lo) & (fol <= hi)].values)
        data.append(np.concatenate(vs))
    bp = ax.boxplot(data, showfliers=False, patch_artist=True, widths=0.6, medianprops={"color": "black"})
    for b in bp["boxes"]: b.set_facecolor(FCOL[f]); b.set_alpha(.45)
    ax.set_xticks(range(1, 6)); ax.set_xticklabels([l.replace(" followers", "") for _, _, l in FB], fontsize=7); ax.tick_params(axis="y", labelsize=7)
    kmed = np.median(np.concatenate([a.k.values for a in att])); hmed = np.median(np.concatenate([a.H_author.values for a in att])); ax.text(0.5, -0.30, f"median reactions per agent: {kmed:.0f}  |  median S = {hmed:.2f} nats (≈ {np.exp(hmed):.0f} authors)", transform=ax.transAxes, fontsize=7.5, ha="center", va="top")
    ax.set_xlabel("followers (in-degree)", fontsize=8)
    if j == 0:
        ax.set_ylabel("entropy S over authors (nats)", fontsize=8)
        ax.text(hx(ax), 1.12, "AE3  Breadth of attention over authors (Shannon entropy of an agent's likes + reshares across the authors it reacted to)", transform=ax.transAxes, **HEAD)
    ax = fig.add_subplot(gs[10, cs(j)]); data = []
    for _n, _g, lo, hi in XB:
        vs = []
        for r, at in zip(R, att):
            xx = r["s"].loc[at.index, "intrinsicOpinion"].abs()
            vs.append(at.H_class[(xx >= lo) & (xx < hi)].values)
        data.append(np.concatenate(vs))
    bp = ax.boxplot(data, showfliers=False, patch_artist=True, widths=0.6, medianprops={"color": "black"})
    for b in bp["boxes"]: b.set_facecolor(FCOL[f]); b.set_alpha(.45)
    ax.set_xticks(range(1, 4)); ax.set_xticklabels([f"{n}\n{g}" for n, g, _, _ in XB], fontsize=7); ax.set_ylim(0, np.log2(5)); ax.axhline(np.log2(5), color="gray", lw=0.6, ls="--")
    ax.tick_params(axis="y", labelsize=7); ax.set_xlabel("agent's own |X| group", fontsize=8)
    if j == 0:
        ax.set_ylabel("entropy over the authors'\n5 opinion classes (bits)", fontsize=8)
        ax.text(hx(ax), 1.12, "AE4  Breadth of attention over viewpoints (entropy of the opinion classes of the authors an agent reacted to; max 2.32 bits)", transform=ax.transAxes, **HEAD)

# AE5: probability distribution of breadth of attention. Row 11 = all agents pooled; rows 13-14 = split by the agent's own |X| group ---------
def ae5_hist(axa, axb, sel, label_n=False):
    for f, lab in FEEDS:
        ha, hb = [], []
        for r, at in zip(D[f], ATTALL[f]):
            xx = r["s"].loc[at.index, "intrinsicOpinion"].abs().values; m = sel(xx)
            ha.append(at.H_author.values[m]); hb.append(at.H_class.values[m])
        ha = np.concatenate(ha); hb = np.concatenate(hb)
        if len(ha) == 0: continue
        axa.hist(ha, bins=40, range=(0, 7), weights=np.full(len(ha), 1.0 / len(ha)), histtype="step", color=FCOL[f], lw=2, label=f"{lab}  (mean S = {ha.mean():.2f}, n = {len(ha)})")
        axb.hist(hb, bins=30, range=(0, np.log2(5)), weights=np.full(len(hb), 1.0 / len(hb)), histtype="step", color=FCOL[f], lw=2, label=f"{lab}  (mean S = {hb.mean():.2f})")
    axa.legend(fontsize=6.5, loc="upper right"); axb.legend(fontsize=6.5, loc="upper left")
    axa.set_xlabel("S over authors (nats)", fontsize=8); axb.set_xlabel("S over opinion classes of the authors (bits; max 2.32)", fontsize=8)
    axa.tick_params(labelsize=7); axb.tick_params(labelsize=7)

YA = "P(S): share of agents in the bin\n(bin width 0.175 nats)"; YB = "P(S): share of agents in the bin\n(bin width 0.077 bits)"
# pooled
axa = fig.add_subplot(gs[11, 0:2]); axb = fig.add_subplot(gs[11, 2:4]); axc = fig.add_subplot(gs[11, 4:6]); axc.axis("off")
ae5_hist(axa, axb, lambda xx: np.ones(len(xx), bool)); axa.set_ylabel(YA, fontsize=8); axb.set_ylabel(YB, fontsize=8)
axa.set_title("all agents (nats)", fontsize=9, pad=3); axb.set_title("all agents (bits)", fontsize=9, pad=3)
axa.text(hx(axa), 1.2, "AE5  Probability distribution P(S) of the breadth of user attention (entropy S); agents pooled over seeds", transform=axa.transAxes, **HEAD)
axc.text(0, 0.9, "f(i) = share of an agent's likes + reshares\n(last 5,000 steps) that went to author i (nats)\nor to opinion class i of the author (bits).\nLarger S = attention spread over more authors /\nviewpoints; S = 0: everything on one.\nP(S) = share of agents in each bin (sums to 1).\nColour = feed. Below: same, split by the agent's\nown |X| group.", fontsize=8, va="top")
# split by the agent's own |X| group
axh = fig.add_subplot(gs[12, 0:2]); axh.axis("off")
axh.text(hx(axh), 0.15, "AE5 (split)  P(S) by the agent's own |X| group (Neutral / Moderate / Extreme, cut-offs in the panel titles)\ntop row: S over authors (nats); bottom row: S over the authors' opinion classes (bits)", transform=axh.transAxes, **HEAD)
for k, (nm, rng, lo, hi) in enumerate(XB):
    axa = fig.add_subplot(gs[13, 2 * k:2 * k + 2]); axb = fig.add_subplot(gs[14, 2 * k:2 * k + 2])
    ae5_hist(axa, axb, lambda xx, lo=lo, hi=hi: (xx >= lo) & (xx < hi))
    axa.set_title(f"{nm} agents  ({rng})", fontsize=10, pad=4)
    if k == 0: axa.set_ylabel(YA, fontsize=8); axb.set_ylabel(YB, fontsize=8)
for ra in (13, 14):
    axs = [a for a in fig.axes if a.get_subplotspec().rowspan.start == ra]
    y1 = max(a.get_ylim()[1] for a in axs)
    for a in axs: a.set_ylim(0, y1 * 1.35)
for a in [a for a in fig.axes if a.get_subplotspec().rowspan.start == 11 and a.axison]: a.set_ylim(0, a.get_ylim()[1] * 1.35)   # headroom so the legend clears the peak

# C: networks -----------------------------------------------------------------------------------------------
for j, (f, lab) in enumerate(FEEDS):
    r = D[f][0]; nodes = list(r["s"].index); xm = r["s"].intrinsicOpinion.to_dict()
    G0 = graph_of(r["e0"], nodes); pos0 = nx.spring_layout(G0, seed=1, iterations=80, k=0.12)
    ax = fig.add_subplot(gs[15, cs(j)]); draw(ax, G0, pos0, xm, indegree(r["e0"]))
    ax.set_title(f"{lab}: initial network\nedges {len(r['e0']):,}, in-degree Gini {gini(r['s0'].followerCount):.2f}", fontsize=13, pad=8)
    if j == 0: ax.text(hx(ax), 1.22, "C  Follow network: initial, mid-run (step T/2) and final (seed 0; colour = X, size = followers; later layouts continue from the previous positions, so node movement shows rewiring)", transform=ax.transAxes, **HEAD)
    Gm = graph_of(r["em"], nodes); posm = nx.spring_layout(Gm, pos=pos0, seed=1, iterations=40, k=0.12)
    Gf = graph_of(r["ef"], nodes); posf = nx.spring_layout(Gf, pos=posm, seed=1, iterations=40, k=0.12)
    ax = fig.add_subplot(gs[16, cs(j)]); draw(ax, Gm, posm, xm, indegree(r["em"])); ax.set_title(f"{lab}: mid-run", fontsize=13, pad=8)
    ax = fig.add_subplot(gs[17, cs(j)]); draw(ax, Gf, posf, xm, indegree(r["ef"])); ax.set_title(f"{lab}: final", fontsize=13, pad=8)
    rs_ = r["rc"][r["rc"].type == "reshare"]
    w = rs_.groupby(["actor", "author"])["count"].sum().reset_index()
    thr = 2
    while (w["count"] >= thr).sum() > 2500: thr += 1
    keep = w[w["count"] >= thr]
    Gr = nx.Graph(); Gr.add_weighted_edges_from(zip(keep.actor, keep.author, keep["count"]))
    ax = fig.add_subplot(gs[18, cs(j)])
    if Gr.number_of_nodes() > 0:
        posr = nx.spring_layout(Gr, seed=1, iterations=60, k=0.2, weight=None)
        recv = keep.groupby("author")["count"].sum().to_dict()
        nx.draw_networkx_edges(Gr, posr, ax=ax, alpha=0.18, width=0.4)
        xy = np.array([posr[i] for i in Gr.nodes]); ax.scatter(xy[:, 0], xy[:, 1], c=[xm[i] for i in Gr.nodes], cmap="coolwarm", vmin=-1, vmax=1,
                                                              s=4 + 3 * np.sqrt([recv.get(i, 0) for i in Gr.nodes]), edgecolors="none")
    ax.set_axis_off(); ax.set_title(f"{lab}: repost graph\nedges with ≥ {thr} reshares: {len(keep):,} of {len(w):,} pairs ({len(keep)/max(1,len(w))*100:.0f}%)", fontsize=9)
    if j == 0: ax.text(hx(ax), 1.18, f"R  Repost network of the converged window (last {CONV:,} steps; resharer — author of the reshared post; colour = X, size = reshares received)", transform=ax.transAxes, **HEAD)

# D-F -----------------------------------------------------------------------------------------------------
ax1 = fig.add_subplot(gs[19, 0:3]); ax2 = fig.add_subplot(gs[19, 3:6]); ax3 = fig.add_subplot(gs[20, :]); ax3.axis("off")
pass
table = []
for f, lab in FEEDS:
    t0 = np.sort(D[f][0]["s0"].followerCount.values)[::-1]; ax1.loglog(np.arange(1, len(t0) + 1) / len(t0), np.maximum(t0, .5), color=FCOL[f], ls="--", lw=1, label=f"{lab} initial")
    for r in D[f]:
        d_ = np.sort(r["s"].followerCount.values)[::-1]; ax1.loglog(np.arange(1, len(d_) + 1) / len(d_), np.maximum(d_, .5), color=FCOL[f], alpha=.35, lw=1)
    d_ = np.mean([np.sort(r["s"].followerCount.values)[::-1] for r in D[f]], axis=0)
    ax1.loglog(np.arange(1, len(d_) + 1) / len(d_), np.maximum(d_, .5), color=FCOL[f], lw=2, label=lab)
    dx = np.concatenate([np.abs(r["s"].intrinsicOpinion.loc[r["ef"].follower].values - r["s"].intrinsicOpinion.loc[r["ef"].followee].values) for r in D[f]])
    ax2.hist(dx, bins=40, range=(0, 2), density=True, histtype="step", color=FCOL[f], lw=2, label=lab)
    asr = np.mean([np.corrcoef(r["s"].intrinsicOpinion.loc[r["ef"].follower].values, r["s"].intrinsicOpinion.loc[r["ef"].followee].values)[0, 1] for r in D[f]])
    def _edge_sq(r):   # per-run mean of (X_i - X_j)^2 over follow edges, and the same divided by 2 Var(X) over agents
        xi = r["s"].intrinsicOpinion; d2 = ((xi.loc[r["ef"].follower].values - xi.loc[r["ef"].followee].values) ** 2).mean()
        return d2, d2 / (2 * xi.var(ddof=0))
    dg = np.mean([_edge_sq(r) for r in D[f]], axis=0)
    table.append([lab, f"{asr:.2f}", f"{dg[0]:.2f}", f"{dg[1]:.2f}", f"{dx.mean():.2f}", f"{np.mean([r['s'].followerCount.max() for r in D[f]]):.0f}", f"{np.mean([gini(r['s'].followerCount) for r in D[f]]):.2f}",
                  f"{np.mean([(r['s'].followerCount - r['s0'].followerCount.loc[r['s'].index]).abs().mean() for r in D[f]]):.1f}"])
ax1.set_xlabel("rank / N", fontsize=8); ax1.set_ylabel("followers (in-degree)", fontsize=8); ax1.legend(fontsize=7); ax1.set_title("D  In-degree by rank (bold = seed mean)", fontsize=10)
ax2.set_xlabel("|X_follower − X_followee| over follow edges", fontsize=8); ax2.set_ylabel("density", fontsize=8); ax2.legend(fontsize=7); ax2.set_title("E  Follow-edge opinion distance", fontsize=10)
tb = ax3.table(cellText=table, colLabels=["feed", "X-assort.\n(r)", "edge\ndisagr.", "norm.\ndisagr.", "mean\n|Δx|", "max\nin-deg", "in-deg\nGini", "mean |Δ|\nin-deg\nvs t0"], loc="center", cellLoc="center")
tb.auto_set_font_size(False); tb.set_fontsize(6.5); tb.scale(1.0, 2.6); ax3.set_title("F  Follow-network summary (seed mean, final)", fontsize=10)
ax3.text(0.0, 0.0, "X-assort. = Pearson correlation of X over follow edges\n(follower, followee); 1 = followers share their followee's X, 0 = unrelated.\n"
         "edge disagr. = mean over follow edges of (X_follower − X_followee)².\n"
         "norm. disagr. = edge disagr. / (2 Var X): 1 = X unrelated across ties\n(random mixing), 0 = identical; ≈ 1 − X-assort. when the follower and\nfollowee X distributions match.",
         transform=ax3.transAxes, ha="left", va="bottom", fontsize=6, color="#444444")
# the three feed columns of one row share the same axis ranges (AE1 lifetime, AE2 reactions received, AE3 entropy)
for row, both in ((7, True), (8, True), (9, False)):
    axs = [a for a in fig.axes if a.get_subplotspec().rowspan.start == row and a.get_subplotspec().colspan.start in (0, 3) and a.axison]
    if len(axs) == 2:
        y0 = min(a.get_ylim()[0] for a in axs); y1 = max(a.get_ylim()[1] for a in axs)
        for a in axs: a.set_ylim(y0, y1)
        if both:
            x0 = min(a.get_xlim()[0] for a in axs); x1 = max(a.get_xlim()[1] for a in axs)
            for a in axs: a.set_xlim(x0, x1)
plt.savefig(sys.argv[1], dpi=200); print("ok")
