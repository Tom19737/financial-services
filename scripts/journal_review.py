#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys
import re
import csv
import yfinance as yf

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

def load_session_json(decisions_path):
    full_path = os.path.join(JOURNAL_DIR, decisions_path)
    if not os.path.exists(full_path):
        return {}
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load session json from {decisions_path}: {e}", file=sys.stderr)
        return {}

def get_current_price(ticker_str):
    ticker_str = ticker_str.strip()
    if len(ticker_str) == 4 and ticker_str[0].isdigit() and ticker_str.isalnum():
        ticker_str = f"{ticker_str}.T"
    try:
        ticker = yf.Ticker(ticker_str)
        info_data = ticker.info
        latest_price = info_data.get("currentPrice") or info_data.get("regularMarketPrice")
        if latest_price is None:
            hist = ticker.history(period="1d")
            if not hist.empty:
                latest_price = float(hist["Close"].iloc[-1])
        return latest_price
    except Exception as e:
        print(f"Warning: Failed to fetch current price for {ticker_str}: {e}", file=sys.stderr)
        return None

def determine_direction(decision):
    category = decision.get("category", "").lower()
    topic = decision.get("topic", "").lower()
    question = decision.get("question", "").lower()
    chosen = str(decision.get("chosen", "")).lower()
    
    # ロング（強気）キーワード
    long_keywords = ["買", "buy", "long", "強気", "bull", "追加", "エントリー", "intact"]
    # ショート/エグジット（弱気・売却）キーワード
    short_keywords = ["売", "sell", "short", "弱気", "bear", "損切", "利確", "エグジット", "broken"]
    
    is_long = False
    is_short = False
    
    for kw in long_keywords:
        if kw in chosen or kw in topic or kw in question:
            is_long = True
            break
    if category == "conclusion" and not is_long:
        is_long = True
        
    for kw in short_keywords:
        if kw in chosen or kw in topic or kw in question:
            is_short = True
            is_long = False
            break
            
    if is_long:
        return "long"
    elif is_short:
        return "short"
    return "N/A"

def handle_verify(args):
    index_data = load_index()
    sessions = index_data.get("sessions", [])
    if not sessions:
        print("No sessions found in index.")
        return

    # 全意思決定を収集
    all_decisions = []
    tickers = set()
    for s in sessions:
        session_data = load_session_json(s['decisions_path'])
        decisions = session_data.get("decisions", [])
        price_at_session = session_data.get("price_at_session")
        
        session_tickers = s.get("tickers", [])
        ticker = session_tickers[0] if session_tickers else "N/A"
        if ticker != "N/A":
            tickers.add(ticker)

        for d in decisions:
            d_copy = d.copy()
            d_copy["session_id"] = s["session_id"]
            d_copy["date"] = s["date"]
            d_copy["ticker"] = ticker
            d_copy["price_at_session"] = price_at_session
            all_decisions.append(d_copy)

    if not all_decisions:
        print("No decisions found in any sessions.")
        return

    print("Fetching current market prices...")
    current_prices = {}
    for t in sorted(tickers):
        price = get_current_price(t)
        if price is not None:
            current_prices[t] = price
            print(f"  {t}: {price:.2f}")
        else:
            print(f"  {t}: Fetch failed")

    print("\n=== Decision Performance Verification ===")
    print(f"{'Date':<10} {'Ticker':<8} {'Topic':<15} {'Conf':<6} {'Dir':<5} {'Prev Px':<10} {'Curr Px':<10} {'Diff %':<8} {'Result':<8}")
    print("-" * 90)

    # 信頼度別の集計辞書
    stats = {
        "high": {"success": 0, "failed": 0, "flat": 0, "na": 0},
        "medium": {"success": 0, "failed": 0, "flat": 0, "na": 0},
        "low": {"success": 0, "failed": 0, "flat": 0, "na": 0}
    }

    for d in all_decisions:
        ticker = d["ticker"]
        prev_price = d["price_at_session"]
        curr_price = current_prices.get(ticker) if ticker != "N/A" else None
        
        direction = determine_direction(d)
        result = "N/A"
        diff_pct_str = "-"
        
        if prev_price is not None and curr_price is not None and prev_price > 0:
            diff_pct = ((curr_price - prev_price) / prev_price) * 100
            diff_pct_str = f"{diff_pct:+.1f}%"
            
            if direction == "long":
                if curr_price > prev_price:
                    result = "Success"
                elif curr_price < prev_price:
                    result = "Failed"
                else:
                    result = "Flat"
            elif direction == "short":
                if curr_price < prev_price:
                    result = "Success"
                elif curr_price > prev_price:
                    result = "Failed"
                else:
                    result = "Flat"
            else:
                result = "N/A"
        else:
            result = "N/A"
            
        conf = d.get("confidence", "medium").lower()
        if conf not in stats:
            conf = "medium"
            
        if result == "Success":
            stats[conf]["success"] += 1
        elif result == "Failed":
            stats[conf]["failed"] += 1
        elif result == "Flat":
            stats[conf]["flat"] += 1
        else:
            stats[conf]["na"] += 1

        prev_price_str = f"{prev_price:.2f}" if prev_price is not None else "-"
        curr_price_str = f"{curr_price:.2f}" if curr_price is not None else "-"
        topic = d.get("topic", "N/A")
        if len(topic) > 15:
            topic = topic[:12] + "..."
            
        print(f"{d['date']:<10} {ticker:<8} {topic:<15} {conf:<6} {direction:<5} {prev_price_str:<10} {curr_price_str:<10} {diff_pct_str:<8} {result:<8}")

    print("\n=== Summary by Confidence ===")
    print(f"{'Confidence':<12} {'Success':<8} {'Failed':<8} {'Flat':<8} {'N/A':<8} {'Accuracy':<8}")
    print("-" * 55)
    
    total_success = 0
    total_failed = 0
    total_flat = 0
    total_na = 0
    
    for level in ["high", "medium", "low"]:
        s_count = stats[level]["success"]
        f_count = stats[level]["failed"]
        fl_count = stats[level]["flat"]
        na_count = stats[level]["na"]
        
        total_success += s_count
        total_failed += f_count
        total_flat += fl_count
        total_na += na_count
        
        denom = s_count + f_count
        accuracy_str = f"{(s_count / denom) * 100:.1f}%" if denom > 0 else "-"
        print(f"{level.capitalize():<12} {s_count:<8} {f_count:<8} {fl_count:<8} {na_count:<8} {accuracy_str:<8}")
        
    print("-" * 55)
    total_denom = total_success + total_failed
    total_accuracy_str = f"{(total_success / total_denom) * 100:.1f}%" if total_denom > 0 else "-"
    print(f"{'Total':<12} {total_success:<8} {total_failed:<8} {total_flat:<8} {total_na:<8} {total_accuracy_str:<8}")

def find_company_data_dir(ticker_symbol):
    ticker_symbol = ticker_symbol.strip()
    if len(ticker_symbol) == 4 and ticker_symbol[0].isdigit() and ticker_symbol.isalnum():
        ticker_symbol = f"{ticker_symbol}.T"
        
    out_dir = os.path.join(PROJECT_ROOT, "out")
    if not os.path.exists(out_dir):
        return None
    for item in os.listdir(out_dir):
        item_path = os.path.join(out_dir, item)
        if os.path.isdir(item_path):
            if item.startswith(f"{ticker_symbol}_") or item == ticker_symbol:
                return item_path
    return None

def calculate_actual_metrics(ticker_symbol):
    metrics = {"revenue_growth": None, "ebitda_margin": None}
    company_dir = find_company_data_dir(ticker_symbol)
    if not company_dir:
        return metrics
        
    csv_path = os.path.join(company_dir, "market_data", "annual_income_stmt.csv")
    if not os.path.exists(csv_path):
        return metrics
        
    try:
        row_data = {}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                row_name = row[0].strip().lower()
                row_data[row_name] = row[1:]
                
        revenue_row = None
        for name, val in row_data.items():
            if "total revenue" in name or "operating revenue" in name:
                revenue_row = val
                break
                
        ebitda_row = None
        for name, val in row_data.items():
            if "ebitda" in name:
                ebitda_row = val
                break
                
        def parse_values(row_val):
            parsed = []
            for v in row_val:
                v_clean = v.strip()
                if v_clean:
                    try:
                        parsed.append(float(v_clean))
                    except ValueError:
                        parsed.append(None)
                else:
                    parsed.append(None)
            return parsed
            
        if revenue_row:
            rev_vals = parse_values(revenue_row)
            valid_revs = [r for r in rev_vals if r is not None]
            if len(valid_revs) >= 2:
                metrics["revenue_growth"] = (valid_revs[0] - valid_revs[1]) / valid_revs[1]
                
        if ebitda_row and revenue_row:
            ebitda_vals = parse_values(ebitda_row)
            rev_vals = parse_values(revenue_row)
            if ebitda_vals and rev_vals and ebitda_vals[0] is not None and rev_vals[0] is not None and rev_vals[0] > 0:
                metrics["ebitda_margin"] = ebitda_vals[0] / rev_vals[0]
                
    except Exception as e:
        print(f"Warning: Failed to parse financial statements for {ticker_symbol}: {e}", file=sys.stderr)
        
    return metrics

def extract_numeric_percentage(chosen_str):
    if not chosen_str:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", chosen_str)
    if match:
        return float(match.group(1)) / 100.0
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", chosen_str)
    if match:
        val = float(match.group(1))
        if val > 1.0:
            return val / 100.0
        return val
    return None

def handle_assumptions(args):
    index_data = load_index()
    sessions = index_data.get("sessions", [])
    if not sessions:
        print("No sessions found in index.")
        return

    all_assumptions = []
    for s in sessions:
        session_data = load_session_json(s['decisions_path'])
        decisions = session_data.get("decisions", [])
        
        session_tickers = s.get("tickers", [])
        ticker = session_tickers[0] if session_tickers else "N/A"
        
        for d in decisions:
            if d.get("category", "").lower() == "assumption":
                d_copy = d.copy()
                d_copy["session_id"] = s["session_id"]
                d_copy["date"] = s["date"]
                d_copy["ticker"] = ticker
                all_assumptions.append(d_copy)

    if not all_assumptions:
        print("No assumptions found in any sessions.")
        return

    grouped = {}
    for a in all_assumptions:
        ticker = a["ticker"]
        topic = a.get("topic", "").lower()
        question = a.get("question", "").lower()
        
        group_name = "Other"
        if any(w in topic or w in question for w in ["wacc", "割引率", "資本コスト", "cost of capital"]):
            group_name = "WACC"
        elif any(w in topic or w in question for w in ["成長", "growth", "売上", "revenue"]):
            group_name = "Revenue Growth"
        elif any(w in topic or w in question for w in ["マージン", "margin", "利益率", "ebitda"]):
            group_name = "Margin"
            
        key = (ticker, group_name)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(a)

    print("=== Investment Assumptions and Variance Analysis ===")
    
    for (ticker, group_name), items in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        items_sorted = sorted(items, key=lambda x: x.get("date", ""))
        
        print(f"\n[{ticker}] Indicator: {group_name}")
        print("-" * 80)
        print(f"{'Date':<10} {'Topic':<15} {'Assumption':<12} {'Actual':<10} {'Variance':<10} {'Rationale'}")
        print("-" * 80)
        
        actual_val = None
        if ticker != "N/A":
            actual_metrics = calculate_actual_metrics(ticker)
            if group_name == "Revenue Growth":
                actual_val = actual_metrics["revenue_growth"]
            elif group_name == "Margin":
                actual_val = actual_metrics["ebitda_margin"]
        
        for item in items_sorted:
            chosen = item.get("chosen", "")
            assumed_num = extract_numeric_percentage(chosen)
            
            actual_str = "-"
            variance_str = "-"
            
            if actual_val is not None and assumed_num is not None:
                actual_str = f"{actual_val * 100:.1f}%"
                variance = (assumed_num - actual_val) * 100
                variance_str = f"{variance:+.1f}%"
            elif group_name in ["Revenue Growth", "Margin"] and actual_val is None:
                actual_str = "N/A"
                
            topic = item.get("topic", "N/A")
            if len(topic) > 15:
                topic = topic[:12] + "..."
                
            rationale = item.get("rationale", "N/A").replace("\n", " ")
            if len(rationale) > 30:
                rationale = rationale[:27] + "..."
                
            print(f"{item['date']:<10} {topic:<15} {chosen:<12} {actual_str:<10} {variance_str:<10} {rationale}")
            
        if len(items_sorted) > 1:
            timeline = " -> ".join([item.get("chosen", "") for item in items_sorted])
            print(f"Timeline: {timeline}")

def load_company_sector(ticker_symbol):
    company_dir = find_company_data_dir(ticker_symbol)
    if not company_dir:
        return "Unknown"
    summary_path = os.path.join(company_dir, "market_data", "summary.json")
    if not os.path.exists(summary_path):
        return "Unknown"
    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("sector") or "Unknown"
    except Exception:
        return "Unknown"

def analyze_trade_holding_periods(trades):
    by_ticker = {}
    for t in trades:
        ticker = t["ticker"]
        if ticker not in by_ticker:
            by_ticker[ticker] = []
        by_ticker[ticker].append(t)
        
    profit_trades = []
    loss_trades = []
    flat_trades = []
    total_weighted_days = 0.0
    total_sold_qty = 0
    
    current_positions = {}
    
    for ticker, t_list in by_ticker.items():
        t_list_sorted = sorted(t_list, key=lambda x: x.get("date", ""))
        buy_queue = []
        
        for t in t_list_sorted:
            side = t["side"].lower()
            qty = int(t["quantity"])
            price = float(t["price"])
            t_date = parse_date(t["date"])
            if not t_date:
                continue
                
            if side == "buy":
                buy_queue.append({"date": t_date, "qty": qty, "price": price})
            elif side == "sell":
                rem_qty = qty
                weighted_days_sum = 0.0
                cost_sum = 0.0
                sold_qty_actual = 0
                
                while buy_queue and rem_qty > 0:
                    buy_item = buy_queue[0]
                    consume_qty = min(rem_qty, buy_item["qty"])
                    
                    days = (t_date - buy_item["date"]).days
                    weighted_days_sum += days * consume_qty
                    cost_sum += buy_item["price"] * consume_qty
                    sold_qty_actual += consume_qty
                    
                    buy_item["qty"] -= consume_qty
                    rem_qty -= consume_qty
                    if buy_item["qty"] == 0:
                        buy_queue.pop(0)
                        
                if sold_qty_actual > 0:
                    avg_days = weighted_days_sum / sold_qty_actual
                    revenue = price * sold_qty_actual
                    pnl = revenue - cost_sum
                    pnl_rate = pnl / cost_sum if cost_sum > 0 else 0.0
                    
                    trade_summary = {
                        "holding_days": avg_days,
                        "pnl_rate": pnl_rate,
                        "pnl": pnl,
                        "qty": sold_qty_actual
                    }
                    
                    if pnl > 0:
                        profit_trades.append(trade_summary)
                    elif pnl < 0:
                        loss_trades.append(trade_summary)
                    else:
                        flat_trades.append(trade_summary)
                        
                    total_weighted_days += weighted_days_sum
                    total_sold_qty += sold_qty_actual
                    
        remaining_qty = sum(item["qty"] for item in buy_queue)
        remaining_cost = sum(item["qty"] * item["price"] for item in buy_queue)
        if remaining_qty > 0:
            current_positions[ticker] = {
                "qty": remaining_qty,
                "cost": remaining_cost
            }
            
    return profit_trades, loss_trades, flat_trades, total_weighted_days, total_sold_qty, current_positions

def handle_biases(args):
    index_data = load_index()
    sessions = index_data.get("sessions", [])
    
    long_count = 0
    short_count = 0
    na_count = 0
    
    for s in sessions:
        session_data = load_session_json(s['decisions_path'])
        decisions = session_data.get("decisions", [])
        for d in decisions:
            direction = determine_direction(d)
            if direction == "long":
                long_count += 1
            elif direction == "short":
                short_count += 1
            else:
                na_count += 1
                
    total_decisions = long_count + short_count
    buy_ratio = long_count / total_decisions if total_decisions > 0 else 0.0
    
    print("=== Investment Biases Analysis ===")
    print("\n[1] Decision Bias (Optimism Analysis)")
    print("-" * 50)
    print(f"Total Directional Decisions: {total_decisions}")
    print(f"  - Long (Buy) Decisions  : {long_count} ({buy_ratio * 100:.1f}%)")
    print(f"  - Short (Sell) Decisions: {short_count} ({(1 - buy_ratio) * 100:.1f}%)")
    
    if total_decisions >= 3 and buy_ratio > 0.8:
        print("\n>> [ALERT] Optimism Bias detected!")
        print("   Almost all of your investment decisions are biased towards buying/bullish scenarios.")
        print("   Make sure you are not ignoring downside risks or selling opportunities.")
    else:
        print("\n>> Decision bias is within normal range.")
        
    trades_data = load_trades()
    trades = trades_data.get("trades", [])
    
    print("\n[2] Holding Period & Disposition Effect Analysis")
    print("-" * 50)
    
    if not trades:
        print("No trade history available for holding period analysis.")
    else:
        profit_trades, loss_trades, flat_trades, total_weighted_days, total_sold_qty, current_positions = analyze_trade_holding_periods(trades)
        
        profit_qty_sum = sum(t["qty"] for t in profit_trades)
        loss_qty_sum = sum(t["qty"] for t in loss_trades)
        
        profit_avg_days = sum(t["holding_days"] * t["qty"] for t in profit_trades) / profit_qty_sum if profit_qty_sum > 0 else 0.0
        loss_avg_days = sum(t["holding_days"] * t["qty"] for t in loss_trades) / loss_qty_sum if loss_qty_sum > 0 else 0.0
        
        profit_avg_rate = sum(t["pnl_rate"] * t["qty"] for t in profit_trades) / profit_qty_sum if profit_qty_sum > 0 else 0.0
        loss_avg_rate = sum(t["pnl_rate"] * t["qty"] for t in loss_trades) / loss_qty_sum if loss_qty_sum > 0 else 0.0
        
        overall_avg_days = total_weighted_days / total_sold_qty if total_sold_qty > 0 else 0.0
        
        print(f"Total Sold Volume      : {total_sold_qty} shares")
        print(f"Overall Average Holding: {overall_avg_days:.1f} days")
        print(f"Realized Profit Trades : {len(profit_trades)} items (Vol: {profit_qty_sum} shares)")
        print(f"  - Avg Holding Period : {profit_avg_days:.1f} days")
        print(f"  - Avg Profit Rate    : {profit_avg_rate * 100:+.1f}%")
        print(f"Realized Loss Trades   : {len(loss_trades)} items (Vol: {loss_qty_sum} shares)")
        print(f"  - Avg Holding Period : {loss_avg_days:.1f} days")
        print(f"  - Avg Loss Rate      : {loss_avg_rate * 100:+.1f}%")
        
        if loss_qty_sum > 0 and profit_qty_sum > 0 and loss_avg_days > profit_avg_days * 1.5:
            ratio = loss_avg_days / profit_avg_days if profit_avg_days > 0 else 0.0
            print("\n>> [ALERT] Disposition Effect (Loss Aversion) detected!")
            print(f"   Your average loss-holding period is {ratio:.1f}x longer than profit-holding period.")
            print("   You might be holding onto losing positions too long (塩漬け) while selling winners too quickly.")
        else:
            print("\n>> Holding period pattern is within normal range.")

        print("\n[3] Sector Concentration Analysis")
        print("-" * 50)
        
        if not current_positions:
            print("No active positions held for sector analysis.")
        else:
            sector_costs = {}
            total_portfolio_cost = 0.0
            
            for ticker, pos in current_positions.items():
                sector = load_company_sector(ticker)
                cost = pos["cost"]
                sector_costs[sector] = sector_costs.get(sector, 0.0) + cost
                total_portfolio_cost += cost
                
            print(f"{'Sector':<25} {'Cost Value (JPY)':<20} {'Weight'}")
            print("-" * 55)
            
            max_sector = None
            max_sector_ratio = 0.0
            
            for sector, cost in sorted(sector_costs.items(), key=lambda x: x[1], reverse=True):
                ratio = cost / total_portfolio_cost if total_portfolio_cost > 0 else 0.0
                if ratio > max_sector_ratio:
                    max_sector_ratio = ratio
                    max_sector = sector
                print(f"{sector:<25} {cost:<20.2f} {ratio * 100:.1f}%")
                
            if total_portfolio_cost > 0 and max_sector_ratio > 0.5:
                print(f"\n>> [ALERT] Sector Concentration Bias detected!")
                print(f"   {max_sector_ratio * 100:.1f}% of your portfolio cost is concentrated in '{max_sector}'.")
                print("   Consider diversifying to mitigate sector-specific macro risks.")
            else:
                print("\n>> Portfolio concentration is within normal range.")

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
    
    # verify コマンド
    parser_verify = subparsers.add_parser("verify", help="Verify decisions performance against current prices")
    
    # assumptions コマンド
    parser_assumptions = subparsers.add_parser("assumptions", help="Verify assumptions variance against actual values")
    
    # biases コマンド
    parser_biases = subparsers.add_parser("biases", help="Analyze investment behavior biases")
    
    args = parser.parse_args()
    
    if args.command == "history":
        handle_history(args)
    elif args.command == "pnl":
        handle_pnl(args)
    elif args.command == "report":
        handle_report(args)
    elif args.command == "verify":
        handle_verify(args)
    elif args.command == "assumptions":
        handle_assumptions(args)
    elif args.command == "biases":
        handle_biases(args)

if __name__ == "__main__":
    main()
