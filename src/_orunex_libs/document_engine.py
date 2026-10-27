# src/utils/document_engine.py
"""Motor de generacion de documentos profesionales para Orunex."""
import os
import re

OUTPUT_DIR = os.path.abspath(os.path.join(os.getcwd(), "orunex_outputs", "documentos"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_pdf(title: str, content: str, filename: str = None) -> str:
    """Genera un PDF profesional con titulo y contenido."""
    from fpdf import FPDF
    
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.pdf"
    
    path = os.path.join(OUTPUT_DIR, filename)
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Helper for Latin-1 safe text (fpdf default fonts don't support full unicode)
    def clean_text(txt):
        # Strip markdown bold/italic markers that FPDF renders as literal asterisks
        txt = re.sub(r'\*\*(.*?)\*\*', r'\1', txt)  # **bold**  bold
        txt = re.sub(r'\*(.*?)\*', r'\1', txt)        # *italic*  italic
        txt = re.sub(r'__(.*?)__', r'\1', txt)        # __bold__  bold
        return txt.encode('latin-1', 'ignore').decode('latin-1')
    
    clean_title = clean_text(title)
        
    # Titulo
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, clean_title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    # Linea separadora
    pdf.set_draw_color(0, 229, 255)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    # Contenido
    pdf.set_font("Helvetica", "", 11)
    for line in content.split('\n'):
        line = line.strip()
        safe_line = clean_text(line)
        
        if safe_line.startswith('# '):
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, safe_line[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
        elif safe_line.startswith('## '):
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, safe_line[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
        elif safe_line.startswith('- '):
            pdf.cell(5)
            pdf.cell(0, 6, f"   {safe_line[2:]}", new_x="LMARGIN", new_y="NEXT")
        elif safe_line:
            pdf.multi_cell(0, 6, safe_line)
        else:
            pdf.ln(3)
    
    pdf.output(path)
    return path


def create_docx(title: str, content: str, filename: str = None) -> str:
    """Genera un DOCX profesional."""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.docx"
    
    path = os.path.join(OUTPUT_DIR, filename)
    
    doc = Document()
    
    # Titulo
    heading = doc.add_heading(title, level=0)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0, 100, 180)
    
    # Contenido
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            doc.add_heading(line[2:], level=1)
        elif line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('- '):
            doc.add_paragraph(line[2:], style='List Bullet')
        elif line:
            doc.add_paragraph(line)
    
    doc.save(path)
    return path


def create_pptx(title: str, slides_text: str, filename: str = None, theme: str = "dark", accent_color: str = "#00E5FF") -> str:
    """Genera una presentacion PPTX profesional dinamica (Diseno Corporativo Orunex).
    
    Soporta temas: dark, light, corporate.
    Soporta layouts dinamicos incrustados en el texto usando etiquetas:
      {LAYOUT: TITLE}
      {LAYOUT: CONTENT}
      {LAYOUT: TWO_COLUMNS} y dividir con ---COL---
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    import requests
    from duckduckgo_search import DDGS
    
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.pptx"
    
    path = os.path.join(OUTPUT_DIR, filename)
    
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    # 1. Parsing Theme Colors
    def hex_to_rgb(hex_str: str) -> RGBColor:
        hex_str = hex_str.lstrip('#')
        if len(hex_str) != 6: return RGBColor(0, 229, 255) # Default cyan
        try:
            return RGBColor(*tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4)))
        except:
            return RGBColor(0, 229, 255)
            
    accent_rgb = hex_to_rgb(accent_color)
    
    t = theme.lower().strip()
    if t == "light":
        bg_rgb = RGBColor(250, 250, 253)
        title_rgb = RGBColor(20, 20, 30)
        text_rgb = RGBColor(60, 60, 70)
    elif t == "corporate":
        bg_rgb = RGBColor(255, 255, 255)
        title_rgb = RGBColor(0, 51, 102)
        text_rgb = RGBColor(30, 30, 30)
    else: # dark
        bg_rgb = RGBColor(10, 10, 18)
        title_rgb = RGBColor(255, 255, 255)
        text_rgb = RGBColor(210, 210, 220)
        
    def apply_bg(slide_obj):
        bg = slide_obj.background
        fill = bg.fill
        fill.solid()
        fill.fore_color.rgb = bg_rgb

    # 2. Portada (Title Slide)
    # Safe layout index  blank layout (index 6) with fallback
    _blank_layout_idx = min(6, len(prs.slide_layouts) - 1)
    slide_layout = prs.slide_layouts[_blank_layout_idx]  # Blank
    cover = prs.slides.add_slide(slide_layout)
    apply_bg(cover)
    
    # Titulo Portada
    txBox = cover.shapes.add_textbox(Inches(1), Inches(3), Inches(11.333), Inches(2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(54)
    p.font.bold = True
    p.font.color.rgb = accent_rgb
    p.alignment = PP_ALIGN.CENTER
    
    # 2.5 Image Helper (Phase 113)
    def add_image_from_query(slide_obj, query, left, top, width):
        try:
            assets_dir = os.path.join(os.path.dirname(OUTPUT_DIR), "assets")
            os.makedirs(assets_dir, exist_ok=True)
            results = DDGS().images(query, max_results=1)
            if results:
                img_url = results[0]['image']
                img_path = os.path.join(assets_dir, f"slide_img_{hash(query)}.jpg")
                r = requests.get(img_url, timeout=10)
                if r.status_code == 200:
                    with open(img_path, 'wb') as f:
                        f.write(r.content)
                    slide_obj.shapes.add_picture(img_path, left, top, width=width)
                    return True
        except: pass
        return False

    # 3. Parseo de Diapositivas
    from .os_executor import notify_progress
    slide_blocks = re.split(r'(?i)Slide\s*\d+\s*:\s*', slides_text)
    slide_blocks = [s.strip() for s in slide_blocks if s.strip()]
    
    # Fallback if model didn't use "Slide X:"
    if not slide_blocks and slides_text.strip():
        slide_blocks = [slides_text.strip()]
    
    total_slides = len(slide_blocks)
    for idx, block in enumerate(slide_blocks):
        notify_progress(f"Diseñando diapositiva {idx+1} de {total_slides}...", "info")
        lines = block.split('\n')
        slide_title = lines[0].strip() if lines else f"Diapositiva {idx+1}"
        slide_content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
        
        # Reconocimiento de Layouts (Case Insensitive)
        layout_type = "CONTENT"
        _upper_content = slide_content.upper()
        if "{LAYOUT: TITLE}" in _upper_content:
            layout_type = "TITLE"
            slide_content = re.sub(r'\{LAYOUT:\s*TITLE\}', '', slide_content, flags=re.IGNORECASE).strip()
        elif "{LAYOUT: TWO_COLUMNS}" in _upper_content:
            layout_type = "TWO_COLUMNS"
            slide_content = re.sub(r'\{LAYOUT:\s*TWO_COLUMNS\}', '', slide_content, flags=re.IGNORECASE).strip()
        elif "{LAYOUT: CONTENT}" in _upper_content:
            slide_content = re.sub(r'\{LAYOUT:\s*CONTENT\}', '', slide_content, flags=re.IGNORECASE).strip()
            
        # Strip any other {LAYOUT: xxx} tags defensively before rendering (IGNORECASE)
        slide_content = re.sub(r'\{LAYOUT:[^}]*\}', '', slide_content, flags=re.IGNORECASE).strip()
        slide = prs.slides.add_slide(prs.slide_layouts[_blank_layout_idx])
        apply_bg(slide)
        
        # Titulo de la diapositiva
        txTitle = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.733), Inches(1.0))
        tfTitle = txTitle.text_frame
        tfTitle.word_wrap = True
        pT = tfTitle.paragraphs[0]
        pT.text = str(slide_title)
        pT.font.size = Pt(32)
        pT.font.bold = True
        pT.font.color.rgb = title_rgb
        
        # Renderizado de contenido visual dinamico
        if not slide_content: continue
        
        if layout_type == "TWO_COLUMNS":
            parts = re.split(r'(?i)---COL---', slide_content)
            col1_text = parts[0].strip()
            col2_text = parts[1].strip() if len(parts) > 1 else ""
            
            # Left Box
            bx1 = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(5.5), Inches(5))
            t1 = bx1.text_frame
            t1.word_wrap = True
            for line in col1_text.split('\n'):
                pC = t1.add_paragraph()
                pC.text = line.strip()
                pC.font.size = Pt(18)
                pC.font.color.rgb = text_rgb
                pC.space_after = Pt(8)
                
            # Right Box
            if col2_text:
                # Check for image in col2
                img_m = re.search(r'\[IMG:\s*(.*?)\]', col2_text)
                if img_m:
                    query = img_m.group(1).strip()
                    add_image_from_query(slide, query, Inches(6.6), Inches(1.8), Inches(5.5))
                else:
                    bx2 = slide.shapes.add_textbox(Inches(6.6), Inches(1.8), Inches(5.5), Inches(5))
                    t2 = bx2.text_frame
                    # ... rest same
                    
        elif layout_type == "TITLE":
            # Un texto centrado grande para enfatizar conceptos
            bx = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.3), Inches(3))
            t = bx.text_frame
            t.word_wrap = True
            for line in slide_content.split('\n'):
                pC = t.add_paragraph()
                pC.text = line.strip()
                pC.font.size = Pt(28)
                pC.font.color.rgb = accent_rgb
                pC.alignment = PP_ALIGN.CENTER
                pC.space_after = Pt(10)
                
        else: # Normal CONTENT
            bx = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.733), Inches(5))
            t = bx.text_frame
            t.word_wrap = True
            for line in slide_content.split('\n'):
                pC = t.add_paragraph()
                pC.text = line.strip()
                pC.font.size = Pt(22)
                pC.font.color.rgb = text_rgb
                pC.space_after = Pt(12)
                
    prs.save(path)
    return path

def create_excel(title: str, content: str, filename: str = None) -> str:
    """Genera un archivo Excel a partir de datos estructurados."""
    import pandas as pd
    import io
    
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.xlsx"
        
    path = os.path.join(OUTPUT_DIR, filename)
    
    try:
        # Try parsing as CSV format
        df = pd.read_csv(io.StringIO(content.strip()), sep=None, engine='python')
        df.to_excel(path, index=False)
        return path
    except Exception as e:
        # Fallback to manual text saving as .csv if Excel parsing totally fails
        csv_path = path.replace('.xlsx', '.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return csv_path

def create_csv(title: str, content: str, filename: str = None) -> str:
    """Genera un archivo CSV simple."""
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.csv"
        
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    return path

def create_md(title: str, content: str, filename: str = None) -> str:
    """Genera un archivo Markdown documentado."""
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.md"
        
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{content}")
    return path

def create_html(title: str, content: str, filename: str = None) -> str:
    """Genera un archivo HTML renderizable con estilos modernos basicos."""
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_')
        filename = f"{safe_title}.html"
        
    path = os.path.join(OUTPUT_DIR, filename)
    
    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; padding: 20px; max-width: 900px; margin: 0 auto; color: #333; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        code {{ font-family: Consolas, monospace; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {content}
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_template)
    return path
