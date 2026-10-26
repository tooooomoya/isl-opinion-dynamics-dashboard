#!/usr/bin/env python3
"""Analysis of the robustness sweep: per setting, mean over seeds of each outcome, the feed contrasts (For You - Chrono,
Trend - Chrono) and their change relative to the baseline (rob_base). Writes docs/report/robustness_stage1.csv and a heat-map PNG.
Usage: python3 scripts/robustness_analysis.py [net]"""
import json, os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
net = sys.argv[1] if len(sys.argv) > 1 else "hk"
OUTC = ["assort", "gini", "fit", "rec", "p_post", "p_like", "p_reshare", "rewire_per_visit", "disag", "disag_norm"]
import glob


def edge_disagreement(jid, seed):
    """mean over follow edges of (X_i - X_j)^2 (logged as `disagreement`), last 2,000 steps; disag_norm = disag / (2 Var X):
    1 = X unrelated across ties (random mixing), 0 = followers identical to followees."""
    f = glob.glob(os.path.join(ROOT, "results/rsearch", jid, f"run_{seed}_*", "metrics", "results.csv"))
    if not f:
        return np.nan, np.nan
    t = pd.read_csv(f[0]).iloc[-2000:]
    return float(t.disagreement.mean()), float(t.disagreement.mean() / (2 * t.opinionVar.mean()))

rows = []
for line in open(os.path.join(ROOT, "results/rsearch/summary.jsonl")):
    d = json.loads(line)
    if not d["id"].startswith("rob_") or d["status"] != "ok":
        continue
    _, param, level, _net, feed = d["id"].split("_", 4) if d["id"].count("_") == 4 else (None,) * 5
    if param is None or _net != net:
        continue
    sh = d["shares"]
    dg, dgn = edge_disagreement(d["id"], d["seed"])
    rows.append({"param": param, "level": level, "feed": feed, "seed": d["seed"], "assort": d["assort"], "gini": d["gini"],
                 "fit": d["fit"], "rec": d["rec"], "p_post": sh["post"], "p_like": sh["like"], "p_reshare": sh["reshare"],
                 "rewire_per_visit": sh.get("rewire", np.nan), "disag": dg, "disag_norm": dgn, "feasible": d["feasible"]})
df = pd.DataFrame(rows)
m = df.groupby(["param", "level", "feed"])[OUTC].mean()
sd = df.groupby(["param", "level", "feed"])[OUTC].std()
n = df.groupby(["param", "level", "feed"]).size().rename("n")
out = []
for (p, l), _ in m.groupby(level=[0, 1]):
    r = {"param": p, "level": l, "n_seeds": int(n.loc[(p, l)].min()) if (p, l) in n.index.droplevel(2) else 0}
    for o in OUTC:
        for f in ["chrono", "foryou", "trend"]:
            r[f"{o}_{f}"] = m.loc[(p, l, f), o] if (p, l, f) in m.index else np.nan
        r[f"{o}_FYvsCH"] = r[f"{o}_foryou"] - r[f"{o}_chrono"]
        r[f"{o}_TRvsCH"] = r[f"{o}_trend"] - r[f"{o}_chrono"]
    out.append(r)
res = pd.DataFrame(out)
base = res[res.param == "base"].iloc[0]
# noise: between-seed sd of the baseline contrast (seeds paired across feeds)
piv = df[df.param == "base"].pivot_table(index="seed", columns="feed", values=OUTC)
noise = {}
for o in OUTC:
    noise[o + "_FYvsCH"] = float((piv[(o, "foryou")] - piv[(o, "chrono")]).std())
    noise[o + "_TRvsCH"] = float((piv[(o, "trend")] - piv[(o, "chrono")]).std())
res.to_csv(os.path.join(ROOT, f"docs/report/robustness_stage1_{net}.csv"), index=False)
pd.Series(noise).to_csv(os.path.join(ROOT, f"docs/report/robustness_stage1_{net}_noise.csv"))

# heat-map of deviations from the baseline in units of the baseline between-seed sd of the same quantity
cols = [c for c in res.columns if c.endswith(("_chrono", "_foryou", "_trend", "_FYvsCH", "_TRvsCH")) and c.split("_")[0] != "n"]
key = [c for c in cols if any(c.startswith(o + "_") for o in ["assort", "disag_norm", "gini", "fit", "rec", "p_post"])]
sdb = df[df.param == "base"].groupby("feed")[OUTC].std()
Z = pd.DataFrame(index=res.index, columns=key, dtype=float)
for c in key:
    o, kind = c.rsplit("_", 1) if c.endswith(("chrono", "foryou", "trend")) else (c.rsplit("_", 1)[0], c.rsplit("_", 1)[1])
    if kind in ("chrono", "foryou", "trend"):
        s = sdb.loc[kind, o]
    else:
        s = noise[c]
    Z[c] = (res[c] - base[c]) / s if s > 0 else np.nan
lab = (res.param + "=" + res.level).values
order = np.argsort(-np.nanmax(np.abs(Z.values), axis=1))
fig, ax = plt.subplots(figsize=(0.45 * len(key) + 4, 0.25 * len(res) + 2))
im = ax.imshow(np.clip(Z.values[order], -6, 6), cmap="RdBu_r", vmin=-6, vmax=6, aspect="auto")
ax.set_yticks(range(len(res))); ax.set_yticklabels(lab[order], fontsize=7)
ax.set_xticks(range(len(key))); ax.set_xticklabels(key, rotation=90, fontsize=7)
fig.colorbar(im, label="(setting - baseline) / baseline seed-sd")
ax.set_title(f"Robustness, {net} start: deviation from baseline in seed-sd units (clipped at +-6)")
fig.tight_layout()
fig.savefig(os.path.join(ROOT, f"docs/report/figures/robustness_stage1_{net}.png"), dpi=150)
print(res[["param", "level", "n_seeds"] + [c for c in res.columns if c.startswith(("assort_", "gini_", "fit_"))][:0]].to_string())
