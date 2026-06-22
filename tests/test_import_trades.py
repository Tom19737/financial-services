import os
import json
import pytest
from unittest.mock import patch, MagicMock
import scripts.import_trades as it

# テスト用モックデータ
SBI_CSV_CONTENT = """
約定履歴照会

商品指定,約定開始年月日,約定終了年月日,明細数,明細指定開始,明細指定終了
"株式現物","2026年06月01日","2026年06月22日","2","1","2"

（注）明細数はご指定された期間の合計です。

約定日,銘柄,銘柄コード,市場,取引,期限,預り,課税,約定数量,約定単価,手数料/諸経費等,税額,受渡日,受渡金額/決済損益
"2026/06/02","メタプラネット","3350","東証",株式現物買,"--"," NISA(成) ","--",100,284,--,--,"2026/06/04",28400
"2026/06/19","ＮＴＴ","9432","PTS","株式現物売","--"," NISA(成) ","--",1000,145.1,--,--,"2026/06/23",145100
"""

RAKUTEN_CSV_CONTENT = """約定日,受渡日,銘柄コード,銘柄名,市場名称,口座区分,取引区分,売買区分,信用区分,弁済期限,数量［株］,単価［円］,手数料［円］,税金等［円］,諸費用［円］,税区分,受渡金額［円］,建約定日,建単価［円］,建手数料［円］,建手数料消費税［円］,金利（支払）〔円〕,金利（受取）〔円〕,逆日歩／特別空売り料（支払）〔円〕,逆日歩（受取）〔円〕,貸株料,事務管理費〔円〕（税抜）,名義書換料〔円〕（税抜）
"2024/6/6","2024/6/10","9432","日本電信電話","東証","NISA成長投資枠","現物","買付","-","-","100","152.0","0","0","0","-","15,200","-","0.0","0","0","0","0","0","0","0","0","0"
"2024/6/6","2024/6/10","9432","日本電信電話","ToSTNeT","NISA成長投資枠","現物","売付","-","-","100","151.3","0","0","0","-","15,130","-","0.0","0","0","0","0","0","0","0","0","0"
"2025/8/27","2025/9/1","8267","イオン","東証","NISA成長投資枠","","入庫","-","-","200","1,066.66","0","0","0","-","-","-","0.0","0","0","0","0","0","0","0","0","0"
"""

INVALID_CSV_CONTENT = """Header1,Header2
Value1,Value2
"""

@pytest.fixture
def temp_csv_files(tmp_path):
    sbi_path = tmp_path / "mock_sbi.csv"
    rakuten_path = tmp_path / "mock_rakuten.csv"
    invalid_path = tmp_path / "mock_invalid.csv"
    
    # 書き込み (cp932エンコードで保存)
    with open(sbi_path, "w", encoding="cp932") as f:
        f.write(SBI_CSV_CONTENT.strip())
    with open(rakuten_path, "w", encoding="cp932") as f:
        f.write(RAKUTEN_CSV_CONTENT.strip())
    with open(invalid_path, "w", encoding="cp932") as f:
        f.write(INVALID_CSV_CONTENT.strip())
        
    return {
        "sbi": str(sbi_path),
        "rakuten": str(rakuten_path),
        "invalid": str(invalid_path)
    }

def test_detect_csv_format(temp_csv_files):
    fmt, header_idx, enc = it.detect_csv_format(temp_csv_files["sbi"])
    assert fmt == "sbi"
    assert header_idx == 7
    
    fmt2, header_idx2, enc2 = it.detect_csv_format(temp_csv_files["rakuten"])
    assert fmt2 == "rakuten"
    assert header_idx2 == 0
    
    fmt3, header_idx3, enc3 = it.detect_csv_format(temp_csv_files["invalid"])
    assert fmt3 is None
    assert header_idx3 == -1

def test_clean_number():
    assert it.clean_number("15,200") == 15200.0
    assert it.clean_number("4,300.0円") == 4300.0
    assert it.clean_number("100株") == 100.0
    assert it.clean_number("--") == 0.0
    assert it.clean_number("-") == 0.0
    assert it.clean_number("") == 0.0

def test_parse_row_rakuten():
    header = [
        "約定日", "受渡日", "銘柄コード", "銘柄名", "市場名称", "口座区分", 
        "取引区分", "売買区分", "信用区分", "弁済期限", "数量［株］", 
        "単価［円］", "手数料［円］", "諸費用［円］", "受渡金額［円］"
    ]
    # 正常系（買付）
    row_buy = [
        "2024/6/6", "2024/6/10", "9432", "日本電信電話", "東証", 
        "NISA", "現物", "買付", "-", "-", "100", "152.0", "10", "5", "15,200"
    ]
    res_buy = it.parse_row("rakuten", header, row_buy)
    assert res_buy is not None
    assert res_buy["date"] == "2024-06-06"
    assert res_buy["ticker"] == "9432.T"
    assert res_buy["side"] == "buy"
    assert res_buy["quantity"] == 100
    assert res_buy["price"] == 152.0
    assert res_buy["fees"] == 15.0  # 10 + 5
    
    # 正常系（売付）
    row_sell = [
        "2024/6/6", "2024/6/10", "9432", "日本電信電話", "東証", 
        "NISA", "現物", "売付", "-", "-", "100", "152.0", "10", "5", "15,200"
    ]
    res_sell = it.parse_row("rakuten", header, row_sell)
    assert res_sell["side"] == "sell"
    
    # 異常系（現物以外の取引区分）
    row_invalid_tx = [
        "2024/6/6", "2024/6/10", "9432", "日本電信電話", "東証", 
        "NISA", "信用", "買付", "-", "-", "100", "152.0", "10", "5", "15,200"
    ]
    assert it.parse_row("rakuten", header, row_invalid_tx) is None
    
    # 異常系（買付・売付以外の売買区分）
    row_invalid_side = [
        "2024/6/6", "2024/6/10", "9432", "日本電信電話", "東証", 
        "NISA", "現物", "その他", "-", "-", "100", "152.0", "10", "5", "15,200"
    ]
    assert it.parse_row("rakuten", header, row_invalid_side) is None

def test_parse_row_sbi():
    header = [
        "約定日", "銘柄", "銘柄コード", "市場", "取引", "期限", 
        "預り", "課税", "約定数量", "約定単価", "手数料/諸経費等", "受渡金額/決済損益"
    ]
    # 正常系（買）
    row_buy = [
        "2026/06/02", "メタプラネット", "3350", "東証", "株式現物買", 
        "--", "NISA", "--", "100", "284", "15", "28400"
    ]
    res_buy = it.parse_row("sbi", header, row_buy)
    assert res_buy is not None
    assert res_buy["date"] == "2026-06-02"
    assert res_buy["ticker"] == "3350.T"
    assert res_buy["side"] == "buy"
    assert res_buy["quantity"] == 100
    assert res_buy["price"] == 284.0
    assert res_buy["fees"] == 15.0
    
    # 正常系（売）
    row_sell = [
        "2026/06/02", "メタプラネット", "3350", "東証", "株式現物売", 
        "--", "NISA", "--", "100", "284", "--", "28400"
    ]
    res_sell = it.parse_row("sbi", header, row_sell)
    assert res_sell["side"] == "sell"
    assert res_sell["fees"] == 0.0

@patch("scripts.import_trades.yf.Ticker")
def test_get_company_name_yfinance(mock_ticker):
    mock_info = {"shortName": "Test Corp", "longName": "Test Corporation"}
    mock_ticker.return_value.info = mock_info
    
    assert it.get_company_name_yfinance("7203.T") == "Test Corp"

@patch("scripts.import_trades.get_company_name_yfinance")
@patch("scripts.import_trades.trade_manager")
def test_main_import_flow(mock_tm, mock_get_name, temp_csv_files):
    # モックの設定
    mock_get_name.return_value = "Mocked Company"
    mock_tm.load_trades.return_value = {
        "trades": [
            # 既存の取引 (楽天の最初の取引と重複)
            {
                "trade_id": "t001",
                "ticker": "9432.T",
                "company": "日本電信電話",
                "side": "buy",
                "date": "2024-06-06",
                "quantity": 100,
                "price": 152.0,
                "currency": "JPY",
                "fees": 0.0,
                "session_refs": [],
                "notes": "existing"
            }
        ]
    }
    mock_tm.generate_trade_id.return_value = "t002"
    
    with patch("sys.argv", ["scripts/import_trades.py", temp_csv_files["rakuten"]]):
        it.main()
        
    # 重複以外の1件がインポートされたか
    assert mock_tm.save_trades.called
    saved_data = mock_tm.save_trades.call_args[0][0]
    
    # 既存1件 + 新規インポート1件（もうひとつの売付の方、入庫はスキップ）
    assert len(saved_data["trades"]) == 2
    assert saved_data["trades"][1]["side"] == "sell"
    assert saved_data["trades"][1]["ticker"] == "9432.T"

@patch("scripts.import_trades.load_sessions_list")
@patch("scripts.import_trades.trade_manager")
@patch("builtins.input")
def test_interactive_mode(mock_input, mock_tm, mock_sessions, temp_csv_files):
    # 対話モードのモック入力
    # 1つ目のインポート対象取引にセッションインデックス "1" を紐付け
    mock_input.return_value = "1"
    mock_sessions.return_value = [
        {"session_id": "session_abc", "date": "2026-06-22", "tickers": ["9432.T"]}
    ]
    mock_tm.load_trades.return_value = {"trades": []}
    mock_tm.generate_trade_id.return_value = "t001"
    
    with patch("sys.argv", ["scripts/import_trades.py", temp_csv_files["rakuten"], "-i"]):
        it.main()
        
    assert mock_tm.save_trades.called
    saved_data = mock_tm.save_trades.call_args[0][0]
    
    # 楽天の買付、売付の2取引がインポートされる (入庫は除外)
    assert len(saved_data["trades"]) == 2
    assert saved_data["trades"][0]["session_refs"] == ["session_abc"]

def test_clean_number_invalid():
    assert it.clean_number("abc") == 0.0

def test_detect_csv_format_file_not_found():
    with pytest.raises(SystemExit):
        it.detect_csv_format("nonexistent_file.csv")

def test_detect_csv_format_invalid():
    # detect_csv_formatでサポートされていない形式
    pass

@patch("scripts.import_trades.yf.Ticker")
def test_get_company_name_yfinance_exception(mock_ticker):
    mock_ticker.side_effect = Exception("API Error")
    assert it.get_company_name_yfinance("7203.T") is None

@patch("scripts.import_trades.trade_manager")
def test_main_import_with_session_ref(mock_tm, temp_csv_files):
    mock_tm.load_trades.return_value = {"trades": []}
    mock_tm.generate_trade_id.return_value = "t001"
    
    with patch("sys.argv", [
        "scripts/import_trades.py", 
        temp_csv_files["rakuten"], 
        "--session-ref", "target_session_id"
    ]):
        it.main()
        
    assert mock_tm.save_trades.called
    saved_data = mock_tm.save_trades.call_args[0][0]
    assert saved_data["trades"][0]["session_refs"] == ["target_session_id"]

@patch("builtins.input")
def test_prompt_for_session_invalid_input(mock_input, capsys):
    mock_input.side_effect = ["abc", "99", "0"]
    sessions = [{"session_id": "session_1", "date": "2026-06-22", "tickers": ["9432.T"]}]
    trade_info = {
        "date": "2026-06-22", "ticker": "9432.T", "side": "buy", "quantity": 100, "price": 150
    }
    
    res = it.prompt_for_session(trade_info, "NTT", sessions)
    assert res == []
    captured = capsys.readouterr()
    assert "数値、またはカンマ区切りの数値を入力してください。" in captured.out
    assert "無効なインデックス: 99" in captured.out

