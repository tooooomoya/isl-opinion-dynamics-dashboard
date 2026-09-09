# 2026-07-13 ダッシュボード: smoothing窓の可変化・seed統一・network structureのカード整理

## 背景

実運用でダッシュボードを触った際の3つの分かりにくさをまとめて解消した。

## 変更内容

1. **smoothingウィンドウを可変に。** `smooth`チェックボックスの移動平均窓は
   `seriesFor`(メイン系列)と`drawFamilyChart`(cRateMean等のクラス別系列)の
   両方で `Math.max(2, Math.round(vals.length/120))` と**同一の式**(常時約120点
   表示になるよう自動決定)だったため、共通ヘルパー`smoothWindow(len)`に切り出し、
   `#smoothWindow`(空欄=auto、2以上の整数を指定するとその値を両方の系列に適用)を
   追加した。`localStorage`の`smoothwin`に永続化。

2. **network snapshot / network structure / agent behaviorのseedを統一。**
   従来、network snapshot・network structureは`netState.seed`(`#netseed`)を
   使う一方、agent behaviorセクションの`repostRow`(repost depth/virality/share)
   だけは`#behSeed`という別セレクタ(実体は上部の「opinion distribution」の
   `#opseed`と同じ値をミラーしているだけ)を使っており、bc/pp distだけがこっそり
   `netState.seed`を参照していた。同じセクション内でセレクタと実際に使われる
   seedが食い違っていて分かりにくかったため、`#behSeed`を廃止し、repostRowも
   `netState.seed`に統一(`state.repost`のfetchも`state.opseed`→`netState.seed`
   ベースに変更)。agent behaviorのh3には`#netseed`を操作する旨の案内と、
   現在のseed/stepを表示する`#attrSeedNote`のみを残した。
   **supersedes**: `#behSeed`によるseed選択(2026-07-11以前の実装)。

3. **agent behavior内で時系列グラフを後方に。** 同セクション内、GEXFスナップショット
   依存の静的分布(bc/pp dist、`attrRow`)を時系列グラフ(repost depth/virality/share、
   `repostRow`)より前に表示するようDOM順を入れ替えた(スナップショット依存かどうかが
   分かりやすいように)。

4. **network structureのカード再編。**
   - 値のみで図を持たない指標(RWC、Hartigan dip、λ<sub>2</sub>、giant component
     fraction)を`renderStructSummary()`で1枚のカード(`.statlist`)に統合。
     従来はこれらが個別カードとして図を持つ指標(clustering histogram、betweenness
     table)と同列に並んでいて、情報密度がバラバラだった。
   - Echo-chamber diet散布図(旧: セクション末尾の素のdiv、カード外・並べ替え不可)を
     `structstats`の並べ替え可能なカード群に編入。structural計算(betweenness等)が
     未完了でも(`op`/`nbrOp`のみ必要なため)描画されるよう、summary/clustering/
     betweennessが値なし("–")表示になる分岐と独立させた。
   - `DEFAULT_ORDER.structstats`: `["rwc","dip","clustering","betweenness","lambda2","giant"]`
     → `["summary","clustering","betweenness","echo"]`。

5. **グリッド線・中間目盛りの追加。** `drawHistChart`(bc/pp分布、clustering係数の
   ヒストグラム)は横グリッド線が皆無で縦軸0/最大値・横軸両端値のみだったのを、
   `ticks()`で縦横とも中間目盛り+横グリッド線を追加。`drawDegreeChart`(次数分布CCDF)
   は縦軸の対数目盛りが軸内側の短いティックのみだったのをカード全幅の横グリッド線に
   変更し、横軸にも中間の対数目盛り(1e1, 1e2, …)を追加。他のグラフ(メイン系列、
   qsign/ei、repost系列、2Dプレーン、opinion分布ヒートマップ)は元から中間目盛りが
   あったため対象外。

6. **カード先頭コンテンツとドラッグハンドルの重なりを解消。** 並べ替え可能なミニ
   カード(`makeCard()`生成、network structure/agent behavior等の全カード)は右上に
   絶対配置のドラッグハンドル(✦)が乗るが、本文の先頭行がその真下から始まっていたため
   「Random Walk Controversy」の値のように隠れるケースがあった。`makeCard()`の本文に
   `cardbody-pad`クラス(`padding-top:14px`)を追加して対応。ネットワークsnapshot
   canvas・2Dプレーン・opinion分布ヒートマップ等、画面いっぱいに描画する固定カードは
   元々問題がないため対象外(通常の`cardbody`のまま)。

7. **5-classファミリー指標を常にseed間平均で表示。** `drawFamilyChart`(cRateMean等)は
   従来`state.opseed`で選んだ単一seedの生値をクラスごとに描くだけで、メイン指標グリッドの
   「show mean」トグルとは無関係だった。単一seedはクラス別値のノイズが大きいため、
   トグルの状態に関わらず常に可視seed全体の平均±SE(`computeMeanSE`/`seBandPath`を
   メイン指標グリッドと共用)を表示するよう変更。タイトルも「seed X」→「mean over N
   seeds」に変更。**supersedes**: family chartが単一`state.opseed`に依存する挙動
   (2026-07-11以前の実装)。

8. **新指標ファミリー `postShare_0..4`(vocal-minority readout)を追加。**
   `src/analysis/Analysis.java`に`computePostShareArray(Agent[])`を新設: その step の
   オリジナル投稿(`postCash` — repostと操作ハブの投稿を除く、`postOpinionVar`と同じ母集団)
   のうち各意見ビンクラスが占める割合を計算。`OpinionDynamics.buildMetricsRow`で
   `cRateMean_i`/`highComfortRateNum_i`と同じ並びで`postShare_i`として出力。
   cRateMean(快適さ/受容性)の対になる「発話量(声の大きさ)」指標で、
   `docs/research-direction.md`の"vocal moderate"論点に直結。ダッシュボード側は
   `DEFAULT_METRICS`に`"postShare"`を追加するだけ(family自動検出の仕組みに乗る)。
   **既存run(過去CSV)にはこの列が無いため、新しいシミュレーション実行後でないと
   グラフには現れない。**

## 検証

- `node --check`でJS構文確認。
- ローカルでサーバー起動し、`/api/repost?seed=0`・`/api/network?...&structural=1`が
  従来通りのキー(`rwc`/`dip`/`lambda2`/`giantComponentFrac`/`clustering`/`betweenness`)
  を返すことを確認(`renderStructSummary`が参照するフィールドと整合)。
- `javac`(gephi/openide依存を除く全ソース)で`Analysis.java`/`OpinionDynamics.java`に
  新規エラーが出ないことを確認(このsandboxには元々gephi/openideのjarが無く、その分の
  エラーのみが残ることを確認した — 環境起因で本変更とは無関係)。
- ヘッドレスブラウザ環境が無いため、ドラッグでの並べ替え・カードリサイズ・グリッド線の
  見た目の目視確認は未実施(前回2026-07-12の持ち越し課題と同様)。`postShare`のグラフ
  描画も、新規シミュレーション実行後の実データでの確認が必要。
