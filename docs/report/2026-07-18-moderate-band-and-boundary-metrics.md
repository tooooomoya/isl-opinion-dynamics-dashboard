# 2026-07-18 Moderate帯の導入 + Guerra et al. 2013指標の追加

## 決定(DECIDED 2026-07-18)

Q_sign単体でのStage2評価が無理筋である、というユーザー指摘を受け、以下を実装した:

1. **`|opinion| < 0.2`のエージェントを、全sign-based指標の2群分割から除外**する
   (`moderateBandHalfWidth`、既定0.2)。
2. **Guerra et al. 2013の2指標を追加**(Boundary Polarization Measure P, Spearman's ρ)。ダッシュボードにのみ実装、Stage2のcalibration targetには含めない。

## 背景:なぜmodularity単体が不十分か

Guerra et al. 2013(`docs/reference/ICWSM13-Polarization.pdf`)の中心的批判: modularityは
homophily(似た者同士が繋がる)とantagonism(異なる者同士が繋がるのを避ける)を同じ式の中で
混同している。非polarizedな文脈(サッカー+バスケ両方のファン、大学の友人関係)でもQ=0.15〜0.24
という無視できない値が出る——「どれだけのQがあれば"polarized"と言えるか」という閾値が
原理的に定義できない。これはStage2でQ_sign_repost=0.48を目指して延々とBOを回していた
状況そのものへの批判として妥当。

## Moderate帯の閾値設計

**Conover et al. 2011もGuerra et al. 2013も、opinion値による閾値分割は一切していない**——
両論文とも、2群はネットワーク自体のコミュニティ検出(label propagation / Louvain modularity
maximization)から決まり、opinion/政治的立場は事後の手動アノテーションによる検証にすぎない。
したがって「元論文の閾値」という意味での根拠となる数値は存在しない。

ただしConover Table 4では、手動アノテーションで「undecidable」と判定されたユーザー(既に
政治的発言をするだけの投稿量がある層の中で5〜11%)は、どちらの陣営にも強制的に割り当てられて
いない。これは「意見が中立的なエージェントを無理に2群に押し込めない」という思想として
参考にできる。

**採用した値:** `|opinion| < 0.2`(固定、SD比例ではない)。過去の関連研究で`[-1,1]`を幅0.4の
5campに等分割し、中央の`[-0.2, 0.2]`をmoderateとしてきた実績があり、それを踏襲(ユーザー
判断、2026-07-18)。1/5分割という設計は突飛な仮定ではないと判断。

**除外率についての留意点(ユーザー指摘):** Conoverの5〜11%は「投稿量が十分にあり政治的立場を
判定できたユーザー」の中での割合。本モデルは非投稿・低頻度投稿のエージェントも全員含むため、
同じ閾値でも全体母集団での除外率はConoverの数字より高くなることが予想される——これは意図した
効果であり、後から11%に合わせて閾値を補正する必要はない。

## 影響範囲

**変更した(sign-based, camp分割を使う指標):**
- `Analysis.java`: `computeSignModularity`(Q_sign)、`computeSignModularityFromMatrix`
  (Q_sign_repost)、`computeCrossCuttingFraction`、`computeInteractionCrossCuttingFraction`
  ——いずれも`isModerate(agent, moderateBandHalfWidth)`でmoderateエージェントを、既存の
  hub(`getTarget()`)除外と同じ扱いで除外。
- `ExperimentConfig.java`/`SimParams.java`: `moderateBandHalfWidth`フィールド追加(既定0.2、
  CLI`moderate_band=`でsweep可能)。
- `dashboard/analysis.py`: `compute_rwc`のside_x/side_y分割を同じ閾値に変更。

**変更していない(連続値ベース、camp分割を使わない指標):**
- `opinionAssortativity`/`interactionAssortativity`——エージェントの連続opinion値同士の
  Pearson相関であり、そもそもsign/camp分割を使わない。**Stage1(follow-graph構造)の校正は
  この変更の影響を受けない**、と結論。

## 新規追加:Guerra et al. 2013の2指標(ダッシュボードのみ)

`dashboard/analysis.py`に追加、`compute_structural`経由でダッシュボードのnetwork-structure
パネルに表示。Stage2のBO targetには含めない(ユーザー指示)。

- **`compute_boundary_polarization`**: 論文式(6)のP値。「境界ノード」(相手陣営にリンクを
  持つが、相手に一切繋がらない仲間もいる)が、内部と相手境界のどちらを優先するかを測る。
  論文Figure 2のtoy exampleで検証済み(期待値P=0.0と一致)。境界が空の場合
  (`boundarySize=0`)は計算不能として扱う(論文の「人類と地球外生命体の間に対立があるか
  問うようなもの」という説明をそのままnoteに反映)。
- **`compute_boundary_rho`**: 論文§6のSpearman相関。全次数ランクと相手陣営への接続数ランクの
  相関——高いほど人気ノードが境界に集中(非polarized)、低いほど人気ノードが境界を避ける
  (polarized)。

実データ(既存のGEXFスナップショット)で動作確認済み:
`{'P': -0.097, 'boundarySize': 106, 'b12': 90, 'b21': 16}`、
`{'rho': -0.1018, 'p': 0.0129, 'n': 595}`——クラッシュなく妥当な値域で出力。

## 未着手・今後の課題

- Stage2の再calibrationは、moderate帯導入後のQ_sign_repostで**再度**やり直しが必要
  (定義が変わったため、既存のstage2b/c/d結果は新定義との直接比較不可)。優先度は次回判断。
- Boundary P / ρをStage2のtargetに組み込むかどうかは未決定(現時点ではダッシュボード
  観測用にとどめる、というユーザー指示)。
