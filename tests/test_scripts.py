import os
import unittest
import sys
import json
from unittest.mock import patch, MagicMock

# scriptsフォルダをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import scripts.fetch_yfinance as fetch_yfinance
import scripts.fetch_gas_sheets as fetch_gas_sheets

class TestFetchYFinance(unittest.TestCase):
    
    @patch('yfinance.Ticker')
    def test_fetch_yfinance_success(self, mock_ticker):
        # Tickerのモック設定
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        # historyのモック
        import pandas as pd
        mock_instance.history.return_value = pd.DataFrame({
            'Close': [2700.0, 2776.5]
        }, index=pd.date_range(start='2026-06-19', periods=2))
        
        # infoのモック
        mock_instance.info = {
            "currentPrice": 2776.5,
            "marketCap": 32876682805248,
            "sharesOutstanding": 11841052480,
            "currency": "JPY",
            "longName": "Toyota Motor Corporation"
        }

        # 財務諸表のモック DataFrame
        mock_df = pd.DataFrame({
            '2026-06-20': [100.0, 200.0]
        }, index=['Revenue', 'NetIncome'])
        
        mock_instance.income_stmt = mock_df
        mock_instance.quarterly_income_stmt = mock_df
        mock_instance.balance_sheet = mock_df
        mock_instance.quarterly_balance_sheet = mock_df
        mock_instance.cashflow = mock_df
        mock_instance.quarterly_cashflow = mock_df
        
        # 引数のパースと実行
        with patch('sys.argv', ['fetch_yfinance.py', '7203', '--outdir', './out/test_market_data']):
            # outdirのクリーンアップ
            if os.path.exists('./out/test_market_data'):
                for f in os.listdir('./out/test_market_data'):
                    try:
                        os.remove(os.path.join('./out/test_market_data', f))
                    except Exception:
                        pass
            
            fetch_yfinance.main()
            
            # ファイルが作成されたか確認
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T.json'))
            
            # 財務諸表CSVの存在確認
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T_annual_income_stmt.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T_quarterly_income_stmt.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T_annual_balance_sheet.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T_quarterly_balance_sheet.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T_annual_cashflow.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T_quarterly_cashflow.csv'))
            
            # JSONの中身を検証
            with open('./out/test_market_data/7203.T.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertEqual(data['ticker'], '7203.T')
                self.assertEqual(data['current_price'], 2776.5)
                self.assertEqual(data['market_cap'], 32876682805248)

class TestFetchGasSheets(unittest.TestCase):
    
    @patch('requests.get')
    def test_fetch_gas_sheets_success(self, mock_get):
        # requests.getのレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "sheetName": "GoogleFinanceData",
            "rowCount": 1,
            "data": [{"Ticker": "7203.T", "Close": 2776.5}]
        }
        mock_get.return_value = mock_response
        
        dummy_url = "https://script.google.com/macros/s/dummy/exec"
        test_outfile = "./out/test_sheet_data.json"
        
        if os.path.exists(test_outfile):
            os.remove(test_outfile)
            
        with patch('sys.argv', ['fetch_gas_sheets.py', dummy_url, '--outfile', test_outfile]):
            fetch_gas_sheets.main()
            
            self.assertTrue(os.path.exists(test_outfile))
            with open(test_outfile, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertEqual(data['status'], 'success')
                self.assertEqual(data['data'][0]['Ticker'], '7203.T')

    @patch('requests.get')
    def test_fetch_gas_sheets_invalid_url(self, mock_get):
        invalid_url = "http://invalid-url.com"
        with patch('sys.argv', ['fetch_gas_sheets.py', invalid_url]):
            with self.assertRaises(SystemExit) as cm:
                fetch_gas_sheets.main()
            self.assertEqual(cm.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
