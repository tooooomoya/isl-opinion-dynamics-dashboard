# 2026-07-13 ダッシュボード: 同一Wi-Fi外からのアクセス対応(Cloudflare Quick Tunnel)

## 背景

これまでダッシュボード(`dashboard/dashboard.py --serve`)はSSHポートフォワード/同一LAN内での
利用を前提としており、`docs/dashboard.md`(=`dashboard/README.md`)の「既知の限界」に明記の通り
認証レイヤーが無い。今回、同じWi-Fi外(別ネットワーク)からアクセスしたいという要望が出た。

## 検討した選択肢と決定

1. Tailscale等のVPN — 自分のデバイス間だけを繋ぐプライベートメッシュ。認証なしという弱点を
   突かれない最も安全な選択肢だが、専用アプリのインストールが要る。
2. **Cloudflare Tunnel(quick tunnel) — 採用。** `cloudflared tunnel --url http://127.0.0.1:<port>`
   でルーター設定・アカウント登録・ドメイン設定なしに`https://<random>.trycloudflare.com`が
   発行される。サーバー自体は`127.0.0.1`にバインドしたままなので、`--host 0.0.0.0`+ポート開放
   のような「LAN/インターネットに直接ポートを晒す」経路を経由しない。
3. ルーターのポート開放+自前Basic認証実装 — 最もリスクが高く、設定コストも最大のため却下。

**ユーザー判断:** 実験メトリクスのみで機密情報が無いため、認証なしのまま公開URLを踏めば誰でも
見られる状態を許容する(「ほぼ誰も見ないから大丈夫」)。ただしURLはQuick Tunnelのランダム
サブドメインであり推測困難、かつプロセスを止めれば失効・再起動のたびに変わる。

## 変更内容

- `cloudflared`をHomebrewでインストール(`brew install cloudflared`)。
- **`dashboard/serve_public.sh`を新設し、デフォルトの起動方法に格上げ。**
  `dashboard.py --serve`とcloudflared quick tunnelを1コマンドでまとめて起動し、発行された
  公開URLを標準出力に表示、Ctrl-Cで両方停止する。`--port`以外の引数は`dashboard.py`へ
  そのまま渡す(`--seeds`等)。
- `dashboard/README.md`(および同期先の`docs/dashboard.md`)の「起動方法」節を書き換え、
  `serve_public.sh`を一番手に、素の`dashboard.py --serve`(ローカル/SSH限定用途)を
  二番手に配置。「既知の限界」節にも、外部公開時は`--host 0.0.0.0`ではなく
  `serve_public.sh`を使う旨を追記。
- **supersedes**: 「`--serve`が推奨、かつ唯一の起動モード」という従来の案内(2026-07-11時点の
  記述) — 起動モードの推奨順位を書き換えた(GUIフォールバックの位置づけ自体は変更なし)。

## 既知の制約(意図的に残した仕様)

- 認証なし。URLを知る者は誰でも閲覧でき、`POST /api/color-presets`でローカルの
  `color_presets.local.json`を書き換えられる。実験メトリクスのみのため許容と判断。
- Quick TunnelのURLは起動のたびにランダムに変わる(アカウントレス利用の制約)。固定URLが
  必要になった場合は「自分のドメインでの固定URL」方式(Cloudflareアカウント+named tunnel)に
  切り替える必要がある — 今回は不要と判断し見送った。
- Cloudflareの稼働率保証なし(quick tunnelの利用規約上の前提)。

## 検証

- `python3 dashboard/dashboard.py --serve --port 8765`をローカルで起動した状態に対し、
  `cloudflared tunnel --url http://127.0.0.1:8765`を張り、発行されたURLへの
  `curl https://<url>/`(200)、`curl https://<url>/api/summary`(実データのJSONを返却)を確認。
  同一ホスト内でのローカル→公開URL経由の疎通を実データで確認済み。
- `dashboard/serve_public.sh`単体でも同様に起動→URL検出→`curl`での200/JSON確認を実施。
- **バグ発見・修正:** 初版は`set -euo pipefail`下で空配列`"${DASHBOARD_ARGS[@]}"`を展開すると
  bash(macOS付属3.2系)で`unbound variable`になり、dashboard.py起動コマンドの展開自体が
  失敗して即座にcleanupが走る不具合があった。`${DASHBOARD_ARGS[@]+"${DASHBOARD_ARGS[@]}"}`
  (配列が未設定/空でも安全に展開されるbashのイディオム)に修正し、再検証で解消を確認。
- Ctrl-C相当の終了処理: スクリプトプロセスへの`SIGTERM`では両子プロセス(dashboard.py/
  cloudflared)とも正しく終了することを確認。`SIGINT`は非対話シェル(ターミナル制御なしの
  バックグラウンドプロセスとしてテストしたケース)では親スクリプトのtrapがすぐには
  発火しなかった — ただし実運用でターミナルからCtrl-Cを押した場合はフォアグラウンド
  プロセスグループ全体(親スクリプト+dashboard.py+cloudflared)に直接SIGINTが届くため、
  `dashboard.py`側の既存の`except KeyboardInterrupt: pass`(`dashboard/api.py`)もあり
  問題なく止まる想定。実ターミナルでのCtrl-C動作は未検証(このセッションはターミナル制御の
  無い環境のため) — 次に人がターミナルから実行した際に確認されたい。
