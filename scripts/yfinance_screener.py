import os
import sys
import argparse
import json
import pandas as pd
import yfinance as yf

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logging

logger = setup_logging("yfinance_screener")

# 抽出する主要カラムの定義
DEFAULT_COLUMNS = [
    "symbol",
    "shortName",
    "regularMarketPrice",
    "regularMarketChangePercent",
    "marketCap",
    "trailingPE",
    "priceToBook",
    "dividendYield",
    "currency",
    "exchange"
]

def parse_args():
    parser = argparse.ArgumentParser(description="yfinance stock screening tool")
    parser.add_argument("--region", type=str, default="jp", help="Region to screen (e.g., jp, us)")
    parser.add_argument("--sector", type=str, help="Sector to screen (e.g., Technology)")
    parser.add_argument("--industry", type=str, help="Industry to screen")
    parser.add_argument("--min-market-cap", type=float, help="Minimum market capitalization (value in regional currency, e.g. JPY or USD)")
    parser.add_argument("--max-market-cap", type=float, help="Maximum market capitalization")
    parser.add_argument("--min-pe", type=float, help="Minimum PE ratio")
    parser.add_argument("--max-pe", type=float, help="Maximum PE ratio")
    parser.add_argument("--count", type=int, default=25, help="Number of results to retrieve (default: 25)")
    parser.add_argument("--sort-by", type=str, default="intradaymarketcap", help="Field to sort by (default: intradaymarketcap)")
    parser.add_argument("--sort-type", type=str, default="DESC", choices=["ASC", "DESC"], help="Sort direction")
    parser.add_argument("--output", type=str, help="File path to save the results")
    parser.add_argument("--format", type=str, default="json", choices=["json", "csv"], help="Output format (json or csv)")
    return parser.parse_args()

def build_query(args):
    """
    コマンドライン引数を元に EquityQuery を組み立てる
    """
    queries = []
    
    # 地域
    if args.region:
        queries.append(yf.EquityQuery("eq", ["region", args.region.lower()]))
        
    # セクター
    if args.sector:
        queries.append(yf.EquityQuery("eq", ["sector", args.sector]))
        
    # 業界
    if args.industry:
        queries.append(yf.EquityQuery("eq", ["industry", args.industry]))
        
    # 時価総額
    if args.min_market_cap is not None:
        queries.append(yf.EquityQuery("gte", ["intradaymarketcap", args.min_market_cap]))
    if args.max_market_cap is not None:
        queries.append(yf.EquityQuery("lte", ["intradaymarketcap", args.max_market_cap]))
        
    # PEレシオ (btwn を使用)
    if args.min_pe is not None or args.max_pe is not None:
        min_pe = args.min_pe if args.min_pe is not None else 0
        max_pe = args.max_pe if args.max_pe is not None else 99999
        queries.append(yf.EquityQuery("btwn", ["peratio.lasttwelvemonths", min_pe, max_pe]))
        
    # クエリの結合
    if not queries:
        # デフォルトは米国株
        return yf.EquityQuery("eq", ["region", "us"])
    elif len(queries) == 1:
        return queries[0]
    else:
        return yf.EquityQuery("and", queries)

def save_results(quotes, filepath, file_format):
    """
    結果をファイルに保存する
    """
    if not quotes:
        logger.warning("No data to save.")
        return False
        
    try:
        # ディレクトリの作成
        dirname = os.path.dirname(filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
            
        if file_format == "csv":
            df = pd.DataFrame(quotes)
            # 存在するカラムのみに絞り込む
            columns_to_keep = [col for col in DEFAULT_COLUMNS if col in df.columns]
            # もし定義した主要カラムが全くない場合はそのまま出力
            if columns_to_keep:
                df = df[columns_to_keep]
            df.to_csv(filepath, index=False, encoding="utf-8-sig")
            logger.info(f"Saved screener results to CSV: {filepath}")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(quotes, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved screener results to JSON: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save results: {e}")
        return False

def main():
    args = parse_args()
    
    logger.info("Building screener query...")
    try:
        query = build_query(args)
        logger.info(f"Generated query: {query}")
        
        logger.info("Executing screen on Yahoo Finance...")
        sort_asc = (args.sort_type == "ASC")
        res = yf.screen(
            query=query,
            count=args.count,
            sortField=args.sort_by,
            sortAsc=sort_asc
        )
        
        quotes = res.get("quotes", [])
        if quotes and args.count is not None:
            quotes = quotes[:args.count]
        logger.info(f"Successfully retrieved {len(quotes)} quotes.")
        
        # 結果の出力
        if args.output:
            save_results(quotes, args.output, args.format)
        else:
            # 簡易表示（コンソール出力）
            if quotes:
                df = pd.DataFrame(quotes)
                columns_to_keep = [col for col in DEFAULT_COLUMNS if col in df.columns]
                if columns_to_keep:
                    print(df[columns_to_keep].to_string(index=False))
                else:
                    print(df.to_string(index=False))
            else:
                logger.info("No stocks matched the criteria.")
                
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
