import os
import shutil
import json
import unittest
import pandas as pd
from unittest.mock import patch

import generate_3statement

class TestGenerate3Statement(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./out/test_3statement_data"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

        # 対象企業のデータを準備
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

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_build_3statement_model(self):
        from utils import get_latest_financial_data
        ticker_data = get_latest_financial_data(self.ticker_dir, self.ticker)
        
        generate_3statement.build_3statement_model(ticker_data, self.ticker_dir)

        # 保存先パス確認
        out_path = os.path.join(self.ticker_dir, "analysis", "3statement_7203.T.xlsx")
        self.assertTrue(os.path.exists(out_path))

    @patch('sys.argv', ['generate_3statement.py', '7203', '--outdir', './out/test_3statement_data'])
    def test_main(self):
        if hasattr(generate_3statement, 'main'):
            generate_3statement.main()
        
        # 期待される出力ファイルが存在するか確認
        output_file = os.path.join(self.ticker_dir, "analysis", "3statement_7203.T.xlsx")
        self.assertTrue(os.path.exists(output_file))
