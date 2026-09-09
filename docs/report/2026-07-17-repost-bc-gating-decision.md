# 2026-07-17 Repostのbcゲート化を恒久化(`coupleOutOfBCRepost`トグル廃止)

## 決定(DECIDED 2026-07-17)

`Agent.repost()`のrepost判定を、**bc範囲内の投稿は`repostProb`、範囲外は別建ての`outOfBCRepostProb`**で
判定するよう恒久化した。従来存在した`coupleOutOfBCRepost`トグル(既定`true`=out-of-bc確率を
`repostProb`に結合、実質ゲートが無効化される)を削除し、`true`側の選択肢自体をなくした——
`2026-07-16`の`bcGateAssim`恒久化と同じ判断枠組み(トグルではなく単一の挙動にする)。

## 経緯・発端

Stage 2の再calibration準備として、新しいStage 1b値(`max_follow=30, follow_prob=0.015, alpha=0.75,
hop=4`)の下で`Q_sign_repost`(repostネットワークのopinion符号によるsign modularity、Conover et al.
2011のTwitter retweetネットワークでの実測~0.7-0.8がtarget)をサニティチェックしたところ、複数点
(旧stage2 round0の5点 + 追加2点)すべてで0.0003〜0.043と、targetから2桁近く低い値に張り付いていた。
一部は「より分離を促すはず」の極端パラメータでむしろ悪化しており(後述の通りこの極端点設定自体が
誤りだったと判明)、パラメータ探索(BO)では埋まらない構造的な問題を疑い、コード調査(サブエージェント)
を実施した。

## 調査結果

`Agent.repost()`(旧`Agent.java:371-411`)を確認したところ:

- repost判定にはbc範囲内/範囲外を区別する`inBc`分岐が**既に存在していた**が、既定`coupleOutOfBCRepost=true`
  により、範囲外でも`repostProb`と同じ確率(既定0.1)が使われ、**ゲートが実質無効化**されていた。
- feedの85%(既定`feedAlgoShare=0.85`当時、Stage1c/1dでは`alpha=0.75`)はopinion-blindなFor-You
  (velocityランキング)チャンネルから供給されており、opinion構造を持つのはchronoチャンネル(15%程度)
  のみ。
- FJ同化(`updateMyself()`)は2026-07-16に恒久的にbcゲート化されている(`docs/report/2026-07-16-bc-gated-assimilation-decision.md`)のに対し、repostには対応する恒久ゲートがなかった——非対称な実装状態だった。

**結論:** `Q_sign_repost`が低いのはパラメータの当たりが悪いからではなく、repost機構そのものが
(既定設定下では)opinionと無関係に発火する設計だったため。BOでこの非対称を埋めることはできない。

## ユーザー判断

「repostもFJと同様にbcゲートすべき」という判断(2026-07-17)を受け、恒久化を実装。

## 実装

- `Agent.java` `repost()`: `p.coupleOutOfBCRepost() ? this.repostProb : p.outOfBCRepostProb()` を
  `p.outOfBCRepostProb()`に単純化(in-bcは`repostProb`のまま、out-of-bcは常に`outOfBCRepostProb`)。
- `ExperimentConfig.java`: `coupleOutOfBCRepost`フィールド・CLIパース(`couple_out_of_bc_repost=`)・
  `tag()`内の分岐条件を削除。`outOfBCRepostProb`の既定値を**0.1→0.02**に変更
  (旧既定はrepostProbと同値でゲートが数値的にno-opになっていたため、実質的な既定値として意味を持つ
  低い値に変更。「稀に反対陣営の投稿を晒し者的にrepostする」ような現実的な下限としての仮置き——
  Stage 2でのcalibration対象)。
- `SimParams.java`: `coupleOutOfBCRepost`フィールドをレコードから削除。
- `InterventionSetup.java`: `writeConfigLog`のCSVヘッダ・行から`couple_out_of_bc_repost`列を削除。
- `test/ModelTests.java`: 旧トグル参照を削除、新規に2件追加:
  - `testRepostBcGatedInBcOnly`: `repost_prob=1.0, out_of_bc_repost_prob=0.0`でin-bc投稿のみrepost
    されることを確認。
  - `testRepostBcGatedOutOfBcUsesSeparateRate`: `repost_prob=0.0, out_of_bc_repost_prob=1.0`で
    out-of-bc投稿のみrepostされることを確認(結合されていない独立レートであることの直接証拠)。
  - 全テストPASS(既知の無関係な3件——`p_u tagged`, `distinct configs tags`, `bc_dec 0.999`——は
    本変更と無関係、変更前から再現)。

## 効果検証(2026-07-17、簡易サニティラン)

新しい恒久ゲート下で2点を実行(N=1000, steps=15000, 1seedのみ、Stage1b値固定):

| 設定 | bc_dec | stub | Q_sign (t=15000) | Q_sign_repost (t=15000) |
|---|---|---|---|---|
| 旧コード(参考、修正前) | 0.95 | 0.5 | 0.309 | 0.043 |
| 新コード・中間点 | 0.95 | 0.5 | 0.133 | **0.109**(2.5倍) |
| 新コード・訂正済み極端点 | 0.90 | 0.9 | 0.365 | **0.291**(6.8倍) |

**訂正済み極端点についての注記:** 当初「極端」として試した`bc_dec=0.999, stub=0.2`は誤り——
`bc_dec`は「不快な接触ごとにbcに掛ける乗数」なので1に近いほど減衰が遅く(分離を弱める)、
探索空間下限の0.9に近いほど急速に減衰する(分離を強める)。`stub`も低いほど同化されやすく
(feedの平均に引っ張られ分離を弱める)、高いほど頑固で初期の分離状態を保持しやすい。
正しい「分離を最も促す」極は`bc_dec→0.9側`・`stub→高い側`(ユーザー指摘、2026-07-17)。

まだtarget(0.75)には遠いが、修正前の0.001〜0.04という「探索では絶対に埋まらない」水準から、
明確に応答するパラメータ領域に入った。Stage 2のBOで`outOfBCRepostProb`を新しい自由次元として
含めれば、さらに改善が見込める。

## 影響・注意点

**Stage 1a/1b/1c/1dのcalibration(follow-graph構造:Gini/gamma/opinionAssortativity)はこの変更の
影響を受けない**——repostのopinion依存性はfollow-graph自体の構造には作用しないため
(chrono経由の間接的な影響は理論上あり得るが、Stage 1b/1cの再calibrationは既にこの変更**前**の
コードで行われている点は要注意)。**Stage 2は本変更の直接的な対象**であり、今回のsanityチェックが
示す通り、旧コードでのround 0結果(`stage2_bo_evaluations.csv`)は完全に無効。
