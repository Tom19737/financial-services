import pandas as pd
import os
import argparse
import sys
from utils import find_ticker_dir, normalize_ticker, setup_logging

logger = setup_logging("clean_data")

def clean_prices(ticker_dir):
    prices_path = os.path.join(ticker_dir, "market_data", "prices.csv")
    if not os.path.exists(prices_path):
        logger.error(f"File not found: {prices_path}")
        return
        
    logger.info(f"Loading data from {prices_path}...")
    df = pd.read_csv(prices_path)
    
    # 検出された問題の出力
    print("=== Data Cleaning Report (clean-data-xls) ===")
    print(f"Total Rows: {len(df)}")
    
    # 1. 空白トリム
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).str.strip()
        
    # 2. 日付形式の標準化 (YYYY-MM-DD)
    # yfinance特有のタイムゾーン表記を削除し正規化
    if 'Date' in df.columns:
        print("  -> Normalizing Date column to YYYY-MM-DD...")
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        
    # 3. 重複行の削除
    initial_len = len(df)
    df.drop_duplicates(inplace=True)
    dup_removed = initial_len - len(df)
    if dup_removed > 0:
        print(f"  -> Removed {dup_removed} duplicate rows.")
    else:
        print("  -> No duplicate rows detected.")
        
    # 4. 数値列の確認（欠損値や不正値の処理）
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            null_count = df[col].isnull().sum()
            if null_count > 0:
                print(f"  -> Found {null_count} null/corrupted values in {col}. Interpolating...")
                df[col] = df[col].interpolate()
                
    # 保存
    df.to_csv(prices_path, index=False)
    logger.info(f"Cleaned data saved back to {prices_path}")
    print("=== Cleaning Complete ===\n")

def main():
    parser = argparse.ArgumentParser(description="Clean up prices.csv data")
    parser.add_argument("ticker", type=str, help="Stock ticker")
    parser.add_argument("--outdir", type=str, default="./out", help="Base output directory")
    args = parser.parse_args()
    
    ticker_str = args.ticker.strip()
    ticker_dir = find_ticker_dir(args.outdir, ticker_str)
    
    if not os.path.exists(ticker_dir):
        logger.error(f"Directory {ticker_dir} does not exist. Please run fetch_yfinance.py first.")
        sys.exit(1)
        
    clean_prices(ticker_dir)

if __name__ == "__main__":
    main()
