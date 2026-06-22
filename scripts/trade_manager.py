#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime

# プロジェクトルートとジャーナルパス
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_DIR = os.path.join(PROJECT_ROOT, "out", "_journal")
TRADES_PATH = os.path.join(JOURNAL_DIR, "trades", "trades.json")
SCHEMAS_DIR = os.path.join(PROJECT_ROOT, "docs", "schemas")
INDEX_PATH = os.path.join(JOURNAL_DIR, "index.json")

def load_json_schema(schema_name):
    schema_path = os.path.join(SCHEMAS_DIR, schema_name)
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def validate_trade_data(data):
    schema = load_json_schema("trade_schema.json")
    if not schema:
        return True
    try:
        import jsonschema
        jsonschema.validate(instance=data, schema=schema)
        return True
    except ImportError:
        # 簡易バリデーション
        if "trades" not in data or not isinstance(data["trades"], list):
            raise ValueError("Root object must contain a 'trades' array")
        required_fields = [
            "trade_id", "ticker", "company", "side", "date",
            "quantity", "price", "currency", "fees", "session_refs", "thesis_snapshot"
        ]
        for i, trade in enumerate(data["trades"]):
            for field in required_fields:
                if field not in trade:
                    raise ValueError(f"Missing required field in trades[{i}]: {field}")
            if trade["side"] not in ["buy", "sell"]:
                raise ValueError(f"Invalid side in trades[{i}]: {trade['side']}")
            if not isinstance(trade["quantity"], int) or trade["quantity"] <= 0:
                raise ValueError(f"Quantity must be a positive integer in trades[{i}]")
        return True
    except Exception as e:
        raise ValueError(f"Schema validation failed: {e}")

def load_trades():
    if not os.path.exists(TRADES_PATH):
        return {"trades": []}
    try:
        with open(TRADES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            validate_trade_data(data)
            return data
    except Exception as e:
        print(f"Warning: Failed to load trades safely, returning empty list. Error: {e}", file=sys.stderr)
        return {"trades": []}

def save_trades(data):
    validate_trade_data(data)
    os.makedirs(os.path.dirname(TRADES_PATH), exist_ok=True)
    with open(TRADES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    update_index_trade_count(len(data["trades"]))

def update_index_trade_count(count):
    if not os.path.exists(INDEX_PATH):
        return
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index_data = json.load(f)
        index_data["trade_count"] = count
        
        # 時系列更新
        import datetime as dt
        jst_timezone = dt.timezone(dt.timedelta(hours=9))
        index_data["last_updated"] = dt.datetime.now(jst_timezone).isoformat()
        
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: Failed to update index trade count: {e}", file=sys.stderr)

def generate_trade_id(trades):
    if not trades:
        return "t001"
    ids = []
    for t in trades:
        tid = t.get("trade_id", "t000")
        if tid.startswith("t") and tid[1:].isdigit():
            ids.append(int(tid[1:]))
    next_id = max(ids) + 1 if ids else 1
    return f"t{next_id:03d}"

def calculate_pnl(trades_list, filter_ticker=None):
    """
    移動平均法を用いて銘柄ごとのポジション（保有数、平均取得単価）および
    実現損益（P&L）を計算する。
    """
    # 日付とID順にソートして時系列に処理する
    sorted_trades = sorted(trades_list, key=lambda x: (x["date"], x["trade_id"]))
    
    positions = {}  # {ticker: {"qty": int, "avg_price": float}}
    realized_pnl = {}  # {ticker: float}
    pnl_details = []  # 各取引の実現損益詳細
    
    for t in sorted_trades:
        ticker = t["ticker"]
        side = t["side"]
        qty = t["quantity"]
        price = t["price"]
        fees = t["fees"]
        
        if ticker not in positions:
            positions[ticker] = {"qty": 0, "avg_price": 0.0}
            realized_pnl[ticker] = 0.0
            
        pos = positions[ticker]
        pnl = 0.0
        
        if side == "buy":
            # 買い：ポジション追加、平均取得単価更新
            new_qty = pos["qty"] + qty
            if new_qty > 0:
                pos["avg_price"] = (pos["qty"] * pos["avg_price"] + qty * price + fees) / new_qty
            pos["qty"] = new_qty
        elif side == "sell":
            # 売り：実現損益の確定、ポジション減少
            if pos["qty"] < qty:
                # 警告を出すが処理は継続（空売りの可能性、またはデータ不整合）
                avg_p = pos["avg_price"] if pos["qty"] > 0 else price
            else:
                avg_p = pos["avg_price"]
                
            pnl = (price * qty - fees) - (avg_p * qty)
            realized_pnl[ticker] += pnl
            pos["qty"] -= qty
            if pos["qty"] == 0:
                pos["avg_price"] = 0.0
                
        pnl_details.append({
            "trade_id": t["trade_id"],
            "date": t["date"],
            "ticker": ticker,
            "side": side,
            "qty": qty,
            "price": price,
            "pnl": pnl
        })
        
    if filter_ticker:
        positions = {k: v for k, v in positions.items() if k == filter_ticker}
        realized_pnl = {k: v for k, v in realized_pnl.items() if k == filter_ticker}
        pnl_details = [x for x in pnl_details if x["ticker"] == filter_ticker]
        
    return positions, realized_pnl, pnl_details

def handle_add(args):
    data = load_trades()
    trade_id = generate_trade_id(data["trades"])
    
    session_refs = [s.strip() for s in args.session_refs.split(",") if s.strip()] if args.session_refs else []
    
    new_trade = {
        "trade_id": trade_id,
        "ticker": args.ticker,
        "company": args.company,
        "side": args.side,
        "date": args.date,
        "quantity": args.quantity,
        "price": args.price,
        "currency": args.currency,
        "fees": args.fees,
        "session_refs": session_refs,
        "thesis_snapshot": args.thesis_snapshot,
        "notes": args.notes if args.notes else ""
    }
    
    data["trades"].append(new_trade)
    try:
        save_trades(data)
        print(f"SUCCESS: Trade {trade_id} added successfully.")
        # 追加後の銘柄ポジション表示
        positions, _, _ = calculate_pnl(data["trades"], filter_ticker=args.ticker)
        pos = positions.get(args.ticker, {"qty": 0, "avg_price": 0.0})
        print(f"Position for {args.ticker}: Qty={pos['qty']}, AvgPrice={pos['avg_price']:.2f}")
    except Exception as e:
        print(f"Error: Failed to save trade: {e}", file=sys.stderr)
        sys.exit(1)

def handle_list(args):
    data = load_trades()
    if not data["trades"]:
        print("No trades found.")
        return
        
    print(f"{'ID':<6} {'Date':<10} {'Ticker':<10} {'Side':<5} {'Qty':<6} {'Price':<10} {'PNL':<10} {'Company':<20}")
    print("-" * 85)
    
    positions, realized_pnl, pnl_details = calculate_pnl(data["trades"])
    pnl_map = {x["trade_id"]: x["pnl"] for x in pnl_details}
    
    for t in sorted(data["trades"], key=lambda x: (x["date"], x["trade_id"])):
        pnl = pnl_map.get(t["trade_id"], 0.0)
        pnl_str = f"{pnl:+.1f}" if t["side"] == "sell" else "-"
        print(f"{t['trade_id']:<6} {t['date']:<10} {t['ticker']:<10} {t['side']:<5} {t['quantity']:<6} {t['price']:<10.2f} {pnl_str:<10} {t['company']:<20}")

def handle_delete(args):
    data = load_trades()
    initial_count = len(data["trades"])
    data["trades"] = [t for t in data["trades"] if t["trade_id"] != args.id]
    
    if len(data["trades"]) == initial_count:
        print(f"Error: Trade ID {args.id} not found.", file=sys.stderr)
        sys.exit(1)
        
    try:
        save_trades(data)
        print(f"SUCCESS: Trade {args.id} deleted successfully.")
    except Exception as e:
        print(f"Error: Failed to delete trade: {e}", file=sys.stderr)
        sys.exit(1)

def handle_stats(args):
    data = load_trades()
    if not data["trades"]:
        print("No trades found.")
        return
        
    positions, realized_pnl, pnl_details = calculate_pnl(data["trades"], filter_ticker=args.ticker)
    
    print("=== Position Status ===")
    for ticker, pos in positions.items():
        if pos["qty"] > 0:
            print(f"Ticker: {ticker:<10} Qty: {pos['qty']:<6} Avg Price: {pos['avg_price']:.2f}")
            
    print("\n=== Realized P&L Summary ===")
    total_pnl = 0.0
    for ticker, pnl in realized_pnl.items():
        print(f"Ticker: {ticker:<10} Realized P&L: {pnl:+.2f}")
        total_pnl += pnl
    print("-" * 35)
    print(f"Total Realized P&L: {total_pnl:+.2f}")

def main():
    parser = argparse.ArgumentParser(description="Manage stock trade history.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # add command
    parser_add = subparsers.add_parser("add", help="Add a new trade record")
    parser_add.add_argument("--side", choices=["buy", "sell"], required=True)
    parser_add.add_argument("--ticker", required=True)
    parser_add.add_argument("--company", required=True)
    parser_add.add_argument("--date", default=datetime.today().strftime('%Y-%m-%d'))
    parser_add.add_argument("--quantity", type=int, required=True)
    parser_add.add_argument("--price", type=float, required=True)
    parser_add.add_argument("--currency", default="JPY")
    parser_add.add_argument("--fees", type=float, default=0.0)
    parser_add.add_argument("--session-refs", help="Comma-separated session IDs")
    parser_add.add_argument("--thesis-snapshot", required=True)
    parser_add.add_argument("--notes")
    
    # list command
    subparsers.add_parser("list", help="List all trade records")
    
    # delete command
    parser_del = subparsers.add_parser("delete", help="Delete a trade record")
    parser_del.add_argument("--id", required=True, help="Trade ID to delete")
    
    # stats command
    parser_stats = subparsers.add_parser("stats", help="Show trade statistics and P&L")
    parser_stats.add_argument("--ticker", help="Filter statistics by ticker")
    
    args = parser.parse_args()
    
    if args.command == "add":
        handle_add(args)
    elif args.command == "list":
        handle_list(args)
    elif args.command == "delete":
        handle_delete(args)
    elif args.command == "stats":
        handle_stats(args)

if __name__ == "__main__":
    main()
