# 2026-07-18 ダッシュボード外部リポジトリのブランチ再構成

## 決定(DECIDED 2026-07-18)

`ISL-opinion-dynamics-dashboard`(このリポジトリの`dashboard/`とgit subtreeで同期している
独立リポジトリ、remote名`dashboard-remote`)は、これまで`main`ブランチ=このプロジェクト
(tomoya)の作業、`yabe`ブランチ=共同研究者の作業、という2ブランチ構成だった。しかし`main`は
「最後にpushした人の内容」になっており、モデル非依存の汎用ベースとしては機能していなかった。

以下のブランチモデルに再構成した:

- **`main`**: 特定モデルに依存しない汎用ベース。yabe/tomoya両フォークの「いいとこどり」。
  今後の汎用的な改善はここにマージする。
- **`toomoya`**(新設): このプロジェクト(polarized-vocal-minority-model)専用フォーク。
  再構成前の`main`の内容をそのままコピー(履歴・内容とも無変更)。
  このリポジトリの`dashboard/`は今後こちらとsubtree同期する(`docs/dashboard.md`/
  `dashboard/README.md`のpush/pullコマンドを`main`→`toomoya`に更新済み)。
- **`yabe`**: 変更なし。

## 比較調査

再構成に先立ち、`main`(=旧tomoya作業)と`yabe`の`core.py`/`analysis.py`/`api.py`/
`dashboard.html`/`README.md`を機能単位で比較した(researchエージェントに委託)。要点:

- 両ブランチはすでにUIシェル(サイドバー+3タブ、ForceAtlas2、per-agent trajectory表示)を
  共有していた — 2026-07-17の個別機能移植(`2026-07-17-dashboard-yabe-feature-port.md`)の
  成果が効いている。
- 残る差分は大きく2種類:
  1. **ハードコードされた、モデル固有の文字列・定数**(main側に集中): 別モデルのデータに
     向けると黙って誤動作/無意味な表示になりうるもの。
  2. **バックエンドのラン検出アーキテクチャそのものの違い**: mainはフラットseed型
     (`logs/run_<seed>.log`+単一root+ディレクトリ名からのtag正規表現抽出)、yabeは
     `run_meta.json`マーカー型(複数root・再帰探索、`/api/meta`、mtime staleness検知、
     パターングルーピングUI付き)。

## スコープ判断: Tier1+2のみ実施、Tier3(ラン検出アーキテクチャ交換)は見送り

(1)の除去・汎用化は今回の`main`再設計で実施した。(2)への全面置き換えは、本番で使われている
ツールの中核ロジックの交換であり、実際のランディレクトリに対する動作確認ができない状況での
実施はリグレッションリスクが見合わないと判断し、**別タスクとして意図的に見送った**。

### `main`に実施した変更(Tier1+2)

- `dashboard.html`: `<title>`/ヘルプ内のwelcome文言をモデル名なしの汎用文言に変更。
  `METRIC_DESC`(旧45エントリの論文固有指標プロース)を空に。`SECTION_HELP`の6エントリを
  「データにあれば」という書き方に一般化。`DEFAULT_METRICS`を空配列に(ピッカーは
  何も事前選択しない状態でスタート)。`NODE_ATTRS`/`SIZE_KEYS`/`COLOR_KEYS`から論文固有の
  GEXFノード属性(`pp`=post probability、`bc`=bounded confidence、`hub`=intervened hub)を
  削除し、両フォーク共通の属性(opinion、in/out/total degree、opinion sign)のみに。
  `getMetricDesc`のファミリー剥離用正規表現を`/_[0-4]$/`→`/_\d+$/`に一般化。
- `core.py`: `FAMILY_RE`を`^(.+)_([0-4])$`(5クラス固定)→`^(.+)_(\d+)$`に一般化し、
  `api_summary`のファミリー判定ロジックも「0..4固定」から「0..N連続なら家族とみなす」
  (Nはデータ依存)に書き換え。`api_repost`(`posts/repost_cascades.csv`という
  このJavaパイプライン固有のスキーマに依存するcascade再構成の実装)をyabe同様の
  空スタブに置換、付随する`_cascade_virality`ヘルパーと未使用になった`SeedStore.repost`
  (`CsvTail`)も削除。
- `analysis.py`: `MODERATE_BAND_HALF_WIDTH`のデフォルトを`0.2`(Complex Networks 2026論文の
  現行手法上の選択)→`0.0`(素のsign分割、yabe相当)に変更 — このモデル固有の研究設計上の
  選択を汎用デフォルトとして持ち込まないため。`compute_structural`の次数・クラスタ係数計算を、
  Javaパイプライン固有の`degrees/`/`clusterings/`側CSVを読む方式から、既に読み込み済みの
  GEXFグラフから直接計算する方式(`G.in_degree()`/`G.out_degree()`/`nx.clustering()`)に変更
  — yabeの構造指標計算と同じ、外部CSV非依存の方式に統一。これに伴い`api_network`の
  follow/repost用CSVファイル名prefix切り替えロジックも不要になり削除。
- `README.md`: 全面書き直し。yabe側の簡潔な英語capability-manifestスタイルを採用し、
  新規「Plugin contract」節(モデルが自動検出を機能させるために提供すべきデータ規約:
  x軸カラム名、`<name>_<index>`ファミリー命名規則、GEXFノード属性の拡張ポイント、
  moderate-band閾値の拡張ポイント)を追加。論文固有の内容(`journal.tex`慣習への言及、
  この論文の指標名に紐づく拡張ウォークスルー等)は削除・トリム。Git Subtreeワークフロー節は
  汎用的なフォーク運用の説明として残しつつ、コマンド例を新ブランチモデル
  (`main`=汎用ベース、`toomoya`/`yabe`=コントリビューターフォーク)に合わせて更新。

### 見送った変更(Tier3、将来の別タスク)

- ラン検出モデルのyabe型(`run_meta.json`マーカー+複数root再帰探索)への全面置き換え
  (`core.py`の`active_seeds`/`result_dir`/`SeedStore`)。
- `/api/meta`ルートの追加。
- mtime-staleness に基づくstalled-run検知の追加。
- yabeにあるサイドバーのパターングルーピングUI(スイープフォルダ単位の折りたたみ表示)の移植。
- 複数ファイルにまたがる動的指標発見(yabeの`_scan_discovered_files`相当)への一般化
  (mainの現行実装は単一`results.csv`内のカラムのみを見る、より狭い版のまま)。

## 実施箇所

- 外部リポジトリ`dashboard-remote`(ローカルでは一時worktreeで作業):
  `main`ブランチに汎用化コミットをpush、新規`toomoya`ブランチ(再構成前`main`のコピー)をpush。
- このリポジトリ: `docs/dashboard.md`/`dashboard/README.md`のsubtree push/pullコマンド例を
  `dashboard-remote main`→`dashboard-remote toomoya`に更新。`dashboard/`自体の内容は無変更
  (再構成前から一貫してこのプロジェクト専用の内容であり、これがそのまま`toomoya`の内容になる)。

## 既知の残課題

- 「Agent Behavior & Attributes」パネルの`bc`/`pp`分布チャート(`dashboard.html`の
  `attrSpec`/`attrpair`)は、`NODE_ATTRS`からの削除対象にしなかった — データが無ければ
  空のヒストグラムを表示するだけで動作は壊れないが、パネル見出し文言(「bounded confidence
  distribution」等)は論文固有のまま残っている。Tier3と合わせて、または独立の小タスクとして
  後日クリーンアップ候補。
