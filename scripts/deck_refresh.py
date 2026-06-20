from pptx import Presentation
import os

def find_ticker_dir(base_dir, ticker_str):
    import glob
    pattern = os.path.join(base_dir, f"{ticker_str}*")
    matches = glob.glob(pattern)
    dirs = [m for m in matches if os.path.isdir(m)]
    dirs.sort(key=len, reverse=True)
    if dirs:
        return dirs[0]
    return os.path.join(base_dir, ticker_str)

def refresh_text(shape, old_text, new_text):
    if shape.has_text_frame:
        tf = shape.text_frame
        for paragraph in tf.paragraphs:
            for run in paragraph.runs:
                if old_text in run.text:
                    safe_run = run.text.replace("¥", "Yen")
                    safe_old = old_text.replace("¥", "Yen")
                    safe_new = new_text.replace("¥", "Yen")
                    print(f"    Updating run: '{safe_run}' -> replacing '{safe_old}' with '{safe_new}'")
                    run.text = run.text.replace(old_text, new_text)
                    
    if shape.has_table:
        table = shape.table
        for row in table.rows:
            for cell in row.cells:
                if old_text in cell.text:
                    safe_cell = cell.text.replace("¥", "Yen")
                    safe_old = old_text.replace("¥", "Yen")
                    safe_new = new_text.replace("¥", "Yen")
                    print(f"    Updating table cell: '{safe_cell}' -> replacing '{safe_old}' with '{safe_new}'")
                    for paragraph in cell.text_frame.paragraphs:
                        for run in paragraph.runs:
                            if old_text in run.text:
                                run.text = run.text.replace(old_text, new_text)

def main():
    ticker_str = "285A"
    outdir = "./out"
    ticker_dir = find_ticker_dir(outdir, ticker_str)
    
    pptx_path = os.path.join(ticker_dir, "analysis", "Kioxia_Pitch_20260620.pptx")
    if not os.path.exists(pptx_path):
        print(f"Presentation not found: {pptx_path}")
        return
        
    print(f"Loading presentation for deck refresh: {pptx_path}...")
    prs = Presentation(pptx_path)
    
    # ロールフォワード（数値置換マッピング）の定義
    replacements = {
        "¥1,850.0 Bn": "¥1,920.0 Bn",
        "¥820.0 Bn": "¥880.0 Bn",
        "44.3%": "45.8%"
    }
    
    print("=== Deck Refresh Execution Plan ===")
    for k, v in replacements.items():
        safe_k = k.replace("¥", "Yen")
        safe_v = v.replace("¥", "Yen")
        print(f"  Mapping: '{safe_k}' -> '{safe_v}'")
        
    for slide_idx, slide in enumerate(prs.slides, 1):
        print(f"  Scanning Slide {slide_idx}...")
        for shape in slide.shapes:
            for old_val, new_val in replacements.items():
                refresh_text(shape, old_val, new_val)
                
    prs.save(pptx_path)
    print(f"Deck refresh complete. Saved updated presentation back to {pptx_path}")
    print("===================================\n")

if __name__ == "__main__":
    main()
