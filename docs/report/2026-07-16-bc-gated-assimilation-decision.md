# 2026-07-16 FJ同化のbcゲート化を恒久化(`bcGateAssim`トグル廃止)

## 決定(DECIDED 2026-07-16)

`Agent.updateMyself()`のFriedkin-Johnsen同化(social influence)を、**常にbounded confidence範囲内の投稿のみで平均する**よう恒久化した。従来存在した`bcGateAssim`トグル(既定`false`=feed全体で平均)を削除し、`false`側の選択肢自体をなくした——`if`分岐ではなく単一の挙動にした。

## 経緯・理由

Bakshy et al. 2015の「individual choice(selective exposure)が露出制限の最大要因」という知見を踏まえ、現行モデルで個人の選択的な情報遮断がunfollow/blockでしか表現されていない点を議論した。当初、これを「bcゲート化されたFJ同化」で近似することを提案したが、以下を明確にした:

- **これはselective exposure(消費前の選択的接触)そのものではない。** 露出後もhostility更新・bc減衰・comfort追跡には全ての投稿が反映される(`Agent.java`の`updateMyself()`内、bc範囲外でも通る処理)。動かないのは「意見表明の同化平均」だけ。より正確には**selective persuadability(選択的被説得性/motivated reasoning)**に近い。
- ユーザーの反論:「feedで見ていることは見ているわけで、それを読む=影響を受ける、と捉えればselective exposureに近い発想」——機構としては別だが、結果として"接触しても影響が及ばない"という点で機能的な類似性はある、という評価で合意。
- どちらの解釈を取るにせよ、**bcは`post`/`repost`/`follow`/`unfollow`で既に全面的に使われている中心パラメータ**であり、FJ同化だけがbcを無視して feed全体を平均するのは内部的に不整合だった、という判断でトグルではなく恒久的な仕様変更とした。
- litmus test(`research-direction.md:161-166`)は通過:非対称bc回復(`bcIncRate`)がある限り、assimilationが完全凍結されるとは限らず、収束・分裂どちらも到達可能なまま。

## 実装

- `Agent.java` `updateMyself()`:`if (!p.bcGateAssim() || ...)` を `if (Math.abs(post.getPostOpinion() - this.opinion) < this.bc)` に変更(ゲート判定を削除、常時適用)。
- `SimParams.java`:`bcGateAssim`フィールドをレコードから削除。
- `ExperimentConfig.java`:`bcGateAssim`フィールド、CLIパース(`bc_gate_assim=`)、`tag()`内の`_bcgate`サフィックスをすべて削除。
- `test/ModelTests.java`:旧トグル参照(`bc_gate_assim=true`引数、`c.bcGateAssim`アサーション)を削除。新規に2件追加:
  - `testBcGatedAssimilationOnly`:in-bc投稿とout-of-bc投稿が混在するfeedで、意見がin-bc投稿の値のみに同化すること(`stubbornness=0`で同化平均を分離して検証)。
  - `testBcGatedAssimilationFreezesWhenNothingInBc`:feed内が全てout-of-bcのとき、その step は意見が凍結すること。
- 全テストPASS(既存の無関係な3件の失敗——`bc_dec 0.999`、`[tag]`2件——は本変更と無関係、2026-07-16 feed機構レビュー時にコミット済みHEADで再現確認済み)。

## 影響・注意点

**これまでのcalibration(stage1a/1b/2のBO評価)は旧挙動(feed全体で平均)の下で行われている。** `bcGateAssim`はもはやCLI引数として存在しないため、旧挙動に戻す手段はない——**再calibrationが必須**。次のsweep/calibrationサイクルでこれを反映すること。
