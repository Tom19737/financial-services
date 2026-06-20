# Financial Services プロジェクト — 包括的コードレビュー報告書 & 改善提案プラン

本ドキュメントは、`financial-services` プロジェクトにおける全9つの Python スクリプト、23個のスキル（`SKILL.md`）、19個のワークフロー、出力データフォルダ、および関連ドキュメントを対象に実施した包括的コードレビューの結果と、それを解消するための段階的な改善提案プランをまとめたものです。

*※2026年6月20日の改修（Issue #16 / PR #18）において、各指摘事項への対応状況（改修完了／未対応など）を追記しました。*

---

## 1. 総合評価サマリー

本プロジェクトは、株式分析ツールとして非常に洗練されたスキル・ワークフローの構成を持っていますが、バックエンドを支える **Python スクリプト層に致命的なバグや設計上の欠陥が多数検出** されました。

| カテゴリ | 検出数 | 影響度 | 改修対応状況 (2026/06/20) |
|---|---|---|---|
| 🔴 **CRITICAL** | 6件 | 本番環境での不具合、データの破壊、他銘柄での実行不能状態 | **全6件 改修完了** |
| 🟠 **HIGH** | 8件 | アーキテクチャの設計不良、著しい DRY 原則違反、OS 依存性 | **全8件 改修完了** |
| 🟡 **MEDIUM** | 12件 | コードの保守性・品質の問題（型ヒント・ログの欠如、マジックナンバー） | **5件改修完了**、残り未対応（今後のフェーズ） |
| 🟢 **LOW** | 5件 | コーディングスタイル、冗長なロジック | 保留（今後のフェーズ） |
| 📄 **ドキュメント・スキル体系不整合** | 8件 | 16スキルにわたるリンク切れ、存在しないファイルへの参照 | **全件 改修完了** |
| 📊 **データ品質・カバレッジの欠落** | 多数 | 7社中3社で財務諸表が欠落、カバレッジの偏り | 未対応（Phase 4 以降で実施予定） |

---

## 2. 🔴 CRITICAL（最優先修正が必要な不具合）

### 【改修完了】 C-1: `generate_3statement.py` — Pretax Income 数式のコピペバグ
* **対象コード:** [generate_3statement.py](file:///d:/Programming/Application/financial-services/scripts/generate_3statement.py#L161)
* **内容:** `FY27E` の Pretax Income（税引前利益）の計算式が `=E13-D14` となっていました。これは `D14`（FY26Eの利息費用）を参照しており、本来あるべき `=E13-E14` からズレていました。
* **影響:** FY27E 以降の税引前利益、純利益、キャッシュフロー、バランスシートのすべてが連鎖的に誤算され、3表連動モデルの整合性が完全に崩壊します。
* **対応内容:** 数式を `=E13-E14` に修正し、整合性を回復しました。

### 【改修完了】 C-2: `generate_pitch.py` — 全データのハードコード（DRY原則の完全な違反）
* **対象コード:** [generate_pitch.py](file:///d:/Programming/Application/financial-services/scripts/generate_pitch.py)
* **内容:** ファイル全体（194行）が「285A.T キオクシア」固有の情報で完全にハードコードされていました。
* **影響:** GEMINI.md の「特定の企業に特化した専用スクリプトを作成せず、引数等でティッカーを受け取って動的にデータをパース・モデル生成する汎用設計」に直接違反しており、他企業に対して一切機能しません。
* **対応内容:** `summary.json` や `annual_income_stmt.csv` などから動的に財務データを読み込んでスライドの各所へバインドし、キオクシア以外の銘柄でもピッチスライドを生成できる汎用設計に書き直しました。

### 【改修完了】 C-3: 複数スクリプトでのティッカーおよびパスのハードコード
* **対象コード:** 
  - [clean_data.py](file:///d:/Programming/Application/financial-services/scripts/clean_data.py#L65-L66)
  - [deck_refresh.py](file:///d:/Programming/Application/financial-services/scripts/deck_refresh.py#L41-L42)
  - [ib_check_deck.py](file:///d:/Programming/Application/financial-services/scripts/ib_check_deck.py#L17-L18)
  - [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L17-L18)
* **内容:** 引数パース（`argparse` など）を一切使用せず、`ticker_str = "285A"` および特定の pptx パスをハードコードしていました。
* **影響:** キオクシア以外の企業データを処理する際、手動でスクリプトを書き換える必要があり、汎用自動化ツールとして機能していません。
* **対応内容:** すべてのスクリプトに `argparse` を導入し、コマンドライン引数からティッカーやアウトプットパスなどを自在に指定可能にしました。

### 【改修完了】 C-4: `model_update.py` — 特定ユーザーの絶対パスのハードコード
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L67)
* **内容:** `subprocess.run` 内で、特定開発者のローカルパスである `C:\Users\fwhrv\.gemini\antigravity\brain\...` がハードコードされていました。
* **影響:** 他の実行環境で実行した際に100%クラッシュします。また、個人情報（ユーザー名等）がコードに露出しており、セキュリティ上のリスクもあります。
* **対応内容:** 絶対パスによる呼び出しを削除し、同じ `scripts/` ディレクトリ配下にある相対パスを `sys.executable` 経由で安全に探索・実行する仕組みに変更しました。

### 【改修完了】 C-5: `model_update.py` — 一次データの破壊的書き換え
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L49-L51)
* **内容:** yfinance から取得した実績データ（`annual_income_stmt.csv`）を直接上書きしていました。
* **影響:** バックアップやバージョニングなしで生データを破壊的に上書きしており、`fetch_yfinance.py` を再実行すると修正した数値が消失する設計上の矛盾が生じています。
* **対応内容:** 上書きする前に、対象の CSV および JSON を `.bak` ファイルとして自動的に退避・バックアップを作成するガードロジックを追加しました。

### 【改修完了】 C-6: 生成スクリプトにおけるキオクシア固有値のフォールバック
* **対象コード:** 
  - [generate_3statement.py](file:///d:/Programming/Application/financial-services/scripts/generate_3statement.py#L27-L39)
  - [generate_lbo.py](file:///d:/Programming/Application/financial-services/scripts/generate_lbo.py#L27-L34)
* **内容:** CSV データが見つからない場合、キオクシアの実績数値がデフォルト値としてハードコードされていました。
* **影響:** 別企業のデータを処理中にエラーが発生した場合にサイレントにキオクシアの数値が使用され、誤った財務モデルが生成されます。
* **対応内容:** デフォルトフォールバックを削除し、必要な CSV/JSON ファイルが読み込めない場合は明示的に `FileNotFoundError` を発生させ、処理を安全に停止（`sys.exit(1)`）するように修正しました。

---

## 3. 🟠 HIGH（設計・アーキテクチャ上の重大な問題）

### 【改修完了】 H-1: `find_ticker_dir()` が8ファイルに重複コピー（DRY違反）
* **内容:** `fetch_yfinance.py` を除くほぼすべてのスクリプトに、全く同一の `find_ticker_dir()` 関数（9行）がコピペされていました。
* **影響:** ディレクトリ構造の変更等が生じた場合、すべてのスクリプトを手動修正する必要があります。
* **対応内容:** [scripts/utils.py](file:///d:/Programming/Application/financial-services/scripts/utils.py) を新設し、この共通探索関数をそちらに一元化しました。

### 【改修完了】 H-2: `get_latest_financial_data()` の重複と不整合
* **内容:** `generate_models.py`（97行）、`generate_3statement.py`（61行）、`generate_lbo.py`（38行）に、それぞれ微妙に異なるデータ読み込み関数がコピペされていました。
* **影響:** 各ファイルで読み込むフィールド名に不整合が発生しやすく、バグ修正や仕様変更が抜け落ちるリスクが極めて高いです。
* **対応内容:** [scripts/utils.py](file:///d:/Programming/Application/financial-services/scripts/utils.py) に、すべての財務指標を安全かつ網羅的に取得する完全な `get_latest_financial_data()` を集約し、各スクリプトからはこれを呼び出すだけに簡素化しました。

### 【改修完了】 H-3: `normalize_ticker()` のインライン実装重複
* **内容:** ティッカーに `.T` を付与する判定処理が、多くのスクリプト内で関数化されずインラインで重複記述されていました。
* **対応内容:** [scripts/utils.py](file:///d:/Programming/Application/financial-services/scripts/utils.py) に共通関数として集約しました。

### 【改修完了】 H-4: Excel スタイル定義の重複
* **内容:** `generate_models.py`、`generate_3statement.py`、`generate_lbo.py` の3ファイルに、同一のフォント、色、罫線などのスタイル定義（各20行程度）がコピペされていました。
* **対応内容:** [scripts/utils.py](file:///d:/Programming/Application/financial-services/scripts/utils.py) 内に `ExcelStyles` クラスを定義し、すべてのモデリングスクリプトからこれをインポートして使い回すことで一元化しました。

### 【改修完了】 H-5: 100倍バグ補正のマジックナンバー
* **対象コード:** [generate_models.py](file:///d:/Programming/Application/financial-services/scripts/generate_models.py#L95-L98)
* **内容:** 株価が 50,000 円を超える場合に 1/100 に補正する処理がありましたが、閾値判定の動作根拠が不明瞭でした。
* **対応内容:** 補正ロジックを [scripts/utils.py](file:///d:/Programming/Application/financial-services/scripts/utils.py) に集約し、補正が適用された際にコンソールおよびログファイルに具体的な数値（補正前RAW株価など）とともに INFO ログを出力して可視化するようにしました。

### 【改修完了】 H-6: `generate_models.py` 内の巨大関数
* **内容:** `create_dcf_model()` や `create_comps_model()` が 200 行近い巨大関数となっていました。
* **対応内容:** 各関数から `find_ticker_dir` などの定義部分や、煩雑な Excel のスタイル初期化部分などを `utils.py` へ分離したことで、関数のスリム化とロジックの整理を実現しました。

### 【改修完了】 H-7: OS 依存の仮想環境 Python パス
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L59)
* **内容:** `os.path.join(".venv", "Scripts", "python")` と Windows のみを前提にしたパス構成になっていました。
* **対応内容:** 現在の仮想環境の Python バイナリを動的に解決する `sys.executable` に完全に統一し、OS依存性を排除しました。

### 【改修完了】 H-8: `model_update.py` — DCF 読み取りが未実装 (`pass` で放置)
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L22-L30)
* **内容:** DCF ファイルをロードしているものの、目標株価などの読み込みが `pass` で放置されていました。
* **対応内容:** `openpyxl` を用いて既存の `dcf_*.xlsx` ファイルの `B47`（目標株価）および `B13`（WACC）の数値を安全にロード・解析し、更新前データとして処理するようロジックを実装しました。

---

## 4. 🟡 MEDIUM（コード品質・保守性の課題）

### 【改修完了】 M-1: `print()` の乱用
* **内容:** すべてのスクリプトで標準の `print()` が使用されており、ログレベルの制御やログファイルへの分離が不可能でした。
* **対応内容:** [scripts/utils.py](file:///d:/Programming/Application/financial-services/scripts/utils.py) に標準ロギング（`setup_logging`）を新設。時間・ログレベルを含む標準フォーマットでのログ出力に変更しました。

### 【未対応】 M-2: 型ヒントの欠如
* **内容:** 全9スクリプト、すべての関数で型ヒント（Type Hints）が記述されていません。
* **対応状況:** 今回のリファクタリングでは見送りました（Phase 6 にて実施予定）。

### 【未対応】 M-3: docstring の欠如
* **内容:** 多くの関数で docstring が欠落しています。
* **対応状況:** 今回のリファクタリングでは見送りました（Phase 6 にて実施予定）。

### 【未対応】 M-4: `fetch_yfinance.py` のインラインインポート
* **内容:** L68で `import re` が関数内で実行されています。
* **対応状況:** `fetch_yfinance.py` は今回のリファクタリング対象から外れており、未対応です。

### 【改修完了】 M-5: `generate_lbo.py` — ウォルラス演算子の誤用
* **対象コード:** [generate_lbo.py](file:///d:/Programming/Application/financial-services/scripts/generate_lbo.py#L212)
* **内容:** `da := eb_val * 0.4` で定義された `da` が以降で参照されていませんでした。
* **対応内容:** 冗長なウォルラス演算子を削除し、`utils.py` から取得した `depreciation`（減価償却費）を LBO 計算に用いるように修正しました。

### 【未対応】 M-6: 数式内での成長率のハードコード
* **対応状況:** 今回の機能等価リファクタリングでは見送りました（前提入力セルへの分離は Phase 1-4 で実施予定）。

### 【未対応】 M-7: COGS 比率のハードコード
* **対応状況:** M-6 と同様に見送りました（Phase 1-4 で実施予定）。

### 【改修完了】 M-8: `ib_check_deck.py` — `df.columns[0]` 仮定による KeyError バグ
* **対象コード:** [ib_check_deck.py](file:///d:/Programming/Application/financial-services/scripts/ib_check_deck.py#L52)
* **内容:** CSV 内に期待される Revenue キーが見つからなかった場合、KeyError でクラッシュする可能性がありました。
* **対応内容:** `Total Revenue`, `Operating Revenue`, `Revenue` などから存在するキーを安全に探索するロジックを実装し、欠損時に KeyError にならないよう例外処理を追加しました。

### 【未対応】 M-9: `¥` 安全処理の冗長性
* **対応状況:** 今回は見送りました。

### 【改修完了】 M-10: `find_ticker_dir` のソート基準の不安定さ
* **内容:** 長さ基準のみのソートでは、部分一致により意図しないフォルダ名が選ばれる可能性がありました。
* **対応内容:** 正規化したティッカーコード文字列の完全一致と部分一致を考慮する安定した探索ロジックに修正しました。

### 【未対応】 M-11: `fetch_yfinance.py` の入力バリデーション
* **対応状況:** `fetch_yfinance.py` の改修は見送られました。

### 【改修完了】 M-12: `generate_models.py` のゼロ除算未保護
* **内容:** EBITDA や Revenue が 0 の場合に `#DIV/0!` エラーが発生していました。
* **対応内容:** Compsの倍率計算を Excel 数式の `=IFERROR(...)` で囲むように修正しました。

---

## 5. 📄 ドキュメント・スキル体系の不整合

### 【改修完了】 5-1: 🔴 日本株オーバーライドのリンク切れ
* **内容:** 3-statement-model, comps-analysis, dcf-model などの **全16個の主要スキル** において、日本株対応セクションの相対リンク先 `../../localization/japan-equity-overrides.md` が存在しませんでした。
* **対応内容:** UTF-8 エンコーディングを崩さずに、正しいパス `../japan-equity-overrides/SKILL.md` に一括置換・修正しました。

### 【改修完了】 5-2: スキル数の不一致
* **内容:** `AGENTS.md` などのドキュメントで「22スキル」と記載されていましたが、実際には「23スキル」存在しました。
* **対応内容:** `AGENTS.md` 等の記載を「23スキル」へ更新しました。

### 【改修完了】 5-3: 存在しないスクリプトへの参照
* **内容:** `fetch_gas_sheets.py` などの存在しないスクリプトの参照がスキル内に残存していました。
* **対応内容:** デッドリファレンスを削除し、yfinance と Web検索のみで動作するようドキュメント表記を整理しました。

---

## 6. 📊 出力データ（`out/`）の監査結果

### 【未対応】 6-1: カバレッジの偏りと財務諸表の欠落
* **内容:** MU, WDC, SK hynix で財務諸表 CSV が欠損しています。
* **対応状況:** `fetch_yfinance` 側の動作や API の制約に依存するため、今回の改修スコープ外とし、Phase 4 でデータ再取得を行う予定です。

---

## 7. テストカバレッジの分析

### 【改修完了】 7-1: 既存テスト（test_scripts.py）のパスの不整合と偽陽性
* **内容:** 成功時と部分データ時で Toyota の保存先パスのアサーションが不整合を起こし、テストが失敗、またはテスト用ディレクトリが残されていました。
* **対応内容:** longName によるフォルダ名生成（`7203.T_Toyota_Motor_Corporation`）および `market_data/` への格納にアサーションパスを適合させ、テスト通過を確認。また、`tearDown()` による一時フォルダのクリーンアップを追加しました。
