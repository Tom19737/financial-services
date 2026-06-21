import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import shutil
import csv

# 既存のscriptsフォルダをインポート元に追加
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_edinet
import edinet_api
import xbrl_parser

class TestFetchEdinet(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        
    def test_xbrl_parsing(self):
        # モックのXBRL (XML) 文字列を作成
        mock_xbrl_content = """<?xml version="1.0" encoding="utf-8"?>
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:jppfs-cor="http://www.fsa.go.jp/taxonomy/jppfs/2021-11-01">
          <xbrli:context id="CurrentYearDuration">
            <xbrli:period>
              <xbrli:startDate>2025-04-01</xbrli:startDate>
              <xbrli:endDate>2026-03-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="CurrentYearInstant">
            <xbrli:period>
              <xbrli:instant>2026-03-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <jppfs-cor:NetSales contextRef="CurrentYearDuration">123456000000</jppfs-cor:NetSales>
          <jppfs-cor:OperatingIncome contextRef="CurrentYearDuration">12345000000</jppfs-cor:OperatingIncome>
          <jppfs-cor:TotalAssets contextRef="CurrentYearInstant">987654000000</jppfs-cor:TotalAssets>
          <jppfs-cor:ShortTermLoansPayable contextRef="CurrentYearInstant">10000000000</jppfs-cor:ShortTermLoansPayable>
          <jppfs-cor:LongTermLoansPayable contextRef="CurrentYearInstant">20000000000</jppfs-cor:LongTermLoansPayable>
          <jppfs-cor:DepreciationAndAmortization contextRef="CurrentYearDuration">5000000000</jppfs-cor:DepreciationAndAmortization>
        </xbrli:xbrl>
        """
        xbrl_path = os.path.join(self.temp_dir, "test.xbrl")
        with open(xbrl_path, "w", encoding="utf-8") as f:
            f.write(mock_xbrl_content)
            
        # 分割された xbrl_parser から直接テストする
        data = xbrl_parser.parse_xbrl_file(xbrl_path)
        
        # マッピング結果の検証
        self.assertIn("Total Revenue", data)
        self.assertEqual(data["Total Revenue"]["2026-03-31"], 123456000000.0)
        
        self.assertIn("Operating Income", data)
        self.assertEqual(data["Operating Income"]["2026-03-31"], 12345000000.0)
        
        self.assertIn("Total Assets", data)
        self.assertEqual(data["Total Assets"]["2026-03-31"], 987654000000.0)
        
        # 有利子負債 (Total Debt = ShortTerm 10B + LongTerm 20B)
        self.assertIn("Total Debt", data)
        self.assertEqual(data["Total Debt"]["2026-03-31"], 30000000000.0)
        
        # EBITDA (Operating Income 12.345B + Depreciation 5B)
        self.assertIn("EBITDA", data)
        self.assertEqual(data["EBITDA"]["2026-03-31"], 17345000000.0)

    def test_lookup_edinet_code(self):
        # モックのEDINETコードマッピングCSVを作成
        csv_path = os.path.join(self.temp_dir, "EdinetcodeDlInfo.csv")
        with open(csv_path, "w", encoding="cp932", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["EDINET Code List Template"])
            writer.writerow([])
            writer.writerow(["ＥＤＩＮＥＴコード", "提出者種別", "提出者名", "提出者名（ヨミ）", "提出者名（英字）", "所在地", "提出者業種", "証券コード", "提出者法人番号"])
            writer.writerow(["E02166", "内国法人・上場", "トヨタ自動車株式会社", "トヨタジドウシャ", "TOYOTA MOTOR CORP", "豊田市", "輸送用機器", "72030", "1234567890123"])
            writer.writerow(["E02188", "内国法人・上場", "ソニーグループ株式会社", "ソニーグループ", "SONY GROUP CORP", "港区", "電気機器", "67580", "9876543210987"])

        # 分割された edinet_api から直接テストする
        res = edinet_api.lookup_edinet_code(csv_path, "7203")
        self.assertEqual(res["edinet_code"], "E02166")
        self.assertEqual(res["filer_name"], "トヨタ自動車株式会社")
        self.assertEqual(res["corporate_number"], "1234567890123")
        
        res = edinet_api.lookup_edinet_code(csv_path, "6758.T")
        self.assertEqual(res["edinet_code"], "E02188")
        
        with self.assertRaises(ValueError):
            edinet_api.lookup_edinet_code(csv_path, "9999")

    # デコレータの順序に対応させて、引数の順番を修正
    # 上から順に complement, extract, download_zip, fetch_doc, lookup の順に引数に渡される
    @patch('fetch_edinet.lookup_edinet_code')
    @patch('fetch_edinet.fetch_document_list')
    @patch('fetch_edinet.download_document_zip')
    @patch('fetch_edinet.extract_financials_from_zip')
    @patch('fetch_edinet.complement_with_yfinance')
    @patch.dict(os.environ, {"EDINET_API_KEY": "dummy_api_key"})
    def test_main_flow(self, mock_lookup, mock_fetch_doc_list, mock_download_zip, mock_extract, mock_complement):
        mock_lookup.return_value = {
            "edinet_code": "E01234",
            "filer_name": "Test Company"
        }
        
        mock_fetch_doc_list.return_value = {
            "results": [
                {
                    "docID": "S100XXXX",
                    "edinetCode": "E01234",
                    "docTypeCode": "120",
                    "docDescription": "有価証券報告書",
                    "submitDateTime": "2026-06-20 15:00"
                }
            ]
        }
        
        mock_download_zip.return_value = True
        
        mock_extract.return_value = {
            "Total Revenue": {"2026-03-31": 1000.0},
            "Operating Income": {"2026-03-31": 100.0},
            "Reconciled Depreciation": {"2026-03-31": 20.0},
            "Tax Provision": {"2026-03-31": 30.0},
            "EBITDA": {"2026-03-31": 120.0},
            "Total Assets": {"2026-03-31": 5000.0},
            "Total Debt": {"2026-03-31": 1000.0},
            "Cash Cash Equivalents And Short Term Investments": {"2026-03-31": 500.0},
            "Operating Cash Flow": {"2026-03-31": 150.0},
            "Capital Expenditure": {"2026-03-31": -80.0},
            "Change In Working Capital": {"2026-03-31": 10.0}
        }
        
        with patch('sys.argv', ['fetch_edinet.py', '7203', '--days', '1', '--outdir', self.temp_dir]):
            fetch_edinet.main()

if __name__ == "__main__":
    unittest.main()
