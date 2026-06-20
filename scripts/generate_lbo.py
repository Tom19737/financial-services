import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import os
import sys
import argparse
from utils import find_ticker_dir, get_latest_financial_data, ExcelStyles, setup_logging

logger = setup_logging("generate_lbo")

def build_lbo_model(ticker_data, ticker_dir):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "LBO Valuation"
    ws.views.sheetView[0].showGridLines = True
    
    # 共通スタイルインポート
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
    
    # 実績値
    mc_val = ticker_data["market_cap"] / div_factor if ticker_data["market_cap"] else 593.0
    debt_val = ticker_data["total_debt"] / div_factor if ticker_data["total_debt"] else 439.5
    cash_val = ticker_data["cash"] / div_factor if ticker_data["cash"] else 167.9
    eb_val = ticker_data["ebitda"] / div_factor if ticker_data["ebitda"] else 768.3
    da_val = ticker_data["depreciation"] / div_factor if ticker_data["depreciation"] else eb_val * 0.4
    
    # タイトル
    ws.merge_cells("A1:H1")
    ws["A1"] = f"{ticker_data['name']} ({ticker_data['ticker']}) - LEVERAGED BUYOUT (LBO) VALUATION MODEL"
    ws["A1"].font = title_font
    ws["A1"].fill = primary_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 40
    
    # I. 取引前提 (Transaction Assumptions)
    ws["A3"] = "I. TRANSACTION ASSUMPTIONS"
    ws["A3"].font = section_font
    ws.merge_cells("A3:C3")
    ws["A3"].fill = section_fill
    
    tx_assumptions = [
        ("Subject Equity Value (Market Cap)", mc_val, "#,##0.0"),
        ("Acquisition Premium", 0.30, "0.0%"),
        ("Offer Equity Value", "=B4*(1+B5)", "#,##0.0"),
        ("Existing Net Debt (to be refinanced)", debt_val - cash_val, "#,##0.0"),
        ("Transaction Fees & Expenses", 15.0, "#,##0.0"),
        ("Total Enterprise Value (TEV)", "=B6+B7+B8", "#,##0.0"),
        ("LBO Debt Financing (% of TEV)", 0.60, "0.0%"),
        ("Senior Debt LTM EBITDA Multiple", 4.0, "0.0x"),
        ("Required Sponsor Equity", "=B9*(1-B10)", "#,##0.0")
    ]
    
    for idx, (label, val, fmt) in enumerate(tx_assumptions):
        row = 4 + idx
        ws.row_dimensions[row].height = 20
        ws.cell(row=row, column=1, value=label).font = bold_data_font if "Equity" in label or "TEV" in label else data_font
        cell_val = ws.cell(row=row, column=2, value=val)
        cell_val.font = data_font if str(val).startswith("=") else input_font
        cell_val.number_format = fmt
        cell_val.alignment = Alignment(horizontal="right")
        
    # II. 資金調達構成 (Sources & Uses)
    ws["A15"] = "II. SOURCES & USES OF FUNDS"
    ws["A15"].font = section_font
    ws.merge_cells("A15:G15")
    ws["A15"].fill = section_fill
    
    ws["A17"] = "Sources of Funds"
    ws["A17"].font = bold_data_font
    ws["B17"] = "Amount"
    ws["B17"].font = bold_data_font
    ws["C17"] = "% Share"
    ws["C17"].font = bold_data_font
    
    ws["A18"] = "Senior Bank Debt (4.0x EBITDA)"
    ws["B18"] = f"=B11*{eb_val}"
    ws["C18"] = "=B18/$B$21"
    
    ws["A19"] = "Mezzanine Financing"
    ws["B19"] = "=B9*B10-B18"
    ws["C19"] = "=B19/$B$21"
    
    ws["A20"] = "Sponsor Equity Contribution"
    ws["B20"] = "=B12"
    ws["C20"] = "=B20/$B$21"
    
    ws["A21"] = "Total Sources"
    ws["B21"] = "=SUM(B18:B20)"
    ws["C21"] = "=SUM(C18:C20)"
    
    ws["E17"] = "Uses of Funds"
    ws["E17"].font = bold_data_font
    ws["F17"] = "Amount"
    ws["F17"].font = bold_data_font
    ws["G17"] = "% Share"
    ws["G17"].font = bold_data_font
    
    ws["E18"] = "Purchase Subject Equity"
    ws["F18"] = "=B6"
    ws["G18"] = "=F18/$F$21"
    
    ws["E19"] = "Refinance Existing Debt"
    ws["F19"] = "=B7"
    ws["G19"] = "=F19/$F$21"
    
    ws["E20"] = "Transaction Fees & Expenses"
    ws["F20"] = "=B8"
    ws["G20"] = "=F20/$F$21"
    
    ws["E21"] = "Total Uses"
    ws["F21"] = "=SUM(F18:F20)"
    ws["G21"] = "=SUM(G18:G20)"
    
    # 書式設定
    for r in range(18, 22):
        for c in [2, 3, 6, 7]:
            cell = ws.cell(row=r, column=c)
            cell.alignment = Alignment(horizontal="right")
            if c in [3, 7]:
                cell.number_format = '0.0%'
            else:
                cell.number_format = '#,##0.0'
            if r == 21:
                cell.font = bold_data_font
                cell.border = Border(top=thin_border_side, bottom=Side(style='double', color='1B263B'))
                
    # III. キャッシュ・フローと債務返済シミュレーション (5年)
    ws["A24"] = f"III. CASH FLOW & DEBT PAYDOWN ({unit_str})"
    ws["A24"].font = section_font
    ws.merge_cells("A24:G24")
    ws["A24"].fill = section_fill
    
    proj_headers = ["Metric", "FY25E", "FY26E", "FY27E", "FY28E", "FY29E"]
    for col_idx, header in enumerate(proj_headers, 1):
        c = ws.cell(row=26, column=col_idx, value=header)
        c.font = header_font
        c.fill = primary_fill
        c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[26].height = 24
    
    # M-5修正: da (ウォルラス演算子) を単純な変数 da_val に置換
    cf_data = [
        ("EBITDA", [eb_val, "=B27*1.08", "=C27*1.06", "=D27*1.05", "=E27*1.05"]),
        ("Less: Depreciation & Amortization", [da_val, "=B28*1.05", "=C28*1.05", "=D28*1.04", "=E28*1.04"]),
        ("EBIT", ["=B27-B28", "=C27-C28", "=D27-D28", "=E27-E28", "=F27-F28"]),
        ("Less: Interest Expense (Senior + Mezz)", ["=B18*0.06+B19*0.10", "=C18*0.06+C19*0.10", "=D18*0.06+D19*0.10", "=E18*0.06+E19*0.10", "=F18*0.06+F19*0.10"]),
        ("Pretax Income", ["=B29-B30", "=C29-C30", "=D29-D30", "=E29-E30", "=F29-F30"]),
        ("Less: Taxes (30.6%)", ["=B31*0.306", "=C31*0.306", "=D31*0.306", "=E31*0.306", "=F31*0.306"]),
        ("Net Income", ["=B31-B32", "=C31-C32", "=D31-D32", "=E31-E32", "=F31-F32"]),
        ("Plus: D&A", ["=B28", "=C28", "=D28", "=E28", "=F28"]),
        ("Less: CapEx", [-150.0, -160.0, -170.0, -170.0, -180.0]),
        ("Less: Change in Working Capital", [-10.0, -12.0, -15.0, -15.0, -15.0]),
        ("Free Cash Flow (to pay down debt)", ["=B33+B34+B35+B36", "=C33+C34+C35+C36", "=D33+D34+D35+D36", "=E33+E34+E35+E36", "=F33+F34+F35+F36"]),
        
        ("Senior Debt Balance - Beginning", ["=B18", "=B40", "=C40", "=D40", "=E40"]),
        ("Less: Debt Repayment (FCF Sweep)", ["=MIN(B38, B39)", "=MIN(C38, C39)", "=MIN(D38, D39)", "=MIN(E38, E39)", "=MIN(F38, F39)"]),
        ("Senior Debt Balance - Ending", ["=B39-B40", "=C39-C40", "=D39-D40", "=E39-E40", "=F39-F40"])
    ]
    
    for idx, (label, vals) in enumerate(cf_data):
        row = 27 + idx
        ws.row_dimensions[row].height = 20
        ws.cell(row=row, column=1, value=label).font = bold_data_font if "Balance" in label or "Free Cash Flow" in label else data_font
        for col_idx, val in enumerate(vals, 2):
            cell = ws.cell(row=row, column=col_idx)
            cell.alignment = Alignment(horizontal="right")
            cell.value = val
            cell.number_format = '#,##0.0'
            if "Balance" in label or "Free Cash Flow" in label:
                cell.fill = section_fill
                
    # IV. リターン分析 (Returns Analysis)
    ws["A43"] = "IV. SPONSOR INVESTMENT RETURNS (Exit in 5 Years)"
    ws["A43"].font = section_font
    ws.merge_cells("A43:G43")
    ws["A43"].fill = section_fill
    
    ws["A45"] = "Exit EV/EBITDA Multiple"
    ws["B45"] = "Exit EV"
    ws["C45"] = "Less: Net Debt"
    ws["D45"] = "Exit Equity Value"
    ws["E45"] = "Sponsor Return (MoIC)"
    ws["F45"] = "Sponsor IRR"
    
    for col in range(1, 7):
        ws.cell(row=45, column=col).font = bold_data_font
        
    exit_multiples = [8.0, 10.0, 12.0]
    for idx, mult in enumerate(exit_multiples):
        row = 46 + idx
        ws.row_dimensions[row].height = 22
        
        ws.cell(row=row, column=1, value=mult).number_format = '0.0x'
        ws.cell(row=row, column=1).font = input_font
        
        # Exit EV = Exit Multiple * FY29 EBITDA (F27)
        ws.cell(row=row, column=2, value=f"=A{row}*F27").number_format = '#,##0.0'
        # Less: Net Debt = Ending Senior Debt (F41) + Mezzanine (B19)
        ws.cell(row=row, column=3, value=f"=F41+$B$19").number_format = '#,##0.0'
        # Exit Equity Value = EV - Net Debt
        ws.cell(row=row, column=4, value=f"=B{row}-C{row}").number_format = '#,##0.0'
        # MoIC = Exit Equity Value / Initial Sponsor Equity (B20)
        ws.cell(row=row, column=5, value=f"=D{row}/$B$20").number_format = '0.00x'
        # IRR = (MoIC)^(1/5) - 1
        ws.cell(row=row, column=6, value=f"=(E{row})^(1/5)-1").number_format = '0.0%'
        
        # ベースケース（10倍）をハイライト
        if mult == 10.0:
            for col in range(1, 7):
                ws.cell(row=row, column=col).fill = highlight_fill
                ws.cell(row=row, column=col).font = bold_data_font
                
        for col in range(1, 7):
            ws.cell(row=row, column=col).border = thin_border
            
    # 列幅調整
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
        
    target_path = os.path.join(ticker_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, f"lbo_{ticker_data['ticker']}.xlsx")
    wb.save(out_file)
    logger.info(f"Successfully generated LBO model: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Generate LBO valuation model")
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
        
    build_lbo_model(ticker_data, ticker_dir)

if __name__ == "__main__":
    main()
