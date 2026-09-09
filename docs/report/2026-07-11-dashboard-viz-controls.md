# 2026-07-11 — ダッシュボード可視化コントロール(ネットワーク描画・色スケール・時間再生)

`scripts/dashboard.html` のネットワークスナップショット/2-Dプレーンに対する
インタラクション強化。いずれもモデル非依存で、汎用監視ツールという方針
([[dashboard-generic-tool]])に沿う。

## 決定と根拠

1. **枠への張り付き対策(fit-to-frame)。** `simTick` の力学積分にあった壁クランプ
   (`if(x[i]<M)…`)を撤去。クランプは境界に触れたノードを壁に貼り付け、レイアウトが
   キャンバスに収まらないときにノードが壁沿いに集積する見た目を生んでいた。代わりに
   `drawNet` が毎フレーム、現レイアウトのbounding boxをキャンバスの**約9割**に収まるよう
   相似変換(`fitView`:中央寄せ+等方スケール、退化レイアウトの暴発防止に `k≤6`)で
   投影する。シミュレーション座標系と画面座標系を分離したので、絶対座標の広がりに
   関係なく必ず枠内に収まる。ホバー判定も同じ変換を通す。**supersedes** 固定マージン
   `M=14` のハードクランプ。ノード半径は画面px固定(スケール `k` の影響を受けない)ので
   可読性を維持。

2. **色スケールをユーザ編集可能に。** 従来は opinion=固定diverging、その他=固定viridis。
   ユーザ要望により、数値属性は**両端＋中央の3点**を選ぶ2-stopグラデーション
   (`gradColor`)、カテゴリ属性は**カテゴリごとのパレット**(`getCatPalette`)に変更。
   カテゴリ属性として `opsign`(意見符号 −/0/+)と `hub`(介入ハブか否か)を追加。
   選択中のcolor属性に応じて `renderColorControls` が `#netcolorctl` にピッカーを出し分け、
   凡例(`updateNetLegend`)も追従。設定は `localStorage`(`netgrad` / `netcat.<attr>`)に
   永続化。opinionのグラデーション域のみ [-1,1] 固定(`fixedDomain`)、他はデータ範囲で正規化。
   **注意:** opinion分布ヒートモード(`renderOpinion`)が依存する固定 `seqColor`(viridis)は
   別関数として存置 — こちらのノード着色(`gradColor`)とは用途が別。

3. **時間シーケンスバー＋再生。**
   - ネットワーク: `#netScrub`＋`#netPlay`。利用可能なGEXFスナップショット(step 0,5000,…)を
     スクラブ/再生。`startNetPlay` は 1.8秒間隔で `fetchNetwork` を進める。初回は
     betweenness等の構造計算で律速、以降はサーバー側のファイルサイズキーcacheで即時。
     位置はstep間で引き継がれるので、ソーティングが進む様子が見える。
   - 2-Dプレーン: `#planePlay`。`state.scrub` をstep0→最新まで約6秒で走査し軌跡を
     漸進描画(`startPlanePlay`、step範囲は `renderPlane` が `state.planeRange` に格納)。
     手動スクラブ/liveで停止。

## 検証

ヘッドレスChromeで実データ(seed 0/1/2、step40kまでのGEXF 9枚)に対しロードし、
`window.onerror`/`unhandledrejection` を捕捉:JS例外なし、`refresh` 完走
(`#ostats` 更新)、ネットワークは 1000ノード/9985エッジで描画(`fitView` 適用)、
`#netScrub` は9スナップショット(max=8)、gradientピッカー3点・play各ボタンをDOMで確認。

## 付記(並行編集）

本作業中、同ファイルが別セッションで並行編集(カードのリサイズ/並べ替え機能、
opinion密度ヒートマップ等)されていた。手順2で `seqColor` を一旦削除した際、
ヒートマップ側の依存を壊して `seqColor is not defined` を誘発(=`refresh` 例外→
「server unreachable」バナー)。固定 `seqColor` を存置して解消。`refresh` が全処理を
単一 `try/catch` で括り、描画中の例外もサーバー到達不可として表示する設計が誤解の
温床である点は未修正(要改善候補)。
