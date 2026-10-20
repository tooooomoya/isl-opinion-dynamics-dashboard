# 2026-10-14 Feed 100%比較：ネットワーク位置 × X

## 結論

全３方式×５seed、15本が完了。フォロワー50+層では、For YouのRESHAREが64.8%、ChronoのPOSTが62.6%、TrendのPOSTが53.3%。フィード方式に応じて、高入次数ノードの行動配分が変わる。これはXの符号を含む個人の属性とは別に、同じ初期グラフ・個人Xで確認した方式差である。

X帯の差は階層・方式によって異なり、端ほどオリジナル投稿が増えるという単調な役割分化を前提にしない。下のseed別符号の表と左右別セルで再現性を確認する。群間の行動割合の差は観測された政策の関連であり、個人にとって最適な役割や均衡への収束の証明ではない。

<!-- feed-role-figures:start -->
## 図で確認する

青＝POST、橙＝LIKE、緑＝RESHARE。平均とseed別の変動を分けて確認する。

中央帯：|X|<1/3、中間帯：1/3≤|X|<2/3、端：|X|≥2/3。
 
### 1 | Action choice by follower group

![1 | Action choice by follower group](figures/feed-position-x-2026-10-14/01_roles_by_followers.png)

Five-seed mean action shares, pooling X groups. Row labels also give each follower group's share of the whole population (agent counts, not action counts).

[SVG](figures/feed-position-x-2026-10-14/01_roles_by_followers.svg) · [PDF](figures/feed-position-x-2026-10-14/01_roles_by_followers.pdf)

### 1b | Action choice by feed, X group, and follower count

![1b | Action choice by feed, X group, and follower count](figures/feed-position-x-2026-10-14/05_stacked_roles_by_x.png)

Columns are feed modes; rows are Neutral, Moderate, and Extreme. Within each panel, contiguous bars show the five follower groups. Blue = POST, orange = LIKE, green = RESHARE. Population labels are joint X × follower-group shares of the whole population, not percentages within the X group.

[SVG](figures/feed-position-x-2026-10-14/05_stacked_roles_by_x.svg) · [PDF](figures/feed-position-x-2026-10-14/05_stacked_roles_by_x.pdf)

### 2 | Action shares by X group and follower count

![2 | Action shares by X group and follower count](figures/feed-position-x-2026-10-14/02_position_x_action_heatmaps.png)

Rows are follower-count groups; columns are Neutral, Moderate, and Extreme X groups. POST, LIKE, and RESHARE have separate panels with fixed 0–100% scales.

[SVG](figures/feed-position-x-2026-10-14/02_position_x_action_heatmaps.svg) · [PDF](figures/feed-position-x-2026-10-14/02_position_x_action_heatmaps.pdf)

### 3｜XによるPOSTの違いは、seedごとに再現するか

![3｜XによるPOSTの違いは、seedごとに再現するか](figures/feed-position-x-2026-10-14/03_x_effect_seed_variation.png)

seedの線は同じseed内のX帯間の比較。誤差帯や信頼区間ではなく、５本の実測runとその平均を示す。

[SVG](figures/feed-position-x-2026-10-14/03_x_effect_seed_variation.svg) · [PDF](figures/feed-position-x-2026-10-14/03_x_effect_seed_variation.pdf)

### 4｜For Youから切り替えると、POSTは何ポイント変わるか

![4｜For Youから切り替えると、POSTは何ポイント変わるか](figures/feed-position-x-2026-10-14/04_paired_post_differences.png)

同じseed・同じ階層・同じX帯でのPOST選択率の差。色の尺度は両パネル共通の−60〜+60pp。小注記は差が正だったseed数。

[SVG](figures/feed-position-x-2026-10-14/04_paired_post_differences.svg) · [PDF](figures/feed-position-x-2026-10-14/04_paired_post_differences.pdf)

<!-- feed-role-figures:end -->
## 結果の解釈

図表更新（2026-10-14）：図1・図2のタイトル、軸、凡例、注記を英語化。図1には各フォロワー階層の全人口に対する割合（５seed平均：0人23.1%、1–4人39.3%、5–19人25.3%、20–49人7.1%、50+人5.2%）を追加。図2のX帯名称はNeutral / Moderate / Extremeとし、閾値は従来どおり1/3と2/3。PNG・SVG・PDFを更新。



1. **Feedが高入次数ノードの行動配分を変える。** 50+層のPOST/LIKE/RESHAREはFor You 23.1/12.0/64.8%、Chrono 62.6/4.0/33.4%、Trend 53.3/11.0/35.7%。同じseedでFor Youから切り替えると、50+層全体のPOSTはChronoで+29.9〜45.3pp、Trendで+15.7〜44.4ppとなり、５seedすべてで増える。X帯別には一部で逆転するセルもあるため、全個人で同じ効果とは言わない。
2. **周辺層の分化は方式ごとに違う。** フォロワー0人層ではFor YouとTrendは約３分の１ずつの混合政策、ChronoはPOST44.7%、LIKE30.0%、RESHARE25.4%。5–19人層ではFor YouのRESHARE56.3%、ChronoのPOST52.4%、Trendは34.5/31.9/33.6%とほぼ混合。Trendの特化は主に最上位層に現れる。
3. **Xによる方向は単調でなく、Feedとの相互作用がある。** Chronoの5–19人層で端−中央のPOST差は−9.3/−6.7/−20.8/−9.7/−13.9pp、５seedすべてで中央帯の方が多い。For Youでは中間帯のPOSTが中央帯より多い傾向があり、5–19人層で４/５seed、50+層でも４/５seedで正。一方、端−中央の差は弱く、seedによって反転する。Trendの中位以下ではX帯の差も小さい。
4. **役割分化と報酬の大小は別。** 全体の平均報酬はFor You19.714、Chrono17.031、Trend14.602。適合度は0.795/0.640/0.658、承認は0.191/0.212/0.072。For Youがこの効用で高いことは、承認が最大という意味ではない（承認はChronoの方が高い）。各人に最適な行動を学習したと証明するには反実仮想の行動比較が必要。
5. **二軸だけで個人の役割を決められる段階ではない。** 次数×Xの群間成分は、全個人の経験的政策JSDの15.6%（For You）、9.6%（Chrono）、3.4%（Trend）。位置に応じた分化は明瞭だが、同じセルの中の個人差が大きい。これはエントロピー分解の記述値であり、因果的説明率やR²ではない。
6. **意見形成ではなく、行動と可視性の差。** 個人Xは固定。露出内容の全体分散はFor You0.154、Chrono0.346、Trend0.344。オリジナル投稿分散は約0.33/0.31/0.33で、For Youの露出分布が狭くなっている。個人内feed分散やユーザー意見の分極化と読み替えない。RESHAREはソースのXを保つため、端の属性の人の再共有が端の内容を表明することとも限らない。

３方式の３行動可用率は主要セルでFor You・Trendほぼ100%、Chrono約97%。空feedだけで高入次数層の大幅な政策差を説明することは難しい。ただし候補供給量や在庫の違いは本比較に含まれており、順位付け単独の効果ではない。

## 実験条件と比較の範囲

全15本完了。各方式seed 0–4、n=1000、20,000 step、η=0.03、k=20、状態なしbandit、rewire off、X固定。For Youの既存seed 0–2を再利用、残り12本を追加。元のeta実験の凍結ソースと観測用クラスを使用。

現在の完了seed数：chrono=5, foryou=5, trend=5。

- For You：100%・5 hop・β=10・更新するX̂への適合による確率抽出。
- Trend：100%・5 hop・再共有速度に基づく優先順位と距離による受理確率。
- Chrono：100%・フォロー先から届く直近のFIFO窓より抽出。現実の新着順ソートではなく、候補窓内はshuffleする現在の実装。
- 他の能動パラメータは固定：τ=0.1、探索率既定0.05、q_init=40、HK(m=15,A=4,pt=0.05)、ρ_L=ρ_R=0.3、寿命200、stock承認報酬、raw適合度、feed容量10、訪問確率0.1。
- For YouとTrendは最大5 hop、距離減衰exp・λ=0.11。Chronoは直接フォロー先の投稿窓であり、候補集合・在庫・順位付けを全て含むフィード方式の総合比較。順位付け単独の因果効果ではない。
- 同じseedのグラフ辺集合と個人別X・フォロワー数を方式間で照合。政策によって乱数消費が変わるため、イベント単位の乱数を対応させた反実仮想実験ではない。
- 評価窓はstep 15001–20000。セル内は個人の行動割合を等重み平均、その後seedを等重み平均。X帯は中央 |X|<1/3、中間 1/3≤|X|<2/3、端 |X|≥2/3。左右別と閾値0.25/0.75も保存。

## 全体の結果

| Feed | POST/LIKE/RESHARE (%) | 平均報酬 | 適合度 | 承認 | 個人政策JSD | feedサイズ | 空feed率 (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| chrono | 49.5/16.6/33.9 | 17.031 | 0.640 | 0.212 | 0.396 | 6.73 | 2.88 |
| foryou | 30.1/25.6/44.3 | 19.714 | 0.795 | 0.191 | 0.265 | 10.00 | 0.00 |
| trend | 34.9/31.0/34.1 | 14.602 | 0.658 | 0.072 | 0.451 | 10.00 | 0.00 |

### 二軸と個人政策の違い

個人の経験的政策分布のJSDをエントロピーで分解した記述指標。群間JSDは群平均政策の差の大きさ（群人数で加重）を表し、個人を群平均へ置換した際に残る政策多様性。因果的な説明率や回帰の決定係数ではない。

| Feed | 次数群間JSD | X群間JSD | 次数×X群間JSD | 全個人JSDに対する群間成分 (%) |
|---|---:|---:|---:|---:|
| chrono | 0.0325 | 0.0025 | 0.0381 | 9.6 |
| foryou | 0.0304 | 0.0038 | 0.0409 | 15.6 |
| trend | 0.0099 | 0.0005 | 0.0141 | 3.4 |

### 意見・投稿・露出の分散

opinionVarは固定された個人X、postOpinionVarは当該stepのオリジナル投稿内容（RESHAREを含まない）、exposureOpinionVarは当該stepに全feedへ届いた内容を露出回数で加重した全体分散。個人内feed分散の平均ではない。値は末尾5000 step平均。

| Feed | 個人X分散 | オリジナル投稿分散 | 露出内容分散 | 露出内容平均X |
|---|---:|---:|---:|---:|
| chrono | 0.337 | 0.311 | 0.346 | 0.052 |
| foryou | 0.337 | 0.325 | 0.154 | 0.113 |
| trend | 0.337 | 0.333 | 0.344 | 0.075 |

## X × フォロワー数：行動配分

各セルはPOST / LIKE / RESHARE (%)。

### foryou

| フォロワー数 | 中央 | 中間 | 端 |
|---|---:|---:|---:|
| 0 | 30.7/35.7/33.6 | 33.5/33.1/33.5 | 32.8/34.9/32.3 |
| 1-4 | 30.3/31.8/37.9 | 33.8/29.7/36.6 | 31.2/29.6/39.3 |
| 5-19 | 21.7/17.1/61.3 | 34.0/16.2/49.8 | 27.7/14.1/58.2 |
| 20-49 | 19.3/12.3/68.4 | 34.9/16.2/48.9 | 28.0/14.5/57.5 |
| 50+ | 15.2/10.7/74.1 | 32.8/15.1/52.1 | 19.3/10.5/70.2 |

### chrono

| フォロワー数 | 中央 | 中間 | 端 |
|---|---:|---:|---:|
| 0 | 46.8/28.5/24.7 | 44.4/29.8/25.8 | 43.1/31.3/25.7 |
| 1-4 | 49.6/16.3/34.1 | 48.3/19.0/32.7 | 45.2/18.9/35.9 |
| 5-19 | 58.0/7.0/35.0 | 53.7/7.5/38.8 | 45.9/8.5/45.6 |
| 20-49 | 60.8/4.6/34.6 | 61.3/4.8/33.9 | 44.4/4.6/50.9 |
| 50+ | 63.4/3.7/32.9 | 68.3/4.1/27.6 | 56.8/4.2/39.0 |

### trend

| フォロワー数 | 中央 | 中間 | 端 |
|---|---:|---:|---:|
| 0 | 31.5/35.2/33.4 | 32.7/33.1/34.2 | 33.7/32.1/34.2 |
| 1-4 | 32.7/32.9/34.4 | 31.5/33.6/34.9 | 34.9/33.3/31.8 |
| 5-19 | 34.1/30.8/35.1 | 34.8/32.8/32.4 | 34.4/31.9/33.7 |
| 20-49 | 34.0/26.3/39.7 | 44.7/20.5/34.7 | 44.7/20.3/35.0 |
| 50+ | 59.2/10.8/30.0 | 52.5/10.2/37.2 | 48.9/11.0/40.1 |

## X差のseed別再現性

同じ次数区間でPOSTの差を比較。+のseed数は処置X帯のPOSTが中央帯より多かったseed数。５seed平均の符号だけで普遍的なX効果とは言わない。

| Feed | 階層 | 中間−中央 POST差 (pp) | +のseed数 | 端−中央 POST差 (pp) | +のseed数 |
|---|---|---:|---:|---:|---:|
| foryou | 5-19 | 12.3 | 4/5 | 6.1 | 3/5 |
| foryou | 20-49 | 15.6 | 4/5 | 8.7 | 4/5 |
| foryou | 50+ | 17.6 | 4/5 | 4.1 | 4/5 |
| foryou | ALL | 7.1 | 4/5 | 3.2 | 4/5 |
| chrono | 5-19 | -4.3 | 0/5 | -12.1 | 0/5 |
| chrono | 20-49 | 0.5 | 3/5 | -16.4 | 0/5 |
| chrono | 50+ | 4.9 | 4/5 | -6.6 | 2/5 |
| chrono | ALL | -1.8 | 0/5 | -6.9 | 0/5 |
| trend | 5-19 | 0.6 | 3/5 | 0.3 | 3/5 |
| trend | 20-49 | 10.7 | 5/5 | 10.7 | 5/5 |
| trend | 50+ | -6.6 | 3/5 | -10.3 | 1/5 |
| trend | ALL | 0.4 | 2/5 | 1.7 | 4/5 |

## 左右別：フォロワー50+層

符号側のセルは少数になり、次数区間内の正確な次数や近隣配置も一致しない。左・右の差をモデルの普遍的な性質として解釈しない。

| Feed | X帯 | POST/LIKE/RESHARE (%) | 最少セル人数/seed |
|---|---|---:|---:|
| foryou | left_edge | 28.0/15.2/56.7 | 5 |
| foryou | left_middle | 31.3/18.8/49.9 | 4 |
| foryou | central | 15.2/10.7/74.1 | 11 |
| foryou | right_middle | 36.4/12.5/51.1 | 7 |
| foryou | right_edge | 11.4/6.5/82.0 | 8 |
| chrono | left_edge | 59.6/4.1/36.3 | 5 |
| chrono | left_middle | 64.0/4.4/31.5 | 4 |
| chrono | central | 63.4/3.7/32.9 | 11 |
| chrono | right_middle | 73.8/4.0/22.2 | 7 |
| chrono | right_edge | 53.0/4.8/42.1 | 8 |
| trend | left_edge | 47.2/10.8/42.0 | 5 |
| trend | left_middle | 48.9/11.0/40.1 | 4 |
| trend | central | 59.2/10.8/30.0 | 11 |
| trend | right_middle | 53.7/10.2/36.2 | 7 |
| trend | right_edge | 50.6/10.3/39.2 | 8 |

## 同じseedでの方式差

符号は処置−For You。各seedの対応セルを引いてからseed平均する。SDは５つのseed差の標準偏差であり、個人を独立な実験単位と扱わない。

| Feed−For You | 階層 | X帯 | POST差 (pp) | LIKE差 (pp) | RESHARE差 (pp) | 報酬差 | RESHARE差のseed SD (pp) |
|---|---|---|---:|---:|---:|---:|---:|
| chrono | 50+ | middle | 35.5 | -11.0 | -24.5 | -4.458 | 21.0 |
| chrono | 50+ | ALL | 39.4 | -8.0 | -31.4 | -4.168 | 5.7 |
| chrono | 50+ | central | 48.2 | -7.0 | -41.2 | -5.133 | 5.9 |
| chrono | 50+ | edge | 37.4 | -6.2 | -31.2 | -3.014 | 14.0 |
| chrono | 5-19 | middle | 19.7 | -8.6 | -11.1 | -2.364 | 7.6 |
| chrono | 5-19 | ALL | 24.4 | -8.1 | -16.4 | -2.210 | 1.8 |
| chrono | 5-19 | edge | 18.2 | -5.6 | -12.6 | -3.194 | 4.5 |
| chrono | 5-19 | central | 36.3 | -10.0 | -26.3 | -1.164 | 6.2 |
| chrono | 0 | middle | 11.0 | -3.3 | -7.7 | -3.852 | 2.4 |
| chrono | 0 | ALL | 12.3 | -4.7 | -7.6 | -3.720 | 1.5 |
| chrono | 0 | central | 16.1 | -7.2 | -8.9 | -2.833 | 2.0 |
| chrono | 0 | edge | 10.3 | -3.6 | -6.7 | -4.347 | 3.5 |
| trend | 50+ | middle | 19.7 | -4.9 | -14.8 | -3.182 | 19.6 |
| trend | 50+ | ALL | 30.2 | -1.1 | -29.1 | -2.721 | 11.6 |
| trend | 50+ | central | 43.9 | 0.1 | -44.0 | -3.181 | 16.4 |
| trend | 50+ | edge | 29.5 | 0.5 | -30.1 | -1.713 | 14.1 |
| trend | 5-19 | middle | 0.8 | 16.7 | -17.4 | -8.431 | 6.5 |
| trend | 5-19 | ALL | 6.5 | 16.1 | -22.6 | -8.038 | 1.7 |
| trend | 5-19 | edge | 6.7 | 17.8 | -24.5 | -8.629 | 7.1 |
| trend | 5-19 | central | 12.5 | 13.7 | -26.2 | -7.174 | 3.2 |
| trend | 0 | middle | -0.8 | 0.0 | 0.7 | -3.469 | 3.3 |
| trend | 0 | ALL | 0.4 | -1.4 | 1.0 | -3.367 | 2.5 |
| trend | 0 | central | 0.8 | -0.6 | -0.2 | -2.437 | 2.9 |
| trend | 0 | edge | 0.9 | -2.8 | 1.9 | -4.062 | 6.1 |

## 持続性・可用性・初期値

前半・後半2500 stepで最多行動が同じ割合。両半窓30訪問以上の個人を対象。標本誤差や固定個人環境を含む。可用率は全３行動を選べた訪問の割合を個人別に計算して平均した値。

| Feed | 階層 | X帯 | 最多行動一致率 (%) | ３行動可用率 (%) | 初期値残存>5%の個人 (%) | 最少セル人数/seed |
|---|---|---|---:|---:|---:|---:|
| foryou | 0 | central | 47.9 | 100.0 | 0.0 | 63 |
| foryou | 0 | middle | 35.7 | 100.0 | 0.0 | 64 |
| foryou | 0 | edge | 51.0 | 100.0 | 1.0 | 65 |
| foryou | 5-19 | central | 67.0 | 100.0 | 0.0 | 74 |
| foryou | 5-19 | middle | 66.0 | 100.0 | 0.0 | 73 |
| foryou | 5-19 | edge | 71.0 | 100.0 | 1.0 | 77 |
| foryou | 50+ | central | 86.7 | 100.0 | 6.5 | 11 |
| foryou | 50+ | middle | 79.9 | 100.0 | 7.2 | 14 |
| foryou | 50+ | edge | 84.9 | 100.0 | 1.3 | 14 |
| chrono | 0 | central | 64.4 | 97.0 | 0.0 | 63 |
| chrono | 0 | middle | 64.5 | 97.0 | 0.0 | 64 |
| chrono | 0 | edge | 60.7 | 97.0 | 0.0 | 65 |
| chrono | 5-19 | central | 72.7 | 97.1 | 0.0 | 74 |
| chrono | 5-19 | middle | 75.1 | 97.2 | 0.0 | 73 |
| chrono | 5-19 | edge | 68.9 | 97.1 | 0.0 | 77 |
| chrono | 50+ | central | 80.7 | 96.9 | 0.0 | 11 |
| chrono | 50+ | middle | 80.0 | 97.0 | 0.0 | 14 |
| chrono | 50+ | edge | 73.9 | 97.1 | 0.0 | 14 |
| trend | 0 | central | 76.0 | 100.0 | 0.0 | 63 |
| trend | 0 | middle | 68.3 | 100.0 | 0.0 | 64 |
| trend | 0 | edge | 67.6 | 100.0 | 0.0 | 65 |
| trend | 5-19 | central | 72.2 | 100.0 | 0.0 | 74 |
| trend | 5-19 | middle | 70.7 | 100.0 | 0.0 | 73 |
| trend | 5-19 | edge | 64.7 | 100.0 | 0.0 | 77 |
| trend | 50+ | central | 80.5 | 100.0 | 1.2 | 11 |
| trend | 50+ | middle | 82.3 | 100.0 | 1.1 | 14 |
| trend | 50+ | edge | 84.1 | 100.0 | 0.0 | 14 |

## 個人内報酬差

両行動30更新以上の個人のみを対象に、セル内の中央値をseed平均。選択時の状況・履歴は一致せず、行動の因果的な優劣の証明ではない。

| Feed | 階層 | X帯 | POST−LIKE | RESHARE−LIKE | RESHARE比較の対象人数・seed平均 |
|---|---|---|---:|---:|---:|
| foryou | 0 | central | 0.001 | 0.002 | 60.0 |
| foryou | 0 | middle | -0.002 | 0.000 | 72.4 |
| foryou | 0 | edge | 0.001 | -0.000 | 67.6 |
| foryou | 5-19 | central | 0.142 | 1.291 | 48.2 |
| foryou | 5-19 | middle | 0.441 | 0.941 | 56.4 |
| foryou | 5-19 | edge | 0.225 | 1.353 | 44.0 |
| foryou | 50+ | central | 0.207 | 0.200 | 4.2 |
| foryou | 50+ | middle | -0.006 | 0.070 | 9.0 |
| foryou | 50+ | edge | 0.128 | 0.045 | 7.0 |
| chrono | 0 | central | 0.002 | 0.010 | 25.6 |
| chrono | 0 | middle | -0.011 | -0.008 | 24.0 |
| chrono | 0 | edge | -0.125 | -0.043 | 30.4 |
| chrono | 5-19 | central | 3.111 | 2.157 | 27.8 |
| chrono | 5-19 | middle | 2.542 | 2.322 | 32.4 |
| chrono | 5-19 | edge | 2.330 | 2.302 | 33.6 |
| chrono | 50+ | central | 0.965 | 1.003 | 2.0 |
| chrono | 50+ | middle | 0.845 | 0.653 | 3.2 |
| chrono | 50+ | edge | 0.677 | 1.289 | 4.8 |
| trend | 0 | central | -0.040 | 0.009 | 43.8 |
| trend | 0 | middle | -0.025 | 0.008 | 38.8 |
| trend | 0 | edge | -0.024 | -0.038 | 46.0 |
| trend | 5-19 | central | 0.059 | 0.033 | 49.8 |
| trend | 5-19 | middle | -0.049 | 0.006 | 47.4 |
| trend | 5-19 | edge | 0.073 | 0.058 | 46.2 |
| trend | 50+ | central | -0.708 | -1.180 | 4.2 |
| trend | 50+ | middle | 2.771 | 0.851 | 5.6 |
| trend | 50+ | edge | 0.675 | 0.663 | 7.6 |

## 解釈上の制限

Xは全runで不変なので、集団の意見が変化して分極化したとは言えない。比較するのは行動配分・報酬・投稿と露出の構成である。フォロワー数の層はネットワーク位置の一側面。高次数×X×符号のセルは少数になり、５seed平均だけで安定した普遍的な役割を断定しない。
RESHAREはソース投稿のXを保った自分名義のコピーであり、将来のLIKEはコピー作者の承認になる。端のXを持つノードが再共有しても、再共有内容が端のXであるとは限らない。作者属性の役割分化と内容の分極化を混同しない。
個人別snapshot_fit / snapshot_recognitionは最終訪問の観測であり、末尾窓平均ではない。主要結果の全体適合度・承認はresults.csvの末尾5000 step平均を使用する。

## 再現・保存

実行：`python3 scripts/feed_role_compare.py --parallel 12`。解析のみ：`python3 scripts/feed_role_analysis.py`。途中集計は未完了と明記し、完了済みrunのみ読む。
`results/feed_role_compare/manifest.json` に全条件・凍結ソースのハッシュ・compiled classハッシュを保存。run別の完了情報は各feed_s*.json。個人別individuals.csv、run別cells.csv、seed平均cells_aggregate.json、方式差paired_cells.csv / paired_aggregate.json、全体summary.csv / summary_aggregate.json。logs/feed_role_compareに実行ログ。

## 追加診断：LIKEの動機と巨大ハブのRESHARE（2026-10-14）

POSTが受ける承認の発生機構と、その承認を学習更新でどの行動へ帰属するかは区別する。POSTは本人の現在Xを投稿し、受信LIKEが本人のrecognitionへ反映される。一方、今回のstock報酬は存続する本人の全投稿への承認を次回訪問の報酬に含め、直前行動へ帰属するため、過去POSTの承認をLIKE/RESHAREが学習する経路もある。POSTの承認収益が実装されていることだけで、各行動のQ差を因果的な利得差とは読めない。

この固定グラフ・5hop設定では、フォロワー0人の作者は他者からのfollow方向の到達集合に入らず、Chronoでも他者へ直接配信されない。最終snapshotで、0人層1155 agent×seed/方式のrecognitionは全て0だった。周辺で「POSTの承認収益がないので、情報環境を調整する行動が相対的に候補になる」という解釈は妥当。ただし0人層のLIKE率はFor Youでも約35%で、LIKEへの全面的な特化を示すものではない。

巨大ハブをフォロワー200人以上として再集計すると、５seedで84 agent×seed。個人割合をseed内で等重み平均し、さらにseed間で平均したPOST/LIKE/RESHAREは、For You26.5/7.5/66.0%、Chrono65.9/5.3/28.8%、Trend55.4/9.8/34.7%。For Youの最終訪問recognitionはseed平均0.886であり、ハブの承認が得られないから再共有へ逃げている、と単純に説明する状況ではない（この値は末尾窓平均ではない）。

RESHAREには、①ソース内容を自分名義で配信しコピーへの将来LIKEを自分の承認にする経路、②ソースのXで推薦プロフィールX̂を更新する経路がある。②は今回LIKEと同じ更新率0.3で、POSTにはない。自分のXに固定されたオリジナル投稿に対し、RESHAREではFor Youのfeedからソース内容を選べる。選んだ内容が受け手にも好まれるなら、ハブの配信力を使って承認を得る利点になるが、その内容適合の寄与は今回の集計では未分解。

以上は実装から特定できる利得経路と観測の対応であり、どの経路が選択の原因として支配的かは未確定。200+層の個人内POST/RESHARE比較は、両行動30更新以上の対象がFor Youでは16/84 agent×seedに限られ、seed別の平均報酬差の中央値も正負が混在する。現在の行動頻度からRESHAREの因果的な優位を証明しない。

切り分ける比較候補は、効用や他の更新率を固定したまま、(a)RESHARE時のX̂更新のみを止める、(b)再共有コピーへの承認帰属を変える、の段階的比較。いずれもモデルの機構を変更する介入であり、今回は実行していない。
