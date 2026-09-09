# 2026-07-14 Feed構成のcamp(5-bin)別内訳(For-You/chrono, repost/original)を追加

## 背景

Feedサイズが`feedCapacity`(既定10)を常に満たすとは限らない(`PostCash`の充足度、
`accessProb`によるスキップ、For-You候補の枯渇などで実現サイズは0〜capacityの範囲で変動する
— [[research-goal-moderate-conduit]]寄りの議論からの派生)という指摘のレビュー中に、
「Feed内のFor-You経由/Repost経由の投稿数(の平均)を、読み手のopinion camp別に時系列で
見たい」という要望が出た。既存コードには当該内訳のロギングが存在しなかったため新規追加した。

## 設計判断の訂正(初版からの変更点)

初版実装ではcampを`sign(opinion)`の2値と誤って解釈し、比率(share)指標として実装した。
ユーザーからの訂正で判明した正しい要件:

1. **camp = 5-bin `opinionClass`**(`feedPostOpinionMean_i`等の既存binned指標と同じ5分類)。
   2値のsign campではない。
2. 欲しいのは**シェア(比率)ではなく、raw/平均の投稿数そのもの**。「ForYou経由の平均投稿数」
   と「chrono経由の平均投稿数」を**別々の系列として**確認したい、という趣旨
   ("wanna confirm the average num of posts coming from the ForYou algo and those coming
   from existing chrono algo... separately")。片方をもう片方の分母にした比率にする
   必要はなかった。

この訂正により、実装は当初の2値camp・shareベースのバージョン(`_pos`/`_neg`列、
`dashboard/core.py`のDERIVEDシェア4種、`dashboard.html`の専用カード`forYouCamp`/
`repostCamp`)を全てリバートし、以下の5-bin・raw平均ベースの版に置き換えた。
**supersedes**: 本ファイル初版の2値camp・shareベース実装(この訂正コミット内で
リバート済み、履歴には残らない)。

## 実装(確定版)

1. **`StepStats.java`**: population-scoped(pinned hub除外, R1と同じ規約)の
   `double[5]`配列を4本追加。
   `feedForYouCountSum`, `feedChronoCountSum`, `feedRepostCountSum`, `feedOriginalCountSum`
   (各`Const.NUM_OF_BINS_OF_OPINION`長)。分母用に`int[5] feedClassAgentCount`も追加。

2. **`AdminOptim.AdminFeedback()`**: channel provenance(chrono vs For-You)は
   `chrono`/`forYou`をマージしてshuffleした時点で失われ、`Agent.feed`やPostオブジェクト
   自体には保持されない。従って**マージ前**の時点でのみ計測可能。
   `user.getOpinionClass()`でbinを求め、`feedClassAgentCount[cls]++`、
   `forYou.size()`/`chrono.size()`をそのまま`feedForYouCountSum`/`feedChronoCountSum`に
   加算。repost/original内訳のみ`Post.isRelay()`で1件ずつ判定して加算。
   呼び出しシグネチャに`StepStats stepStats`引数を追加(呼び出し元は
   `OpinionDynamics.java`1箇所のみ)。

3. **`OpinionDynamics.buildMetricsRow()`**: `feedPostOpinionMean_i`等と全く同じ
   パターンで、`sum/agentCount`(該当agentが0なら0.0)を`metrics/results.csv`に
   `feedForYouCountMean_0..4`, `feedChronoCountMean_0..4`,
   `feedRepostCountMean_0..4`, `feedOriginalCountMean_0..4`として出力
   (4ファミリー×5列 = 20列)。

4. **ダッシュボード側は無変更**。列名を`_0`〜`_4`のsuffixにしたことで、
   `dashboard/core.py`の`FAMILY_RE`(`^(.+)_([0-4])$`)が自動的に4つのファミリーとして
   検出し、`/api/summary`のfamilies一覧・メトリクスpicker経由で選択可能になる
   (`feedPostOpinionMean`等の既存binned指標と全く同じ経路)。専用の派生比率・
   専用カード・専用JS描画関数は一切追加していない — 既存の`drawFamilyChart`
   (hover tooltip・diverging palette込み)がそのまま使われる。

## 検証

n=200, steps=200のスモークランで実施。
- `metrics/results.csv`に20列が出力され、値は妥当(例:
  `feedForYouCountMean_2=5.0`(=algoSlots上限に到達)、
  `feedChronoCountMean_2=3.22`(chronoSlots上限5に届いていない = PostCash不足の実例)、
  `feedRepostCountMean_2=2.78`, `feedOriginalCountMean_2=5.44`)。
- `dashboard.py --serve`を別ポートで起動し、`/api/summary`の`families`に
  `feedForYouCountMean`, `feedChronoCountMean`, `feedRepostCountMean`,
  `feedOriginalCountMean`の4ファミリー(各5列)が自動検出されることを確認。
- ブラウザでのvisual確認(実際に`drawFamilyChart`で描画されるか)は未実施。

## 既知の注意点

- camp判定は「読み手」の`opinionClass`(feed構築時点)。post自体のクラスではない
  (既存の`Analysis.computeFeedMetrics`と同じ規約)。
- accessProbで今step platformにアクセスしないagentは`AdminFeedback`自体が呼ばれず
  この集計に一切寄与しない(既存のpopulation/activeCount規約と同じ扱い)。
- `feedForYouCountMean_i`が繰り返しalgoSlots上限(`floor(feedAlgoShare*feedCapacity)`)
  に張り付く一方、`feedChronoCountMean_i`がchronoSlots上限に届かない、という非対称は
  まさに直前のFeedサイズ変動レビューで指摘した「chronoはPostCash不足で埋まらないことが
  多いが、For-Youはvelocityランキングの母数さえあれば埋まりやすい」という仮説と整合する
  実例。継続的にウォッチする価値がある。
