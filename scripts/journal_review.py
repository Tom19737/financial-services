#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys

# プロジェクトルートとパスの設定
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_DIR = os.path.join(PROJECT_ROOT, "out", "_journal")
INDEX_PATH = os.path.join(JOURNAL_DIR, "index.json")
TRADES_PATH = os.path.join(JOURNAL_DIR, "trades", "trades.json")
REPORTS_DIR = os.path.join(JOURNAL_DIR, "reports")

# trade_manager.pyをインポートするためにsys.pathに追加
sys.path.append(os.path.join(PROJECT_ROOT, "scripts"))
try:
    import trade_manager
except ImportError:
    trade_manager = None

def load_index():
    if not os.path.exists(INDEX_PATH):
        return {"sessions": [], "trade_count": 0, "last_updated": ""}
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load index.json: {e}", file=sys.stderr)
        return {"sessions": [], "trade_count": 0, "last_updated": ""}

def load_trades():
    if trade_manager:
        return trade_manager.load_trades()
    if not os.path.exists(TRADES_PATH):
        return {"trades": []}
    try:
        with open(TRADES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load trades.json: {e}", file=sys.stderr)
        return {"trades": []}

def get_session_decisions(decisions_path):
    full_path = os.path.join(JOURNAL_DIR, decisions_path)
    if not os.path.exists(full_path):
        return []
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("decisions", [])
    except Exception as e:
        print(f"Warning: Failed to load decisions from {decisions_path}: {e}", file=sys.stderr)
        return []

def get_session_summary_preview(summary_path):
    full_path = os.path.join(JOURNAL_DIR, summary_path)
    if not os.path.exists(full_path):
        return "要約ファイルが見つかりません。"
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # YAMLフロントマターを取り除く
        content_lines = []
        in_frontmatter = False
        frontmatter_count = 0
        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                frontmatter_count += 1
                continue
            if not in_frontmatter and frontmatter_count >= 2:
                content_lines.append(line)
        
        content = "".join(content_lines).strip()
        # プレビュー用に最初の数行（最大200文字）を抽出
        if len(content) > 200:
            return content[:200] + "..."
        return content
    except Exception as e:
        return f"要約の読み込みエラー: {e}"

def handle_history(args):
    index_data = load_index()
    sessions = index_data.get("sessions", [])
    
    # 銘柄でフィルタリング
    ticker_upper = args.ticker.upper()
    filtered_sessions = []
    for s in sessions:
        tickers = [t.upper() for t in s.get("tickers", [])]
        if ticker_upper in tickers:
            filtered_sessions.append(s)
            
    if not filtered_sessions:
        print(f"No sessions found for ticker: {args.ticker}")
        return

    # 日付昇順でソート
    filtered_sessions = sorted(filtered_sessions, key=lambda x: x.get("date", ""))
    
    print(f"=== Session History for {args.ticker} (Found {len(filtered_sessions)} sessions) ===")
    for s in filtered_sessions:
        print(f"\nDate: {s['date']}")
        print(f"Session ID: {s['session_id']}")
        print(f"Workflow: {s['workflow']} | Confidence: {s['confidence']}")
        print(f"Tags: {', '.join(s['tags'])}")
        
        # 意思決定ログのロードと表示
        decisions = get_session_decisions(s['decisions_path'])
        if decisions:
            print("Decisions:")
            for d in decisions:
                print(f"  - [{d.get('category', 'N/A')}] {d.get('topic', 'N/A')}")
                print(f"    Q: {d.get('question', 'N/A')}")
                print(f"    A: {d.get('chosen', 'N/A')} (Impact: {d.get('impact', 'medium')})")
                print(f"    Rationale: {d.get('rationale', 'N/A')}")
        else:
            print("Decisions: None")
            
        print("-" * 50)

def parse_date(date_str):
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

def handle_pnl(args):
    trades_data = load_trades()
    trades = trades_data.get("trades", [])
    if not trades:
        print("No trades found.")
        return

    if not trade_manager:
        print("Error: trade_manager.py could not be imported.", file=sys.stderr)
        sys.exit(1)

    # 全取引でP&Lを計算（移動平均の計算は時系列全体が必要）
    positions, realized_pnl, pnl_details = trade_manager.calculate_pnl(trades)
    
    # フィルタ用の期間
    start_date = parse_date(args.start) if args.start else None
    end_date = parse_date(args.end) if args.end else None
    
    filtered_pnl_details = []
    for detail in pnl_details:
        # tickerフィルタ
        if args.ticker and detail["ticker"].upper() != args.ticker.upper():
            continue
        # 日付フィルタ
        detail_date = parse_date(detail["date"])
        if not detail_date:
            continue
        if start_date and detail_date < start_date:
            continue
        if end_date and detail_date > end_date:
            continue
        filtered_pnl_details.append(detail)

    # 期間実現損益の集計
    total_pnl = sum(d["pnl"] for d in filtered_pnl_details if d["side"] == "sell")
    
    print("=== Trade P&L Summary ===")
    if args.ticker:
        print(f"Ticker: {args.ticker.upper()}")
    if args.start or args.end:
        print(f"Period: {args.start or 'Any'} to {args.end or 'Any'}")
    print(f"Total Realized P&L in Period: {total_pnl:+.2f}")
    print("-" * 50)
    
    if filtered_pnl_details:
        print(f"{'ID':<6} {'Date':<10} {'Ticker':<10} {'Side':<5} {'Qty':<6} {'Price':<10} {'PNL':<10}")
        print("-" * 65)
        for d in filtered_pnl_details:
            pnl_val = d["pnl"]
            pnl_str = f"{pnl_val:+.1f}" if d["side"] == "sell" else "-"
            print(f"{d['trade_id']:<6} {d['date']:<10} {d['ticker']:<10} {d['side']:<5} {d['qty']:<6} {d['price']:<10.2f} {pnl_str:<10}")
    else:
        print("No matching trade details in this period.")

def handle_report(args):
    # 月のパース (YYYY-MM)
    try:
        report_year, report_month = map(int, args.month.split("-"))
    except ValueError:
        print("Error: Invalid month format. Use YYYY-MM.", file=sys.stderr)
        sys.exit(1)

    start_date_str = f"{args.month}-01"
    # 次の月の1日の前日を求める
    if report_month == 12:
        next_month_start = datetime.date(report_year + 1, 1, 1)
    else:
        next_month_start = datetime.date(report_year, report_month + 1, 1)
    end_date = next_month_start - datetime.timedelta(days=1)
    end_date_str = end_date.strftime("%Y-%m-%d")

    index_data = load_index()
    sessions = index_data.get("sessions", [])
    trades_data = load_trades()
    trades = trades_data.get("trades", [])

    # 1. 当月セッションの抽出
    monthly_sessions = []
    for s in sessions:
        s_date = s.get("date", "")
        if s_date.startswith(args.month):
            monthly_sessions.append(s)

    # 2. 当月取引の抽出
    monthly_trades = []
    for t in trades:
        t_date = t.get("date", "")
        if t_date.startswith(args.month):
            monthly_trades.append(t)

    # 3. 意思決定ログの集約 (Impact: High/Medium)
    monthly_decisions = []
    for s in monthly_sessions:
        decisions = get_session_decisions(s['decisions_path'])
        for d in decisions:
            if d.get("impact", "medium").lower() in ["high", "medium"]:
                # セッションIDを付与して保存
                d_copy = d.copy()
                d_copy["session_id"] = s["session_id"]
                monthly_decisions.append(d_copy)

    # 4. P&L計算 (月末時点のポジションと当月の実現損益)
    # 当月末までの全取引をフィルタリングしてポジションを計算
    trades_until_end = []
    for t in trades:
        t_date_parsed = parse_date(t.get("date", ""))
        if t_date_parsed and t_date_parsed <= end_date:
            trades_until_end.append(t)

    if not trade_manager:
        print("Error: trade_manager.py could not be imported.", file=sys.stderr)
        sys.exit(1)

    positions, _, pnl_details = trade_manager.calculate_pnl(trades_until_end)
    
    # 当月内の実現損益のみ集計
    monthly_realized_pnl = 0.0
    pnl_map = {}
    for detail in pnl_details:
        d_date = detail["date"]
        if d_date.startswith(args.month):
            pnl_map[detail["trade_id"]] = detail["pnl"]
            if detail["side"] == "sell":
                monthly_realized_pnl += detail["pnl"]

    # 当月の取引リストに実現損益を紐付ける
    trades_with_pnl = []
    for t in monthly_trades:
        t_copy = t.copy()
        t_copy["pnl"] = pnl_map.get(t["trade_id"], 0.0)
        trades_with_pnl.append(t_copy)

    # 当月のアクティビティ分析
    target_tickers = sorted(list(set(
        [tick for s in monthly_sessions for tick in s.get("tickers", [])] +
        [t["ticker"] for t in monthly_trades]
    )))

    # レポートマークダウンの生成
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    md_content = f"""# 月次振り返りレポート: {report_year}年{report_month:02d}月

生成日時: {now_str} JST

## 1. サマリーメトリクス
- **対象銘柄**: {', '.join(target_tickers) if target_tickers else 'なし'}
- **実施セッション数**: {len(monthly_sessions)} 回
- **取引回数**: {len(monthly_trades)} 回
- **月次実現損益 (P&L)**: {monthly_realized_pnl:+.2f} JPY

## 2. 実施セッション・アクティビティ
{f"| 日付 | セッションID | 銘柄 | ワークフロー | 信頼度 | タグ |" if monthly_sessions else "当月はセッションがありません。"}
{"| --- | --- | --- | --- | --- | --- |" if monthly_sessions else ""}
"""
    for s in monthly_sessions:
        md_content += f"| {s['date']} | [{s['session_id']}](../{s['summary_path']}) | {', '.join(s['tickers'])} | {s['workflow']} | {s['confidence']} | {', '.join(s['tags'])} |\n"

    md_content += f"""
## 3. 下された主要な意思決定 (Impact: High/Medium)
{f"| セッションID | ID | カテゴリ | トピック | 決定した内容 | 根拠・理由 | 影響度 |" if monthly_decisions else "当月は主要な意思決定がありません。"}
{"| --- | --- | --- | --- | --- | --- | --- |" if monthly_decisions else ""}
"""
    for d in monthly_decisions:
        # 改行などをエスケープ
        rationale = d.get('rationale', '').replace('\n', ' ')
        chosen = str(d.get('chosen', '')).replace('\n', ' ')
        md_content += f"| {d['session_id']} | {d.get('id', 'N/A')} | {d.get('category', 'N/A')} | {d.get('topic', 'N/A')} | {chosen} | {rationale} | {d.get('impact', 'medium')} |\n"

    md_content += f"""
## 4. 取引アクティビティ & 実現損益
{f"| 取引ID | 日付 | 銘柄 | 売買 | 数量 | 価格 | 実現損益 | 投資仮説 |" if monthly_trades else "当月は取引がありません。"}
{"| --- | --- | --- | --- | --- | --- | --- | --- |" if monthly_trades else ""}
"""
    for t in trades_with_pnl:
        pnl_val = t["pnl"]
        pnl_str = f"{pnl_val:+.1f}" if t["side"] == "sell" else "-"
        thesis = t.get("thesis_snapshot", "").replace('\n', ' ')
        md_content += f"| {t['trade_id']} | {t['date']} | {t['ticker']} | {t['side']} | {t['quantity']} | {t['price']:.2f} | {pnl_str} | {thesis} |\n"

    md_content += f"""
## 5. 月末時点の保有ポジション状況
{f"| 銘柄 | 保有数量 | 平均取得単価 |" if positions else "保有ポジションはありません。"}
{"| --- | --- | --- |" if positions else ""}
"""
    for ticker, pos in sorted(positions.items()):
        if pos["qty"] > 0:
            md_content += f"| {ticker} | {pos['qty']} | {pos['avg_price']:.2f} |\n"

    md_content += """
## 6. 自己反省と今後の課題 (要編集)
- **分析の精度とバイアスについて**:
  - *ここに当月の分析の妥当性、前提（WACCや成長率など）の適切性に関する考察を記入してください。*
- **取引実行と意思決定の整合性**:
  - *分析結果（セッションの判断）と、実際の取引（エントリー・エグジットのタイミング）がどの程度整合していたかを評価してください。*
- **次月の注力アクション**:
  - *次月にフォローアップすべき銘柄や、アップデートが必要なモデルなどのアクションプランを記述してください。*
"""

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_filename = f"monthly_{args.month}.md"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"SUCCESS: Monthly report generated at {report_path}")
    except Exception as e:
        print(f"Error: Failed to save monthly report: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Review stock journal and trade history.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # history コマンド
    parser_history = subparsers.add_parser("history", help="Show session history and decisions for a ticker")
    parser_history.add_argument("--ticker", required=True, help="Stock ticker symbol")
    
    # pnl コマンド
    parser_pnl = subparsers.add_parser("pnl", help="Show trade realized P&L and metrics")
    parser_pnl.add_argument("--ticker", help="Filter by stock ticker symbol")
    parser_pnl.add_argument("--start", help="Filter by start date (YYYY-MM-DD)")
    parser_pnl.add_argument("--end", help="Filter by end date (YYYY-MM-DD)")
    
    # report コマンド
    parser_report = subparsers.add_parser("report", help="Generate monthly review report")
    parser_report.add_argument("--month", required=True, help="Target month (YYYY-MM)")
    
    args = parser.parse_args()
    
    if args.command == "history":
        handle_history(args)
    elif args.command == "pnl":
        handle_pnl(args)
    elif args.command == "report":
        handle_report(args)

if __name__ == "__main__":
    main()
