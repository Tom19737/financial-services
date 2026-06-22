---
name: journal-save
description: Save research/discussion session data, decisions, and summaries using scripts/journal_save.py.
---

# journal-save スキル

現在の会話コンテキストからセッション要約と判断ログを抽出し、`scripts/journal_save.py` を呼び出して永続化します。

## 手順

1. **基本情報の抽出**
   - 現在の日本時間（JST）の日付（`YYYY-MM-DD`）を取得します。
   - 対象となっている銘柄（ティッカー、企業名）を会話から抽出します。
   - 実行したワークフロー名（`dcf`, `comps`, `initiate`, `earnings`など、無ければ `freeform`）を決定します。
   - セッション中に生成・参照された成果物のパス（例: `out/285A.T_KIOXIA_HOLDINGS_CORPORATION/analysis/dcf_285A.T.xlsx` など）を `artifacts` 配列に抽出します。

2. **現在株価（price_at_session）の取得**
   - ティッカーが存在する場合、`python scripts/fetch_yfinance.py` があればそれを利用するか、無ければ議論時の株価を `price_at_session` に設定します。取得できない場合は `null` にします。

3. **セッション要約（Markdown）の生成**
   - 以下の構成でマークダウン本文（`summary_markdown`）を記述します。
     - `# セッション要約: [Session_ID]`
     - `## 目的`（このセッションで達成しようとしたこと）
     - `## 結論・主要アウトプット`（算出された株価レンジ、投資判断の方向性など）
     - `## 主要な前提と根拠`（採用したWACC、成長率、マージンなどの前提と根拠）
     - `## 未解決事項・次のアクション`（残った疑問、追加で必要な調査など）

4. **個別判断（decisions）の抽出**
   - 会話中に発生した個別の判断（前提の設定、シナリオの選択、手法の選択、最終判断、リスク評価など）を抽出し、以下のスキーマに従って配列を作成します。
     - `id`: `d001`, `d002` ... 形式のユニークID。
     - `category`: `assumption` / `scenario` / `methodology` / `conclusion` / `risk` のいずれか。
     - `topic`: 判断のトピック（例: `WACC設定`, `成長率シナリオ`）。
     - `question`: 問い（例: `WACCを何%に設定するか`）。
     - `chosen`: 選択された値や結論。
     - `alternatives`: 却下された他の選択肢（配列。各要素は `value` と `reason_rejected` を含む）。
     - `rationale`: 選択した根拠。
     - `source`: 情報源やデータソース。
     - `confidence`: 自信度（`high` / `medium` / `low`）。
     - `impact`: 結論への影響度（`high` / `medium` / `low`）。

5. **JSON データの組み立て**
   - スキーマ `docs/schemas/session_schema.json` に準拠するJSONデータを組み立てます。
   - `session_id` は `YYYY-MM-DDTHH-MM_[TICKER]_[WORKFLOW]` 形式（例: `2026-06-22T17-00_285A.T_dcf`）。
   - `trigger` は自動呼び出しなら `auto`、手動（ユーザー指示による`/save-session`）なら `manual`。

6. **永続化スクリプトの実行**
   - 組み立てた JSON データを一時ファイル（例: `out/_journal/sessions/tmp_save.json`）に書き込みます。
   - 以下のコマンドを実行して永続化します。
     ```powershell
     .venv\Scripts\python scripts/journal_save.py --data-file out/_journal/sessions/tmp_save.json
     ```
   - 実行後、作成した一時ファイルを削除します。
     ```powershell
     Remove-Item out/_journal/sessions/tmp_save.json
     ```
