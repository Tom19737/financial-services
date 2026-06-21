import os
import sys
import argparse
import json
import datetime
import re
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# 共通ユーティリティと新規分割モジュールのインポート
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logging, normalize_ticker, sanitize_folder_name
from edinet_api import fetch_document_list, download_document_zip, lookup_edinet_code
from xbrl_parser import extract_financials_from_zip

logger = setup_logging("fetch_edinet")

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
    df_new = pd.Series(new_data_dict, name=data_name).to_frame().T
    
    if df_existing is not None:
        # 重複する列（日付）は新規データで上書き
        for col in df_new.columns:
            df_existing[col] = df_new[col]
            
        df_merged = df_existing
        cols = sorted(list(df_merged.columns), reverse=True)
        df_merged = df_merged[cols]
    else:
        df_merged = df_new
        
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
            
    summary["ticker"] = ticker_str
    summary["currency"] = currency
    if "long_name" not in summary or not summary["long_name"]:
        summary["long_name"] = filer_name
        
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
        
        if not hist.empty:
            prices_path = os.path.join(target_dir, "prices.csv")
            hist.to_csv(prices_path)
            logger.info(f"Complemented prices.csv at {prices_path}")
            
        info_data = {}
        try:
            info_data = ticker.info
        except Exception as e:
            logger.warning(f"Failed to fetch info from yfinance: {e}")
            
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
    # 標準の dotenv で環境変数を読み込む
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
    
    csv_path = os.path.join(args.outdir, "market_data", "EdinetcodeDlInfo.csv")
    try:
        company_info = lookup_edinet_code(csv_path, ticker_str)
    except Exception as e:
        logger.error(f"Failed to lookup EDINET code: {e}")
        sys.exit(1)
        
    edinet_code = company_info["edinet_code"]
    filer_name = company_info["filer_name"]
    logger.info(f"Identified company: {filer_name} (EDINET Code: {edinet_code})")
    
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
        clean_name = sanitize_folder_name(filer_name)
        folder_name = f"{ticker_str}_{clean_name}"
        target_dir = os.path.join(args.outdir, folder_name, "market_data")
        os.makedirs(target_dir, exist_ok=True)
        update_summary_json(target_dir, ticker_str, filer_name)
        if not args.skip_yfinance:
            complement_with_yfinance(ticker_str, target_dir)
        sys.exit(0)
        
    logger.info(f"Found {len(target_docs)} matching documents.")
    target_docs.sort(key=lambda x: (x["docTypeCode"] == "120", x["submitDateTime"]), reverse=True)
    selected_doc = target_docs[0]
    logger.info(f"Selected document for download: {selected_doc['docDescription']} (ID: {selected_doc['docID']}, Submitted: {selected_doc['submitDateTime']})")
    
    cache_dir = os.path.join(args.outdir, "market_data", "raw_edinet")
    zip_path = os.path.join(cache_dir, f"{selected_doc['docID']}.zip")
    
    success = download_document_zip(api_key, selected_doc["docID"], zip_path)
    if not success:
        logger.error("Failed to download the document package.")
        sys.exit(1)
        
    financials = extract_financials_from_zip(zip_path)
    if not financials:
        logger.error("No financial data could be extracted from the document.")
        sys.exit(1)
        
    clean_name = sanitize_folder_name(filer_name)
    folder_name = f"{ticker_str}_{clean_name}"
    target_dir = os.path.join(args.outdir, folder_name, "market_data")
    os.makedirs(target_dir, exist_ok=True)
    
    pl_data = {
        "Total Revenue": financials.get("Total Revenue", {}),
        "Operating Income": financials.get("Operating Income", {}),
        "Reconciled Depreciation": financials.get("Reconciled Depreciation", {}),
        "Tax Provision": financials.get("Tax Provision", {}),
        "EBITDA": financials.get("EBITDA", {})
    }
    
    bs_data = {
        "Total Assets": financials.get("Total Assets", {}),
        "Total Debt": financials.get("Total Debt", {}),
        "Cash Cash Equivalents And Short Term Investments": financials.get("Cash Cash Equivalents And Short Term Investments", {})
    }
    
    cf_data = {
        "Operating Cash Flow": financials.get("Operating Cash Flow", {}),
        "Capital Expenditure": financials.get("Capital Expenditure", {}),
        "Change In Working Capital": financials.get("Change In Working Capital", {})
    }
    
    df_is = pd.DataFrame(pl_data).T
    df_is.to_csv(os.path.join(target_dir, "annual_income_stmt.csv"))
    logger.info("Saved annual_income_stmt.csv")
    
    df_bs = pd.DataFrame(bs_data).T
    df_bs.to_csv(os.path.join(target_dir, "annual_balance_sheet.csv"))
    logger.info("Saved annual_balance_sheet.csv")
    
    df_cf = pd.DataFrame(cf_data).T
    df_cf.to_csv(os.path.join(target_dir, "annual_cashflow.csv"))
    logger.info("Saved annual_cashflow.csv")
    
    update_summary_json(target_dir, ticker_str, filer_name)
    
    if not args.skip_yfinance:
        complement_with_yfinance(ticker_str, target_dir)
        
    logger.info("EDINET financial data extraction completed successfully.")

if __name__ == "__main__":
    main()
