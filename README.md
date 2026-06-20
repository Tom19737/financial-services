# Stock Research (for Antigravity)

本プロジェクトは、Antigravity（Gemini）専用に適合化された、株式調査（エクイティリサーチ）および財務モデリングの統合ツールセットです。
決算分析・カバレッジ開始・モデル更新・セクター調査・バリュエーションモデリング（DCF/comps/LBO/3表連動モデル）を自動化するためのワークフロー、カスタムスキル、および常時適用ルールを内包しています。

本プロジェクトのすべての財務モデルは **Google Workspace（Google スプレッドシート）** での閲覧・編集に対応しています。

---

## 1. ディレクトリ構成

Antigravity のワークスペース設定ディレクトリである `.agents/` 内にすべての機能が集約されています。

```
.agents/
├── AGENTS.md                  # 統合された常時適用ルール＆プロジェクト案内
├── skills/                    # 23個のカスタムスキル（自動検出・適用対象）
│   ├── dcf-model/             # DCFバリュエーションモデル構築ロジック
│   ├── comps-analysis/        # 類似企業比較分析（comps）構築ロジック
│   ├── 3-statement-model/     # 3表連動モデル構築ロジック
│   ├── lbo-model/             # LBOモデル構築ロジック
│   ├── japan-equity-overrides/# 日本株ローカライズ共通ルール
│   └── ... (他18スキル)
└── workflows/                 # 19個のスラッシュコマンド（ワークフロー）定義
    ├── dcf.md                 # /dcf
    ├── comps.md               # /comps
    ├── agent-market-researcher.md # /agent-market-researcher
    └── ... (他16ワークフロー)
```

各機能の解説 is [docs/feature-guide.md](docs/feature-guide.md) を参照してください。

---

## 2. 特徴と機能

### ① Google Workspace（Google スプレッドシート）完全互換
- 成果物は Python の `openpyxl` を用いてスタンドアロンの `.xlsx` ファイルとして生成されます。Google ドライブにアップロードするだけでそのまま利用できます。
- Excel 独自の Live アドイン（Office JS API）や高度なマクロは使用せず、Google スプレッドシート互換の標準的な数式のみを使用します。
- 3表連動モデルなどの金利の循環参照を解くため、ファイル保存時に**反復計算（Iterative Calculation）を最初から有効化**するメタデータを自動付与します。

### ② 日本株ローカライズ（共通ルール化）
- スキル `japan-equity-overrides` を新設し、日本株を扱う際の基準（有報/短信等の開示優先順、円/百万円単位、3月期決算カレンダー、実効税率約30%、10年JGBリスクフリーレート、TOPIXベータ、PBR1倍割れ改善要請への考慮など）を完全に自動適用します。

### ③ 開発プロセスのプロセス強制
- 本プロジェクトの機能やルールの改修を行う場合は、常に新規ブランチを作成し、プルリクエスト（PR）を経由して `main` ブランチへマージする安全なワークフローを適用します。

---

## 3. データ取得方法と無料データパイプライン（yfinance）

本プロジェクトは、有料データプロバイダ（FactSet等）のMCPコネクタ未接続時でも動作するよう、無料かつ自動でデータ収集を行うためのパイプライン（[scripts/](scripts/)）を搭載しています。

株価情報および財務データの取得時には、以下の優先順位ルールが適用されます。

1. **【第1優先】Pythonライブラリ「yfinance」による自動取得**
   - スクリプト: [fetch_yfinance.py](scripts/fetch_yfinance.py)
   - 動作: 指定したティッカー（日本株は4桁のコードを渡せば自動的に `.T` を付加）の株価、ヒストリカルデータ、財務諸表（PL/BS/CFの年次・四半期）を取得し、`./out/market_data/` にCSV/JSONとして出力します。
2. **【第2優先】有料データプロバイダ（MCP） / 手動Web検索**
   - 上記の自動化ツールが利用できない場合のフォールバック。

### セットアップと実行方法
以下の手順で仮想環境を作成し、`requirements.txt` を用いて一括で依存関係をインストールできます。

```bash
# 1. 仮想環境の作成 (uv使用)
uv venv

# 2. 依存関係の一括インストール
uv pip install -r requirements.txt   # もしくは pip install -r requirements.txt

# 3. データの取得テスト
.\.venv\Scripts\python scripts/fetch_yfinance.py 7203
```

---

## 5. 付属スクリプト・ツールセット

本プロジェクトの [scripts/](scripts/) ディレクトリには、株式調査およびバリュエーションモデリングの一連の流れを自動化・デモ検証するための Python スクリプト群（全9ツール）が用意されています。

### ① データ収集 & 整形 (Data Pipeline)
- **[fetch_yfinance.py](scripts/fetch_yfinance.py)**: yfinanceから財務諸表CSVおよび株価データを自動収集。
- **[clean_data.py](scripts/clean_data.py)**: `prices.csv` などの生データの重複排除、空白トリム、日付フォーマット標準化等のクレンジングを実行。

### ② 財務バリュエーションモデル生成 (Financial Modeling)
- **[generate_models.py](scripts/generate_models.py)**: データベース（CSV）から動的に数値をパースし、DCFおよびCompsのExcelモデルを自動生成。
- **[generate_3statement.py](scripts/generate_3statement.py)**: 金利の循環参照を解決し、反復計算メタデータを付与した3表（PL/BS/CF）連動Excelモデルを自動生成。
- **[generate_lbo.py](scripts/generate_lbo.py)**: PE投資シミュレーション用LBOモデルを自動生成（Debt返済キャッシュスイープ、倍率別感度分析）。
- **[model_update.py](scripts/model_update.py)**: 前提変更（ガイダンス上方修正等）を自動反映して全モデルを再生成し、Valuationへの影響比較レポートをMarkdownで出力。

### ③ プレゼンテーション・資料自動化 (Pitch Book Automation)
- **[generate_pitch.py](scripts/generate_pitch.py)**: `python-pptx` を用いて、投資ピッチプレゼンテーション資料 (`.pptx`) を新規自動生成。
- **[deck_refresh.py](scripts/deck_refresh.py)**: 既存のスライド内の数値（売上・EBITDAマージン等）を最新モデルの値へ自動置換更新（ロールフォワード）。
- **[ib_check_deck.py](scripts/ib_check_deck.py)**: スライド上の数値が財務データベースと一致しているかを突合監査し、不整合を検出する品質チェック（QC）レポートを出力。

---

## 6. 開発・改修フロー

本プロジェクトを変更する際は、以下のプロセスに従ってください：

1. **GitHub イシューの作成**
   改修内容に応じたイシューを作成します。
2. **新規ブランチの作成**
   `main` から機能改修用のブランチを作成します。
   `git checkout -b feat/your-feature-name`
3. **コード編集とテスト**
   `.agents/` 配下のスキルやワークフローを編集し、テストを行います。
4. **プッシュとPR作成**
   変更をプッシュして、GitHub 上で PR を作成します。
5. **マージとクリーンアップ**
   PR を `main` ブランチにマージし、ローカル環境をクリーンアップします。

---

## 7. 留意事項
本プロジェクトが生成するモデル、メモ、リサーチノートはすべて**アナリスト用の草案（ドラフト）**です。最終的な数値検証、投資判断、自社に適用される規制の遵守は人間のレビューと自己責任に基づきます。
