import os
import shutil
import json
import unittest
import pandas as pd
from unittest.mock import patch, MagicMock

import generate_models

class TestGenerateModels(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./out/test_models_data"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

        # テスト対象企業のデータを準備
        self.ticker = "7203"
        self.ticker_dir = os.path.join(self.test_dir, "7203.T_Toyota_Motor")
        self.market_data_dir = os.path.join(self.ticker_dir, "market_data")
        os.makedirs(self.market_data_dir, exist_ok=True)

        summary = {
            "long_name": "Toyota Motor",
            "ticker": "7203.T",
            "currency": "JPY",
            "current_price": 2700.0,
            "shares_outstanding": 11841052480,
            "market_cap": 32000000000000,
            "ebitda": 5000000000000
        }
        with open(os.path.join(self.market_data_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f)

        inc_df = pd.DataFrame({
            "2026-03-31": [40000000000000, 5000000000000, 4500000000000, 500000000000, 1000000000000]
        }, index=["Total Revenue", "EBITDA", "EBIT", "Reconciled Depreciation", "Tax Provision"])
        inc_df.to_csv(os.path.join(self.market_data_dir, "annual_income_stmt.csv"))

        bs_df = pd.DataFrame({
            "2026-03-31": [80000000000000, 10000000000000, 9000000000000]
        }, index=["Total Assets", "Total Debt", "Cash Cash Equivalents And Short Term Investments"])
        bs_df.to_csv(os.path.join(self.market_data_dir, "annual_balance_sheet.csv"))

        cf_df = pd.DataFrame({
            "2026-03-31": [3000000000000, 2000000000000, 100000000000]
        }, index=["Operating Cash Flow", "Capital Expenditure", "Change In Working Capital"])
        cf_df.to_csv(os.path.join(self.market_data_dir, "annual_cashflow.csv"))

        # ピア（競合）企業のデータを準備
        self.peer = "7267"
        self.peer_dir = os.path.join(self.test_dir, "7267.T_Honda_Motor")
        self.peer_market_dir = os.path.join(self.peer_dir, "market_data")
        os.makedirs(self.peer_market_dir, exist_ok=True)

        peer_summary = {
            "long_name": "Honda Motor",
            "ticker": "7267.T",
            "currency": "JPY",
            "current_price": 1600.0,
            "shares_outstanding": 5000000000,
            "market_cap": 8000000000000,
            "ebitda": 1500000000000
        }
        with open(os.path.join(self.peer_market_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(peer_summary, f)
        
        # ピアのCSVも同様に最低限作成
        inc_df.to_csv(os.path.join(self.peer_market_dir, "annual_income_stmt.csv"))
        bs_df.to_csv(os.path.join(self.peer_market_dir, "annual_balance_sheet.csv"))
        cf_df.to_csv(os.path.join(self.peer_market_dir, "annual_cashflow.csv"))

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('subprocess.run')
    def test_fetch_peer_data_if_missing(self, mock_run):
        # 存在するピアの場合、subprocess.runは呼ばれない
        generate_models.fetch_peer_data_if_missing("7267", self.test_dir)
        mock_run.assert_not_called()

        # 存在しないピアの場合、subprocess.runが呼ばれる
        generate_models.fetch_peer_data_if_missing("9999", self.test_dir)
        mock_run.assert_called_once()

    def test_create_comps_model(self):
        from utils import get_latest_financial_data
        ticker_data = get_latest_financial_data(self.ticker_dir, self.ticker)
        
        generate_models.create_comps_model(ticker_data, [self.peer], self.test_dir)
        
        # 保存先パス確認
        out_path = os.path.join(self.ticker_dir, "analysis", "comps_7203.T.xlsx")
        self.assertTrue(os.path.exists(out_path))

    @patch('sys.argv', ['generate_models.py', '7203', '--peers', '7267', '--outdir', './out/test_models_data'])
    @patch('subprocess.run')
    def test_main_flow(self, mock_run):
        # generate_models.main() の実行テスト
        # 実際には generate_models に main() 関数があり、それがスクリプト全体を呼び出している
        # main() が直接定義されているか、あるいはトップレベルスクリプトかを確かめるため、
        # generate_models に main 関数があるか確認
        if hasattr(generate_models, 'main'):
            generate_models.main()
        else:
            # もし main 関数が定義されておらず、スクリプトが if __name__ == '__main__': の直下にコードを書いている場合、
            # テスト実行時にすでにインポートされているので、それをテストする
            # (generate_models.py を view_file で確認しつつ進める)
            pass
        
        # 期待される出力ファイルが存在するか確認
        comps_file = os.path.join(self.ticker_dir, "analysis", "comps_7203.T.xlsx")
        dcf_file = os.path.join(self.ticker_dir, "analysis", "dcf_7203.T.xlsx")
        self.assertTrue(os.path.exists(comps_file))
        self.assertTrue(os.path.exists(dcf_file))
