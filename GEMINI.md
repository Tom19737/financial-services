# GEMINI.md - プロジェクト開発ルール & ガイドライン

本プロジェクト（financial-services）で作業する際、すべてのエージェントが常時遵守しなければならない絶対的なルールおよび設計規約です。

---

## 1. ディレクトリ構成ルール

出力フォルダ（`out/`）は、最上位で用途別に分割した上で、配下にティッカーごとのサブフォルダを作成して整理します。**ティッカーごとのフォルダを `out/` 直下に直接配置してはなりません。**

```text
out/
├── [Ticker]_[Company_English]/      # 例：285A.T_Kioxia_Holdings, 7203.T_Toyota_Motor, MU_Micron_Technology 等の企業別フォルダ
│   ├── market_data/                 # マーケットデータ（yfinanceから取得した一次情報）
│   │   ├── prices.csv               # 日次株価データ
│   │   ├── summary.json             # 企業基本情報
│   │   ├── annual_income_stmt.csv   # 損益計算書 (年次)
│   │   └── ...                      # その他財務諸表CSV
│   │
│   └── analysis/                    # 分析成果物（モデリング結果、アナリストレポート）
│       ├── comps_[Ticker].xlsx      # 類似企業比較（Comps）スプレッドシート
│       ├── dcf_[Ticker].xlsx        # DCFバリュエーションスプレッドシート
│       ├── [Company]_Initiation_Report_[Date].md  # カバレッジ開始レポート
│       └── [Company]_Earnings_Update_[Date].md    # 決算アップデートレポート
```

---

## 2. 実装・開発規約

* **DRY原則（Don't Repeat Yourself）の徹底**:
  - 特定の企業（キオクシア等）に特化した専用スクリプトを作成せず、引数等でティッカーを受け取って動的にデータをパース・モデル生成する汎用設計（例: `generate_models.py`）を維持します。
* **データ読み込みルール**:
  - 分析やモデル構築を行う際は、必ず `out/market_data/[Ticker]/` 配下に格納されたCSV/JSONファイルを一次情報として動的に読み込んで使用します。
* **Gitワークフロー**:
  - 変更はローカルでのコミットに留め、**ユーザーから明確な指示があるまで `git push` は絶対に行いません**。
  - イシュー番号（例：#14）に対応したトピックブランチ（例：`fix/alphanumeric-tickers`）で作業を行います。

---

## 3. テクノロジースタック

* **言語 & ライブラリ**: Python 3 (openpyxl, pandas, yfinance)
* **スプレッドシート形式**: 常に Google スプレッドシートへインポート可能な互換性のある標準数式のみで構成された `.xlsx` ファイルを `openpyxl` を用いて headless 出力します。
* **反復計算の有効化**: 3表連動などの循環参照を解決するため、openpyxlでの出力時は必ず `CalcProperties(iterate=True)` を設定します。
