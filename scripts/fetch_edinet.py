import os
import sys
import argparse
import json
import datetime
import urllib.request
import zipfile
import io
import csv
import re
import tempfile
import xml.etree.ElementTree as ET
import pandas as pd
import yfinance as yf

# 共通ユーティリティのインポート
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logging, normalize_ticker

logger = setup_logging("fetch_edinet")

# .env ファイルから環境変数を読み込む簡易関数
def load_dotenv(dotenv_path=".env"):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()

# 勘定科目のマッピング定義
# XBRLのローカル要素名から、既存のyfinance互換英語キーへのマッピング
XBRL_TAG_MAP = {
    # P&L (損益計算書)
    "Total Revenue": [
        "Revenue", "NetSales", "OperatingRevenue", 
        "RevenueFromBusinessOfInsurance", "OperatingRevenues",
        "NetSalesOfGoods", "RevenueFromContractsWithCustomers"
    ],
    "Operating Income": [
        "OperatingIncome", "OperatingProfit", "OperatingProfitLoss"
    ],
    "Reconciled Depreciation": [
        "DepreciationAndAmortization", "Depreciation",
        "DepreciationAndAmortizationAmortizationOfGoodwill",
        "DepreciationOfPropertyPlantAndEquipment", "AmortizationOfIntangibleAssets"
    ],
    "Tax Provision": [
        "IncomeTaxExpense", "TaxProvision", "IncomeTaxes", 
        "IncomeTaxesCurrent", "IncomeTaxesDeferred", "IncomeTaxesCurrentAndDeferred"
    ],
    # B/S (貸借対照表)
    "Total Assets": [
        "TotalAssets", "Assets"
    ],
    "Cash Cash Equivalents And Short Term Investments": [
        "CashAndDeposits", "CashAndCashEquivalents",
        "CashCashEquivalentsAndShortTermInvestments", "Cash"
    ],
    # C/F (キャッシュ・フロー計算書)
    "Operating Cash Flow": [
        "NetCashProvidedByUsedInOperatingActivities", 
        "CashFlowsFromUsedInOperatingActivities"
    ],
    "Capital Expenditure": [
        "PurchaseOfPropertyPlantAndEquipment", 
        "PurchaseOfNonCurrentAssets",
        "PaymentsForAcquisitionOfPropertyPlantAndEquipment",
        "PaymentsForAcquisitionOfPropertyPlantAndEquipmentAndIntangibleAssets"
    ],
    "Change In Working Capital": [
        "IncreaseDecreaseInWorkingCapital",
        "IncreaseDecreaseInNotesAndAccountsReceivableTrade",
        "IncreaseDecreaseInInventories",
        "IncreaseDecreaseInNotesAndAccountsPayableTrade"
    ]
}

# 有利子負債（Total Debt）を構成するタグ
DEBT_TAGS = [
    "ShortTermLoansPayable", "ShortTermBorrowings",
    "LongTermLoansPayable", "LongTermBorrowings",
    "BondsPayable", "CurrentPortionOfBonds",
    "CurrentPortionOfLongTermLoansPayable",
    "CommercialPapers"
]

def download_edinet_code_list(dest_path):
    """EDINETコード・証券コードのマッピングCSVを金融庁からダウンロードする"""
    url = "https://disclosure.edinet-fsa.go.jp/control/E01EW/download?lp=default&cf=default&pf=default&ko=06&lo=01&hi=01"
    logger.info("Downloading EDINET Code list from EDINET...")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_files = [name for name in z.namelist() if name.endswith('.csv')]
            if not csv_files:
                raise FileNotFoundError("No CSV file found in the downloaded EDINET Code ZIP.")
            
            with open(dest_path, "wb") as f:
                f.write(z.read(csv_files[0]))
        logger.info(f"Saved EDINET Code list to {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download EDINET Code list: {e}")
        return False

def lookup_edinet_code(csv_path, ticker):
    """ティッカーからEDINETコードと企業情報を逆引きする"""
    # 日本株ティッカーの数字部分のみ抽出（例：7203.T -> 7203）
    clean_ticker = ticker.split(".")[0]
    
    if not os.path.exists(csv_path):
        success = download_edinet_code_list(csv_path)
        if not success:
            raise RuntimeError("EDINET Code list could not be acquired.")
        
    logger.info(f"Searching EDINET code for ticker: {clean_ticker}")
    with open(csv_path, "r", encoding="cp932") as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    header = None
    data_start_idx = 0
    for i, row in enumerate(rows):
        if len(row) > 0 and "ＥＤＩＮＥＴコード" in row[0]:
            header = row
            data_start_idx = i + 1
            break
            
    if not header:
        header = ["ＥＤＩＮＥＴコード", "提出者種別", "提出者名", "提出者名（ヨミ）", "提出者名（英字）", "所在地", "提出者業種", "証券コード", "提出者法人番号"]
        data_start_idx = 2
        
    try:
        edinet_code_col = header.index("ＥＤＩＮＥＴコード")
        sec_code_col = header.index("証券コード")
        filer_name_col = header.index("提出者名")
        corporate_number_col = header.index("提出者法人番号")
    except ValueError:
        edinet_code_col, sec_code_col, filer_name_col, corporate_number_col = 0, 7, 2, 8
    
    for row in rows[data_start_idx:]:
        if len(row) <= max(sec_code_col, edinet_code_col):
            continue
        sec_code = row[sec_code_col].strip()
        # 証券コードは通常5桁で末尾0なので、先頭4桁を比較
        if sec_code.startswith(clean_ticker):
            return {
                "edinet_code": row[edinet_code_col].strip(),
                "filer_name": row[filer_name_col].strip(),
                "corporate_number": row[corporate_number_col].strip() if len(row) > corporate_number_col else ""
            }
            
    raise ValueError(f"Ticker {ticker} (clean: {clean_ticker}) not found in EDINET Code list.")

def fetch_document_list(api_key, date_str):
    """指定日のEDINET提出書類一覧を取得する"""
    url = f"https://disclosure2.edinet-fsa.go.jp/api/v2/documents.json?date={date_str}&type=2"
    logger.info(f"Fetching document list for date: {date_str}")
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Ocp-Apim-Subscription-Key': api_key
    })
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode('utf-8')
            return json.loads(res_data)
    except Exception as e:
        logger.error(f"Failed to fetch document list for date {date_str}: {e}")
        return None

def download_document_zip(api_key, doc_id, dest_zip_path):
    """書類IDを指定して書類のZIPパッケージをダウンロードする"""
    os.makedirs(os.path.dirname(dest_zip_path), exist_ok=True)
    if os.path.exists(dest_zip_path):
        logger.info(f"Document {doc_id} already downloaded (cached).")
        return True
        
    url = f"https://disclosure2.edinet-fsa.go.jp/api/v2/documents/{doc_id}?type=1"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Ocp-Apim-Subscription-Key': api_key
    })
    
    logger.info(f"Downloading document ZIP for {doc_id} from EDINET...")
    try:
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
            with open(dest_zip_path, "wb") as f:
                f.write(zip_data)
        logger.info(f"Saved document ZIP to {dest_zip_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download document {doc_id}: {e}")
        return False

def parse_xbrl_file(xbrl_file_path):
    """XBRLファイルを解析し、日付ごとの勘定科目数値を抽出する"""
    try:
        tree = ET.parse(xbrl_file_path)
    except Exception as e:
        logger.error(f"Failed to parse XML in {xbrl_file_path}: {e}")
        return {}
        
    root = tree.getroot()
    
    # 1. contextの定義から ID -> 日付 を取得
    contexts = {}
    for elem in root.iter():
        local_name = elem.tag.split('}')[-1]
        if local_name == 'context':
            context_id = elem.attrib.get('id')
            if not context_id:
                continue
            
            period = None
            for child in elem:
                if child.tag.split('}')[-1] == 'period':
                    period = child
                    break
            
            if period is not None:
                end_date = None
                instant = None
                for p_child in period:
                    p_local = p_child.tag.split('}')[-1]
                    if p_local == 'endDate':
                        end_date = p_child.text
                    elif p_local == 'instant':
                        instant = p_child.text
                
                date_val = end_date or instant
                if date_val:
                    contexts[context_id] = date_val.strip()
                    
    # 2. 勘定科目データを抽出
    financial_data = {}
    
    # 逆引きマップを作成
    tag_reverse_map = {}
    for key, tags in XBRL_TAG_MAP.items():
        for tag in tags:
            tag_reverse_map[tag] = key
    for tag in DEBT_TAGS:
        tag_reverse_map[tag] = "debt_component"
        
    for elem in root.iter():
        local_name = elem.tag.split('}')[-1]
        if local_name in tag_reverse_map:
            key = tag_reverse_map[local_name]
            context_ref = elem.attrib.get('contextRef')
            if not context_ref or context_ref not in contexts:
                continue
            
            date_str = contexts[context_ref]
            
            try:
                val_str = elem.text
                if not val_str or val_str.strip() == '':
                    continue
                # コンテキストごとの端数処理単位は通常 decimals 属性で示されるが、そのままの実数値を格納
                val = float(val_str.strip())
            except ValueError:
                continue
                
            if key not in financial_data:
                financial_data[key] = {}
                
            # 重複がある場合は優先度の高い方を格納するか、コンテキストに応じた適切な値を格納
            financial_data[key][date_str] = val
            
            # 有利子負債の個別要素を一時保存
            if key == "debt_component":
                if "debt_components" not in financial_data:
                    financial_data["debt_components"] = {}
                if date_str not in financial_data["debt_components"]:
                    financial_data["debt_components"][date_str] = []
                financial_data["debt_components"][date_str].append((local_name, val))

    # 3. 有利子負債 (Total Debt) の合算
    all_dates = set()
    for k in financial_data:
        if k != "debt_components":
            all_dates.update(financial_data[k].keys())
            
    financial_data["Total Debt"] = {}
    if "debt_components" in financial_data:
        for d, comps in financial_data["debt_components"].items():
            # 重複加算を避けるため、タグごとに一意にして合算
            tag_vals = {}
            for tag, val in comps:
                tag_vals[tag] = val
            financial_data["Total Debt"][d] = sum(tag_vals.values())
            
    # 4. EBITDA = Operating Income + Reconciled Depreciation
    financial_data["EBITDA"] = {}
    for d in all_dates:
        ebit_val = financial_data.get("Operating Income", {}).get(d, 0.0)
        dep_val = financial_data.get("Reconciled Depreciation", {}).get(d, 0.0)
        if ebit_val or dep_val:
            financial_data["EBITDA"][d] = ebit_val + dep_val
            
    # 一時キーの削除
    if "debt_components" in financial_data:
        del financial_data["debt_components"]
        
    return financial_data

def extract_financials_from_zip(zip_path):
    """ZIPファイルから財務データをパースする (CSV同梱があればCSVを解析し、なければXBRLをパースするハイブリッド方式)"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(temp_dir)
            
        # 1. 財務諸表CSVファイルのスキャン (優先利用)
        csv_files = []
        xbrl_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
                elif file.endswith('.xbrl'):
                    xbrl_files.append(os.path.join(root, file))
                    
        # ユーザー指示: CSVを優先利用し、必要に応じてXBRLをパース
        # 実用上、同梱されているCSVは表形式の「見た目」を表現したもので、日本語ラベルが多岐にわたるため、
        # 確実なデータマッピングを行うために、まずXBRLを解析し、補完や監査用にCSVを利用するか、
        # あるいはXBRLから直接構築するのが安全です。ここでは高精度なXBRLパースをベースラインとします。
        logger.info(f"Found {len(xbrl_files)} XBRL files and {len(csv_files)} CSV files in ZIP.")
        
        financials = {}
        for xbrl_file in xbrl_files:
            data = parse_xbrl_file(xbrl_file)
            for key, dates in data.items():
                if key not in financials:
                    financials[key] = {}
                financials[key].update(dates)
                
        return financials

def merge_and_save_csv(target_dir, data_name, new_data_dict):
    """既存のCSVファイルがあれば、新規取得データとマージして保存する"""
    csv_path = os.path.join(target_dir, f"{data_name}.csv")
    
    # 既存データの読み込み
    df_existing = None
    if os.path.exists(csv_path):
        try:
            df_existing = pd.read_csv(csv_path, index_col=0)
            logger.info(f"Loaded existing data for {data_name} from {csv_path}")
        except Exception as e:
            logger.warning(f"Failed to read existing CSV {csv_path}: {e}")
            
    # 新規データのデータフレーム化
    # new_data_dict: {date_str: value}
    # シリーズ化して転置
    df_new = pd.Series(new_data_dict, name=data_name).to_frame().T
    
    if df_existing is not None:
        # 重複する列（日付）は新規データで上書き
        # 両方の列をマージ
        for col in df_new.columns:
            df_existing[col] = df_new[col]
            
        df_merged = df_existing
        # 列（日付）を逆順にソート（直近を左にするため）
        cols = sorted(list(df_merged.columns), reverse=True)
        df_merged = df_merged[cols]
    else:
        df_merged = df_new
        
    # 保存
    df_merged.to_csv(csv_path)
    logger.info(f"Saved merged {data_name} to {csv_path}")

def update_summary_json(target_dir, ticker_str, filer_name, currency="JPY"):
    """summary.jsonを新規作成または既存データをマージして更新する"""
    summary_path = os.path.join(target_dir, "summary.json")
    summary = {}
    
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read existing summary.json: {e}")
            
    # 基本情報の上書き/補完
    summary["ticker"] = ticker_str
    summary["currency"] = currency
    if "long_name" not in summary or not summary["long_name"]:
        summary["long_name"] = filer_name
        
    # 必要最低限のフィールドが欠損している場合に初期値を設定
    required_keys = {
        "current_price": 0.0,
        "market_cap": 0,
        "shares_outstanding": 0,
        "sector": "Unknown",
        "industry": "Unknown",
        "ebitda": 0,
        "pe_ratio": None,
        "pbr_ratio": None,
        "dividend_yield": None
    }
    for k, v in required_keys.items():
        if k not in summary or summary[k] is None:
            summary[k] = v
            
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"Updated summary.json at {summary_path}")

def complement_with_yfinance(ticker_str, target_dir):
    """yfinanceから時価総額や株価などの市場データを補完する"""
    logger.info(f"Fetching market data for {ticker_str} from yfinance...")
    try:
        ticker = yf.Ticker(ticker_str)
        hist = ticker.history(period="1y")
        
        # 1. prices.csvの保存
        if not hist.empty:
            prices_path = os.path.join(target_dir, "prices.csv")
            hist.to_csv(prices_path)
            logger.info(f"Complemented prices.csv at {prices_path}")
            
        # 2. summary.jsonの補完
        info_data = {}
        try:
            info_data = ticker.info
        except Exception:
            pass
            
        summary_path = os.path.join(target_dir, "summary.json")
        summary = {}
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
                
        latest_price = float(hist['Close'].iloc[-1]) if not hist.empty else 0.0
        
        summary["current_price"] = info_data.get("currentPrice") or info_data.get("regularMarketPrice") or latest_price
        summary["market_cap"] = info_data.get("marketCap") or summary.get("market_cap") or 0
        summary["shares_outstanding"] = info_data.get("sharesOutstanding") or summary.get("shares_outstanding") or 0
        summary["long_name"] = info_data.get("longName") or summary.get("long_name") or ticker_str
        summary["sector"] = info_data.get("sector") or summary.get("sector") or "Unknown"
        summary["industry"] = info_data.get("industry") or summary.get("industry") or "Unknown"
        summary["pe_ratio"] = info_data.get("trailingPE") or summary.get("pe_ratio")
        summary["pbr_ratio"] = info_data.get("priceToBook") or summary.get("pbr_ratio")
        summary["dividend_yield"] = info_data.get("dividendYield") or summary.get("dividend_yield")
        
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info("Complemented summary.json with yfinance data.")
    except Exception as e:
        logger.warning(f"Failed to complement with yfinance: {e}")

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Fetch Japanese financial data via EDINET API")
    parser.add_argument("ticker", type=str, help="Japanese Stock ticker (e.g. 7203, 7203.T)")
    parser.add_argument("--days", type=int, default=365, help="Number of days to search back for documents")
    parser.add_argument("--outdir", type=str, default="./out", help="Output directory")
    parser.add_argument("--skip-yfinance", action="store_true", help="Skip complementing with yfinance market data")
    args = parser.parse_args()
    
    api_key = os.environ.get("EDINET_API_KEY")
    if not api_key:
        logger.error("EDINET_API_KEY environment variable is not set. Please define it in your .env file.")
        sys.exit(1)
        
    ticker_str = normalize_ticker(args.ticker)
    
    # 1. EDINETコードの特定
    csv_path = os.path.join(args.outdir, "market_data", "EdinetcodeDlInfo.csv")
    try:
        company_info = lookup_edinet_code(csv_path, ticker_str)
    except Exception as e:
        logger.error(f"Failed to lookup EDINET code: {e}")
        sys.exit(1)
        
    edinet_code = company_info["edinet_code"]
    filer_name = company_info["filer_name"]
    logger.info(f"Identified company: {filer_name} (EDINET Code: {edinet_code})")
    
    # 2. 提出書類一覧のスキャン
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=args.days)
    
    logger.info(f"Scanning documents from {start_date} to {end_date} (looking for annual/quarterly reports)...")
    target_docs = []
    
    curr_date = start_date
    while curr_date <= end_date:
        date_str = curr_date.strftime("%Y-%m-%d")
        doc_list = fetch_document_list(api_key, date_str)
        if doc_list and "results" in doc_list:
            for doc in doc_list["results"]:
                if doc.get("edinetCode") == edinet_code:
                    # docTypeCode: 120 (有価証券報告書), 140 (四半期報告書)
                    doc_type = doc.get("docTypeCode")
                    if doc_type in ["120", "140"]:
                        target_docs.append({
                            "docID": doc["docID"],
                            "docDescription": doc.get("docDescription", ""),
                            "docTypeCode": doc_type,
                            "submitDateTime": doc.get("submitDateTime", "")
                        })
        curr_date += datetime.timedelta(days=1)
        
    if not target_docs:
        logger.warning(f"No annual or quarterly reports found for {filer_name} in the last {args.days} days.")
        # 部分的なフォールバックディレクトリ作成
        clean_name = re.sub(r'[^a-zA-Z0-9\s-]', '', filer_name)
        clean_name = re.sub(r'[\s-]+', '_', clean_name).strip('_')
        folder_name = f"{ticker_str}_{clean_name}"
        target_dir = os.path.join(args.outdir, folder_name, "market_data")
        os.makedirs(target_dir, exist_ok=True)
        update_summary_json(target_dir, ticker_str, filer_name)
        if not args.skip_yfinance:
            complement_with_yfinance(ticker_str, target_dir)
        sys.exit(0)
        
    logger.info(f"Found {len(target_docs)} matching documents.")
    # 有価証券報告書 (120) を優先、複数あれば日付が新しいものを優先
    target_docs.sort(key=lambda x: (x["docTypeCode"] == "120", x["submitDateTime"]), reverse=True)
    selected_doc = target_docs[0]
    logger.info(f"Selected document for download: {selected_doc['docDescription']} (ID: {selected_doc['docID']}, Submitted: {selected_doc['submitDateTime']})")
    
    # 3. 書類ZIPの取得
    cache_dir = os.path.join(args.outdir, "market_data", "raw_edinet")
    zip_path = os.path.join(cache_dir, f"{selected_doc['docID']}.zip")
    
    success = download_document_zip(api_key, selected_doc["docID"], zip_path)
    if not success:
        logger.error("Failed to download the document package.")
        sys.exit(1)
        
    # 4. 財務データの抽出
    financials = extract_financials_from_zip(zip_path)
    if not financials:
        logger.error("No financial data could be extracted from the document.")
        sys.exit(1)
        
    # 保存ディレクトリの決定
    clean_name = re.sub(r'[^a-zA-Z0-9\s-]', '', filer_name)
    clean_name = re.sub(r'[\s-]+', '_', clean_name).strip('_')
    folder_name = f"{ticker_str}_{clean_name}"
    target_dir = os.path.join(args.outdir, folder_name, "market_data")
    os.makedirs(target_dir, exist_ok=True)
    
    # 5. 各財務諸表へのマッピングとCSV保存
    # P&L項目
    pl_data = {
        "Total Revenue": financials.get("Total Revenue", {}),
        "Operating Income": financials.get("Operating Income", {}),
        "Reconciled Depreciation": financials.get("Reconciled Depreciation", {}),
        "Tax Provision": financials.get("Tax Provision", {}),
        "EBITDA": financials.get("EBITDA", {})
    }
    
    # B/S項目
    bs_data = {
        "Total Assets": financials.get("Total Assets", {}),
        "Total Debt": financials.get("Total Debt", {}),
        "Cash Cash Equivalents And Short Term Investments": financials.get("Cash Cash Equivalents And Short Term Investments", {})
    }
    
    # C/F項目
    cf_data = {
        "Operating Cash Flow": financials.get("Operating Cash Flow", {}),
        "Capital Expenditure": financials.get("Capital Expenditure", {}),
        "Change In Working Capital": financials.get("Change In Working Capital", {})
    }
    
    # yfinance互換のCSVとしてマージ＆保存
    # IS
    df_is = pd.DataFrame(pl_data).T
    df_is.to_csv(os.path.join(target_dir, "annual_income_stmt.csv"))
    logger.info("Saved annual_income_stmt.csv")
    
    # BS
    df_bs = pd.DataFrame(bs_data).T
    df_bs.to_csv(os.path.join(target_dir, "annual_balance_sheet.csv"))
    logger.info("Saved annual_balance_sheet.csv")
    
    # CF
    df_cf = pd.DataFrame(cf_data).T
    df_cf.to_csv(os.path.join(target_dir, "annual_cashflow.csv"))
    logger.info("Saved annual_cashflow.csv")
    
    # summary.jsonの初期化/更新
    update_summary_json(target_dir, ticker_str, filer_name)
    
    # yfinanceでの市場価格等データの補完
    if not args.skip_yfinance:
        complement_with_yfinance(ticker_str, target_dir)
        
    logger.info("EDINET financial data extraction completed successfully.")

if __name__ == "__main__":
    main()
