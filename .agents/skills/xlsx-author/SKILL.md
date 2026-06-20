---
name: xlsx-author
description: Produce a .xlsx file on disk (headless) instead of driving a live Excel workbook — for managed-agent sessions with no open Office app.
---

# xlsx-author

Use this skill when running **headless** (managed-agent / CMA mode) and you need to deliver an Excel workbook as a **file artifact** rather than editing a live workbook via `mcp__office__excel_*`.

## Output contract

- Write to `./out/<name>.xlsx`. Create `./out/` if it does not exist.
- Return the relative path in your final message so the orchestration layer can collect it.

## How to build the workbook

Write a short Python script and run it with Bash. Use `openpyxl`:

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

wb = Workbook()
ws = wb.active; ws.title = "Inputs"
ws["B2"] = "Revenue"; ws["C2"] = 1_250_000_000
ws["C2"].font = Font(color="0000FF")           # blue = hardcoded input
calc = wb.create_sheet("DCF")
calc["C5"] = "=Inputs!C2*(1+Inputs!C3)"        # black = formula
wb.save("./out/model.xlsx")
```

## Conventions (mirror `audit-xls`)

- **Blue / black / green.** Blue = hardcoded input, black = formula, green = link to another sheet/file.
- **No hardcodes in calc cells.** Every calculation cell is a formula; every input lives on an Inputs tab.
- **Named ranges** for any value referenced from a deck or memo.
- **Balance checks.** Include a Checks tab that ties (BS balances, CF ties to cash, etc.) and surfaces TRUE/FALSE.
- **One model per file.** Do not append to an existing workbook unless explicitly asked.

## Google Workspace / Google Sheets Compatibility

Google Workspace（Google スプレッドシート）を分析に使用するため、`mcp__office__excel_*` などのライブ Excel 連携ツールは一切使用しないでください。常にこの headless スキル（Python/openpyxl）を使用して、Google ドライブに直接アップロード可能な `.xlsx` ファイルを生成してください。


---

## 日本株対応（ローカライズ）

> 日本株の成果物を扱う場合の補足。共通の読み替えは [日本株ローカライズ共通オーバーライド](../../localization/japan-equity-overrides.md)。

- 通貨・単位は **円／百万円**。数値書式は `#,##0`（小数なし、千区切り）、必要に応じ `¥` 表示。
- 年月は西暦で統一（和暦併記が必要な場合のみ追記）。決算期は3月期等を明示。
