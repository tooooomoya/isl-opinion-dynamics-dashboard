# src/ 以下のモデルおよび分析ファイルの正確性検証・クリティカルレビュー

- **作成日**: 2026-08-24
- **対象**: `src/` 配下の全モデル・意見ダイナミクス・ネットワーク生成・分析統計コード
- **目的**: モデルの正確性・数学的厳密性・計算社会科学（CSS）的妥当性の徹底調査と今後の改善・修正メモ

---

## 1. 総括・検証サマリー

本プロジェクトの `src/` 配下のソースコードについて、数理モデルの厳密性および計算社会科学の理論的枠組みに基づき徹底的なレビューを実施した。
シミュレーション基盤として先進的な機能が備わっている一方で、**モデルの根幹をなす意見更新・ネットワーク生成・サンクション行動・統計計測において、理論的仮説を無効化・歪曲しかねない複数の重大な問題点・不整合**が確認された。

---

## 2. 意見ダイナミクスおよびエージェント行動モデルの検証 (`src/agent/`, `src/dynamics/`)

### 2.1 Friedkin-Johnsen (FJ) Persuasion メカニズムにおける「平均化」処理とソーシャルプルーフの消失
- **該当箇所**: [Agent.java:L454](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/agent/Agent.java#L454)
- **問題点**:
  標準的な FJ モデル $x_i(t+1) = a_i x_i(0) + (1 - a_i) \sum_j w_{ij} x_j(t)$ に対し、本コードでは BC 内投稿の単純平均 `assimSum / assimNum` を用いて更新を行っている。
- **影響**:
  同意見の投稿がフィード内に1件存在する場合と、リポスト等により100件氾濫している場合でエージェントの意見更新量が同一となる。これにより、リポストによる情報拡散やバズ（Virality）が持つ社会的証明（Social Proof）の効果が意見更新から消滅している。

### 2.2 Graded Bounded Confidence (BC) 弛緩モデルにおける履歴（Inertia）喪失とタイムスケール非整合
- **該当箇所**: [Agent.java:L412-L417](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/agent/Agent.java#L412-L417), [ExperimentConfig.java:L253](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/experiment/ExperimentConfig.java#L253)
- **問題点**:
  緩和率 `bcDecRate` がキャリブレーション等で `1.0`（または `0.5`）に設定されると、$BC$ は過去の接触履歴（Inertia）を一切保持せず、直前の 1 ステップのフィード構成割合 `inBcRate` の決定論的関数へと退化する。
- **影響**:
  プラットフォームアクセス確率 `accessProb`（デフォルト 0.1）とのタイムスケール無次元化がなされておらず、アクセス頻度を変更すると不寛容化の進行速度が非線形に崩壊する。

### 2.3 Vocal-Minority メカニズムにおける Density Bias と `vocal_comfort_radius` の外部操作の実態
- **該当箇所**: [Agent.java:L376](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/agent/Agent.java#L376), [ExperimentConfig.java:L530](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/experiment/ExperimentConfig.java#L530)
- **問題点と操作実態**:
  - **歴史的経緯**: 元々は `Const.java` で `VOCAL_COMFORT_RADIUS = 0.2` の固定値だったが、キャリブレーション精度向上等のため CLI 引数 `vocal_comfort_radius`（内部変数: `vocalComfortRadius`）として外部パラメータ化された。
  - **実験スクリプトでの操作**: `scripts/` 配下の Python / shell スクリプト（例: `bridging_current_config.py`, `app_pol_baseline_bo_v13_graded_bc.py`）等において、`0.1`, `0.1257`, `0.452`, `0.5` などに動的変更・ベイズ最適化（BO）・OATスイープが行われている。
  - **モデル的課題**: 外部操作可能になったものの、絶対半径による一律カットオフ構造そのものが、高密度な中道派（Moderates）の快適度を高めて発言させ、低密度な両極派（Extremists）を黙らせる構造的 Density Bias を生む本質的課題は残存している。

### 2.4 サンクション行動における「身代わりブロック」バグ
- **該当箇所**: [Agent.java:L629-L641](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/agent/Agent.java#L629-L641)
- **問題点**:
  デフォルトの `relAttrib = "original"` の下で、フォロー中の媒介者 $B$ が不快な原著者 $C$ の投稿をリポストして届いた際、$A$ は $B$ ではなく、フォローもしていない原著者 $C$ を `dislikeUser` に追加して永久ブロックする。
- **影響**:
  不快情報を流してきた情報配信者（Relayer）にサンクションが向かわず、遠くの原著者に矛先が向かうため、ソーシャルメディア上の拡散・サンクションの因果メカニズムが実態と大きく乖離している。

---

## 3. ネットワーク生成アルゴリズムの検証 (`src/network/`)

### 3.1 有向 Barabási-Albert (BA) モデルにおける優先的選択の歪み
- **該当箇所**: [BarabasiAlbertNetwork.java:L42-L73](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/network/BarabasiAlbertNetwork.java#L42-L73)
- **問題点**:
  有向グラフの優先的選択は入次数（In-degree）に比例すべきであるが、新規ノード追加時にまだ誰からもフォローされていない入次数 0 の `newNode` までも `degreePool` に追加している。（[DMSNetwork.java](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/network/DMSNetwork.java) の方が初期魅力 $A$ を用いた理論的に正しい定式化を行っている）。

### 3.2 有向 Watts-Strogatz (WS) モデルにおける出次数 $K$ と $K/2$ の乖離
- **該当箇所**: [WattsStrogatzNetwork.java:L26-L35](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/network/WattsStrogatzNetwork.java#L26-L35)
- **問題点**:
  コンストラクタ引数 `K` に対し、実際のコードでは `halfK = K / 2` 個の右隣のノードにのみ有向辺を張っている。そのため指定値 $K=4$ に対し、実際の出次数は 2 となり、パラメータ定義と構造が 2 倍ズレている。

### 3.3 DC-SBM モデルにおける度数正準化と分布クランピング
- **該当箇所**: [DCSBMNetwork.java:L177-L206](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/network/DCSBMNetwork.java#L177-L206)
- **問題点**:
  $\theta_{in}$ の確率飽和を防ぐため `SATURATION_THRESHOLD = 0.8` でキャップをかけ、失われた平均度数を補うために非キャップノードを `reScale` している。これにより Pareto 分布のロングテール（Scale-free 性）が人工的に歪められている。

---

## 4. 分析および統計指標の計算精度 (`src/analysis/`)

### 4.1 サイン付きモジュラリティ ($Q_{sign}$) における Moderate 除外と不連続性
- **該当箇所**: [Analysis.java:L339-L341](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/analysis/Analysis.java#L339-L341)
- **問題点**:
  `|opinion| < moderateBandHalfWidth` のエージェントをモジュラリティ計算から除外しているため、意見が 0 付近を跨ぐ際に計算対象ノード・エッジ数が不連続に変化し、指標が急変する脆弱性がある。

### 4.2 Exposure Metrics (`exposureOpinionVar/Mean`) におけるアクセス・サンプリングバイアス
- **該当箇所**: [Analysis.java:L638-L667](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/analysis/Analysis.java#L638-L667), [OpinionDynamics.java:L317](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/dynamics/OpinionDynamics.java#L317)
- **問題点**:
  `feedMap` への書き込みがそのステップでプラットフォームにアクセスしたエージェント（`agent.setUsed() == true`）のみに対して行われるため、全集団の真の露出分布ではなく、アクティブユーザーのサンプリング露出のみを測定している。

### 4.3 Sarle's Bimodality Coefficient ($b$) の極限挙動における不確実性
- **該当箇所**: [Analysis.java:L129-L146](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/analysis/Analysis.java#L129-L146)
- **問題点**:
  完全合意 $m_2 \to 0$ への収束局面で、浮動小数点数誤差（`1e-11` 付近）によりゼロ除算に近い数値不安定が発生し、異常値を返すリスクがある。

---

## 5. 配信・管理ロジックの非対称性 (`src/admin/`)

### 5.1 Chrono（時系列配信）と For-You（アルゴリズム配信）の配信タイムラグ非対称性
- **該当箇所**: [OpinionDynamics.java:L413-L420](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/dynamics/OpinionDynamics.java#L413-L420)
- **問題点**:
  フォロー経由の配信が全エージェントのターン終了後のバッチ処理（`PendingDelivery`）に変更されたため、Chrono 配信は翌ステップ（$t+1$）に届くのに対し、For-You 候補 `recentPosts` には即時追加されるため同ステップ（$t$）内で届き得る。1ステップのタイムラグ非対称性が存在する。

### 5.2 Dynamic Rewiring と Reach BFS キャッシュ（100ステップ）の遅延
- **該当箇所**: [AdminOptim.java:L313-L322](file:///Users/tomoyatakeda/Documents/polarized-vocal-minority-model/src/admin/AdminOptim.java#L313-L322)
- **問題点**:
  $h$-hop Reach キャッシュが 100 ステップ固定で更新されるため、動的な Follow/Unfollow/Block の変更が即座に反映されず、過去のトポロジーに基づいて For-You が選考される。

---

## 6. 今後の修正・検証アクションプラン

1. **サンクションの正常化**: `unfollow()` 内の判定で、リポスト投稿に対するブロック/アンフォロー対象を `relayerId`（直近送信者）に変更する。
2. **快適度判定の相対化**: `vocal_comfort_radius` の判定を集団の意見標準偏差 $\sigma_{op}$ や各エージェントの動的 $BC$ に相対化し、Density Bias を軽減する。
3. **FJ モデルのソーシャルプルーフ導入**: 単純平均から、投稿数・リポスト数に応じた加重平均 / 累積インパルス型更新へのリファクタリング。
4. **ネットワーク生成モデルのパラメータ・ロジック修正**: WS モデルの出次数 $K$ の補正、BA モデルのイン度数優先的選択の修正。
5. **露出統計のサンプリングバイアス修正**: アクセスの有無にかかわらず、全エージェントのフィードを一元評価する集計ロジックへの変更。
