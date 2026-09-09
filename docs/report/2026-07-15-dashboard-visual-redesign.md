# 2026-07-15 ダッシュボード: `docs/tasks/dashboard_design_refinement/` 準拠のビジュアル刷新

## 背景

`docs/tasks/dashboard_design_refinement/README.md` + `Opinion Dynamics Dashboard.dc.html`
（design reference prototype）に基づき、`dashboard/dashboard.html`（2385行、実データ配線・
resizable/reorderable card・network force-sim・in-page color picker等を含む本番ダッシュボード）
の見た目を刷新した。プロトタイプは6指標・5seed固定のモックだが、本番は43+指標/family・
任意seed数・GEXFネットワーク解析など遥かに広い機能を持つため、**「データ配線とインタラクション
機能は温存し、デザイントークン/タイポグラフィ/コンポーネント意匠だけを刷新する」**方針で作業した。

## 変更内容

1. **デザイントークン刷新。** `:root`/`@media (prefers-color-scheme: dark)`/
   `[data-theme=light|dark]` の値を design reference のパレットに合わせて置換
   (`--page`→#f6f7f9/#0a0d12, `--surface`→#ffffff/#12161f, `--ink2`→#5b6472/#9aa4b2,
   `--muted`→#98a2b3/#5b6472, `--good`/`--bad`/`--warn`/`--accent` 等)。既存のJS/CSSが
   参照する変数名(`--surface`, `--ink2`, `--muted`, `--accent`等)はそのまま残し、値だけ
   差し替えることで書き換え範囲を局所化した。新規に `--panel-soft`, `--lapis-mid`,
   `--lapis-ink`, `--lapis-100/50`, `--gold`, `--shadow-card` を追加。
2. **タイポグラフィ。** Google Fonts Inter を導入し本文フォントに設定。ただし
   **SVGチャートの軸ラベルだけは system-ui のまま維持**した — Inter の等幅数字が
   system-ui より横幅が広く、`drawHistChart`等の固定ピクセルマージン
   (`HG.L=28`など)に対して軸ラベル("800.0"等)がSVG viewBox の外(x<0)にはみ出し、
   デフォルトの `overflow:hidden` でクリップされる回帰を screenshot 検証で発見したため
   (詳細は「検証で見つけた不具合」参照)。
3. **コンポーネント意匠。** ボタン/セレクト/chipを pill 型(radius 999px, padding 7px 14px)に、
   カード(`.panel`, `.panel.card`, `.stattile`)を radius 14px + `box-shadow:var(--shadow-card)`
   に統一。seed chip・ドット・statusラベルは design reference の仕様値に整合。
4. **ヘッダー再構成。** タイトル+ステータス行(pulse アイコン付き)を左の `.titleblock` にまとめ、
   進捗バー+既存コントロール群(pause/interval/smooth/show mean/reset zoom/theme)を右に配置
   (`justify-content:space-between`)。テーマ切替ボタンは32×32の円形アイコンボタン化。
5. **Metrics セクション新設。** carousel の上に eyebrow "METRICS" + heading "Trends over time"
   を追加し、現在選択中の指標を常時表示するグラデーション pill chip 列(`#metricChips`,
   `renderMetricChips()`)を新設 — クリックでその指標を非表示にできる(既存の
   `#pickerlist` チェックボックスと同じ状態を操作)。43+指標をすべて chip 化すると
   スケールしないため、詳細指標選択は既存の `<details id="picker">`("more metrics…"に改称)
   に残した。design reference の「6指標固定chip」とはこの点で意図的に異なる。
6. **Structure / Behavior セクション見出し。** eyebrow("STRUCTURE"/"BEHAVIOR") +
   Title Case 見出し(`h3.big`)を追加。同様に "2-D outcome plane"→"Outcome Plane",
   "opinion distribution over time"→"Opinion Distribution", "network snapshot"→
   "Network Snapshot" に変更(technical subnote文言は変更なし)。
7. **JSカラーパレット整合。** `SERIES_LIGHT/DARK`・`BINS_LIGHT/DARK`・`opColor()`・
   `stopsDefault()`(ネットワーク色スケールの既定グラデーション)を新トークンに整合。
   `SERIES_*` は5色分だけ差し替え、6色目以降(6 seed超で使う予備色)は不変(spec不定義のため)。
8. **network snapshot canvas の背景。** design reference通り `--panel-soft` を背景に設定
   (従来は透明でカード背景と同化していた)。

## 検証で見つけた不具合(今回の変更で修正)

- **軸ラベルの Inter フォントによるクリップ**(上記2.)。`svg text` に Inter を適用した結果、
  `drawHistChart` の bounded confidence / post probability distribution で
  y軸ラベル("800.0"等)の先頭文字が viewBox 外にクリップされていた。`svg text` は
  system-ui に戻して回避。
- **`drawHistChart` の左マージン不足(独立した既存バグ)**。上記のクリップはフォント変更を
  戻した後も再現したため、`HG.L=28` が元々 (Inter 抜きでも) ぎりぎりで、カードpadding拡大の
  有無に関わらず潜在していた既存の作図バグと判断。`HG.L` を28→34に拡張して解消。
  今回の刷新のスコープ外の不具合だが、触っているコンポーネントの可読性に直結するため合わせて修正した。
- **数値入力欄のプレースホルダー切れ**。新しい `input[type=number]` の共通padding(3px 8px)により、
  固定幅(`width:52px`/`4.5em`)だった `#smoothWindow`/`#netwmin`/`#netwmax` の
  プレースホルダー("auto"/"min"/"max")が見切れていた。幅をそれぞれ64px/5.5emに拡張して解消。

## 意図的にデザイン仕様から外した点

- **Metric card の delta バッジ**(design reference: 各カードに前後差分%のバッジ)は実装しなかった。
  実データの delta 計算(どの seed 基準か、smoothing窓との整合等)は新規のデータロジックであり、
  「既存の見た目を刷新する」スコープを超えるため見送り。
- **Q_sign / E-I index の統合**。design reference は1カードに Q_sign と E-I index を
  2本線で重ねる想定だが、本番は「指標ごとに複数seedを比較する」情報設計のため、
  従来通り指標ごとに独立したカード(`qsignei` group: qsign/ei)を維持した。
- **アプリタイトル文言は変更していない**("run.sh live dashboard" のまま)。design reference の
  "Opinion Dynamics — Live Monitor" は placeholder mock のタイトルであり、実アプリの
  識別名(run.sh ラッパー由来)を上書きするのは見た目刷新の範囲外と判断。

## 検証

- `node --check` でJS構文確認(スクリプトブロック抽出)。
- `dashboard/dashboard.py --serve` を起動し、実行中の実run(logs/配下の実データ)に対して
  Playwright(Chromium headless)で screenshot 検証。light/dark 両テーマ、
  Metrics/Outcome Plane/Opinion Distribution/Network Snapshot/Network Structure/
  Agent Behavior の全セクションを確認。`console --errors` 相当のpageerror/console.error
  収集は0件。
- metric chip クリックでの指標非表示、seed chip クリックでの表示切替(`.chip.off`)を
  実際にクリックさせて動作確認。
