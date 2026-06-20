import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
import os
import sys
import json
import argparse
import subprocess
from utils import normalize_ticker, find_ticker_dir, get_latest_financial_data, ExcelStyles, setup_logging

logger = setup_logging("generate_models")

def parse_args():
    parser = argparse.ArgumentParser(description="Generate generic DCF and Comps models for a given stock ticker")
    parser.add_argument("ticker", type=str, help="Subject stock ticker (e.g. 7203, 285A, MSFT)")
    parser.add_argument("--peers", type=str, help="Comma-separated list of peer tickers for Comps (e.g. 7267,7201 or MU,WDC)")
    parser.add_argument("--outdir", type=str, default="./out", help="Base output directory")
    return parser.parse_args()

def fetch_peer_data_if_missing(peer_ticker, outdir):
    """ピア企業のデータが不足している場合、fetch_yfinance.py を自動実行して補う"""
    peer_dir = find_ticker_dir(outdir, peer_ticker)
    summary_path = os.path.join(peer_dir, "market_data", "summary.json")
    if not os.path.exists(summary_path):
        logger.info(f"Peer data for {peer_ticker} is missing. Fetching using fetch_yfinance.py...")
        try:
            script_path = os.path.join(os.path.dirname(__file__), "fetch_yfinance.py")
            subprocess.run([
                sys.executable, 
                script_path, 
                peer_ticker, 
                "--skip-fundamentals", 
                "--outdir", outdir
            ], check=True)
        except Exception as e:
            logger.error(f"Failed to fetch peer {peer_ticker}: {e}")

def create_comps_model(ticker_data, peers_list, outdir):
    """類似企業比較 (Comps) シートを構築する"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Comparable Companies"
    ws.views.sheetView[0].showGridLines = True
    
    # 共通スタイルインポート
    styles = ExcelStyles()
    
    font_family = styles.font_family
    title_font = styles.title_font
    header_font = styles.header_font
    data_font = styles.data_font
    input_font = styles.input_font
    bold_data_font = styles.bold_data_font
    primary_fill = styles.primary_fill
    section_fill = styles.section_fill
    subject_fill = styles.subject_fill
    thin_border = styles.thin_border
    
    is_jpy = ticker_data["currency"] == "JPY"
    unit_str = "Bn JPY" if is_jpy else "Mn USD"
    div_factor = 1e9 if is_jpy else 1e6
    
    # タイトル
    ws.merge_cells("A1:K1")
    ws["A1"] = f"{ticker_data['name']} ({ticker_data['ticker']}) - COMPARABLE COMPANY ANALYSIS"
    ws["A1"].font = title_font
    ws["A1"].fill = primary_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 40
    
    # ヘッダー行
    headers = [
        "Company", "Ticker", "Currency", f"Market Cap\n({unit_str})", f"Enterprise Value\n({unit_str})",
        f"Revenue\n({unit_str})", "Revenue Growth\n(YoY)", f"EBITDA\n({unit_str})", "EBITDA Margin",
        "EV / Revenue", "EV / EBITDA"
    ]
    
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx)
        cell.value = header
        cell.font = header_font
        cell.fill = primary_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[3].height = 35
    
    # ピアデータの集計
    all_data = []
    # 1. ピア企業
    for peer in peers_list:
        fetch_peer_data_if_missing(peer, outdir)
        p_dir = find_ticker_dir(outdir, peer)
        try:
            p_data = get_latest_financial_data(p_dir, peer)
            all_data.append((p_data["name"], peer, p_data["currency"], p_data["market_cap"], p_data["revenue"], p_data["ebitda"]))
        except Exception as e:
            logger.warning(f"Skipping peer {peer} due to missing data: {e}")
        
    # 2. 対象企業 (最後に配置)
    all_data.append((f"{ticker_data['name']} (Subject)", ticker_data["ticker"], ticker_data["currency"], ticker_data["market_cap"], ticker_data["revenue"], ticker_data["ebitda"]))
    
    start_row = 4
    for idx, (name, tk, curr, mc, rev, ebitda) in enumerate(all_data):
        row = start_row + idx
        ws.row_dimensions[row].height = 24
        
        ws.cell(row=row, column=1, value=name).font = bold_data_font if "Subject" in name else data_font
        ws.cell(row=row, column=2, value=tk).font = input_font
        ws.cell(row=row, column=3, value=curr).font = input_font
        
        mc_val = mc / div_factor if mc else 0.0
        rev_val = rev / div_factor if rev else 0.0
        eb_val = ebitda / div_factor if ebitda else 0.0
        
        # 簡易EV計算
        ev_val = mc_val
        peer_dir = find_ticker_dir(outdir, tk)
        sum_path = os.path.join(peer_dir, "market_data", "summary.json")
        if os.path.exists(sum_path):
            with open(sum_path, "r", encoding="utf-8") as f:
                s = json.load(f)
                if "market_cap" in s and s["market_cap"]:
                    ev_info = s.get("enterprise_value") or s.get("market_cap")
                    ev_val = float(ev_info) / div_factor
                if tk == ticker_data["ticker"]:
                    ev_val = mc_val + (ticker_data["total_debt"] - ticker_data["cash"]) / div_factor
        
        ws.cell(row=row, column=4, value=mc_val).font = input_font
        ws.cell(row=row, column=5, value=ev_val).font = input_font
        ws.cell(row=row, column=6, value=rev_val).font = input_font
        
        growth_cell = ws.cell(row=row, column=7, value=0.10)
        growth_cell.font = input_font
        
        ws.cell(row=row, column=8, value=eb_val).font = input_font
        
        # ゼロ除算保護（IFERROR適用）
        margin_cell = ws.cell(row=row, column=9, value=f"=IFERROR(H{row}/F{row}, 0)")
        margin_cell.font = data_font
        margin_cell.number_format = '0.0%'
        
        ev_rev_cell = ws.cell(row=row, column=10, value=f"=IFERROR(E{row}/F{row}, \"-\")")
        ev_rev_cell.font = data_font
        ev_rev_cell.number_format = '0.00x'
        
        ev_eb_cell = ws.cell(row=row, column=11, value=f"=IFERROR(E{row}/H{row}, \"-\")")
        ev_eb_cell.font = data_font
        ev_eb_cell.number_format = '0.00x'
        
        for col in range(4, 9):
            c = ws.cell(row=row, column=col)
            if col == 7:
                c.number_format = '0.0%'
            else:
                c.number_format = '#,##0.0'
                
        for col_idx in range(1, 12):
            ws.cell(row=row, column=col_idx).border = thin_border
            if "Subject" in name:
                ws.cell(row=row, column=col_idx).fill = subject_fill
                
    # 統計サマリー
    stats = [
        ("Maximum", "MAX"),
        ("75th Percentile", "QUARTILE.INC"),
        ("Median", "MEDIAN"),
        ("25th Percentile", "QUARTILE.INC"),
        ("Minimum", "MIN")
    ]
    
    stat_start_row = start_row + len(all_data) + 1
    ws.cell(row=stat_start_row - 1, column=1, value="PEER STATISTICS").font = Font(name=font_family, size=11, bold=True, color="1B263B")
    
    for idx, (label, func) in enumerate(stats):
        row = stat_start_row + idx
        ws.row_dimensions[row].height = 24
        
        ws.cell(row=row, column=1, value=label).font = bold_data_font
        ws.cell(row=row, column=1).fill = section_fill
        
        peer_range_end = start_row + len(all_data) - 2
        
        for col in range(4, 12):
            col_letter = get_column_letter(col)
            cell = ws.cell(row=row, column=col)
            cell.font = bold_data_font
            cell.border = thin_border
            
            if func == "QUARTILE.INC":
                q_num = 3 if "75th" in label else 1
                cell.value = f"=QUARTILE.INC({col_letter}{start_row}:{col_letter}{peer_range_end}, {q_num})"
            else:
                cell.value = f"={func}({col_letter}{start_row}:{col_letter}{peer_range_end})"
                
            if col in [4, 5, 6, 8]:
                cell.number_format = '#,##0.0'
            elif col in [7, 9]:
                cell.number_format = '0.0%'
            elif col in [10, 11]:
                cell.number_format = '0.00x'
                
            if label == "Median":
                cell.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
                
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    subject_dir = find_ticker_dir(outdir, ticker_data["ticker"])
    target_path = os.path.join(subject_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, f"comps_{ticker_data['ticker']}.xlsx")
    wb.save(out_file)
    logger.info(f"Successfully generated Comps model: {out_file}")

def create_dcf_model(ticker_data, outdir):
    """ディスカウント・キャッシュ・フロー (DCF) シートを構築する"""
    wb = openpyxl.Workbook()
    
    calc_pr = CalcProperties(iterate=True, refMode='A1', iterateCount=100, iterateDelta=0.001)
    wb.properties.calcPr = calc_pr
    
    ws = wb.active
    ws.title = "DCF Valuation"
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
    currency_symbol = "¥" if is_jpy else "$"
    
    # タイトル行
    ws.merge_cells("A1:H1")
    ws["A1"] = f"{ticker_data['name']} ({ticker_data['ticker']}) - DISCOUNTED CASH FLOW VALUATION MODEL"
    ws["A1"].font = title_font
    ws["A1"].fill = primary_fill
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 40
    
    # Inputsシートを作成して前提条件を配置
    ws_inputs = wb.create_sheet(title="Inputs")
    ws_inputs.views.sheetView[0].showGridLines = True

    # タイトル行 (Inputs)
    ws_inputs.merge_cells("A1:C1")
    ws_inputs["A1"] = f"{ticker_data['name']} ({ticker_data['ticker']}) - VALUATION INPUTS"
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

    rf_rate = 0.010 if is_jpy else 0.040
    tax_rate = 0.306 if is_jpy else 0.210

    inputs_data = [
        ("Risk-Free Rate (10y Govt Bond)", rf_rate, "0.0%", f"[ASSUMPTION] 10y {'JGB' if is_jpy else 'US Treasury'} Yield"),
        ("Equity Beta (vs market)", 1.20, "0.00", "[ASSUMPTION] Peer Beta"),
        ("Equity Risk Premium", 0.060, "0.0%", "[ASSUMPTION] Market Risk Premium"),
        ("Pre-tax Cost of Debt", 0.025 if is_jpy else 0.055, "0.0%", "[ASSUMPTION] Average Cost of Debt"),
        ("Effective Tax Rate", tax_rate, "0.0%", "[ASSUMPTION] Statutory Tax Rate"),
        ("Target Debt / (Debt + Equity)", 0.20, "0.0%", "[ASSUMPTION] Target Capital Structure"),
        ("Terminal EV/EBITDA Multiple", 10.0, "0.0x", "[ASSUMPTION] Peer Trading Multiple"),
        ("Perpetual Growth Rate (Gordon Growth)", 0.005 if is_jpy else 0.020, "0.0%", "[ASSUMPTION] Long-term GDP Growth")
    ]

    for idx, (label, val, fmt, src) in enumerate(inputs_data):
        row = 4 + idx
        ws_inputs.row_dimensions[row].height = 20
        ws_inputs.cell(row=row, column=1, value=label).font = data_font
        cell_val = ws_inputs.cell(row=row, column=2, value=val)
        cell_val.font = input_font
        cell_val.number_format = fmt
        cell_val.alignment = Alignment(horizontal="right")
        ws_inputs.cell(row=row, column=3, value=src).font = data_font

        for col in range(1, 4):
            ws_inputs.cell(row=row, column=col).border = thin_border

    # Inputsシートの列幅調整
    for col in ws_inputs.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_inputs.column_dimensions[col_letter].width = max(max_len + 3, 14)

    # I. 前提条件セクション (WACC & Terminal Multiple)
    ws["A3"] = "I. VALUATION ASSUMPTIONS"
    ws["A3"].font = section_font
    ws.merge_cells("A3:C3")
    ws["A3"].fill = section_fill
    
    assumptions = [
        ("Risk-Free Rate (10y Govt Bond)", "=Inputs!B4", "0.0%"),
        ("Equity Beta (vs market)", "=Inputs!B5", "0.00"),
        ("Equity Risk Premium", "=Inputs!B6", "0.0%"),
        ("Cost of Equity (CAPM)", "=B4+B5*B6", "0.0%"),
        ("Pre-tax Cost of Debt", "=Inputs!B7", "0.0%"),
        ("Effective Tax Rate", "=Inputs!B8", "0.0%"),
        ("After-tax Cost of Debt", "=B8*(1-B9)", "0.0%"),
        ("Target Debt / (Debt + Equity)", "=Inputs!B9", "0.0%"),
        ("Target Equity / (Debt + Equity)", "=1-B11", "0.0%"),
        ("Weighted Average Cost of Capital (WACC)", "=B7*B12+B10*B11", "0.0%"),
        ("Terminal EV/EBITDA Multiple", "=Inputs!B10", "0.0x"),
        ("Perpetual Growth Rate (Gordon Growth)", "=Inputs!B11", "0.0%")
    ]
    
    for idx, (label, val, fmt) in enumerate(assumptions):
        row = 4 + idx
        ws.row_dimensions[row].height = 20
        ws.cell(row=row, column=1, value=label).font = bold_data_font if "WACC" in label else data_font
        cell_val = ws.cell(row=row, column=2, value=val)
        cell_val.font = data_font if str(val).startswith("=") else input_font
        cell_val.number_format = fmt
        cell_val.alignment = Alignment(horizontal="right")
        
        if "WACC" in label:
            ws.cell(row=row, column=1).fill = highlight_fill
            cell_val.fill = highlight_fill
            cell_val.font = Font(name=font_family, size=11, bold=True, color="047857")
            
    # II. プロジェクションセクション
    ws["A18"] = f"II. FINANCIAL PROJECTIONS (Base Case - {unit_str})"
    ws["A18"].font = section_font
    ws.merge_cells("A18:H18")
    ws["A18"].fill = section_fill
    
    proj_headers = ["Metric", "Actual (LTM)", "FY1E", "FY2E", "FY3E", "FY4E", "FY5E", "Terminal"]
    for col_idx, header in enumerate(proj_headers, 1):
        c = ws.cell(row=20, column=col_idx, value=header)
        c.font = header_font
        c.fill = primary_fill
        c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[20].height = 28
    
    rev_ltm = ticker_data["revenue"] / div_factor if ticker_data["revenue"] else 1000.0
    eb_ltm = ticker_data["ebitda"] / div_factor if ticker_data["ebitda"] else 150.0
    ebit_ltm = ticker_data["ebit"] / div_factor if ticker_data["ebit"] else 100.0
    da_ltm = ticker_data["depreciation"] / div_factor if ticker_data["depreciation"] else 50.0
    capex_ltm = ticker_data["capex"] / div_factor if ticker_data["capex"] else 80.0
    nwc_ltm = ticker_data["nwc_change"] / div_factor if ticker_data["nwc_change"] else 10.0
    
    eb_margin_ltm = eb_ltm / rev_ltm if rev_ltm else 0.15
    da_percent_ltm = da_ltm / rev_ltm if rev_ltm else 0.05
    capex_percent_ltm = capex_ltm / rev_ltm if rev_ltm else 0.08
    nwc_percent_ltm = nwc_ltm / rev_ltm if rev_ltm else 0.01
    
    rows_def = [
        ("Total Revenue", "input", [rev_ltm, "=B21*1.08", "=C21*1.06", "=D21*1.05", "=E21*1.05", "=F21*1.05"], "#,##0.0"),
        ("Revenue Growth", "calc", ["", "=(C21-B21)/B21", "=(D21-C21)/C21", "=(E21-D21)/D21", "=(F21-E21)/E21", "=(G21-F21)/F21"], "0.0%"),
        ("EBITDA", "calc", [eb_ltm, f"=C21*{eb_margin_ltm:.4f}", f"=D21*{eb_margin_ltm:.4f}", f"=E21*{eb_margin_ltm:.4f}", f"=F21*{eb_margin_ltm:.4f}", f"=G21*{eb_margin_ltm:.4f}"], "#,##0.0"),
        ("EBITDA Margin", "calc", ["=B23/B21", "=C23/C21", "=D23/D21", "=E23/E21", "=F23/F21", "=G23/G21"], "0.0%"),
        ("Depreciation & Amortization", "calc", [da_ltm, f"=C21*{da_percent_ltm:.4f}", f"=D21*{da_percent_ltm:.4f}", f"=E21*{da_percent_ltm:.4f}", f"=F21*{da_percent_ltm:.4f}", f"=G21*{da_percent_ltm:.4f}"], "#,##0.0"),
        ("EBIT (Operating Income)", "calc", ["=B23-B25", "=C23-C25", "=D23-D25", "=E23-E25", "=F23-F25", "=G23-G25"], "#,##0.0"),
        ("Taxes on EBIT", "calc", ["", "=C26*$B$9", "=D26*$B$9", "=E26*$B$9", "=F26*$B$9", "=G26*$B$9"], "#,##0.0"),
        ("NOPAT (Net Operating Profit After Tax)", "calc", ["", "=C26-C27", "=D26-D27", "=E26-E27", "=F26-F27", "=G26-G27"], "#,##0.0"),
        ("Plus: D&A", "calc", ["", "=C25", "=D25", "=E25", "=F25", "=G25"], "#,##0.0"),
        ("Less: Capital Expenditures (CapEx)", "calc", [capex_ltm, f"=C21*{capex_percent_ltm:.4f}", f"=D21*{capex_percent_ltm:.4f}", f"=E21*{capex_percent_ltm:.4f}", f"=F21*{capex_percent_ltm:.4f}", f"=G21*{capex_percent_ltm:.4f}"], "#,##0.0"),
        ("Less: Change in Net Working Capital", "calc", [nwc_ltm, f"=C21*{nwc_percent_ltm:.4f}", f"=D21*{nwc_percent_ltm:.4f}", f"=E21*{nwc_percent_ltm:.4f}", f"=F21*{nwc_percent_ltm:.4f}", f"=G21*{nwc_percent_ltm:.4f}"], "#,##0.0"),
        ("Free Cash Flow to Firm (FCFF)", "calc", ["", "=C28+C29-C30-C31", "=D28+D29-D30-D31", "=E28+E29-E30-E31", "=F28+F29-F30-F31", "=G28+G29-G30-G31"], "#,##0.0"),
        ("Discount Period", "calc", ["", 0.5, 1.5, 2.5, 3.5, 4.5], "0.0"),
        ("Discount Factor", "calc", ["", "=1/((1+$B$13)^C33)", "=1/((1+$B$13)^D33)", "=1/((1+$B$13)^E33)", "=1/((1+$B$13)^F33)", "=1/((1+$B$13)^G33)"], "0.0000"),
        ("Present Value of FCFF", "calc", ["", "=C32*C34", "=D32*D34", "=E32*E34", "=F32*F34", "=G32*G34"], "#,##0.0")
    ]
    
    for r_idx, (label, r_type, vals, fmt) in enumerate(rows_def):
        row = 21 + r_idx
        ws.row_dimensions[row].height = 22
        ws.cell(row=row, column=1, value=label).font = bold_data_font if "FCFF" in label or "Present Value" in label else data_font
        
        if "FCFF" in label or "Present Value" in label:
            for col_idx in range(1, 9):
                ws.cell(row=row, column=col_idx).border = Border(top=thin_border_side, bottom=thin_border_side)
                ws.cell(row=row, column=col_idx).fill = PatternFill(start_color="FAF5FF", end_color="FAF5FF", fill_type="solid")
                
        for c_idx, val in enumerate(vals):
            col = 2 + c_idx
            cell = ws.cell(row=row, column=col)
            cell.number_format = fmt
            cell.alignment = Alignment(horizontal="right")
            
            if str(val).startswith("="):
                cell.value = val
                cell.font = data_font
            else:
                cell.value = val
                cell.font = input_font if (r_type == "input" and col == 2) else data_font
                
    ws.cell(row=23, column=8, value="=G23*(1+$B$15)").font = data_font
    ws.cell(row=23, column=8).number_format = "#,##0.0"
    
    # III. 企業価値ブリッジ
    ws["A38"] = "III. VALUATION BRIDGE & CONCLUSION"
    ws["A38"].font = section_font
    ws.merge_cells("A38:C38")
    ws["A38"].fill = section_fill
    
    debt_val = ticker_data["total_debt"] / div_factor if ticker_data["total_debt"] else 100.0
    cash_val = ticker_data["cash"] / div_factor if ticker_data["cash"] else 50.0
    shares_outstanding_m = ticker_data["shares_outstanding"] / 1e6 if ticker_data["shares_outstanding"] else 100.0
    current_price_raw = ticker_data["current_price"] if ticker_data["current_price"] else 100.0
    
    bridge = [
        ("Cumulative PV of FCFs", "=SUM(C35:G35)", "#,##0.0"),
        ("Terminal Value (Exit Multiple Method)", "=H23*$B$14", "#,##0.0"),
        ("PV of Terminal Value", "=B40*G34", "#,##0.0"),
        ("Implied Enterprise Value (EV)", "=B39+B41", "#,##0.0"),
        ("Less: Total Debt", debt_val, "#,##0.0"),
        ("Plus: Cash & Equivalents", cash_val, "#,##0.0"),
        ("Implied Equity Value", "=B42-B43+B44", "#,##0.0"),
        ("Shares Outstanding (Millions)", shares_outstanding_m, "#,##0.0"),
        ("Implied Share Price", "=(B45/B46)*100" if is_jpy else "=B45/B46", f"{currency_symbol}#,##0.00"),
        ("Current Share Price", current_price_raw, f"{currency_symbol}#,##0.00"),
        ("Implied Premium / (Discount)", "=(B47-B48)/B48", "0.0%")
    ]
    
    for idx, (label, val, fmt) in enumerate(bridge):
        row = 39 + idx
        ws.row_dimensions[row].height = 20
        ws.cell(row=row, column=1, value=label).font = bold_data_font if "Price" in label or "EV" in label else data_font
        cell_val = ws.cell(row=row, column=2, value=val)
        cell_val.font = data_font if str(val).startswith("=") else input_font
        cell_val.number_format = fmt
        cell_val.alignment = Alignment(horizontal="right")
        
        if "Share Price" in label:
            ws.cell(row=row, column=1).fill = highlight_fill
            cell_val.fill = highlight_fill
            cell_val.font = Font(name=font_family, size=11, bold=True, color="047857")
            
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
        
    subject_dir = find_ticker_dir(outdir, ticker_data["ticker"])
    target_path = os.path.join(subject_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, f"dcf_{ticker_data['ticker']}.xlsx")
    wb.save(out_file)
    logger.info(f"Successfully generated DCF model: {out_file}")

def main():
    args = parse_args()
    ticker_str = normalize_ticker(args.ticker)
    
    logger.info(f"Running generic financial modeling for {ticker_str}...")
    ticker_dir = find_ticker_dir(args.outdir, ticker_str)
    
    if not os.path.exists(ticker_dir):
        logger.error(f"Directory {ticker_dir} does not exist. Please run fetch_yfinance.py first.")
        sys.exit(1)
        
    try:
        ticker_data = get_latest_financial_data(ticker_dir, ticker_str)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
        
    peers = []
    if args.peers:
        peers = [normalize_ticker(p) for p in args.peers.split(",") if p.strip()]
        
    create_dcf_model(ticker_data, args.outdir)
    
    if peers:
        create_comps_model(ticker_data, peers, args.outdir)
    else:
        logger.info("Skipped Comps model generation (no peers specified).")

if __name__ == "__main__":
    main()
