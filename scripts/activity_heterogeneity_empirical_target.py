"""
2026-08-01 -- Individual-level posting-activity heterogeneity: empirical target vs. current
model. Follows up on docs/report/2026-07-31-wssit-era-vs-current-model-diff.md's fifth pass,
which found current-model posting activity is nowhere near heavy-tailed (CV 0.12-0.24) and
flagged this as a previously-uncalibrated axis. This script pulls the individual-level data
underlying Buntain & Snegovaya 2025's EMPIRICAL_POST_BIN_WEIGHTS (Const.java) -- OSF
10.17605/OSF.IO/KQFM6, `_anon_data/tw_handle_to_libcon.csv` joined against
`_anon_data/twitter.2020to2021.matched.counts.parquet` (per-user daily post counts,
2020-01-01 to 2022-01-06) -- to get the actual per-user total-post-count distribution, not just
the per-bin means already hardcoded.

Validated: summing each user's daily counts and grouping by ideological_lean_label reproduces
Const.java's EMPIRICAL_POST_BIN_WEIGHTS exactly (to rounding), confirming this is the same
source and the reconstruction is correct.

Files expected at OSF_DATA_DIR (fetched via OSF API, see chat history for the retrieval path):
  tw_handle_to_libcon.csv, twitter.2020to2021.matched.counts.parquet
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OSF_DATA_DIR = "/private/tmp/claude-503/-Users-tomoyatakeda-Documents-polarized-vocal-minority-model/c5867d67-821c-4a23-9e79-41106f81b807/scratchpad/osf_data"
CUR_DIR = "/Users/tomoyatakeda/Documents/polarized-vocal-minority-model/results"
TAG = "ext-NONE_nmod-0_size-LARGEST_ch-BOTH"
CUR_SEEDS = [100, 101, 102, 103, 104]

COLOR_EMPIRICAL = "#eb6834"  # orange -- real Twitter (Buntain & Snegovaya 2025)
COLOR_CURRENT = "#2a78d6"    # blue -- current model
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

BIN_ORDER = ["1 Very liberal", "2 Liberal", "3 Somewhat liberal", "4 Middle of the road",
             "5 Somewhat conservative", "6 Conservative", "7 Very conservative"]


def load_empirical_activity():
    libcon = pd.read_csv(f"{OSF_DATA_DIR}/tw_handle_to_libcon.csv")
    counts = pd.read_parquet(f"{OSF_DATA_DIR}/twitter.2020to2021.matched.counts.parquet")
    total_posts = counts.sum(axis=1)
    total_posts.name = "total_posts"
    merged = libcon.set_index("handle").join(total_posts, how="left").dropna(subset=["total_posts"])
    return merged


def load_simulated_activity(seed):
    base = f"{CUR_DIR}/run_{seed}_{TAG}"
    cascades = pd.read_csv(f"{base}/posts/repost_cascades.csv", usecols=["author", "relayer"])
    lifespan = pd.read_csv(f"{base}/posts/post_lifespan.csv", usecols=["author"])
    n_agents = 1000
    orig_counts = lifespan["author"].value_counts()
    repost_counts = cascades["relayer"].value_counts()
    activity = pd.Series(0, index=range(n_agents), dtype=float)
    activity = activity.add(orig_counts, fill_value=0).add(repost_counts, fill_value=0)
    return activity


def ccdf(pooled):
    s = np.sort(pooled)[::-1]
    n = len(s)
    y = np.arange(1, n + 1) / n
    return s, y


def main():
    empirical = load_empirical_activity()
    print("=== Empirical (Buntain & Snegovaya 2025) per-bin activity stats ===")
    print(f"{'bin':28s} {'n':>5s} {'mean':>10s} {'std':>10s} {'CV':>6s} {'median':>8s}")
    for b in BIN_ORDER:
        sub = empirical[empirical["ideological_lean_label"] == b]["total_posts"]
        print(f"{b:28s} {len(sub):5d} {sub.mean():10.1f} {sub.std():10.1f} "
              f"{sub.std()/sub.mean():6.3f} {sub.median():8.1f}")
    overall = empirical["total_posts"]
    print(f"\nOVERALL empirical: n={len(overall)} mean={overall.mean():.1f} std={overall.std():.1f} "
          f"CV={overall.std()/overall.mean():.3f} median={overall.median():.1f} "
          f"min={overall.min():.0f} max={overall.max():.0f}")

    sim_activity = pd.concat([load_simulated_activity(s) for s in CUR_SEEDS], ignore_index=True)
    print(f"\nOVERALL simulated (current model, pooled 5 seeds): n={len(sim_activity)} "
          f"mean={sim_activity.mean():.1f} std={sim_activity.std():.1f} "
          f"CV={sim_activity.std()/sim_activity.mean():.3f} median={sim_activity.median():.1f} "
          f"min={sim_activity.min():.0f} max={sim_activity.max():.0f}")

    # --- CCDF plot, normalized by each distribution's own mean so the heavy-tail SHAPE
    # (not the raw scale -- different observation windows: ~736 days real vs 40000 steps sim)
    # is what's being compared ---
    fig, ax = plt.subplots(figsize=(7, 5.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    for label, pooled, color in [
        ("Twitter, real (Buntain & Snegovaya 2025)", overall.values, COLOR_EMPIRICAL),
        ("current model (pooled 5 seeds)", sim_activity.values, COLOR_CURRENT),
    ]:
        pooled = pooled[pooled > 0]
        x, y = ccdf(pooled / pooled.mean())
        ax.plot(x, y, color=color, linewidth=2, label=label, solid_capstyle="round")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("posting activity, normalized by population mean (x / mean)", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("P(activity ≥ x)", color=INK_SECONDARY, fontsize=10)
    ax.set_title("Posting-activity heterogeneity: real Twitter vs current model\n(mean-normalized CCDF, log-log)",
                 color=INK, fontsize=11, loc="left")
    ax.grid(True, which="major", color=GRID, linewidth=0.8, zorder=0)
    ax.grid(True, which="minor", color=GRID, linewidth=0.4, alpha=0.6, zorder=0)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#c3c2b7")
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.legend(frameon=False, loc="lower left", fontsize=9, labelcolor=INK_SECONDARY)

    fig.tight_layout()
    out_path = "/Users/tomoyatakeda/Documents/polarized-vocal-minority-model/docs/report/2026-08-01-activity-heterogeneity-ccdf.png"
    fig.savefig(out_path, facecolor=SURFACE)
    print(f"\nCCDF plot saved to {out_path}")


if __name__ == "__main__":
    main()
