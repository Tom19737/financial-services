import os
import sys
import argparse
import json
import yfinance as yf

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch stock data and financial statements using yfinance")
    parser.add_argument("ticker", type=str, help="Stock ticker (e.g. MSFT, 7203)")
    parser.add_argument("--period", type=str, default="1y", help="Data period for stock prices (e.g. 1d, 5d, 1mo, 1y)")
    parser.add_argument("--interval", type=str, default="1d", help="Data interval for stock prices (e.g. 1d, 1wk)")
    parser.add_argument("--outdir", type=str, default="./out/market_data", help="Output directory")
    parser.add_argument("--skip-fundamentals", action="store_true", help="Skip fetching financial statements (PL/BS/CF)")
    return parser.parse_args()

def save_financial_statement(df, ticker_str, name, outdir):
    """財務諸表DataFrameをCSVとして保存するヘルパー関数"""
    if df is None or df.empty:
        print(f"Warning: No data found for {name} ({ticker_str}). Skipping.")
        return False
    try:
        csv_path = os.path.join(outdir, f"{ticker_str}_{name}.csv")
        df.to_csv(csv_path)
        print(f"Saved {name} to {csv_path}")
        return True
    except Exception as e:
        print(f"Error saving {name} to CSV: {e}", file=sys.stderr)
        return False

def main():
    args = parse_args()
    ticker_str = args.ticker.strip()
    
    # 日本株対応: 4桁の数値の場合は末尾に .T を付加
    if ticker_str.isdigit() and len(ticker_str) == 4:
        ticker_str = f"{ticker_str}.T"
        print(f"Detected Japanese ticker code. Appended '.T': {ticker_str}")
        
    print(f"Fetching data for {ticker_str}...")
    
    try:
        ticker = yf.Ticker(ticker_str)
        
        # 1. ヒストリカル株価データの取得
        hist = ticker.history(period=args.period, interval=args.interval)
        if hist.empty:
            print(f"Error: No historical data found for {ticker_str}.", file=sys.stderr)
            sys.exit(1)
            
        # ディレクトリ作成
        os.makedirs(args.outdir, exist_ok=True)
        
        # 株価CSV出力
        csv_path = os.path.join(args.outdir, f"{ticker_str}.csv")
        hist.to_csv(csv_path)
        print(f"Saved historical stock prices to {csv_path}")
        
        # 2. 会社基本情報（info）の取得（フォールバック付き）
        info_data = {}
        try:
            info_data = ticker.info
        except Exception as e:
            print(f"Warning: Failed to fetch ticker info: {e}", file=sys.stderr)
            
        latest_price = float(hist['Close'].iloc[-1]) if not hist.empty else None
            
        summary = {
            "ticker": ticker_str,
            "current_price": info_data.get("currentPrice") or info_data.get("regularMarketPrice") or latest_price,
            "market_cap": info_data.get("marketCap"),
            "shares_outstanding": info_data.get("sharesOutstanding"),
            "currency": info_data.get("currency"),
            "long_name": info_data.get("longName"),
            "sector": info_data.get("sector"),
            "industry": info_data.get("industry"),
            "ebitda": info_data.get("ebitda"),
            "pe_ratio": info_data.get("trailingPE"),
            "pbr_ratio": info_data.get("priceToBook"),
            "dividend_yield": info_data.get("dividendYield"),
        }
        
        # 基本情報JSON出力
        json_path = os.path.join(args.outdir, f"{ticker_str}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"Saved summary data to {json_path}")
        
        # 3. 財務諸表（ファンダメンタルズ）の取得と保存
        if not args.skip_fundamentals:
            print("Fetching financial statements (PL/BS/CF)...")
            
            # 損益計算書 (Income Statement)
            try:
                save_financial_statement(ticker.income_stmt, ticker_str, "annual_income_stmt", args.outdir)
                save_financial_statement(ticker.quarterly_income_stmt, ticker_str, "quarterly_income_stmt", args.outdir)
            except Exception as e:
                print(f"Warning: Failed to fetch Income Statement: {e}", file=sys.stderr)
                
            # 貸借対照表 (Balance Sheet)
            try:
                save_financial_statement(ticker.balance_sheet, ticker_str, "annual_balance_sheet", args.outdir)
                save_financial_statement(ticker.quarterly_balance_sheet, ticker_str, "quarterly_balance_sheet", args.outdir)
            except Exception as e:
                print(f"Warning: Failed to fetch Balance Sheet: {e}", file=sys.stderr)
                
            # キャッシュフロー計算書 (Cash Flow)
            try:
                save_financial_statement(ticker.cashflow, ticker_str, "annual_cashflow", args.outdir)
                save_financial_statement(ticker.quarterly_cashflow, ticker_str, "quarterly_cashflow", args.outdir)
            except Exception as e:
                print(f"Warning: Failed to fetch Cash Flow Statement: {e}", file=sys.stderr)
        
        # 完了時コンソール出力（JSON）
        print("\nSummary metrics:")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error occurred while fetching data: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
