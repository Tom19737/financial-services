from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
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

def main():
    prs = Presentation()
    
    # プレゼンテーションサイズを 16:9 ワイドスクリーンに設定
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    
    # 配色設定 (ダークネイビーとゴールド／イエローをベースにした高級感あるテーマ)
    c_navy = RGBColor(27, 38, 59)
    c_gold = RGBColor(212, 175, 55)
    c_dark = RGBColor(30, 30, 30)
    c_gray = RGBColor(120, 120, 120)
    c_white = RGBColor(255, 255, 255)
    
    font_title = "Outfit"
    font_body = "Outfit"

    # ヘルパー関数: スライドにタイトルと背景色を追加
    def set_slide_base(slide, title_text, dark_bg=False):
        background = slide.background
        fill = background.fill
        if dark_bg:
            fill.solid()
            fill.fore_color.rgb = c_navy
        else:
            fill.solid()
            fill.fore_color.rgb = c_white
            
        # タイトルの追加 (ヘッダー)
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(12), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.name = font_title
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = c_white if dark_bg else c_navy

    # Slide 1: Title Slide (Dark Background)
    slide_layout = prs.slide_layouts[6] # Blank layout
    slide1 = prs.slides.add_slide(slide_layout)
    set_slide_base(slide1, "", dark_bg=True)
    
    # 中央のメインタイトル
    title_box = slide1.shapes.add_textbox(Inches(1), Inches(2.2), Inches(11.33), Inches(2))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.text = "Kioxia Holdings (285A.T)"
    p.font.name = font_title
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = c_gold
    
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    p2.text = "INVESTOR PITCH PRESENTATION"
    p2.font.name = font_title
    p2.font.size = Pt(24)
    p2.font.bold = True
    p2.font.color.rgb = c_white
    
    # 日付と署名
    meta_box = slide1.shapes.add_textbox(Inches(1), Inches(5.5), Inches(11.33), Inches(1))
    tf_meta = meta_box.text_frame
    p_meta = tf_meta.paragraphs[0]
    p_meta.alignment = PP_ALIGN.CENTER
    p_meta.text = "June 20, 2026 | Prepared by Financial Services Analyst"
    p_meta.font.name = font_body
    p_meta.font.size = Pt(14)
    p_meta.font.color.rgb = c_gray

    # Slide 2: Executive Summary (Light Background)
    slide2 = prs.slides.add_slide(slide_layout)
    set_slide_base(slide2, "I. EXECUTIVE SUMMARY")
    
    # メイン提案ボックス
    prop_box = slide2.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(6), Inches(4.5))
    tf_prop = prop_box.text_frame
    tf_prop.word_wrap = True
    p_prop = tf_prop.paragraphs[0]
    p_prop.text = "Investment Recommendation:"
    p_prop.font.name = font_title
    p_prop.font.size = Pt(18)
    p_prop.font.bold = True
    p_prop.font.color.rgb = c_navy
    
    p_rec = tf_prop.add_paragraph()
    p_rec.text = "BUY (Long)"
    p_rec.font.name = font_title
    p_rec.font.size = Pt(36)
    p_rec.font.bold = True
    p_rec.font.color.rgb = RGBColor(4, 120, 87) # Emerald Green
    
    p_target = tf_prop.add_paragraph()
    p_target.text = "Target Price: ¥1,500\nCurrent Price: ¥1,086 (Upside +38.1%)"
    p_target.font.name = font_body
    p_target.font.size = Pt(16)
    p_target.font.color.rgb = c_dark
    
    p_desc = tf_prop.add_paragraph()
    p_desc.text = "\nKioxia is the premier pure-play NAND flash manufacturer. As the market transitions rapidly from HDD to high-capacity Enterprise SSD (eSSD) driven by AI demands, Kioxia is poised for asymmetric earnings growth."
    p_desc.font.name = font_body
    p_desc.font.size = Pt(14)
    p_desc.font.color.rgb = c_dark
    
    # 統計指標テーブル
    rows, cols = 5, 2
    left, top, width, height = Inches(7), Inches(1.8), Inches(5.8), Inches(4)
    table_shape = slide2.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table
    table.columns[0].width = Inches(3.3)
    table.columns[1].width = Inches(2.5)
    
    table_data = [
        ("FY25E Revenue", "¥1,850.0 Bn"),
        ("FY25E EBITDA", "¥820.0 Bn"),
        ("FY25E EBITDA Margin", "44.3%"),
        ("NAND Revenue Mix", "100.0%"),
        ("Implied Valuation (PBR)", "1.80x")
    ]
    for row_idx, (k, v) in enumerate(table_data):
        cell_k = table.cell(row_idx, 0)
        cell_v = table.cell(row_idx, 1)
        cell_k.text = k
        cell_v.text = v
        for cell in [cell_k, cell_v]:
            for p in cell.text_frame.paragraphs:
                p.font.name = font_body
                p.font.size = Pt(14)
                p.font.bold = True if row_idx == 0 else False
                p.font.color.rgb = c_dark
                p.alignment = PP_ALIGN.LEFT if cell == cell_k else PP_ALIGN.RIGHT

    # Slide 3: Key Investment Pillars (Light Background)
    slide3 = prs.slides.add_slide(slide_layout)
    set_slide_base(slide3, "II. KEY INVESTMENT PILLARS")
    
    # 3つのピラーを列ボックスで配置
    widths = Inches(3.8)
    gap = Inches(0.4)
    for idx, (title, text) in enumerate([
        ("1. Enterprise SSD Shift", "High-capacity eSSDs (64TB+) represent Kioxia's core margin expansion opportunity. AI servers require massive throughput, allowing Kioxia to capture high pricing premiums and drive EBITDA margin towards 44%+."),
        ("2. BiCS 8 Process Lead", "Kioxia's 218-layer BiCS 8 technology focuses on practical cost efficiency and high manufacturing yields. This ensures the industry's lowest bit cost without over-investing in riskier 300+ layer architectures."),
        ("3. WD Merger Potential", "The potential merger with Western Digital's memory division will create a日米 Memory Champion. This consolidation will enhance pricing power, eliminate redundant capex, and maximize shareholder value.")
    ]):
        x_pos = Inches(0.5) + idx * (widths + gap)
        col_box = slide3.shapes.add_textbox(x_pos, Inches(1.8), widths, Inches(4.5))
        tf_col = col_box.text_frame
        tf_col.word_wrap = True
        
        p_title = tf_col.paragraphs[0]
        p_title.text = title
        p_title.font.name = font_title
        p_title.font.size = Pt(18)
        p_title.font.bold = True
        p_title.font.color.rgb = c_navy
        
        p_body = tf_col.add_paragraph()
        p_body.text = "\n" + text
        p_body.font.name = font_body
        p_body.font.size = Pt(13)
        p_body.font.color.rgb = c_dark
        
    # 保存
    outdir = "./out"
    ticker_dir = find_ticker_dir(outdir, "285A")
    target_path = os.path.join(ticker_dir, "analysis")
    os.makedirs(target_path, exist_ok=True)
    out_file = os.path.join(target_path, "Kioxia_Pitch_20260620.pptx")
    prs.save(out_file)
    print(f"Presentation saved to {out_file}")

if __name__ == "__main__":
    main()
