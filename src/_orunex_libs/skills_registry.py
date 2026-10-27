# src/utils/skills_registry.py
"""Registro modular de conocimientos y habilidades para carga dinamica (JIT) en los agentes."""

SKILLS = {
    "finance": """### Finanzas y Trading
- Smart Money Concepts: Liquidity Grabs, Fair Value Gaps, Order Blocks institucionales
- Analisis tecnico: Fibonacci, Wyckoff (Acumulacion/Distribucion), RSI divergencias
- Gestion de Riesgo: Kelly Criterion, Position Sizing, Drawdown control
- Cripto & Forex: Tokenomics, On-chain data, DCA, tasas de interes
- Uso de APIS Financieras (Binance, Yahoo Finance)""",
    
    "business": """### Estrategia Empresarial
- Metodologias: Lean Startup, Scrum/Kanban, Design Thinking
- Modelos de negocio: Lean Canvas, SaaS, Freemium, B2B/B2C
- Metricas: CAC, LTV, Churn Rate, MRR/ARR, Burn Rate
- Gestion: OKRs, SWOT/DAFO, estrategias de Moat empresarial""",
    
    "science": """### Ciencias y Razonamiento
- Matematicas, fisica cuantica, filosofia analitica, logica formal
- Razonamiento desde primeros principios (First Principles)
- Metodo socratico y analisis de hipotesis cientificas""",
    
    "devops": """### Automatizacion y DevOps
- Scraping resiliente: BeautifulSoup, Selenium, evasion de bloqueos, Playwright
- Pipelines: LOOP/WATCH, Retry con Exponential Backoff, manejo de logs
- Scripts de Windows, manipulacion de archivos masivos, Regex avanzadas
- Macros de escritorio automaticas con vision artificial""",
    
    "web_dev": """### Arquitectura y Desarrollo Web (Full-Stack)
- Patrones: MVC, Microservicios, Clean Architecture, SOLID, DRY
- Frontend: HTML/CSS/JS, React, Vue, TailwindCSS, Framer Motion, Bootstrap
- Backend: Python (Flask/FastAPI), Node.js, REST API, GraphQL
- Bases de datos: SQLite, PostgreSQL, MongoDB, Redis
- Seguridad OWASP: Sanitizacion de inputs, XSS/CSRF, JWT, Bcrypt"""
}

def get_skill(name: str) -> str:
    """Retorna el contenido de la habilidad solicitada o un mensaje de error si no existe."""
    return SKILLS.get(name.lower().strip(), "[WARN] Skill no encontrada en el registro. Utiliza tus herramientas estandar.")
