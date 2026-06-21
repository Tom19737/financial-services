import os
import shutil
import json
import unittest
import pandas as pd
from unittest.mock import patch

from utils import normalize_ticker, find_ticker_dir, get_latest_financial_data, setup_logging, ExcelStyles

class TestUtils(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./out/test_utils_data"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_normalize_ticker(self):
        self.assertEqual(normalize_ticker("7203"), "7203.T")
        self.assertEqual(normalize_ticker("7203.T"), "7203.T")
        self.assertEqual(normalize_ticker("AAPL"), "AAPL")
        self.assertEqual(normalize_ticker(""), "")
        self.assertEqual(normalize_ticker(None), "")

    def test_find_ticker_dir(self):
        # フォルダが存在しない場合
        res = find_ticker_dir(self.test_dir, "7203")
        self.assertEqual(res, os.path.join(self.test_dir, "7203.T"))

        # フォルダが存在する場合
        target = os.path.join(self.test_dir, "7203.T_Toyota_Motor")
        os.makedirs(target, exist_ok=True)
        res = find_ticker_dir(self.test_dir, "7203")
        self.assertEqual(res, target)

    def test_setup_logging(self):
        logger = setup_logging("test_logger")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "test_logger")

    def test_get_latest_financial_data_missing_files(self):
        ticker_dir = os.path.join(self.test_dir, "7203.T")
        os.makedirs(ticker_dir, exist_ok=True)
        with self.assertRaises(FileNotFoundError):
            get_latest_financial_data(ticker_dir, "7203")

    def test_get_latest_financial_data_success(self):
        ticker_dir = os.path.join(self.test_dir, "7203.T_Toyota_Motor")
        market_data_dir = os.path.join(ticker_dir, "market_data")
        os.makedirs(market_data_dir, exist_ok=True)

        # summary.json
        summary = {
            "long_name": "Toyota Motor Corporation",
            "currency": "JPY",
            "current_price": 2700.0,
            "shares_outstanding": 11841052480,
            "market_cap": 32000000000000,
            "ebitda": 5000000000000
        }
        with open(os.path.join(market_data_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f)

        # annual_income_stmt.csv
        inc_df = pd.DataFrame({
            "2026-03-31": [40000000000000, 5000000000000, 4500000000000, 500000000000, 1000000000000]
        }, index=["Total Revenue", "EBITDA", "EBIT", "Reconciled Depreciation", "Tax Provision"])
        inc_df.to_csv(os.path.join(market_data_dir, "annual_income_stmt.csv"))

        # annual_balance_sheet.csv
        bs_df = pd.DataFrame({
            "2026-03-31": [80000000000000, 10000000000000, 9000000000000]
        }, index=["Total Assets", "Total Debt", "Cash Cash Equivalents And Short Term Investments"])
        bs_df.to_csv(os.path.join(market_data_dir, "annual_balance_sheet.csv"))

        # annual_cashflow.csv
        cf_df = pd.DataFrame({
            "2026-03-31": [3000000000000, 2000000000000, 100000000000]
        }, index=["Operating Cash Flow", "Capital Expenditure", "Change In Working Capital"])
        cf_df.to_csv(os.path.join(market_data_dir, "annual_cashflow.csv"))

        data = get_latest_financial_data(ticker_dir, "7203")
        self.assertEqual(data["ticker"], "7203.T")
        self.assertEqual(data["name"], "Toyota Motor Corporation")
        self.assertEqual(data["revenue"], 40000000000000.0)
        self.assertEqual(data["ebitda"], 5000000000000.0)
        self.assertEqual(data["ebit"], 4500000000000.0)
        self.assertEqual(data["depreciation"], 500000000000.0)
        self.assertEqual(data["tax_provision"], 1000000000000.0)
        self.assertEqual(data["total_debt"], 10000000000000.0)
        self.assertEqual(data["cash"], 9000000000000.0)
        self.assertEqual(data["capex"], 2000000000000.0)
        self.assertEqual(data["nwc_change"], 100000000000.0)

    def test_get_latest_financial_data_100x_correction(self):
        ticker_dir = os.path.join(self.test_dir, "7203.T_Toyota_Motor")
        market_data_dir = os.path.join(ticker_dir, "market_data")
        os.makedirs(market_data_dir, exist_ok=True)

        # 異常値（100倍）が設定された summary.json
        summary = {
            "long_name": "Toyota Motor Corporation",
            "currency": "JPY",
            "current_price": 270000.0, # 本来 2700.0
            "shares_outstanding": 11841052480,
            "market_cap": 3.2e15, # 本来 3.2e13
            "ebitda": 5000000000000
        }
        with open(os.path.join(market_data_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f)

        # 最小限の CSV を作成
        inc_df = pd.DataFrame({"2026-03-31": [10.0]}, index=["Total Revenue"])
        inc_df.to_csv(os.path.join(market_data_dir, "annual_income_stmt.csv"))
        bs_df = pd.DataFrame({"2026-03-31": [10.0]}, index=["Total Assets"])
        bs_df.to_csv(os.path.join(market_data_dir, "annual_balance_sheet.csv"))

        data = get_latest_financial_data(ticker_dir, "7203")
        self.assertEqual(data["current_price"], 2700.0)
        self.assertEqual(data["market_cap"], 3.2e13)

    def test_excel_styles(self):
        from openpyxl.styles import Font, PatternFill, Border
        styles = ExcelStyles()
        self.assertIsInstance(styles.header_font, Font)
        self.assertIsInstance(styles.primary_fill, PatternFill)
        self.assertIsInstance(styles.thin_border, Border)
