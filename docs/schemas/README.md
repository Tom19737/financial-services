# ジャーナル＆取引履歴システム スキーマ定義

このディレクトリには、株式調査ジャーナルおよび取引履歴を蓄積するためのJSON Schema定義ファイルを格納しています。

## ディレクトリ構造

```text
out/_journal/
├── sessions/
│   ├── [Session_ID].md              # セッション要約（frontmatter + 本文）
│   ├── [Session_ID]_decisions.json   # 判断ログ
│   └── ...
├── trades/
│   └── trades.json                  # 取引履歴
└── index.json                       # ジャーナル全体およびセッションのマスターインデックス
```

## スキーマファイル

### 1. [SessionJournal Schema](session_schema.json)
セッション要約のfrontmatterおよび個別判断ログ（decisions）を検証します。
- `session_id`: `YYYY-MM-DDTHH-MM_[TICKER]_[WORKFLOW]` 形式の文字列。
- `decisions`: セッション中に発生した個別の判断ポイント（前提値、シナリオ、手法など）を記述する配列。

### 2. [TradeHistory Schema](trade_schema.json)
取引履歴ファイル（`trades.json`）を検証します。
- `trades`: 取引一覧の配列。
- `session_refs`: その取引の根拠となったセッションのID（`session_id`）の配列。

### 3. [JournalIndex Schema](index_schema.json)
セッション全体のメタデータを一元管理するインデックスファイル（`index.json`）を検証します。
