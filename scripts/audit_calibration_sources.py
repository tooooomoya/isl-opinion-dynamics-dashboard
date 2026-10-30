#!/usr/bin/env python3
"""Reproduce source-level calibration targets without running the ABM.

Uses pandas/numpy and a parquet engine (pyarrow). Downloads public source files
into results/empirical_source_audit; never executes downloaded notebooks/pickles.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "counts.parquet": "https://osf.io/download/68ee6a97ce3457183271da64/",
    "libcon.csv": "https://osf.io/download/rp2tq/",
    "paired.csv": "https://osf.io/download/68ee6a9f760d11ddd12e792b/",
    "survey_ideology.ipynb": "https://osf.io/download/293da/",
    "twitter_merge.ipynb": "https://osf.io/download/4a23q/",
    "activity_model.ipynb": "https://osf.io/download/68ee6a57cafd9791162e7a0e/",
    "osf_README.md": "https://osf.io/download/vymzx/",
    "conover.zip": "https://zenodo.org/records/4589065/files/icwsm_polarization.zip?download=1",
    "buntain.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12624514/fullTextXML",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "results/empirical_source_audit")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/report/empirical-target-audit-2026-10-27")
    args = parser.parse_args()
    args.source_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, url in SOURCES.items():
        path = args.source_dir / name
        if not path.exists():
            data = urllib.request.urlopen(url, timeout=60).read()
            path.write_bytes(data)
        manifest[name] = {"url": url, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}

    counts = pd.read_parquet(args.source_dir / "counts.parquet")
    labels_raw = pd.read_csv(args.source_dir / "libcon.csv")
    labels = labels_raw.drop_duplicates("handle", keep="first").set_index("handle")
    assert counts.index.is_unique and labels.index.is_unique
    assert set(counts.index) == set(labels.index)
    dates = pd.to_datetime(counts.columns)
    masks = {"full": np.ones(len(dates), dtype=bool), "2020": dates < "2021-01-01",
             "pre_2021_01_08": dates < "2021-01-08", "post_2021_01_08": dates >= "2021-01-08"}
    rng = np.random.default_rng(20261027)
    rows = []
    for window, mask in masks.items():
        joined = labels.join(counts.loc[:, mask].sum(axis=1).rename("total_posts"))
        for name, group in joined.groupby("ideological_lean_label", sort=True):
            values = group.total_posts.to_numpy(dtype=float)
            daily = values / mask.sum()
            boot = rng.choice(daily, size=(5000, len(daily)), replace=True).mean(axis=1)
            lo, hi = np.quantile(boot, [.025, .975])
            rows.append({"window": window, "bin": name, "n_people": len(values), "n_days": int(mask.sum()),
                         "mean_total_posts": values.mean(), "mean_posts_per_day": daily.mean(),
                         "median_posts_per_day": np.median(daily), "activity_cv": daily.std(ddof=1) / daily.mean(),
                         "mean_daily_bootstrap_low": lo, "mean_daily_bootstrap_high": hi})
    pd.DataFrame(rows).to_csv(args.output_dir / "activity_targets.csv", index=False)
    local = pd.read_csv(ROOT / "data/empirical/buntain_snegovaya_2025_activity_by_handle.csv")
    expected = counts.sum(axis=1)
    assert np.array_equal(local.total_posts.to_numpy(), expected.reindex(local.handle).to_numpy())
    manifest["activity_audit"] = {"raw_label_rows": len(labels_raw), "unique_people": len(labels),
        "duplicate_rows_removed": int(labels_raw.duplicated("handle").sum()), "daily_counts_shape": list(counts.shape),
        "missing_count_cells": int(counts.isna().sum().sum()), "total_posts_unique_people": float(counts.sum().sum()),
        "local_summary_rows": len(local), "local_summary_duplicate_handles": int(local.duplicated("handle").sum())}

    with zipfile.ZipFile(args.source_dir / "conover.zip") as archive:
        cluster = dict(line.split("\t") for line in archive.read("retweet.nodes").decode().splitlines())
        edges = [tuple(line.split("\t")[:2]) for line in archive.read("retweet.edgelist").decode().splitlines()]
    metrics = {"nodes": len(cluster), "cluster_sizes": dict(collections.Counter(cluster.values()))}
    variants = {"event_weighted_directed": edges, "unique_directed": sorted(set(edges)),
                "unique_undirected": sorted({tuple(sorted(e)) for e in edges})}
    for name, variant in variants.items():
        ko, ki = collections.Counter(), collections.Counter()
        same = 0
        for a, b in variant:
            ko[cluster[a]] += 1
            ki[cluster[b]] += 1
            same += cluster[a] == cluster[b]
        m = len(variant)
        null = (sum((v / (2 * m)) ** 2 for v in (ko + ki).values()) if name == "unique_undirected"
                else sum(ko[c] * ki[c] for c in ko) / m ** 2)
        metrics[name] = {"edges": m, "modularity_published_partition": same / m - null,
                         "cross_cluster_fraction": 1 - same / m}
    (args.output_dir / "conover_targets.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (args.output_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest["activity_audit"], indent=2))
    print(json.dumps(metrics, indent=2))
    print("Wrote", args.output_dir)


if __name__ == "__main__":
    main()
