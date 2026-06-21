import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.yfinance_screener import build_query, save_results

class DummyArgs:
    def __init__(self, **kwargs):
        self.region = kwargs.get("region", "jp")
        self.sector = kwargs.get("sector", None)
        self.industry = kwargs.get("industry", None)
        self.min_market_cap = kwargs.get("min_market_cap", None)
        self.max_market_cap = kwargs.get("max_market_cap", None)
        self.min_pe = kwargs.get("min_pe", None)
        self.max_pe = kwargs.get("max_pe", None)
        self.count = kwargs.get("count", 25)
        self.sort_by = kwargs.get("sort_by", "intradaymarketcap")
        self.sort_type = kwargs.get("sort_type", "DESC")
        self.output = kwargs.get("output", None)
        self.format = kwargs.get("format", "json")

def test_build_query_basic():
    args = DummyArgs(region="us")
    query = build_query(args)
    assert query is not None
    assert "region" in str(query)

def test_build_query_complex():
    args = DummyArgs(region="jp", min_market_cap=1000000, max_pe=15)
    query = build_query(args)
    assert query is not None
    q_str = str(query)
    assert "region" in q_str
    assert "intradaymarketcap" in q_str
    assert "peratio" in q_str

def test_save_results_json(tmp_path):
    output_file = os.path.join(tmp_path, "results.json")
    dummy_quotes = [{"symbol": "7203.T", "shortName": "Toyota"}]
    
    success = save_results(dummy_quotes, output_file, "json")
    assert success is True
    assert os.path.exists(output_file)
    
    with open(output_file, "r", encoding="utf-8") as f:
        import json
        data = json.load(f)
        assert len(data) == 1
        assert data[0]["symbol"] == "7203.T"

def test_save_results_csv(tmp_path):
    output_file = os.path.join(tmp_path, "results.csv")
    dummy_quotes = [{"symbol": "7203.T", "shortName": "Toyota", "marketCap": 50000}]
    
    success = save_results(dummy_quotes, output_file, "csv")
    assert success is True
    assert os.path.exists(output_file)
    
    import pandas as pd
    df = pd.read_csv(output_file)
    assert len(df) == 1
    assert df.loc[0, "symbol"] == "7203.T"

@patch('yfinance.screen')
def test_main_execution(mock_screen):
    mock_screen.return_value = {
        "quotes": [
            {"symbol": "7203.T", "shortName": "Toyota", "regularMarketPrice": 3000.0}
        ]
    }
    
    from scripts.yfinance_screener import main
    test_args = [
        "yfinance_screener.py",
        "--region", "jp",
        "--count", "1"
    ]
    
    with patch('sys.argv', test_args):
        # 正常に走り抜けることの確認
        main()
        assert mock_screen.called
