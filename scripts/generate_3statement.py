import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import os
import sys
import argparse
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
        ("Total Revenue", [rev_act, "=B6*1.12", "=C6*1.10", "=D6*1.08", "=E6*1.06", "=F6*1.05"]),
        ("Revenue Growth", ["", "=(C6-B6)/B6", "=(D6-C6)/C6", "=(E6-D6)/D6", "=(F6-E6)/E6", "=(G6-F6)/F6"]),
        ("Cost of Goods Sold (COGS)", [rev_act * 0.65, "=C6*0.64", "=D6*0.63", "=E6*0.62", "=F6*0.62", "=G6*0.62"]),
        ("Gross Profit", ["=B6-B8", "=C6-C8", "=D6-D8", "=E6-E8", "=F6-F8", "=G6-G8"]),
        ("SG&A Expenses", [rev_act * 0.15, "=C6*0.145", "=D6*0.14", "=E6*0.14", "=F6*0.14", "=G6*0.14"]),
        ("EBITDA", ["=B9-B10", "=C9-C10", "=D9-D10", "=E9-E10", "=F9-F10", "=G9-G10"]),
        ("Depreciation & Amortization", [da_act, "=C6*0.10", "=D6*0.10", "=E6*0.095", "=F6*0.09", "=G6*0.09"]),
        ("EBIT (Operating Income)", ["=B11-B12", "=C11-C12", "=D11-D12", "=E11-E12", "=F11-F12", "=G11-G12"]),
        ("Interest Expense", [15.0, "=AVERAGE(B28,C28)*0.025", "=AVERAGE(C28,D28)*0.025", "=AVERAGE(D28,E28)*0.025", "=AVERAGE(E28,F28)*0.025", "=AVERAGE(F28,G28)*0.025"]), # B/S Debtを参照
        ("Pretax Income", ["=B13-B14", "=C13-C14", "=D13-D14", "=E13-E14", "=F13-F14", "=G13-G14"]), # C-1バグ修正: "=E13-D14" -> "=E13-E14"
        ("Income Taxes", [tax_act, f"=C15*{tax_rate_ltm:.4f}", f"=D15*{tax_rate_ltm:.4f}", f"=E15*{tax_rate_ltm:.4f}", f"=F15*{tax_rate_ltm:.4f}", f"=G15*{tax_rate_ltm:.4f}"]),
        ("Net Income", ["=B15-B16", "=C15-C16", "=D15-D16", "=E15-E16", "=F15-F16", "=G15-G16"])
    ]
    
    # 2. 貸借対照表 (Balance Sheet)
    bs_rows = [
        ("ASSETS", ["", "", "", "", "", ""]),
        ("Cash & Equivalents", [cash_act, "=B49", "=C49", "=D49", "=E49", "=F49"]), # CFの期末現金 (49行目)
        ("Accounts Receivable", [rev_act * 0.12, "=C6*0.12", "=D6*0.12", "=E6*0.12", "=F6*0.12", "=G6*0.12"]),
        ("Inventory", [rev_act * 0.18, "=C6*0.17", "=D6*0.17", "=E6*0.17", "=F6*0.17", "=G6*0.17"]),
        ("Property, Plant & Equipment (Net)", [1200.0, "=B24+C43-C12", "=C24+D43-D12", "=D24+E43-E12", "=E24+F43-F12", "=F24+G43-G12"]), # 前期PPE + CapEx(43行目) - D&A(12行目)
        ("Total Assets", ["=SUM(B21:B24)", "=SUM(C21:C24)", "=SUM(D21:D24)", "=SUM(E21:E24)", "=SUM(F21:F24)", "=SUM(G21:G24)"]),
        
        ("LIABILITIES & EQUITY", ["", "", "", "", "", ""]),
        ("Accounts Payable", [rev_act * 0.08, "=C6*0.08", "=D6*0.08", "=E6*0.08", "=F6*0.08", "=G6*0.08"]),
        ("Short-Term & Long-Term Debt", [debt_act, "=B28+C45", "=C28+D45", "=D28+E45", "=E28+F45", "=F28+G45"]), # 前期Debt + 借入純増減 (45行目)
        ("Total Liabilities", ["=B27+B28", "=C27+C28", "=D27+D28", "=E27+E28", "=F27+F28", "=G27+G28"]),
        
        ("Share Capital (Paid-in)", [800.0, "=B30", "=C30", "=D30", "=E30", "=F30"]),
        ("Retained Earnings", [300.0, "=B31+C17", "=C31+D17", "=D31+E17", "=E31+F17", "=F31+G17"]), # 前期純資産 + 当期純利益 (17行目)
        ("Total Equity", ["=B30+B31", "=C30+C31", "=D30+D31", "=E30+E31", "=F30+F31", "=G30+G31"]),
        ("Total Liabilities & Equity", ["=B29+B32", "=C29+C32", "=D29+D32", "=E29+E32", "=F29+F32", "=G29+G32"]),
        
        ("BALANCE CHECK (Tie-out)", ["=B25-B33", "=C25-C33", "=D25-D33", "=E25-E33", "=F25-F33", "=G25-G33"])
    ]
    
    # 3. キャッシュ・フロー計算書 (Cash Flow Statement)
    cf_rows = [
        ("Net Income", ["=B17", "=C17", "=D17", "=E17", "=F17", "=G17"]),
        ("Plus: D&A", ["=B12", "=C12", "=D12", "=E12", "=F12", "=G12"]),
        ("Less: Change in Receivables", ["", "=-(C22-B22)", "=-(D22-C22)", "=-(E22-D22)", "=-(F22-E22)", "=-(G22-F22)"]),
        ("Less: Change in Inventory", ["", "=-(C23-B23)", "=-(D23-C23)", "=-(E23-D23)", "=-(F23-E23)", "=-(G23-F23)"]),
        ("Plus: Change in Payables", ["", "=C27-B27", "=D27-C27", "=E27-D27", "=F27-E27", "=G27-F27"]),
        ("Operating Cash Flow (OCF)", ["=SUM(B37:B41)", "=SUM(C37:C41)", "=SUM(D37:D41)", "=SUM(E37:E41)", "=SUM(F37:F41)", "=SUM(G37:G41)"]),
        
        ("Capital Expenditures (CapEx)", [-225.6, -300.0, -320.0, -310.0, -300.0, -300.0]),
        ("Investing Cash Flow (ICF)", ["=B43", "=C43", "=D43", "=E43", "=F43", "=G43"]),
        
        ("Debt Drawdown / (Repayment)", [-324.3, 50.0, -20.0, -30.0, -40.0, -50.0]),
        ("Financing Cash Flow (FCF)", ["=B45", "=C45", "=D45", "=E45", "=F45", "=G45"]),
        
        ("Net Change in Cash", ["=B42+B44+B46", "=C42+C44+C46", "=D42+D44+D46", "=E42+E44+E46", "=F42+F44+F46", "=G42+G44+G46"]),
        ("Beginning Cash Balance", [187.6, "=B49", "=C49", "=D49", "=E49", "=F49"]),
        ("Ending Cash Balance", ["=B47+B48", "=C47+C48", "=D47+D48", "=E47+E48", "=F47+F48", "=G47+G48"])
    ]
    
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
                
                if str(val).startswith("="):
                    cell.value = val
                    cell.font = bold_data_font if is_bold else data_font
                else:
                    cell.value = val
                    cell.font = input_font if (col_idx == 2 or label in ["Capital Expenditures (CapEx)", "Debt Drawdown / (Repayment)", "Total Revenue"]) else data_font
                
                if "%" in label or "Growth" in label:
                    cell.number_format = '0.0%'
                elif label == "BALANCE CHECK (Tie-out)":
                    cell.number_format = '0.00'
                    cell.fill = highlight_fill
                else:
                    cell.number_format = '#,##0.0'
                    
                if is_bold:
                    cell.border = Border(top=thin_border_side, bottom=Side(style='double' if "Total" in label or "Balance" in label or "Income" in label else 'thin', color='1B263B'))
                    
        return start_row + len(rows)
        
    # I. ISを描画
    last_row = populate_section(is_rows, 6) # 6-17行
    
    # II. BSを描画 (動的にタイトル行を決定)
    title_row_bs = last_row + 2
    ws.cell(row=title_row_bs, column=1, value="II. BALANCE SHEET").font = section_font
    ws.merge_cells(start_row=title_row_bs, start_column=1, end_row=title_row_bs, end_column=7)
    ws.cell(row=title_row_bs, column=1).fill = section_fill
    last_row = populate_section(bs_rows, title_row_bs + 1)
    
    # III. CFを描画
    title_row_cf = last_row + 2
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
