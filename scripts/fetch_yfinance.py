import os
import sys
import argparse
import json
import yfinance as yf

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import sanitize_folder_name, setup_logging

logger = setup_logging("fetch_yfinance")

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch stock data and financial statements using yfinance")
    parser.add_argument("ticker", type=str, help="Stock ticker (e.g. MSFT, 7203)")
    parser.add_argument("--period", type=str, default="1y", help="Data period for stock prices (e.g. 1d, 5d, 1mo, 1y)")
    parser.add_argument("--interval", type=str, default="1d", help="Data interval for stock prices (e.g. 1d, 1wk)")
    parser.add_argument("--outdir", type=str, default="./out", help="Output directory")
    parser.add_argument("--name", type=str, help="English company name to append to the folder (e.g. Toyota_Motor)")
    parser.add_argument("--skip-fundamentals", action="store_true", help="Skip fetching financial statements (PL/BS/CF)")
    parser.add_argument("--exchange-rate", type=float, help="Exchange rate to JPY (e.g. 150.5). If not specified, fetches the latest rate from yfinance.")
    return parser.parse_args()

def get_exchange_rate(from_currency: str) -> float:
    """指定された通貨から JPY への最新の為替レートを取得する。"""
    if not from_currency:
        return 1.0
    
    from_currency = from_currency.upper().strip()
    if from_currency == "JPY":
        return 1.0
        
    ticker_symbol = f"{from_currency}JPY=X"
    logger.info(f"Fetching exchange rate for {ticker_symbol}...")
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            rate = float(hist["Close"].iloc[-1])
            logger.info(f"Exchange rate for {ticker_symbol}: {rate}")
            return rate
        else:
            rate = ticker.fast_info.get("regularMarketPrice")
            if rate is not None:
                logger.info(f"Exchange rate for {ticker_symbol} (fast_info): {rate}")
                return float(rate)
    except Exception as e:
        logger.warning(f"Failed to fetch exchange rate for {ticker_symbol}: {e}")
        
    logger.error(f"Could not retrieve exchange rate for {from_currency}. No conversion applied.")
    return 1.0

def save_financial_statement(df, name, outdir, rate=1.0):
    """財務諸表DataFrameをCSVとして保存するヘルパー関数"""
    if df is None or df.empty:
        logger.warning(f"No data found for {name}. Skipping.")
        return False
    try:
        import pandas as pd
        csv_path = os.path.join(outdir, f"{name}.csv")
        
        # 為替換算
        if rate != 1.0:
            df = df.copy()
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce') * rate
                
        df.to_csv(csv_path)
        logger.info(f"Saved {name} to {csv_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving {name} to CSV: {e}")
        return False

def main():
    args = parse_args()
    ticker_str = args.ticker.strip()
    
    # 日本株対応: 4桁かつ先頭が数字（新証券コードなどの英数字混在を含む）の場合は末尾に .T を付加
    # 例: "7203" -> "7203.T", "285A" -> "285A.T"
    # ※ 米国の4桁ティッカー (MSFT等) は先頭が英字のため除外されます。
    if len(ticker_str) == 4 and ticker_str[0].isdigit() and ticker_str.isalnum():
        ticker_str = f"{ticker_str}.T"
        logger.info(f"Detected Japanese ticker code. Appended '.T': {ticker_str}")
        
    logger.info(f"Fetching data for {ticker_str}...")
    
    try:
        ticker = yf.Ticker(ticker_str)
        
        # 1. ヒストリカル株価データの取得
        hist = ticker.history(period=args.period, interval=args.interval)
        if hist.empty:
            logger.error(f"Error: No historical data found for {ticker_str}.")
            sys.exit(1)
            
        # 2. 会社基本情報（info）の取得（フォールバック付き）
        info_data = {}
        try:
            info_data = ticker.info
        except Exception as e:
            logger.warning(f"Failed to fetch ticker info: {e}")
            
        currency = info_data.get("currency")
        
        # 為替レートの決定（日本株 .T の場合で、かつ元通貨が JPY 以外の場合のみ円換算を行う）
        rate = 1.0
        is_converted = False
        
        is_japanese_stock = ticker_str.endswith(".T")
        
        if is_japanese_stock and currency and currency.upper() != "JPY":
            if args.exchange_rate is not None:
                rate = args.exchange_rate
                if rate != 1.0:
                    is_converted = True
                    logger.info(f"Using specified exchange rate for Japanese stock: {rate}")
            else:
                rate = get_exchange_rate(currency)
                if rate != 1.0:
                    is_converted = True
                    logger.info(f"Using latest exchange rate from yfinance for Japanese stock: {rate}")
                
        # 株価データの換算
        if is_converted:
            price_cols = ["Open", "High", "Low", "Close", "Adj Close", "Dividends"]
            for col in price_cols:
                if col in hist.columns:
                    hist[col] = hist[col] * rate
            
        # 英語会社名の決定とクリーンアップ
        company_name = None
        if args.name:
            company_name = args.name.strip()
        else:
            company_name = info_data.get("longName") or info_data.get("shortName")
            
        if company_name:
            clean_name = sanitize_folder_name(company_name)
            folder_name = f"{ticker_str}_{clean_name}"
        else:
            folder_name = ticker_str
            
        logger.info(f"Target folder name: {folder_name}")
        
        # ディレクトリ作成 (企業コードごとのフォルダ)
        target_dir = os.path.join(args.outdir, folder_name, "market_data")
        os.makedirs(target_dir, exist_ok=True)
        
        # 株価CSV出力
        csv_path = os.path.join(target_dir, "prices.csv")
        hist.to_csv(csv_path)
        logger.info(f"Saved historical stock prices to {csv_path}")
            
        latest_price = float(hist['Close'].iloc[-1]) if not hist.empty else None
            
        summary = {
            "ticker": ticker_str,
            "current_price": info_data.get("currentPrice") or info_data.get("regularMarketPrice") or latest_price,
            "market_cap": info_data.get("marketCap"),
            "shares_outstanding": info_data.get("sharesOutstanding"),
            "currency": "JPY" if is_converted else (currency or "JPY"),
            "long_name": info_data.get("longName"),
            "sector": info_data.get("sector"),
            "industry": info_data.get("industry"),
            "ebitda": info_data.get("ebitda"),
            "pe_ratio": info_data.get("trailingPE"),
            "pbr_ratio": info_data.get("priceToBook"),
            "dividend_yield": info_data.get("dividendYield"),
        }
        
        if is_converted:
            if summary["current_price"] is not None:
                summary["current_price"] = float(summary["current_price"]) * rate
            if summary["market_cap"] is not None:
                summary["market_cap"] = float(summary["market_cap"]) * rate
            if summary["ebitda"] is not None:
                summary["ebitda"] = float(summary["ebitda"]) * rate
            summary["original_currency"] = currency
            summary["exchange_rate_applied"] = rate
        
        # 基本情報JSON出力
        json_path = os.path.join(target_dir, "summary.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved summary data to {json_path}")
        
        # 3. 財務諸表（ファンダメンタルズ）の取得と保存
        if not args.skip_fundamentals:
            logger.info("Fetching financial statements (PL/BS/CF)...")
            
            # 損益計算書 (Income Statement)
            try:
                save_financial_statement(ticker.income_stmt, "annual_income_stmt", target_dir, rate=rate)
                save_financial_statement(ticker.quarterly_income_stmt, "quarterly_income_stmt", target_dir, rate=rate)
            except Exception as e:
                logger.warning(f"Failed to fetch Income Statement: {e}")
                
            # 貸借対照表 (Balance Sheet)
            try:
                save_financial_statement(ticker.balance_sheet, "annual_balance_sheet", target_dir, rate=rate)
                save_financial_statement(ticker.quarterly_balance_sheet, "quarterly_balance_sheet", target_dir, rate=rate)
            except Exception as e:
                logger.warning(f"Failed to fetch Balance Sheet: {e}")
                
            # キャッシュフロー計算書 (Cash Flow)
            try:
                save_financial_statement(ticker.cashflow, "annual_cashflow", target_dir, rate=rate)
                save_financial_statement(ticker.quarterly_cashflow, "quarterly_cashflow", target_dir, rate=rate)
            except Exception as e:
                logger.warning(f"Failed to fetch Cash Flow Statement: {e}")
        
        # 完了時コンソール出力（JSON）
        logger.info("Summary metrics:\n" + json.dumps(summary, indent=2, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Error occurred while fetching data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
