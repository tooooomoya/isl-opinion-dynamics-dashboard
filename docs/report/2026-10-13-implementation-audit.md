# 2026-10-13 実装監査：行動・推薦・計測・実験実行

**結論：最初に指摘したQ学習の行動マスクと重複反応は、監査中に入った修正によって通常の実行経路では改善している。ただし、投稿禁止を破る処理、固定ハブの変動、古い推薦到達集合、実験失敗の成功扱い、CNNの無限ループ、ログからの誤った集計などが残っている。**

本監査は理論・新規性レビューとは別に、実装が指定条件と整合して動くかを確認したもの。モデル本体は変更していない。確認中に `Agent.java` / `OpinionDynamics.java` / `ModelTests.java` が更新されたため、その後の修正版を一時ディレクトリへコピーして検証した。最後に現行ソースとのSHA-256一致も確認した。

対象版、コードのアーカイブ、再現スクリプト、全検証結果は [監査添付ディレクトリ](2026-10-13-implementation-audit/) に保存した。旧レビューの「未修正」の記述を現在の状況として読まないこと。

## 1. 検証の範囲と方法

対象：Agent、Post、PostCash、AdminOptim、OpinionDynamics、SimParams/ExperimentConfig、InterventionSetup、Analysis、AssertionCheck、Writer、GEXF読込・書出し、全CLIネットワーク種別、run.sh、dashboardのログ・数値・カスケード処理。

| 検証 | 条件 | 結果 |
|---|---|---|
| 既存ModelTests | 修正版の現行ソース | 94項目PASS |
| 追加Java契約チェック | 独立した入出力・不変条件 | 37チェック中13 PASS / 24 FAIL |
| Python・実験実行・表示チェック | スタブ失敗、間引き、部分CSV、条件選択 | 10チェック中2 PASS / 8 FAIL |
| 通常条件の統合実験 | 4条件×3 seed、N=64、1001 steps、assert毎step | 主要保存則・schemaは通過。全12 runで最終診断窓の欠落を確認 |
| フィード不変条件 | 100 seed | 容量・自作投稿除外・root重複除去・生存条件・投稿pool保存則を通過 |
| フォロー管理 | 5000回の追加/削除 | 正逆インデックス・フォロワー数の一致を確認 |
| HK生成 | N=60、m=15、A=1、pt=.05、1000 seed | 今回は出次数不足を検出せず |
| ネットワークsmoke | 10生成器のseed0、N=64、5 steps | 完走。CNN seed123は生成中に停止 |
| 境界条件の実験 | silence、pin+mu、small WS、l_ref=0、window=0 | 下記の破綻を再現 |

通常条件の4条件は WS/chrono/static、DBA/For You/static、WS/Trend/static、WS/Trend+For You/rewire。統合実験では、投稿pool保存則、生成数の増分、行動share、CSV構造、mu=0での意見分散、再共有ログ数、actor–rootの再共有一意性などを確認した。行ごとのチェックは計72,189回だが、独立実験数は12であり、チェック回数を検証の網羅性や統計的標本数とは扱わない。

FAIL数は不具合数ではない。同じ原因を複数条件で検証している。追加チェックにはAPIの直接呼出し、非常に大きいbeta、非デフォルトのlocale等も含み、それらと通常実行の問題を以下で分ける。

## 2. 最初の2問題：修正後の評価

### Q学習の行動マスク：通常経路で修正を確認

`Agent.observeAndLearn()` は `availableActions()` を使って次状態のmaxを取るようになった。`rewire=false`、空フィード、like/reshareに大きい値が残る条件で、利用可能なPOSTのQだけを参照することを再現テストで確認した。以前の問題を現行コードに残っているとは判定しない。

ただし「利用可能行動なし」の場合の選択側は別の問題がある（A1）。

### 重複いいね・再共有：通常経路で防止を確認、API側の防御は残課題

`likedPostIds` と `resharedRoots` が導入された。いいね済み投稿はlike候補から外れ、全投稿がいいね済みならLIKE行動も選ばれない。同じrootの別コピーも再共有対象から外れ、自分のオリジナルも再共有しない。統合12 runの再共有ログでactor–root重複は検出しなかった。

一方、`Agent.like()` 自体を同じ投稿へ2回直接呼ぶと、今もカウンタが2になる。現在の単一スレッドの通常ループは選択側のfilterで防いでいるため、これは **現在の通常経路で二重加算が続く証拠ではない**。APIの利用者が増えたり、別の行動経路を追加した際に再発しうる防御不足として区別する。

修正候補：最終的な反応実行地点でも一意性を保証し、成功/不成立を返す。外側の反応数・プロフィール更新・寿命更新は成功したときだけ行う。pick側だけを修正しても将来の経路追加を守れない。

## 3. 優先して修正すべき問題

### A1 高 — 行動がないと投稿禁止を破ってPOSTする

場所：[Agent.java](../../src/agent/Agent.java)、`chooseAction()` の `ok[POST] = true`。

`rewire=false`、channel NONE、空フィードで、許可行動がないとPOSTを強制する。探索確率0/1の両方で再現。修正前の例外は避けているが、禁止条件の違反が残った。

実際のmainでも `n=24, steps=1, access_prob=1, trend_share=0, rewire=false, silent_until_ids=0, activation_step=20` で、沈黙中の1人を含め24人全員が投稿した。沈黙した人が初期の投稿供給を作ってしまう。

修正：明示的なNONE/no-opを返す。学習・訪問・行動shareの分母をどう扱うかも揃える。POSTを代替行動として使わない。

### A2 高（mu>0のpin介入）— 固定したハブが動く

場所：[Agent.java](../../src/agent/Agent.java) の `updateValues()`、[InterventionSetup.java](../../src/experiment/InterventionSetup.java) の `pinHub()`。

pinはstubbornness=1を設定するが、意見更新はglobalなmuのみを使っている。`mu=.1, extreme=SYM` の2-step実験で、固定値 +1 が .8771、−1 が −.9104に動いた。

さらに最終stepに違反が発生したため、ログには `AC Error` があるのに最終集計は0、終了コードも0だった（A6と組み合わさる）。`pin_opinion_ids` の設定でも固定の実装を統一する必要がある。基準mu=0にはこの変動は出ない。

修正：targetという集計除外フラグと、固定意見という制御フラグを分け、更新側が固定を尊重するようにする。

### A3 高（動的ネットワークの推薦）— フォローを変更しても古い到達範囲を使う

場所：[AdminOptim.java](../../src/admin/AdminOptim.java) の `ensureReachable()` / `selectForYou()`、`addFollowEdge()` / `removeFollowEdge()`。

到達集合は100 stepsごとの更新で、辺の変更で無効化されない。hop1で0が1をフォロー→2へ交換した直後、TrendとFor Youのどちらも2ではなく1の投稿を出すことを再現した。

単なる実装上の近似として選んでいるなら、その時間遅れがモデルの一部になる。現行の説明は現在のfollow graphによるhop制約なので、それと厳密には一致しない。静的ネットワーク版には影響しない。

修正：辺変更時にcacheを無効化する、またはgraph revision単位で更新する。近似を残すなら設定・ログ・頑健性評価に更新間隔を含める。

### A4 高 — 書き込みに失敗してもバッファを捨てて継続する

場所：[Writer.java](../../src/writer/Writer.java) の `appendToFile()` / `flushBatch()`。

出力先の親が通常ファイルである条件を作ると、I/O例外を表示するだけでflushは正常に戻り、その後バッファ長が0になる。保存されていないデータを破棄している。`PrintWriter` は書込中のエラーを内部に保持する場合もあるが、`checkError()` も使っていない。

修正：I/O失敗を呼出し元へ伝え、保存成功前にバッファやstartedフラグを更新しない。実験は非0で終了する。checkpoint/config/Gephi出力にも例外の握りつぶしがあり、必要な成果物の失敗を一貫して扱う。

### A5 高 — Java実験の失敗がバッチ全体では成功になる

場所：[run.sh](../../run.sh) の `run_one()` / `xargs ... bash -c`、[OpinionDynamics.java](../../src/dynamics/OpinionDynamics.java) のmain。

親シェルの `set -e` は `bash -c` の子へ自動継承されない。Javaが42で終了するスタブで現行 `run_one()` をそのまま実行すると、後続の `[END]` を書いて関数は0で終了した。xargsからも成功に見える。

mainも出力先衝突・フォルダ作成失敗で `return` するので、実行していないrunが終了コード0になる。これは無効な条件が後続の集計へ入る原因になる。

修正：Javaの終了コードを明示的に保存し、成功時だけEND、失敗時はFAILとそのコードを返す。Java側の失敗も非0へ統一する。

### A6 高 — assertion違反が最終集計から消え、NaNも検出しない

場所：[AssertionCheck.java](../../src/analysis/AssertionCheck.java) の `reportASError()` / `assertionChecker()`。

- 集計ループが `i < maxStep` で、最終stepの違反を落とす。
- `o < -1 || o > 1` はNaNに対してどちらもfalseなので検出しない。
- 違反を見つけてもシミュレーションは非0終了しない。
- stepsがassertIntervalの倍数でないと、最終状態のチェック自体も行われない。

pin実験とsmall WS実験で、違反ログと「sum=0」の同居を実際に確認した。l_ref=0の実験は承認・QがNaNになったのにsum=0、終了コード0だった。

修正：最終stepまで集計し、必ず終了時に検証する。意見・Q・報酬・プロフィールの有限性、正逆辺、pool保存則、行動可用性も検証し、重大違反時は非0とする。

### A7 高（CNN）— 合法なseedで初期ネットワーク生成が無限ループ

場所：[ConnectingNearestNeighborNetwork.java](../../src/network/ConnectingNearestNeighborNetwork.java)、ランダム辺追加のdo–while。

初期2ノードは互いに接続済み。ランダム辺追加に入ると、選んだfromに未接続の他ノードが存在せず、target探索が終了しない。

`network=cnn, seed=123, n=64` で再現。network RNG最初の2値が .723174… と .990898… で、ノードを追加せず、この分岐へ入る。5秒timeoutで生成の `start making network` から進まず、コード上も接続先が存在しないため終了不能。seed0は完走しており、単一seed smokeでは見逃す。

修正：未接続候補を列挙し、空なら追加をスキップまたは成長分岐に戻す。無制限の再抽選を使わない。

### A8 高（実験再現性）— 全設定が記録されず、異なる条件が衝突する

場所：[ExperimentConfig.java](../../src/experiment/ExperimentConfig.java) の `tag()`、[InterventionSetup.java](../../src/experiment/InterventionSetup.java) の `writeConfigLog()`。

介入ハブが0ならrun_configはヘッダーだけ。介入があってもFor YouやQの多くの設定がない。次の4組が全て同じ出力先になった。

| 変える条件 | 衝突した値 |
|---|---|
| interaction_window | 100 / 200 |
| q_tau | .1001 / .1002 |
| read_path | a.gexf / b.gexf |
| pin_opinion_ids | 0:.1 / 0:.9 |

修正：全実効設定をrun単位で保存し、丸める前の正規化設定からIDを生成する。コード版、dirty状態、入力ファイルhashも保存する。

### A9 高（表示結果の信頼性）— 間引いたイベントから件数・top・カスケード構造を再計算する

場所：[dashboard/core.py](../../dashboard/core.py)、`CsvTail` / `api_repost()` / `api_post_lifespan()`。

時系列表示用の間引きをイベントログにも適用し、残った行だけで集計する。

- 寿命1000の投稿を1つ、寿命1の投稿を9つ置いた例で、topの1000が消えて最大1になる。
- 本来10件なのに `n=4` と返す。
- 7ノードの鎖のstructural viralityは2.6667だが、辺が間引かれるとrootから届く2ノードだけを使い1.0になる。

再現にはthreshold=4を使ったが、製品側の8000でも同じ間引き処理が発動する。これは単なる折れ線の表示精度ではなく、集計とグラフ構造の破損。元CSVやJavaの累積指標自体をこの問題で書き換えているわけではない。

修正：イベントの正確な集計・top-K・cascade再構成を行ってから、表示点だけを間引く。大規模ならstreaming集計を使う。

## 4. 特定条件・補助機能で確認した問題

| ID | 問題・再現条件 | 影響と修正候補 |
|---|---|---|
| B1 | `SimParams.from()` がNaNや範囲違反を受理。追加15ケース全て通過 | l_ref=0でNaN、window=0でゼロ除算。finite・正値・確率範囲・state境界順序・列挙値を入口で検証 |
| B2 | 未知/撤去キーを無視。`bc_dec=.99` はエラーにならない。`init_dist=empirical` も受理してuniformへフォールバック | 旧スクリプトやtypoが意図と違う実験を作る。未知キー・未対応値は明示的に拒否 |
| B3 | `GephiReader` はexportされた `accessprob` を、`accessProb` と比較する | 0.8を保存して読んでも0.1になる。attribute id→titleを解決して型付き読込 |
| B4 | GEXF読込でopinion=.5の後にintrinsic=.1を設定すると、currentも.1に上書きされる | mu>0等で現在値と初期値が違う入力を壊す。読み終わってから独立して設定 |
| B5 | GEXF namespace1.2draftでは辺0→1が0本になる。欠損ファイルも例外を表示後に空graphを返す | `network=read` が別の初期状態で継続しうる。形式を検出/検証し、不完全入力は失敗として返す |
| B6 | n=8にdefault ws_out=15でWSを作ると自己辺ができる | 小規模smokeが別モデルになる。nとout-degreeの整合を拒否または明示的clamp |
| B7 | beta_h=1000で指数重みが全て0になる | like pickが末尾を選び、rewireが不成立、For Youは候補ありでも空。距離の最小値を引いてからexp等、安定化する。default beta=3では今回検出せず |
| B8 | `computeFeedMetrics()` がtarget readerも集計する | 同じclassの一般reader平均−1がtargetの+1と混ざって0になる。他のpopulation系とfilterを揃えるか別指標として明記 |
| B9 | populationが0なら意見の平均・分散がNaN | 全員targetにする条件で再現。undefinedを明示し、一般の数値として集計しない |
| B10 | JavaのString.formatがdefault locale依存 | Germany localeで `step,value` の行が `0,0,5000` になり列数が崩れる。CSV・tag生成にLocale.ROOT |
| B11 | state_action/fit_quantilesは500stepごとのみ保存 | 1001stepsの全12 runで最後の訪問が欠落。500未満ならファイル自体がない。最終残余窓をflushし、窓長も保存 |
| B12 | outGroupExposureCountを計算するがresultsへ出していない | 計画したout-group outcomeが直接保存されない。分母と一緒に出力 |
| B13 | dashboardはABORTとOutOfMemoryErrorをrunningとする | runの選択・進捗確認を誤らせる。明示status/終了コードを読む |
| B14 | dashboardのneutral bandは常に.2 | Javaのneutral_band変更がcamp指標に反映されない。±.1はJavaでband=0なら対象だがdashboardでは除外。run設定を読む |
| B15 | run.shの中断処理は `pkill -f OpinionDynamics` | 自分が起動したrun以外の同名実験も終了させる。自分の子PIDまたはprocess groupだけを管理。これは静的に確認し、実際に既存プロセスを終了する検証は行っていない |

これらを全部「現在のdefault実験が壊れている」と扱うことはできない。例えばB3/B4/B5はread利用時、B10はlocale変更時、B7は非常に大きいbeta、B8/B9は介入・集計対象条件で発生する。

## 5. バグと断定しなかった事項

- フィード内のroot重複除去と、いいねのpost単位一意性は別の規則。同じrootの別コピーを1回ずついいねできることは、現行の規則と矛盾しない。
- like/repostの反応を同step中に即座に反映するため、承認観測には更新順序が関わる。これは非同期更新の選択であり、同期を要求しない限りバグとは断定しない。
- chronoの訪問後全消去、候補不足時に空き枠を残すこと、reshareの承認を再共有者に付けることは設計選択。
- Trendのランキングcache更新間隔は実装されている設計。更新前に新規投稿が出ないことを、それだけでバグとはしない。
- `postLifespanMean` は最後の再共有までの期間で、最後のいいね・死亡までの期間ではない。`postStillActiveAtEvictionFrac` は自然死では原理的に0になる（死亡時には最後の反応からL超、最後の再共有はそれ以前）。現モデルの診断としては古い意味を引き継いでいるが、カウンタ誤加算とは区別する。
- いいね/再共有履歴の集合はrun全体で増える。死んだ投稿のliked IDも残るため長期実行のメモリ課題になりうるが、今回OOMを起こしたとまでは確認していない。
- 現行Q表のstateは反応履歴を含まない。これは状態抽象化の理論上の制約であり、今回の実装バグ一覧には入れていない。

## 6. 修正順と合格基準

1. **結果の破損・誤った成功を防ぐ：A4/A5/A6/A8。** 保存失敗・assertion違反・条件衝突で非0、必須成果物が揃い、設定が完全に保存される。
2. **行動と介入を守る：A1/A2、API側の一意性。** 禁止投稿0件、固定意見不変、反応不成立時に承認・寿命・プロフィール・反応数を変更しない。
3. **ネットワーク・推薦：A3/A7/B6/B7。** 辺変更後に到達集合が整合、合法seedで終了、自己辺なし、極端な重みでも定義された抽出になる。
4. **入力・出力・集計：A9/B1〜B5/B8〜B14。** 不正入力を拒否、readの属性を保持、非標準localeでも列数固定、全イベントから正確に集計、最後まで診断を保存する。

修正前の既存結果を自動で削除・上書きする必要はない。影響する条件を識別し、主要結果を修正後に新しいrun IDで再実行する。

## 7. 再現と記録

```bash
python3 docs/report/2026-10-13-implementation-audit/audit.py
```

ソースを一時領域へコピーし、そこでコンパイル・実験する。既存のresults/logs/binを上書きしない。既知の契約違反を検出するため、監査対象版では終了コード1が期待される。結果は冒頭に表示する新しい一時ディレクトリに保存される。

保存済み記録：[既存テスト](2026-10-13-implementation-audit/baseline-tests.txt)、[追加Javaチェック](2026-10-13-implementation-audit/contracts.stdout.txt)、[Pythonチェック](2026-10-13-implementation-audit/python-contracts.json)、[統合実験](2026-10-13-implementation-audit/integration.json)、[境界条件](2026-10-13-implementation-audit/edge-integration.json)、[ネットワークsmoke](2026-10-13-implementation-audit/network-smokes.json)、[対象版manifest](2026-10-13-implementation-audit/manifest.json)、[ソースsnapshot](2026-10-13-implementation-audit/source-snapshot.zip)。

検証の限界：大規模長期実行の資源限界、ブラウザの表示全体、旧スクリプト全件の実行、全ネットワーク・全数値の組み合わせを網羅したものではない。少なくとも、ここで問題として挙げた主要項目はコード追跡に加えて再現例で確認し、静的確認のみ/APIのみの項目は明示した。
