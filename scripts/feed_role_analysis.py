#!/usr/bin/env python3
"""Analyze feed_role_compare at agent, position x X, and paired-seed levels."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

import eta_noise_compare as base
from eta_role_by_position import ACTS, COLS, read, tier
from eta_role_by_position_x import dump_csv, xbin

OUT = base.ROOT / "results/feed_role_compare"
REPORT = base.ROOT / "docs/report/2026-10-14-feed-position-x-comparison.md"
FEEDS = ["foryou", "chrono", "trend"]
TIERS = ["0", "1-4", "5-19", "20-49", "50+", "ALL"]


def avg(vals):
    finite = [v for v in vals if v is not None and math.isfinite(v)]
    return statistics.mean(finite) if finite else None


def med(vals):
    finite = [v for v in vals if v is not None and math.isfinite(v)]
    return statistics.median(finite) if finite else None


def sd(vals):
    finite = [v for v in vals if v is not None and math.isfinite(v)]
    return statistics.stdev(finite) if len(finite) > 1 else None


def extract(meta):
    d = Path(meta["run_dir"])
    snap = {int(r["agentId"]): r for r in read(d / "degrees/agent_snapshot_final.csv")}
    assert len(snap) == 1000 and all(r["opinion"] == r["intrinsicOpinion"] for r in snap.values())
    totals = {i: [0, 0, 0] for i in snap}
    halves = {i: [[0, 0, 0], [0, 0, 0]] for i in snap}
    for r in read(d / "metrics/agent_actions.csv"):
        step = int(r["step"])
        if step <= 15000:
            continue
        i = int(r["agentId"])
        for a, c in enumerate(COLS):
            n = int(r[c]); totals[i][a] += n; halves[i][int(step > 17500)][a] += n
    moments = {}
    for r in read(d / "metrics/eta_agents.csv"):
        if int(r["step"]) <= 15000:
            continue
        acc = moments.setdefault(int(r["agentId"]), {})
        for c, v in r.items():
            if c not in ["step", "agentId"]:
                acc[c] = acc.get(c, 0) + float(v)
    qt = {int(r["agentId"]): r for r in read(d / "degrees/q_table_final.csv") if r["state"] == "0"}
    people = []
    for i, r in snap.items():
        n = sum(totals[i]); assert n > 0
        m = moments[i]
        p = {"feed": meta["feed"], "seed": meta["seed"], "agent_id": i,
             "x": float(r["intrinsicOpinion"]), "followers": int(r["followerCount"]),
             "tier": tier(int(r["followerCount"])), "n_visits": n}
        for a, action in enumerate(ACTS):
            p["share_"+action] = totals[i][a]/n
        h = halves[i]
        p["half_agreement"] = (int(max(range(3), key=lambda a: h[0][a]) == max(range(3), key=lambda a: h[1][a]))
                               if min(map(sum, h)) >= 30 else None)
        p["half_policy_tv"] = sum(abs(h[0][a]/sum(h[0])-h[1][a]/sum(h[1])) for a in range(3))/2
        p["mean_reward"] = sum(m["sumR_"+a] for a in ACTS)/sum(m["nR_"+a] for a in ACTS)
        p["all_three_available"] = m["nQ"]/n
        p["snapshot_fit"] = float(r["identityFit"])
        p["snapshot_recognition"] = float(r["recognition"])
        for a in ["post", "reshare"]:
            p["gap_"+a+"_like"] = (m["sumR_"+a]/m["nR_"+a] - m["sumR_like"]/m["nR_like"]
                                    if min(m["nR_"+a], m["nR_like"]) >= 30 else None)
        min_n = min(float(qt[i][c]) for c in COLS)
        p["initialization_retained"] = int((1-0.03)**min_n > 0.05)
        people.append(p)
    edges = sorted((int(r["follower"]), int(r["followee"])) for r in read(d / "degrees/edges_final.csv"))
    digest = hashlib.sha256(json.dumps(edges).encode()).hexdigest()
    cov = [(p["agent_id"], p["x"], p["followers"]) for p in people]
    return people, digest, cov


def summarize(group):
    r = {"n_agents": len(group)}
    for c in ["share_post", "share_like", "share_reshare", "mean_reward", "half_agreement",
              "half_policy_tv", "all_three_available", "snapshot_fit", "snapshot_recognition",
              "initialization_retained"]:
        r[c] = avg([p[c] for p in group])
    for a in ["post", "reshare"]:
        r["gap_"+a+"_like"] = med([p["gap_"+a+"_like"] for p in group])
        r["gap_"+a+"_like_n_agents"] = sum(p["gap_"+a+"_like"] is not None for p in group)
    return r


def aggregate(rows, keys):
    grouped = {}
    for r in rows:
        grouped.setdefault(tuple(r[k] for k in keys), []).append(r)
    result = []
    for key, group in grouped.items():
        item = dict(zip(keys, key)); item["n_seeds"] = len(group)
        if "n_agents" in group[0]:
            item["min_cell_n"] = min(r["n_agents"] for r in group)
        for c in group[0]:
            if c in keys or c == "seed":
                continue
            vals = [r[c] for r in group]
            item[c] = avg(vals); item[c+"_seed_sd"] = sd(vals)
            item[c+"_valid_seeds"] = sum(v is not None and math.isfinite(v) for v in vals)
        result.append(item)
    return result


def write_report(summary, cells, contrasts, complete, x_effects):
    def cell(feed, degree, x, signed=False, cutoffs="thirds"):
        return next(r for r in cells if r["feed"] == feed and r["tier"] == degree
                    and r["x_group"] == x and r["signed"] == signed and r["cutoffs"] == cutoffs)
    def fmt(v, scale=1, precision=1):
        return "—" if v is None else f"{v*scale:.{precision}f}"
    def triple(r):
        return "/".join(fmt(r["share_"+a],100) for a in ACTS)
    lines = ["# 2026-10-14 Feed 100%比較：ネットワーク位置 × X", "",
             "## 実験条件と比較の範囲", "",
             f"{'全15本完了' if complete else '途中集計（未完了）'}。各方式seed 0–4、n=1000、20,000 step、η=0.03、k=20、状態なしbandit、rewire off、X固定。For Youの既存seed 0–2を再利用、残り12本を追加。元のeta実験の凍結ソースと観測用クラスを使用。", "",
             "現在の完了seed数：" + ", ".join(f"{r['feed']}={r['n_seeds']}" for r in summary) + "。", "",
             "- For You：100%・5 hop・β=10・更新するX̂への適合による確率抽出。",
             "- Trend：100%・5 hop・再共有速度に基づく優先順位と距離による受理確率。",
             "- Chrono：100%・フォロー先から届く直近のFIFO窓より抽出。現実の新着順ソートではなく、候補窓内はshuffleする現在の実装。",
             "- 他の能動パラメータは固定：τ=0.1、探索率既定0.05、q_init=40、HK(m=15,A=4,pt=0.05)、ρ_L=ρ_R=0.3、寿命200、stock承認報酬、raw適合度、feed容量10、訪問確率0.1。",
             "- For YouとTrendは最大5 hop、距離減衰exp・λ=0.11。Chronoは直接フォロー先の投稿窓であり、候補集合・在庫・順位付けを全て含むフィード方式の総合比較。順位付け単独の因果効果ではない。",
             "- 同じseedのグラフ辺集合と個人別X・フォロワー数を方式間で照合。政策によって乱数消費が変わるため、イベント単位の乱数を対応させた反実仮想実験ではない。",
             "- 評価窓はstep 15001–20000。セル内は個人の行動割合を等重み平均、その後seedを等重み平均。X帯は中央 |X|<1/3、中間 1/3≤|X|<2/3、端 |X|≥2/3。左右別と閾値0.25/0.75も保存。", "",
             "## 全体の結果", "",
             "| Feed | POST/LIKE/RESHARE (%) | 平均報酬 | 適合度 | 承認 | 個人政策JSD | feedサイズ | 空feed率 (%) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['feed']} | {triple(r)} | {fmt(r['mean_reward'],precision=3)} | {fmt(r['meanIdentityFit'],precision=3)} | {fmt(r['meanRecognition'],precision=3)} | {fmt(r['policy_jsd'],precision=3)} | {fmt(r['meanFeedSize'],precision=2)} | {fmt(r['emptyFeedShare'],100,2)} |")
    lines += ["", "### 二軸と個人政策の違い", "",
              "個人の経験的政策分布のJSDをエントロピーで分解した記述指標。群間JSDは群平均政策の差の大きさ（群人数で加重）を表し、個人を群平均へ置換した際に残る政策多様性。因果的な説明率や回帰の決定係数ではない。", "",
              "| Feed | 次数群間JSD | X群間JSD | 次数×X群間JSD | 全個人JSDに対する群間成分 (%) |",
              "|---|---:|---:|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['feed']} | {fmt(r['between_degree_jsd'],precision=4)} | {fmt(r['between_x_jsd'],precision=4)} | {fmt(r['between_degree_x_jsd'],precision=4)} | {fmt(r['between_degree_x_fraction'],100)} |")
    lines += ["", "### 意見・投稿・露出の分散", "",
              "opinionVarは固定された個人X、postOpinionVarは当該stepのオリジナル投稿内容（RESHAREを含まない）、exposureOpinionVarは当該stepに全feedへ届いた内容を露出回数で加重した全体分散。個人内feed分散の平均ではない。値は末尾5000 step平均。", "",
              "| Feed | 個人X分散 | オリジナル投稿分散 | 露出内容分散 | 露出内容平均X |", "|---|---:|---:|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['feed']} | {fmt(r['opinionVar'],precision=3)} | {fmt(r['postOpinionVar'],precision=3)} | {fmt(r['exposureOpinionVar'],precision=3)} | {fmt(r['exposureOpinionMean'],precision=3)} |")
    lines += ["", "## X × フォロワー数：行動配分", "", "各セルはPOST / LIKE / RESHARE (%)。"]
    for feed in FEEDS:
        if not any(r["feed"] == feed for r in cells):
            continue
        lines += ["", f"### {feed}", "", "| フォロワー数 | 中央 | 中間 | 端 |", "|---|---:|---:|---:|"]
        for degree in TIERS[:-1]:
            lines.append("| "+degree+" | "+" | ".join(triple(cell(feed,degree,x)) for x in ["central","middle","edge"])+" |")
    lines += ["", "## X差のseed別再現性", "",
              "同じ次数区間でPOSTの差を比較。+のseed数は処置X帯のPOSTが中央帯より多かったseed数。５seed平均の符号だけで普遍的なX効果とは言わない。", "",
              "| Feed | 階層 | 中間−中央 POST差 (pp) | +のseed数 | 端−中央 POST差 (pp) | +のseed数 |",
              "|---|---|---:|---:|---:|---:|"]
    for feed in FEEDS:
        for degree in ["5-19","20-49","50+","ALL"]:
            group = [r for r in x_effects if r["feed"]==feed and r["tier"]==degree]
            if not group:
                continue
            middle = [r["post_middle_minus_central"] for r in group]
            edge = [r["post_edge_minus_central"] for r in group]
            lines.append(f"| {feed} | {degree} | {fmt(avg(middle),100)} | {sum(v>0 for v in middle)}/{len(middle)} | {fmt(avg(edge),100)} | {sum(v>0 for v in edge)}/{len(edge)} |")
    lines += ["", "## 左右別：フォロワー50+層", "",
              "符号側のセルは少数になり、次数区間内の正確な次数や近隣配置も一致しない。左・右の差をモデルの普遍的な性質として解釈しない。", "",
              "| Feed | X帯 | POST/LIKE/RESHARE (%) | 最少セル人数/seed |", "|---|---|---:|---:|"]
    for feed in FEEDS:
        if not any(r["feed"]==feed for r in cells):
            continue
        for x in ["left_edge","left_middle","central","right_middle","right_edge"]:
            r = cell(feed,"50+",x,True)
            lines.append(f"| {feed} | {x} | {triple(r)} | {r['min_cell_n']} |")
    lines += ["", "## 同じseedでの方式差", "", "符号は処置−For You。各seedの対応セルを引いてからseed平均する。SDは５つのseed差の標準偏差であり、個人を独立な実験単位と扱わない。", "",
              "| Feed−For You | 階層 | X帯 | POST差 (pp) | LIKE差 (pp) | RESHARE差 (pp) | 報酬差 | RESHARE差のseed SD (pp) |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for r in contrasts:
        if r["tier"] in ["0","5-19","50+"] and r["cutoffs"] == "thirds" and not r["signed"]:
            lines.append(f"| {r['feed']} | {r['tier']} | {r['x_group']} | {fmt(r['share_post'],100)} | {fmt(r['share_like'],100)} | {fmt(r['share_reshare'],100)} | {fmt(r['mean_reward'],precision=3)} | {fmt(r['share_reshare_seed_sd'],100)} |")
    lines += ["", "## 持続性・可用性・初期値", "", "前半・後半2500 stepで最多行動が同じ割合。両半窓30訪問以上の個人を対象。標本誤差や固定個人環境を含む。可用率は全３行動を選べた訪問の割合を個人別に計算して平均した値。", "",
              "| Feed | 階層 | X帯 | 最多行動一致率 (%) | ３行動可用率 (%) | 初期値残存>5%の個人 (%) | 最少セル人数/seed |", "|---|---|---|---:|---:|---:|---:|"]
    for feed in FEEDS:
        if not any(r["feed"] == feed for r in cells):
            continue
        for degree in ["0","5-19","50+"]:
            for x in ["central","middle","edge"]:
                r = cell(feed,degree,x)
                lines.append(f"| {feed} | {degree} | {x} | {fmt(r['half_agreement'],100)} | {fmt(r['all_three_available'],100)} | {fmt(r['initialization_retained'],100)} | {r['min_cell_n']} |")
    lines += ["", "## 個人内報酬差", "", "両行動30更新以上の個人のみを対象に、セル内の中央値をseed平均。選択時の状況・履歴は一致せず、行動の因果的な優劣の証明ではない。", "",
              "| Feed | 階層 | X帯 | POST−LIKE | RESHARE−LIKE | RESHARE比較の対象人数・seed平均 |", "|---|---|---|---:|---:|---:|"]
    for feed in FEEDS:
        if not any(r["feed"] == feed for r in cells):
            continue
        for degree in ["0","5-19","50+"]:
            for x in ["central","middle","edge"]:
                r = cell(feed,degree,x)
                lines.append(f"| {feed} | {degree} | {x} | {fmt(r['gap_post_like'],precision=3)} | {fmt(r['gap_reshare_like'],precision=3)} | {fmt(r['gap_reshare_like_n_agents'])} |")
    lines += ["", "## 解釈上の制限", "",
              "Xは全runで不変なので、集団の意見が変化して分極化したとは言えない。比較するのは行動配分・報酬・投稿と露出の構成である。フォロワー数の層はネットワーク位置の一側面。高次数×X×符号のセルは少数になり、５seed平均だけで安定した普遍的な役割を断定しない。",
              "RESHAREはソース投稿のXを保った自分名義のコピーであり、将来のLIKEはコピー作者の承認になる。端のXを持つノードが再共有しても、再共有内容が端のXであるとは限らない。作者属性の役割分化と内容の分極化を混同しない。",
              "個人別snapshot_fit / snapshot_recognitionは最終訪問の観測であり、末尾窓平均ではない。主要結果の全体適合度・承認はresults.csvの末尾5000 step平均を使用する。", "",
              "## 再現・保存", "",
              "実行：`python3 scripts/feed_role_compare.py --parallel 12`。解析のみ：`python3 scripts/feed_role_analysis.py`。途中集計は未完了と明記し、完了済みrunのみ読む。",
              "`results/feed_role_compare/manifest.json` に全条件・凍結ソースのハッシュ・compiled classハッシュを保存。run別の完了情報は各feed_s*.json。個人別individuals.csv、run別cells.csv、seed平均cells_aggregate.json、方式差paired_cells.csv / paired_aggregate.json、全体summary.csv / summary_aggregate.json。logs/feed_role_compareに実行ログ。", ""]
    if complete:
        fy, ch, tr = [cell(f,"50+","ALL") for f in FEEDS]
        lines[2:2] = ["## 結論", "",
                      f"全３方式×５seed、15本が完了。フォロワー50+層では、For YouのRESHAREが{fmt(fy['share_reshare'],100)}%、ChronoのPOSTが{fmt(ch['share_post'],100)}%、TrendのPOSTが{fmt(tr['share_post'],100)}%。フィード方式に応じて、高入次数ノードの行動配分が変わる。これはXの符号を含む個人の属性とは別に、同じ初期グラフ・個人Xで確認した方式差である。", "",
                      "X帯の差は階層・方式によって異なり、端ほどオリジナル投稿が増えるという単調な役割分化を前提にしない。下のseed別符号の表と左右別セルで再現性を確認する。群間の行動割合の差は観測された政策の関連であり、個人にとって最適な役割や均衡への収束の証明ではない。", ""]
        if REPORT.exists():
            previous = REPORT.read_text()
            start, end = "## 結果の解釈", "## 実験条件と比較の範囲"
            if start in previous and end in previous:
                interpretation = start + previous.split(start,1)[1].split(end,1)[0]
                index = lines.index(end)
                lines[index:index] = [interpretation.rstrip(), ""]
            figure_start, figure_end = "<!-- feed-role-figures:start -->", "<!-- feed-role-figures:end -->"
            if figure_start in previous and figure_end in previous:
                gallery = figure_start + previous.split(figure_start,1)[1].split(figure_end,1)[0] + figure_end
                index = next((i for i,v in enumerate(lines) if v.startswith("## 結果の解釈")),lines.index(end))
                lines[index:index] = [gallery, ""]
    REPORT.write_text("\n".join(lines))


def main():
    metas = [json.loads(p.read_text()) for p in sorted(OUT.glob("*_s*.json"))]
    if not metas:
        return
    individuals, cells, summaries, graph_hashes, covariates = [], [], [], {}, {}
    for meta in metas:
        people, digest, cov = extract(meta)
        seed = meta["seed"]
        assert graph_hashes.setdefault(seed,digest) == digest, "Graphs differ across feeds"
        assert covariates.setdefault(seed,cov) == cov, "X or degree differs across feeds"
        individuals.extend(people)
        report = base.analyze_run(meta); report.pop("eta"); report["feed"] = meta["feed"]
        # Entropy decomposition of observed individual policies (equal agent weights).
        # Between-cell JSD is a descriptive association, not causal explained variance.
        pbar = [avg([p["share_"+a] for p in people]) for a in ACTS]
        for label, keyfunc in [("degree",lambda p:p["tier"]),
                               ("x",lambda p:xbin(p["x"],1/3,2/3)),
                               ("degree_x",lambda p:(p["tier"],xbin(p["x"],1/3,2/3)))]:
            groups = {}
            for p in people:
                groups.setdefault(keyfunc(p),[]).append(p)
            conditional_entropy = 0.0
            for group in groups.values():
                pg = [avg([p["share_"+a] for p in group]) for a in ACTS]
                conditional_entropy += len(group)/len(people)*base.entropy(pg)
            report["between_"+label+"_jsd"] = base.entropy(pbar)-conditional_entropy
        report["between_degree_x_fraction"] = report["between_degree_x_jsd"]/report["policy_jsd"] if report["policy_jsd"]>0 else None
        metrics = [r for r in base.read(Path(meta["run_dir"])/"metrics/results.csv") if r["step"] > 15000]
        assert max(r["step"] for r in metrics) == 20000 and meta["assert_errors"] == 0
        # Verify that the selected channel is actually pure in the delivered feed.
        channels = {"foryou":"ForYou", "chrono":"Chrono", "trend":"Trend"}
        for inactive, suffix in channels.items():
            if inactive != meta["feed"]:
                assert all(r[f"feed{suffix}CountMean_{cls}"] == 0 for r in metrics for cls in range(5)), (meta["feed"],inactive)
        for c in ["postOpinionVar", "exposureOpinionVar", "opinionVar", "exposureOpinionMean"]:
            report[c] = avg([r[c] for r in metrics])
        summaries.append(report)
        for lo, hi, spec in [(1/3,2/3,"thirds"),(.25,.75,"quarters")]:
            for signed in [False, True]:
                groups = {}
                for p in people:
                    for degree in [p["tier"], "ALL"]:
                        for label in [xbin(p["x"],lo,hi,signed),"ALL"]:
                            groups.setdefault((degree,label),[]).append(p)
                for (degree,label), group in groups.items():
                    cells.append({"feed": meta["feed"], "seed": seed, "cutoffs": spec,
                                  "signed": signed, "tier": degree, "x_group": label, **summarize(group)})
        for degree in TIERS[:-1]:
            relevant = [r for r in cells if r["feed"] == meta["feed"] and r["seed"] == seed
                        and r["tier"] == degree and r["cutoffs"] == "thirds" and not r["signed"] and r["x_group"] != "ALL"]
            group = [p for p in people if p["tier"] == degree]
            assert sum(r["n_agents"] for r in relevant) == len(group)
            for action in ACTS:
                assert abs(sum(r["n_agents"]*r["share_"+action] for r in relevant)/len(group)
                           - avg([p["share_"+action] for p in group])) < 1e-12
    dump_csv(OUT/"individuals.csv",individuals); dump_csv(OUT/"cells.csv",cells)
    dump_csv(OUT/"summary.csv",summaries)
    ca = aggregate(cells,["feed","cutoffs","signed","tier","x_group"])
    sa = aggregate(summaries,["feed"])
    indexed = {(r["feed"],r["seed"],r["cutoffs"],r["signed"],r["tier"],r["x_group"]):r for r in cells}
    paired = []
    for r in cells:
        if r["feed"] == "foryou":
            continue
        key = ("foryou",r["seed"],r["cutoffs"],r["signed"],r["tier"],r["x_group"])
        if key not in indexed:
            continue
        ref = indexed[key]; assert ref["n_agents"] == r["n_agents"]
        diff = {k:r[k] for k in ["feed","seed","cutoffs","signed","tier","x_group"]}
        for c in r:
            if c not in diff:
                diff[c] = r[c]-ref[c] if r[c] is not None and ref[c] is not None else None
        paired.append(diff)
    if paired:
        dump_csv(OUT/"paired_cells.csv",paired)
    pa = aggregate(paired,["feed","cutoffs","signed","tier","x_group"])
    x_effects = []
    for feed in FEEDS:
        for seed in range(5):
            for degree in TIERS:
                primary = {r["x_group"]:r for r in cells if r["feed"]==feed and r["seed"]==seed
                           and r["tier"]==degree and r["cutoffs"]=="thirds" and not r["signed"]}
                if not all(x in primary for x in ["central","middle","edge"]):
                    continue
                row = {"feed":feed,"seed":seed,"tier":degree}
                for a in ACTS:
                    for target in ["middle","edge"]:
                        row[a+"_"+target+"_minus_central"] = primary[target]["share_"+a]-primary["central"]["share_"+a]
                x_effects.append(row)
    dump_csv(OUT/"x_effects.csv",x_effects)
    xa = aggregate(x_effects,["feed","tier"])
    for name,data in [("cells_aggregate",ca),("summary_aggregate",sa),("paired_aggregate",pa),("x_effects_aggregate",xa)]:
        # Diagnostics that are undefined in a cell are represented by null.
        (OUT/(name+".json")).write_text(json.dumps(data,indent=2,allow_nan=False))
    complete = len(metas)==15
    if complete:
        assert len(individuals)==15000 and len(graph_hashes)==5
        assert all(r["n_seeds"]==5 for r in sa)
        assert {(m["feed"],m["seed"]) for m in metas} == {(f,s) for f in FEEDS for s in range(5)}
    (OUT/"validation.json").write_text(json.dumps({"completed_runs":len(metas),"complete":complete,
          "agents":len(individuals),"graph_hashes":graph_hashes,"same_X_degree_per_seed":True,
          "X_cells_reconstruct_degree_means":True},indent=2))
    write_report(sa,ca,pa,complete,x_effects)
    for r in sa:
        print(r["feed"],r["n_seeds"],"seeds", "shares",[round(r["share_"+a],3) for a in ACTS],
              "fit",round(r["meanIdentityFit"],3),"reward",round(r["mean_reward"],3))
    print("Analysis complete:",len(metas),"/15 runs; fixed graphs/X verified.")


if __name__ == "__main__":
    main()
