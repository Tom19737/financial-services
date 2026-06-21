import os
import xml.etree.ElementTree as ET
import zipfile
import tempfile
from utils import setup_logging

logger = setup_logging("xbrl_parser")

# 勘定科目のマッピング定義
XBRL_TAG_MAP = {
    # P&L (損益計算書)
    "Total Revenue": [
        "Revenue", "NetSales", "OperatingRevenue", 
        "RevenueFromBusinessOfInsurance", "OperatingRevenues",
        "NetSalesOfGoods", "RevenueFromContractsWithCustomers"
    ],
    "Operating Income": [
        "OperatingIncome", "OperatingProfit", "OperatingProfitLoss"
    ],
    "Reconciled Depreciation": [
        "DepreciationAndAmortization", "Depreciation",
        "DepreciationAndAmortizationAmortizationOfGoodwill",
        "DepreciationOfPropertyPlantAndEquipment", "AmortizationOfIntangibleAssets"
    ],
    "Tax Provision": [
        "IncomeTaxExpense", "TaxProvision", "IncomeTaxes", 
        "IncomeTaxesCurrent", "IncomeTaxesDeferred", "IncomeTaxesCurrentAndDeferred"
    ],
    # B/S (貸借対照表)
    "Total Assets": [
        "TotalAssets", "Assets"
    ],
    "Cash Cash Equivalents And Short Term Investments": [
        "CashAndDeposits", "CashAndCashEquivalents",
        "CashCashEquivalentsAndShortTermInvestments", "Cash"
    ],
    # C/F (キャッシュ・フロー計算書)
    "Operating Cash Flow": [
        "NetCashProvidedByUsedInOperatingActivities", 
        "CashFlowsFromUsedInOperatingActivities"
    ],
    "Capital Expenditure": [
        "PurchaseOfPropertyPlantAndEquipment", 
        "PurchaseOfNonCurrentAssets",
        "PaymentsForAcquisitionOfPropertyPlantAndEquipment",
        "PaymentsForAcquisitionOfPropertyPlantAndEquipmentAndIntangibleAssets"
    ],
    "Change In Working Capital": [
        "IncreaseDecreaseInWorkingCapital",
        "IncreaseDecreaseInNotesAndAccountsReceivableTrade",
        "IncreaseDecreaseInInventories",
        "IncreaseDecreaseInNotesAndAccountsPayableTrade"
    ]
}

# 有利子負債（Total Debt）を構成するタグ
DEBT_TAGS = [
    "ShortTermLoansPayable", "ShortTermBorrowings",
    "LongTermLoansPayable", "LongTermBorrowings",
    "BondsPayable", "CurrentPortionOfBonds",
    "CurrentPortionOfLongTermLoansPayable",
    "CommercialPapers"
]

def parse_xbrl_file(xbrl_file_path):
    """XBRLファイルを解析し、日付ごとの勘定科目数値を抽出する"""
    try:
        tree = ET.parse(xbrl_file_path)
    except Exception as e:
        logger.error(f"Failed to parse XML in {xbrl_file_path}: {e}")
        return {}
        
    root = tree.getroot()
    
    # 1. contextの定義から ID -> 日付 を取得
    contexts = {}
    for elem in root.iter():
        local_name = elem.tag.split('}')[-1]
        if local_name == 'context':
            context_id = elem.attrib.get('id')
            if not context_id:
                continue
            
            period = None
            for child in elem:
                if child.tag.split('}')[-1] == 'period':
                    period = child
                    break
            
            if period is not None:
                end_date = None
                instant = None
                for p_child in period:
                    p_local = p_child.tag.split('}')[-1]
                    if p_local == 'endDate':
                        end_date = p_child.text
                    elif p_local == 'instant':
                        instant = p_child.text
                
                date_val = end_date or instant
                if date_val:
                    contexts[context_id] = date_val.strip()
                    
    # 2. 勘定科目データを抽出
    financial_data = {}
    
    # 逆引きマップを作成
    tag_reverse_map = {}
    for key, tags in XBRL_TAG_MAP.items():
        for tag in tags:
            tag_reverse_map[tag] = key
    for tag in DEBT_TAGS:
        tag_reverse_map[tag] = "debt_component"
        
    for elem in root.iter():
        local_name = elem.tag.split('}')[-1]
        if local_name in tag_reverse_map:
            key = tag_reverse_map[local_name]
            context_ref = elem.attrib.get('contextRef')
            if not context_ref or context_ref not in contexts:
                continue
            
            date_str = contexts[context_ref]
            
            try:
                val_str = elem.text
                if not val_str or val_str.strip() == '':
                    continue
                val = float(val_str.strip())
            except ValueError:
                continue
                
            if key not in financial_data:
                financial_data[key] = {}
                
            financial_data[key][date_str] = val
            
            # 有利子負債の個別要素を一時保存
            if key == "debt_component":
                if "debt_components" not in financial_data:
                    financial_data["debt_components"] = {}
                if date_str not in financial_data["debt_components"]:
                    financial_data["debt_components"][date_str] = []
                financial_data["debt_components"][date_str].append((local_name, val))

    # 3. 有利子負債 (Total Debt) の合算
    all_dates = set()
    for k in financial_data:
        if k != "debt_components":
            all_dates.update(financial_data[k].keys())
            
    financial_data["Total Debt"] = {}
    if "debt_components" in financial_data:
        for d, comps in financial_data["debt_components"].items():
            tag_vals = {}
            for tag, val in comps:
                tag_vals[tag] = val
            financial_data["Total Debt"][d] = sum(tag_vals.values())
            
    # 4. EBITDA = Operating Income + Reconciled Depreciation
    financial_data["EBITDA"] = {}
    for d in all_dates:
        ebit_val = financial_data.get("Operating Income", {}).get(d, 0.0)
        dep_val = financial_data.get("Reconciled Depreciation", {}).get(d, 0.0)
        if ebit_val or dep_val:
            financial_data["EBITDA"][d] = ebit_val + dep_val
            
    # 一時キーの削除
    if "debt_components" in financial_data:
        del financial_data["debt_components"]
        
    return financial_data

def extract_financials_from_zip(zip_path):
    """ZIPファイルから財務データをパースする (XBRLを優先パース)"""
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(temp_dir)
            
        csv_files = []
        xbrl_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
                elif file.endswith('.xbrl'):
                    xbrl_files.append(os.path.join(root, file))
                    
        logger.info(f"Found {len(xbrl_files)} XBRL files and {len(csv_files)} CSV files in ZIP.")
        
        financials = {}
        for xbrl_file in xbrl_files:
            data = parse_xbrl_file(xbrl_file)
            for key, dates in data.items():
                if key not in financials:
                    financials[key] = {}
                financials[key].update(dates)
                
        return financials
