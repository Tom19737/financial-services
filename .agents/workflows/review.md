# ワークフロー: /review

蓄積されたジャーナルデータ（セッション要約・判断ログ）と取引履歴を読み込み、分析履歴の振り返り、実現損益の集計、または月次レポートの自動生成を行います。

## オプション引数
以下のようなワンライナーでの入力が可能です：
- 銘柄別履歴表示: `/review --ticker [TICKER]` (例: `/review --ticker 285A.T`)
- 損益サマリー表示: `/review pnl [--ticker TICKER] [--start YYYY-MM-DD] [--end YYYY-MM-DD]`
- 月次レポート生成: `/review report --month YYYY-MM` (例: `/review report --month 2026-06`)
- 判断検証表示: `/review verify`
- 前提検証表示: `/review assumptions`
- バイアス検出表示: `/review biases`

引数がない場合は対話式（ヒアリングモード）で実行します。

## 実行手順

1. **クエリタイプの判定 / ヒアリング**
   - **引数が指定されている場合**:
     - 指定された引数（`--ticker`, `pnl`, `report`, `verify`, `assumptions`, `biases` など）を抽出して、対応する実行コマンドを判定します。
   - **対話式の場合**:
     - ユーザーに実行したい内容を問いかけます：
       1. 銘柄別の分析履歴表示
       2. ポジションと損益サマリーの表示
       3. 月次振り返りレポートの生成
       4. 意思決定の判断検証（的中率・株価変化率分析）の表示
       5. 投資前提（WACC・成長率等）の推移と実績乖離分析の表示
       6. 投資行動・意思決定のバイアス検出（塩漬け・楽観バイアス等）の表示
       必要なパラメータがある場合は追加でヒアリングします。

2. **レビュー処理の実行**
   判定したクエリタイプに基づき、以下のいずれかのコマンドを実行します。

   - **A. 銘柄別履歴表示**:
     ```powershell
     .venv\Scripts\python scripts/journal_review.py history --ticker [TICKER]
     ```
   - **B. 損益サマリー表示**:
     ```powershell
     .venv\Scripts\python scripts/journal_review.py pnl [--ticker TICKER] [--start START] [--end END]
     ```
     ※ `--ticker`, `--start`, `--end` は省略可能です。
   - **C. 月次振り返りレポート生成**:
     ```powershell
     .venv\Scripts\python scripts/journal_review.py report --month [MONTH]
     ```
   - **D. 判断検証表示**:
     ```powershell
     .venv\Scripts\python scripts/journal_review.py verify
     ```
   - **E. 前提検証表示**:
     ```powershell
     .venv\Scripts\python scripts/journal_review.py assumptions
     ```
   - **F. バイアス検出表示**:
     ```powershell
     .venv\Scripts\python scripts/journal_review.py biases
     ```

3. **実行結果 of提示とフォローアップ**
   - **銘柄別履歴表示 / 損益サマリー表示 / 判断検証表示 / 前提検証表示 / バイアス検出表示の場合**:
     - コマンドの出力結果をマークダウン等の読みやすいフォーマットに整理し、会話内に提示します。
     - 判断検証表示の場合、的中（Success）と外れ（Failed）の傾向、特に信頼度（Confidence）の高さと的中率の整合性について着目し、分析の精度や反省点をユーザーと振り返ります。
     - 前提検証表示の場合、過去の前提値の時系列推移を振り返り、さらに最新の決算実績等から算出された「売上成長率」や「EBITDAマージン」の実績値と前提値の「乖離」を確認します。前提設定に楽観バイアスや悲観バイアスがなかったか振り返りを促します。
     - バイアス検出表示の場合、買い/売り判断の比率（楽観バイアス）、利確と損切りの平均保有期間（塩漬けバイアス/プロスペクト理論）、現在のポートフォリオのセクター偏り（分散不足）を可視化し、客観的な数値に基づいて自己反省の材料とします。
     - 必要に応じて、特定の意思決定がその後の取引結果（実現損益）にどう影響したか、相関の分析や議論をユーザーに提案します。
   - **月次振り返りレポート生成の場合**:
     - 生成されたレポートファイル（例: `out/_journal/reports/monthly_2026-06.md`）へのリンクを提示し、作成が成功した旨を報告します。
     - レポート内の「自己反省と今後の課題（要編集）」セクションについて、ユーザーが追記すべき項目（分析の精度、取引と意思決定の整合性、次月のアクション）を示し、必要であれば下書き作成の壁打ちやドラフト作成のサポートを提案します。
