# Financial Services プロジェクト — 包括的コードレビュー報告書 & 改善提案プラン

本ドキュメントは、`financial-services` プロジェクトにおける全9つの Python スクリプト、23個のスキル（`SKILL.md`）、19個のワークフロー、出力データフォルダ、および関連ドキュメントを対象に実施した包括的コードレビューの結果と、それを解消するための段階的な改善提案プランをまとめたものです。

---

## 1. 総合評価サマリー

本プロジェクトは、株式分析ツールとして非常に洗練されたスキル・ワークフローの構成を持っていますが、バックエンドを支える **Python スクリプト層に致命的なバグや設計上の欠陥が多数検出** されました。

| カテゴリ | 検出数 | 影響度 |
|---|---|---|
| 🔴 **CRITICAL** | 6件 | 本番環境での不具合、データの破壊、他銘柄での実行不能状態 |
| 🟠 **HIGH** | 8件 | アーキテクチャの設計不良、著しい DRY 原則違反、OS 依存性 |
| 🟡 **MEDIUM** | 12件 | コードの保守性・品質の問題（型ヒント・ログの欠如、マジックナンバー） |
| 🟢 **LOW** | 5件 | コーディングスタイル、冗長なロジック |
| 📄 **ドキュメント・スキル体系不整合** | 8件 | 16スキルにわたるリンク切れ、存在しないファイルへの参照 |
| 📊 **データ品質・カバレッジの欠落** | 多数 | 7社中3社で財務諸表が欠落、カバレッジの偏り |

---

## 2. 🔴 CRITICAL（最優先修正が必要な不具合）

### C-1: `generate_3statement.py` — Pretax Income 数式のコピペバグ
* **対象コード:** [generate_3statement.py](file:///d:/Programming/Application/financial-services/scripts/generate_3statement.py#L161)
* **内容:** `FY27E` の Pretax Income（税引前利益）の計算式が `=E13-D14` となっています。これは `D14`（FY26Eの利息費用）を参照しており、本来あるべき `=E13-E14` からズレています。
* **影響:** FY27E 以降の税引前利益、純利益、キャッシュフロー、バランスシートのすべてが連鎖的に誤算され、3表連動モデルの整合性が完全に崩壊します。

### C-2: `generate_pitch.py` — 全データのハードコード（DRY原則の完全な違反）
* **対象コード:** [generate_pitch.py](file:///d:/Programming/Application/financial-services/scripts/generate_pitch.py)
* **内容:** ファイル全体（194行）が「285A.T キオクシア」固有の情報で完全にハードコードされています。
* **影響:** GEMINI.md の「特定の企業に特化した専用スクリプトを作成せず、引数等でティッカーを受け取って動的にデータをパース・モデル生成する汎用設計」に直接違反しており、他企業に対して一切機能しません。

### C-3: 複数スクリプトでのティッカーおよびパスのハードコード
* **対象コード:** 
  - [clean_data.py](file:///d:/Programming/Application/financial-services/scripts/clean_data.py#L65-L66)
  - [deck_refresh.py](file:///d:/Programming/Application/financial-services/scripts/deck_refresh.py#L41-L42)
  - [ib_check_deck.py](file:///d:/Programming/Application/financial-services/scripts/ib_check_deck.py#L17-L18)
  - [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L17-L18)
* **内容:** 引数パース（`argparse` など）を一切使用せず、`ticker_str = "285A"` および特定の pptx パスをハードコードしています。
* **影響:** キオクシア以外の企業データを処理する際、手動でスクリプトを書き換える必要があり、汎用自動化ツールとして機能していません。

### C-4: `model_update.py` — 特定ユーザーの絶対パスのハードコード
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L67)
* **内容:** `subprocess.run` 内で、特定開発者のローカルパスである `C:\Users\fwhrv\.gemini\antigravity\brain\...` がハードコードされています。
* **影響:** 他の実行環境で実行した際に100%クラッシュします。また、個人情報（ユーザー名等）がコードに露出しており、セキュリティ上のリスクもあります。

### C-5: `model_update.py` — 一次データの破壊的書き換え
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L49-L51)
* **内容:** yfinance から取得した実績データ（`annual_income_stmt.csv`）を直接上書きしています。
* **影響:** バックアップやバージョニングなしで生データを破壊的に上書きしており、`fetch_yfinance.py` を再実行すると修正した数値が消失する設計上の矛盾が生じています。

### C-6: 生成スクリプトにおけるキオクシア固有値のフォールバック
* **対象コード:** 
  - [generate_3statement.py](file:///d:/Programming/Application/financial-services/scripts/generate_3statement.py#L27-L39)
  - [generate_lbo.py](file:///d:/Programming/Application/financial-services/scripts/generate_lbo.py#L27-L34)
* **内容:** CSV データが見つからない場合、キオクシアの実績数値がデフォルト値としてハードコードされています。
* **影響:** 別企業のデータを処理中にエラーが発生した場合にサイレントにキオクシアの数値が使用され、誤った財務モデルが生成されます。

---

## 3. 🟠 HIGH（設計・アーキテクチャ上の重大な問題）

### H-1: `find_ticker_dir()` が8ファイルに重複コピー（DRY違反）
* **内容:** `fetch_yfinance.py` を除くほぼすべてのスクリプトに、全く同一の `find_ticker_dir()` 関数（9行）がコピペされています。
* **影響:** ディレクトリ構造の変更等が生じた場合、すべてのスクリプトを手動修正する必要があります。共通の `utils.py` に集約すべきです。

### H-2: `get_latest_financial_data()` の重複と不整合
* **内容:** `generate_models.py`（97行）、`generate_3statement.py`（61行）、`generate_lbo.py`（38行）に、それぞれ微妙に異なるデータ読み込み関数がコピペされています。
* **影響:** 各ファイルで読み込むフィールド名に不整合が発生しやすく、バグ修正や仕様変更が抜け落ちるリスクが極めて高いです。

### H-3: `normalize_ticker()` のインライン実装重複
* **内容:** ティッカーに `.T` を付与する以下の判定処理が、多くのスクリプト内で関数化されずインラインで重複記述されています。
  ```python
  if len(ticker_str) == 4 and ticker_str[0].isdigit() and ticker_str.isalnum():
      ticker_str = f"{ticker_str}.T"
  ```

### H-4: Excel スタイル定義の重複
* **内容:** `generate_models.py`、`generate_3statement.py`、`generate_lbo.py` の3ファイルに、同一のフォント、色、罫線などのスタイル定義（各20行程度）がコピペされています。共通のスタイルモジュールに抽出されるべきです。

### H-5: 100倍バグ補正のマジックナンバー
* **対象コード:** [generate_models.py](file:///d:/Programming/Application/financial-services/scripts/generate_models.py#L95-L98)
* **内容:** 株価が 50,000 円を超える場合に 1/100 に補正する処理（および `generate_3statement.py` L50-51, `generate_lbo.py` L45-46）がありますが、閾値 `50000` の設定根拠が不明であり、株価の高い実在する銘柄（ファーストリテイリング等）で誤作動するリスクがあります。

### H-6: `generate_models.py` 内の巨大関数
* **内容:** `create_dcf_model()` が 206 行（L347-552）、`create_comps_model()` が 180 行（L159-345）の巨大関数となっており、グローバルルール「関数は50行未満」に著しく違反しています。

### H-7: OS 依存の仮想環境 Python パス
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L59)
* **内容:** `os.path.join(".venv", "Scripts", "python")` と Windows のみを前提にしたパス構成になっています（Linux/macOS では `bin/python`）。`sys.executable` に統一すべきです。

### H-8: `model_update.py` — DCF 読み取りが未実装 (`pass` で放置)
* **対象コード:** [model_update.py](file:///d:/Programming/Application/financial-services/scripts/model_update.py#L22-L30)
* **内容:** `openpyxl` を用いて DCF ファイルをロードしているものの、`pass` のまま放置されており、既存のターゲットプライスなどの読み込みが機能していません。

---

## 4. 🟡 MEDIUM（コード品質・保守性の課題）

1. **`print()` の乱用:** すべてのスクリプトで標準の `print()` が使用されており、`logging` モジュールによるログレベルの制御やログファイルへの分離が不可能です。
2. **型ヒントの欠如:** 全9スクリプト、すべての関数で型ヒント（Type Hints）が一切記述されていません。
3. **docstring の欠如:** `generate_models.py` の一部を除くほぼすべての関数で、引数や戻り値、処理内容を説明する docstring が欠落しています。
4. **数式内での成長率のハードコード:** `generate_models.py` L457 にて `1.08`, `1.06` などの将来の売上成長率が Excel の数式文字列として直接埋め込まれています。これらは入力前提セルから参照されるべきです。
5. **COGS 比率のハードコード:** `generate_3statement.py` L154 にて、売上原価率（`0.65`, `0.64` 等）が数式内にハードコードされています。
6. **ゼロ除算未保護:** `generate_models.py` L262-272 にて、EBITDA や Revenue が 0 の場合に `#DIV/0!` が発生します。Excel の `IFERROR` 関数で囲むべきです。

---

## 5. 📄 ドキュメント・スキル体系の不整合

### 5-1. 🔴 日本株オーバーライド（japan-equity-overrides）のリンク切れ
* **内容:** 3-statement-model, comps-analysis, dcf-model などの **全16個の主要スキル** において、日本株対応セクションで指定されている参照リンクが `[../../localization/japan-equity-overrides.md]` となっていますが、このディレクトリおよびファイルは存在しません。
* **正しいパス:** `[../japan-equity-overrides/SKILL.md]`

### 5-2. スキル数の不一致
* **内容:** `AGENTS.md` や `ANTIGRAVITY_MIGRATION.md` には「22スキル」と記載されていますが、実際のディレクトリには「23スキル」存在します。

### 5-3. 存在しないスクリプトへの参照
* **内容:** `dcf-model` や `comps-analysis` スキルの内部で、第二データソースとして `fetch_gas_sheets.py` が指定されていますが、`scripts/` に該当ファイルはありません。また、`recalc.py` への言及もデッドコピーです。

---

## 6. 📊 出力データ（`out/`）の監査結果

全7社の出力データを検証した結果、カバレッジと整合性に深刻な問題が確認されました。

### 構成規約の適合状況
* **ティッカー名フォルダ:** `out/285A.T_Kioxia_Holdings` 等、GEMINI.md で定義された `[Ticker]_[Company_English]` 命名規則には完全に従っています。

### データ欠落の深刻さ

| 企業名 | 財務諸表 CSV | analysis/ 成果物 | 状況評価 |
|---|---|---|---|
| **285A.T_Kioxia_Holdings** | ✅ 完備 | ✅ 17ファイル完備 | ★★★ 完全 |
| **7203.T_Toyota_Motor** | ✅ 完備 | ⚠️ comps / dcf のみ | ★★☆ 中程度 |
| **7201.T_Nissan_Motor** | ⚠️ annual のみ | ❌ なし | ★☆☆ 部分的 |
| **7267.T_Honda_Motor** | ✅ 完備 | ❌ なし | ★☆☆ 部分的 |
| **MU (Micron)** | ❌ **一切なし** | ❌ なし | ☆☆☆ prices / summary のみ |
| **000660.KS (SK hynix)** | ❌ **一切なし** | ❌ なし | ☆☆☆ prices / summary のみ |
| **WDC (Western Digital)** | ❌ **一切なし** | ❌ なし | ☆☆☆ prices / summary のみ |

### データ品質の課題
1. **タイムゾーン不統一:** `prices.csv` の日付フォーマットにおいて、日本株（`2025-06-19`）と米国・韓国株（タイムゾーン付き表記 `2025-06-20 00:00:00-04:00`）が混在しており、データ読み込み時にエラーの原因となります。
2. **四半期データの過度な疎化:** キオクシア（285A.T）および日産（7201.T）の `quarterly_income_stmt.csv` が EPS と株式数の 4 行しか存在せず、Revenue や Operating Income などの主要科目が完全に空です。

---

## 7. テストカバレッジの分析

### テスト対象の偏り
* テストスクリプトは [test_scripts.py](file:///d:/Programming/Application/financial-services/tests/test_scripts.py) の 1 ファイルのみ。
* テストされているのは `fetch_yfinance.py` のみであり、残りの **8つの Python スクリプトは全くテストされていません（未テスト率 88.8%）**。

### 既存テストの不備
1. **偽陽性の疑い:** テスト内で出力先の検証パスを `./out/test_market_data/7203.T/...` のように指定していますが、実際の `fetch_yfinance.py` は `longName` を取得して `7203.T_Toyota_Motor_Corporation` のようにフォルダを作成するため、本来はパスが一致しないはずです。テスト環境での mock 動作に起因する偽陽性の可能性があります。
2. **クリーンアップ処理の欠落:** テスト実行後に `./out/test_market_data` などの一時ディレクトリが削除されずに残ります。

---

## 8. 改善提案プラン（段階的リファクタリングロードマップ）

### Phase 0 — 致命的バグの即時修正
* **概要:** 財務計算結果に直接影響するバグの修正。
* **項目:**
  - `generate_3statement.py` の FY27E Pretax Income 計算式の `=E13-D14` → `=E13-E14` への修正。
  - `model_update.py` における絶対パス `C:\Users\fwhrv\...` の除去、相対パスまたは動的な環境パス取得への移行。
  - `model_update.py` における実績 CSV データの破壊的上書きを防止（バックアップを取る、または一時ファイル経由にする）。

### Phase 1 — アーキテクチャ改善（スクリプト層のリファクタリング）
* **概要:** DRY 原則の適用、保守性の向上、および他企業に対応させるための汎用化。
* **項目:**
  - **`utils.py` の新設:** 各スクリプトで重複している `find_ticker_dir()`, `normalize_ticker()`, `get_latest_financial_data()` およびスタイル定義を一元管理。
  - **引数引渡し機能（`argparse`）の導入:** `clean_data.py`, `deck_refresh.py`, `ib_check_deck.py`, `model_update.py` に `argparse` を実装し、コマンドラインから任意のティッカーやファイルパスを指定可能にする。
  - **`generate_pitch.py` の汎用化:** ハードコードされているキオクシア固有データを取り出し、JSON/CSV または summary.json から動的にデータを読み込む設計へ再構築。
  - **巨大関数の分割:** `create_dcf_model()` や `create_comps_model()` を 50 行以内の処理ブロック（仮定作成、予測作成、バリュエーションブリッジ等）へ分割。

### Phase 2 — テスト基盤の構築
* **概要:** リファクタリングによる予期せぬ動作変更（デグレード）を防ぐためのテストの追加。
* **項目:**
  - **`tests/test_utils.py` の作成:** `normalize_ticker()`, `find_ticker_dir()`, `get_latest_financial_data()` の単体テスト。
  - **財務モデル生成テスト:** DCF, Comps, 3-Statement, LBO の生成 xlsx 内の主要数式が Google Sheets 互換で正しく埋め込まれているかを自動検査する仕組み。
  - **テスト環境の改善:** テスト後に残される一時ディレクトリを `tearDown()` で確実に削除する処理の追加。

### Phase 3 — ドキュメント・スキル体系の整理
* **概要:** 壊れた参照パスの修正と、ドキュメントの最新化。
* **項目:**
  - **日本株オーバーライドのリンクパス修復:** 全 16 スキル内に埋め込まれた `../../localization/japan-equity-overrides.md` の参照先を `../japan-equity-overrides/SKILL.md` に一括修正。
  - **`AGENTS.md` の整理:** 古い `tools/` への参照を `.agents/` に書き換え、前半と後半で重複しているルールを統合。
  - **存在しない参照の削除:** `fetch_gas_sheets.py` などの存在しないスクリプトの参照を削除。

### Phase 4 — データパイプラインの強化
* **概要:** データの鮮度・一貫性・網羅性の向上。
* **項目:**
  - **米国株・韓国株の財務諸表データの再取得:** `prices.csv` と `summary.json` しか存在しない MU, WDC, SK hynix につき、`fetch_yfinance.py` を正常実行してデータを補完。
  - **日付フォーマットの正規化:** 各社の `prices.csv` の日付を ISO 8601 形式（タイムゾーンなしの `YYYY-MM-DD`）に統一。
  - **`quarterly` データの疎密問題の調査:** 日本株で売上高や営業利益などの主要四半期財務科目が欠落する yfinance の制限に対し、必要に応じてスクリーニングを補強。

### Phase 5 — 新機能追加提案
* **概要:** 株式分析ツールとしてのカバレッジ領域の拡張。
* **項目:**
  - **M&A / Merger Model スキルの新設:** 合併後の EPS（Accretion/Dilution）試算、日本の TOB スキーム対応。
  - **Sum-of-the-Parts (SOTP) バリュエーションスキルの追加:** 日本のコングロマリット企業分析に不可欠なセグメント別評価およびディカウントの反映。
  - **チャート自動生成ツール:** matplotlib/plotly を用いた、分析レポート用標準チャートの自動出力ガイド。
  - **データバリデーター (`validate_data.py`):** 取得された CSV や JSON の網羅性をチェックする検証スクリプトの新設。

### Phase 6 — コード品質の底上げ
* **概要:** Python スタイルの改善と静的解析の準備。
* **項目:**
  - **型ヒントの追加:** 全9スクリプトの全関数に対して型アノテーションを記述。
  - **`logging` への移行:** 全ての `print()` を標準 `logging` モジュール（ログレベル指定可能）に統一。
  - **ゼロ除算保護:** 類似企業倍率計算部への `IFERROR` ラップ数式の実装。

---

## 9. 実行優先度と推奨スケジュール

各タスクの優先度および依存関係を考慮した実装プラン。

| 順序 | 対象タスク | 見積工数 | 依存関係 |
|---|---|---|---|
| **1st** | Phase 0（🔴 致命的バグの修正） | 1 - 2時間 | なし |
| **2nd** | Phase 1-1, 1-2（共通 utils 抽出 ＋ argparse 導入） | 4 - 6時間 | Phase 0 |
| **3rd** | Phase 3（📄 ドキュメント・リンクの修復） | 2 - 3時間 | なし |
| **4th** | Phase 4-1（📊 財務諸表データの再取得） | 1時間 | なし |
| **5th** | Phase 2（🧪 テスト基盤の構築・カバレッジ80%） | 4 - 6時間 | Phase 1 |
| **6th** | Phase 1-3, 1-4（関数分割・マジックナンバー排除） | 3 - 4時間 | Phase 1-1 |
| **7th** | Phase 6（💻 型ヒント、logging 移行など品質向上） | 4 - 6時間 | Phase 1 |

---

## 10. 検証計画

### 10-1. 自動テストの実行
リファクタリング適用後は、以下のコマンドでテストを実行し、1件もエラーが出ないことを検証します。
```bash
cd d:\Programming\Application\financial-services
python -m pytest tests/ -v
```

### 10-2. 手動検証
- **Phase 0 完了時:** `generate_3statement.py` にて出力された Excel シートを開き、FY27E 以降の税引前利益計算が前年の利息ではなく、当年の利息費用を参照していることを数式（例: `=E13-E14`）で目視確認します。
- **Phase 1 完了時:** コマンドラインから `--ticker 7203.T` を指定して `generate_models.py` などのスクリプトを実行し、キオクシア以外のトヨタ（7203.T）のデータがエラーなく処理され、`out/7203.T_Toyota_Motor_Corporation/analysis/` にモデルが出力されるかを確認します。

---

## 11. Open Questions（ユーザー承認・決定が必要な項目）

> [!IMPORTANT]
> 以下の事項について、実装を進める前に方針の合意が必要です。
>
> 1. **`generate_pitch.py` の扱い方針:** 完全書き直しを行うか、あるいは廃止するか。現在キオクシア専用となっているため、汎用化コストが非常に高いです。`pptx-author` スキルが自動でスライドを作成する仕様になっているため、スクリプト単体としての存在意義は低い可能性があります。
> 2. **`xlsxwriter` パッケージの扱い:** `requirements.txt` に含まれていますが、本プロジェクトは `openpyxl` に統一方針を掲げています。他に `xlsxwriter` を前提としたコードがない場合は削除しても問題ないか。
> 3. **100倍バグ補正の正しいアプローチ:** yfinance が日本株で稀に不正な金額（単位が100倍ズレるなど）を返す問題に対し、現在のような株価の絶対値（`> 50000`）による補正（閾値判定）を継続するか、より高度な判定ロジックを導入するか。
> 4. **新機能（Phase 5）の優先度:** M&A/Merger Model スキルと SOTP（セグメント評価）スキルのどちらを優先して拡充すべきか。
> 5. **Comps/DCF ワークフローの重複整理:** 現在 `comps.md` (109行) などのワークフロー記述が、対応するスキル本体 (`SKILL.md`) と大きく重複しています。ワークフロー側を薄いラッパーに統合し、メンテナンス性を高めるアプローチで進めてよいか。
