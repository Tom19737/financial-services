import os
import sys
import csv
import urllib.request
import zipfile
import io
from utils import setup_logging

logger = setup_logging("edinet_api")

def download_edinet_code_list(dest_path):
    """EDINETコード・証券コードのマッピングCSVを金融庁からダウンロードする"""
    url = "https://disclosure.edinet-fsa.go.jp/control/E01EW/download?lp=default&cf=default&pf=default&ko=06&lo=01&hi=01"
    logger.info("Downloading EDINET Code list from EDINET...")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
        
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            csv_files = [name for name in z.namelist() if name.endswith('.csv')]
            if not csv_files:
                raise FileNotFoundError("No CSV file found in the downloaded EDINET Code ZIP.")
            
            with open(dest_path, "wb") as f:
                f.write(z.read(csv_files[0]))
        logger.info(f"Saved EDINET Code list to {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download EDINET Code list: {e}")
        return False

def lookup_edinet_code(csv_path, ticker):
    """ティッカーからEDINETコードと企業情報を逆引きする"""
    clean_ticker = ticker.split(".")[0]
    
    if not os.path.exists(csv_path):
        success = download_edinet_code_list(csv_path)
        if not success:
            raise RuntimeError("EDINET Code list could not be acquired.")
        
    logger.info(f"Searching EDINET code for ticker: {clean_ticker}")
    with open(csv_path, "r", encoding="cp932") as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    header = None
    data_start_idx = 0
    for i, row in enumerate(rows):
        if len(row) > 0 and "ＥＤＩＮＥＴコード" in row[0]:
            header = row
            data_start_idx = i + 1
            break
            
    if not header:
        header = ["ＥＤＩＮＥＴコード", "提出者種別", "提出者名", "提出者名（ヨミ）", "提出者名（英字）", "所在地", "提出者業種", "証券コード", "提出者法人番号"]
        data_start_idx = 2
        
    try:
        edinet_code_col = header.index("ＥＤＩＮＥＴコード")
        sec_code_col = header.index("証券コード")
        filer_name_col = header.index("提出者名")
        corporate_number_col = header.index("提出者法人番号")
    except ValueError:
        edinet_code_col, sec_code_col, filer_name_col, corporate_number_col = 0, 7, 2, 8
    
    for row in rows[data_start_idx:]:
        if len(row) <= max(sec_code_col, edinet_code_col):
            continue
        sec_code = row[sec_code_col].strip()
        if sec_code.startswith(clean_ticker):
            return {
                "edinet_code": row[edinet_code_col].strip(),
                "filer_name": row[filer_name_col].strip(),
                "corporate_number": row[corporate_number_col].strip() if len(row) > corporate_number_col else ""
            }
            
    raise ValueError(f"Ticker {ticker} (clean: {clean_ticker}) not found in EDINET Code list.")

def fetch_document_list(api_key, date_str):
    """指定日のEDINET提出書類一覧を取得する"""
    url = f"https://disclosure2.edinet-fsa.go.jp/api/v2/documents.json?date={date_str}&type=2"
    logger.info(f"Fetching document list for date: {date_str}")
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Ocp-Apim-Subscription-Key': api_key
    })
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode('utf-8')
            return json.loads(res_data)
    except Exception as e:
        logger.error(f"Failed to fetch document list for date {date_str}: {e}")
        return None

def download_document_zip(api_key, doc_id, dest_zip_path):
    """書類IDを指定して書類のZIPパッケージをダウンロードする"""
    os.makedirs(os.path.dirname(dest_zip_path), exist_ok=True)
    if os.path.exists(dest_zip_path):
        logger.info(f"Document {doc_id} already downloaded (cached).")
        return True
        
    url = f"https://disclosure2.edinet-fsa.go.jp/api/v2/documents/{doc_id}?type=1"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Ocp-Apim-Subscription-Key': api_key
    })
    
    logger.info(f"Downloading document ZIP for {doc_id} from EDINET...")
    try:
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
            with open(dest_zip_path, "wb") as f:
                f.write(zip_data)
        logger.info(f"Saved document ZIP to {dest_zip_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download document {doc_id}: {e}")
        return False
