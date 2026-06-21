---
name: model-update
description: Update financial models with new data — quarterly earnings, management guidance, macro changes, or revised assumptions. Adjusts estimates, recalculates valuation, and flags material changes. Use after earnings, guidance updates, or when assumptions need refreshing. Triggers on "update model", "plug earnings", "refresh estimates", "update numbers for [company]", "new guidance", or "revise estimates".
---

# Model Update

## Workflow

### Step 1: Identify What Changed

Determine the update trigger:
- **Earnings release**: New quarterly actuals to plug in
- **Guidance change**: Company updated forward outlook
- **Estimate revision**: Analyst changing assumptions based on new data
- **Macro update**: Interest rates, FX, commodity prices changed
- **Event-driven**: M&A, restructuring, new product, management change

### Step 2: Plug New Data

#### After Earnings
Update the model with reported actuals:

| Line Item | Prior Estimate | Actual | Delta | Notes |
|-----------|---------------|--------|-------|-------|
| Revenue | | | | |
| Gross Margin | | | | |
| Operating Expenses | | | | |
| EBITDA | | | | |
| EPS | | | | |
| [Key metric 1] | | | | |
| [Key metric 2] | | | | |

**Segment Detail** (if applicable):
- Update each segment's revenue and margin
- Note any segment mix shifts

**Balance Sheet / Cash Flow Updates**:
- Cash and debt balances
- Share count (buybacks, dilution)
- Capex actual vs. estimate
- Working capital changes

### Step 3: Revise Forward Estimates

Based on the new data, adjust forward estimates:

| | Old FY Est | New FY Est | Change | Old Next FY | New Next FY | Change |
|---|-----------|-----------|--------|------------|------------|--------|
| Revenue | | | | | | |
| EBITDA | | | | | | |
| EPS | | | | | | |

**Key Assumption Changes:**
- What assumptions are you changing and why?
- Revenue growth rate: old → new (reason)
- Margin assumption: old → new (reason)
- Any new items (restructuring charges, one-time gains, etc.)

### Step 4: Valuation Impact

Recalculate valuation with updated estimates:

| Valuation Method | Prior | Updated | Change |
|-----------------|-------|---------|--------|
| DCF fair value | | | |
| P/E (NTM EPS × target multiple) | | | |
| EV/EBITDA (NTM EBITDA × target multiple) | | | |
| **Price Target** | | | |

### Step 5: Summary & Action

**Estimate Change Summary:**
- One paragraph: what changed, why, and what it means for the stock
- Is this a thesis-changing event or noise?

**Rating / Price Target:**
- Maintain or change rating?
- New price target (if changed) with methodology
- Upside/downside to current price

### Step 6: Output

- Updated Excel model (if user provides the existing model)
- Estimate change summary (markdown or Word)
- Updated price target derivation

## Important Notes

- Always reconcile your estimates to the company's reported figures before projecting forward
- Note any non-recurring items and whether your estimates are GAAP or adjusted
- Track your estimate revision history — it shows your analytical progression
- If the quarter was noisy, separate signal from noise in your estimate changes
- Check consensus after updating — how do your revised estimates compare to the Street?
- Share count matters — dilution from stock comp, converts, or buybacks can materially affect EPS


---

## 日本株対応（ローカライズ）

> 本スキルは米国式（英語開示・USD・SEC EDGAR）前提。日本株では共通の読み替えを [日本株ローカライズ共通オーバーライド](../japan-equity-overrides/SKILL.md) に従い、本スキル固有の上書きは以下。

- 反映元は **決算短信の実績 ＋ 会社予想（通期見通し）**、および **業績予想の修正開示**。
- **経常利益段階** を含めて更新。通貨・単位は円／百万円。

---

## モデル更新自動化スクリプト (`model_update.py`) の利用方法

本プロジェクトには、上記のプロセスを自動化するためのPythonスクリプト `scripts/model_update.py` が用意されています。このスクリプトは、業績前提の修正、バックアップ作成、モデル再生成、監査履歴の記録、影響レポートの作成を一括で処理します。

### 1. 主な機能
- **財務前提の自動更新**: 引数で指定された売上高、EBIT、EBITDAの最新予想値を `summary.json` や `annual_income_stmt.csv` に自動反映します。
- **自動バックアップ作成**: データを書き換える前に、既存ファイルのタイムスタンプ付きバックアップ（例: `summary.json.20260621_120000.bak`）を同一ディレクトリに自動生成し、不慮のデータ消失を防ぎます。
- **監査トレール（変更履歴）の記録**: `update_history.json` を作成し、いつ・どの値をどう変更したかの推移履歴（監査証跡）を自動記録します。
- **全財務モデルの連動再生成**: 
  前提更新後、`generate_models.py`, `generate_3statement.py`, `generate_lbo.py` を順次実行し、DCF、Comps、3表連動、LBOモデルをすべて最新の前提に即して自動再生成します。
  - **【今回の改修】** テスト環境やマルチプロジェクト環境で出力先を変更できるよう、自身に指定された `--outdir` 引数を子プロセスへ安全に中継・伝播させ、データロード時のディレクトリの不整合やエラーを完全に防止する仕組みを実装しました。
- **更新影響レポートの自動出力**: 修正前後の目標株価（DCF法による）や主要前提の推移をまとめたMarkdown形式の比較レポート（例: `[Company]_Model_Update_[Date].md`）を `analysis/` 配下に自動生成します。

### 2. コマンドの使用方法
```bash
# 基本的な実行方法（ティッカーと各種予測前提の指定）
python scripts/model_update.py [Ticker] --revenue [新しい売上予測] --ebit [新しい営業利益予測] --ebitda [新しいEBITDA予測]

# 例: トヨタ自動車(7203)のEBITDA予測を10兆円に引き上げ、出力ディレクトリを `./out` に指定して実行
python scripts/model_update.py 7203 --ebitda 10000000000000 --outdir ./out
```

#### 引数オプション:
- `ticker` (必須): 企業ティッカー（例: `7203`, `MU`）
- `--revenue`: 新しい売上高予測値（数値）
- `--ebit`: 新しい営業利益（EBIT）予測値（数値）
- `--ebitda`: 新しいEBITDA予測値（数値）
- `--outdir` (任意, デフォルト: `./out`): 入出力フォルダのベースディレクトリ。この値は自動的に呼び出される子スクリプト（`generate_models.py` 等）にもそのまま引き継がれます。

