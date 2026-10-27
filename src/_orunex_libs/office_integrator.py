"""
office_integrator.py — Sovereign Office integration for Orunex V40.0
Expert control of Excel, Word, and PowerPoint via win32com (Native APIs).
Supports Macros, VBA, professional design, and complex structuring.
"""
import os
import time
import json
try:
    import win32com.client as win32 # type: ignore
    from win32com.client import constants
except ImportError:
    win32 = None

class OfficeIntegrator:
    def __init__(self):
        self.excel = None
        self.word = None
        self.pptx = None

    def _ensure_excel(self, visible=True):
        if not win32: return None
        try:
            self.excel = win32.GetActiveObject("Excel.Application")
        except:
            self.excel = win32.Dispatch("Excel.Application")
        self.excel.Visible = visible
        return self.excel

    def _ensure_word(self, visible=True):
        if not win32: return None
        try:
            self.word = win32.GetActiveObject("Word.Application")
        except:
            self.word = win32.Dispatch("Word.Application")
        self.word.Visible = visible
        return self.word

    def _ensure_pptx(self, visible=True):
        if not win32: return None
        try:
            self.pptx = win32.GetActiveObject("PowerPoint.Application")
        except:
            self.pptx = win32.Dispatch("PowerPoint.Application")
        self.pptx.Visible = visible
        return self.pptx

    # --- EXCEL EXPERT ---
    def vba_preflight(self, code):
        """V40.6: Verifica coherencia básica de VBA antes de inyección."""
        code_str = str(code)
        issues = []
        if "Sub " in code_str and "End Sub" not in code_str:
            issues.append("Bloque 'Sub' no cerrado con 'End Sub'.")
        if "Function " in code_str and "End Function" not in code_str:
            issues.append("Bloque 'Function' no cerrado.")
        # Limpieza de caracteres ilegales en nombres de componentes
        return issues

    def create_excel_macro(self, file_path, macro_name, vba_code):
        """Inyecta y ejecuta una Macro VBA en un libro de Excel (V40.6 Robust)."""
        issues = self.vba_preflight(vba_code)
        if issues:
            return f"[ERR] Pre-vuelo fallido: {', '.join(issues)}"

        xl = self._ensure_excel()
        if not xl: return "[ERR] win32com no disponible."
        
        try:
            full_path = os.path.abspath(file_path)
            if not os.path.exists(full_path):
                return f"[ERR] Archivo no hallado: {full_path}"
                
            wb = xl.Workbooks.Open(full_path)
            try:
                # V40.6: Sanitize component name
                comp_name = f"Orunex_{macro_name.replace(' ', '_')}"
                # Remove if already exists
                for comp in wb.VBProject.VBComponents:
                    if comp.Name == comp_name:
                        wb.VBProject.VBComponents.Remove(comp)
                        break
                
                module = wb.VBProject.VBComponents.Add(1) # Standard Module
                module.Name = comp_name
                module.CodeModule.AddFromString(vba_code)
                
                print(f"[OFFICE] Ejecutando Macro: {macro_name}...")
                xl.Run(macro_name)
                return f"[OK] Macro '{macro_name}' inyectada y validada en {os.path.basename(file_path)}"
            except Exception as e:
                return f"[WARN] Error de Seguridad Office (VBA Object Model): {e}"
        except Exception as e:
            return f"[ERR] Fallo Excel Expert: {e}"

    def format_as_dashboard(self, file_path):
        """V40.6: Formato Dashboard Multiserie."""
        xl = self._ensure_excel()
        if not xl: return "[ERR] Excel no disponible."
        try:
            wb = xl.Workbooks.Open(os.path.abspath(file_path))
            ws = wb.ActiveSheet
            xl.ActiveWindow.DisplayGridlines = False
            ws.Rows(1).Font.Bold = True
            ws.Columns.AutoFit()
            ws.Range("A2").Select()
            xl.ActiveWindow.FreezePanes = True
            return f"[OK] Dashboard Matrix aplicado a {os.path.basename(file_path)}"
        except Exception as e:
            return f"[ERR] Error Dashboard: {e}"

    # --- PPT EXPERT ---
    def create_slides_from_data(self, topic, slides_json):
        """V40.6: Diseño de Presentación Pro-Logic."""
        ppt = self._ensure_pptx()
        if not ppt: return "[ERR] PowerPoint no disponible."
        try:
            pres = ppt.Presentations.Add()
            data = json.loads(slides_json)
            for slide_data in data:
                layout = 1 if slide_data.get("type") == "title" else 2
                slide = pres.Slides.Add(len(pres.Slides) + 1, layout)
                slide.Shapes.Title.TextFrame.TextRange.Text = slide_data.get("title", "")
                if layout == 2:
                    slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = slide_data.get("body", "")
            
            out_name = f"PPT_{topic.replace(' ','_')}.pptx"
            path = os.path.join(os.getcwd(), "orunex_outputs", out_name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            pres.SaveAs(os.path.abspath(path))
            return f"[OK] Presentación creada: {out_name}"
        except Exception as e:
            return f"[ERR] PPT Expert: {e}"

# Unified entry point
_integrator = OfficeIntegrator()

def run_office_mission(target, action, payload, **kwargs):
    """Interfaz universal para misiones de Office V40.6."""
    target = str(target or "").lower().strip()
    action = str(action or "").lower().strip()
    
    if target == "excel":
        if action == "macro":
            return _integrator.create_excel_macro(kwargs.get("path"), kwargs.get("name"), payload)
        elif action == "dashboard":
            return _integrator.format_as_dashboard(kwargs.get("path") or payload)
    elif target in ("pptx", "powerpoint"):
        return _integrator.create_slides_from_data(kwargs.get("topic") or "General", payload)
    return f"[ERR] Acción Office '{action}' no reconocida."
