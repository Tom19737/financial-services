#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import datetime
import yfinance as yf

# プロジェクトルートとパスの設定
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))

try:
    import utils
    import trade_manager
except ImportError:
    utils = None
    trade_manager = None

# パスの定義
JOURNAL_DIR = os.path.join(PROJECT_ROOT, "out", "_journal")
INDEX_PATH = os.path.join(JOURNAL_DIR, "index.json")

def normalize_ticker(ticker_str):
    if utils:
        return utils.normalize_ticker(ticker_str)
    ticker_str = ticker_str.strip()
    if len(ticker_str) == 4 and ticker_str.isdigit():
        return f"{ticker_str}.T"
    return ticker_str

def get_company_name_yfinance(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        name = info.get("shortName") or info.get("longName")
        if name:
            return name
    except Exception:
        pass
    return None

def detect_csv_format(filepath):
    """
    CSVファイルを読み込み、ヘッダー行を検出して証券会社フォーマットを返す。
    """
    encoding = 'cp932'
    try:
        with open(filepath, 'r', encoding=encoding) as f:
            lines = f.readlines()
    except (UnicodeDecodeError, FileNotFoundError):
        encoding = 'utf-8'
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: File not found {filepath}", file=sys.stderr)
            sys.exit(1)
            
    for i, line in enumerate(lines):
        parts = [p.strip().replace('"', '') for p in line.split(',')]
        
        # 楽天証券の判定
        if "約定日" in parts and "銘柄コード" in parts and "数量［株］" in parts:
            return "rakuten", i, encoding
            
        # SBI証券の判定
        if "約定日" in parts and "銘柄コード" in parts and "約定数量" in parts and "手数料/諸経費等" in parts:
            return "sbi", i, encoding
            
    return None, -1, encoding

def clean_number(val_str):
    if not val_str:
        return 0.0
    val_str = val_str.replace(",", "").replace("円", "").replace("株", "").strip()
    if val_str == "-" or val_str == "--" or val_str == "":
        return 0.0
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def parse_row(fmt, header, row):
    if len(row) < len(header):
        # 列数が足りない行はスキップ
        return None
        
    if fmt == "rakuten":
        col_date = header.index("約定日")
        col_ticker = header.index("銘柄コード")
        col_company = header.index("銘柄名")
        col_side = header.index("売買区分")
        col_qty = header.index("数量［株］")
        col_price = header.index("単価［円］")
        col_fee = header.index("手数料［円］")
        col_other_fee = header.index("諸費用［円］")
        col_tx_type = header.index("取引区分")
        
        tx_type = row[col_tx_type].strip()
        if tx_type != "現物":
            return None
            
        side_val = row[col_side].strip()
        if side_val == "買付":
            side = "buy"
        elif side_val == "売付":
            side = "sell"
        else:
            return None
            
        date_raw = row[col_date].strip().replace('"', '')
        try:
            dt = datetime.datetime.strptime(date_raw, "%Y/%m/%d")
        except ValueError:
            dt = datetime.datetime.strptime(date_raw, "%Y-%m-%d")
        date_str = dt.strftime("%Y-%m-%d")
        
        ticker = normalize_ticker(row[col_ticker].strip().replace('"', ''))
        company = row[col_company].strip().replace('"', '')
        
        quantity = int(clean_number(row[col_qty]))
        price = clean_number(row[col_price])
        fees = clean_number(row[col_fee]) + clean_number(row[col_other_fee])
        
        return {
            "date": date_str,
            "ticker": ticker,
            "csv_company": company,
            "side": side,
            "quantity": quantity,
            "price": price,
            "fees": fees,
            "thesis_snapshot": f"楽天証券 約定取引インポート (約定日: {date_str})"
        }
        
    elif fmt == "sbi":
        col_date = header.index("約定日")
        col_ticker = header.index("銘柄コード")
        col_company = header.index("銘柄")
        col_side = header.index("取引")
        col_qty = header.index("約定数量")
        col_price = header.index("約定単価")
        col_fee = header.index("手数料/諸経費等")
        
        side_val = row[col_side].strip()
        if "買" in side_val:
            side = "buy"
        elif "売" in side_val:
            side = "sell"
        else:
            return None
            
        date_raw = row[col_date].strip().replace('"', '')
        try:
            dt = datetime.datetime.strptime(date_raw, "%Y/%m/%d")
        except ValueError:
            dt = datetime.datetime.strptime(date_raw, "%Y-%m-%d")
        date_str = dt.strftime("%Y-%m-%d")
        
        ticker = normalize_ticker(row[col_ticker].strip().replace('"', ''))
        company = row[col_company].strip().replace('"', '')
        
        quantity = int(clean_number(row[col_qty]))
        price = clean_number(row[col_price])
        fees = clean_number(row[col_fee])
        
        return {
            "date": date_str,
            "ticker": ticker,
            "csv_company": company,
            "side": side,
            "quantity": quantity,
            "price": price,
            "fees": fees,
            "thesis_snapshot": f"SBI証券 約定取引インポート (約定日: {date_str})"
        }
        
    return None

def load_sessions_list():
    if not os.path.exists(INDEX_PATH):
        return []
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index_data = json.load(f)
            return index_data.get("sessions", [])
    except Exception as e:
        print(f"Warning: Failed to load index.json for sessions: {e}", file=sys.stderr)
        return []

def prompt_for_session(trade_info, company_name, sessions):
    print("\n" + "="*70)
    print(f"取引情報: {trade_info['date']} | {trade_info['ticker']} ({company_name}) | {trade_info['side'].upper()} | {trade_info['quantity']}株 @ {trade_info['price']}円")
    print("="*70)
    print("関連セッションの選択:")
    print("  [0] スキップ（紐付けなし）")
    for idx, s in enumerate(sessions):
        tickers_str = ",".join(s.get("tickers", []))
        print(f"  [{idx+1}] {s['date']} | {s['session_id']} | 対象銘柄: {tickers_str}")
        
    while True:
        try:
            inp = input("紐付けるセッション番号を選択してください (複数可。カンマ区切り。スキップは0): ").strip()
            if not inp or inp == '0':
                return []
            indices = [int(x.strip()) - 1 for x in inp.split(",") if x.strip()]
            refs = []
            valid = True
            for i in indices:
                if 0 <= i < len(sessions):
                    refs.append(sessions[i]["session_id"])
                else:
                    print(f"無効なインデックス: {i+1}")
                    valid = False
            if valid:
                return refs
        except ValueError:
            print("数値、またはカンマ区切りの数値を入力してください。")

def main():
    parser = argparse.ArgumentParser(description="Import trades from SBI/Rakuten brokerage CSV files.")
    parser.add_argument("csv_path", help="Path to the CSV file")
    parser.add_argument("-i", "--interactive", action="store_true", help="Prompt to link sessions interactively")
    parser.add_argument("--session-ref", help="Directly link all imported trades to this session ID")
    parser.add_argument("--currency", default="JPY", help="Default currency for imported trades (default: JPY)")
    
    args = parser.parse_args()
    
    csv_path = args.csv_path
    
    fmt, header_idx, encoding = detect_csv_format(csv_path)
    if not fmt:
        print(f"Error: Could not detect SBI or Rakuten CSV format in {csv_path}", file=sys.stderr)
        sys.exit(1)
        
    print(f"検出フォーマット: {fmt.upper()} (文字コード: {encoding}, ヘッダー行: {header_idx + 1})")
    
    if trade_manager:
        existing_data = trade_manager.load_trades()
    else:
        existing_data = {"trades": []}
        
    existing_keys = set()
    for t in existing_data.get("trades", []):
        key = (
            t.get("date"),
            t.get("ticker"),
            t.get("side"),
            t.get("quantity"),
            t.get("price")
        )
        existing_keys.add(key)
        
    # CSV読み込み
    with open(csv_path, 'r', encoding=encoding) as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    header = [r.strip().replace('"', '') for r in rows[header_idx]]
    data_rows = rows[header_idx + 1:]
    
    sessions = []
    if args.interactive:
        sessions = load_sessions_list()
        if not sessions:
            print("Warning: index.json からセッションが見つかりません。対話型紐付けはスキップします。")
            args.interactive = False
            
    skipped_count = 0
    imported_count = 0
    
    for row_num, row in enumerate(data_rows):
        if not row or all(cell == '' for cell in row):
            continue
            
        try:
            trade_info = parse_row(fmt, header, row)
            if not trade_info:
                continue
                
            key = (
                trade_info["date"],
                trade_info["ticker"],
                trade_info["side"],
                trade_info["quantity"],
                trade_info["price"]
            )
            
            if key in existing_keys:
                skipped_count += 1
                continue
                
            ticker = trade_info["ticker"]
            csv_company = trade_info["csv_company"]
            
            print(f"yfinance から会社名を取得中... ({ticker})")
            yf_name = get_company_name_yfinance(ticker)
            company_name = yf_name if yf_name else csv_company
            
            trade_id = trade_manager.generate_trade_id(existing_data["trades"]) if trade_manager else f"t{len(existing_data['trades'])+1:03d}"
            
            session_refs = []
            if args.interactive:
                session_refs = prompt_for_session(trade_info, company_name, sessions)
            elif args.session_ref:
                session_refs = [args.session_ref]
                
            new_trade = {
                "trade_id": trade_id,
                "ticker": ticker,
                "company": company_name,
                "side": trade_info["side"],
                "date": trade_info["date"],
                "quantity": trade_info["quantity"],
                "price": trade_info["price"],
                "currency": args.currency,
                "fees": trade_info["fees"],
                "session_refs": session_refs,
                "thesis_snapshot": trade_info.get("thesis_snapshot", f"CSVインポート取引 ({fmt.upper()})"),
                "notes": f"CSV Import from {os.path.basename(csv_path)} (Original Name: {csv_company})"
            }
            
            existing_data["trades"].append(new_trade)
            existing_keys.add(key)
            imported_count += 1
            
        except Exception as e:
            print(f"Error parsing row {row_num + header_idx + 2}: {e}", file=sys.stderr)
            
    if imported_count > 0:
        if trade_manager:
            trade_manager.save_trades(existing_data)
        else:
            os.makedirs(os.path.dirname(trade_manager.TRADES_PATH), exist_ok=True)
            with open(trade_manager.TRADES_PATH, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
                
    print(f"インポート完了: {imported_count} 件インポート, {skipped_count} 件重複スキップ。")

if __name__ == "__main__":
    main()
