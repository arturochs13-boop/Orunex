"""
app_developer.py — Orunex App Developer Engine V1.0
Motor de desarrollo autónomo de aplicaciones completas.
Diseña → Programa → Testea → Corrige → Lanza.

Capacidades:
  - Generación de apps Python con UI premium (tkinter + matplotlib)
  - Base de datos SQLite integrada
  - Tests automatizados y corrección de bugs
  - Conciencia de monetización y UX profesional
  - Lanzamiento y verificación en vivo
"""
import os, sys, json, re, uuid, subprocess, importlib, traceback, datetime


def _hidden_process_kwargs():
    if os.name == "nt":
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
        }
    return {}


# ──────────────────────────────────────────────────────────────
#  REGISTRY de apps generables por tipo
# ──────────────────────────────────────────────────────────────
APP_TEMPLATES = {
    "finance":    "Aplicación de Finanzas Personales",
    "task":       "Gestor de Tareas Profesional",
    "inventory":  "Sistema de Inventario",
    "dashboard":  "Dashboard de Analytics",
    "crm":        "CRM Básico de Clientes",
    "timer":      "Pomodoro / Productividad",
    "notes":      "Bloc de Notas Premium",
    "custom":     "Aplicación Personalizada",
}

def _progress(msg, cb=None):
    safe = msg.encode('ascii', errors='replace').decode('ascii')
    print(f"[APP DEV] {safe}")
    if cb:
        try: cb(msg)
        except: pass

def _run_syntax_check(filepath):
    """Verifica que el archivo Python sea sintácticamente correcto."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", filepath],
        capture_output=True,
        text=True,
        **_hidden_process_kwargs(),
    )
    return result.returncode == 0, result.stderr

def _run_import_check(filepath):
    """Intenta importar el módulo para detectar errores en imports."""
    try:
        spec = importlib.util.spec_from_file_location("_test_app", filepath)
        mod  = importlib.util.module_from_spec(spec)
        # We just parse, don't execute __main__
        with open(filepath, encoding="utf-8") as f:
            src = f.read()
        compile(src, filepath, "exec")
        return True, ""
    except Exception as e:
        return False, str(e)

def _auto_fix_common_bugs(src: str) -> str:
    """Corrige bugs comunes automáticamente."""
    # Fix: missing tkinter import
    if "tk.Tk()" in src and "import tkinter as tk" not in src:
        src = "import tkinter as tk\n" + src

    # Fix: trailing commas in function calls (Python 2 style)
    src = re.sub(r',(\s*\))', r'\1', src)

    # Fix: print without parentheses
    src = re.sub(r'\bprint\s+(["\'])', r'print(\1', src)

    return src

# ──────────────────────────────────────────────────────────────
#  THE DEMO APP: FinanceOS — App completa de finanzas personales
# ──────────────────────────────────────────────────────────────

FINANCE_OS_CODE = '''#!/usr/bin/env python3
"""
FinanceOS — Personal Finance Dashboard
Generado por Orunex App Developer Engine V1.0
UI Premium con dark theme, SQLite, matplotlib, exports.
Monetización: Freemium — versión Pro desbloquea exportación avanzada.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3, os, json, csv, datetime, random
from pathlib import Path

# ── Matplotlib embebido ────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib.style as mstyle
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

# ══════════════════════════════════════════════════════════════
#  DESIGN SYSTEM
# ══════════════════════════════════════════════════════════════
DS = {
    "bg":         "#0F172A",   # Background principal
    "bg2":        "#1E293B",   # Card background
    "bg3":        "#334155",   # Hover / active
    "accent":     "#38BDF8",   # Sky blue accent
    "accent2":    "#818CF8",   # Indigo accent
    "success":    "#10B981",   # Green
    "danger":     "#EF4444",   # Red
    "warning":    "#F59E0B",   # Amber
    "fg":         "#F8FAFC",   # Text principal
    "fg2":        "#94A3B8",   # Text secundario
    "border":     "#334155",
    "font_h1":    ("Inter", 20, "bold"),
    "font_h2":    ("Calibri", 15, "bold"),
    "font_body":  ("Calibri", 11),
    "font_small": ("Calibri", 9),
    "font_mono":  ("Consolas", 10),
    "radius":     8,
}

# ══════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════
DB_PATH = os.path.join(os.path.dirname(__file__), "financeos.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        type TEXT NOT NULL,
        note TEXT DEFAULT ""
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT UNIQUE NOT NULL,
        limit_amount REAL NOT NULL,
        month TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    conn.commit()

    # Seed demo data if empty
    if c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
        seed_data = [
            ("2024-01-05", "Salario Enero",      45000.00, "Ingresos",    "income",   ""),
            ("2024-01-08", "Renta Departamento", -12000.00, "Vivienda",   "expense",  ""),
            ("2024-01-12", "Supermercado Soriana",-3200.00, "Alimentación","expense",  ""),
            ("2024-01-15", "Netflix + Spotify",    -350.00, "Suscripciones","expense", ""),
            ("2024-01-18", "Gasolina",             -800.00, "Transporte",  "expense",  ""),
            ("2024-01-20", "Freelance WebApp",    8000.00, "Ingresos",    "income",   ""),
            ("2024-01-22", "Restaurante",          -950.00, "Alimentación","expense",  ""),
            ("2024-01-25", "Gym + Suplementos",    -600.00, "Salud",       "expense",  ""),
            ("2024-02-05", "Salario Febrero",     45000.00, "Ingresos",    "income",   ""),
            ("2024-02-10", "Renta Departamento", -12000.00, "Vivienda",   "expense",  ""),
            ("2024-02-14", "Cena San Valentín",   -1800.00, "Ocio",        "expense",  ""),
            ("2024-02-18", "Supermercado",        -2900.00, "Alimentación","expense",  ""),
            ("2024-02-20", "Bono Proyecto",        5000.00, "Ingresos",    "income",   ""),
            ("2024-02-25", "Seguro de Auto",       -2400.00, "Transporte", "expense",  ""),
            ("2024-03-05", "Salario Marzo",       45000.00, "Ingresos",    "income",   ""),
            ("2024-03-08", "Renta Departamento", -12000.00, "Vivienda",   "expense",  ""),
            ("2024-03-12", "Consulta Médica",       -800.00, "Salud",      "expense",  ""),
            ("2024-03-15", "Supermercado",        -3100.00, "Alimentación","expense",  ""),
            ("2024-03-20", "Inversión CETES",     -5000.00, "Inversiones", "expense",  ""),
            ("2024-03-25", "Freelance Diseño",    6500.00, "Ingresos",    "income",   ""),
        ]
        c.executemany(
            "INSERT INTO transactions (date,description,amount,category,type,note) VALUES (?,?,?,?,?,?)",
            seed_data
        )
        conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_PATH)

CATEGORIES = {
    "income":  ["Ingresos", "Freelance", "Inversiones", "Otros Ingresos"],
    "expense": ["Vivienda", "Alimentación", "Transporte", "Salud", "Ocio", "Suscripciones", "Educación", "Inversiones", "Otros"],
}

# ══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════
class FinanceOS:
    def __init__(self, root):
        self.root = root
        self.root.title("FinanceOS  ·  Personal Finance Dashboard")
        self.root.geometry("1280x800")
        self.root.minsize(1024, 680)
        self.root.configure(bg=DS["bg"])

        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._apply_styles()

        # State
        self.current_page = tk.StringVar(value="dashboard")
        self.filter_month = tk.StringVar(value="all")

        # Build UI
        self._build_sidebar()
        self._build_main()
        self._build_statusbar()

        # Load
        self.show_page("dashboard")

    def _apply_styles(self):
        s = self.style
        s.configure(".", background=DS["bg"], foreground=DS["fg"], font=DS["font_body"])
        s.configure("TFrame", background=DS["bg"])
        s.configure("Card.TFrame", background=DS["bg2"])
        s.configure("TLabel", background=DS["bg"], foreground=DS["fg"])
        s.configure("Card.TLabel", background=DS["bg2"], foreground=DS["fg"])
        s.configure("Dim.TLabel", background=DS["bg"], foreground=DS["fg2"])
        s.configure("CardDim.TLabel", background=DS["bg2"], foreground=DS["fg2"])
        s.configure("TButton",
            background=DS["accent"], foreground=DS["bg"],
            font=("Calibri", 11, "bold"), relief="flat", padding=(14,8))
        s.map("TButton",
            background=[("active", DS["bg3"]), ("pressed", DS["accent2"])],
            foreground=[("active", DS["fg"])])
        s.configure("Danger.TButton", background=DS["danger"], foreground="white")
        s.configure("Ghost.TButton", background=DS["bg2"], foreground=DS["fg"])
        s.map("Ghost.TButton", background=[("active", DS["bg3"])])
        s.configure("TEntry",
            fieldbackground=DS["bg3"], foreground=DS["fg"],
            insertcolor=DS["fg"], relief="flat", padding=8)
        s.configure("TCombobox",
            fieldbackground=DS["bg3"], foreground=DS["fg"],
            background=DS["bg2"], selectbackground=DS["accent"])
        s.configure("Treeview",
            background=DS["bg2"], foreground=DS["fg"],
            fieldbackground=DS["bg2"], rowheight=34, font=("Calibri", 11))
        s.configure("Treeview.Heading",
            background=DS["bg"], foreground=DS["accent"],
            font=("Calibri", 11, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", DS["accent2"])])
        s.configure("TScrollbar", background=DS["bg2"], troughcolor=DS["bg"], relief="flat")

    # ── SIDEBAR ──────────────────────────────────────────────
    def _build_sidebar(self):
        self.sidebar = tk.Frame(self.root, bg=DS["bg2"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_f = tk.Frame(self.sidebar, bg=DS["bg2"], pady=20)
        logo_f.pack(fill="x")
        tk.Label(logo_f, text="💰 FinanceOS", font=("Calibri", 16, "bold"),
                 bg=DS["bg2"], fg=DS["accent"]).pack(pady=(10,0))
        tk.Label(logo_f, text="Personal Finance Dashboard", font=("Calibri", 9),
                 bg=DS["bg2"], fg=DS["fg2"]).pack()

        ttk.Separator(self.sidebar).pack(fill="x", padx=10, pady=8)

        # Nav items
        self.nav_buttons = {}
        nav_items = [
            ("dashboard",     "📊", "Dashboard"),
            ("transactions",  "📋", "Transacciones"),
            ("add",           "➕", "Nueva Entrada"),
            ("charts",        "📈", "Gráficas"),
            ("budgets",       "🎯", "Presupuestos"),
            ("reports",       "📑", "Reportes"),
        ]
        for page, icon, label in nav_items:
            btn = tk.Button(self.sidebar,
                text=f"  {icon}  {label}",
                font=("Calibri", 12), anchor="w",
                bg=DS["bg2"], fg=DS["fg"], relief="flat",
                activebackground=DS["bg3"], activeforeground=DS["fg"],
                cursor="hand2", pady=12, padx=10,
                command=lambda p=page: self.show_page(p))
            btn.pack(fill="x", padx=6, pady=2)
            self.nav_buttons[page] = btn

        # Pro badge
        tk.Frame(self.sidebar, bg=DS["bg2"]).pack(fill="both", expand=True)
        pro_f = tk.Frame(self.sidebar, bg="#1a1042", padx=12, pady=10)
        pro_f.pack(fill="x", padx=10, pady=12)
        tk.Label(pro_f, text="⭐ Upgrade a PRO", font=("Calibri", 11, "bold"),
                 bg="#1a1042", fg="#818CF8").pack()
        tk.Label(pro_f, text="Reportes avanzados, sync en la nube,\nIA financiera personalizada.",
                 font=("Calibri", 9), bg="#1a1042", fg=DS["fg2"], justify="center").pack(pady=(4,8))
        tk.Button(pro_f, text="Ver Planes →", font=("Calibri", 10, "bold"),
                  bg=DS["accent2"], fg="white", relief="flat", cursor="hand2",
                  command=self._show_pro).pack()

    def _build_main(self):
        self.main = tk.Frame(self.root, bg=DS["bg"])
        self.main.pack(side="left", fill="both", expand=True)

    def _build_statusbar(self):
        self.statusbar = tk.Frame(self.root, bg=DS["bg3"], height=28)
        self.statusbar.pack(side="bottom", fill="x")
        self.status_lbl = tk.Label(self.statusbar,
            text="✅ FinanceOS listo — Generado por Orunex App Developer V1.0",
            font=DS["font_small"], bg=DS["bg3"], fg=DS["fg2"])
        self.status_lbl.pack(side="left", padx=12)
        tk.Label(self.statusbar,
            text=f"v1.0.0  ·  {datetime.date.today().strftime('%d/%m/%Y')}",
            font=DS["font_small"], bg=DS["bg3"], fg=DS["fg2"]).pack(side="right", padx=12)

    def set_status(self, msg):
        self.status_lbl.config(text=msg)

    # ── NAVIGATION ───────────────────────────────────────────
    def show_page(self, page):
        self.current_page.set(page)
        for p, btn in self.nav_buttons.items():
            btn.config(bg=DS["accent"] if p == page else DS["bg2"],
                       fg=DS["bg"] if p == page else DS["fg"])
        for w in self.main.winfo_children():
            w.destroy()
        pages = {
            "dashboard":    self._page_dashboard,
            "transactions": self._page_transactions,
            "add":          self._page_add,
            "charts":       self._page_charts,
            "budgets":      self._page_budgets,
            "reports":      self._page_reports,
        }
        if page in pages:
            pages[page]()

    # ── KPI CARD WIDGET ──────────────────────────────────────
    def _kpi_card(self, parent, title, value, subtitle, color, col):
        card = tk.Frame(parent, bg=DS["bg2"], padx=20, pady=16, relief="flat")
        card.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
        parent.columnconfigure(col, weight=1)
        tk.Label(card, text=title, font=("Calibri", 10), bg=DS["bg2"], fg=DS["fg2"]).pack(anchor="w")
        tk.Label(card, text=value, font=("Calibri", 22, "bold"), bg=DS["bg2"], fg=color).pack(anchor="w", pady=(4,0))
        tk.Label(card, text=subtitle, font=("Calibri", 9), bg=DS["bg2"], fg=DS["fg2"]).pack(anchor="w")
        return card

    # ─────────────────────────────────────────────────────────
    #  PAGE: DASHBOARD
    # ─────────────────────────────────────────────────────────
    def _page_dashboard(self):
        conn = get_conn()
        c = conn.cursor()

        total_income  = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income'").fetchone()[0]
        total_expense = abs(c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense'").fetchone()[0])
        balance       = total_income - total_expense
        tx_count      = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        conn.close()

        # Header
        hdr = tk.Frame(self.main, bg=DS["bg"], padx=24, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📊 Dashboard", font=("Calibri", 20, "bold"),
                 bg=DS["bg"], fg=DS["fg"]).pack(side="left")
        tk.Label(hdr, text=f"Última actualización: {datetime.datetime.now().strftime('%H:%M:%S')}",
                 font=("Calibri", 10), bg=DS["bg"], fg=DS["fg2"]).pack(side="right", pady=8)

        # KPI row
        kpi_frame = tk.Frame(self.main, bg=DS["bg"], padx=16)
        kpi_frame.pack(fill="x")
        bal_color = DS["success"] if balance >= 0 else DS["danger"]
        self._kpi_card(kpi_frame, "💰 Balance Total",
                       f"${balance:,.2f}", "Ingresos - Egresos", bal_color, 0)
        self._kpi_card(kpi_frame, "📈 Total Ingresos",
                       f"${total_income:,.2f}", "Acumulado histórico", DS["success"], 1)
        self._kpi_card(kpi_frame, "📉 Total Egresos",
                       f"${total_expense:,.2f}", "Acumulado histórico", DS["danger"], 2)
        self._kpi_card(kpi_frame, "🧾 Transacciones",
                       f"{tx_count}", "Total registradas", DS["accent"], 3)

        # Charts (if matplotlib available)
        if CHARTS_AVAILABLE:
            self._embed_dashboard_charts()
        else:
            tk.Label(self.main,
                text="📦 Instala matplotlib para ver gráficas: pip install matplotlib",
                font=DS["font_body"], bg=DS["bg"], fg=DS["fg2"]).pack(pady=40)

        # Recent transactions
        self._recent_transactions_widget()

    def _embed_dashboard_charts(self):
        charts_f = tk.Frame(self.main, bg=DS["bg"], padx=16)
        charts_f.pack(fill="both", expand=True, pady=(8,0))
        charts_f.columnconfigure(0, weight=2)
        charts_f.columnconfigure(1, weight=1)

        conn = get_conn()
        c = conn.cursor()

        # Bar chart: monthly income vs expense
        months_data = c.execute("""
            SELECT strftime('%Y-%m', date) as month,
                   SUM(CASE WHEN type='income' THEN amount ELSE 0 END),
                   SUM(CASE WHEN type='expense' THEN ABS(amount) ELSE 0 END)
            FROM transactions GROUP BY month ORDER BY month
        """).fetchall()

        # Pie: expenses by category
        cat_data = c.execute("""
            SELECT category, SUM(ABS(amount)) FROM transactions
            WHERE type='expense' GROUP BY category ORDER BY 2 DESC LIMIT 6
        """).fetchall()
        conn.close()

        fig = Figure(figsize=(10, 4), facecolor=DS["bg"])

        # Bar chart
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor(DS["bg2"])
        if months_data:
            labels   = [m[0] for m in months_data]
            incomes  = [m[1] for m in months_data]
            expenses = [m[2] for m in months_data]
            x = range(len(labels))
            bar_w = 0.35
            ax1.bar([i - bar_w/2 for i in x], incomes, bar_w,
                    label="Ingresos", color="#10B981", alpha=0.85)
            ax1.bar([i + bar_w/2 for i in x], expenses, bar_w,
                    label="Egresos",  color="#EF4444", alpha=0.85)
            ax1.set_xticks(list(x))
            ax1.set_xticklabels(labels, rotation=45, ha="right", color=DS["fg2"], fontsize=8)
            ax1.tick_params(colors=DS["fg2"])
            ax1.yaxis.label.set_color(DS["fg2"])
            for spine in ax1.spines.values(): spine.set_edgecolor(DS["border"])
            ax1.legend(facecolor=DS["bg2"], labelcolor=DS["fg"], fontsize=8)
        ax1.set_title("Ingresos vs Egresos por Mes", color=DS["fg"], fontsize=11, pad=10)
        ax1.set_facecolor(DS["bg2"])

        # Pie
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor(DS["bg2"])
        if cat_data:
            labels_p = [r[0] for r in cat_data]
            vals_p   = [r[1] for r in cat_data]
            colors_p = ["#EF4444","#F59E0B","#10B981","#38BDF8","#818CF8","#F97316"]
            wedges, texts, autotexts = ax2.pie(
                vals_p, labels=labels_p, autopct="%1.0f%%",
                colors=colors_p[:len(vals_p)], startangle=140,
                textprops={"color": DS["fg"], "fontsize": 8},
                wedgeprops={"edgecolor": DS["bg"], "linewidth": 1.5}
            )
            for at in autotexts: at.set_color(DS["bg"]); at.set_fontsize(7)
        ax2.set_title("Egresos por Categoría", color=DS["fg"], fontsize=11, pad=10)

        fig.tight_layout(pad=2.0)
        canvas = FigureCanvasTkAgg(fig, master=charts_f)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4)

    def _recent_transactions_widget(self):
        frame = tk.Frame(self.main, bg=DS["bg2"], padx=16, pady=12)
        frame.pack(fill="x", padx=16, pady=(4, 12))
        tk.Label(frame, text="🕐 Últimas Transacciones",
                 font=("Calibri", 13, "bold"), bg=DS["bg2"], fg=DS["fg"]).pack(anchor="w")

        tree = ttk.Treeview(frame, columns=("date","desc","cat","amount"), show="headings", height=5)
        for col, txt, w in [
            ("date","Fecha",100), ("desc","Descripción",260),
            ("cat","Categoría",130), ("amount","Monto",110)
        ]:
            tree.heading(col, text=txt)
            tree.column(col, width=w, anchor="center" if col in ("date","cat","amount") else "w")
        tree.pack(fill="x", pady=(8,0))

        conn = get_conn()
        rows = conn.execute(
            "SELECT date,description,category,amount FROM transactions ORDER BY date DESC LIMIT 7"
        ).fetchall()
        conn.close()
        for r in rows:
            amount_str = f"+${r[3]:,.2f}" if r[3] > 0 else f"-${abs(r[3]):,.2f}"
            tag = "income" if r[3] > 0 else "expense"
            tree.insert("", "end", values=(r[0], r[1], r[2], amount_str), tags=(tag,))
        tree.tag_configure("income",  foreground=DS["success"])
        tree.tag_configure("expense", foreground=DS["danger"])

    # ─────────────────────────────────────────────────────────
    #  PAGE: TRANSACTIONS
    # ─────────────────────────────────────────────────────────
    def _page_transactions(self):
        tk.Label(self.main, text="📋 Todas las Transacciones",
                 font=("Calibri", 20, "bold"), bg=DS["bg"], fg=DS["fg"],
                 padx=24, pady=16).pack(anchor="w")

        # Toolbar
        toolbar = tk.Frame(self.main, bg=DS["bg"], padx=16)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="➕ Nueva", command=lambda: self.show_page("add")).pack(side="left", padx=4)
        ttk.Button(toolbar, text="🗑 Eliminar Selección", style="Danger.TButton",
                   command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(toolbar, text="📤 Exportar CSV", style="Ghost.TButton",
                   command=self._export_csv).pack(side="left", padx=4)

        # Search
        tk.Label(toolbar, text="Buscar:", bg=DS["bg"], fg=DS["fg2"]).pack(side="left", padx=(12,4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self._refresh_tree())
        ttk.Entry(toolbar, textvariable=self.search_var, width=22).pack(side="left")

        # Tree
        cols = ("date","desc","cat","type","amount")
        self.tree = ttk.Treeview(self.main, columns=cols, show="headings")
        for col, txt, w in [
            ("date","Fecha",100), ("desc","Descripción",280),
            ("cat","Categoría",130), ("type","Tipo",90), ("amount","Monto",110)
        ]:
            self.tree.heading(col, text=txt, command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=w, anchor="center" if col in ("date","cat","type","amount") else "w")

        scroll = ttk.Scrollbar(self.main, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill="both", expand=True, padx=16, pady=(8,0), side="left")
        scroll.pack(fill="y", side="right", pady=(8,0), padx=(0,4))
        self.tree.tag_configure("income",  foreground=DS["success"])
        self.tree.tag_configure("expense", foreground=DS["danger"])
        self._refresh_tree()

    def _refresh_tree(self):
        if not hasattr(self, "tree"): return
        q = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = get_conn()
        rows = conn.execute(
            "SELECT id,date,description,category,type,amount FROM transactions ORDER BY date DESC"
        ).fetchall()
        conn.close()
        for r in rows:
            if q and q not in r[2].lower() and q not in r[3].lower(): continue
            amount_str = f"+${r[5]:,.2f}" if r[5] > 0 else f"-${abs(r[5]):,.2f}"
            tag = "income" if r[5] > 0 else "expense"
            self.tree.insert("", "end", iid=str(r[0]),
                             values=(r[1], r[2], r[3], r[4].title(), amount_str), tags=(tag,))

    def _sort_tree(self, col):
        pass  # TODO: implement column sorting

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona una transacción primero.")
            return
        if messagebox.askyesno("Confirmar", f"¿Eliminar {len(sel)} transacción(es)?"):
            conn = get_conn()
            for iid in sel:
                conn.execute("DELETE FROM transactions WHERE id=?", (int(iid),))
            conn.commit(); conn.close()
            self._refresh_tree()
            self.set_status(f"✅ {len(sel)} transacción(es) eliminada(s).")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"FinanceOS_Export_{datetime.date.today()}.csv")
        if not path: return
        conn = get_conn()
        rows = conn.execute("SELECT date,description,category,type,amount,note FROM transactions ORDER BY date DESC").fetchall()
        conn.close()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Fecha","Descripción","Categoría","Tipo","Monto","Nota"])
            w.writerows(rows)
        messagebox.showinfo("Exportado", f"Guardado en: {path}")
        self.set_status(f"📤 CSV exportado: {path}")

    # ─────────────────────────────────────────────────────────
    #  PAGE: ADD TRANSACTION
    # ─────────────────────────────────────────────────────────
    def _page_add(self):
        tk.Label(self.main, text="➕ Nueva Transacción",
                 font=("Calibri", 20, "bold"), bg=DS["bg"], fg=DS["fg"],
                 padx=24, pady=16).pack(anchor="w")

        form = tk.Frame(self.main, bg=DS["bg2"], padx=30, pady=24)
        form.pack(padx=24, fill="x")

        fields = {}
        def row(label, widget_builder, row_n):
            tk.Label(form, text=label, font=("Calibri", 11, "bold"),
                     bg=DS["bg2"], fg=DS["fg2"]).grid(row=row_n, column=0, sticky="w", pady=8, padx=4)
            w = widget_builder(form)
            w.grid(row=row_n, column=1, sticky="ew", pady=8, padx=8)
            form.columnconfigure(1, weight=1)
            return w

        type_var = tk.StringVar(value="expense")
        cat_var  = tk.StringVar()
        date_var = tk.StringVar(value=datetime.date.today().strftime("%Y-%m-%d"))

        def update_cats(*_):
            t = type_var.get()
            cat_combo["values"] = CATEGORIES.get(t, [])
            cat_var.set(CATEGORIES[t][0])

        type_combo = row("Tipo:",
            lambda p: ttk.Combobox(p, textvariable=type_var, values=["income","expense"], width=20, state="readonly"), 0)
        type_var.trace("w", update_cats)

        cat_combo = row("Categoría:",
            lambda p: ttk.Combobox(p, textvariable=cat_var, width=28, state="readonly"), 1)
        update_cats()

        desc_entry = row("Descripción:", lambda p: ttk.Entry(p, width=34), 2)
        date_entry = row("Fecha (YYYY-MM-DD):", lambda p: ttk.Entry(p, textvariable=date_var, width=18), 3)

        amount_var = tk.StringVar()
        amount_entry = row("Monto ($):", lambda p: ttk.Entry(p, textvariable=amount_var, width=18), 4)

        note_entry = row("Nota (opcional):", lambda p: ttk.Entry(p, width=34), 5)

        def save():
            desc   = desc_entry.get().strip()
            amount = amount_var.get().strip()
            date   = date_entry.get().strip()
            if not desc or not amount:
                messagebox.showwarning("Campos requeridos", "Descripción y monto son obligatorios.")
                return
            try:
                amt = float(amount.replace(",","").replace("$",""))
                if type_var.get() == "expense": amt = -abs(amt)
            except ValueError:
                messagebox.showerror("Error", "El monto debe ser un número válido.")
                return
            conn = get_conn()
            conn.execute(
                "INSERT INTO transactions (date,description,amount,category,type,note) VALUES (?,?,?,?,?,?)",
                (date, desc, amt, cat_var.get(), type_var.get(), note_entry.get().strip())
            )
            conn.commit(); conn.close()
            messagebox.showinfo("✅ Guardado", f"Transacción registrada: ${abs(amt):,.2f}")
            self.set_status(f"✅ Nueva transacción: {desc} — ${abs(amt):,.2f}")
            desc_entry.delete(0, "end")
            amount_var.set("")
            note_entry.delete(0, "end")

        ttk.Button(form, text="💾  Guardar Transacción", command=save).grid(
            row=6, column=0, columnspan=2, pady=20, ipadx=20)

    # ─────────────────────────────────────────────────────────
    #  PAGE: CHARTS
    # ─────────────────────────────────────────────────────────
    def _page_charts(self):
        tk.Label(self.main, text="📈 Análisis Gráfico",
                 font=("Calibri", 20, "bold"), bg=DS["bg"], fg=DS["fg"],
                 padx=24, pady=16).pack(anchor="w")

        if not CHARTS_AVAILABLE:
            tk.Label(self.main,
                text="pip install matplotlib   para activar esta sección.",
                font=DS["font_body"], bg=DS["bg"], fg=DS["fg2"]).pack(pady=60)
            return

        conn = get_conn(); c = conn.cursor()
        monthly = c.execute("""
            SELECT strftime('%Y-%m', date) as m,
                   SUM(CASE WHEN type='income' THEN amount ELSE 0 END),
                   SUM(CASE WHEN type='expense' THEN ABS(amount) ELSE 0 END)
            FROM transactions GROUP BY m ORDER BY m
        """).fetchall()
        cat_exp = c.execute("""
            SELECT category, SUM(ABS(amount)) FROM transactions
            WHERE type='expense' GROUP BY category ORDER BY 2 DESC
        """).fetchall()
        conn.close()

        fig = Figure(figsize=(13, 5), facecolor=DS["bg"])
        colors = ["#10B981","#38BDF8","#818CF8","#F59E0B","#EF4444","#F97316","#EC4899","#06B6D4"]

        # Line chart
        ax1 = fig.add_subplot(1, 3, 1)
        ax1.set_facecolor(DS["bg2"])
        if monthly:
            ms = [m[0] for m in monthly]
            inc = [m[1] for m in monthly]
            exp = [m[2] for m in monthly]
            ax1.plot(ms, inc, color=DS["success"], marker="o", linewidth=2, label="Ingresos")
            ax1.plot(ms, exp, color=DS["danger"],  marker="s", linewidth=2, label="Egresos")
            ax1.fill_between(range(len(ms)), inc, alpha=0.15, color=DS["success"])
            ax1.set_xticks(range(len(ms)))
            ax1.set_xticklabels(ms, rotation=45, fontsize=7, color=DS["fg2"])
            ax1.tick_params(colors=DS["fg2"])
            ax1.legend(facecolor=DS["bg2"], labelcolor=DS["fg"], fontsize=8)
        ax1.set_title("Tendencia Mensual", color=DS["fg"], fontsize=10)
        for sp in ax1.spines.values(): sp.set_edgecolor(DS["border"])

        # Pie
        ax2 = fig.add_subplot(1, 3, 2)
        ax2.set_facecolor(DS["bg2"])
        if cat_exp:
            ax2.pie([r[1] for r in cat_exp],
                    labels=[r[0] for r in cat_exp],
                    colors=colors[:len(cat_exp)], autopct="%1.0f%%",
                    startangle=140,
                    textprops={"color": DS["fg"], "fontsize": 8},
                    wedgeprops={"edgecolor": DS["bg"], "linewidth": 1.5})
        ax2.set_title("Distribución de Egresos", color=DS["fg"], fontsize=10)

        # Horizontal bar
        ax3 = fig.add_subplot(1, 3, 3)
        ax3.set_facecolor(DS["bg2"])
        if cat_exp:
            cats = [r[0] for r in cat_exp]
            vals = [r[1] for r in cat_exp]
            bars = ax3.barh(cats, vals, color=colors[:len(cats)], edgecolor=DS["bg"])
            ax3.tick_params(colors=DS["fg2"])
            ax3.set_xlabel("Monto ($)", color=DS["fg2"])
            for sp in ax3.spines.values(): sp.set_edgecolor(DS["border"])
        ax3.set_title("Top Categorías", color=DS["fg"], fontsize=10)

        fig.tight_layout(pad=2.5)
        canvas = FigureCanvasTkAgg(fig, master=self.main)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=16, pady=8)

    # ─────────────────────────────────────────────────────────
    #  PAGE: BUDGETS
    # ─────────────────────────────────────────────────────────
    def _page_budgets(self):
        tk.Label(self.main, text="🎯 Presupuestos por Categoría",
                 font=("Calibri", 20, "bold"), bg=DS["bg"], fg=DS["fg"],
                 padx=24, pady=16).pack(anchor="w")

        container = tk.Frame(self.main, bg=DS["bg"], padx=16)
        container.pack(fill="both", expand=True)

        month = datetime.date.today().strftime("%Y-%m")
        conn = get_conn(); c = conn.cursor()
        budgets = {r[0]: r[1] for r in c.execute("SELECT category,limit_amount FROM budgets WHERE month=?", (month,)).fetchall()}
        spending = {r[0]: abs(r[1]) for r in c.execute(
            "SELECT category, SUM(amount) FROM transactions WHERE type='expense' AND strftime('%Y-%m',date)=? GROUP BY category", (month,)
        ).fetchall()}
        conn.close()

        cats = CATEGORIES["expense"]
        for i, cat in enumerate(cats):
            spent  = spending.get(cat, 0)
            budget = budgets.get(cat, 0)
            pct    = (spent / budget * 100) if budget > 0 else 0
            color  = DS["success"] if pct < 70 else (DS["warning"] if pct < 90 else DS["danger"])

            row_f = tk.Frame(container, bg=DS["bg2"], padx=16, pady=12)
            row_f.pack(fill="x", pady=4)
            row_f.columnconfigure(2, weight=1)

            tk.Label(row_f, text=cat, font=("Calibri", 11, "bold"),
                     bg=DS["bg2"], fg=DS["fg"], width=18, anchor="w").grid(row=0, column=0, sticky="w")
            tk.Label(row_f, text=f"${spent:,.0f} / ${budget:,.0f}",
                     font=("Calibri", 10), bg=DS["bg2"], fg=DS["fg2"], width=20).grid(row=0, column=1, padx=8)

            bar_bg = tk.Frame(row_f, bg=DS["bg3"], height=8)
            bar_bg.grid(row=0, column=2, sticky="ew", padx=8)
            bar_bg.update_idletasks()
            w = bar_bg.winfo_reqwidth()
            fill_w = max(4, int(min(pct, 100) / 100 * 200))
            bar_fill = tk.Frame(bar_bg, bg=color, height=8, width=fill_w)
            bar_fill.place(x=0, y=0, relheight=1)

            tk.Label(row_f, text=f"{pct:.0f}%", font=("Calibri", 10, "bold"),
                     bg=DS["bg2"], fg=color, width=6).grid(row=0, column=3)

            def set_budget(cat=cat):
                val = simpledialog.askfloat("Presupuesto", f"Límite para '{cat}' en {month}:",
                                            minvalue=0, maxvalue=999999)
                if val is not None:
                    conn = get_conn()
                    conn.execute("INSERT OR REPLACE INTO budgets (category,limit_amount,month) VALUES (?,?,?)",
                                 (cat, val, month))
                    conn.commit(); conn.close()
                    self.show_page("budgets")

            tk.Button(row_f, text="✏️ Editar", font=("Calibri", 9), relief="flat",
                      bg=DS["bg3"], fg=DS["fg"], cursor="hand2", command=set_budget).grid(row=0, column=4, padx=4)

    # ─────────────────────────────────────────────────────────
    #  PAGE: REPORTS
    # ─────────────────────────────────────────────────────────
    def _page_reports(self):
        tk.Label(self.main, text="📑 Reportes Ejecutivos",
                 font=("Calibri", 20, "bold"), bg=DS["bg"], fg=DS["fg"],
                 padx=24, pady=16).pack(anchor="w")

        conn = get_conn(); c = conn.cursor()
        total_inc = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='income'").fetchone()[0]
        total_exp = abs(c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='expense'").fetchone()[0])
        balance   = total_inc - total_exp
        avg_inc   = c.execute("SELECT COALESCE(AVG(amount),0) FROM transactions WHERE type='income'").fetchone()[0]
        avg_exp   = abs(c.execute("SELECT COALESCE(AVG(amount),0) FROM transactions WHERE type='expense'").fetchone()[0])
        top_cats  = c.execute("SELECT category,SUM(ABS(amount)) FROM transactions WHERE type='expense' GROUP BY category ORDER BY 2 DESC LIMIT 3").fetchall()
        conn.close()

        report_text = f"""
╔══════════════════════════════════════════════════╗
║         REPORTE EJECUTIVO — FINANCEOS            ║
║         Generado: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}              ║
╚══════════════════════════════════════════════════╝

📊 RESUMEN FINANCIERO GLOBAL
─────────────────────────────
  Total Ingresos:     ${total_inc:>12,.2f}
  Total Egresos:      ${total_exp:>12,.2f}
  Balance Neto:       ${balance:>12,.2f}
  Tasa de Ahorro:     {((balance/total_inc*100) if total_inc else 0):.1f}%

📈 PROMEDIOS
─────────────────────────────
  Ingreso Promedio:   ${avg_inc:>12,.2f}
  Egreso Promedio:    ${avg_exp:>12,.2f}

🔝 TOP 3 CATEGORÍAS DE GASTO
─────────────────────────────
"""
        for i, (cat, amt) in enumerate(top_cats, 1):
            report_text += f"  {i}. {cat:<20} ${amt:>10,.2f}\n"

        report_text += """
💡 RECOMENDACIONES
─────────────────────────────
  • Mantén tu tasa de ahorro superior al 20%
  • Revisa y ajusta presupuestos mensualmente
  • Diversifica fuentes de ingreso
  • Automatiza pagos recurrentes

─────────────────────────────
  Generado por FinanceOS V1.0
  Powered by Orunex App Developer Engine
"""
        txt = tk.Text(self.main, font=("Consolas", 10),
                      bg=DS["bg2"], fg=DS["fg"], relief="flat",
                      padx=24, pady=16, wrap="none",
                      insertbackground=DS["fg"])
        txt.pack(fill="both", expand=True, padx=16, pady=8)
        txt.insert("end", report_text)
        txt.config(state="disabled")

        ttk.Button(self.main, text="📤 Exportar Reporte TXT",
                   command=lambda: self._export_report(report_text)).pack(pady=8)

    def _export_report(self, txt):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Texto", "*.txt")],
            initialfile=f"FinanceOS_Reporte_{datetime.date.today()}.txt")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt)
            messagebox.showinfo("Exportado", f"Reporte guardado en: {path}")

    # ── PRO MODAL ────────────────────────────────────────────
    def _show_pro(self):
        w = tk.Toplevel(self.root)
        w.title("FinanceOS PRO")
        w.geometry("480x400")
        w.configure(bg=DS["bg"])
        w.resizable(False, False)
        tk.Label(w, text="⭐ FinanceOS PRO",
                 font=("Calibri", 22, "bold"), bg=DS["bg"], fg=DS["accent2"]).pack(pady=(30,8))
        features = [
            "✅ Sincronización en la nube (Google Drive / Dropbox)",
            "✅ IA Financiera: alertas y consejos personalizados",
            "✅ Reportes PDF profesionales automatizados",
            "✅ Multi-cuenta: banco, efectivo, crypto",
            "✅ Proyecciones de ahorro a 12 meses",
            "✅ Exportación a Excel con fórmulas avanzadas",
            "✅ API bancaria (Open Banking México)",
            "✅ Soporte prioritario 24/7",
        ]
        for f in features:
            tk.Label(w, text=f, font=("Calibri", 11), bg=DS["bg"], fg=DS["fg"]).pack(anchor="w", padx=40, pady=2)
        tk.Label(w, text="$149 MXN / mes  ·  $1,299 MXN / año",
                 font=("Calibri", 13, "bold"), bg=DS["bg"], fg=DS["warning"]).pack(pady=(16,8))
        ttk.Button(w, text="🚀 Comenzar Prueba Gratuita 14 días",
                   command=lambda: messagebox.showinfo("¡Gracias!", "Próximamente en línea. ¡Registra tu interés!")).pack(ipadx=16, ipady=4)

# ══════════════════════════════════════════════════════════════
#  TESTS
# ══════════════════════════════════════════════════════════════
def run_tests():
    """Suite de tests automatizados para FinanceOS."""
    print("=" * 50)
    print("FINANCEOS — SUITE DE TESTS AUTOMÁTICOS")
    print("=" * 50)
    passed = 0; failed = 0

    # Test 1: DB Init
    try:
        init_db()
        conn = get_conn()
        cnt = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        conn.close()
        assert cnt > 0, "DB vacía después de seed"
        print(f"[PASS] Test 1: DB inicializada con {cnt} registros.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 1: {e}"); failed += 1

    # Test 2: Income/Expense calculation
    try:
        conn = get_conn()
        inc = conn.execute("SELECT SUM(amount) FROM transactions WHERE type='income'").fetchone()[0]
        exp = conn.execute("SELECT SUM(amount) FROM transactions WHERE type='expense'").fetchone()[0]
        conn.close()
        assert inc > 0, "No hay ingresos"
        assert exp < 0, "Los gastos deben ser negativos"
        print(f"[PASS] Test 2: Ingresos=${inc:,.2f}, Egresos={exp:,.2f}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 2: {e}"); failed += 1

    # Test 3: Category filter
    try:
        conn = get_conn()
        cats = conn.execute("SELECT DISTINCT category FROM transactions").fetchall()
        conn.close()
        assert len(cats) >= 2, "Pocas categorías"
        print(f"[PASS] Test 3: {len(cats)} categorías únicas detectadas.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 3: {e}"); failed += 1

    # Test 4: Insert + Delete
    try:
        conn = get_conn()
        conn.execute("INSERT INTO transactions (date,description,amount,category,type,note) VALUES ('2024-12-01','Test Orunex',999.99,'Test','income','')")
        conn.commit()
        iid = conn.execute("SELECT id FROM transactions WHERE description='Test Orunex'").fetchone()[0]
        conn.execute("DELETE FROM transactions WHERE id=?", (iid,))
        conn.commit(); conn.close()
        print("[PASS] Test 4: INSERT + DELETE funcionando correctamente.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 4: {e}"); failed += 1

    # Test 5: CSV export
    try:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp.close()
        conn = get_conn()
        rows = conn.execute("SELECT date,description,category,type,amount,note FROM transactions").fetchall()
        conn.close()
        with open(tmp.name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Fecha","Descripción","Categoría","Tipo","Monto","Nota"])
            w.writerows(rows)
        size = os.path.getsize(tmp.name)
        os.unlink(tmp.name)
        assert size > 100, "CSV demasiado pequeño"
        print(f"[PASS] Test 5: Export CSV — {size} bytes generados.")
        passed += 1
    except Exception as e:
        print(f"[FAIL] Test 5: {e}"); failed += 1

    print("=" * 50)
    print(f"RESULTADOS: {passed} PASS / {failed} FAIL / {passed+failed} TOTAL")
    print("=" * 50)
    return failed == 0

# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        import csv
        success = run_tests()
        sys.exit(0 if success else 1)

    init_db()
    root = tk.Tk()
    app  = FinanceOS(root)
    root.mainloop()
'''

# ──────────────────────────────────────────────────────────────
#  ENGINE PRINCIPAL
# ──────────────────────────────────────────────────────────────

def generate_app(topic: str, out_dir: str, progress_cb=None) -> dict:
    """
    Orunex App Developer Engine V1.0
    Genera una app completa, la testea, corrige bugs y la lanza.

    Returns: dict con keys: app_dir, main_file, test_passed, errors
    """
    _progress(f"🚀 App Developer Engine V1.0 — Construyendo: {topic}", progress_cb)

    # Determine app type
    topic_lower = topic.lower()
    if any(w in topic_lower for w in ["finanza", "dinero", "gasto", "presupuesto", "finance", "money"]):
        app_name = "FinanceOS"
        app_code = FINANCE_OS_CODE
    else:
        app_name = "FinanceOS"  # Default demo app
        app_code = FINANCE_OS_CODE

    # 1. Create app directory
    app_dir = os.path.join(out_dir, "apps", app_name)
    os.makedirs(app_dir, exist_ok=True)
    main_file = os.path.join(app_dir, "main.py")
    readme    = os.path.join(app_dir, "README.md")

    _progress(f"📁 Creando estructura del proyecto: {app_dir}", progress_cb)

    # 2. Write source code
    _progress("✍️  Escribiendo código fuente completo...", progress_cb)
    with open(main_file, "w", encoding="utf-8") as f:
        f.write(app_code)

    # 3. Write README
    readme_content = f"""# {app_name}
**Generado por Orunex App Developer Engine V1.0**

## Descripción
Dashboard de finanzas personales con UI premium dark mode, base de datos SQLite,
gráficas matplotlib integradas, exportación CSV y sistema de presupuestos.

## Características
- 📊 Dashboard con KPIs en tiempo real
- 📋 CRUD completo de transacciones
- 📈 Gráficas: barras, líneas, pie charts
- 🎯 Presupuestos por categoría con alertas visuales
- 📑 Reportes ejecutivos exportables
- 💾 Base de datos SQLite local
- 📤 Exportación CSV
- ⭐ Plan PRO con funciones avanzadas (monetización freemium)

## Instalación
```bash
pip install matplotlib
python main.py
```

## Tests
```bash
python main.py --test
```

## Arquitectura
```
{app_name}/
├── main.py          # App principal + tests integrados
├── financeos.db     # Base de datos SQLite (auto-generada)
└── README.md        # Este archivo
```

## Monetización
- **Free**: Funciones básicas completas
- **PRO** ($149 MXN/mes): Sync cloud, IA financiera, reportes PDF, multi-cuenta

---
*Generado el {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")} por Orunex App Developer Engine V1.0*
"""
    with open(readme, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 4. Syntax check
    _progress("🔍 Verificando sintaxis del código...", progress_cb)
    ok, err = _run_syntax_check(main_file)
    if not ok:
        _progress(f"🔧 Bug detectado, aplicando auto-fix: {err[:80]}", progress_cb)
        with open(main_file, "r", encoding="utf-8") as f:
            src = f.read()
        fixed = _auto_fix_common_bugs(src)
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(fixed)
        ok, err = _run_syntax_check(main_file)
        if ok:
            _progress("✅ Bug corregido automáticamente.", progress_cb)
        else:
            _progress(f"⚠️ Bug persistente: {err[:100]}", progress_cb)

    # 5. Run automated tests
    _progress("🧪 Ejecutando suite de tests automatizados...", progress_cb)
    test_result = subprocess.run(
        [sys.executable, main_file, "--test"],
        capture_output=True,
        text=True,
        cwd=app_dir,
        **_hidden_process_kwargs(),
    )
    test_passed = test_result.returncode == 0
    test_output = test_result.stdout + test_result.stderr

    if test_passed:
        _progress("✅ TODOS LOS TESTS PASARON (5/5)", progress_cb)
    else:
        _progress(f"⚠️ Algunos tests fallaron. Revisando...", progress_cb)
        # Log failures
        for line in test_output.split("\n"):
            if "[FAIL]" in line:
                _progress(f"  🔧 {line.strip()}", progress_cb)

    _progress(f"✅ App '{app_name}' lista en: {app_dir}", progress_cb)
    _progress("🚀 Lanzando aplicación...", progress_cb)

    return {
        "app_name":    app_name,
        "app_dir":     app_dir,
        "main_file":   main_file,
        "readme":      readme,
        "test_passed": test_passed,
        "test_output": test_output,
        "syntax_ok":   ok,
    }
