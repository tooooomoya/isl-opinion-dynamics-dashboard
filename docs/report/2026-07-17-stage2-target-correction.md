# 2026-07-17 Q_sign_repostのtarget訂正(0.75→0.48、一次資料確認済み)

## 決定(DECIDED 2026-07-17)

`Q_sign_repost`のcalibration target を**0.75→0.48**に訂正する。`docs/reference/Political Polarization
on Twitter.pdf`(Conover et al. 2011, ICWSM)を直接読み、根拠を確認した。

## 経緯

`scripts/stage2_bo_calibration.py`(元のStage 2スクリプト、2026-07-16以前に作成)のdocstringには
「Conover et al. 2011 ~0.7-0.8」と記載されていたが、これは一次資料未確認の値だった。Stage 2b実行後、
target 0.75に対しbest実測が0.35止まりで大きな乖離が続いたため、ユーザーの提案で一次資料を直接確認した。

## 確認内容(p.91、§3.1 Community Structure)

> "Modularity (Newman and Girvan 2004) resulting from the cluster assignments offers a first measure
> of segregation... The modularity induced by the communities in the retweet and mention networks
> have values of 0.48 and 0.17, respectively."

- retweetネットワーク: **Q = 0.48**
- mentionネットワーク: Q = 0.17
- 手法: label propagation(leading-eigenvector modularity maximizationでseed)による2コミュニティ検出、
  Newman & Girvan (2004) のmodularity定義。
- Table 4(手動アノテーション、p.92)によれば、この2クラスタは政治的立場とほぼ対応(クラスタA=93.4%
  右派、クラスタB=80.1%左派)——完全な党派分離ではないが強い対応。

## 比較可能性についての留意点

- 論文の0.48は**データ駆動のコミュニティ検出**(label propagation)によるmodularityであり、
  本モデルの`Q_sign_repost`は**既知のopinion符号による厳密な2分割**(sign modularity)。
  論文のクラスタが完全に党派一致していない(A=93%右派、B=80%左派、混在あり)ことを踏まえると、
  「真の」符号ベース分割のmodularityは0.48よりやや高いか低いか、論文からは直接読み取れない
  (どちらの方向にずれるかも自明ではない——検出クラスタと真の分割が完全一致しない場合、
  一般には検出クラスタのmodularityは最大化アルゴリズムの出力なので真の分割より高くなりやすいが、
  ラベル誤りの分だけ「真の分割」でのmodularityは論文の0.48より低くなる可能性の方が高い)。
- したがって0.48は「大体このオーダー」という目安であり、厳密な同一指標比較ではない。

## 影響

`scripts/stage2b_bo_calibration.py`(Q_TARGET=0.75で実行済み、`docs/report/stage2b_bo_evaluations.csv`)
はtarget値が誤っていたため、"loss"の絶対値は再解釈が必要——ただし生の`q_sign_repost_mean`自体は
有効なデータ。best実測 0.355 は、訂正後target 0.48 に対しては相対的にずっと近い(旧target比で
「半分以下」だったが新target比では7割程度まで来ている)。

`scripts/stage2c_bo_calibration.py`(次のスイープ、本ドキュメントと同時に作成)はQ_TARGET=0.48で実行する。
