# 2026-07-17 ダッシュボード: yabeブランチからの機能移植(opinion trajectory / ForceAtlas2)

## 追記6(2026-07-17): ページ全体スクロールをやめ、yabeの固定ビューポート・シェルに変更

ユーザーから「今のスクロールページはやめて良いので、yabeの方を参考にして」との指示。
これまで温存していた「ページ全体が縦スクロールする」構造をやめ、yabeの
`body:height:100vh + 内部flex`シェルに変更した:

- `body`/`#appShell`を`height:100vh; overflow:hidden`の固定ビューポートにし、
  ヘッダー/バナー/シードバーを`flex:none`で常時表示、アクティブな`.tabpanel`
  だけが残り高さいっぱいに広がって**自分自身でスクロール**する
  (`flex:1 1 auto; min-height:0; overflow-y:auto`)。サイドバー(`#rail`)と
  ヘッダーはタブを切り替えてもスクロールで隠れない。
- **Opinion/Outcomeタブ**は内部スクロールさせず、`#topPairRow`をタブの全高まで
  伸ばし、中の2枚のカードを`min-height:0; resize:none`にして、SVG/canvasを
  `height:100%`で完全にフィットさせた(yabeの`.tabpanel[data-tabpanel="opinion"]`
  相当のルールを移植)。前回の「左側の図」がタブ全体を使って表示されるように
  なった。
- **Time Seriesタブ**はヘッダー部分(`#metricsHeader`)固定+`<main>`だけが
  内部スクロールする2段構成に。
- **Networkタブ**は(yabeのように"Graph"/"Metrics"のサブタブに分けるところまでは
  やらず)タブ全体を1つのスクロール領域とし、Network SnapshotのcanvasはCSSの
  `min-height:60vh`で見栄えの良いサイズを確保、Structure/Behaviorはその下に
  スクロールして到達する形にした — 指標をタブごとに分割する構造変更は
  「サイズ」の範囲を超えるため見送り、既存の1タブ構成のまま。

### レイアウト変更で見つかった実バグ2件(ヘッドレスChromeで検証して発見・修正)

このリポジトリにはブラウザでの目視確認手段がなかったため、
`/Applications/Google Chrome.app`をheadlessモードで起動し、Chrome DevTools
Protocol(`websocket-client`をpipインストール)経由で実際にタブ切り替え・
スクリーンショット・`getComputedStyle`等を検証した。その過程で以下の実バグを
発見し修正:

1. **`[hidden]`が効かず非アクティブなタブが表示され続ける**: 追加した
   `.tabpanel[data-tabpanel="opinion"] { display:flex; ... }`等のルールが、
   ブラウザ既定の`[hidden]{display:none}`より詳細度(specificity)が高く、
   `hidden`属性があってもタブが表示されたままになっていた。
   `.tabpanel[hidden] { display:none !important; }`に変更して修正。
2. **Network Snapshotのcanvasが、非表示中に測定されて縦に間延びする**:
   `startSim()`はcanvasの`clientWidth`/`clientHeight`を測って強制シミュレーションを
   初期化するが、Networkタブが非表示(display:none)の間はこれが常に0になり、
   JS側のフォールバック値(900×900)で初期化されてしまい、その"意図しない縦横比"が
   canvasのwidth/height属性に固定され、実際に表示された時にcanvasの高さが
   異常に間延びする(831pxなど)不具合があった。`startSim()`の先頭で
   「canvasが完全に非表示(0×0)なら何もせず抜ける」ガードを追加し、
   `switchTab()`のnetworkタブ有効化時に無条件で`startSim()`を呼ぶよう変更
   (以前は`if(netState.sim)`で「既に初期化済みの場合だけ」再計算していたため、
   非表示中に一度も初期化されていないケースを取りこぼしていた)。

opinion/outcomeタブ、network タブとも、修正後にヘッドレスChromeで
スクリーンショットを取得し、正しい見た目(タブの分離、canvasの妥当なサイズ、
グラフの中心寄せ)を確認済み。

## 追記5(2026-07-17): 残りのカードサイズをyabeと突き合わせ

「各カードのサイズとかも参考にして」との指示を受け、local/yabe両方のCSSを
セレクタ単位で機械的に diff し、サイズ関連の差分を洗い出した。既に一致済みだった
もの(`.panel.card`のmin-width/min-height/flex-basis、`.trio`/`.duo`のflex-basis、
チャートのviewBox定数`LC`/`PL`/`DG`/`ES`)を除き、純粋なサイズ調整として安全な差分
のみ反映:

- `.chip .dot`(seedバーのステータスドット): 8px→9px。
- `.cp-box`/`.cp-handle`(カラーピッカーモーダル): border-radius 14px→10px。
- `.cp-sv`(彩度・明度パッド): border-radius 8px→6px。
- `#banner`: border-radius 10px→8px。

**yabeに揃えなかったサイズ差**(理由付き):
- `#network`canvasの高さ/`.tabpanel[data-tabpanel="opinion"] > .panel.card`の
  `min-height:0`等 — yabeは`body`を`height:100vh`固定+内部flexで埋める
  レイアウトモデルのため、"サイズ0=残り全部埋める"が成立する。local側は
  通常のドキュメントフロー(ページがスクロールする)のままなので、同じ値を
  持ち込むとcanvasの高さが0に潰れる。レイアウトモデル自体を変える話になり
  「サイズ」の範囲を超えるため見送った。
- `#gridWrap`のCSS Grid方式によるメトリクスカードサイズ — カルーセル+featured行
  という別アーキテクチャのままなので直接比較できる値がない(前回の追記3で
  判断済みの内容を踏襲)。

## 追記4(2026-07-17): opinion/outcomeタブの左右順序・デフォルトビューをyabeに合わせた

ユーザーから「yabeブランチのopinion/outcomeにある左側の図(横軸ステップ・縦軸opinion)を
足して」との指示。該当の図自体(per-agent trajectory canvas)は追記2で機能としては
既に実装済みだったが、(1)`#topPairRow`内でOutcome Planeの右側に位置し、
(2)Opinion Distributionカードを開いた時のデフォルトはheatmap(bin-share密度)側で、
trajectoriesはプルダウンを切り替えないと出てこない状態だった — 「左側の図」という
説明と一致していなかったため、以下を修正:

- `#topPairRow`内の並びを入れ替え、Opinion Distribution(trajectories/heatmap)を
  左、Outcome Planeを右に(yabeの`opinion`データカード=左, `plane`データカード=右
  という並びに一致)。
- `state.opview`のデフォルトを`"heat"`→`"traj"`に変更 — trajectoriesがデフォルト
  表示になる(yabeも"R5, default opinion-tab view"としてtrajectoriesを既定にしている)。
- 左右の幅比をyabeに合わせ3:2(opinion側が広い)に(`.tabpanel[data-tabpanel="opinion"]`
  配下の`flex`値を指定)。
- 指標・データ計算ロジックの変更は無し(追記2で実装した`analysis.trajectory_data`/
  `api_trajectories`をそのまま使用)。

## 追記3(2026-07-17): フィルタUI・細かいサイズもyabeに合わせた

ユーザーから「指標の内容さえ変えなければ、フィルタとか、細かいUIも反映させていいよ。
大きさとか。」と追加の許可。前回見送った項目のうち、**指標そのものの内容(どの列が
存在するか・何を計算するか)を変えずに済むもの**を追加で反映した:

- `#pickerlist`(「more metrics…」の中の全指標チェックボックスリスト)を、
  多列CSSグリッドから yabe の単一カラム・行hover式(`min-height:30px`,
  hover時`background:var(--grid)`)に変更。中身は変わらず(同じ列名の
  アルファベット順フラットリスト) — 見た目の密度だけyabeに合わせた。
- `.duo, .trio`(Outcome Plane/Opinion、Network Structureのトリオ、Behaviorの
  duo/trio等で使う横並びカードグループ)のgapを20px→8pxに、
  `#gridCarousel`/`#gridFeature`(メトリクスグリッド)のgapも20px→8pxに、
  それぞれyabeの値へ変更 — より密度の高いレイアウトになった。
- **据え置いたもの**: ボタン/セレクトのpill形状(radius 999px, padding 7px 14px)は
  `docs/tasks/dashboard_design_refinement/README.md`で明示的に指定された値
  (「Pause/Resume pill button: 7×14px padding」等)なので変更していない —
  yabeは角丸矩形ボタン(radius 8px)で形状自体が異なり、これは「サイズ」ではなく
  「デザイン言語の選択」の話になるため対象外とした。カルーセル+featured行という
  2段レイアウト自体(yabeは単一の折り返しグリッド)も、拡大/縮小のインタラクション
  モデルは両者とも同じ(♢ボタンでfeatured化)なので、コンテナ構造の書き換えは
  リスク対効果が見合わないと判断し見送った。

## 追記2(2026-07-17): 各タブ中身のカードデザインもyabeに寄せた(できる範囲で)

ユーザーから「各タブの中身のデザインも合わせてみて。できるところは」との指示。yabeの
CSSを`.panel`/`.panel.card`/`.metriccard`単位で比較し、直接移植できる範囲(データ結線・
DOM構造を変えずにCSSのみで実現できる範囲)に限定して適用した:

- **カードのクロム**: yabeはチャートカード(`.metriccard`, `.panel.card` — メトリクスグリッド、
  Outcome Plane/Opinion Distribution、Network Snapshot)を「箱+影」ではなく
  「透明背景+上罫線のみ」のフラットな見た目にしている("less visual noise"方針)。
  これをそのまま移植 — 該当カードは`background:transparent; border-top:1px solid var(--border)`
  になり、hover/focus-within時に`border-top-color`が濃くなる。
  非カードの`.panel`(Network Structure/Behavior等のセクション包み、stattile)は
  引き続き箱+影のまま(yabeも同様にここは箱型を維持)、ただしpadding/radiusは
  yabeの値(radius 12px, padding 10px 12px 6px)に合わせて少し締めた
  (元は`docs/tasks/dashboard_design_refinement/`の設計スペックでradius 14px/padding
  16-20pxだったが、今回の指示で更新)。
- **draghandle・enlargebtn**: 常時表示だったのを、yabeと同じ「hover/focus時のみ
  opacity 1、それ以外は0.38」に変更 — ノイズが減る。
- **リサイズ角のヒント**: `.duo > .panel.card::after` / `.trio > .panel.card::after`で
  右下リサイズハンドルの視覚的ヒントをhover時のみ表示(yabeの実装をそのまま移植)。
  local側が既に確定していた「垂直方向のみリサイズ可能」(`resize:vertical`、
  2026-07-12の`60c6679`)は変更していない — yabeは`resize:both`だが、これは
  中身ではなく挙動の変更になるため据え置いた。
- **移植しなかったもの**: yabeは`#metricChips`のようなpill型メトリクスフィルタを
  持たず、代わりにサイドバー常設の`#pickerlist`(チェックボックスのカテゴリ別リスト)
  UIパターンに置き換えている。これは「中身の指標は今のまま」の方針(前回の指示)に
  反するため移植せず、既存のmetric chip UIをそのまま維持した。同様に、Network
  Snapshotの各種コントロール(layout/size/color等)をyabeのような専用`#netsidebar`
  カラムへ再配置することもしていない — インライン配置のまま。

## 追記(2026-07-17): サイドバー化・タブ構造もデザインとして移植

当初「他はデザイン参考のみ」としていたが、ユーザーから追加指示があり、yabeの
**サイドバーナビゲーション(`#rail`)とタブ構造(Time Series / Opinion&Outcome / Network
の3分割)を構造として移植**することにした。中身の指標・パネルは変更しない
(既存の`data-card`要素をタブ内に再配置するのみ)。

- 配色・トークンはyabe独自パレットではなく、このダッシュボードの既存design tokens
  (`--panel-soft`, `--accent`, `--lapis-*`等、`docs/tasks/dashboard_design_refinement/`の
  モックアップで導入済み)を流用 — 見た目の一貫性を優先。
- 3タブへの割り当て: timeseries=メトリクスグリッド(旧`<main>`前半)、
  opinion=Outcome Plane+Opinion Distributionの`#topPairRow`、
  network=Network Snapshot+Network Structure+Agent Behavior & Attributes。
  既存の要素ID・`data-card`属性は一切変更していない(タブでラップしただけ)ので、
  レンダリング関数群(`renderGrid`/`renderPlane`/`renderOpinion`/`renderStructural`/
  `renderBehavior`等)は無改修で動作する。
- yabeにあった各タブ専用の`#sidebar`(メトリクスpicker)/`#netsidebar`(ネットワーク
  コントロール一式)への移設は行っていない — 「中身は今のまま」の指示に沿い、
  既存のheader/カード内インラインコントロール配置を維持。
- canvas依存の2ビュー(Network Snapshotの`drawNet`、Opinion Distributionの
  `renderOpinionTraj`)は、タブが`display:none`の間は`host.clientWidth`が0になり
  誤ったサイズで描画されてしまう問題があったため、(1)タブ切り替え時に
  `switchTab()`が該当ビューを即座に再描画、(2)`initStaticCard`の`ResizeObserver`
  フック(既存の`netsnapshot`用に加えて`opinion`カードにも追加)がフォールバックとして
  効くようにした。
- サイドバーの折りたたみ(`#railToggle`、`body.sidebar-compact`)も実装、
  localStorageに永続化。
- HTMLパーサでタグの対応関係を検証し、`/api/summary`等の既存エンドポイントに
  非回帰がないことを確認済み。ブラウザでの目視確認は未実施 — 次回起動時に確認要。

## 決定(DECIDED 2026-07-17)

`dashboard-remote/yabe`ブランチ(前回同期: `44f1557`, 2026-07-12)に、その後6コミット分の
大幅なUI再設計(サイドバー化・タブ化・ナビゲーション刷新)が積まれていた。全面的な
`git subtree pull`によるマージは行わず、以下の**2機能のみを個別移植**し、残りは
デザイン参考に留めることをユーザーと合意した:

1. **per-agent opinion trajectory表示**(既存の「Opinion Distribution」パネルに
   heatmap/trajectoriesトグルとして追加)
2. **ForceAtlas2レイアウトアルゴリズム**(Network Snapshotパネルの既存force-directed
   レイアウトに、選択式の代替レイアウトとして追加)

見た目のデザイン(サイドバーナビゲーション、タブ構造、CSS design tokens等)は移植せず、
`docs/tasks/dashboard_design_refinement/`で進行中の社内モックアップ実装([b7855ec]
でコミット済みのWIP)をそのまま維持する。

## 経緯

- `git subtree pull --prefix=dashboard dashboard-remote yabe --squash`は
  `fatal: can't squash-merge: 'dashboard' was never added.`で失敗した。原因を
  調査したところ、前回の同期(`44f1557`)自体が`git subtree`コマンドを使わない
  手動コピー由来のコミットで、subtreeの分割点(split point)履歴が繋がっていなかった
  ため、以降`git subtree pull`が機能しない状態になっていたと判明。
  → 以降のyabe同期は、個別ファイルの手動diff/移植で行う方針とする
    (`docs/dashboard.md`のsubtree運用ノートは別途見直しが必要)。
- yabe側の`api_trajectories`/`gexf_trajectory_data`は、"done"な実行では
  `opinions.csv.xz`(全stepの全エージェント生opinionを持つファイル)を読む設計だったが、
  **このリポジトリのJava Writer(`src/writer/Writer.java`)はbinned
  `opinion/opinion_result.csv`しか書いておらず、per-agentの生時系列は一切出力していない**。
  そのためyabeの実装をそのまま移植することはできず、代わりに既存のNetwork Snapshot
  パネルが既に使っているGEXFスナップショット(`GEXF/<net>/step_*.gexf`、各ノードに
  `opinion`属性を保持)から軌跡を再構成する方式で実装した
  (`dashboard/analysis.py::trajectory_data`)。この結果、trajectoryはGEXF
  スナップショット間隔(典型的には5000step間隔、1 runあたり9点程度)でしか取れず、
  heatmapパネル(opinion_result.csvベース、per-step)より疎な時間解像度になる —
  これはこのパイプラインが書き出しているデータの制約であり、移植上の妥協ではない。
- ForceAtlas2 (`simTickFA2`)はyabeのコードをほぼそのまま移植できた。既存の
  `simTick`(d3-style spring/repulsion、`After github.com/soramame0518/
  Social-Media-Echo-Chamber`)と同じ物理シミュレーションの枠組み(グリッド近似による
  多体間力)を共有しており、選択式レイアウト(`netState.layout`)として並置している。
  yabeにあったノードピン留め機能(`s.fx`/`s.fy`によるドラッグ固定)と、`baseView`/
  `composedNetView`によるビューポート安定化は移植していない — 前者はUIごと未移植、
  後者は既存の`fitView()`(giant component基準の自動フィット、yabeより高機能)を
  そのまま使う方が一貫性があると判断したため。

## 実装箇所

- `dashboard/analysis.py`: `trajectory_data()`, `api_trajectories()`,
  `TRAJ_MAX_STEPS`/`TRAJ_MAX_AGENTS`定数を追加。
- `dashboard/api.py`: `/api/trajectories`ルートを追加。
- `dashboard/dashboard.html`:
  - `renderOpinion()`をディスパッチャ化し、既存実装を`renderOpinionHeat()`に改名、
    新規`renderOpinionTraj()`(canvas密度フィールド描画、agent別ラインをfinal opinionで
    着色)を追加。`#opview`セレクトで切り替え。
  - `simTickFA2()`を追加し、`netState.layout`(`force`|`forceAtlas2`)で`loop()`が
    ティック関数を出し分け。`#netlayout`セレクト + repulsion/attraction/gravity/
    velocity retention/prevent overlapのコントロール一式(`netState.fa2`,
    `localStorage`永続化)を追加。

## 動作確認

`dashboard/dashboard.py --serve`をローカル一時ポートで起動し、`results/run_2_...`
(seed 2, 1000 agents, GEXFスナップショット9点)に対して`/api/trajectories`が
`shown=total=1000`、9 step分の軌跡を返すこと、既存の`/api/network`・`/api/opinion`が
非回帰であることを確認した。ブラウザでの目視確認(canvas描画・トグルUI)は
ヘッドレスブラウザが環境になく未実施 — 次にダッシュボードを開いた際に目視確認すること。
