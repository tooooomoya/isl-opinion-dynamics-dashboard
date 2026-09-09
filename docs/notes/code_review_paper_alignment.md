# コード見直し・論文整合性検証メモ (Paper-Code Alignment Review)

- **対象論文**: `tex/CNA2026/CNA2026-5th.tex` (Complex Networks 2026 原稿)
- **対象コード**: `src/` 配下のシミュレーションモデル (Java)
- **基本方針**:
  1. **論文再現性の担保**: 論文（特に Model / Experimental Setup セクション）に記述されている数式・メカニズム・パラメータが、Java コード上で過不足なく正確に実装・再現されているかを検証する。
  2. **不要コードの削ぎ落とし**: 過去の実験的試行錯誤で追加されたが、最終論文に記載されていない不要な分岐・死滅パラメータ・レガシーロジックを特定し、適宜整理・削除する。
  3. **進行体制**: ユーザー主導でコードを読み進め、適宜 Antigravity に解説要求・数理的妥当性の検証・コード編集・メモ追記を依頼する。

---

## 1. 論文 (CNA2026-5th.tex) に対応する主要モジュール対照表

| 論文内の概念・セクション | 対応する Java ソース | 主な検証ポイント |
| :--- | :--- | :--- |
| **Model: Network Structure** (SBM / Scale-free / DMS) | `src/network/` (`DCSBMNetwork.java`, `DMSNetwork.java` 等) | 論文記載のブロック確率・次数分布が正確か |
| **Model: Agent Opinions & BC** | `src/agent/Agent.java`, `src/dynamics/OpinionDynamics.java` | 意見の初期化、有界信頼区間 ($BC$) の動的更新、FJ 意見更新 |
| **Model: Posting & Vocal Minority** | `src/agent/Agent.java` | 快適度（Comfort rate）の計算、発言閾値 ($p_u$)、Bin 依存投稿率 |
| **Model: Feed Delivery & Algorithmic Amplification** | `src/admin/AdminOptim.java`, `src/dynamics/OpinionDynamics.java` | Chronological / Top-$K$ 配信、リポストの露出・伝播 |
| **Model: Sanction / Unfollow** | `src/agent/Agent.java` | アンフォロー / ブロックのトリガー条件と対象の妥当性 |
| **Intervention / Hub Manipulation** | `src/experiment/InterventionSetup.java`, `src/dynamics/OpinionDynamics.java` | 媒介ハブ介入（M-silent, M-extreme 等）の実装 |
| **Metrics & Evaluation** | `src/analysis/Analysis.java` | 分極度指標、サイン付きモジュラリティ ($Q_{sign}$)、Bin別投稿比率 |

---

### 2026-09-07: `OpinionDynamics.java` ダイナミクス前介入コードの整理・論文整合化
- **対象箇所**: `OpinionDynamics.java` (L174-L212, L206-L210, L408-L412)
- **判定と措置**:
  - **削除**: `muteAccessIds`, `muteRepostIds`, `removeHubIds` の処理を削除。
    - *根拠*: 論文（`sec:model-intervention`）では「フォロイー関係や閲覧は維持したまま発言のみを遮断する（silence）」と明記されており、アクセス確率を0にする（休眠化）やエッジを強制切断する介入は論文の実験設計から完全に外れているため。
  - **一本化**: `pinNeutralIds` を `pinOpinionIds` に統合。
    - *根拠*: 0.0 固定のみを扱う旧実装であり、任意意見に固定できる `pinOpinionIds` で完全に包含されているため。
  - **残存・正常化**:
    - `pinOpinionIds`: 論文の 60 ハブ意見固定（Extreme $\pm 1.0$, Moderate $\pm 0.4$, Neutral $0.0$）の実装として保持。
    - `silentUntilIds`: 論文の N-silent 条件（中立ハブ20人の発言遮断）の実装として保持。
- **検証**: Java コンパイル通過確認済み。


