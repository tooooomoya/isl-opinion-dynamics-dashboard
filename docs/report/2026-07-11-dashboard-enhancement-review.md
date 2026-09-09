# 2026-07-11 — ダッシュボード強化レビュー(opinion dynamics研究品質の観点)

> **【決定 2026-07-11(同日追記)— Tier 2のみ採用、指導原理を修正】**
> ユーザー判断: ダッシュボードは**この実験の意思決定装置ではなく、opinion dynamicsモデル一般に
> 使える汎用監視ツール**を目指す。したがって本文の指導原理(「Step-2/3の判断ループ短縮に寄与するか」)は
> **却下**され、正しい価値基準は「**opinion dynamicsモデル一般に転用可能な指標・可視化か**」。
> - **採用(実装する):** Tier 2 全項目 — RWC、Hartigan dip、エコーチェンバー散布図(Cinelli型)、
>   structural virality、powerlaw fitのlognormal比較。いずれもモデル非依存の汎用指標。
> - **却下:** Tier 1(Step-2ゲート固有の診断)、Tier 3(この実験のsweep設計に固有のビュー)。
>   Tier 4は未決(汎用性はあるが今回のスコープ外)。
> - 実装ノート: dip統計量は既存GPL実装(unidip/diptest)をベンダリングせず、公開アルゴリズム
>   (Hartigan & Hartigan 1985)から自前実装し、C参照実装(diptestパッケージ、使い捨てvenvで
>   テスト専用)との数値照合で検証する。依存追加なし・GPL混入なしを両立するため。
> - 以下の本文はレビュー時の記録としてそのまま残す(Tier 1/3の提案部分は上記判断により失効)。

> 依頼: 「opinion dynamics系の研究として、ダッシュボードを洗練させ研究の質を向上させる改善・追加の洗い出し」。
> 現状把握(`docs/dashboard.md`、`scripts/dashboard.py`、`results.csv`の60列、`repost_cascades.csv`、
> `agent_snapshot_*.csv`)+ 文献調査(分極測定・シミュレーション出力解析・感度分析)に基づく提案。
> **これは提案の記録であり、採否の決定ではない。** 採用時は個別に日付付きエントリで確定させること。

## 指導原理(先に固定する)

ダッシュボードは**ライブ監視ツール**であり、論文数値の出所ではない(一様ストライドの
デシメーション+`CsvTail`の適応間引きがあるため、既に`docs/dashboard.md`が明記している通り)。
したがって追加機能の価値基準は一つ: **「実行中のrunが情報を持つか(続けるか・殺すか・
どこを見るべきか)の判断ループを短縮するか」**。これに寄与しない「論文用の精密計算」は
`Analysis.java`/分析スクリプト側に実装し、ダッシュボードはそれを読むだけにする。
**論文に載せる指標をダッシュボード側にしか実装しない状態を作らない**(再現性の分岐点になる)。

## Tier 1 — Step-2ゲートの未解決項目に直結(最優先)

### 1.1 定常性/プラトー診断(未解決項目1に直結)
Gate 1が30000stepでもプラトーしない問題への器具的対応。現状は目視で「まだ傾いてる」を
判断している。シミュレーション出力解析の標準手法を載せる:
- **MSER-5によるtruncation点マーカー**を各時系列チャートに重ね描き(「ここから先を
  late-windowとして平均してよい」の視覚化)。MSER-5はwarm-up検出の事実上の標準
  ([Hoad et al., automated warm-up estimation](https://link.springer.com/article/10.1057/jors.2009.87)、
  [WSC 2011](https://www.informs-sim.org/wsc11papers/044.pdf))。
- **rolling傾きバッジ**: 各seed×指標について、直近ウィンドウのMann-Kendall傾向(または
  単純な回帰傾き/値域比)を「still trending / plateaued」の2値バッジで表示。
  seedチップの隣に置けば「このrunはもう読める」が一目で分かる。
- late-window平均の**報告規約そのもの**(ウィンドウ幅・開始点)はStep-2の決定事項として
  別途確定し、ダッシュボードはそれを可視化する側に回る。

### 1.2 heavy-tail頑健なクロスseed要約(未解決項目2: `bc_inc`に直結)
現状の「show mean」は平均線のみ。hub-mediated cascade countのような裾の重い指標では
平均がrare eventに支配される(10 seedでも符号が定まらなかった件)。
- mean線に**median + IQRバンド**オプションを追加(トグル)。
- cascadeパネルに**超過確率表示** P(depth ≥ d) を追加(既にdepthHistがあるので安い)。
- ヒストグラムの**対数yオプション**(`drawHistChart`、既知の限界として自己申告済み)。

### 1.3 hubロールパネル(推定対象そのものの可視化 — 最大のギャップ)
**現在60列をライブで見られるのに、論文の主題(moderate hubの構造的橋渡し)だけが
ライブで見えない。** `crossCuttingFraction`等は設計上hub接触辺を除外している
(`Writer.java:222`のコメントが明記)。追加すべきもの:
- **hub-mediated cross-camp repost fraction**の時系列: `repost_cascades.csv`の
  `relayer`列 × `agent_snapshot`の陣営ルックアップで計算可能(Writer.javaコメントが
  述べるpost-hoc計算のライブ版)。conveyedOpinion×relayerOpinionが既に行内にあるので
  「hubが逆陣営opinionを運んだイベント」を直接数えられる。
- **hubのbetweenness/次数成長トラジェクトリ**: `compute_structural`は既にtop-10
  betweenness表に`hub`フラグを出している — スナップショット横断の時系列化だけ。
- hubの**bridging centrality**(betweenness × bridging coefficient;
  [Bridges in social networks review](https://pmc.ncbi.nlm.nih.gov/articles/PMC12453711/))は
  単なるbetweennessより「コミュニティ間橋」への特異度が高い。

### 1.4 realized h-hop reachable fraction(research-direction §3.6の明示的要求)
「最終ネットワーク上で実測せよ、レンジを仮定するな」と北極星文書に書かれているが
未実装。`compute_structural()`にBFSで追加(キャッシュに乗せる)。h=1,2,3での
到達可能ノード割合を表示 — 高αレジームで`h`が実質グローバルに飽和していないかを
run中に確認できる(conduit redundancyリスクの早期警報)。

## Tier 2 — 最先端の分極・分離指標の追加

### 2.1 Random Walk Controversy (RWC)
[Garimella et al.のRWC](http://sites.computer.org/debull/A25jun/p58.pdf)は
「ランダムウォーカーが自陣営に留まる確率差」で構造分離を測る、モジュラリティ/E-Iと
相補的な指標(比較研究で直観的なcontroversy概念を最もよく捉えると報告されている)。
personalized PageRank 2本で近似でき`GRAPH_CACHE`済みグラフ上で安価。2-D planeの
x軸候補が増える。**ただし**: 論文採用するなら`Analysis.java`か分析スクリプト側が正、
ダッシュボードは写像。

### 2.2 dip統計量(Sarle's BCの相補)
Sarle's bimodality coefficientは**歪んだ単峰分布を偽陽性で二峰と判定する既知の弱点**が
ある([dip統計量との併用を推奨する文献](https://www.researchgate.net/publication/338222918_Development_of_Hartigan's_Dip_Statistic_with_Bimodality_Coefficient_to_Assess_Multimodality_of_Distributions))。
y軸(意見分極)がBC単独に依存するのは反論可能点。Hartigan dipには生の`O_i`が要る —
5-binヒストグラムでは不可なので、`agent_snapshot`の書き出し頻度を上げるか
Java側で計算して`results.csv`列にするのが正道(後者推奨: FAMILY/列追加だけで
ダッシュボードには自動で乗る)。[近年の比較研究](https://arxiv.org/pdf/2501.07473)も
単一スカラーでは不十分としており、2-D plane方針自体はこの知見と整合している。

### 2.3 エコーチェンバー散布図(Cinelli型、own vs. neighborhood opinion)
自分のopinion x 近傍平均opinionの散布図はエコーチェンバー診断の古典。ネットワーク
ペイロード(`nodes[].op` + `edges`)がブラウザに既に届いているので**純クライアント側で
サーバーコストゼロ**。対角集中=echo chamber、無相関=well-mixed。相関係数は
x軸のもう一つの候補にもなる。

### 2.4 structural virality(cascade木の平均ペア距離)
Goel et al. 2015の指標。broadcast型拡散(浅く広い)とviral型拡散(深い連鎖)を区別する。
`repost_cascades.csv`は木構造(root/parent/post)を完全に持っているので計算可能。
「hub経由の拡散はbroadcast型かviral型か」はconduit機構の性格描写として論文の
メカニズム節に直接効く。depth平均より情報量が多い。

### 2.5 powerlaw fitのlognormal比較
既に自己申告済みの限界(指数分布との比較のみ)。Clauset et al.の作法上、
lognormalは最重要の対立仮説なので`distribution_compare("power_law","lognormal")`を
1行追加してR値を並記する。

## Tier 3 — クロスランレイヤー(phase diagramビュー)

### 3.1 sweep-matrixビュー(構想としては最大の価値、コストも最大)
**論文=phase diagram(`P_u`×reactance)であり、主要な反実仮想(hub有無・algorithm
on/off・degree-matched rewiring)はすべてrun間の対比**なのに、ダッシュボードは
単一バッチのseed群しか見られない。`results/run_*_<tag>/`のtagをパースし、
各フォルダのlate-window平均を指標×パラメータのヒートマップ/small multiplesに
集約する「campaignビュー」を追加すれば、Step 3の本バッチ監視が質的に変わる
(「phase境界がどこに立ち上がりつつあるか」をバッチ完走前に見られる)。
1.1のlate-window規約が先に決まっている必要がある(依存関係)。

### 3.2 config/tag差分表示
seedチップにrun tagの差分(デフォルトから外れたパラメータ)を表示。sbm_pin/pout
フォルダ衝突事故(2026-07-09に修正)の再発をヒトの目でも検知可能にする。

## Tier 4 — 統計的作法・磨き込み

- mean線 → **seedエンベロープ(min–max帯)またはmean±CI帯**。seed数が少ない現状は
  エンベロープが誠実。
- late-window平均に**自己相関/実効サンプルサイズの注記**(30000 stepの窓でも実効的には
  数点しかない場合がある — Geweke/Heidelberg-Welch系の発想。
  [出力解析の標準手法群](https://rossetti.github.io/RossettiArenaBook/statistical-analysis-techniques-for-warmup-detection.html))。
- 2-D planeに**Type-1/Type-2象限アノテーション**(upper-right/upper-leftのラベル)+
  複数seedの平均軌跡。planeは「読みたい対象」のパネルなのに現状は無地。

## やらないこと・分析側に送ること(批判的レビューとしての線引き)

1. **ダッシュボード数値の論文流入禁止**を維持(既存方針の再確認)。Tier-2指標は
   `Analysis.java`/分析スクリプトが正、ダッシュボードは写像 — 逆順で実装しない。
2. **感度分析のGSA化はダッシュボードの仕事ではない**が、記録しておく: 現行OATは
   相互作用を原理的に見られない([ABM向けGSAプロトコル](https://link.springer.com/article/10.1007/s10588-021-09358-5)、
   [変数間相互作用が期待される非線形モデルでのOATの限界](https://ascpt.onlinelibrary.wiley.com/doi/10.1002/psp4.13256))。
   Tier-D knobsのロバストネス付録を書く際、Morris screeningが最小コストの格上げ
   (Sobolはrun数的に非現実的)。これは分析側のStep-3後課題。
3. **ライブ監視はgarden-of-forking-pathsの誘惑装置でもある**。run中に結果を見て
   モデルを触る事故を防ぐのはfreeze gate(Step 3)の規律であり、ダッシュボードは
   runの凍結済みconfigを目立つ位置に表示することで規律を支援する側に回る(3.2と同件)。

## 推奨実装順

1.1(プラトーバッジ)→ 1.3(hubパネル)→ 1.2(median/超過確率)→ 1.4(h-hop)が
Step-2/3に直接効く順。Tier 2はJava側実装が先行するもの(2.2)とダッシュボード単独で
済むもの(2.3, 2.5)を区別し、後者から。3.1はStep-3本バッチ開始前に間に合えば効果最大。
