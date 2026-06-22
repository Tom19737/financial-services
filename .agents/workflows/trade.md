# ワークフロー: /trade

取引履歴（買付・売却）の登録を行います。

## オプション引数
`/trade [buy/sell] [TICKER] [QTY] [PRICE] --thesis "投資仮説"` のようにワンライナーでの入力が可能です。
引数がない場合は対話式（ヒアリングモード）で実行します。

## 実行手順

1. **引数解析 / ヒアリング**
   - **ワンライナーの場合**: 
     - 指定された引数（side, ticker, quantity, price）を抽出します。
     - `--thesis` があればそれを `thesis_snapshot` に設定します。無ければ現在の会話履歴から直近の投資理由を自動要約して `thesis_snapshot` を作成します。
     - `company` 名は、既存の `out/[Ticker]/summary.json` や会話履歴から自動判別します。判別できない場合は、ユーザーに一度質問するか、yfinanceから取得します。
   - **対話式の場合**:
     - ユーザーに対して、以下の情報を順次（または一括で）ヒアリングします。
       - 売買区分（買い or 売り）
       - ティッカー（例: `285A.T`）
       - 企業名
       - 数量（株数）
       - 単価（株価）
       - 取引日（デフォルトは本日）
       - 投資仮説（当取引のエントリー理由やメモ）
       - 手数料（任意）
       - 関連セッションID（自動で直近のセッションIDを提案、もしくはユーザー指定）

2. **取引の登録実行**
   - 抽出・ヒアリングしたパラメータを元に、以下のコマンドを実行します。
     ```powershell
     .venv\Scripts\python scripts/trade_manager.py add --side [SIDE] --ticker [TICKER] --company "[COMPANY]" --quantity [QTY] --price [PRICE] --date [DATE] --currency [CURRENCY] --fees [FEES] --session-refs "[SESSION_ID]" --thesis-snapshot "[THESIS]" --notes "[NOTES]"
     ```

3. **実行結果の表示**
   - 登録に成功した場合、以下を出力します。
     - 生成された取引ID（`trade_id`）
     - 今回の取引の概要
     - 更新後の保有ポジション状況（数量、平均取得単価）
