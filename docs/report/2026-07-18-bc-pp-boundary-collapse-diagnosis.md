# 2026-07-18 bc/postProb の境界(0/1)への張り付き — 原因診断

## 背景

ユーザー報告: 現行モデルを回すと bounded confidence (`bc`) と post probability (`postProb`) が上下の境界に張り付く。旧モデル (`../Dev-SNAM2026`) では境界付近に集まりつつも interior(中間値)にもエージェントが残っていた。フィードアルゴリズム由来のバースト的な増減が原因ではないか、バグかもしれないという仮説。

## 調査方法

1. `../Dev-SNAM2026/src/agent/Agent.java` と現行 `src/agent/Agent.java` の `updateMyself()` を突き合わせ、bc/postProb の更新則の差分を特定。
2. `../Dev-SNAM2026/src/admin/AdminOptim.java` と現行 `src/admin/AdminOptim.java` の `AdminFeedback` を突き合わせ、フィード構成の差分を特定。
3. 実測による検証: 同一 seed(42)・同一ネットワーク(DC-SBM, n=300)で `feedAlgoShare (alpha)` のみを 0.0 と既定値 0.85 で振った制御実験を実施(`steps=5000`, `log_gexf=true`)。`step_5000.gexf` のノード属性(`boundedConfidence`, `postProb`)からターゲット(hub)を除く分布を集計。実行結果は `results/run_42_..._a-0.00_..._st-5000/` と `results/run_42_..._st-5000/`(alpha 既定)。

## 実測結果(n=297, hub除く)

| | bc floor(0.2) | bc ceiling(1.0) | bc interior | pp floor(0.05) | pp ceiling(0.5) | pp interior |
|---|---|---|---|---|---|---|
| alpha=0.0 (chrono only) | 21.5% | 50.5% | **27.9%** | 95.6% | 0.0% | 4.4% |
| alpha=0.85 (既定) | 16.2% | 83.2% | **0.7%** | 63.0% | 27.3% | 9.8% |

`meanTolerance`/`toleranceVar` の全ステップ時系列を確認したところ、集団平均としては滑らかに変化してステップ2000-3000あたりでプラトーに達しており(step-by-stepのdeltaも滑らか)、"バースト"は個体レベル・分布形状レベルの急速な収束であって、集団平均に離散的なジャンプが出るタイプの現象ではない。

## 根本原因: 2つの独立した設計変更が複合している

**結論から言うと、コードのロジックバグ(符号ミス・off-by-one等)は見つからなかった。** 実装は各所のコメントが示す設計意図と整合している。境界張り付きは、2026-07に加えられた2つの意図的な設計変更が組み合わさって生じる、数学的にほぼ必然の創発的挙動である。

### 原因A(主要因): bc更新則が「自己参照的な乗法ラチェット」になった

- 旧モデル(`Dev-SNAM2026/Agent.java:263-265`): `bc` は **out-of-bc接触でのみ** `bc *= BC_DEC_RATE(0.98)` と単調減少する片方向ラチェット。回復項は存在しない。初期値は `BOUNDED_CONFIDENCE=1.0`(=ceiling)。したがって「ceilingに留まっている」状態は「まだ減衰イベントに当たっていない過渡状態」であり、真の安定平衡ではない。
- 現行モデル(`src/agent/Agent.java:316-327`, 2026-07-10 "asymmetric tolerance" 決定): out-of-bc接触で `bc *= bcDecRate(0.99)`、**in-bc接触でも** `bc *= bcIncRate(1.001)` と、双方向の乗法ラチェットになった。

問題は分類基準そのもの: 「このpostがin-bcかout-of-bcか」の判定は `Math.abs(post.getPostOpinion() - this.opinion) < this.bc` であり、**閾値として使われる `bc` 自身が、その判定結果によって直後に更新される状態変数**になっている(`Agent.java:290,323-327`)。これは典型的な正のフィードバックループを構成する:
- `bc` が縮むと、閾値が厳しくなり、以後のpostがout-of-bcと判定されやすくなり、さらに `bc` が縮む。
- `bc` が伸びると、閾値が緩くなり、以後のpostがin-bcと判定されやすくなり、さらに `bc` が伸びる。

外的な復元力(中心へ引き戻す力)が存在しないため、これは強化されたランダムウォーク(Pólyaの壺に近い自己強化過程)であり、`[bcFloor, bcCeiling]` の壁でクランプされる限り、質量が両端に集中するのは統計的にほぼ避けられない。中間値に留まれるのは「フィード内の快適/不快の比率が長期にわたって五分五分に釣り合い続ける」というほぼゼロ測度の特殊条件を満たすエージェントだけになる。

**実測の裏付け**: alpha=0.0(フィードアルゴリズムを切り、旧モデル同様の"followee限定"露出にしても)、この自己参照ラチェットだけで bc の72.0%が境界に張り付く(旧モデル相当の露出構造でもここまで悪化する)。これは現行のbc更新則そのものが主因であることを示す。

### 原因B(増幅要因): For-Youフィード(velocity-primary, alpha既定0.85)が局所ホモフィリーの負のフィードバックを無効化する

- 旧モデル(`Dev-SNAM2026/AdminOptim.java:103-114` `AdminFeedback`): フィードは100% chronological-from-follows。フォロー関係はhomophily駆動のfollow/unfollow/blockで進化するため、「bcが縮む→不快な相手をunfollow/block→将来の露出が減る→それ以上bcが縮みにくくなる」という自己制限(負のフィードバック)が暗黙に働く。
- 現行モデル(`src/admin/AdminOptim.java:281-351` `AdminFeedback`): フィード容量の `floor(alpha*capacity)` 枠(既定 `alpha=0.85, capacity=10` → 8/10枠)が、opinion-blindかつ **フォロワー数で正規化しないvelocityランキング**(2026-07-09決定、`AdminOptim.java:162-173`、意図的な"rich-get-richer"化)由来のグローバルな "For-You" 投稿で埋まる。これは `h=4` ホップ以内なら誰の投稿でも入り得るため、個々のエージェントのblock/unfollowでは(その特定の発信者を止められても)止められない——次にバズる別の発信者が同じ枠を埋める。さらにランキングは `velocityRankInterval() = round(1/accessProb) = 10` ステップごとにしか更新されず、その間は同一のトップ投稿群が凍結されたまま集団の大部分に同時配信され続ける(`AdminOptim.java:210-233`)。

**実測の裏付け**: alpha を 0→0.85 にすると bc の境界質量は 72.0%→99.3%、interior は 27.9%→0.7% までほぼ消滅。原因Aのラチェットに、原因Bの「ホモフィリーによる自己制限の欠如」+「集団相関した一様な圧力」が乗ることで、境界への収束がほぼ完全になる。

### postProb について

`postProb` は post単位ではなくstep単位で `comfortPostRate`(固定半径 `VOCAL_COMFORT_RADIUS=0.2` 基準、`bc`非依存)と `Const.OPINION_PREVALENCE=0.5` の比較により `comfortPpFactor=1.01` で乗除される(`Agent.java:330-343`)。bcと違い自己参照ループではないが、「フィードの過半数が±0.2以内」という基準は多くのエージェントにとって恒常的に満たされにくく、alpha=0では95.6%がfloorへ一方向に収束する(何百ステップも同方向に`÷1.01`され続ければ当然の帰結)。alpha=0.85ではceiling側にも27.3%が現れる——バイラルなFor-You投稿が(hub以外の)多数派意見に近い層には「快適」として作用し、その層ではpostProbが逆方向にラチェットされるため。これはバグというより、`OPINION_PREVALENCE=0.5`という基準の厳しさ+一方向ラチェット+回復力なしという設計の組み合わせが引き起こす別の(bcとは独立した)境界張り付き経路。

## 評価: バグか、設計の帰結か

実装ロジックそのものに誤りは見当たらない。ただし研究設計上は重大な懸念: 2-D outcome plane や Type-2 affective polarization の議論が bc/postProb の**分布の広がり(heterogeneity)**に依拠するなら、現行の既定パラメータではそのheterogeneityが数千ステップ以内にほぼ消失し、母集団が「floor個体」と「ceiling個体」の二山にほぼ完全崩壊する。これは `docs/research-direction.md` の目標(moderate conduitによるnuancedな分極)にとって望ましくない可能性が高い。

## 推奨アクション(未実施、要議論)

1. **`bcIncRate` の弱化 or 撤廃を検討**: 1.001でも数百〜数千接触にわたり複利で効くため、回復項の強さそのものを疑うべき(alpha=0でも72%が境界に達している事実から、For-You機構を触るより先にこちらが優先度高)。
2. **bc自己参照ループの切断**: in/out-of-bc判定に(既存の `VOCAL_COMFORT_RADIUS` のような)固定閾値、または「現在のbcではなくstep開始時点のbcスナップショット」を使うことで、正のフィードバックを弱める設計を検討。
3. **`alpha` sweep**: 原因Aを緩和した上で、0, 0.15, 0.3, 0.5, 0.85 で改めてsweepし、For-You機構単体の寄与を測定(現状は原因Aと交絡している)。
4. 検証用の一時実行結果は `results/run_42_ext-SYM_nmod-1_size-LARGEST_ch-BOTH_a-0.00_nw-dcsbm_n-300_st-5000/` と `results/run_42_ext-SYM_nmod-1_size-LARGEST_ch-BOTH_nw-dcsbm_n-300_st-5000/`(いずれも `results/` は gitignore 済み、削除して問題なし)。

## 対応(DECIDED & 実装済み、2026-07-18)

推奨アクション1・2をユーザーと議論のうえ採用: **`bcIncRate`(乗法的ラチェット、同化と対称)を廃止し、
`bcRecoveryRate`(平均回帰、内容非依存)に置き換えた。** decline側(`bc *= bcDecRate`、out-of-bc接触時のみ)は
変更なし——「decは内容依存のまま、incは内容に関係なく働くべき」というユーザーの整理に基づく。

**検討・却下した代替案:** 「inc条件だけ外す(`bc *= bcIncRate`を毎post無条件に適用)」という素朴な実装は、
数値的にほぼ無意味と判明——現行defaults(`bcIncRate=1.03, bcDecRate=0.70`)の下では、in-bc post側は元々
「else」分岐で毎回incRateが掛かっていた(homogeneousなfeedのエージェントはdecRate分岐を一度も踏まない)ため
無条件化しても不変。唯一変わるout-of-bc側は`bcDecRate*bcIncRate=0.721`とわずかに弱まるだけで、境界崩壊を
悪化させる方向にしか効かない。根本原因は「内容依存か否か」ではなく「定数倍(bcの現在値に依存しない)か、
現在値からの距離に比例した復元力か」という軸——後者(平均回帰)だけが真の安定点を作れる。

**実装:**
```java
// Agent.java updateMyself(), per post in feed:
if (Math.abs(post.getPostOpinion() - this.opinion) > this.bc) {
    this.bc *= p.bcDecRate();
}
this.bc += p.bcRecoveryRate() * (p.bcInit() - this.bc);
```
- `bcIncRate`→`bcRecoveryRate`に全面リネーム(`ExperimentConfig`/`SimParams`/CLI `bc_inc`→`bc_recovery`/
  `tag()`の`_bcinc-`→`_bcrecovery-`)。値の意味が乗法係数→線形回帰率へ根本的に変わるため、旧名を残すと
  暗黙に挙動が変わったことが見えなくなる(`coupleOutOfBCRepost`/`bcGateAssim`廃止と同じ判断)。
- **回帰目標値は agent固有の`bcInit`を再利用**(ユーザー判断、新規パラメータは追加しない)。ただし
  `bcInit`の既定値がこれまで`1.0`(=`bcCeiling`)だったため、これをそのまま回帰先にすると
  「天井に向かって回帰する」という同じ問題を再生産してしまう——`bcFloor`/`bcCeiling`の中間値
  `0.6`に変更(未較正、Stage 2の対象)。
- 新規`bcRecoveryRate`の既定値は`0.03`(未較正のプレースホルダー)。

**実機検証(2026-07-18、n=300, DC-SBM, seed=42, steps=5000、他は全てdefaults):**

| bc_dec | bc_recovery | floor% | ceiling% | interior% | 備考 |
|---|---|---|---|---|---|
| 0.70(Stage-2d既定、旧メカニズム用に較正された値) | 0.03(新既定) | 96.7 | 0.0 | 3.3 | decRateが単発で強すぎ、弱いrecoveryでは相殺できずfloorへ全崩壊(旧ceiling崩壊とは逆向きだが同じ質の問題) |
| 0.95 | 0.10 | 0.0 | 0.0 | **100.0** | mean=0.536, std=0.071 — 境界崩壊なし、interiorに広がりのある分布 |

**結論:** メカニズム自体は正しく機能する(2行目でinterior heterogeneityが実現することを確認済み)。
ただし`bcDecRate=0.70`は旧メカニズム(乗法ラチェット、高頻度のincRateとの綱引きを前提に較正)向けの値であり、
新メカニズム下では較正的な意味を持たない——**`bcDecRate`/`bcRecoveryRate`は両方とも実質的に未較正の自由
パラメータとして扱い、Stage 2で新規に(ペアで)探索し直す必要がある**(旧Stage2b/c/d結果は流用不可、
Stage1c/1dのfollow-graph構造calibrationには影響しない、という既存の整理と同じ切り分け)。

**テスト:** `ModelTests`全体を再実行、bc_recovery関連は全PASS。無関係な既知3件の失敗
(`p_u tagged only when non-default`、`distinct configs => distinct tags`——別の未コミット変更で
`pU`の既定値が0.05に変わったのに追随していないテストのstaleness、と`truncate default + bc_dec 0.999`——
コミット済みHEAD時点から存在)は本変更と無関係、修正対象外(スコープ外)。
