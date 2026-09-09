# 2026-07-16 Feed機構(chrono / For-You)の設計レビューと決定

## 決定1: フィード合成アーキテクチャを維持(DECIDED 2026-07-16)

現行の二層構成——**chronological-from-follows**(followeeのpost/repostのみ、有向、`postCash`から一様抽出)+ **For-You**(velocity上位、`h`ホップ以内、割合`α`で混合)——をそのまま維持する。

**理由:** `α`(algorithmic share)と`h`(reach)を振ることで、本セッションで議論した仮説群——
- 公称αと実現αの乖離(下記issue 2)
- moderate hubの"沈黙conduit"仮説(hubが投稿せず、位置だけでh-hop reachを介して他者の露出を変える)
- Type1(構造分離)vs Type2(affective)の切り分け(Gauthier et al. 2026, Nyhan/Guess et al. 2023との対応)

をすべて単一のsweep軸上で検証できる。アーキテクチャを変える必要はない。

## 決定2: "soaring/小口アカウント優遇"要件の撤回(DECIDED 2026-07-16、`research-direction.md:176`に反映済み)

velocityのfollower数正規化なし(absolute count)を正式な設計として確定。小口アカウント発見はこの研究の目的ではない。結果として、velocity機構は実質「今伸びているアカウント/hubの可視性を上げる」機構であり、divisive-content amplifierでも小口アカウント優遇機構でもない、と明記。この特性を動機づけに使う際、Milli et al. 2023(engagement-content-intensity相関)のような文献は誤った動機づけになるため引用しないこと。

## 未決定・要検証:issue inventory

以下は「バグ」「要測定の交絡」「既知の許容済みトレードオフ」に分類。次のアクションを決めるための一覧。

### [方針決定・実装待ち] 1. windowed velocityのdtが常に1

`OpinionDynamics.java:183` で `admin.rankByVelocity(step)` は毎ステップ1回呼ばれる。`windowedVelocityScore`(`AdminOptim.java:178-185`)の `dt = step - lastStep` は常に1になり、"直近ステップでのreposts純増数"という生カウントに退化している——`windowed`という名前が意図した平滑化効果を持たない。

**なぜ`VELOCITY_WINDOW`と同じ100を再利用してはいけないか(2026-07-16確認):** 更新間隔をプールの寿命(100ステップ)と揃えると、1投稿が生涯で受けるスコア再計算がほぼ1回きりになり、windowedモードの存在意義(伸び悩んだ投稿を降格し、今伸びている投稿を昇格する)が消える。加えて、更新直後に生まれた投稿は次の更新境界まで最大100ステップFor-Youに一切現れず、配信リストも100ステップ丸ごと固定されてしまう(「recency-biased engagement ranking」という設計意図と矛盾)。

**決定・実装済み(2026-07-16、`AdminOptim.java`):** 更新間隔を`VELOCITY_WINDOW`から独立させ、`1/accessProb`(既定`accessProb=0.1`→10ステップ)で決める。根拠:(a) chrono側の`postCash`実効窓(下記issue 5参照)と同じ自然なタイムスケールになり、chrono/For-You間で"tempo"の一貫性が取れる、(b) `VELOCITY_WINDOW`の1/10なので投稿生涯で約10回のスコア再評価機会が確保でき、stalled burstの降格が機能する解像度になる、(c) `SimParams.accessProb`は元々「the model's global timescale knob」と自己文書化されており(`SimParams.java:51-52`)、この選択はコードベース自身の既存の設計思想と整合する。

実装:`AdminOptim`に`cachedRanked`/`lastRankStep`を追加し、`rankByVelocity(step)`は`velocityRankInterval() = max(1, round(1/accessProb))`未満の間隔では再スコアリング・再ソートをスキップしてキャッシュを返す(`AdminOptim.java` `velocityRankInterval()`/`rankByVelocity()`)。`pruneRecentPosts`と本体の再計算はrefresh stepでのみ実行。

**検証済み(`src/test/ModelTests.java` `testVelocityRankingCache`, `testChronoRootDedup`, 2026-07-16):** 軽量アサーションハーネス(JUnit不使用、既存の`ModelTests`規約に準拠)に2件追加。
- `testVelocityRankingCache`:更新間隔内(`access_prob=0.2`→interval=5)ではランキングが完全に凍結(同一リストインスタンス)されること、間隔を超えると再計算され、直近増分0のstalled burstが直近増分ありのcurrently-rising投稿に順位を逆転されることを確認(全5アサーションPASS)。
- `testChronoRootDedup`:同一`rootPostId`を持つ2つの別リレー(異なる`postId`)がpostCashにあるとき、配信feedには1つだけ残ることを確認(全3アサーションPASS)。
- 実行:`java -cp bin test.ModelTests`。無関係な既存失敗3件(`bc_dec 0.999`、`[tag]`2件)はコミット済みHEAD時点で再現することを確認済み(stashして検証)——今回の変更が原因ではない。

### [要測定] 2. 公称α ≠ 実現α

`AdminFeedback`(`AdminOptim.java:272-288`)はグローバルに1本のvelocityランキングを作り、ユーザーごとに`withinReach`でフィルタしながら`algoSlots`件拾う。小さい`h`・疎な到達範囲では埋まりきらず、`forYou.size() < algoSlots`のまま終わることがある——設定した`α`と実際に配信されたFor-You比率が乖離しうる。`feedForYouCountMean_i`は記録されているが、「nominal αに対する実現率」を直接見る指標がない。h-sweepの前に追加すべき計測。

### [既知・未解消のcaveat] 3. h=1 reachのundirected vs chronoのdirected不整合

`computeReachable`(`AdminOptim.java:220-239`)はfollowees∪followers(無向)でBFS。一方`postCash`(chrono供給源)はfollowees限定(有向、自分がフォローする相手の投稿のみ)。`research-direction.md`のcaveat (i)としてすでに記録済みだが未解消。h=1は「chronoの穏健な並べ替え」という位置づけ(`research-direction.md:177`)だが厳密には別集合。

### [修正済み] 4. PostCashの重複によるchronoの暗黙的velocity漏れ

`PostCash.addPost()`(重複排除なし)+ repost配信(`OpinionDynamics.java:221-224`、repostのたびに全followerのpostCashへコピー追加)により、複数のfolloweeが同じpostをrepostすると、そのpostがpostCash内に多重に乗り、一様ランダム抽出のはずのchronoが実質的に多重度加重抽出になる問題。窓が平均10ステップ(下記issue 5参照、当初「約1ステップ」としたのは誤り)あるため、想定より頻繁に起こりうる。

**修正(2026-07-16、`AdminOptim.java:262-296`実装済み):** repost(relay)は`Agent.relay()`/`Post.relayOf()`によって毎回新しい`postId`を持つが`rootPostId`(オリジナルの系譜ID)は継承される。chronoスロットの抽出を`rootPostId`単位でdedupするよう変更(シャッフル後、未出現の`rootPostId`のみ`chronoSlots`件まで採用)。あわせて、For-You側とchronoの重複排除チェックも`postId`ベースから`rootPostId`ベースに変更(異なるリレーコピーが両チャンネルに別々に載る抜け穴も塞いだ)。コンパイル確認済み。

### [整理] 5. 3つの異なる"window"は別スケールで動いている

| 名称 | 値 | 対象 | 定義箇所 |
|---|---|---|---|
| `VELOCITY_WINDOW` | 100ステップ | For-You候補プール(`recentPosts`)の保持期間 | `Const.java:17` |
| `REACH_REFRESH_INTERVAL` | 100ステップ | hop到達可能集合のキャッシュ更新間隔(コンテンツと無関係、計算コスト対策) | `Const.java` |
| `postCash`容量 | `feedCapacity`(既定10) | chronoの候補プール。固定長10のFIFO。`agent.resetPostCash()`(`OpinionDynamics.java:271`)は`accessProb`判定(`OpinionDynamics.java:191-192`)に外れた非アクティブstepでは`continue`によりスキップされるため、リセットは**本人が実際にアクティブだったstepの直後**にのみ起きる。実効的な記憶窓は直前アクティブstepからの間隔=幾何分布、平均`1/accessProb`(既定`accessProb=0.1`で**平均10ステップ**) | `Agent.java:85,208-209,271`, `OpinionDynamics.java:190-194` |

**訂正(2026-07-16):** 当初「実効窓は約1ステップ」と記載したが誤り。`resetPostCash()`は`accessProb`ゲートの内側にあり非アクティブstepではスキップされるため、正しくは平均`1/accessProb`(既定10ステップ)。For-You側(100ステップ)とchrono側(平均10ステップ)は1桁スケールが違う——意図的な設計だが、「chronoのプールサイズ」という独立パラメータは存在せず、`feedCapacity`を転用している点は明示しておく価値がある。この10ステップという時間スケールは、issue 1のランキング更新間隔の決定にも流用できる(同じ自然な"population turnover"のタイムスケール)。

### [解決済み・参考] 6. feedCapacity二重ハードコード問題

2026-07-09に修正済み。`Agent`コンストラクタに`AdminOptim`のfeedCapacityと独立した"10"がハードコードされており、`feed_capacity=`スイープが無効化されていた(経緯は`Agent.java:81-85`のコメントに記録)。現在は両者とも`SimParams.feedCapacity()`を参照するよう統一済み。

## 保留中の仮説(未決定、次セッションで詰める)

**"沈黙conduit"仮説**(2026-07-16議論):moderate hubが`postEnabled=false, repostEnabled=false`でも、followグラフ上の橋渡し位置だけでh-hop reachを介して他者のFor-You露出を変えうる。`unfollow()`(`Agent.java:511-531`)の2分岐——①既存フォロー先への「辺を切る」backfire、②未フォロー先への「blockのみ(辺なし)」——のうち、For-You由来の不快な投稿はほぼ確実に②を通る。②は`follow()`(`Agent.java:440-447`)がblock済みユーザーを候補から除外するため、「既存の辺を切る」のではなく「将来の辺形成を妨げる」形でセグリゲーションに寄与する——従来のstructural backfire effect(journal.tex、分岐①想定)とは異なるミクロ機構。(i) hub不在 (ii) hub存在・沈黙 (iii) hub通常稼働、の3群比較で検証可能。まだ実験設計として確定していない。
