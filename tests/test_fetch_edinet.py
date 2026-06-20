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
            
        data = fetch_edinet.parse_xbrl_file(xbrl_path)
        
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
            # ヘッダー説明など
            writer.writerow(["EDINET Code List Template"])
            writer.writerow([])
            # ヘッダー
            writer.writerow(["ＥＤＩＮＥＴコード", "提出者種別", "提出者名", "提出者名（ヨミ）", "提出者名（英字）", "所在地", "提出者業種", "証券コード", "提出者法人番号"])
            # データ行 (トヨタ自動車のダミー)
            writer.writerow(["E02166", "内国法人・上場", "トヨタ自動車株式会社", "トヨタジドウシャ", "TOYOTA MOTOR CORP", "豊田市", "輸送用機器", "72030", "1234567890123"])
            # データ行 (ソニーのダミー)
            writer.writerow(["E02188", "内国法人・上場", "ソニーグループ株式会社", "ソニーグループ", "SONY GROUP CORP", "港区", "電気機器", "67580", "9876543210987"])

        # 正常系: 7203
        res = fetch_edinet.lookup_edinet_code(csv_path, "7203")
        self.assertEqual(res["edinet_code"], "E02166")
        self.assertEqual(res["filer_name"], "トヨタ自動車株式会社")
        self.assertEqual(res["corporate_number"], "1234567890123")
        
        # 正常系: 6758.T (末尾市場コード付き)
        res = fetch_edinet.lookup_edinet_code(csv_path, "6758.T")
        self.assertEqual(res["edinet_code"], "E02188")
        
        # 異常系: 存在しないティッカー
        with self.assertRaises(ValueError):
            fetch_edinet.lookup_edinet_code(csv_path, "9999")

if __name__ == "__main__":
    unittest.main()
