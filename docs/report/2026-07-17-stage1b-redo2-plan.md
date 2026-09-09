# 2026-07-17 Stage 1b 再々calibration(GP+BO)計画

## 背景:前回のstage1b(redo)以降に入った変更

`stage1b_redo_bo_calibration.py`の実行(2026-07-16、`stage1b_redo_bo_evaluations.csv`確定)より**後**に、
feed機構および同化ロジックに3件のコミット前変更が入っている(`git diff`で確認、いずれも未commit)。
Stage 1bの損失関数はfollow-graph構造(Gini/degree exponent/opinionAssortativity)のみを見ているが、
これらは全てhostility/bc/unfollowダイナミクス経由でfollow-graphの均衡形状に影響しうるため、
**再calibrationが必要**と判断する。

1. **`bcGateAssim`の恒久化**(`docs/report/2026-07-16-bc-gated-assimilation-decision.md`で決定・明記済み:
   「これまでのcalibration(stage1a/1b/2のBO評価)は旧挙動下で行われている……再calibrationが必須」)。
   FJ同化が常にbc範囲内投稿のみで平均されるようになった(旧:feed全体で平均)。意見の動きが変わる→
   hostility/unfollow判断が変わる→follow-graph形状が変わる、という経路。
2. **velocityランキングのキャッシュ化**(`AdminOptim.rankByVelocity`、`docs/report/2026-07-16-feed-mechanism-design-review.md`
   issue 1)。再スコアリング間隔を毎step→`round(1/accessProb)`step(既定10step)に変更。For-You側の
   構成が変わりうる。
3. **chrono/For-Youの重複排除を`postId`→`rootPostId`単位に変更**(同issue 4)。同じ投稿が複数の
   followeeにrelayされたとき、従来はchronoスロットに多重に乗り実質的にvelocity加重抽出になっていたのが
   解消された。特に`alpha`(For-You比率)が低い設定でchronoの実効的な多様性が変わる。

3件とも「alpha/hopがfollow-graph構造に与える影響」を直接変える変更であり、前回のBO評価点
(`stage1b_redo_bo_evaluations.csv`)はこれら変更前のダイナミクスで評価されたものなので、**その評価点を
今回のwarm startに使うのは不適切**と考える(GPの事後分布を、もはや存在しないダイナミクスの下でのalpha/hop
依存性に引きずられさせてしまう)。→ 今回は warm start なしで実行する提案。

## 提案:stage1c BOスイープ

前回(`stage1b_redo_bo_calibration.py`)と同一の目的関数・探索空間を踏襲し、warm startのみ外す。

- **ターゲット:** Gini=0.8(scale 0.05)、degree exponent(fit)=2.276(scale 0.3)、
  opinionAssortativity floor=0.6(one-sided, scale 0.15) — 前回と同一
- **探索空間:** `max_follow∈[15,100]`、`follow_prob∈[0.01,0.3]`(log-uniform)、
  `alpha∈[0,1]`、`hop∈{1,...,5}` — 前回と同一
- **N=1000, steps=15000**(前回と同一スケール)
- **ラウンド構成:** 前回同様、5点/ラウンド並列、有望点は複数seedで確認 — ラウンド数は前回3だったが、
  warm startなしで開始点情報が少ないぶん、**4〜5ラウンドに増やすことを提案**(要承認)
- **ログ:** `docs/report/stage1c_bo_evaluations.csv` + このファイルに追記形式で結果サマリ
- **スクリプト:** `scripts/stage1c_bo_calibration.py`(`stage1b_redo_bo_calibration.py`をベースに
  warm_start_points()を除去)

## 決定事項(DECIDED 2026-07-17、ユーザー承認済み)

1. **warm startは外す。** 前回stage1b(redo)の評価点は使わない(上記理由:alpha/hopのfollow-graph構造への
   影響そのものが変わったダイナミクス下の評価点なので、GP事後分布の初期化に使うとバイアスになる)。
2. **ラウンド数は5に増やす**(前回3→5、warm startを外した分の探索補強)。
3. **Stage 2の再calibrationは今回のスコープに含めない。** stage1c完了・follow_prob/max_follow確定後に
   別途プランを立てて着手する。

## stage1c結果(DONE 2026-07-17)

5ラウンド完了、best loss=0.072(`docs/report/stage1c_bo_evaluations.csv`)。

**批判的所見:** best点(round2, seed80013: `max_follow=100.0, follow_prob=0.01, alpha=0.884, hop=5`)は
4次元中3次元が探索空間の境界(`max_follow`上限、`follow_prob`下限、`hop`上限)に張り付いており、
GP事後分布が箱の外を外挿している可能性が高い。この値をそのまま採用しない。

2位の完全に内部にある点(round4, seed80023: `max_follow=29.32, follow_prob=0.0145, alpha=0.763, hop=4`,
loss=0.197, gini=0.808, gamma_fit=2.152, assort=0.664)を暫定候補とし、以下2件を並行実施(ユーザー承認済み):

1. **`scripts/stage1c_confirm_seed80023.py`** — seed80023点を5seed(81000-81004)で確認、
   `docs/report/stage1c_confirm_seed80023.csv`に記録。
2. **`scripts/stage1d_bo_calibration.py`** — 境界が張り付いた3次元のみ拡張した探索空間で再探索:
   `max_follow: [15,100]→[10,200]`、`follow_prob: [0.01,0.3]→[0.003,0.3]`(log-uniform)、
   `hop: [1,5]→[1,8]`(`alpha`は内部点だったため`[0,1]`のまま)。stage1cとstage1dはダイナミクスが
   同一(箱を広げただけ)なので、stage1cの25評価点をそのままwarm startに使う(stage1b_redo→stage1c間の
   warm start除外とは事情が異なる——今回は事後分布のバイアスではなく単なる探索範囲の拡張)。
   結果は`docs/report/stage1d_bo_evaluations.csv`。

## Transparency記録の運用方針(このセッションでの決定)

BOループ本体(長時間実行・nohup前提)は従来通りスクリプト実行 + CSV生ログ + この種の日付付きmarkdown
決定記録、という既存パターンを維持する。今回追加するのは、結果が出た後の**診断・可視化専用のnotebook**
(`scripts/hk_calibration_analysis.py`をベースに、収束曲線・パラメータ×loss散布図をnotebook化)。
理由:BOループ自体をnotebookで書くと長時間実行・セル再実行順序の問題で再現性が損なわれるため、
実行はスクリプトのまま、可視化・探索的診断だけをnotebookに切り出す。得られた結論は最終的に
このmarkdown決定記録に文章として還元し、notebookは「作業過程の記録」、markdownは「決定の記録」という
役割分担にする。

## stage1d結果(DONE 2026-07-17):箱を広げても境界点を上回る点はなし

25新規点(warm start 25点と合わせ計50点)を評価したが、best lossはstage1cの境界点(0.072)から
更新されなかった。上位5点の`follow_prob`は0.0030〜0.0099、`hop`は5〜8、`max_follow`は30〜197と、
拡張した3軸をまんべんなく探索した上でこの結果——**境界張り付き自体は箱の切り詰めアーティファクトでは
なさそうだ、という点は否定された(=真に箱の外に良い点はなかった)**。

## 5seed確認結果(DONE 2026-07-17):単一seed評価は信頼できない、boundary点はfloorを安定して満たさない

`stage1c_confirm_seed80023.py`(内部点)と`stage1c_confirm_seed80013.py`(境界点)をそれぞれ5seedで
実行(`docs/report/stage1c_confirm_seed80023.csv`, `stage1c_confirm_seed80013.csv`)。

| 候補 | パラメータ | 単一seed loss(元のBO評価) | 5seed loss (mean±std) | gini (mean±std) | gamma (mean±std) | assort (mean±std) | floor(0.6)超え回数 |
|---|---|---|---|---|---|---|---|
| **seed80013(境界)** | max_follow=100, follow_prob=0.01, alpha=0.884, hop=5 | 0.072 | 2.683±3.219 | 0.798±0.021 | 2.332±0.238 | **0.489±0.172** | **1/5** |
| **seed80023(内部)** | max_follow=29.3, follow_prob=0.0145, alpha=0.763, hop=4 | 0.197 | 4.699±1.748 | 0.814±0.024 | 2.357±0.613 | 0.666±0.104 | 4/5 |

**所見:**
1. **単一seedのBO点推定は大きく外れる。** 両候補とも、5seed平均lossは元の単一seed点推定の10〜25倍。
   BOの探索が「たまたま良かったseed」を"最適点"として拾っている可能性が高く、`Optimizer.tell()`に
   1seedしか渡していない現在のBO設計そのものが評価ノイズに弱い(次回以降の設計課題、後述)。
2. **境界点(seed80013)はopinionAssortativity floorを安定して満たさない。** 5seed中4回が0.6を
   下回り、うち1回(seed82002)は0.163という壊滅的な値——これは元の(未redo)Stage 1bで
   `follow_prob=0.01`が引き起こした「follow-graph上に意見構造が全く形成されない」問題
   (`calibration-decisions.md`: assort~0.27)と同じ不安定領域に、feed機構修正後のBOが
   再び迷い込んだ可能性が高い。`follow_prob≈0.01`という値そのものが、Gini/gammaには良くても
   assortativityに関しては本質的に脆弱な領域であるように見える。
3. **内部点(seed80023、follow_prob=0.0145)は相対的に安定。** 5seed中4回floorを超えており、
   giniも0.814と極めて良好。gammaのばらつき(±0.613)はStage 1aから既知のfinite-size fitting
   ノイズと同オーダー。

**推奨(要ユーザー承認):** `seed80023`のパラメータ(`max_follow=29.3, follow_prob=0.0145,
alpha=0.763, hop=4`)をStage 1bの暫定calibrated値として採用する。単一loss値では`seed80013`に
劣るが、`opinionAssortativity floor`という核心的な行動要件("follow graphがType-1的分離状態に
到達できる"という`research-direction.md`の要求)を安定して満たすのはこちらだけであり、単一loss値の
優劣よりもこの制約の安定達成を優先すべきと判断する。

**構造的な留意点(次サイクルへの申し送り):** `follow_prob`が0.01付近で`opinionAssortativity`が
双峰的/不安定になる現象は、feed機構修正の前後で一貫して観測されている。Stage 2以降のBOでは
1点=1seedではなく2〜3seed平均で評価するようループ自体を設計し直すことを検討すべき
(今回のように事後の5seed確認で「実は不採用」と分かるのは非効率)。
