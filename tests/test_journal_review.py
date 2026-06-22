import os
import json
import pytest
import datetime
from unittest import mock
import sys

# テスト対象モジュールのパスを通す
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))
import journal_review

@pytest.fixture
def mock_journal_env(tmp_path, monkeypatch):
    """
    テスト用の一時的なジャーナル環境を構築し、
    journal_review のファイルパス変数を差し替えます。
    """
    journal_dir = tmp_path / "_journal"
    journal_dir.mkdir()
    
    sessions_dir = journal_dir / "sessions"
    sessions_dir.mkdir()
    
    trades_dir = journal_dir / "trades"
    trades_dir.mkdir()
    
    reports_dir = journal_dir / "reports"
    reports_dir.mkdir()
    
    index_path = journal_dir / "index.json"
    trades_path = trades_dir / "trades.json"
    
    monkeypatch.setattr(journal_review, "JOURNAL_DIR", str(journal_dir))
    monkeypatch.setattr(journal_review, "INDEX_PATH", str(index_path))
    monkeypatch.setattr(journal_review, "TRADES_PATH", str(trades_path))
    monkeypatch.setattr(journal_review, "REPORTS_DIR", str(reports_dir))
    
    if journal_review.trade_manager:
        monkeypatch.setattr(journal_review.trade_manager, "JOURNAL_DIR", str(journal_dir))
        monkeypatch.setattr(journal_review.trade_manager, "TRADES_PATH", str(trades_path))
    
    return {
        "journal_dir": journal_dir,
        "sessions_dir": sessions_dir,
        "trades_dir": trades_dir,
        "reports_dir": reports_dir,
        "index_path": index_path,
        "trades_path": trades_path,
    }

def test_load_index_not_exist(mock_journal_env):
    data = journal_review.load_index()
    assert data == {"sessions": [], "trade_count": 0, "last_updated": ""}

def test_load_index_broken(mock_journal_env):
    mock_journal_env["index_path"].write_text("{broken_json", encoding="utf-8")
    data = journal_review.load_index()
    assert data == {"sessions": [], "trade_count": 0, "last_updated": ""}

def test_load_index_exist(mock_journal_env):
    expected = {"sessions": [{"session_id": "test_s1"}], "trade_count": 1, "last_updated": "2026-06-22"}
    mock_journal_env["index_path"].write_text(json.dumps(expected), encoding="utf-8")
    data = journal_review.load_index()
    assert data == expected

def test_load_trades_not_exist(mock_journal_env):
    # trade_manager がロードされているかによって挙動が変わる可能性があるため、
    # trade_manager が存在しない/モックされる前提でも安全にチェック
    with mock.patch("journal_review.trade_manager", None):
        data = journal_review.load_trades()
        assert data == {"trades": []}

def test_load_trades_broken(mock_journal_env):
    with mock.patch("journal_review.trade_manager", None):
        mock_journal_env["trades_path"].write_text("{broken", encoding="utf-8")
        data = journal_review.load_trades()
        assert data == {"trades": []}

def test_load_trades_exist(mock_journal_env):
    expected = {"trades": [{"trade_id": "t001"}]}
    with mock.patch("journal_review.trade_manager", None):
        mock_journal_env["trades_path"].write_text(json.dumps(expected), encoding="utf-8")
        data = journal_review.load_trades()
        assert data == expected

def test_get_session_decisions_not_exist(mock_journal_env):
    decisions = journal_review.get_session_decisions("sessions/non_exist_decisions.json")
    assert decisions == []

def test_get_session_decisions_broken(mock_journal_env):
    dec_file = mock_journal_env["sessions_dir"] / "broken_decisions.json"
    dec_file.write_text("{broken", encoding="utf-8")
    dec_path = "sessions/broken_decisions.json"
    decisions = journal_review.get_session_decisions(dec_path)
    assert decisions == []

def test_get_session_decisions_exist(mock_journal_env):
    expected = {"decisions": [{"id": "d001", "topic": "test"}]}
    dec_file = mock_journal_env["sessions_dir"] / "test_decisions.json"
    dec_file.write_text(json.dumps(expected), encoding="utf-8")
    
    dec_path = "sessions/test_decisions.json"
    decisions = journal_review.get_session_decisions(dec_path)
    assert decisions == expected["decisions"]

def test_get_session_summary_preview_not_exist(mock_journal_env):
    preview = journal_review.get_session_summary_preview("sessions/non_exist.md")
    assert "要約ファイルが見つかりません" in preview

def test_get_session_summary_preview_exist(mock_journal_env):
    md_content = """---
session_id: test
---

# Title
This is the main body. It has some text.
"""
    md_file = mock_journal_env["sessions_dir"] / "test.md"
    md_file.write_text(md_content, encoding="utf-8")
    
    preview = journal_review.get_session_summary_preview("sessions/test.md")
    assert "# Title" in preview
    assert "This is the main body" in preview

def test_handle_history_no_sessions(mock_journal_env, capsys):
    args = argparse_namespace(ticker="285A.T")
    journal_review.handle_history(args)
    captured = capsys.readouterr()
    assert "No sessions found" in captured.out

def test_handle_history_with_sessions(mock_journal_env, capsys):
    index_data = {
        "sessions": [
            {
                "session_id": "2026-06-22T10-00_285A.T_dcf",
                "date": "2026-06-22",
                "tickers": ["285A.T"],
                "companies": ["Kioxia"],
                "workflow": "dcf",
                "trigger": "manual",
                "confidence": "high",
                "tags": ["NAND"],
                "summary_path": "sessions/2026-06-22T10-00_285A.T_dcf.md",
                "decisions_path": "sessions/2026-06-22T10-00_285A.T_dcf_decisions.json",
                "artifact_paths": []
            }
        ],
        "trade_count": 0,
        "last_updated": ""
    }
    mock_journal_env["index_path"].write_text(json.dumps(index_data), encoding="utf-8")
    
    # Decisionsも用意
    decisions_data = {
        "decisions": [
            {
                "id": "d001",
                "category": "assumption",
                "topic": "WACC",
                "question": "WACC setting?",
                "chosen": "5.0%",
                "rationale": "JGB WACC base",
                "impact": "high"
            }
        ]
    }
    dec_file = mock_journal_env["sessions_dir"] / "2026-06-22T10-00_285A.T_dcf_decisions.json"
    dec_file.write_text(json.dumps(decisions_data), encoding="utf-8")
    
    args = argparse_namespace(ticker="285A.T")
    journal_review.handle_history(args)
    captured = capsys.readouterr()
    
    assert "Session History for 285A.T" in captured.out
    assert "Workflow: dcf" in captured.out
    assert "WACC setting?" in captured.out
    assert "5.0%" in captured.out

def test_handle_pnl_no_trades(mock_journal_env, capsys):
    with mock.patch("journal_review.load_trades") as mock_load:
        mock_load.return_value = {"trades": []}
        args = argparse_namespace(ticker=None, start=None, end=None)
        journal_review.handle_pnl(args)
        captured = capsys.readouterr()
        assert "No trades found." in captured.out

def test_handle_pnl_with_trades(mock_journal_env, capsys):
    trades = {
        "trades": [
            {
                "trade_id": "t001",
                "ticker": "285A.T",
                "company": "Kioxia",
                "side": "buy",
                "date": "2026-06-01",
                "quantity": 100,
                "price": 1000.0,
                "currency": "JPY",
                "fees": 10.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            },
            {
                "trade_id": "t002",
                "ticker": "285A.T",
                "company": "Kioxia",
                "side": "sell",
                "date": "2026-06-15",
                "quantity": 100,
                "price": 1200.0,
                "currency": "JPY",
                "fees": 10.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            }
        ]
    }
    
    with mock.patch("journal_review.load_trades", return_value=trades):
        # trade_manager が正常に機能している前提
        args = argparse_namespace(ticker=None, start=None, end=None)
        journal_review.handle_pnl(args)
        captured = capsys.readouterr()
        
        assert "Trade P&L Summary" in captured.out
        # 1200 * 100 - 10 = 119990
        # 1000 * 100 + 10 = 100010
        # pnl = 119990 - 100010 = +19980
        assert "Total Realized P&L in Period: +19980.00" in captured.out
        assert "t001" in captured.out
        assert "t002" in captured.out

def test_handle_pnl_with_filters(mock_journal_env, capsys):
    trades = {
        "trades": [
            {
                "trade_id": "t001",
                "ticker": "285A.T",
                "company": "Kioxia",
                "side": "buy",
                "date": "2026-06-01",
                "quantity": 100,
                "price": 1000.0,
                "currency": "JPY",
                "fees": 10.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            },
            {
                "trade_id": "t002",
                "ticker": "7203.T",
                "company": "Toyota",
                "side": "buy",
                "date": "2026-06-05",
                "quantity": 50,
                "price": 2000.0,
                "currency": "JPY",
                "fees": 5.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            },
            {
                "trade_id": "t003",
                "ticker": "285A.T",
                "company": "Kioxia",
                "side": "sell",
                "date": "2026-06-15",
                "quantity": 100,
                "price": 1200.0,
                "currency": "JPY",
                "fees": 10.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            }
        ]
    }
    
    with mock.patch("journal_review.load_trades", return_value=trades):
        # tickerフィルタ
        args = argparse_namespace(ticker="7203.T", start=None, end=None)
        journal_review.handle_pnl(args)
        captured = capsys.readouterr()
        assert "Ticker: 7203.T" in captured.out
        assert "t002" in captured.out
        assert "t001" not in captured.out
        
        # 日付フィルタ (期間外のt003が含まれないことの確認)
        args_date = argparse_namespace(ticker=None, start="2026-06-01", end="2026-06-10")
        journal_review.handle_pnl(args_date)
        captured_date = capsys.readouterr()
        assert "t001" in captured_date.out
        assert "t002" in captured_date.out
        assert "t003" not in captured_date.out

def test_handle_report_invalid_format(mock_journal_env):
    args = argparse_namespace(month="invalid-month")
    with pytest.raises(SystemExit):
        journal_review.handle_report(args)

def test_handle_report_success(mock_journal_env, capsys):
    # テスト用データ準備
    index_data = {
        "sessions": [
            {
                "session_id": "2026-06-05T10-00_285A.T_dcf",
                "date": "2026-06-05",
                "tickers": ["285A.T"],
                "companies": ["Kioxia"],
                "workflow": "dcf",
                "trigger": "manual",
                "confidence": "high",
                "tags": ["NAND"],
                "summary_path": "sessions/2026-06-05T10-00_285A.T_dcf.md",
                "decisions_path": "sessions/2026-06-05T10-00_285A.T_dcf_decisions.json",
                "artifact_paths": []
            }
        ]
    }
    mock_journal_env["index_path"].write_text(json.dumps(index_data), encoding="utf-8")
    
    decisions_data = {
        "decisions": [
            {
                "id": "d001",
                "category": "assumption",
                "topic": "WACC",
                "question": "WACC setting?",
                "chosen": "5.0%",
                "rationale": "Rationale",
                "impact": "high"
            }
        ]
    }
    dec_file = mock_journal_env["sessions_dir"] / "2026-06-05T10-00_285A.T_dcf_decisions.json"
    dec_file.write_text(json.dumps(decisions_data), encoding="utf-8")
    
    trades_data = {
        "trades": [
            {
                "trade_id": "t001",
                "ticker": "285A.T",
                "company": "Kioxia",
                "side": "buy",
                "date": "2026-06-01",
                "quantity": 100,
                "price": 1000.0,
                "currency": "JPY",
                "fees": 10.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            },
            {
                "trade_id": "t002",
                "ticker": "285A.T",
                "company": "Kioxia",
                "side": "sell",
                "date": "2026-06-10",
                "quantity": 100,
                "price": 1200.0,
                "currency": "JPY",
                "fees": 10.0,
                "session_refs": [],
                "thesis_snapshot": "test"
            }
        ]
    }
    mock_journal_env["trades_path"].write_text(json.dumps(trades_data), encoding="utf-8")
    
    args = argparse_namespace(month="2026-06")
    journal_review.handle_report(args)
    captured = capsys.readouterr()
    
    assert "SUCCESS: Monthly report generated" in captured.out
    
    # ファイル存在確認
    report_file = mock_journal_env["reports_dir"] / "monthly_2026-06.md"
    assert report_file.exists()
    
    content = report_file.read_text(encoding="utf-8")
    assert "# 月次振り返りレポート: 2026年06月" in content
    assert "実施セッション数**: 1" in content
    assert "2026-06-05T10-00_285A.T_dcf" in content
    assert "d001" in content
    assert "t001" in content
    assert "t002" in content

def test_main_history():
    with mock.patch("journal_review.handle_history") as mock_hist, \
         mock.patch("sys.argv", ["journal_review.py", "history", "--ticker", "285A.T"]):
        journal_review.main()
        mock_hist.assert_called_once()
        args = mock_hist.call_args[0][0]
        assert args.ticker == "285A.T"

def test_main_pnl():
    with mock.patch("journal_review.handle_pnl") as mock_pnl, \
         mock.patch("sys.argv", ["journal_review.py", "pnl", "--ticker", "285A.T", "--start", "2026-06-01"]):
        journal_review.main()
        mock_pnl.assert_called_once()
        args = mock_pnl.call_args[0][0]
        assert args.ticker == "285A.T"
        assert args.start == "2026-06-01"

def test_main_report():
    with mock.patch("journal_review.handle_report") as mock_rep, \
         mock.patch("sys.argv", ["journal_review.py", "report", "--month", "2026-06"]):
        journal_review.main()
        mock_rep.assert_called_once()
        args = mock_rep.call_args[0][0]
        assert args.month == "2026-06"

def test_load_session_json(mock_journal_env):
    data = journal_review.load_session_json("sessions/non_exist.json")
    assert data == {}

    dec_file = mock_journal_env["sessions_dir"] / "broken.json"
    dec_file.write_text("{broken", encoding="utf-8")
    data = journal_review.load_session_json("sessions/broken.json")
    assert data == {}

    expected = {"session_id": "test_s1", "price_at_session": 1000.0}
    dec_file = mock_journal_env["sessions_dir"] / "test_s1.json"
    dec_file.write_text(json.dumps(expected), encoding="utf-8")
    data = journal_review.load_session_json("sessions/test_s1.json")
    assert data == expected

def test_get_current_price():
    with mock.patch("yfinance.Ticker") as mock_ticker:
        mock_instance = mock.Mock()
        mock_instance.info = {"currentPrice": 150.0}
        mock_ticker.return_value = mock_instance
        
        price = journal_review.get_current_price("MSFT")
        assert price == 150.0

        mock_instance.info = {"regularMarketPrice": 2500.0}
        price = journal_review.get_current_price("7203")
        mock_ticker.assert_called_with("7203.T")
        assert price == 2500.0

        mock_instance.info = {}
        import pandas as pd
        mock_hist = pd.DataFrame({"Close": [100.0]}, index=[pd.Timestamp("2026-06-22")])
        mock_instance.history.return_value = mock_hist

        
        price = journal_review.get_current_price("285A.T")
        assert price == 100.0

        mock_instance.history.side_effect = Exception("error")
        price = journal_review.get_current_price("TEST")
        assert price is None

def test_determine_direction():
    d1 = {"category": "conclusion", "topic": "test", "chosen": "Hold"}
    assert journal_review.determine_direction(d1) == "long"

    d2 = {"category": "assumption", "topic": "buy target", "chosen": "1200"}
    assert journal_review.determine_direction(d2) == "long"

    d3 = {"category": "conclusion", "topic": "test", "chosen": "sell all"}
    assert journal_review.determine_direction(d3) == "short"

    d4 = {"category": "assumption", "topic": "WACC calculation", "chosen": "5.5%"}
    assert journal_review.determine_direction(d4) == "N/A"

def test_handle_verify(mock_journal_env, capsys):
    index_data = {
        "sessions": [
            {
                "session_id": "2026-06-05T10-00_285A.T_dcf",
                "date": "2026-06-05",
                "tickers": ["285A.T"],
                "companies": ["Kioxia"],
                "workflow": "dcf",
                "summary_path": "sessions/2026-06-05T10-00_285A.T_dcf.md",
                "decisions_path": "sessions/2026-06-05T10-00_285A.T_dcf_decisions.json"
            }
        ]
    }
    mock_journal_env["index_path"].write_text(json.dumps(index_data), encoding="utf-8")
    
    decisions_data = {
        "session_id": "2026-06-05T10-00_285A.T_dcf",
        "price_at_session": 1000.0,
        "decisions": [
            {
                "id": "d001",
                "category": "assumption",
                "topic": "WACC",
                "question": "WACC setting?",
                "chosen": "5.0%",
                "rationale": "Rationale",
                "confidence": "high",
                "impact": "high"
            },
            {
                "id": "d002",
                "category": "conclusion",
                "topic": "Investment Decision",
                "question": "Action?",
                "chosen": "Buy Kioxia",
                "rationale": "Strong demand",
                "confidence": "high",
                "impact": "high"
            }
        ]
    }
    dec_file = mock_journal_env["sessions_dir"] / "2026-06-05T10-00_285A.T_dcf_decisions.json"
    dec_file.write_text(json.dumps(decisions_data), encoding="utf-8")

    with mock.patch("journal_review.get_current_price", return_value=1200.0):
        args = argparse_namespace()
        journal_review.handle_verify(args)
        captured = capsys.readouterr()
        
        assert "Decision Performance Verification" in captured.out
        assert "285A.T" in captured.out
        assert "Success" in captured.out
        assert "+20.0%" in captured.out
        assert "Accuracy" in captured.out

def test_main_verify():
    with mock.patch("journal_review.handle_verify") as mock_ver, \
         mock.patch("sys.argv", ["journal_review.py", "verify"]):
        journal_review.main()
        mock_ver.assert_called_once()

# ヘルパー
def argparse_namespace(**kwargs):
    return mock.Mock(**kwargs)
