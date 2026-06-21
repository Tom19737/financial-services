import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import os
import sys
import argparse
import re
from utils import find_ticker_dir, get_latest_financial_data, ExcelStyles, setup_logging

logger = setup_logging("generate_3statement")

def build_3statement_model(ticker_data, ticker_dir):
    wb = openpyxl.Workbook()
    
    # 反復計算有効化（3表の循環参照解決に必須）
    calc_pr = CalcProperties(iterate=True, refMode='A1', iterateCount=100, iterateDelta=0.001)
    wb.properties.calcPr = calc_pr
    
    ws = wb.active
    ws.title = "3-Statement Model"
    ws.views.sheetView[0].showGridLines = True
    
    # 共通スタイルのインポート
    styles = ExcelStyles()
    
    font_family = styles.font_family
    title_font = styles.title_font
    header_font = styles.header_font
    section_font = styles.section_font
    data_font = styles.data_font
    input_font = styles.input_font
    bold_data_font = styles.bold_data_font
    primary_fill = styles.primary_fill
    section_fill = styles.section_fill
    highlight_fill = styles.highlight_fill
    thin_border_side = styles.thin_border_side
    thin_border = styles.thin_border
    
    is_jpy = ticker_data["currency"] == "JPY"
    unit_str = "Bn JPY" if is_jpy else "Mn USD"
    div_factor = 1e9 if is_jpy else 1e6
    
    # 実績データの単位変換
    rev_act = ticker_data["revenue"] / div_factor
    ebit_act = ticker_data["ebit"] / div_factor
    da_act = ticker_data["depreciation"] / div_factor
    tax_act = ticker_data["tax_provision"] / div_factor
    debt_act = ticker_data["total_debt"] / div_factor
    cash_act = ticker_data["cash"] / div_factor
    
    # タイトル
    ws.merge_cells("A1:H1")
    ws["A1"] = f"{ticker_data['name']} ({ticker_data['ticker']}) - 3-STATEMENT INTEGRATED FINANCIAL MODEL"
    ws["A1"].font = title_font
    ws["A1"].fill = primary_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 40
    
    # Inputsシートを作成して前提条件を配置
    ws_inputs = wb.create_sheet(title="Inputs")
    ws_inputs.views.sheetView[0].showGridLines = True

    # タイトル行 (Inputs)
    ws_inputs.merge_cells("A1:C1")
    ws_inputs["A1"] = f"{ticker_data['name']} ({ticker_data['ticker']}) - 3-STATEMENT VALUATION INPUTS"
    ws_inputs["A1"].font = title_font
    ws_inputs["A1"].fill = primary_fill
    ws_inputs["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws_inputs.row_dimensions[1].height = 40

    ws_inputs.cell(row=3, column=1, value="Parameter").font = header_font
    ws_inputs.cell(row=3, column=1).fill = primary_fill
    ws_inputs.cell(row=3, column=2, value="Value").font = header_font
    ws_inputs.cell(row=3, column=2).fill = primary_fill
    ws_inputs.cell(row=3, column=3, value="Source / Note").font = header_font
    ws_inputs.cell(row=3, column=3).fill = primary_fill
    ws_inputs.row_dimensions[3].height = 25

    inputs_data = [
        # Revenue Growth
        ("Revenue Growth FY25E", 0.12, "0.0%", "[ASSUMPTION]"),
        ("Revenue Growth FY26E", 0.10, "0.0%", "[ASSUMPTION]"),
        ("Revenue Growth FY27E", 0.08, "0.0%", "[ASSUMPTION]"),
        ("Revenue Growth FY28E", 0.06, "0.0%", "[ASSUMPTION]"),
        ("Revenue Growth FY29E", 0.05, "0.0%", "[ASSUMPTION]"),
        ("Dummy", "", "", ""), # Row 9
        # COGS % of Rev
        ("COGS % of Revenue FY25E", 0.64, "0.0%", "[ASSUMPTION]"),
        ("COGS % of Revenue FY26E", 0.63, "0.0%", "[ASSUMPTION]"),
        ("COGS % of Revenue FY27E", 0.62, "0.0%", "[ASSUMPTION]"),
        ("COGS % of Revenue FY28E", 0.62, "0.0%", "[ASSUMPTION]"),
        ("COGS % of Revenue FY29E", 0.62, "0.0%", "[ASSUMPTION]"),
        ("Dummy", "", "", ""), # Row 15
        # SG&A % of Rev
        ("SG&A % of Revenue FY25E", 0.145, "0.0%", "[ASSUMPTION]"),
        ("SG&A % of Revenue FY26E", 0.14, "0.0%", "[ASSUMPTION]"),
        ("SG&A % of Revenue FY27E", 0.14, "0.0%", "[ASSUMPTION]"),
        ("SG&A % of Revenue FY28E", 0.14, "0.0%", "[ASSUMPTION]"),
        ("SG&A % of Revenue FY29E", 0.14, "0.0%", "[ASSUMPTION]"),
        ("Dummy", "", "", ""), # Row 21
        # D&A % of Rev
        ("D&A % of Revenue FY25E", 0.10, "0.0%", "[ASSUMPTION]"),
        ("D&A % of Revenue FY26E", 0.10, "0.0%", "[ASSUMPTION]"),
        ("D&A % of Revenue FY27E", 0.095, "0.0%", "[ASSUMPTION]"),
        ("D&A % of Revenue FY28E", 0.09, "0.0%", "[ASSUMPTION]"),
        ("D&A % of Revenue FY29E", 0.09, "0.0%", "[ASSUMPTION]"),
        ("Dummy", "", "", ""), # Row 27
        # Debt Interest Rate
        ("Debt Interest Rate", 0.025, "0.0%", "[ASSUMPTION] Cost of Debt"),
        ("Dummy", "", "", ""), # Row 29
        # AR/Inv/AP % of Rev
        ("Accounts Receivable % of Rev", 0.12, "0.0%", "[ASSUMPTION]"),
        ("Inventory % of Rev", 0.17, "0.0%", "[ASSUMPTION]"),
        ("Accounts Payable % of Rev", 0.08, "0.0%", "[ASSUMPTION]"),
    ]

    inputs_map = {}

    for idx, (label, val, fmt, src) in enumerate(inputs_data):
        row = 4 + idx
        ws_inputs.row_dimensions[row].height = 20
        ws_inputs.cell(row=row, column=1, value=label).font = data_font
        if val != "":
            cell_val = ws_inputs.cell(row=row, column=2, value=val)
            cell_val.font = input_font
            cell_val.number_format = fmt
            cell_val.alignment = Alignment(horizontal="right")
            inputs_map[label] = f"Inputs!$B${row}"
        ws_inputs.cell(row=row, column=3, value=src).font = data_font
        for col in range(1, 4):
            ws_inputs.cell(row=row, column=col).border = thin_border

    # CapEx Projections
    ws_inputs.cell(row=38, column=1, value="CapEx Projections").font = bold_data_font
    ws_inputs.cell(row=39, column=1, value="Year").font = header_font
    ws_inputs.cell(row=39, column=1).fill = primary_fill
    ws_inputs.cell(row=39, column=2, value="CapEx").font = header_font
    ws_inputs.cell(row=39, column=2).fill = primary_fill
    ws_inputs.cell(row=39, column=3, value="Source / Note").font = header_font
    ws_inputs.cell(row=39, column=3).fill = primary_fill
    ws_inputs.row_dimensions[39].height = 20

    capex_inputs = [
        ("FY25E", -300.0, "[ASSUMPTION]"),
        ("FY26E", -320.0, "[ASSUMPTION]"),
        ("FY27E", -310.0, "[ASSUMPTION]"),
        ("FY28E", -300.0, "[ASSUMPTION]"),
        ("FY29E", -300.0, "[ASSUMPTION]"),
    ]
    for idx, (yr, val, src) in enumerate(capex_inputs):
        row = 40 + idx
        ws_inputs.row_dimensions[row].height = 20
        ws_inputs.cell(row=row, column=1, value=yr).font = data_font
        cell_val = ws_inputs.cell(row=row, column=2, value=val)
        cell_val.font = input_font
        cell_val.number_format = "#,##0.0"
        cell_val.alignment = Alignment(horizontal="right")
        ws_inputs.cell(row=row, column=3, value=src).font = data_font
        inputs_map[f"CapEx {yr}"] = f"Inputs!$B${row}"
        for col in range(1, 4):
            ws_inputs.cell(row=row, column=col).border = thin_border

    # Debt Drawdown / (Repayment)
    ws_inputs.cell(row=46, column=1, value="Debt Drawdown / (Repayment)").font = bold_data_font
    ws_inputs.cell(row=47, column=1, value="Year").font = header_font
    ws_inputs.cell(row=47, column=1).fill = primary_fill
    ws_inputs.cell(row=47, column=2, value="Drawdown").font = header_font
    ws_inputs.cell(row=47, column=2).fill = primary_fill
    ws_inputs.cell(row=47, column=3, value="Source / Note").font = header_font
    ws_inputs.cell(row=47, column=3).fill = primary_fill
    ws_inputs.row_dimensions[47].height = 20

    debt_inputs = [
        ("FY25E", 50.0, "[ASSUMPTION]"),
        ("FY26E", -20.0, "[ASSUMPTION]"),
        ("FY27E", -30.0, "[ASSUMPTION]"),
        ("FY28E", -40.0, "[ASSUMPTION]"),
        ("FY29E", -50.0, "[ASSUMPTION]"),
    ]
    for idx, (yr, val, src) in enumerate(debt_inputs):
        row = 48 + idx
        ws_inputs.row_dimensions[row].height = 20
        ws_inputs.cell(row=row, column=1, value=yr).font = data_font
        cell_val = ws_inputs.cell(row=row, column=2, value=val)
        cell_val.font = input_font
        cell_val.number_format = "#,##0.0"
        cell_val.alignment = Alignment(horizontal="right")
        ws_inputs.cell(row=row, column=3, value=src).font = data_font
        inputs_map[f"Debt Drawdown {yr}"] = f"Inputs!$B${row}"
        for col in range(1, 4):
            ws_inputs.cell(row=row, column=col).border = thin_border

    # Inputsシートの列幅調整
    for col in ws_inputs.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_inputs.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # ヘッダー
    headers = [f"Integrated Financial Model ({unit_str})", "FY24A", "FY25E", "FY26E", "FY27E", "FY28E", "FY29E"]
    for col_idx, header in enumerate(headers, 1):
        c = ws.cell(row=3, column=col_idx, value=header)
        c.font = header_font
        c.fill = primary_fill
        c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[3].height = 28
    
    # 1. 損益計算書 (Income Statement)
    ws["A5"] = "I. INCOME STATEMENT"
    ws["A5"].font = section_font
    ws.merge_cells("A5:G5")
    ws["A5"].fill = section_fill
    
    tax_rate_ltm = tax_act / ebit_act if ebit_act > 0 else 0.306
    
    is_rows = [
        ("Total Revenue", [rev_act, "=B{row}*(1+{Inputs:Revenue Growth FY25E})", "=C{row}*(1+{Inputs:Revenue Growth FY26E})", "=D{row}*(1+{Inputs:Revenue Growth FY27E})", "=E{row}*(1+{Inputs:Revenue Growth FY28E})", "=F{row}*(1+{Inputs:Revenue Growth FY29E})"]),
        ("Revenue Growth", ["", "=(C{Total Revenue}-B{Total Revenue})/B{Total Revenue}", "=(D{Total Revenue}-C{Total Revenue})/C{Total Revenue}", "=(E{Total Revenue}-D{Total Revenue})/D{Total Revenue}", "=(F{Total Revenue}-E{Total Revenue})/E{Total Revenue}", "=(G{Total Revenue}-F{Total Revenue})/F{Total Revenue}"]),
        ("Cost of Goods Sold (COGS)", [rev_act * 0.65, "=C{Total Revenue}*{Inputs:COGS % of Revenue FY25E}", "=D{Total Revenue}*{Inputs:COGS % of Revenue FY26E}", "=E{Total Revenue}*{Inputs:COGS % of Revenue FY27E}", "=F{Total Revenue}*{Inputs:COGS % of Revenue FY28E}", "=G{Total Revenue}*{Inputs:COGS % of Revenue FY29E}"]),
        ("Gross Profit", ["=B{Total Revenue}-B{Cost of Goods Sold (COGS)}", "=C{Total Revenue}-C{Cost of Goods Sold (COGS)}", "=D{Total Revenue}-D{Cost of Goods Sold (COGS)}", "=E{Total Revenue}-E{Cost of Goods Sold (COGS)}", "=F{Total Revenue}-F{Cost of Goods Sold (COGS)}", "=G{Total Revenue}-G{Cost of Goods Sold (COGS)}"]),
        ("SG&A Expenses", [rev_act * 0.15, "=C{Total Revenue}*{Inputs:SG&A % of Revenue FY25E}", "=D{Total Revenue}*{Inputs:SG&A % of Revenue FY26E}", "=E{Total Revenue}*{Inputs:SG&A % of Revenue FY27E}", "=F{Total Revenue}*{Inputs:SG&A % of Revenue FY28E}", "=G{Total Revenue}*{Inputs:SG&A % of Revenue FY29E}"]),
        ("EBITDA", ["=B{Gross Profit}-B{SG&A Expenses}", "=C{Gross Profit}-C{SG&A Expenses}", "=D{Gross Profit}-D{SG&A Expenses}", "=E{Gross Profit}-E{SG&A Expenses}", "=F{Gross Profit}-F{SG&A Expenses}", "=G{Gross Profit}-G{SG&A Expenses}"]),
        ("Depreciation & Amortization", [da_act, "=C{Total Revenue}*{Inputs:D&A % of Revenue FY25E}", "=D{Total Revenue}*{Inputs:D&A % of Revenue FY26E}", "=E{Total Revenue}*{Inputs:D&A % of Revenue FY27E}", "=F{Total Revenue}*{Inputs:D&A % of Revenue FY28E}", "=G{Total Revenue}*{Inputs:D&A % of Revenue FY29E}"]),
        ("EBIT (Operating Income)", ["=B{EBITDA}-B{Depreciation & Amortization}", "=C{EBITDA}-C{Depreciation & Amortization}", "=D{EBITDA}-D{Depreciation & Amortization}", "=E{EBITDA}-E{Depreciation & Amortization}", "=F{EBITDA}-F{Depreciation & Amortization}", "=G{EBITDA}-G{Depreciation & Amortization}"]),
        ("Interest Expense", [15.0, "=AVERAGE(B{Short-Term & Long-Term Debt},C{Short-Term & Long-Term Debt})*{Inputs:Debt Interest Rate}", "=AVERAGE(C{Short-Term & Long-Term Debt},D{Short-Term & Long-Term Debt})*{Inputs:Debt Interest Rate}", "=AVERAGE(D{Short-Term & Long-Term Debt},E{Short-Term & Long-Term Debt})*{Inputs:Debt Interest Rate}", "=AVERAGE(E{Short-Term & Long-Term Debt},F{Short-Term & Long-Term Debt})*{Inputs:Debt Interest Rate}", "=AVERAGE(F{Short-Term & Long-Term Debt},G{Short-Term & Long-Term Debt})*{Inputs:Debt Interest Rate}"]),
        ("Pretax Income", ["=B{EBIT (Operating Income)}-B{Interest Expense}", "=C{EBIT (Operating Income)}-C{Interest Expense}", "=D{EBIT (Operating Income)}-D{Interest Expense}", "=E{EBIT (Operating Income)}-E{Interest Expense}", "=F{EBIT (Operating Income)}-F{Interest Expense}", "=G{EBIT (Operating Income)}-G{Interest Expense}"]),
        ("Income Taxes", [tax_act, f"=C{{Pretax Income}}*{tax_rate_ltm:.4f}", f"=D{{Pretax Income}}*{tax_rate_ltm:.4f}", f"=E{{Pretax Income}}*{tax_rate_ltm:.4f}", f"=F{{Pretax Income}}*{tax_rate_ltm:.4f}", f"=G{{Pretax Income}}*{tax_rate_ltm:.4f}"]),
        ("Net Income", ["=B{Pretax Income}-B{Income Taxes}", "=C{Pretax Income}-C{Income Taxes}", "=D{Pretax Income}-D{Income Taxes}", "=E{Pretax Income}-E{Income Taxes}", "=F{Pretax Income}-F{Income Taxes}", "=G{Pretax Income}-G{Income Taxes}"])
    ]
    
    # 2. 貸借対照表 (Balance Sheet)
    bs_rows = [
        ("ASSETS", ["", "", "", "", "", ""]),
        ("Cash & Equivalents", [cash_act, "=B{Ending Cash Balance}", "=C{Ending Cash Balance}", "=D{Ending Cash Balance}", "=E{Ending Cash Balance}", "=F{Ending Cash Balance}"]),
        ("Accounts Receivable", [rev_act * 0.12, "=C{Total Revenue}*{Inputs:Accounts Receivable % of Rev}", "=D{Total Revenue}*{Inputs:Accounts Receivable % of Rev}", "=E{Total Revenue}*{Inputs:Accounts Receivable % of Rev}", "=F{Total Revenue}*{Inputs:Accounts Receivable % of Rev}", "=G{Total Revenue}*{Inputs:Accounts Receivable % of Rev}"]),
        ("Inventory", [rev_act * 0.18, "=C{Total Revenue}*{Inputs:Inventory % of Rev}", "=D{Total Revenue}*{Inputs:Inventory % of Rev}", "=E{Total Revenue}*{Inputs:Inventory % of Rev}", "=F{Total Revenue}*{Inputs:Inventory % of Rev}", "=G{Total Revenue}*{Inputs:Inventory % of Rev}"]),
        ("Property, Plant & Equipment (Net)", [1200.0, "=B{row}+C{Capital Expenditures (CapEx)}-C{Depreciation & Amortization}", "=C{row}+D{Capital Expenditures (CapEx)}-D{Depreciation & Amortization}", "=D{row}+E{Capital Expenditures (CapEx)}-E{Depreciation & Amortization}", "=E{row}+F{Capital Expenditures (CapEx)}-F{Depreciation & Amortization}", "=F{row}+G{Capital Expenditures (CapEx)}-G{Depreciation & Amortization}"]),
        ("Total Assets", ["=SUM(B{Cash & Equivalents}:B{Property, Plant & Equipment (Net)})", "=SUM(C{Cash & Equivalents}:C{Property, Plant & Equipment (Net)})", "=SUM(D{Cash & Equivalents}:D{Property, Plant & Equipment (Net)})", "=SUM(E{Cash & Equivalents}:E{Property, Plant & Equipment (Net)})", "=SUM(F{Cash & Equivalents}:F{Property, Plant & Equipment (Net)})", "=SUM(G{Cash & Equivalents}:G{Property, Plant & Equipment (Net)})"]),
        
        ("LIABILITIES & EQUITY", ["", "", "", "", "", ""]),
        ("Accounts Payable", [rev_act * 0.08, "=C{Total Revenue}*{Inputs:Accounts Payable % of Rev}", "=D{Total Revenue}*{Inputs:Accounts Payable % of Rev}", "=E{Total Revenue}*{Inputs:Accounts Payable % of Rev}", "=F{Total Revenue}*{Inputs:Accounts Payable % of Rev}", "=G{Total Revenue}*{Inputs:Accounts Payable % of Rev}"]),
        ("Short-Term & Long-Term Debt", [debt_act, "=B{row}+C{Debt Drawdown / (Repayment)}", "=C{row}+D{Debt Drawdown / (Repayment)}", "=D{row}+E{Debt Drawdown / (Repayment)}", "=E{row}+F{Debt Drawdown / (Repayment)}", "=F{row}+G{Debt Drawdown / (Repayment)}"]),
        ("Total Liabilities", ["=B{Accounts Payable}+B{Short-Term & Long-Term Debt}", "=C{Accounts Payable}+C{Short-Term & Long-Term Debt}", "=D{Accounts Payable}+D{Short-Term & Long-Term Debt}", "=E{Accounts Payable}+E{Short-Term & Long-Term Debt}", "=F{Accounts Payable}+F{Short-Term & Long-Term Debt}", "=G{Accounts Payable}+G{Short-Term & Long-Term Debt}"]),
        
        ("Share Capital (Paid-in)", [800.0, "=B{row}", "=C{row}", "=D{row}", "=E{row}", "=F{row}"]),
        ("Retained Earnings", [300.0, "=B{row}+C{Net Income}", "=C{row}+D{Net Income}", "=D{row}+E{Net Income}", "=E{row}+F{Net Income}", "=F{row}+G{Net Income}"]),
        ("Total Equity", ["=B{Share Capital (Paid-in)}+B{Retained Earnings}", "=C{Share Capital (Paid-in)}+C{Retained Earnings}", "=D{Share Capital (Paid-in)}+D{Retained Earnings}", "=E{Share Capital (Paid-in)}+E{Retained Earnings}", "=F{Share Capital (Paid-in)}+F{Retained Earnings}", "=G{Share Capital (Paid-in)}+G{Retained Earnings}"]),
        ("Total Liabilities & Equity", ["=B{Total Liabilities}+B{Total Equity}", "=C{Total Liabilities}+C{Total Equity}", "=D{Total Liabilities}+D{Total Equity}", "=E{Total Liabilities}+E{Total Equity}", "=F{Total Liabilities}+F{Total Equity}", "=G{Total Liabilities}+G{Total Equity}"]),
        
        ("BALANCE CHECK (Tie-out)", ["=B{Total Assets}-B{Total Liabilities & Equity}", "=C{Total Assets}-C{Total Liabilities & Equity}", "=D{Total Assets}-D{Total Liabilities & Equity}", "=E{Total Assets}-E{Total Liabilities & Equity}", "=F{Total Assets}-F{Total Liabilities & Equity}", "=G{Total Assets}-G{Total Liabilities & Equity}"])
    ]
    
    # 3. キャッシュ・フロー計算書 (Cash Flow Statement)
    cf_rows = [
        ("Net Income (CF)", ["=B{Net Income}", "=C{Net Income}", "=D{Net Income}", "=E{Net Income}", "=F{Net Income}", "=G{Net Income}"]),
        ("Plus: D&A", ["=B{Depreciation & Amortization}", "=C{Depreciation & Amortization}", "=D{Depreciation & Amortization}", "=E{Depreciation & Amortization}", "=F{Depreciation & Amortization}", "=G{Depreciation & Amortization}"]),
        ("Less: Change in Receivables", ["", "=-(C{Accounts Receivable}-B{Accounts Receivable})", "=-(D{Accounts Receivable}-C{Accounts Receivable})", "=-(E{Accounts Receivable}-D{Accounts Receivable})", "=-(F{Accounts Receivable}-E{Accounts Receivable})", "=-(G{Accounts Receivable}-F{Accounts Receivable})"]),
        ("Less: Change in Inventory", ["", "=-(C{Inventory}-B{Inventory})", "=-(D{Inventory}-C{Inventory})", "=-(E{Inventory}-D{Inventory})", "=-(F{Inventory}-E{Inventory})", "=-(G{Inventory}-F{Inventory})"]),
        ("Plus: Change in Payables", ["", "=C{Accounts Payable}-B{Accounts Payable}", "=D{Accounts Payable}-C{Accounts Payable}", "=E{Accounts Payable}-D{Accounts Payable}", "=F{Accounts Payable}-E{Accounts Payable}", "=G{Accounts Payable}-F{Accounts Payable}"]),
        ("Operating Cash Flow (OCF)", ["=SUM(B{Net Income (CF)}:B{Plus: Change in Payables})", "=SUM(C{Net Income (CF)}:C{Plus: Change in Payables})", "=SUM(D{Net Income (CF)}:D{Plus: Change in Payables})", "=SUM(E{Net Income (CF)}:E{Plus: Change in Payables})", "=SUM(F{Net Income (CF)}:F{Plus: Change in Payables})", "=SUM(G{Net Income (CF)}:G{Plus: Change in Payables})"]),
        
        ("Capital Expenditures (CapEx)", [-225.6, "={Inputs:CapEx FY25E}", "={Inputs:CapEx FY26E}", "={Inputs:CapEx FY27E}", "={Inputs:CapEx FY28E}", "={Inputs:CapEx FY29E}"]),
        ("Investing Cash Flow (ICF)", ["=B{Capital Expenditures (CapEx)}", "=C{Capital Expenditures (CapEx)}", "=D{Capital Expenditures (CapEx)}", "=E{Capital Expenditures (CapEx)}", "=F{Capital Expenditures (CapEx)}", "=G{Capital Expenditures (CapEx)}"]),
        
        ("Debt Drawdown / (Repayment)", [-324.3, "={Inputs:Debt Drawdown FY25E}", "={Inputs:Debt Drawdown FY26E}", "={Inputs:Debt Drawdown FY27E}", "={Inputs:Debt Drawdown FY28E}", "={Inputs:Debt Drawdown FY29E}"]),
        ("Financing Cash Flow (FCF)", ["=B{Debt Drawdown / (Repayment)}", "=C{Debt Drawdown / (Repayment)}", "=D{Debt Drawdown / (Repayment)}", "=E{Debt Drawdown / (Repayment)}", "=F{Debt Drawdown / (Repayment)}", "=G{Debt Drawdown / (Repayment)}"]),
        
        ("Net Change in Cash", ["=B{Operating Cash Flow (OCF)}+B{Investing Cash Flow (ICF)}+B{Financing Cash Flow (FCF)}", "=C{Operating Cash Flow (OCF)}+C{Investing Cash Flow (ICF)}+C{Financing Cash Flow (FCF)}", "=D{Operating Cash Flow (OCF)}+D{Investing Cash Flow (ICF)}+D{Financing Cash Flow (FCF)}", "=E{Operating Cash Flow (OCF)}+E{Investing Cash Flow (ICF)}+E{Financing Cash Flow (FCF)}", "=F{Operating Cash Flow (OCF)}+F{Investing Cash Flow (ICF)}+F{Financing Cash Flow (FCF)}", "=G{Operating Cash Flow (OCF)}+G{Investing Cash Flow (ICF)}+G{Financing Cash Flow (FCF)}"]),
        ("Beginning Cash Balance", [187.6, "=B{Ending Cash Balance}", "=C{Ending Cash Balance}", "=D{Ending Cash Balance}", "=E{Ending Cash Balance}", "=F{Ending Cash Balance}"]),
        ("Ending Cash Balance", ["=B{Beginning Cash Balance}+B{Net Change in Cash}", "=C{Beginning Cash Balance}+C{Net Change in Cash}", "=D{Beginning Cash Balance}+D{Net Change in Cash}", "=E{Beginning Cash Balance}+E{Net Change in Cash}", "=F{Beginning Cash Balance}+F{Net Change in Cash}", "=G{Beginning Cash Balance}+G{Net Change in Cash}"])
    ]
    
    # 行番号を動的に事前確定する
    row_map = {}
    
    # 1. IS の行番号確定
    current_row = 6
    for label, _ in is_rows:
        row_map[label] = current_row
        current_row += 1
        
    # 2. BS の行番号確定
    title_row_bs = current_row + 1 # タイトル行 (II. BALANCE SHEET)
    current_row = title_row_bs + 1 # ASSETSラベルの行
    for label, _ in bs_rows:
        row_map[label] = current_row
        current_row += 1
        
    # 3. CF の行番号確定
    title_row_cf = current_row + 1 # タイトル行 (III. CASH FLOW STATEMENT)
    current_row = title_row_cf + 1
    for label, _ in cf_rows:
        row_map[label] = current_row
        current_row += 1

    # テンプレート数式を解決するヘルパー関数
    def resolve_formula(template, col_idx, current_row_num):
        if not isinstance(template, str) or not template.startswith("="):
            return template
            
        col_letter = get_column_letter(col_idx)
        prev_col_letter = get_column_letter(col_idx - 1) if col_idx > 2 else ""
        
        formula = template
        
        # {Inputs:xxx} の置換
        def replace_inputs(match):
            key = match.group(1)
            return inputs_map.get(key, f"Inputs!$B$4")
            
        formula = re.sub(r'\{Inputs:([^}]+)\}', replace_inputs, formula)
        
        # {row} 自体の置換 (現在の行)
        formula = formula.replace("{row}", str(current_row_num))
        
        # {prev_col_letter} や {col_letter} を補完するためにプレースホルダー内の置換を行う
        # {prev:xxx} の置換
        def replace_prev(match):
            key = match.group(1)
            row = row_map.get(key)
            if row:
                return f"{prev_col_letter}{row}"
            return f"{prev_col_letter}1"
            
        formula = re.sub(r'\{prev:([^}]+)\}', replace_prev, formula)
        
        # {xxx} の置換 (現在の列 of 特定行)
        def replace_curr(match):
            key = match.group(1)
            row = row_map.get(key)
            if row:
                return f"{col_letter}{row}"
            return f"{col_letter}1"
            
        formula = re.sub(r'\{([^}]+)\}', replace_curr, formula)
        
        return formula

    # データを流し込む関数
    def populate_section(rows, start_row):
        for idx, (label, vals) in enumerate(rows):
            r = start_row + idx
            ws.row_dimensions[r].height = 22
            
            is_bold = label in ["Total Revenue", "Gross Profit", "EBITDA", "Net Income", "Total Assets", "Total Liabilities", "Total Equity", "Total Liabilities & Equity", "Operating Cash Flow (OCF)", "Investing Cash Flow (ICF)", "Financing Cash Flow (FCF)", "Net Change in Cash", "Ending Cash Balance", "BALANCE CHECK (Tie-out)"]
            
            cell_label = ws.cell(row=r, column=1, value=label)
            cell_label.font = bold_data_font if is_bold else data_font
            
            if label == "BALANCE CHECK (Tie-out)":
                cell_label.fill = highlight_fill
                cell_label.font = Font(name=font_family, size=11, bold=True, color="047857")
                
            for col_idx, val in enumerate(vals, 2):
                cell = ws.cell(row=r, column=col_idx)
                cell.alignment = Alignment(horizontal="right")
                
                # 数式テンプレートの動的解決
                resolved_val = resolve_formula(val, col_idx, r)
                
                if str(resolved_val).startswith("="):
                    cell.value = resolved_val
                    cell.font = bold_data_font if is_bold else data_font
                else:
                    cell.value = resolved_val
                    cell.font = input_font if (col_idx == 2 or label in ["Capital Expenditures (CapEx)", "Debt Drawdown / (Repayment)", "Total Revenue"]) else data_font
                
                if "%" in label or "Growth" in label:
                    cell.number_format = '0.0%'
                elif label == "BALANCE CHECK (Tie-out)":
                    cell.number_format = '0.00'
                    cell.fill = highlight_fill
                else:
                    cell.number_format = '#,##0.0'
                    
                if is_bold:
                    cell.border = Border(top=thin_border_side, bottom=Side(style='double' if "Total" in label or "Balance" in label or "Ending Cash" in label or "Net Income" in label else 'thin', color='1B263B'))
                    
        return start_row + len(rows)
        
    # I. ISを描画
    last_row = populate_section(is_rows, 6)
    
    # II. BSを描画
    ws.cell(row=title_row_bs, column=1, value="II. BALANCE SHEET").font = section_font
    ws.merge_cells(start_row=title_row_bs, start_column=1, end_row=title_row_bs, end_column=7)
    ws.cell(row=title_row_bs, column=1).fill = section_fill
    last_row = populate_section(bs_rows, title_row_bs + 1)
    
    # III. CFを描画
    ws.cell(row=title_row_cf, column=1, value="III. CASH FLOW STATEMENT").font = section_font
    ws.merge_cells(start_row=title_row_cf, start_column=1, end_row=title_row_cf, end_column=7)
    ws.cell(row=title_row_cf, column=1).fill = section_fill
    last_row = populate_section(cf_rows, title_row_cf + 1)
    
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 15)
        
    target_path = os.path.join(ticker_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, f"3statement_{ticker_data['ticker']}.xlsx")
    wb.save(out_file)
    logger.info(f"Successfully generated 3-Statement model: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Generate 3-statement financial model")
    parser.add_argument("ticker", type=str, help="Stock ticker")
    parser.add_argument("--outdir", type=str, default="./out", help="Base output directory")
    args = parser.parse_args()
    
    ticker_str = args.ticker.strip()
    ticker_dir = find_ticker_dir(args.outdir, ticker_str)
    
    try:
        ticker_data = get_latest_financial_data(ticker_dir, ticker_str)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
        
    build_3statement_model(ticker_data, ticker_dir)

if __name__ == "__main__":
    main()
