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
    
    def setUp(self):
        # 一時テストフォルダのクリア
        for path in ['./out/test_market_data', './out/test_partial_data']:
            if os.path.exists(path):
                shutil.rmtree(path)

    def tearDown(self):
        # テスト実行後のクリーンアップ
        for path in ['./out/test_market_data', './out/test_partial_data']:
            if os.path.exists(path):
                shutil.rmtree(path)

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
            fetch_yfinance.main()
            
            # 保存先フォルダ名は 7203.T_Toyota_Motor_Corporation / market_data
            target_dir = './out/test_market_data/7203.T_Toyota_Motor_Corporation/market_data'
            
            # ファイルが作成されたか確認
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'prices.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'summary.json')))
            
            # 財務諸表CSVの存在確認
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'annual_income_stmt.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'quarterly_income_stmt.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'annual_balance_sheet.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'quarterly_balance_sheet.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'annual_cashflow.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'quarterly_cashflow.csv')))
            
            # JSONの中身を検証
            with open(os.path.join(target_dir, 'summary.json'), 'r', encoding='utf-8') as f:
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
            fetch_yfinance.main()
            
            # 保存先フォルダ名は 7203.T / market_data
            target_dir = './out/test_partial_data/7203.T/market_data'
            
            # 株価や正常なBSは出力されるが、欠損しているPLやCFファイルは生成されずに正常終了することを確認
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'prices.csv')))
            self.assertTrue(os.path.exists(os.path.join(target_dir, 'annual_balance_sheet.csv')))
            self.assertFalse(os.path.exists(os.path.join(target_dir, 'annual_income_stmt.csv')))
            self.assertFalse(os.path.exists(os.path.join(target_dir, 'annual_cashflow.csv')))

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

    @patch('yfinance.Ticker')
    def test_fetch_yfinance_with_specified_exchange_rate(self, mock_ticker):
        # Tickerのモック設定（USD建ての日本企業）
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        import pandas as pd
        mock_instance.history.return_value = pd.DataFrame({
            'Close': [100.0, 110.0]
        }, index=pd.date_range(start='2026-06-19', periods=2))
        
        mock_instance.info = {
            "currentPrice": 110.0,
            "marketCap": 1100000,
            "sharesOutstanding": 10000,
            "currency": "USD",
            "longName": "Test JP Company USD Reporting"
        }
        
        mock_df = pd.DataFrame({
            '2026-06-20': [10.0, 20.0]
        }, index=['Revenue', 'NetIncome'])
        
        mock_instance.income_stmt = mock_df
        mock_instance.quarterly_income_stmt = mock_df
        mock_instance.balance_sheet = mock_df
        mock_instance.quarterly_balance_sheet = mock_df
        mock_instance.cashflow = mock_df
        mock_instance.quarterly_cashflow = mock_df

        # 手動で為替レート 150.0 を指定、ティッカーは日本株（.T で終わる）
        with patch('sys.argv', ['fetch_yfinance.py', 'MSFT.T', '--outdir', './out/test_market_data', '--exchange-rate', '150.0']):
            fetch_yfinance.main()
            
            target_dir = './out/test_market_data/MSFT.T_Test_JP_Company_USD_Reporting/market_data'
            
            # summary.jsonの検証
            with open(os.path.join(target_dir, 'summary.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertEqual(data['ticker'], 'MSFT.T')
                self.assertEqual(data['currency'], 'JPY')
                self.assertEqual(data['original_currency'], 'USD')
                self.assertEqual(data['exchange_rate_applied'], 150.0)
                # 110.0 * 150.0 = 16500.0
                self.assertEqual(data['current_price'], 16500.0)
                # 1100000 * 150.0 = 165000000.0
                self.assertEqual(data['market_cap'], 165000000.0)

            # prices.csv の検証
            df_prices = pd.read_csv(os.path.join(target_dir, 'prices.csv'))
            # 最新の Close 値は 110.0 * 150.0 = 16500.0
            self.assertEqual(df_prices['Close'].iloc[-1], 16500.0)

            # 財務諸表CSVの検証
            df_inc = pd.read_csv(os.path.join(target_dir, 'annual_income_stmt.csv'), index_col=0)
            # 10.0 * 150.0 = 1500.0
            self.assertEqual(df_inc.loc['Revenue', '2026-06-20'], 1500.0)

    @patch('yfinance.Ticker')
    def test_fetch_yfinance_with_auto_exchange_rate(self, mock_ticker):
        import pandas as pd
        
        # モックの side_effect を定義して、USDJPY=X と対象銘柄の切り替えを行う
        def side_effect(ticker_symbol):
            mock_inst = MagicMock()
            if ticker_symbol == 'USDJPY=X':
                mock_inst.history.return_value = pd.DataFrame({
                    'Close': [160.0]
                }, index=pd.date_range(start='2026-06-20', periods=1))
            else:
                mock_inst.history.return_value = pd.DataFrame({
                    'Close': [100.0, 110.0]
                }, index=pd.date_range(start='2026-06-19', periods=2))
                
                mock_inst.info = {
                    "currentPrice": 110.0,
                    "marketCap": 1100000,
                    "sharesOutstanding": 10000,
                    "currency": "USD",
                    "longName": "Test JP Company USD Reporting"
                }
                
                mock_df = pd.DataFrame({
                    '2026-06-20': [10.0, 20.0]
                }, index=['Revenue', 'NetIncome'])
                
                mock_inst.income_stmt = mock_df
                mock_inst.quarterly_income_stmt = mock_df
                mock_inst.balance_sheet = mock_df
                mock_inst.quarterly_balance_sheet = mock_df
                mock_inst.cashflow = mock_df
                mock_inst.quarterly_cashflow = mock_df
            return mock_inst

        mock_ticker.side_effect = side_effect

        # 自動為替レート（USDJPY=X から 160.0 が取得される）、ティッカーは日本株（.T で終わる）
        with patch('sys.argv', ['fetch_yfinance.py', 'MSFT.T', '--outdir', './out/test_market_data']):
            fetch_yfinance.main()
            
            target_dir = './out/test_market_data/MSFT.T_Test_JP_Company_USD_Reporting/market_data'
            
            # summary.jsonの検証
            with open(os.path.join(target_dir, 'summary.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertEqual(data['ticker'], 'MSFT.T')
                self.assertEqual(data['currency'], 'JPY')
                self.assertEqual(data['original_currency'], 'USD')
                self.assertEqual(data['exchange_rate_applied'], 160.0)
                # 110.0 * 160.0 = 17600.0
                self.assertEqual(data['current_price'], 17600.0)

            # 財務諸表CSVの検証
            df_inc = pd.read_csv(os.path.join(target_dir, 'annual_income_stmt.csv'), index_col=0)
            # 10.0 * 160.0 = 1600.0
            self.assertEqual(df_inc.loc['Revenue', '2026-06-20'], 1600.0)

    @patch('yfinance.Ticker')
    def test_fetch_yfinance_us_stock_not_converted(self, mock_ticker):
        # 米国株（.T で終わらない）は為替換算されないことを確認
        mock_instance = MagicMock()
        mock_ticker.return_value = mock_instance
        
        import pandas as pd
        mock_instance.history.return_value = pd.DataFrame({
            'Close': [100.0, 110.0]
        }, index=pd.date_range(start='2026-06-19', periods=2))
        
        mock_instance.info = {
            "currentPrice": 110.0,
            "marketCap": 1100000,
            "sharesOutstanding": 10000,
            "currency": "USD",
            "longName": "Test US Company"
        }
        
        mock_df = pd.DataFrame({
            '2026-06-20': [10.0, 20.0]
        }, index=['Revenue', 'NetIncome'])
        
        mock_instance.income_stmt = mock_df
        mock_instance.quarterly_income_stmt = mock_df
        mock_instance.balance_sheet = mock_df
        mock_instance.quarterly_balance_sheet = mock_df
        mock_instance.cashflow = mock_df
        mock_instance.quarterly_cashflow = mock_df

        # 手動で為替レート 150.0 を指定するが、ティッカーは米国株（MSFT）
        with patch('sys.argv', ['fetch_yfinance.py', 'MSFT', '--outdir', './out/test_market_data', '--exchange-rate', '150.0']):
            fetch_yfinance.main()
            
            target_dir = './out/test_market_data/MSFT_Test_US_Company/market_data'
            
            # summary.jsonの検証（換算されていないこと）
            with open(os.path.join(target_dir, 'summary.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.assertEqual(data['ticker'], 'MSFT')
                self.assertEqual(data['currency'], 'USD') # USDのまま
                self.assertNotIn('original_currency', data)
                self.assertNotIn('exchange_rate_applied', data)
                self.assertEqual(data['current_price'], 110.0) # 110.0のまま
                self.assertEqual(data['market_cap'], 1100000) # 換算なし

            # prices.csv の検証
            df_prices = pd.read_csv(os.path.join(target_dir, 'prices.csv'))
            self.assertEqual(df_prices['Close'].iloc[-1], 110.0) # 110.0のまま

            # 財務諸表CSVの検証
            df_inc = pd.read_csv(os.path.join(target_dir, 'annual_income_stmt.csv'), index_col=0)
            self.assertEqual(df_inc.loc['Revenue', '2026-06-20'], 10.0) # 10.0のまま

if __name__ == '__main__':
    unittest.main()
