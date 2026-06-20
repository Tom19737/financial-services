import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.properties import CalcProperties
import os
import sys
import json
import argparse
import subprocess

# pandas はデータのパースに必須
try:
    import pandas as pd
except ImportError:
    print("Error: pandas is required. Please install it in the virtual environment.", file=sys.stderr)
    sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description="Generate generic DCF and Comps models for a given stock ticker")
    parser.add_argument("ticker", type=str, help="Subject stock ticker (e.g. 7203, 285A, MSFT)")
    parser.add_argument("--peers", type=str, help="Comma-separated list of peer tickers for Comps (e.g. 7267,7201 or MU,WDC)")
    parser.add_argument("--outdir", type=str, default="./out", help="Base output directory")
    return parser.parse_args()

def normalize_ticker(ticker_str):
    ticker_str = ticker_str.strip()
    if len(ticker_str) == 4 and ticker_str[0].isdigit() and ticker_str.isalnum():
        return f"{ticker_str}.T"
    return ticker_str

def find_ticker_dir(base_dir, ticker_str):
    """base_dir配下から、ticker_strで始まるティッカーフォルダを動的に探索する"""
    import glob
    pattern = os.path.join(base_dir, f"{ticker_str}*")
    matches = glob.glob(pattern)
    dirs = [m for m in matches if os.path.isdir(m)]
    dirs.sort(key=len, reverse=True)
    if dirs:
        return dirs[0]
    return os.path.join(base_dir, ticker_str)

def fetch_peer_data_if_missing(peer_ticker, outdir):
    """ピア企業のデータが不足している場合、fetch_yfinance.py を自動実行して補う"""
    peer_dir = find_ticker_dir(outdir, peer_ticker)
    summary_path = os.path.join(peer_dir, "market_data", "summary.json")
    if not os.path.exists(summary_path):
        print(f"Peer data for {peer_ticker} is missing. Fetching using fetch_yfinance.py...")
        try:
            # fetch_yfinance.py の場所を特定
            script_path = os.path.join(os.path.dirname(__file__), "fetch_yfinance.py")
            subprocess.run([
                sys.executable, 
                script_path, 
                peer_ticker, 
                "--skip-fundamentals", # ピアはComps用の基本情報のみで良いため財務三表はスキップ
                "--outdir", outdir
            ], check=True)
        except Exception as e:
            print(f"Warning: Failed to fetch peer {peer_ticker}: {e}", file=sys.stderr)

def get_latest_financial_data(ticker_dir, ticker_str):
    """CSVおよびJSONから実績データを読み込み、辞書として返す"""
    data = {
        "ticker": ticker_str,
        "name": ticker_str,
        "currency": "JPY" if ticker_str.endswith(".T") else "USD",
        "current_price": 0.0,
        "shares_outstanding": 0.0,
        "market_cap": 0.0,
        "revenue": 0.0,
        "ebitda": 0.0,
        "ebit": 0.0,
        "depreciation": 0.0,
        "tax_provision": 0.0,
        "capex": 0.0,
        "nwc_change": 0.0,
        "total_debt": 0.0,
        "cash": 0.0
    }
    
    # 1. summary.json の読み込み
    summary_path = os.path.join(ticker_dir, "market_data", "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
            data["name"] = summary.get("long_name") or summary.get("ticker")
            data["currency"] = summary.get("currency") or data["currency"]
            data["current_price"] = summary.get("current_price") or 0.0
            data["shares_outstanding"] = summary.get("shares_outstanding") or 0.0
            data["market_cap"] = summary.get("market_cap") or 0.0
            data["ebitda"] = summary.get("ebitda") or 0.0
            
            # 日本株の100倍バグ補正
            # キオクシア(285A)などの新規上場株で、株価・時価総額が100倍で取得されるバグに対応
            if ticker_str.endswith(".T") and data["current_price"] > 50000:
                data["current_price"] /= 100
                if data["market_cap"] > 1e13: # 10兆円以上になっている場合
                    data["market_cap"] /= 100
                    
    # ヘルパー関数: 安全に値を取得する
    def get_val(df, index_names, col):
        for name in index_names:
            if name in df.index:
                val = df.loc[name, col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if pd.notna(val):
                    return float(val)
        return 0.0

    # 有効なデータが入っている最初の列を探すヘルパー
    def get_latest_actual_col(df, index_names):
        for name in index_names:
            if name in df.index:
                for col in df.columns:
                    val = df.loc[name, col]
                    if isinstance(val, pd.Series):
                        val = val.iloc[0]
                    if pd.notna(val) and val != 0:
                        return col
        return df.columns[0]

    # 2. annual_income_stmt.csv
    inc_path = os.path.join(ticker_dir, "market_data", "annual_income_stmt.csv")
    if os.path.exists(inc_path):
        df = pd.read_csv(inc_path, index_col=0)
        latest_col = get_latest_actual_col(df, ["Total Revenue", "Operating Revenue", "Revenue"])
        
        data["revenue"] = get_val(df, ["Total Revenue", "Operating Revenue", "Revenue"], latest_col)
        # EBITDAが取得できない場合は営業利益+減価償却で補完
        ebitda_val = get_val(df, ["EBITDA", "Normalized EBITDA"], latest_col)
        ebit_val = get_val(df, ["EBIT", "Operating Income", "Total Operating Income As Reported"], latest_col)
        dep_val = get_val(df, ["Reconciled Depreciation", "Depreciation And Amortization", "Depreciation"], latest_col)
        
        data["ebit"] = ebit_val
        data["depreciation"] = dep_val
        data["ebitda"] = ebitda_val if ebitda_val != 0 else (ebit_val + dep_val)
        data["tax_provision"] = get_val(df, ["Tax Provision", "Income Tax Expense"], latest_col)
        
    # 3. annual_balance_sheet.csv
    bs_path = os.path.join(ticker_dir, "market_data", "annual_balance_sheet.csv")
    if os.path.exists(bs_path):
        df = pd.read_csv(bs_path, index_col=0)
        latest_col = get_latest_actual_col(df, ["Total Assets"])
        data["total_debt"] = get_val(df, ["Total Debt", "Long Term Debt", "Current Debt"], latest_col)
        data["cash"] = get_val(df, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash"], latest_col)
        
    # 4. annual_cashflow.csv
    cf_path = os.path.join(ticker_dir, "market_data", "annual_cashflow.csv")
    if os.path.exists(cf_path):
        df = pd.read_csv(cf_path, index_col=0)
        latest_col = get_latest_actual_col(df, ["Operating Cash Flow", "Net Income From Continuing Operations"])
        # CapExは通常マイナス値で入るため、絶対値にする
        data["capex"] = abs(get_val(df, ["Capital Expenditure", "Purchase Of PPE", "Net PPE Purchase And Sale"], latest_col))
        data["nwc_change"] = get_val(df, ["Change In Working Capital", "Changes In Cash"], latest_col)
        
    return data

def create_comps_model(ticker_data, peers_list, outdir):
    """類似企業比較 (Comps) シートを構築する"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Comparable Companies"
    ws.views.sheetView[0].showGridLines = True
    
    font_family = "Outfit"
    title_font = Font(name=font_family, size=16, bold=True, color="FFFFFF")
    header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    section_font = Font(name=font_family, size=12, bold=True, color="0D1B2A")
    data_font = Font(name=font_family, size=11, color="000000")
    input_font = Font(name=font_family, size=11, color="003366")
    bold_data_font = Font(name=font_family, size=11, bold=True, color="000000")
    
    primary_fill = PatternFill(start_color="1B263B", end_color="1B263B", fill_type="solid")
    section_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    subject_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid") # Highlight Yellow
    
    thin_border_side = Side(style='thin', color='CBD5E1')
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    
    # 通貨マークの設定
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
        p_data = get_latest_financial_data(p_dir, peer)
        all_data.append((p_data["name"], peer, p_data["currency"], p_data["market_cap"], p_data["revenue"], p_data["ebitda"]))
        
    # 2. 対象企業 (最後に配置)
    all_data.append((f"{ticker_data['name']} (Subject)", ticker_data["ticker"], ticker_data["currency"], ticker_data["market_cap"], ticker_data["revenue"], ticker_data["ebitda"]))
    
    start_row = 4
    for idx, (name, tk, curr, mc, rev, ebitda) in enumerate(all_data):
        row = start_row + idx
        ws.row_dimensions[row].height = 24
        
        # 会社基本情報
        ws.cell(row=row, column=1, value=name).font = bold_data_font if "Subject" in name else data_font
        ws.cell(row=row, column=2, value=tk).font = input_font
        ws.cell(row=row, column=3, value=curr).font = input_font
        
        # 数値（十億円または百万ドル単位に変換して入力）
        mc_val = mc / div_factor if mc else 0.0
        rev_val = rev / div_factor if rev else 0.0
        eb_val = ebitda / div_factor if ebitda else 0.0
        
        # 簡易EV計算
        ev_val = mc_val # Default fallback
        peer_dir = find_ticker_dir(outdir, tk)
        sum_path = os.path.join(peer_dir, "market_data", "summary.json")
        if os.path.exists(sum_path):
            with open(sum_path, "r", encoding="utf-8") as f:
                s = json.load(f)
                if "market_cap" in s and s["market_cap"]:
                    # EV = Market Cap + Debt - Cash (yfinance info から enterpriseValue を取得してあれば使う)
                    ev_info = s.get("enterprise_value") or s.get("market_cap")
                    ev_val = float(ev_info) / div_factor
                if tk == ticker_data["ticker"]:
                    ev_val = mc_val + (ticker_data["total_debt"] - ticker_data["cash"]) / div_factor
        
        ws.cell(row=row, column=4, value=mc_val).font = input_font
        ws.cell(row=row, column=5, value=ev_val).font = input_font
        ws.cell(row=row, column=6, value=rev_val).font = input_font
        
        # 成長率（実績は仮で入力）
        growth_cell = ws.cell(row=row, column=7, value=0.10)
        growth_cell.font = input_font
        
        ws.cell(row=row, column=8, value=eb_val).font = input_font
        
        # EBITDA Margin = EBITDA / Revenue
        margin_cell = ws.cell(row=row, column=9, value=f"=H{row}/F{row}")
        margin_cell.font = data_font
        margin_cell.number_format = '0.0%'
        
        # EV / Revenue
        ev_rev_cell = ws.cell(row=row, column=10, value=f"=E{row}/F{row}")
        ev_rev_cell.font = data_font
        ev_rev_cell.number_format = '0.00x'
        
        # EV / EBITDA
        ev_eb_cell = ws.cell(row=row, column=11, value=f"=E{row}/H{row}")
        ev_eb_cell.font = data_font
        ev_eb_cell.number_format = '0.00x'
        
        # 書式適用
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
        
        # 統計範囲 (Subjectは統計から除外するため、最後から2番目の行まで)
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
                
            # フォーマット
            if col in [4, 5, 6, 8]:
                cell.number_format = '#,##0.0'
            elif col in [7, 9]:
                cell.number_format = '0.0%'
            elif col in [10, 11]:
                cell.number_format = '0.00x'
                
            if label == "Median":
                cell.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid") # Light Green
                
    # 列幅調整
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    subject_dir = find_ticker_dir(outdir, ticker_data["ticker"])
    target_path = os.path.join(subject_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, f"comps_{ticker_data['ticker']}.xlsx")
    wb.save(out_file)
    print(f"Comps model saved to {out_file}")

def create_dcf_model(ticker_data, outdir):
    """ディスカウント・キャッシュ・フロー (DCF) シートを構築する"""
    wb = openpyxl.Workbook()
    
    # 反復計算の有効化
    calc_pr = CalcProperties(iterate=True, refMode='A1', iterateCount=100, iterateDelta=0.001)
    wb.properties.calcPr = calc_pr
    
    ws = wb.active
    ws.title = "DCF Valuation"
    ws.views.sheetView[0].showGridLines = True
    
    font_family = "Outfit"
    title_font = Font(name=font_family, size=16, bold=True, color="FFFFFF")
    header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
    section_font = Font(name=font_family, size=12, bold=True, color="1B263B")
    data_font = Font(name=font_family, size=11, color="000000")
    input_font = Font(name=font_family, size=11, color="003366")
    bold_data_font = Font(name=font_family, size=11, bold=True, color="000000")
    
    primary_fill = PatternFill(start_color="1B263B", end_color="1B263B", fill_type="solid")
    section_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    highlight_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    
    thin_border_side = Side(style='thin', color='E2E8F0')
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    
    # 通貨判定
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
    
    # I. 前提条件セクション (WACC & Terminal Multiple)
    ws["A3"] = "I. VALUATION ASSUMPTIONS"
    ws["A3"].font = section_font
    ws.merge_cells("A3:C3")
    ws["A3"].fill = section_fill
    
    # 国別デフォルト値
    rf_rate = 0.010 if is_jpy else 0.040
    tax_rate = 0.306 if is_jpy else 0.210
    
    assumptions = [
        ("Risk-Free Rate (10y Govt Bond)", rf_rate, "0.0%"),
        ("Equity Beta (vs market)", 1.20, "0.00"),
        ("Equity Risk Premium", 0.060, "0.0%"),
        ("Cost of Equity (CAPM)", "=B4+B5*B6", "0.0%"),
        ("Pre-tax Cost of Debt", 0.025 if is_jpy else 0.055, "0.0%"),
        ("Effective Tax Rate", tax_rate, "0.0%"),
        ("After-tax Cost of Debt", "=B8*(1-B9)", "0.0%"),
        ("Target Debt / (Debt + Equity)", 0.20, "0.0%"),
        ("Target Equity / (Debt + Equity)", "=1-B11", "0.0%"),
        ("Weighted Average Cost of Capital (WACC)", "=B7*B12+B10*B11", "0.0%"),
        ("Terminal EV/EBITDA Multiple", 10.0, "0.0x"),
        ("Perpetual Growth Rate (Gordon Growth)", 0.005 if is_jpy else 0.020, "0.0%")
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
    
    # 財務データの単位変換
    rev_ltm = ticker_data["revenue"] / div_factor if ticker_data["revenue"] else 1000.0
    eb_ltm = ticker_data["ebitda"] / div_factor if ticker_data["ebitda"] else 150.0
    ebit_ltm = ticker_data["ebit"] / div_factor if ticker_data["ebit"] else 100.0
    da_ltm = ticker_data["depreciation"] / div_factor if ticker_data["depreciation"] else 50.0
    capex_ltm = ticker_data["capex"] / div_factor if ticker_data["capex"] else 80.0
    nwc_ltm = ticker_data["nwc_change"] / div_factor if ticker_data["nwc_change"] else 10.0
    
    # 比率の算出
    eb_margin_ltm = eb_ltm / rev_ltm if rev_ltm else 0.15
    da_percent_ltm = da_ltm / rev_ltm if rev_ltm else 0.05
    capex_percent_ltm = capex_ltm / rev_ltm if rev_ltm else 0.08
    nwc_percent_ltm = nwc_ltm / rev_ltm if rev_ltm else 0.01
    
    # プロジェクション行の定義
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
    
    # プロジェクションの記入
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
                
    # Terminal EBITDA の計算
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
            
    # 列幅調整
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
        
    subject_dir = find_ticker_dir(outdir, ticker_data["ticker"])
    target_path = os.path.join(subject_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, f"dcf_{ticker_data['ticker']}.xlsx")
    wb.save(out_file)
    print(f"DCF model saved to {out_file}")

def main():
    args = parse_args()
    ticker_str = normalize_ticker(args.ticker)
    
    print(f"Running generic financial modeling for {ticker_str}...")
    ticker_dir = find_ticker_dir(args.outdir, ticker_str)
    
    if not os.path.exists(ticker_dir):
        print(f"Error: Directory {ticker_dir} does not exist. Please run fetch_yfinance.py first.", file=sys.stderr)
        sys.exit(1)
        
    ticker_data = get_latest_financial_data(ticker_dir, ticker_str)
    
    # ピア企業リストのパース
    peers = []
    if args.peers:
        peers = [normalize_ticker(p) for p in args.peers.split(",") if p.strip()]
        
    # DCFモデル生成
    create_dcf_model(ticker_data, args.outdir)
    
    # Compsモデル生成
    if peers:
        create_comps_model(ticker_data, peers, args.outdir)
    else:
        print("Skipped Comps model generation (no peers specified).")

if __name__ == "__main__":
    main()
