import os
import json
import pytest
from unittest.mock import patch, MagicMock
import scripts.trade_manager as tm

# テストデータ
VALID_TRADE_DATA = {
    "trades": [
        {
            "trade_id": "t001",
            "ticker": "285A.T",
            "company": "KIOXIA Holdings",
            "side": "buy",
            "date": "2026-06-22",
            "quantity": 100,
            "price": 2000.0,
            "currency": "JPY",
            "fees": 100.0,
            "session_refs": ["2026-06-22T17-00_285A.T_dcf"],
            "thesis_snapshot": "DCF analysis suggests undervaluation.",
            "notes": "Initial position"
        }
    ]
}

INVALID_TRADE_DATA = {
    "trades": [
        {
            "trade_id": "t001",
            "ticker": "285A.T",
            "company": "KIOXIA Holdings",
            "side": "invalid-side",  # enum違反
            "date": "2026-06-22",
            "quantity": 0,  # 0以下
            "price": 2000.0,
            "currency": "JPY",
            "fees": 100.0,
            "session_refs": [],
            "thesis_snapshot": ""
        }
    ]
}

@pytest.fixture
def temp_trades_env(tmp_path):
    """
    テスト用の一時ディレクトリを設定するフィクスチャ。
    """
    orig_path = tm.TRADES_PATH
    orig_index = tm.INDEX_PATH
    
    trades_file = tmp_path / "trades.json"
    index_file = tmp_path / "index.json"
    
    tm.TRADES_PATH = str(trades_file)
    tm.INDEX_PATH = str(index_file)
    
    # ダミーのindex.jsonを作成
    index_data = {
        "sessions": [],
        "trade_count": 0,
        "last_updated": ""
    }
    with open(str(index_file), "w", encoding="utf-8") as f:
        json.dump(index_data, f)
        
    yield tmp_path
    
    tm.TRADES_PATH = orig_path
    tm.INDEX_PATH = orig_index

def test_validate_trade_data():
    assert tm.validate_trade_data(VALID_TRADE_DATA) is True
    with pytest.raises(ValueError):
        tm.validate_trade_data(INVALID_TRADE_DATA)

def test_load_save_trades(temp_trades_env):
    # 初回ロード（空）
    data = tm.load_trades()
    assert data == {"trades": []}
    
    # 保存
    tm.save_trades(VALID_TRADE_DATA)
    assert os.path.exists(tm.TRADES_PATH)
    
    # 二回目ロード
    loaded = tm.load_trades()
    assert len(loaded["trades"]) == 1
    assert loaded["trades"][0]["trade_id"] == "t001"
    
    # index.jsonのtrade_countが更新されているか
    with open(tm.INDEX_PATH, "r", encoding="utf-8") as f:
        idx = json.load(f)
        assert idx["trade_count"] == 1

def test_generate_trade_id():
    assert tm.generate_trade_id([]) == "t001"
    assert tm.generate_trade_id([{"trade_id": "t001"}, {"trade_id": "t005"}]) == "t006"

def test_calculate_pnl():
    # 複数取引による平均取得単価と損益計算のシミュレーション
    trades = [
        # 1. 285A.T 100株を2000円で買い、手数料100円
        # ポジション: 100株、平均価格 (200000 + 100)/100 = 2001
        {
            "trade_id": "t001",
            "ticker": "285A.T",
            "side": "buy",
            "date": "2026-06-22",
            "quantity": 100,
            "price": 2000.0,
            "fees": 100.0
        },
        # 2. 285A.T 100株を2500円で買い、手数料100円
        # ポジション: 200株、平均価格 (200100 + 250000 + 100)/200 = 2251
        {
            "trade_id": "t002",
            "ticker": "285A.T",
            "side": "buy",
            "date": "2026-06-23",
            "quantity": 100,
            "price": 2500.0,
            "fees": 100.0
        },
        # 3. 285A.T 100株を3000円で売り、手数料200円
        # 損益: (300000 - 200) - (2251 * 100) = 299800 - 225100 = +74700円
        # ポジション: 100株、平均価格は変わらず 2251
        {
            "trade_id": "t003",
            "ticker": "285A.T",
            "side": "sell",
            "date": "2026-06-24",
            "quantity": 100,
            "price": 3000.0,
            "fees": 200.0
        }
    ]
    
    positions, realized_pnl, pnl_details = tm.calculate_pnl(trades)
    
    assert positions["285A.T"]["qty"] == 100
    assert positions["285A.T"]["avg_price"] == 2251.0
    assert realized_pnl["285A.T"] == 74700.0
    
    # 各売買での個別損益確認
    assert pnl_details[0]["pnl"] == 0.0  # buy
    assert pnl_details[1]["pnl"] == 0.0  # buy
    assert pnl_details[2]["pnl"] == 74700.0  # sell

def test_handle_add(temp_trades_env):
    class DummyArgs:
        side = "buy"
        ticker = "285A.T"
        company = "KIOXIA"
        date = "2026-06-22"
        quantity = 100
        price = 2000.0
        currency = "JPY"
        fees = 0.0
        session_refs = "s001,s002"
        thesis_snapshot = "Undervalued"
        notes = "note"
        
    tm.handle_add(DummyArgs())
    loaded = tm.load_trades()
    assert len(loaded["trades"]) == 1
    assert loaded["trades"][0]["session_refs"] == ["s001", "s002"]

def test_handle_delete(temp_trades_env):
    tm.save_trades(VALID_TRADE_DATA)
    
    class DummyArgs:
        id = "t001"
        
    tm.handle_delete(DummyArgs())
    loaded = tm.load_trades()
    assert len(loaded["trades"]) == 0

def test_handle_delete_not_found(temp_trades_env):
    tm.save_trades(VALID_TRADE_DATA)
    
    class DummyArgs:
        id = "t999"
        
    with pytest.raises(SystemExit):
        tm.handle_delete(DummyArgs())

def test_calculate_pnl_sell_more_than_qty():
    trades = [
        {
            "trade_id": "t001",
            "ticker": "285A.T",
            "side": "sell",
            "date": "2026-06-22",
            "quantity": 100,
            "price": 2000.0,
            "fees": 0.0
        }
    ]
    positions, realized_pnl, pnl_details = tm.calculate_pnl(trades)
    assert positions["285A.T"]["qty"] == -100

def test_handle_list(temp_trades_env, capsys):
    tm.save_trades(VALID_TRADE_DATA)
    tm.handle_list(None)
    captured = capsys.readouterr()
    assert "t001" in captured.out
    assert "285A.T" in captured.out

def test_handle_stats(temp_trades_env, capsys):
    tm.save_trades(VALID_TRADE_DATA)
    
    class DummyArgs:
        ticker = None
        
    tm.handle_stats(DummyArgs())
    captured = capsys.readouterr()
    assert "Position Status" in captured.out
    assert "285A.T" in captured.out

def test_handle_stats_filtered(temp_trades_env, capsys):
    tm.save_trades(VALID_TRADE_DATA)
    
    class DummyArgs:
        ticker = "285A.T"
        
    tm.handle_stats(DummyArgs())
    captured = capsys.readouterr()
    assert "285A.T" in captured.out

def test_main_add(temp_trades_env):
    with patch("sys.argv", [
        "scripts/trade_manager.py", "add",
        "--side", "buy",
        "--ticker", "285A.T",
        "--company", "KIOXIA",
        "--quantity", "100",
        "--price", "2000.0",
        "--thesis-snapshot", "thesis"
    ]):
        tm.main()
    loaded = tm.load_trades()
    assert len(loaded["trades"]) == 1
    assert loaded["trades"][0]["ticker"] == "285A.T"

def test_main_list(temp_trades_env, capsys):
    tm.save_trades(VALID_TRADE_DATA)
    with patch("sys.argv", ["scripts/trade_manager.py", "list"]):
        tm.main()
    captured = capsys.readouterr()
    assert "t001" in captured.out

def test_main_delete(temp_trades_env):
    tm.save_trades(VALID_TRADE_DATA)
    with patch("sys.argv", ["scripts/trade_manager.py", "delete", "--id", "t001"]):
        tm.main()
    loaded = tm.load_trades()
    assert len(loaded["trades"]) == 0

def test_main_stats(temp_trades_env, capsys):
    tm.save_trades(VALID_TRADE_DATA)
    with patch("sys.argv", ["scripts/trade_manager.py", "stats"]):
        tm.main()
    captured = capsys.readouterr()
    assert "Position Status" in captured.out

