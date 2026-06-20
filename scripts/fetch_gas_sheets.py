import os
import sys
import argparse
import json
import requests

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Google Sheets data via GAS Web App API")
    parser.add_argument("url", type=str, help="GAS Web App deployment URL")
    parser.add_argument("--outfile", type=str, default="./out/sheet_data.json", help="Output JSON file path")
    return parser.parse_args()

def main():
    args = parse_args()
    url = args.url.strip()
    
    if not url.startswith("https://script.google.com/"):
        print("Error: Invalid GAS Web App URL. Must start with https://script.google.com/", file=sys.stderr)
        sys.exit(1)
        
    print(f"Fetching spreadsheet data from GAS Web App...")
    
    try:
        # GASのWeb Appは302リダイレクトを行うため、allow_redirects=Trueを指定
        response = requests.get(url, allow_redirects=True, timeout=30)
        
        if response.status_code != 200:
            print(f"Error: Failed to fetch data. HTTP Status Code: {response.status_code}", file=sys.stderr)
            sys.exit(1)
            
        # JSONが正しくパースできるかチェック
        try:
            data = response.json()
        except ValueError:
            print("Error: Response content is not valid JSON.", file=sys.stderr)
            print("Response text snippet:", response.text[:200], file=sys.stderr)
            sys.exit(1)
            
        # ディレクトリ作成
        outdir = os.path.dirname(args.outfile)
        if outdir:
            os.makedirs(outdir, exist_ok=True)
            
        # JSON書き出し
        with open(args.outfile, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"Successfully saved spreadsheet data to {args.outfile}")
        
    except Exception as e:
        print(f"Error occurred during HTTP request: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
