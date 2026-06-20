import os
import unittest
import sys
import json
import shutil
from unittest.mock import patch, MagicMock

# scriptsフォルダをインポートパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import scripts.fetch_yfinance as fetch_yfinance

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
                shutil.rmtree('./out/test_market_data')
            
            fetch_yfinance.main()
            
            # ファイルが作成されたか確認
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/prices.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/summary.json'))
            
            # 財務諸表CSVの存在確認
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/annual_income_stmt.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/quarterly_income_stmt.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/annual_balance_sheet.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/quarterly_balance_sheet.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/annual_cashflow.csv'))
            self.assertTrue(os.path.exists('./out/test_market_data/7203.T/quarterly_cashflow.csv'))
            
            # JSONの中身を検証
            with open('./out/test_market_data/7203.T/summary.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertEqual(data['ticker'], '7203.T')
                self.assertEqual(data['current_price'], 2776.5)
                self.assertEqual(data['market_cap'], 32876682805248)

    @patch('yfinance.Ticker')
    def test_fetch_yfinance_partial_data(self, mock_ticker):
        # Tickerのモック設定
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        # historyのモック
        import pandas as pd
        mock_instance.history.return_value = pd.DataFrame({
            'Close': [2776.5]
        }, index=pd.date_range(start='2026-06-20', periods=1))
        
        # infoは最小限、財務諸表の一部がNoneや空のDataFrameで欠損している設定
        mock_instance.info = {"currentPrice": 2776.5}
        mock_instance.income_stmt = None  # PL欠損
        mock_instance.quarterly_income_stmt = pd.DataFrame()  # 空のPL
        mock_instance.balance_sheet = pd.DataFrame({'2026-06-20': [100.0]}, index=['Assets']) # BSは正常
        mock_instance.quarterly_balance_sheet = None
        mock_instance.cashflow = None
        mock_instance.quarterly_cashflow = None
        
        with patch('sys.argv', ['fetch_yfinance.py', '7203', '--outdir', './out/test_partial_data']):
            # クリーンアップ
            if os.path.exists('./out/test_partial_data'):
                shutil.rmtree('./out/test_partial_data')
            
            fetch_yfinance.main()
            
            # 株価や正常なBSは出力されるが、欠損しているPLやCFファイルは生成されずに正常終了することを確認
            self.assertTrue(os.path.exists('./out/test_partial_data/7203.T/prices.csv'))
            self.assertTrue(os.path.exists('./out/test_partial_data/7203.T/annual_balance_sheet.csv'))
            self.assertFalse(os.path.exists('./out/test_partial_data/7203.T/annual_income_stmt.csv'))
            self.assertFalse(os.path.exists('./out/test_partial_data/7203.T/annual_cashflow.csv'))

    @patch('yfinance.Ticker')
    def test_fetch_yfinance_invalid_ticker(self, mock_ticker):
        # Tickerのモック設定（historyが空）
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        import pandas as pd
        mock_instance.history.return_value = pd.DataFrame()
        
        with patch('sys.argv', ['fetch_yfinance.py', 'INVALID_TICKER']):
            with self.assertRaises(SystemExit) as cm:
                fetch_yfinance.main()
            self.assertEqual(cm.exception.code, 1)

            self.assertEqual(cm.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
