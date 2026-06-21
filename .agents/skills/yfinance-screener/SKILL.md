---
name: yfinance-screener
description: yfinance の標準スクリーニング機能（screen, EquityQuery）を用いて、特定の条件（P/Eレシオ、時価総額、地域等）を満たす銘柄の一覧を取得する。
---

# yfinance 銘柄スクリーニング（Screener）スキル

## 概要
Yahoo Finance が提供するスクリーニングAPIを `yfinance` を通じて呼び出し、特定の条件を満たす銘柄の一覧を取得します。
ローカルで全ティッカーをループしてデータを取得する方法に比べ、API制限に引っかかりにくく、非常に高速に動作します。

---

## 1. 関連ファイル
* **スクリプト**: [yfinance_screener.py](file:///d:/Programming/Application/financial-services/scripts/yfinance_screener.py) — 汎用的なスクリーニング処理を実行するためのコマンドラインスクリプト。

---

## 2. スクリプト引数の仕様

| 引数 | 説明 | デフォルト値 | 例 |
|---|---|---|---|
| `--region` | 銘柄の対象地域 | `jp` (日本) | `us` (米国), `jp` |
| `--sector` | 対象セクター | なし | `Technology`, `Financial Services` |
| `--industry` | 対象業界 | なし | `Semiconductors`, `Banks` |
| `--min-market-cap` | 最小時価総額 (地域通貨単位) | なし | JPYの場合: `1000000000000` (1兆円) |
| `--max-market-cap` | 最大時価総額 (地域通貨単位) | なし | JPYの場合: `5000000000000` (5兆円) |
| `--min-pe` | 最小 P/E レシオ | なし | `5` |
| `--max-pe` | 最大 P/E レシオ | なし | `15` |
| `--count` | 取得する最大銘柄数 | `25` | `10` |
| `--sort-by` | ソート基準フィールド | `intradaymarketcap` | `trailingPE`, `regularMarketPrice` |
| `--sort-type` | ソートの順序 | `DESC` (降順) | `ASC` (昇順) |
| `--output` | 結果の出力ファイルパス | なし | `out/screener_results.json` |
| `--format` | 出力ファイル形式 | `json` | `csv`, `json` |

---

## 3. コマンドライン実行例

### 例1：日本の大型株でP/Eが15倍以下の銘柄を5件抽出（コンソール出力）
```bash
.venv\Scripts\python scripts/yfinance_screener.py --region jp --min-market-cap 1000000000000 --max-pe 15 --count 5
```

### 例2：米国のITセクターでP/Eが30倍以下の銘柄を抽出し、CSVに保存
```bash
.venv\Scripts\python scripts/yfinance_screener.py --region us --sector Technology --max-pe 30 --format csv --output out/us_tech_undervalued.csv
```

---

## 4. エージェントがこのスキルを使用する際の手順

1. **要件定義**:
   ユーザーが「時価総額が〇〇以上の企業」「P/Eが〇〇以下のセクター」などを求めた場合、このスキルを活用します。
2. **スクリプト実行**:
   `yfinance_screener.py` を用いて、適切なパラメータを渡してスクリーニングを実行します。
3. **成果物の作成・更新**:
   出力されたCSVまたはJSONデータを元に、類似企業比較（Comps）スプレッドシートや、セクター分析レポートの作成に繋げます。
