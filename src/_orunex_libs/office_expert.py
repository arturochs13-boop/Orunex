"""Office Expert Studio for Orunex.

This module turns a natural-language request into a genuinely researched,
professionally designed Office deliverable:

* PowerPoint decks with topic-aware narratives, native charts, speaker notes,
  slide transitions and real entrance animations (OOXML ``p:timing``).
* Excel workbooks with a dashboard, formulas, conditional formatting, charts,
  a 30/60/90 plan and a research annex.
* Word executive reports with a cover, table of contents, KPI tables, charts,
  risk/roadmap tables, headers, footers and page numbers.

The studio works without a language model.  It combines the user's own data
(metrics, requested sections) with a bilingual domain knowledge base and, when
the network is available, a short web-research pass that is cited in the
deliverable.  Everything is deterministic and auditable: no invented numbers.
"""

from __future__ import annotations

import datetime as _dt
import math
import os
import queue
import re
import tempfile
import threading
from typing import Any, Callable, Optional, Sequence
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

_ES_WORDS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "que", "con", "para",
    "por", "sobre", "como", "más", "mas", "pero", "sin", "sus", "este", "esta",
    "crea", "crear", "genera", "presentacion", "presentación", "documento",
    "informe", "ventas", "clientes", "datos", "año", "años", "equipo", "plan",
}
_EN_WORDS = {
    "the", "a", "an", "of", "and", "to", "in", "on", "for", "with", "about",
    "create", "make", "generate", "presentation", "document", "report", "sales",
    "customers", "data", "year", "years", "team", "plan", "growth", "market",
}


def detect_language(text: str) -> str:
    """Return ``es`` or ``en`` using a small but reliable stop-word vote."""
    lowered = str(text or "").lower()
    es = sum(1 for word in re.findall(r"[a-záéíóúüñ]+", lowered) if word in _ES_WORDS)
    en = sum(1 for word in re.findall(r"[a-z]+", lowered) if word in _EN_WORDS)
    if en > es:
        return "en"
    return "es"


def _pick(value: Any, lang: str) -> Any:
    """Pick the ``es``/``en`` branch of a bilingual value."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("es") or value.get("en")
    return value


T: dict[str, dict[str, str]] = {
    "es": {
        "executive_report": "Informe ejecutivo",
        "prepared_by": "Preparado por Orunex",
        "confidential": "Documento confidencial",
        "agenda": "Contenido",
        "summary": "Resumen ejecutivo",
        "context": "Contexto y desafío",
        "findings": "Hallazgos del mercado",
        "trends": "Tendencias que importan",
        "kpi_panel": "Panel de métricas",
        "analysis": "Análisis y hallazgos",
        "plan": "Plan de acción",
        "framework": "Marco de trabajo",
        "risks": "Riesgos y mitigación",
        "roadmap": "Plan 30/60/90",
        "recommendations": "Decisiones recomendadas",
        "closing": "Gracias",
        "closing_sub": "Preguntas y siguientes pasos",
        "baseline": "Línea base",
        "reading": "Lectura",
        "implication": "Implicación",
        "next_step": "Siguiente paso",
        "source": "Fuente",
        "sources": "Fuentes y metodología",
        "no_metrics": "Sin métricas en la solicitud",
        "recommended_kpis": "KPIs recomendados",
        "metric": "Métrica",
        "value": "Valor",
        "unit": "Unidad",
        "weight": "% del total",
        "vs_avg": "vs promedio",
        "ranking": "Ranking",
        "comment": "Comentario",
        "total": "TOTAL",
        "average": "PROMEDIO",
        "data": "Datos",
        "dashboard": "Dashboard",
        "analysis_sheet": "Análisis",
        "plan_sheet": "Plan",
        "research_sheet": "Investigación",
        "status": "Estado",
        "owner": "Responsable",
        "horizon": "Horizonte",
        "action": "Acción",
        "pending": "Pendiente",
        "in_progress": "En curso",
        "done": "Completado",
        "blocked": "Bloqueado",
        "risk": "Riesgo",
        "impact": "Impacto",
        "mitigation": "Mitigación",
        "high": "Alto",
        "medium": "Medio",
        "low": "Bajo",
        "scenario": "Escenario",
        "base": "Base",
        "conservative": "Conservador (-10%)",
        "optimistic": "Optimista (+10%)",
        "methodology": "Metodología",
        "assumptions": "Supuestos",
        "version_control": "Control de versiones",
        "version": "Versión",
        "date": "Fecha",
        "author": "Autor",
        "change": "Cambio",
        "document": "Documento",
        "key_messages": "Mensajes clave",
        "decision": "Decisión",
        "expected_result": "Resultado esperado",
        "recommended": "Recomendado",
        "evidence": "Evidencia",
        "what_we_know": "Lo que sabemos",
        "what_it_means": "Lo que significa",
        "what_to_do": "Qué hacer ahora",
        "sources_note": "Fuentes consultadas",
        "internal_framework": "Marco interno Orunex",
        "no_external_sources": "No se consultaron fuentes externas en esta ejecución; el contenido se apoya en el marco interno de Orunex y en los datos de la solicitud.",
        "data_from_request": "Dato tomado de la solicitud",
        "needs_data": "A completar con datos reales",
        "sensitivity_note": "Sensibilidad mecánica de ±10% sobre la línea base. No es un pronóstico.",
        "research_query_note": "Investigación rápida de tendencias y contexto. Verifica las fuentes antes de una decisión crítica.",
        "confidential_note": "Uso interno. No distribuir sin autorización.",
        "page": "Página",
        "of": "de",
        "index": "Índice",
        "annex": "Anexo",
        "metrics_annex": "Anexo de métricas",
        "assumptions_text": "Las cifras provienen de la solicitud del usuario. Los marcos y tendencias son referencias de análisis, no datos de la empresa. Las fuentes externas se citan con su URL.",
    },
    "en": {
        "executive_report": "Executive report",
        "prepared_by": "Prepared by Orunex",
        "confidential": "Confidential document",
        "agenda": "Contents",
        "summary": "Executive summary",
        "context": "Context and challenge",
        "findings": "Market findings",
        "trends": "Trends that matter",
        "kpi_panel": "Metrics dashboard",
        "analysis": "Analysis and findings",
        "plan": "Action plan",
        "framework": "Working framework",
        "risks": "Risks and mitigation",
        "roadmap": "30/60/90 plan",
        "recommendations": "Recommended decisions",
        "closing": "Thank you",
        "closing_sub": "Questions and next steps",
        "baseline": "Baseline",
        "reading": "Reading",
        "implication": "Implication",
        "next_step": "Next step",
        "source": "Source",
        "sources": "Sources and methodology",
        "no_metrics": "No metrics in the request",
        "recommended_kpis": "Recommended KPIs",
        "metric": "Metric",
        "value": "Value",
        "unit": "Unit",
        "weight": "% of total",
        "vs_avg": "vs average",
        "ranking": "Ranking",
        "comment": "Comment",
        "total": "TOTAL",
        "average": "AVERAGE",
        "data": "Data",
        "dashboard": "Dashboard",
        "analysis_sheet": "Analysis",
        "plan_sheet": "Plan",
        "research_sheet": "Research",
        "status": "Status",
        "owner": "Owner",
        "horizon": "Horizon",
        "action": "Action",
        "pending": "Pending",
        "in_progress": "In progress",
        "done": "Completed",
        "blocked": "Blocked",
        "risk": "Risk",
        "impact": "Impact",
        "mitigation": "Mitigation",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
        "scenario": "Scenario",
        "base": "Base",
        "conservative": "Conservative (-10%)",
        "optimistic": "Optimistic (+10%)",
        "methodology": "Methodology",
        "assumptions": "Assumptions",
        "version_control": "Version control",
        "version": "Version",
        "date": "Date",
        "author": "Author",
        "change": "Change",
        "document": "Document",
        "key_messages": "Key messages",
        "decision": "Decision",
        "expected_result": "Expected result",
        "recommended": "Recommended",
        "evidence": "Evidence",
        "what_we_know": "What we know",
        "what_it_means": "What it means",
        "what_to_do": "What to do now",
        "sources_note": "Sources consulted",
        "internal_framework": "Orunex internal framework",
        "no_external_sources": "No external sources were consulted in this run; the content relies on Orunex's internal framework and the data in the request.",
        "data_from_request": "Data taken from the request",
        "needs_data": "To be completed with real data",
        "sensitivity_note": "Mechanical ±10% sensitivity on the baseline. This is not a forecast.",
        "research_query_note": "Quick scan of trends and context. Verify sources before a critical decision.",
        "confidential_note": "Internal use. Do not distribute without authorization.",
        "page": "Page",
        "of": "of",
        "index": "Contents",
        "annex": "Annex",
        "metrics_annex": "Metrics annex",
        "assumptions_text": "Figures come from the user's request. Frameworks and trends are analytical references, not company data. External sources are cited with their URL.",
    },
}


def tr(lang: str, key: str) -> str:
    return T.get(lang, T["es"]).get(key, key)


# ---------------------------------------------------------------------------
# Domain knowledge base
# ---------------------------------------------------------------------------

DOMAINS: list[dict[str, Any]] = [
    {
        "key": "sales",
        "label": {"es": "Ventas y crecimiento comercial", "en": "Sales and commercial growth"},
        "theme": "coral",
        "keywords": ["venta", "ventas", "comercial", "ingreso", "ingresos", "pipeline", "b2b", "ticket", "cartera", "clientes", "sales", "revenue", "quota", "deal"],
        "focus": {"es": "calidad del pipeline, ticket medio y conversión", "en": "pipeline quality, average deal size and conversion"},
        "context": {
            "es": [
                "El crecimiento comercial depende cada vez menos de sumar vendedores y más de priorizar cuentas, acortar el ciclo y elevar el ticket medio.",
                "Los compradores llegan con más información y esperan propuestas específicas; el equipo comercial debe aportar criterio, no solo catálogo.",
                "Una previsión fiable exige un pipeline segmentado por etapa, probabilidad y fecha real de cierre.",
            ],
            "en": [
                "Commercial growth depends less on adding salespeople and more on prioritizing accounts, shortening the cycle and raising average deal size.",
                "Buyers arrive better informed and expect specific proposals; sales teams must bring judgment, not just a catalog.",
                "A reliable forecast requires a pipeline segmented by stage, probability and realistic close date.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "MEDDIC", "desc": "Calificación de oportunidades complejas.", "steps": ["Metrics: impacto cuantificado", "Economic buyer: quién firma", "Decision criteria y proceso", "Identify pain y Champion"]},
                {"name": "Pipeline por etapas", "desc": "Control de avance y cobertura.", "steps": ["Definir etapas y criterios de salida", "Fijar SLA por etapa", "Medir conversión y ciclo", "Revisar cobertura 3x"]},
            ],
            "en": [
                {"name": "MEDDIC", "desc": "Qualification for complex opportunities.", "steps": ["Metrics: quantified impact", "Economic buyer: who signs", "Decision criteria and process", "Identify pain and Champion"]},
                {"name": "Stage-gated pipeline", "desc": "Progress and coverage control.", "steps": ["Define stages and exit criteria", "Set an SLA per stage", "Measure conversion and cycle", "Review 3x coverage"]},
            ],
        },
        "trends": {
            "es": [
                "Comités de compra más amplios: la decisión ya no depende de una sola persona.",
                "Ciclos más largos y más evidencia exigida antes de la primera reunión.",
                "La IA acelera la prospección, pero eleva la exigencia de relevancia y personalización.",
            ],
            "en": [
                "Wider buying committees: decisions no longer depend on one person.",
                "Longer cycles and more evidence required before the first meeting.",
                "AI accelerates prospecting but raises the bar for relevance and personalization.",
            ],
        },
        "kpis": {
            "es": ["Ventas netas / ingreso recurrente", "Ticket medio", "Conversión por etapa", "Ciclo de venta (días)", "Cobertura de pipeline", "Retención neta de ingresos"],
            "en": ["Net sales / recurring revenue", "Average deal size", "Stage conversion", "Sales cycle (days)", "Pipeline coverage", "Net revenue retention"],
        },
        "risks": {
            "es": [
                {"risk": "Concentración en pocas cuentas", "mitigation": "Diversificar por segmento y construir un plan específico para las 10 cuentas de mayor valor.", "level": "Alto"},
                {"risk": "Pipeline inflado o sin fecha real", "mitigation": "Aplicar criterios de calificación y auditar semanalmente las oportunidades estancadas.", "level": "Alto"},
                {"risk": "Descuentos no controlados", "mitigation": "Fijar una guía de precios y un flujo de aprobación para excepciones.", "level": "Medio"},
            ],
            "en": [
                {"risk": "Concentration in a few accounts", "mitigation": "Diversify by segment and build a specific plan for the top 10 accounts.", "level": "High"},
                {"risk": "Inflated pipeline without real dates", "mitigation": "Apply qualification criteria and audit stalled opportunities weekly.", "level": "High"},
                {"risk": "Uncontrolled discounting", "mitigation": "Set a pricing guide and an approval flow for exceptions.", "level": "Medium"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Segmentar la cartera por ICP y potencial.", "Auditar las 20 cuentas de mayor valor.", "Definir guion de descubrimiento y criterios de calificación."],
                "60": ["Rediseñar etapas y SLA del pipeline.", "Piloto de propuesta de valor por segmento.", "Tablero semanal de conversión y ciclo."],
                "90": ["Escalar el playbook ganador.", "Revisar pricing y política de descuentos.", "Plan de retención y expansión."],
            },
            "en": {
                "30": ["Segment the portfolio by ICP and potential.", "Audit the top 20 accounts.", "Define a discovery script and qualification criteria."],
                "60": ["Redesign pipeline stages and SLAs.", "Pilot a value proposition per segment.", "Weekly conversion and cycle dashboard."],
                "90": ["Scale the winning playbook.", "Review pricing and discount policy.", "Build a retention and expansion plan."],
            },
        },
    },
    {
        "key": "marketing",
        "label": {"es": "Marketing, marca y demanda", "en": "Marketing, brand and demand"},
        "theme": "violet",
        "keywords": ["marketing", "marca", "campaña", "campana", "publicidad", "contenido", "redes", "seo", "demanda", "conversion", "conversión", "brand", "campaign", "advertising", "content", "social"],
        "focus": {"es": "atribución, costo de adquisición y consistencia de marca", "en": "attribution, acquisition cost and brand consistency"},
        "context": {
            "es": [
                "La presión por demostrar retorno obliga a conectar cada canal con un resultado de negocio, no solo con impresiones.",
                "La marca y la demanda se refuerzan: la cobertura construye preferencia y la activación captura intención.",
                "La fragmentación de canales exige una arquitectura de medición común y una propuesta creativa consistente.",
            ],
            "en": [
                "Pressure to prove return forces every channel to connect to a business outcome, not just impressions.",
                "Brand and demand reinforce each other: reach builds preference and activation captures intent.",
                "Channel fragmentation requires a common measurement architecture and a consistent creative proposition.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "AIDA", "desc": "Diseño del recorrido de audiencia.", "steps": ["Atención: alcance relevante", "Interés: contenido y prueba", "Deseo: propuesta de valor", "Acción: oferta y fricción mínima"]},
                {"name": "4P", "desc": "Coherencia de la mezcla comercial.", "steps": ["Producto y promesa", "Precio y incentivo", "Plaza y canales", "Promoción y medición"]},
            ],
            "en": [
                {"name": "AIDA", "desc": "Audience journey design.", "steps": ["Attention: relevant reach", "Interest: content and proof", "Desire: value proposition", "Action: offer and low friction"]},
                {"name": "4P", "desc": "Coherence of the commercial mix.", "steps": ["Product and promise", "Price and incentive", "Place and channels", "Promotion and measurement"]},
            ],
        },
        "trends": {
            "es": [
                "El contenido útil y verificable gana terreno frente al mensaje puramente promocional.",
                "La medición se desplaza hacia modelos mix y experimentos incrementales.",
                "La IA multiplica la producción creativa; la diferenciación se mueve hacia el criterio y la marca.",
            ],
            "en": [
                "Useful, verifiable content is winning over purely promotional messaging.",
                "Measurement is shifting toward marketing-mix models and incremental experiments.",
                "AI multiplies creative output; differentiation moves toward judgment and brand.",
            ],
        },
        "kpis": {
            "es": ["CAC", "LTV / CAC", "Tasa de conversión", "Alcance cualificado", "ROAS", "Contribución por canal"],
            "en": ["CAC", "LTV / CAC", "Conversion rate", "Qualified reach", "ROAS", "Channel contribution"],
        },
        "risks": {
            "es": [
                {"risk": "Dispersión en demasiados canales", "mitigation": "Concentrar la inversión en 2-3 canales con evidencia y escalar solo con señal.", "level": "Alto"},
                {"risk": "Atribución incompleta", "mitigation": "Combinar last-click con experimentos de incremento y encuestas de origen.", "level": "Medio"},
                {"risk": "Creatividad sin oferta clara", "mitigation": "Alinear cada pieza con una audiencia, un mensaje y una acción medible.", "level": "Medio"},
            ],
            "en": [
                {"risk": "Spread across too many channels", "mitigation": "Concentrate spend on 2-3 channels with evidence and scale only on signal.", "level": "High"},
                {"risk": "Incomplete attribution", "mitigation": "Combine last-click with incrementality tests and source surveys.", "level": "Medium"},
                {"risk": "Creative without a clear offer", "mitigation": "Align every asset with an audience, a message and a measurable action.", "level": "Medium"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Auditar canales, costos y contribución.", "Definir audiencia y promesa por segmento.", "Instrumentar eventos clave."],
                "60": ["Piloto de 2 experimentos incrementales.", "Producir una campaña con prueba social.", "Revisar mezcla y creatividades."],
                "90": ["Escalar el canal ganador.", "Consolidar tablero de CAC y LTV.", "Plan de marca a 12 meses."],
            },
            "en": {
                "30": ["Audit channels, costs and contribution.", "Define audience and promise per segment.", "Instrument key events."],
                "60": ["Pilot two incrementality experiments.", "Produce a campaign with social proof.", "Review mix and creative."],
                "90": ["Scale the winning channel.", "Consolidate the CAC and LTV dashboard.", "Build a 12-month brand plan."],
            },
        },
    },
    {
        "key": "finance",
        "label": {"es": "Finanzas y rentabilidad", "en": "Finance and profitability"},
        "theme": "navy",
        "keywords": ["finanza", "finanzas", "presupuesto", "costo", "coste", "margen", "rentabilidad", "flujo", "caja", "inversion", "inversión", "ebitda", "finance", "budget", "cost", "margin", "cash", "profit"],
        "focus": {"es": "margen, flujo de caja y disciplina presupuestal", "en": "margin, cash flow and budget discipline"},
        "context": {
            "es": [
                "La rentabilidad se decide en la combinación de precio, mezcla y costo de servir, no solo en el volumen.",
                "El flujo de caja es el límite real del crecimiento; una venta sin cobranza no financia la operación.",
                "Los presupuestos más útiles separan lo comprometido, lo variable y lo discrecional.",
            ],
            "en": [
                "Profitability is decided by price, mix and cost-to-serve, not volume alone.",
                "Cash flow is the real limit on growth; a sale without collection does not fund operations.",
                "The most useful budgets separate committed, variable and discretionary spend.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "Unit economics", "desc": "Rentabilidad por unidad o cliente.", "steps": ["Ingreso por unidad", "Costo variable directo", "Margen de contribución", "Payback y LTV"]},
                {"name": "Presupuesto base cero", "desc": "Asignación desde necesidades, no desde inercia.", "steps": ["Paquetes de actividad", "Priorización por retorno", "Límite por área", "Revisión mensual"]},
            ],
            "en": [
                {"name": "Unit economics", "desc": "Profitability per unit or customer.", "steps": ["Revenue per unit", "Direct variable cost", "Contribution margin", "Payback and LTV"]},
                {"name": "Zero-based budgeting", "desc": "Allocate from needs, not inertia.", "steps": ["Activity packages", "Prioritize by return", "Cap per area", "Monthly review"]},
            ],
        },
        "trends": {
            "es": [
                "Mayor exigencia de visibilidad de caja en horizontes semanales.",
                "Costos de capital más altos: crecer sin rentabilidad es más caro.",
                "Automatización del cierre y de la conciliación para liberar análisis.",
            ],
            "en": [
                "Greater demand for weekly cash visibility.",
                "Higher cost of capital: growth without profitability is more expensive.",
                "Automation of close and reconciliation to free up analysis.",
            ],
        },
        "kpis": {
            "es": ["Margen bruto", "EBITDA", "Flujo de caja libre", "Desviación presupuestal", "Días de cobro", "Retorno sobre la inversión"],
            "en": ["Gross margin", "EBITDA", "Free cash flow", "Budget variance", "Days sales outstanding", "Return on investment"],
        },
        "risks": {
            "es": [
                {"risk": "Supuestos de ingresos optimistas", "mitigation": "Contrastar con un escenario conservador y definir disparadores de ajuste.", "level": "Alto"},
                {"risk": "Costos fijos difíciles de reducir", "mitigation": "Separar compromisos y revisar contratos antes de asumir nuevos fijos.", "level": "Medio"},
                {"risk": "Presión de caja por cobranza", "mitigation": "Priorizar cobranza, anticipos y condiciones comerciales claras.", "level": "Alto"},
            ],
            "en": [
                {"risk": "Optimistic revenue assumptions", "mitigation": "Test against a conservative scenario and define adjustment triggers.", "level": "High"},
                {"risk": "Fixed costs that are hard to cut", "mitigation": "Separate commitments and review contracts before adding fixed costs.", "level": "Medium"},
                {"risk": "Cash pressure from collections", "mitigation": "Prioritize collections, deposits and clear commercial terms.", "level": "High"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Construir la línea base de ingresos, costos y caja.", "Identificar las 5 fugas de margen.", "Definir escenario conservador."],
                "60": ["Renegociar 3 contratos relevantes.", "Instalar revisión semanal de caja.", "Piloto de pricing."],
                "90": ["Consolidar tablero de rentabilidad.", "Plan de reducción de costo de servir.", "Presupuesto rodante a 12 meses."],
            },
            "en": {
                "30": ["Build the revenue, cost and cash baseline.", "Identify the top five margin leaks.", "Define a conservative scenario."],
                "60": ["Renegotiate three relevant contracts.", "Install a weekly cash review.", "Run a pricing pilot."],
                "90": ["Consolidate the profitability dashboard.", "Plan to reduce cost-to-serve.", "Build a rolling 12-month budget."],
            },
        },
    },
    {
        "key": "product_tech",
        "label": {"es": "Producto, tecnología e IA", "en": "Product, technology and AI"},
        "theme": "cyan",
        "keywords": ["producto", "tecnologia", "tecnología", "software", "ia", "inteligencia artificial", "digital", "app", "plataforma", "datos", "automatizacion", "automatización", "product", "technology", "ai", "digital", "platform", "data", "automation"],
        "focus": {"es": "adopción real, time-to-value y deuda técnica", "en": "real adoption, time-to-value and technical debt"},
        "context": {
            "es": [
                "El valor de un producto se demuestra en adopción sostenida, no en funcionalidades entregadas.",
                "La IA amplía el espacio de soluciones, pero también los riesgos de calidad, privacidad y confianza.",
                "La deuda técnica y la fragmentación de datos limitan la velocidad más que la capacidad del equipo.",
            ],
            "en": [
                "Product value is proven by sustained adoption, not features shipped.",
                "AI expands the solution space but also quality, privacy and trust risks.",
                "Technical debt and data fragmentation limit speed more than team capacity.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "RICE", "desc": "Priorización de iniciativas.", "steps": ["Reach: usuarios afectados", "Impact: efecto esperado", "Confidence: evidencia", "Effort: costo de ejecución"]},
                {"name": "North Star", "desc": "Métrica que captura valor real.", "steps": ["Definir la métrica", "Descomponer en palancas", "Instrumentar el dato", "Revisar semanalmente"]},
            ],
            "en": [
                {"name": "RICE", "desc": "Initiative prioritization.", "steps": ["Reach: users affected", "Impact: expected effect", "Confidence: evidence", "Effort: execution cost"]},
                {"name": "North Star", "desc": "A metric that captures real value.", "steps": ["Define the metric", "Break it into levers", "Instrument the data", "Review weekly"]},
            ],
        },
        "trends": {
            "es": [
                "La IA generativa pasa de piloto a flujo de trabajo con control humano.",
                "La privacidad y el gobierno del dato se vuelven requisitos de producto.",
                "Los equipos pequeños con buena instrumentación compiten mejor que los grandes sin foco.",
            ],
            "en": [
                "Generative AI is moving from pilot to workflow with human control.",
                "Privacy and data governance are becoming product requirements.",
                "Small, well-instrumented teams compete better than large unfocused ones.",
            ],
        },
        "kpis": {
            "es": ["Activación", "Retención D30", "Adopción de la función clave", "Time-to-value", "NPS", "Costo por transacción"],
            "en": ["Activation", "D30 retention", "Key-feature adoption", "Time-to-value", "NPS", "Cost per transaction"],
        },
        "risks": {
            "es": [
                {"risk": "Alcance difuso y muchas prioridades", "mitigation": "Elegir una métrica norte y limitar el trabajo en curso.", "level": "Alto"},
                {"risk": "Baja adopción por fricción", "mitigation": "Observar el recorrido real y eliminar pasos antes de añadir funciones.", "level": "Alto"},
                {"risk": "Deuda técnica y dependencia de proveedores", "mitigation": "Reservar capacidad por sprint y documentar arquitectura y salidas.", "level": "Medio"},
            ],
            "en": [
                {"risk": "Diffuse scope and too many priorities", "mitigation": "Choose one north-star metric and limit work in progress.", "level": "High"},
                {"risk": "Low adoption due to friction", "mitigation": "Observe the real journey and remove steps before adding features.", "level": "High"},
                {"risk": "Technical debt and vendor lock-in", "mitigation": "Reserve sprint capacity and document architecture and exit paths.", "level": "Medium"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Instrumentar el recorrido clave.", "Entrevistar 10 usuarios.", "Definir métrica norte y línea base."],
                "60": ["Lanzar un piloto acotado.", "Reducir fricción en el flujo principal.", "Revisar arquitectura y riesgos."],
                "90": ["Escalar lo que muestre adopción.", "Plan de deuda técnica.", "Gobierno de datos y IA."],
            },
            "en": {
                "30": ["Instrument the key journey.", "Interview 10 users.", "Define the north-star metric and baseline."],
                "60": ["Launch a scoped pilot.", "Reduce friction in the main flow.", "Review architecture and risks."],
                "90": ["Scale what shows adoption.", "Technical-debt plan.", "Data and AI governance."],
            },
        },
    },
    {
        "key": "people",
        "label": {"es": "Talento, cultura y organización", "en": "People, culture and organization"},
        "theme": "light",
        "keywords": ["rrhh", "talento", "empleado", "empleados", "cultura", "capacitacion", "capacitación", "clima", "equipo", "liderazgo", "people", "talent", "employee", "culture", "training", "team", "leadership"],
        "focus": {"es": "claridad de roles, capacidades críticas y retención", "en": "role clarity, critical capabilities and retention"},
        "context": {
            "es": [
                "La estrategia avanza a la velocidad de las capacidades del equipo y de la claridad de sus decisiones.",
                "La rotación costosa no siempre es la visible: la dependencia de personas clave es un riesgo silencioso.",
                "La cultura se gestiona con comportamientos observables, no solo con declaraciones de valores.",
            ],
            "en": [
                "Strategy moves at the speed of team capabilities and decision clarity.",
                "Costly turnover is not always visible: key-person dependency is a silent risk.",
                "Culture is managed through observable behaviors, not value statements alone.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "9-box", "desc": "Desempeño y potencial.", "steps": ["Definir desempeño esperado", "Evaluar potencial", "Plan por cuadrante", "Revisión semestral"]},
                {"name": "OKR", "desc": "Alineación de equipos.", "steps": ["Objetivo inspirador", "3 resultados medibles", "Dueño por resultado", "Revisión quincenal"]},
            ],
            "en": [
                {"name": "9-box", "desc": "Performance and potential.", "steps": ["Define expected performance", "Assess potential", "Plan by quadrant", "Review twice a year"]},
                {"name": "OKR", "desc": "Team alignment.", "steps": ["Inspiring objective", "3 measurable results", "Owner per result", "Biweekly review"]},
            ],
        },
        "trends": {
            "es": [
                "Modelos híbridos que exigen acuerdos explícitos de colaboración.",
                "Más peso a habilidades y evidencia que a credenciales.",
                "Bienestar y carga de trabajo como factores de retención.",
            ],
            "en": [
                "Hybrid models that require explicit collaboration agreements.",
                "More weight on skills and evidence than on credentials.",
                "Well-being and workload as retention factors.",
            ],
        },
        "kpis": {
            "es": ["Rotación voluntaria", "eNPS", "Tiempo de cobertura de vacantes", "Productividad por equipo", "Horas de formación", "Ausentismo"],
            "en": ["Voluntary turnover", "eNPS", "Time to fill", "Productivity per team", "Training hours", "Absenteeism"],
        },
        "risks": {
            "es": [
                {"risk": "Dependencia de personas clave", "mitigation": "Documentar procesos críticos y crear planes de sucesión.", "level": "Alto"},
                {"risk": "Roles y expectativas difusos", "mitigation": "Actualizar descripciones, decisiones y criterios de éxito.", "level": "Medio"},
                {"risk": "Sobrecarga sostenida", "mitigation": "Priorizar cartera, medir carga y proteger tiempo de foco.", "level": "Alto"},
            ],
            "en": [
                {"risk": "Key-person dependency", "mitigation": "Document critical processes and create succession plans.", "level": "High"},
                {"risk": "Unclear roles and expectations", "mitigation": "Update role descriptions, decision rights and success criteria.", "level": "Medium"},
                {"risk": "Sustained overload", "mitigation": "Prioritize the portfolio, measure workload and protect focus time.", "level": "High"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Mapear roles y capacidades críticas.", "Medir carga y clima con una encuesta corta.", "Identificar dependencias de personas clave."],
                "60": ["Rediseñar 2 procesos de talento.", "Plan de desarrollo para posiciones críticas.", "Acuerdos de trabajo híbrido."],
                "90": ["Revisar estructura y decisiones.", "Consolidar tablero de talento.", "Plan de sucesión a 12 meses."],
            },
            "en": {
                "30": ["Map roles and critical capabilities.", "Measure workload and climate with a short survey.", "Identify key-person dependencies."],
                "60": ["Redesign two talent processes.", "Development plan for critical roles.", "Hybrid working agreements."],
                "90": ["Review structure and decision rights.", "Consolidate the talent dashboard.", "12-month succession plan."],
            },
        },
    },
    {
        "key": "operations",
        "label": {"es": "Operaciones, procesos y cadena de suministro", "en": "Operations, processes and supply chain"},
        "theme": "emerald",
        "keywords": ["operacion", "operación", "operaciones", "logistica", "logística", "cadena", "suministro", "proceso", "calidad", "manufactura", "inventario", "operations", "logistics", "supply", "process", "quality", "manufacturing", "inventory"],
        "focus": {"es": "flujo, calidad y resiliencia de la cadena", "en": "flow, quality and supply-chain resilience"},
        "context": {
            "es": [
                "La eficiencia se decide en los cuellos de botella y en la variabilidad, no solo en el costo unitario.",
                "La resiliencia exige visibilidad de proveedores, inventario y capacidad ante interrupciones.",
                "Cada proceso crítico necesita un dueño, una métrica y una rutina de revisión.",
            ],
            "en": [
                "Efficiency is decided by bottlenecks and variability, not unit cost alone.",
                "Resilience requires visibility into suppliers, inventory and capacity under disruption.",
                "Every critical process needs an owner, a metric and a review routine.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "Lean / SIPOC", "desc": "Visión de extremo a extremo.", "steps": ["Proveedor y entrada", "Proceso y responsable", "Salida y cliente", "Métrica y desperdicio"]},
                {"name": "Teoría de restricciones", "desc": "Mejorar el cuello de botella.", "steps": ["Identificar la restricción", "Explotarla", "Subordinarla", "Elevar capacidad"]},
            ],
            "en": [
                {"name": "Lean / SIPOC", "desc": "End-to-end view.", "steps": ["Supplier and input", "Process and owner", "Output and customer", "Metric and waste"]},
                {"name": "Theory of constraints", "desc": "Improve the bottleneck.", "steps": ["Identify the constraint", "Exploit it", "Subordinate", "Elevate capacity"]},
            ],
        },
        "trends": {
            "es": [
                "Mayor foco en resiliencia y proveedores alternativos.",
                "Automatización de la planificación y visibilidad en tiempo real.",
                "Trazabilidad y sostenibilidad como requisitos de cliente.",
            ],
            "en": [
                "Greater focus on resilience and alternative suppliers.",
                "Automation of planning and real-time visibility.",
                "Traceability and sustainability as customer requirements.",
            ],
        },
        "kpis": {
            "es": ["OTIF", "Lead time", "Costo por unidad", "Rotación de inventario", "Tasa de defectos", "Utilización de capacidad"],
            "en": ["OTIF", "Lead time", "Cost per unit", "Inventory turns", "Defect rate", "Capacity utilization"],
        },
        "risks": {
            "es": [
                {"risk": "Proveedor único en un insumo crítico", "mitigation": "Calificar una alternativa y mantener inventario de seguridad acotado.", "level": "Alto"},
                {"risk": "Cuello de botella no medido", "mitigation": "Mapear el flujo y medir cola, tiempo y capacidad por etapa.", "level": "Alto"},
                {"risk": "Variabilidad que rompe promesas", "mitigation": "Reducir variación y comunicar capacidad real a ventas.", "level": "Medio"},
            ],
            "en": [
                {"risk": "Single supplier for a critical input", "mitigation": "Qualify an alternative and hold a bounded safety stock.", "level": "High"},
                {"risk": "Unmeasured bottleneck", "mitigation": "Map the flow and measure queue, time and capacity per stage.", "level": "High"},
                {"risk": "Variability that breaks promises", "mitigation": "Reduce variation and communicate real capacity to sales.", "level": "Medium"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Mapear el flujo crítico y sus tiempos.", "Identificar el cuello de botella.", "Definir OTIF y línea base."],
                "60": ["Piloto de reducción de variabilidad.", "Plan de proveedores alternativos.", "Tablero de capacidad."],
                "90": ["Estandarizar el nuevo flujo.", "Revisar inventario y costo total.", "Plan de resiliencia a 12 meses."],
            },
            "en": {
                "30": ["Map the critical flow and cycle times.", "Identify the bottleneck.", "Define OTIF and baseline."],
                "60": ["Variability-reduction pilot.", "Alternative-supplier plan.", "Capacity dashboard."],
                "90": ["Standardize the new flow.", "Review inventory and total cost.", "12-month resilience plan."],
            },
        },
    },
    {
        "key": "sustainability",
        "label": {"es": "Sostenibilidad y ESG", "en": "Sustainability and ESG"},
        "theme": "emerald",
        "keywords": ["sostenibilidad", "esg", "ambiental", "ambiente", "energia", "energía", "carbono", "emisiones", "social", "reciclaje", "sustainability", "environment", "energy", "carbon", "emissions", "social", "recycling"],
        "focus": {"es": "materialidad, medición verificable y transición", "en": "materiality, verifiable measurement and transition"},
        "context": {
            "es": [
                "La sostenibilidad se vuelve gestión cuando se traduce en metas, datos y decisiones de inversión.",
                "El riesgo reputacional es real, pero el operativo suele ser mayor: energía, agua, residuos y cadena de suministro.",
                "La doble materialidad conecta el impacto del negocio en el entorno con el impacto del entorno en el negocio.",
            ],
            "en": [
                "Sustainability becomes management when translated into targets, data and investment decisions.",
                "Reputational risk is real, but operational risk is often larger: energy, water, waste and supply chain.",
                "Double materiality connects the business impact on the environment with the environment's impact on the business.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "Doble materialidad", "desc": "Priorización de temas ESG.", "steps": ["Impacto en el negocio", "Impacto en el entorno", "Consulta con grupos de interés", "Matriz de prioridades"]},
                {"name": "GHG Protocol", "desc": "Medición de emisiones.", "steps": ["Alcance 1: directas", "Alcance 2: energía", "Alcance 3: cadena", "Plan de reducción"]},
            ],
            "en": [
                {"name": "Double materiality", "desc": "ESG topic prioritization.", "steps": ["Impact on the business", "Impact on the environment", "Stakeholder consultation", "Priority matrix"]},
                {"name": "GHG Protocol", "desc": "Emissions measurement.", "steps": ["Scope 1: direct", "Scope 2: energy", "Scope 3: value chain", "Reduction plan"]},
            ],
        },
        "trends": {
            "es": [
                "Reportes más exigentes y verificación de datos.",
                "Energía renovable y eficiencia como palancas de costo.",
                "Trazabilidad de la cadena y criterios ESG en compras.",
            ],
            "en": [
                "Stricter reporting and data verification.",
                "Renewable energy and efficiency as cost levers.",
                "Supply-chain traceability and ESG criteria in procurement.",
            ],
        },
        "kpis": {
            "es": ["tCO2e evitadas", "Intensidad energética", "% de energía renovable", "Residuos valorizados", "Diversidad en liderazgo", "Horas de formación social"],
            "en": ["tCO2e avoided", "Energy intensity", "% renewable energy", "Waste recovered", "Leadership diversity", "Social training hours"],
        },
        "risks": {
            "es": [
                {"risk": "Greenwashing por datos incompletos", "mitigation": "Publicar solo indicadores verificables y explicar la metodología.", "level": "Alto"},
                {"risk": "Costo de transición sin retorno claro", "mitigation": "Priorizar medidas con ahorro operativo y financiamiento por fases.", "level": "Medio"},
                {"risk": "Riesgo regulatorio", "mitigation": "Mapear obligaciones y anticipar reportes con un calendario.", "level": "Alto"},
            ],
            "en": [
                {"risk": "Greenwashing from incomplete data", "mitigation": "Publish only verifiable indicators and explain the methodology.", "level": "High"},
                {"risk": "Transition cost without clear return", "mitigation": "Prioritize measures with operating savings and phase financing.", "level": "Medium"},
                {"risk": "Regulatory risk", "mitigation": "Map obligations and anticipate reporting with a calendar.", "level": "High"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Hacer la matriz de materialidad.", "Medir energía, agua y residuos.", "Mapear obligaciones regulatorias."],
                "60": ["Piloto de eficiencia energética.", "Criterios ESG en 3 compras clave.", "Borrador de reporte."],
                "90": ["Fijar metas a 12 meses.", "Verificación externa del dato clave.", "Plan de transición y financiamiento."],
            },
            "en": {
                "30": ["Build the materiality matrix.", "Measure energy, water and waste.", "Map regulatory obligations."],
                "60": ["Energy-efficiency pilot.", "ESG criteria in three key purchases.", "Draft report."],
                "90": ["Set 12-month targets.", "External verification of key data.", "Transition and financing plan."],
            },
        },
    },
    {
        "key": "strategy",
        "label": {"es": "Estrategia y transformación", "en": "Strategy and transformation"},
        "theme": "navy",
        "keywords": ["estrategia", "plan", "crecimiento", "transformacion", "transformación", "negocio", "mercado", "expansion", "expansión", "competencia", "strategy", "growth", "transformation", "business", "market", "expansion", "competition"],
        "focus": {"es": "elecciones claras, trade-offs y ejecución", "en": "clear choices, trade-offs and execution"},
        "context": {
            "es": [
                "La estrategia es un conjunto de elecciones: dónde competir, cómo ganar y qué dejar de hacer.",
                "La mayoría de los planes fallan en la ejecución por demasiadas iniciativas y pocos dueños.",
                "El contexto cambia más rápido que los ciclos presupuestales; el plan debe tener disparadores de revisión.",
            ],
            "en": [
                "Strategy is a set of choices: where to compete, how to win and what to stop doing.",
                "Most plans fail in execution because of too many initiatives and too few owners.",
                "Context changes faster than budget cycles; the plan needs review triggers.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "Porter", "desc": "Posicionamiento competitivo.", "steps": ["Cinco fuerzas", "Ventaja defendible", "Trade-offs", "Ajuste de actividades"]},
                {"name": "Tres horizontes", "desc": "Cartera de crecimiento.", "steps": ["H1: sostener el negocio", "H2: construir lo nuevo", "H3: opciones futuras", "Presupuesto por horizonte"]},
            ],
            "en": [
                {"name": "Porter", "desc": "Competitive positioning.", "steps": ["Five forces", "Defensible advantage", "Trade-offs", "Activity fit"]},
                {"name": "Three horizons", "desc": "Growth portfolio.", "steps": ["H1: sustain the core", "H2: build the new", "H3: future options", "Budget by horizon"]},
            ],
        },
        "trends": {
            "es": [
                "Ciclos de planificación más cortos y revisión por escenarios.",
                "Competencia por talento y capacidad, no solo por capital.",
                "La IA cambia costos y modelos de negocio en paralelo.",
            ],
            "en": [
                "Shorter planning cycles and scenario-based reviews.",
                "Competition for talent and capacity, not just capital.",
                "AI changes costs and business models at the same time.",
            ],
        },
        "kpis": {
            "es": ["Crecimiento de ingresos", "Participación de mercado", "Margen operativo", "NPS", "Velocidad de ejecución", "ROI de iniciativas"],
            "en": ["Revenue growth", "Market share", "Operating margin", "NPS", "Execution velocity", "Initiative ROI"],
        },
        "risks": {
            "es": [
                {"risk": "Iniciativas dispersas sin foco", "mitigation": "Limitar la cartera a 3 apuestas y decir explícitamente qué se detiene.", "level": "Alto"},
                {"risk": "Falta de dueño y gobernanza", "mitigation": "Asignar un dueño único por apuesta y una cadencia de revisión.", "level": "Alto"},
                {"risk": "Supuestos de mercado desactualizados", "mitigation": "Definir señales de cambio y revisar el plan cada trimestre.", "level": "Medio"},
            ],
            "en": [
                {"risk": "Scattered initiatives without focus", "mitigation": "Limit the portfolio to three bets and state what stops.", "level": "High"},
                {"risk": "Lack of ownership and governance", "mitigation": "Assign one owner per bet and a review cadence.", "level": "High"},
                {"risk": "Outdated market assumptions", "mitigation": "Define change signals and review the plan quarterly.", "level": "Medium"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Definir 3 apuestas y sus trade-offs.", "Auditar la cartera de iniciativas.", "Asignar dueño y métrica a cada apuesta."],
                "60": ["Piloto de la apuesta principal.", "Reasignar recursos desde lo que no funciona.", "Tablero de ejecución."],
                "90": ["Revisar resultados y escalar.", "Actualizar escenarios.", "Plan anual rodante."],
            },
            "en": {
                "30": ["Define three bets and their trade-offs.", "Audit the initiative portfolio.", "Assign an owner and metric to each bet."],
                "60": ["Pilot the main bet.", "Reallocate resources from what is not working.", "Execution dashboard."],
                "90": ["Review results and scale.", "Update scenarios.", "Rolling annual plan."],
            },
        },
    },
    {
        "key": "general",
        "label": {"es": "Gestión y resultados", "en": "Management and results"},
        "theme": "navy",
        "keywords": [],
        "focus": {"es": "objetivos claros, evidencia y ejecución", "en": "clear objectives, evidence and execution"},
        "context": {
            "es": [
                "Un entregable útil no acumula información: ordena decisiones y hace visible el siguiente paso.",
                "La claridad sobre el objetivo, el público y el criterio de éxito evita trabajo que no se puede usar.",
                "Los datos deben separarse de las interpretaciones y los supuestos para poder revisar el avance.",
            ],
            "en": [
                "A useful deliverable does not accumulate information: it organizes decisions and makes the next step visible.",
                "Clarity on the objective, audience and success criteria prevents unusable work.",
                "Data must be separated from interpretations and assumptions so progress can be reviewed.",
            ],
        },
        "frameworks": {
            "es": [
                {"name": "PDCA", "desc": "Mejora continua.", "steps": ["Planificar con hipótesis", "Ejecutar un piloto", "Verificar con datos", "Ajustar y estandarizar"]},
                {"name": "OKR", "desc": "Alineación y foco.", "steps": ["Objetivo cualitativo", "Resultados medibles", "Dueño", "Revisión"]},
            ],
            "en": [
                {"name": "PDCA", "desc": "Continuous improvement.", "steps": ["Plan with a hypothesis", "Run a pilot", "Verify with data", "Adjust and standardize"]},
                {"name": "OKR", "desc": "Alignment and focus.", "steps": ["Qualitative objective", "Measurable results", "Owner", "Review"]},
            ],
        },
        "trends": {
            "es": [
                "Menos reportes y más decisiones basadas en pocos indicadores.",
                "Automatización de tareas repetitivas para liberar criterio.",
                "Equipos pequeños con ciclos cortos de aprendizaje.",
            ],
            "en": [
                "Fewer reports and more decisions based on a few indicators.",
                "Automation of repetitive tasks to free up judgment.",
                "Small teams with short learning cycles.",
            ],
        },
        "kpis": {
            "es": ["Avance del objetivo", "Costo", "Tiempo", "Calidad", "Satisfacción", "Retorno"],
            "en": ["Objective progress", "Cost", "Time", "Quality", "Satisfaction", "Return"],
        },
        "risks": {
            "es": [
                {"risk": "Alcance difuso", "mitigation": "Definir qué entra y qué no entra en la primera versión.", "level": "Alto"},
                {"risk": "Datos insuficientes", "mitigation": "Marcar vacíos y validar con una fuente primaria antes de decidir.", "level": "Medio"},
                {"risk": "Falta de gobernanza", "mitigation": "Asignar dueño, fecha y criterio de aceptación.", "level": "Medio"},
            ],
            "en": [
                {"risk": "Diffuse scope", "mitigation": "Define what is in and out of the first version.", "level": "High"},
                {"risk": "Insufficient data", "mitigation": "Flag gaps and validate with a primary source before deciding.", "level": "Medium"},
                {"risk": "Lack of governance", "mitigation": "Assign an owner, date and acceptance criterion.", "level": "Medium"},
            ],
        },
        "actions": {
            "es": {
                "30": ["Confirmar objetivo, público y criterio de éxito.", "Reunir datos y fuentes.", "Definir la primera versión."],
                "60": ["Validar con usuarios o expertos.", "Ajustar el alcance.", "Medir el resultado."],
                "90": ["Estandarizar lo que funciona.", "Documentar aprendizajes.", "Plan de siguiente ciclo."],
            },
            "en": {
                "30": ["Confirm objective, audience and success criteria.", "Gather data and sources.", "Define the first version."],
                "60": ["Validate with users or experts.", "Adjust scope.", "Measure the result."],
                "90": ["Standardize what works.", "Document learnings.", "Next-cycle plan."],
            },
        },
    },
]


def detect_domain(text: str, title: str) -> dict[str, Any]:
    lowered = f" {str(text or '').lower()} {str(title or '').lower()} "
    best = DOMAINS[-1]
    best_score = 0
    for pack in DOMAINS[:-1]:
        score = 0
        for word in pack.get("keywords", []):
            if f" {word} " in lowered or re.search(rf"(?<!\w){re.escape(word)}(?!\w)", lowered):
                score += 2 if len(word) > 5 else 1
        if score > best_score:
            best, best_score = pack, score
    return best


def domain_label(pack: dict[str, Any], lang: str) -> str:
    return _pick(pack.get("label"), lang)


# ---------------------------------------------------------------------------
# Quick, cited web research
# ---------------------------------------------------------------------------

_RESEARCH_CACHE: dict[str, list[dict[str, str]]] = {}
_RESEARCH_LOCK = threading.Lock()


def _clean_snippet(value: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^[A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}\s*[·\-–]\s*", "", text)
    text = re.sub(r"^(Read more|Leer más|Ver más)\s*[·\-–]?\s*", "", text, flags=re.I)
    text = re.sub(r"https?://\S+", "", text).strip()
    if len(text) > limit:
        cut = text[:limit]
        stop = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(", "))
        text = (cut[:stop] if stop > limit * 0.55 else cut).rstrip(" ,;.") + "..."
    return text


def _short_title(value: str, limit: int = 82) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _relevance(result: dict[str, str], words: set[str]) -> int:
    haystack = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    return sum(1 for word in words if len(word) > 3 and word in haystack)


def _research_worker(query: str, max_results: int, output: "queue.Queue[list[dict[str, str]]]") -> None:
    try:
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore

        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore")
            raw = list(DDGS().text(query, max_results=max_results))
        results: list[dict[str, str]] = []
        for item in raw:
            title = _short_title(item.get("title") or "")
            snippet = _clean_snippet(item.get("body") or "")
            href = str(item.get("href") or "").strip()
            if not title or not snippet or not href.startswith("http"):
                continue
            if "youtube.com" in href or "youtu.be" in href:
                continue
            source = urlparse(href).netloc.replace("www.", "")
            results.append({"title": title, "snippet": snippet, "url": href, "source": source})
        output.put(results)
    except Exception:
        output.put([])


def research_topic(
    title: str,
    pack: dict[str, Any],
    lang: str,
    budget: float = 9.0,
    max_results: int = 6,
) -> list[dict[str, str]]:
    """Run a short, bounded web scan and return cited snippets.

    The scan is deliberately capped so a slow network never blocks the whole
    artifact.  Results are filtered for relevance and deduplicated by source.
    """
    label = domain_label(pack, lang)
    if lang == "en":
        query = f"{title} {label} trends 2026 key data"
    else:
        query = f"{title} {label} tendencias 2026 datos clave"
    query = re.sub(r"\s+", " ", query).strip()

    with _RESEARCH_LOCK:
        cached = _RESEARCH_CACHE.get(query)
    if cached is not None:
        return cached

    box: "queue.Queue[list[dict[str, str]]]" = queue.Queue()
    thread = threading.Thread(target=_research_worker, args=(query, max_results, box), daemon=True)
    thread.start()
    try:
        raw = box.get(timeout=budget)
    except queue.Empty:
        raw = []

    words = {
        word for word in re.findall(r"[a-záéíóúüñ]{4,}", f"{title} {label}".lower())
        if word not in _ES_WORDS and word not in _EN_WORDS
    }
    scored = sorted(raw, key=lambda item: _relevance(item, words), reverse=True)
    relevant = [item for item in scored if _relevance(item, words) > 0]
    selected = relevant[:4] if relevant else scored[:3]

    seen_sources: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in selected:
        key = item["source"].lower()
        if key in seen_sources:
            continue
        seen_sources.add(key)
        unique.append(item)
        if len(unique) >= 3:
            break

    with _RESEARCH_LOCK:
        _RESEARCH_CACHE[query] = unique
    return unique


# ---------------------------------------------------------------------------
# Topic-aware narrative
# ---------------------------------------------------------------------------

_TOPIC_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    ("summary", ("resumen", "summary", "executive summary", "síntesis", "sintesis")),
    ("context", ("contexto", "context", "situación", "situacion", "antecedentes", "desafío", "desafio")),
    ("objectives", ("objetivo", "objetivos", "goals", "objectives", "okr", "metas")),
    ("conversion", ("conversion", "conversión", "tasa de conversion", "conversion rate", "funnel", "embudo")),
    ("channels", ("canal", "canales", "channel", "channels", "medios", "media")),
    ("pricing", ("precio", "precios", "pricing", "tarifa", "descuento", "discount")),
    ("data", ("datos", "data", "analitica", "analítica", "analytics", "medicion", "medición")),
    ("ai", ("inteligencia artificial", "ia", "artificial intelligence", " ai ", "machine learning")),
    ("innovation", ("innovacion", "innovación", "innovation", "nuevo producto", "i+d")),
    ("customer_experience", ("experiencia de cliente", "experiencia cliente", "customer experience", "cx", "satisfaccion", "satisfacción")),
    ("metrics", ("metrica", "métrica", "metricas", "métricas", "kpi", "indicadores", "results", "resultados")),
    ("products", ("producto", "productos", "portafolio", "catálogo", "catalogo", "servicios", "product", "products", "portfolio", "offering")),
    ("regions", ("region", "región", "regiones", "mercados", "geografía", "geografia", "territorio", "regions", "markets", "geography")),
    ("customers", ("cliente", "clientes", "segmento", "segmentos", "audiencia", "customer", "customers", "segment", "audience")),
    ("competition", ("competencia", "competidor", "competidores", "posicionamiento", "competition", "competitor", "positioning")),
    ("risks", ("riesgo", "riesgos", "risk", "risks", "mitigación", "mitigacion", "mitigation")),
    ("budget", ("presupuesto", "budget", "inversión", "inversion", "costos", "costes", "cost")),
    ("timeline", ("cronograma", "calendario", "timeline", "roadmap", "fases", "hitos", "milestones", "plazos")),
    ("team", ("equipo", "team", "roles", "talento", "organización", "organizacion", "gobernanza", "governance")),
    ("marketing", ("marketing", "campaña", "campana", "marca", "brand", "demanda", "demand", "contenido", "content")),
    ("sales", ("ventas", "comercial", "sales", "pipeline", "ingresos", "revenue")),
    ("framework", ("marco", "framework", "metodología", "metodologia", "modelo", "model")),
    ("research", ("investigación", "investigacion", "hallazgos", "findings", "tendencias", "trends")),
    ("conclusions", ("conclusión", "conclusion", "conclusiones", "conclusions", "recomendaciones", "recommendations")),
    ("closing", ("cierre", "closing", "próximos pasos", "próximo paso", "next steps", "gracias", "thank you")),
    ("plan", ("plan", "plan de acción", "plan de accion", "action plan", "implementación", "implementacion")),
]


def _strip_accents(value: str) -> str:
    return (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ü", "u").replace("ñ", "n")
    )


_ES_ACCENTS = {
    "metricas": "métricas", "metrica": "métrica", "analitica": "analítica",
    "analisis": "análisis", "conversion": "conversión", "conversiones": "conversiones",
    "informacion": "información", "investigacion": "investigación",
    "implementacion": "implementación", "organizacion": "organización",
    "transformacion": "transformación", "capacitacion": "capacitación",
    "operacion": "operación", "operaciones": "operaciones",
    "logistica": "logística", "geografia": "geografía", "inversion": "inversión",
    "presupuesto": "presupuesto", "rentabilidad": "rentabilidad",
    "satisfaccion": "satisfacción", "retencion": "retención",
    "categoria": "categoría", "categorias": "categorías",
    "estrategia": "estrategia", "diagnostico": "diagnóstico",
    "pronostico": "pronóstico", "escenario": "escenario",
    "proximo": "próximo", "proximos": "próximos", "dia": "día", "dias": "días",
    "pagina": "página", "paginas": "páginas", "version": "versión",
    "resumen": "resumen", "contexto": "contexto", "riesgos": "riesgos",
    "mitigacion": "mitigación", "recomendaciones": "recomendaciones",
    "inteligencia": "inteligencia", "artificial": "artificial",
    "innovacion": "innovación", "experiencia": "experiencia",
    "cliente": "cliente", "clientes": "clientes", "ventas": "ventas",
    "comercial": "comercial", "marketing": "marketing", "finanzas": "finanzas",
    "producto": "producto", "productos": "productos", "talento": "talento",
    "equipo": "equipo", "equipos": "equipos", "cadena": "cadena",
    "suministro": "suministro", "sostenibilidad": "sostenibilidad",
    "energia": "energía", "emisiones": "emisiones", "residuos": "residuos",
    "calidad": "calidad", "proceso": "proceso", "procesos": "procesos",
    "canales": "canales", "canal": "canal", "precio": "precio",
    "precios": "precios", "datos": "datos", "tecnologia": "tecnología",
    "digital": "digital", "plataforma": "plataforma", "mercado": "mercado",
    "mercados": "mercados", "competencia": "competencia", "costo": "costo",
    "costos": "costos", "margen": "margen", "caja": "caja",
}


def polish_text(value: str, lang: str = "es") -> str:
    """Normalize casing and restore Spanish accents for common business words."""
    text = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;-")
    if not text:
        return text
    if lang == "es":
        def fix(match: re.Match) -> str:
            word = match.group(0)
            replacement = _ES_ACCENTS.get(_strip_accents(word).lower())
            if not replacement:
                return word
            return replacement.capitalize() if word[:1].isupper() else replacement
        text = re.sub(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", fix, text)
    return text[:1].upper() + text[1:]


def polish_title(value: str, lang: str = "es") -> str:
    text = polish_text(value, lang)
    if not text:
        return "Informe ejecutivo" if lang == "es" else "Executive report"
    if lang == "es":
        words = text.split()
        domain_words = {
            "marketing", "ventas", "clientes", "producto", "productos", "finanzas",
            "talento", "operaciones", "logística", "tecnología", "ia", "datos",
            "canales", "conversión", "riesgos", "estrategia", "mercado", "competencia",
            "innovación", "sostenibilidad", "energía", "comercial", "rrhh",
            "crecimiento", "transformación", "expansión", "rentabilidad", "productividad",
        }
        if (
            len(words) == 2
            and _strip_accents(words[0].lower()) in {"metricas", "datos", "resultados", "tendencias", "indicadores", "kpis"}
            and _strip_accents(words[1].lower()) in domain_words
        ):
            text = f"{words[0]} de {words[1]}"
        elif (
            len(words) >= 2
            and _strip_accents(words[0].lower()) in {"estrategia", "plan", "proyecto", "programa", "modelo", "marco", "presupuesto"}
            and _strip_accents(words[1].lower()) in domain_words
        ):
            text = f"{words[0]} de {' '.join(words[1:])}"
    return text


def classify_topic(topic: str) -> str:
    clean = _strip_accents(str(topic or "").lower())
    for kind, words in _TOPIC_ALIASES:
        for word in words:
            token = _strip_accents(word)
            if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", clean):
                return kind
    return "generic"


def _metric_text(metrics: Sequence[dict], lang: str, limit: int = 3) -> str:
    if not metrics:
        return tr(lang, "no_metrics")
    return "; ".join(f"{m['label']} {m['display']}" for m in metrics[:limit])


def _pick_metric(
    metrics: Sequence[dict], keywords: Sequence[str]
) -> Optional[dict]:
    """Return the first metric whose label matches one of ``keywords``."""
    for keyword in keywords:
        token = _strip_accents(str(keyword or "").lower())
        if not token:
            continue
        for metric in metrics:
            label = _strip_accents(str(metric.get("label", "")).lower())
            if token in label:
                return metric
    return None


def _kpi_phrase(kpi: str) -> str:
    """Lowercase a KPI for prose while keeping acronyms such as CAC or LTV intact."""
    text = str(kpi or "").strip()
    letters = [char for char in text if char.isalpha()]
    if letters and sum(1 for char in letters if char.isupper()) / len(letters) >= 0.6:
        return text
    return text.lower()


def _topic_bullets(topic: str, kind: str, plan: dict[str, Any]) -> list[str]:
    lang = plan["lang"]
    title = plan["title"]
    pack = plan["domain"]
    metrics = plan["metrics"]
    frameworks = _pick(pack["frameworks"], lang)
    kpis = _pick(pack["kpis"], lang)
    risks = _pick(pack["risks"], lang)
    actions = _pick(pack["actions"], lang)
    findings = plan["findings"]
    es = lang == "es"

    if kind == "summary":
        return list(plan["key_messages"])[:3] + [
            ("Siguiente paso: aprobar el alcance y asignar un dueño único." if es
             else "Next step: approve the scope and assign a single owner.")
        ]
    if kind == "context":
        context = list(_pick(pack["context"], lang))
        implication = (
            f"Implicación: el foco debe estar en {_pick(pack['focus'], lang)}."
            if es else
            f"Implication: the focus should be {_pick(pack['focus'], lang)}."
        )
        return context[:3] + [implication]
    if kind == "objectives":
        if es:
            return [
                f"Objetivo 1: ordenar {topic.lower()} en torno a una línea base verificable.",
                f"Objetivo 2: mover {_kpi_phrase(kpis[0])} sin deteriorar {_kpi_phrase(kpis[1])}.",
                f"Objetivo 3: dejar instalada una rutina de revisión con dueño y fecha.",
                f"Criterio de éxito: decisión documentada y avance medible a 90 días.",
            ]
        return [
            f"Objective 1: organize {topic.lower()} around a verifiable baseline.",
            f"Objective 2: move {_kpi_phrase(kpis[0])} without hurting {_kpi_phrase(kpis[1])}.",
            "Objective 3: install a review routine with an owner and a date.",
            "Success criterion: a documented decision and measurable progress at 90 days.",
        ]
    if kind == "metrics":
        if metrics:
            bullets = [
                (f"{m['label']}: {m['display']}." if es else f"{m['label']}: {m['display']}.")
                for m in metrics[:4]
            ]
            bullets.append(
                ("Lectura: separar volumen, precio y margen antes de concluir." if es
                 else "Reading: separate volume, price and margin before concluding.")
            )
            return bullets[:5]
        return [
            (f"KPI recomendado: {kpi}." if es else f"Recommended KPI: {kpi}.")
            for kpi in kpis[:4]
        ]
    if kind == "products":
        return [
            ("Portafolio: separar productos tractores, productos de margen y cola larga." if es
             else "Portfolio: separate volume drivers, margin products and the long tail."),
            (f"Decisión: priorizar los que sostienen {_kpi_phrase(metrics[0]['label']) if metrics else _kpi_phrase(kpis[0])} sin sacrificar rentabilidad." if es
             else f"Decision: prioritize what sustains {_kpi_phrase(metrics[0]['label']) if metrics else _kpi_phrase(kpis[0])} without sacrificing profitability."),
            ("Evidencia: cruzar ventas, margen y rotación antes de ampliar el catálogo." if es
             else "Evidence: cross sales, margin and turns before expanding the catalog."),
            ("Acción: rediseñar o retirar los productos de baja contribución." if es
             else "Action: redesign or retire low-contribution products."),
        ]
    if kind == "regions":
        return [
            ("Concentración: identificar qué mercados explican la mayor parte del resultado." if es
             else "Concentration: identify which markets explain most of the result."),
            ("Criterio: priorizar regiones por potencial, costo de entrada y facilidad de servicio." if es
             else "Criterion: prioritize regions by potential, entry cost and ease of service."),
            ("Riesgo: expandirse sin capacidad operativa ni propuesta local." if es
             else "Risk: expanding without operating capacity or a local proposition."),
            ("Acción: piloto en 1-2 regiones con métricas de entrada y salida." if es
             else "Action: pilot in 1-2 regions with clear entry and exit metrics."),
        ]
    if kind == "customers":
        return [
            ("Segmentos: distinguir valor, frecuencia y costo de servir." if es
             else "Segments: distinguish value, frequency and cost-to-serve."),
            ("Propuesta: un mensaje y una oferta por segmento, no una sola propuesta para todos." if es
             else "Proposition: one message and offer per segment, not one for everyone."),
            ("Retención: medir la segunda compra y el uso real, no solo la adquisición." if es
             else "Retention: measure the second purchase and actual usage, not acquisition alone."),
            ("Acción: entrevistar 10 clientes y validar el problema antes de invertir más." if es
             else "Action: interview 10 customers and validate the problem before investing more."),
        ]
    if kind == "competition":
        return [
            ("Posicionamiento: definir en qué dimensión se quiere ser la opción obvia." if es
             else "Positioning: define the dimension where you want to be the obvious choice."),
            ("Diferenciadores: comparar promesa, evidencia, precio y experiencia de servicio." if es
             else "Differentiators: compare promise, proof, price and service experience."),
            ("Riesgo: competir por precio sin una estructura de costos superior." if es
             else "Risk: competing on price without a superior cost structure."),
            ("Acción: construir una matriz de alternativas y validar con clientes." if es
             else "Action: build an alternatives matrix and validate it with customers."),
        ]
    if kind == "risks":
        bullets = [
            (f"{item['risk']}: {item['mitigation']}" if es else f"{item['risk']}: {item['mitigation']}")
            for item in risks[:3]
        ]
        bullets.append(
            ("Gobernanza: revisar riesgos en la misma cadencia que los resultados." if es
             else "Governance: review risks on the same cadence as results.")
        )
        return bullets
    if kind == "budget":
        return [
            ("Asignación 70/20/10: sostener lo que funciona, mejorar lo clave y explorar lo nuevo." if es
             else "70/20/10 allocation: sustain what works, improve what matters and explore the new."),
            ("Contingencia: reservar 10-15% para imprevistos y oportunidades." if es
             else "Contingency: reserve 10-15% for surprises and opportunities."),
            ("Control: revisar desviación mensual por centro de costo y por iniciativa." if es
             else "Control: review monthly variance by cost center and initiative."),
            ("Retorno: exigir una hipótesis de retorno antes de aprobar la inversión." if es
             else "Return: require a return hypothesis before approving investment."),
        ]
    if kind == "timeline":
        return [
            (f"30 días: {actions['30'][0]}" if es else f"30 days: {actions['30'][0]}"),
            (f"60 días: {actions['60'][0]}" if es else f"60 days: {actions['60'][0]}"),
            (f"90 días: {actions['90'][0]}" if es else f"90 days: {actions['90'][0]}"),
            ("Cadencia: revisión semanal de avance y mensual de resultados." if es
             else "Cadence: weekly progress review and monthly results review."),
        ]
    if kind == "team":
        return [
            ("Roles: un dueño por resultado, no un comité sin responsabilidad final." if es
             else "Roles: one owner per result, not a committee without final accountability."),
            ("Capacidades: identificar las 3 habilidades críticas y cerrar la brecha con plan." if es
             else "Capabilities: identify the three critical skills and close the gap with a plan."),
            ("Gobernanza: decisiones en cadencia fija, con datos y criterios explícitos." if es
             else "Governance: decisions on a fixed cadence with data and explicit criteria."),
            ("Riesgo: dependencia de personas clave sin plan de sucesión." if es
             else "Risk: key-person dependency without a succession plan."),
        ]
    if kind == "marketing":
        return [
            ("Embudo: medir alcance, consideración, conversión y recompra por separado." if es
             else "Funnel: measure reach, consideration, conversion and repeat purchase separately."),
            ("Canales: concentrar la inversión en 2-3 canales con evidencia antes de escalar." if es
             else "Channels: concentrate spend on 2-3 channels with evidence before scaling."),
            ("Mensaje: una promesa verificable y una prueba por segmento." if es
             else "Message: one verifiable promise and one proof point per segment."),
            ("Medición: combinar atribución con experimentos de incremento." if es
             else "Measurement: combine attribution with incrementality experiments."),
        ]
    if kind == "sales":
        return [
            ("Pipeline: calificar por dolor, presupuesto, decisor y fecha real." if es
             else "Pipeline: qualify by pain, budget, decision-maker and real date."),
            ("Conversión: medir por etapa y detectar dónde se estanca la oportunidad." if es
             else "Conversion: measure by stage and detect where opportunities stall."),
            ("Ticket: revisar mezcla, descuentos y costo de servir." if es
             else "Deal size: review mix, discounts and cost-to-serve."),
            ("Retención: la segunda compra y la expansión valen más que una venta aislada." if es
             else "Retention: the second purchase and expansion matter more than a one-off sale."),
        ]
    if kind == "conversion":
        conversion_metric = _pick_metric(
            metrics,
            (
                "conversion", "conversión", "tasa", "rate", "cvr", "cr",
                "cierre", "close",
            ),
        )
        volume_metric = _pick_metric(
            metrics,
            (
                "lead", "visita", "visit", "sesión", "session", "tráfico",
                "traffic", "clic", "click", "usuario", "user", "prospecto",
                "oportunidad", "opportunity",
            ),
        )
        if conversion_metric:
            rate_text = f"{conversion_metric['label']} {conversion_metric['display']}"
        else:
            rate_text = (
                "no incluida en la solicitud" if es
                else "not provided in the request"
            )
        volume_ref = (
            _kpi_phrase(volume_metric["label"]) if volume_metric
            else ("el volumen de entrada" if es else "the input volume")
        )
        return [
            (f"Tasa actual: {rate_text}; leerla contra {volume_ref}, no contra el gasto." if es
             else f"Current rate: {rate_text}; read it against {volume_ref}, not against spend."),
            ("Embudo: medir paso a paso y atacar el punto con mayor caída, no el que más se ve." if es
             else "Funnel: measure step by step and fix the biggest drop, not the most visible one."),
            ("Fricción: revisar formularios, tiempos de respuesta y claridad de la oferta." if es
             else "Friction: review forms, response times and offer clarity."),
            ("Prueba: un experimento por hipótesis, con tamaño de muestra definido antes de lanzar." if es
             else "Test: one experiment per hypothesis, with the sample size defined before launch."),
        ]
    if kind == "channels":
        result_metric = _pick_metric(
            metrics,
            (
                "ingreso", "revenue", "venta", "sales", "conversion", "conversión",
                "lead", "resultado", "roas", "margen", "margin", "contribución",
            ),
        )
        cost_metric = _pick_metric(
            metrics,
            (
                "gasto", "spend", "costo", "cost", "inversión", "investment",
                "cac",
            ),
        )
        result_ref = (
            _kpi_phrase(result_metric["label"]) if result_metric
            else ("el resultado" if es else "the outcome")
        )
        cost_ref = (
            f" ({_kpi_phrase(cost_metric['label'])} {cost_metric['display']})"
            if cost_metric else ""
        )
        return [
            (f"Contribución: ordenar cada canal por {result_ref}, no por volumen de actividad." if es
             else f"Contribution: rank each channel by {result_ref}, not by activity volume."),
            (f"Costo: comparar costo por resultado{cost_ref} y no solo costo por clic o por impresión." if es
             else f"Cost: compare cost per outcome{cost_ref}, not just cost per click or impression."),
            ("Concentración: sostener 2-3 canales con evidencia y podar el resto." if es
             else "Concentration: sustain 2-3 channels with evidence and prune the rest."),
            ("Medición: separar atribución de correlación con un experimento de incremento." if es
             else "Measurement: separate attribution from correlation with an incrementality test."),
        ]
    if kind == "pricing":
        price_metric = _pick_metric(
            metrics,
            (
                "precio", "price", "ticket", "margen", "margin", "arpu",
                "descuento", "discount", "valor", "value",
            ),
        )
        price_ref = (
            f"{_kpi_phrase(price_metric['label'])} {price_metric['display']}"
            if price_metric
            else ("el valor percibido" if es else "perceived value")
        )
        return [
            (f"Referencia: contrastar precio con {price_ref} y con el costo de servir." if es
             else f"Reference: test price against {price_ref} and cost-to-serve."),
            ("Disciplina: fijar una guía de descuentos y aprobación para excepciones." if es
             else "Discipline: set a discount guide and an approval path for exceptions."),
            ("Mezcla: revisar qué combinación de planes sostiene el margen." if es
             else "Mix: review which plan combination sustains margin."),
            ("Prueba: piloto de precio en un segmento acotado antes de un cambio general." if es
             else "Test: price pilot in a bounded segment before a broad change."),
        ]
    if kind == "data":
        return [
            ("Definición: una métrica por decisión, con fórmula, dueño y fuente única." if es
             else "Definition: one metric per decision, with formula, owner and single source."),
            ("Calidad: medir cobertura, duplicados y retraso antes de confiar en el tablero." if es
             else "Quality: measure coverage, duplicates and lag before trusting the dashboard."),
            ("Acceso: separar dato operativo, reporte y análisis para no mezclar responsabilidades." if es
             else "Access: separate operational data, reporting and analysis to avoid mixed ownership."),
            ("Rutina: revisión semanal de pocos indicadores y revisión mensual de tendencia." if es
             else "Routine: weekly review of a few indicators and monthly trend review."),
        ]
    if kind == "ai":
        return [
            ("Caso de uso: elegir una tarea repetitiva y medible antes de comprar tecnología." if es
             else "Use case: choose one repetitive, measurable task before buying technology."),
            ("Control: mantener revisión humana en decisiones con impacto en cliente o dinero." if es
             else "Control: keep human review on decisions affecting customers or money."),
            ("Datos: verificar privacidad, licencia y trazabilidad de las fuentes usadas." if es
             else "Data: verify privacy, licensing and traceability of the sources used."),
            ("Retorno: medir tiempo ahorrado y calidad, no solo número de usuarios." if es
             else "Return: measure time saved and quality, not just user count."),
        ]
    if kind == "innovation":
        return [
            ("Portafolio: separar mejoras del negocio actual, apuestas nuevas y opciones futuras." if es
             else "Portfolio: separate core improvements, new bets and future options."),
            ("Hipótesis: formular qué debe ser cierto para que la apuesta funcione." if es
             else "Hypothesis: state what must be true for the bet to work."),
            ("Prueba: prototipo barato con usuarios reales antes de invertir en producción." if es
             else "Test: cheap prototype with real users before investing in production."),
            ("Decisión: criterio explícito para escalar, pivotar o detener." if es
             else "Decision: explicit criteria to scale, pivot or stop."),
        ]
    if kind == "customer_experience":
        return [
            ("Recorrido: mapear los momentos que más pesan en la decisión y en la recompra." if es
             else "Journey: map the moments that most affect the decision and repeat purchase."),
            ("Fricción: eliminar pasos antes de añadir funciones o canales." if es
             else "Friction: remove steps before adding features or channels."),
            ("Señal: medir esfuerzo, respuesta y resolución, no solo satisfacción declarada." if es
             else "Signal: measure effort, response and resolution, not just stated satisfaction."),
            ("Cierre: cerrar el bucle con el cliente y comunicar el cambio realizado." if es
             else "Loop: close the loop with the customer and communicate the change made."),
        ]
    if kind == "framework":
        framework = frameworks[0]
        return [f"{step}." for step in framework["steps"]] + [
            (f"Uso: aplicar {framework['name']} a {title} con un dueño y una fecha." if es
             else f"Use: apply {framework['name']} to {title} with an owner and a date.")
        ]
    if kind == "research":
        if findings:
            return [
                (f"{item['title']}: {item['snippet']}" if es else f"{item['title']}: {item['snippet']}")
                for item in findings[:3]
            ]
        return list(_pick(pack["trends"], lang))
    if kind == "conclusions":
        return list(plan["recommendations"])[:3] + [
            ("Decisión: aprobar la primera fase y revisar a 30 días." if es
             else "Decision: approve the first phase and review at 30 days.")
        ]
    if kind == "closing":
        return [
            ("Aprobar el alcance y el presupuesto de la primera fase." if es
             else "Approve the scope and budget for the first phase."),
            ("Asignar un dueño único con mandato y fecha." if es
             else "Assign a single owner with a mandate and a date."),
            ("Revisar a 30 días con datos, no con percepciones." if es
             else "Review at 30 days with data, not perceptions."),
            ("Documentar aprendizajes y ajustar el plan." if es
             else "Document learnings and adjust the plan."),
        ]
    if kind == "plan":
        return [
            (f"30 días: {actions['30'][0]}" if es else f"30 days: {actions['30'][0]}"),
            (f"60 días: {actions['60'][0]}" if es else f"60 days: {actions['60'][0]}"),
            (f"90 días: {actions['90'][0]}" if es else f"90 days: {actions['90'][0]}"),
            ("Revisión: semanal de avance, mensual de resultados." if es
             else "Review: weekly progress, monthly results."),
        ]

    # Generic topic: still contextual, never "what is X".
    metric_ref = metrics[0]["label"].lower() if metrics else _kpi_phrase(kpis[0])
    if es:
        return [
            f"Situación: {topic.lower()} se lee contra la línea base de {metric_ref}.",
            f"Palanca: {frameworks[0]['name']} ordena las decisiones y evita iniciativas sueltas.",
            f"Medida: {_kpi_phrase(kpis[0])} con responsable y revisión semanal.",
            f"Riesgo: {risks[0]['risk'].lower()}.",
        ]
    return [
        f"Situation: {topic.lower()} is read against the baseline of {metric_ref}.",
        f"Lever: {frameworks[0]['name']} organizes decisions and prevents scattered initiatives.",
        f"Measure: {_kpi_phrase(kpis[0])} with an owner and weekly review.",
        f"Risk: {risks[0]['risk'].lower()}.",
    ]


# ---------------------------------------------------------------------------
# Content plan
# ---------------------------------------------------------------------------

def _requested_slides(text: str) -> Optional[int]:
    match = re.search(r"(?i)\b(\d{1,2})\s*(?:diapositivas?|slides?|páginas?|paginas?)\b", str(text or ""))
    if not match:
        return None
    value = int(match.group(1))
    return value if 5 <= value <= 30 else None


def _wants_animations(text: str) -> bool:
    lowered = _strip_accents(str(text or "").lower())
    if any(token in lowered for token in ("sin animacion", "sin animaciones", "no animation", "no animations", "static deck")):
        return False
    return True


def _dedupe_topics(topics: Sequence[str], limit: int = 7) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        clean = re.sub(r"\s+", " ", str(topic or "")).strip(" .,:;-")
        if len(clean) < 3:
            continue
        key = _strip_accents(clean.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(clean[:1].upper() + clean[1:])
        if len(result) >= limit:
            break
    return result


def _key_messages(title: str, pack: dict[str, Any], metrics: Sequence[dict], lang: str) -> list[str]:
    focus = _pick(pack["focus"], lang)
    kpis = _pick(pack["kpis"], lang)
    if lang == "es":
        baseline = (
            f"Punto de partida: {_metric_text(metrics, lang, 2)}."
            if metrics else f"Punto de partida: definir la línea base de {_kpi_phrase(kpis[0])}."
        )
        return [
            baseline,
            f"Apuesta: concentrar los recursos en {focus}.",
            f"Ejecución: 3 fases, un dueño por resultado y revisión semanal de {_kpi_phrase(kpis[0])}.",
        ]
    baseline = (
        f"Starting point: {_metric_text(metrics, lang, 2)}."
        if metrics else f"Starting point: define the baseline for {_kpi_phrase(kpis[0])}."
    )
    return [
        baseline,
        f"Bet: concentrate resources on {focus}.",
        f"Execution: three phases, one owner per result and weekly review of {_kpi_phrase(kpis[0])}.",
    ]


def _executive_summary(title: str, pack: dict[str, Any], metrics: Sequence[dict], lang: str) -> str:
    focus = _pick(pack["focus"], lang)
    kpis = _pick(pack["kpis"], lang)
    if lang == "es":
        if metrics:
            metric_word = "métrica" if len(metrics) == 1 else "métricas"
            return (
                f"{title} se analiza a partir de {len(metrics)} {metric_word} de la solicitud "
                f"({_metric_text(metrics, lang, 3)}). El documento ordena el contexto, "
                f"los hallazgos y un plan a 90 días para mover {focus}. "
                f"La decisión central no es añadir iniciativas, sino priorizar las que "
                f"pueden demostrarse con {_kpi_phrase(kpis[0])} y {_kpi_phrase(kpis[1])}."
            )
        return (
            f"{title} se aborda con un enfoque de gestión: contexto, evidencia y un plan "
            f"ejecutable. El foco propuesto es {focus}. El documento define una línea base, "
            f"tres decisiones y una cadencia de revisión para evitar que el plan quede en intenciones."
        )
    if metrics:
        metric_word = "metric" if len(metrics) == 1 else "metrics"
        return (
            f"{title} is analyzed through {len(metrics)} {metric_word} from the request "
            f"({_metric_text(metrics, lang, 3)}). The document organizes context, findings "
            f"and a 90-day plan to move {focus}. The central decision is not to add initiatives, "
            f"but to prioritize those that can be proven with {_kpi_phrase(kpis[0])} and {_kpi_phrase(kpis[1])}."
        )
    return (
        f"{title} is approached with a management lens: context, evidence and an executable plan. "
        f"The proposed focus is {focus}. The document defines a baseline, three decisions and a "
        f"review cadence so the plan does not remain a statement of intent."
    )


def _context_paragraphs(title: str, pack: dict[str, Any], research: Sequence[dict], lang: str) -> list[str]:
    context = list(_pick(pack["context"], lang))
    if lang == "es":
        context.append(
            f"Aplicado a {title}, el reto es convertir el análisis en una decisión con dueño, "
            "presupuesto y fecha, no en un documento más."
        )
        if research:
            context.append(f"Señal externa: {research[0]['snippet']}")
    else:
        context.append(
            f"Applied to {title}, the challenge is to turn analysis into a decision with an owner, "
            "a budget and a date, not another document."
        )
        if research:
            context.append(f"External signal: {research[0]['snippet']}")
    return context[:4]


def _findings(pack: dict[str, Any], research: Sequence[dict], lang: str) -> list[dict[str, str]]:
    if research:
        return [
            {
                "title": item["title"],
                "snippet": item["snippet"],
                "source": item["source"],
                "url": item["url"],
                "kind": "web",
            }
            for item in research[:3]
        ]
    trends = list(_pick(pack["trends"], lang))
    findings: list[dict[str, str]] = []
    for trend in trends[:3]:
        title = trend.split(":")[0].strip()
        findings.append(
            {
                "title": title[:1].upper() + title[1:],
                "snippet": trend,
                "source": tr(lang, "internal_framework"),
                "url": "",
                "kind": "internal",
            }
        )
    return findings


def _recommendations(title: str, pack: dict[str, Any], metrics: Sequence[dict], lang: str) -> list[str]:
    focus = _pick(pack["focus"], lang)
    if lang == "es":
        return [
            f"Aprobar 3 apuestas y detener explícitamente lo que no contribuye a {focus}.",
            "Asignar un dueño y una métrica a cada apuesta, con revisión semanal y presupuesto acotado.",
            "Validar los supuestos con datos antes de escalar; dejar una reserva para aprender y corregir.",
        ]
    return [
        f"Approve three bets and explicitly stop what does not contribute to {focus}.",
        "Assign one owner and one metric to each bet, with weekly review and a bounded budget.",
        "Validate assumptions with data before scaling; keep a reserve to learn and correct.",
    ]


def _default_topics(pack: dict[str, Any], lang: str) -> list[str]:
    if lang == "es":
        return ["Contexto y objetivos", "Métricas clave", "Riesgos y mitigación", "Plan de acción"]
    return ["Context and objectives", "Key metrics", "Risks and mitigation", "Action plan"]


_SPECIFIC_TOPICS: dict[str, dict[str, list[str]]] = {
    "sales": {
        "es": ["Clientes y segmentos", "Competencia y posicionamiento", "Pipeline comercial"],
        "en": ["Customers and segments", "Competition and positioning", "Sales pipeline"],
    },
    "marketing": {
        "es": ["Canales y mezcla", "Conversión", "Clientes y segmentos"],
        "en": ["Channels and mix", "Conversion", "Customers and segments"],
    },
    "finance": {
        "es": ["Presupuesto y asignación", "Rentabilidad por unidad", "Flujo de caja"],
        "en": ["Budget and allocation", "Unit profitability", "Cash flow"],
    },
    "product_tech": {
        "es": ["Producto y portafolio", "Datos y analítica", "IA y automatización"],
        "en": ["Product and portfolio", "Data and analytics", "AI and automation"],
    },
    "people": {
        "es": ["Equipo y roles", "Cultura y retención", "Capacidades críticas"],
        "en": ["Team and roles", "Culture and retention", "Critical capabilities"],
    },
    "operations": {
        "es": ["Procesos y cuellos de botella", "Cadena de suministro", "Calidad y trazabilidad"],
        "en": ["Processes and bottlenecks", "Supply chain", "Quality and traceability"],
    },
    "sustainability": {
        "es": ["Materialidad y metas", "Energía y emisiones", "Cadena de suministro"],
        "en": ["Materiality and targets", "Energy and emissions", "Supply chain"],
    },
    "strategy": {
        "es": ["Competencia y posicionamiento", "Mercados y expansión", "Marco de priorización"],
        "en": ["Competition and positioning", "Markets and expansion", "Prioritization framework"],
    },
    "general": {
        "es": ["Objetivos y alcance", "Marco de trabajo", "Plan de implementación"],
        "en": ["Objectives and scope", "Working framework", "Implementation plan"],
    },
}


_STANDARD_KINDS = {"summary", "context", "metrics", "risks", "plan", "closing", "conclusions", "framework", "research"}


def _specific_topics(pack: dict[str, Any], lang: str) -> list[str]:
    pack_topics = _SPECIFIC_TOPICS.get(str(pack.get("key")), _SPECIFIC_TOPICS["general"])
    return list(_pick(pack_topics, lang) or _SPECIFIC_TOPICS["general"][lang])


def build_plan(
    title: str,
    raw: str,
    data: dict[str, Any],
    lang: str,
    research_enabled: bool = True,
    progress: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Build the single source of truth used by PPTX, XLSX, DOCX and PDF."""
    pack = detect_domain(raw, title)
    lang_title = polish_title(title, lang)
    metrics: list[dict[str, Any]] = []
    for item in data.get("metrics") or []:
        metric = dict(item)
        metric["label"] = polish_text(str(metric.get("label") or ""), lang)
        metrics.append(metric)
    raw_topics = _dedupe_topics(data.get("bullets") or [])
    specific = [topic for topic in raw_topics if classify_topic(topic) not in _STANDARD_KINDS]
    topics = specific or _specific_topics(pack, lang)
    topics = _dedupe_topics(topics, limit=4)

    if progress:
        progress("Analizando el contexto y la estructura..." if lang == "es" else "Analyzing context and structure...")

    research: list[dict[str, str]] = []
    if research_enabled:
        if progress:
            progress("Investigando tendencias y fuentes..." if lang == "es" else "Researching trends and sources...")
        research = research_topic(lang_title, pack, lang)

    if progress:
        progress("Construyendo el hilo narrativo..." if lang == "es" else "Building the narrative...")

    key_messages = _key_messages(lang_title, pack, metrics, lang)
    summary = _executive_summary(lang_title, pack, metrics, lang)
    context = _context_paragraphs(lang_title, pack, research, lang)
    findings = _findings(pack, research, lang)
    frameworks = _pick(pack["frameworks"], lang)
    risks = _pick(pack["risks"], lang)
    actions = _pick(pack["actions"], lang)
    recommendations = _recommendations(lang_title, pack, metrics, lang)
    kpis = _pick(pack["kpis"], lang)

    deep_dives: list[dict[str, Any]] = []
    for topic in topics:
        kind = classify_topic(topic)
        deep_dives.append(
            {
                "topic": polish_text(topic, lang),
                "kind": kind,
                "bullets": _topic_bullets(topic, kind, {
                    "lang": lang,
                    "title": lang_title,
                    "domain": pack,
                    "metrics": metrics,
                    "findings": findings,
                    "key_messages": key_messages,
                    "recommendations": recommendations,
                }),
            }
        )

    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in research:
        if item["url"] and item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            sources.append(item)

    plan: dict[str, Any] = {
        "lang": lang,
        "title": lang_title,
        "raw": raw,
        "domain": pack,
        "domain_label": domain_label(pack, lang),
        "theme": pack.get("theme", "navy"),
        "metrics": metrics,
        "topics": [polish_text(topic, lang) for topic in topics],
        "research": research,
        "findings": findings,
        "sources": sources,
        "key_messages": key_messages,
        "executive_summary": summary,
        "context": context,
        "frameworks": frameworks,
        "framework": frameworks[0],
        "risks": risks,
        "actions": actions,
        "recommendations": recommendations,
        "kpis": kpis,
        "deep_dives": deep_dives,
        "requested_slides": _requested_slides(raw),
        "animations": _wants_animations(raw),
        "generated_at": _dt.datetime.now().strftime("%d/%m/%Y"),
    }
    return plan


def _chart_metrics(metrics: Sequence[dict]) -> list[dict]:
    """Return a comparable group of metrics sharing a unit and magnitude.

    Metrics in the same unit can still be wildly different in scale (1 280
    conversions vs 187 500 revenue).  Charting them together makes the small
    value unreadable, so values more than 8x away from the group median are
    excluded from the chart and shown in the table instead.
    """
    groups: dict[str, list[dict]] = {}
    for metric in metrics:
        try:
            float(metric.get("value"))
        except (TypeError, ValueError):
            continue
        unit = str(metric.get("unit") or "").strip().lower()
        key = unit or "number"
        groups.setdefault(key, []).append(metric)
    if not groups:
        return []
    best = max(groups.values(), key=len)
    if len(best) < 2:
        return []
    values = sorted(abs(float(m["value"])) for m in best)
    median = values[len(values) // 2]
    if median <= 0:
        return best
    kept = [m for m in best if median / 8 <= abs(float(m["value"])) <= median * 8]
    return kept if len(kept) >= 2 else []


def plan_to_markdown(plan: dict[str, Any]) -> str:
    lang = plan["lang"]
    es = lang == "es"
    lines: list[str] = [f"# {plan['title']}", "", f"*{tr(lang, 'executive_report')} · Orunex · {plan['generated_at']}*", ""]
    lines += [f"## {tr(lang, 'summary')}", "", plan["executive_summary"], ""]
    lines += [f"### {tr(lang, 'key_messages')}", ""]
    lines += [f"- {message}" for message in plan["key_messages"]]
    lines += ["", f"## {tr(lang, 'context')}", ""]
    lines += [paragraph for paragraph in plan["context"]]
    if plan["metrics"]:
        lines += ["", f"## {tr(lang, 'kpi_panel')}", ""]
        lines += [f"- **{m['label']}:** {m['display']}" for m in plan["metrics"]]
    lines += ["", f"## {tr(lang, 'findings')}", ""]
    for item in plan["findings"]:
        lines += [f"### {item['title']}", "", item["snippet"], "", f"*{tr(lang, 'source')}: {item['source']}*", ""]
    for dive in plan["deep_dives"]:
        lines += [f"## {dive['topic']}", ""]
        lines += [f"- {bullet}" for bullet in dive["bullets"]]
        lines.append("")
    lines += [f"## {tr(lang, 'framework')}: {plan['framework']['name']}", "", plan["framework"]["desc"], ""]
    lines += [f"- {step}" for step in plan["framework"]["steps"]]
    lines += ["", f"## {tr(lang, 'risks')}", ""]
    for item in plan["risks"]:
        lines.append(f"- **{item['risk']}** ({item['level']}): {item['mitigation']}")
    lines += ["", f"## {tr(lang, 'roadmap')}", ""]
    for horizon in ("30", "60", "90"):
        lines.append(f"### {horizon} {'días' if es else 'days'}")
        lines += [f"- {action}" for action in plan["actions"][horizon]]
        lines.append("")
    lines += [f"## {tr(lang, 'recommendations')}", ""]
    lines += [f"- {item}" for item in plan["recommendations"]]
    lines += ["", f"## {tr(lang, 'sources')}", ""]
    if plan["sources"]:
        lines += [f"- [{item['source']}]({item['url']}): {item['title']}" for item in plan["sources"]]
    else:
        lines.append(f"- {tr(lang, 'no_external_sources')}")
    lines += ["", tr(lang, "assumptions_text")]
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# PowerPoint design system
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, Any]] = {
    "navy": {
        "name": "Executive Navy",
        "bg": (9, 20, 44), "panel": (20, 39, 78), "accent": (37, 99, 235),
        "accent2": (96, 165, 250), "text": (255, 255, 255), "muted": (166, 188, 222),
        "content_bg": (255, 255, 255), "content_text": (15, 28, 55),
        "content_muted": (92, 108, 132), "card": (244, 248, 255),
        "border": (218, 230, 248), "dark": True, "cover": "orbit",
    },
    "coral": {
        "name": "Growth Coral",
        "bg": (42, 20, 32), "panel": (66, 29, 45), "accent": (244, 90, 80),
        "accent2": (251, 176, 64), "text": (255, 255, 255), "muted": (236, 202, 202),
        "content_bg": (255, 251, 249), "content_text": (45, 25, 35),
        "content_muted": (122, 96, 106), "card": (255, 242, 238),
        "border": (250, 220, 212), "dark": True, "cover": "split",
    },
    "violet": {
        "name": "Creative Violet",
        "bg": (28, 20, 55), "panel": (48, 33, 92), "accent": (139, 92, 246),
        "accent2": (244, 114, 182), "text": (255, 255, 255), "muted": (211, 201, 236),
        "content_bg": (252, 250, 255), "content_text": (35, 25, 60),
        "content_muted": (110, 100, 132), "card": (246, 242, 255),
        "border": (230, 220, 250), "dark": True, "cover": "band",
    },
    "cyan": {
        "name": "Tech Cyan",
        "bg": (7, 24, 34), "panel": (14, 44, 58), "accent": (6, 182, 212),
        "accent2": (34, 211, 238), "text": (255, 255, 255), "muted": (180, 216, 226),
        "content_bg": (247, 253, 255), "content_text": (12, 35, 45),
        "content_muted": (85, 116, 126), "card": (238, 250, 253),
        "border": (205, 235, 242), "dark": True, "cover": "orbit",
    },
    "emerald": {
        "name": "Emerald Strategy",
        "bg": (9, 35, 29), "panel": (18, 59, 50), "accent": (16, 185, 129),
        "accent2": (163, 230, 53), "text": (255, 255, 255), "muted": (185, 226, 211),
        "content_bg": (247, 253, 250), "content_text": (12, 45, 38),
        "content_muted": (85, 121, 106), "card": (236, 251, 245),
        "border": (205, 235, 220), "dark": True, "cover": "split",
    },
    "light": {
        "name": "Editorial Light",
        "bg": (244, 247, 252), "panel": (255, 255, 255), "accent": (13, 92, 99),
        "accent2": (30, 102, 245), "text": (18, 35, 55), "muted": (92, 112, 132),
        "content_bg": (255, 255, 255), "content_text": (18, 35, 55),
        "content_muted": (92, 108, 128), "card": (243, 248, 250),
        "border": (214, 228, 235), "dark": False, "cover": "grid",
    },
}


def _rgb(triple: Sequence[int]):
    from pptx.dml.color import RGBColor  # type: ignore

    return RGBColor(int(triple[0]), int(triple[1]), int(triple[2]))


def _short(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _fmt_value(value: float, unit: str, lang: str) -> str:
    unit = str(unit or "").strip().lower()
    if unit in {"%", "por ciento"}:
        raw = f"{value:,.2f}".rstrip("0").rstrip(".")
        raw = raw.replace(",", " ")
        return raw.replace(".", ",") + " %" if lang == "es" else raw + "%"
    raw = f"{value:,.2f}".rstrip("0").rstrip(".")
    if lang == "es":
        raw = raw.replace(",", " ")
    if unit:
        return f"{raw} {unit.upper()}"
    return raw


def _pptx_helpers(prs, theme: dict[str, Any]):
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # type: ignore
    from pptx.util import Emu, Inches, Pt  # type: ignore

    width = float(prs.slide_width)
    height = float(prs.slide_height)

    def add_rect(slide, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE, line=None, line_width=1.0):
        obj = slide.shapes.add_shape(shape, Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
        if fill is None:
            obj.fill.background()
        else:
            obj.fill.solid()
            obj.fill.fore_color.rgb = _rgb(fill)
        if line is None:
            obj.line.fill.background()
        else:
            obj.line.color.rgb = _rgb(line)
            obj.line.width = Pt(line_width)
        obj.shadow.inherit = False
        return obj

    def add_text(
        slide, x, y, w, h, text, size, color, bold=False, align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.TOP, font="Segoe UI", italic=False, spacing=1.0,
        margins=(0, 0, 0, 0),
    ):
        box = slide.shapes.add_textbox(Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
        frame = box.text_frame
        frame.word_wrap = True
        frame.margin_left = Emu(int(margins[0]))
        frame.margin_right = Emu(int(margins[1]))
        frame.margin_top = Emu(int(margins[2]))
        frame.margin_bottom = Emu(int(margins[3]))
        frame.vertical_anchor = anchor
        lines = str(text).split("\n")
        for index, line in enumerate(lines):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = line
            paragraph.alignment = align
            paragraph.space_after = Pt(0)
            paragraph.space_before = Pt(0)
            paragraph.line_spacing = spacing
            for run in paragraph.runs:
                run.font.name = font
                run.font.size = Pt(size)
                run.font.bold = bold
                run.font.italic = italic
                run.font.color.rgb = _rgb(color)
        return box

    def add_chip(slide, x, y, w, h, text, fill, text_color, size=10, bold=True):
        add_rect(slide, x, y, w, h, fill, MSO_SHAPE.ROUNDED_RECTANGLE)
        add_text(slide, x, y, w, h, text, size, text_color, bold=bold, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    def add_footer(slide, page, total, domain, dark=False):
        color = theme["muted"] if dark else theme["content_muted"]
        add_text(slide, Inches(0.7), height - Inches(0.42), Inches(7.0), Inches(0.25),
                 f"Orunex  ·  {domain}", 8, color)
        add_text(slide, width - Inches(1.5), height - Inches(0.42), Inches(0.8), Inches(0.25),
                 f"{page}/{total}", 8, color, align=PP_ALIGN.RIGHT)

    def add_header(slide, title, kicker, page, total, domain):
        add_rect(slide, 0, 0, width, height, theme["content_bg"])
        band = theme["bg"] if theme["dark"] else theme["panel"]
        add_rect(slide, 0, 0, width, Inches(1.02), band)
        add_rect(slide, 0, Inches(1.02), width, Inches(0.055), theme["accent"])
        text_color = theme["text"] if theme["dark"] else theme["content_text"]
        muted = theme["muted"] if theme["dark"] else theme["content_muted"]
        add_text(slide, Inches(0.7), Inches(0.16), Inches(10.6), Inches(0.24), kicker.upper(), 8.5, muted, bold=True)
        title_box = add_text(slide, Inches(0.7), Inches(0.38), Inches(10.9), Inches(0.52), title, 24, text_color, bold=True)
        add_text(slide, width - Inches(1.5), Inches(0.2), Inches(0.8), Inches(0.3),
                 f"{page}/{total}", 9, muted, align=PP_ALIGN.RIGHT)
        add_footer(slide, page, total, domain, dark=False)
        return title_box

    def add_bullets(slide, x, y, w, bullets, color, accent, size=16, gap=0.82, max_items=5, animate=None):
        current = y
        for bullet in bullets[:max_items]:
            add_rect(slide, x, current + Inches(0.13), Inches(0.09), Inches(0.09), accent, MSO_SHAPE.OVAL)
            box = add_text(slide, x + Inches(0.26), current, w - Inches(0.26), Inches(gap - 0.06),
                           bullet, size, color, spacing=1.02)
            if animate is not None:
                animate.append(box)
            current += Inches(gap)
        return current

    def add_metric_card(slide, x, y, w, h, metric, big=True):
        add_rect(slide, x, y, w, h, theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_rect(slide, x, y, w, Inches(0.075), theme["accent"])
        value = metric.get("display") or _fmt_value(metric.get("value", 0), metric.get("unit", ""), "es")
        add_text(slide, x + Inches(0.22), y + Inches(0.22), w - Inches(0.44), Inches(0.62),
                 _short(str(value), 24), 22 if big else 18, theme["accent"], bold=True)
        add_text(slide, x + Inches(0.22), y + h - Inches(0.62), w - Inches(0.44), Inches(0.42),
                 _short(str(metric.get("label") or ""), 42), 10.5, theme["content_muted"])

    return {
        "width": width, "height": height, "add_rect": add_rect, "add_text": add_text,
        "add_chip": add_chip, "add_footer": add_footer, "add_header": add_header,
        "add_bullets": add_bullets, "add_metric_card": add_metric_card,
    }


def _add_transition(slide, kind: str = "fade") -> None:
    from pptx.oxml.ns import nsdecls, qn  # type: ignore
    from pptx.oxml import parse_xml  # type: ignore

    for tag in ("p:transition", "p:timing"):
        existing = slide.element.find(qn(tag))
        if existing is not None:
            slide.element.remove(existing)
    if kind == "fade":
        xml = f'<p:transition {nsdecls("p")} spd="med" advClick="1"><p:fade/></p:transition>'
    else:
        xml = f'<p:transition {nsdecls("p")} spd="med" advClick="1"><p:push dir="l"/></p:transition>'
    slide.element.append(parse_xml(xml))


def _add_animations(slide, entries: Sequence[tuple[Any, str, int]], transition: str = "fade") -> None:
    """Inject real PowerPoint entrance effects (fade / wipe) into a slide."""
    from pptx.oxml.ns import nsdecls  # type: ignore
    from pptx.oxml import parse_xml  # type: ignore

    if not entries:
        _add_transition(slide, transition)
        return

    _add_transition(slide, transition)
    effects: list[str] = []
    cursor = 5
    for shape, effect, delay in entries:
        if shape is None:
            continue
        spid = int(shape.shape_id)
        preset = 10 if effect == "fade" else 22
        filt = "fade" if effect == "fade" else "wipe(up)"
        cid = cursor
        effects.append(
            f'<p:par><p:cTn id="{cid}" presetID="{preset}" presetClass="entr" presetSubtype="0" '
            f'fill="hold" grpId="0" nodeType="afterEffect"><p:stCondLst><p:cond delay="{int(delay)}"/>'
            f'</p:stCondLst><p:childTnLst><p:set><p:cBhvr><p:cTn id="{cid + 1}" dur="1" fill="hold">'
            f'<p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn><p:tgtEl><p:spTgt spid="{spid}"/>'
            f'</p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
            f'</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
            f'<p:animEffect transition="in" filter="{filt}"><p:cBhvr><p:cTn id="{cid + 2}" dur="450"/>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
            f'</p:childTnLst></p:cTn></p:par>'
        )
        cursor += 3

    timing = (
        f'<p:timing {nsdecls("p")}><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" '
        f'nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" '
        f'dur="indefinite" nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="3" fill="hold">'
        f'<p:stCondLst><p:cond delay="indefinite"/></p:stCondLst><p:childTnLst><p:par>'
        f'<p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
        + "".join(effects)
        + f'</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>'
        f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>'
        f'</p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/>'
        f'</p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
    )
    slide.element.append(parse_xml(timing))


# ---------------------------------------------------------------------------
# Slide composition
# ---------------------------------------------------------------------------

try:  # Keep the module importable even if PowerPoint support is absent.
    from pptx.enum.shapes import MSO_SHAPE  # type: ignore
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # type: ignore
except ImportError:  # pragma: no cover
    MSO_SHAPE = MSO_ANCHOR = PP_ALIGN = None  # type: ignore

_IN = 914400


def _in(value: float) -> int:
    return int(value * _IN)


def _blend(first: Sequence[int], second: Sequence[int], amount: float) -> tuple[int, int, int]:
    return tuple(int(first[i] + (second[i] - first[i]) * amount) for i in range(3))  # type: ignore


def _select_slides(plan: dict[str, Any]) -> list[dict[str, Any]]:
    lang = plan["lang"]
    es = lang == "es"
    dives = [
        {"layout": "deep_dive", "tag": "deep", "dive": dive, "index": index}
        for index, dive in enumerate(plan["deep_dives"])
    ]
    candidates: list[dict[str, Any]] = [
        {"layout": "cover"},
        {"layout": "agenda", "tag": "agenda"},
        {"layout": "summary"},
        {"layout": "context"},
        {"layout": "findings"},
        {"layout": "metrics"},
        {"layout": "divider", "tag": "divider_analysis", "number": "01",
         "title": tr(lang, "analysis"), "subtitle": ("Del contexto a las decisiones." if es else "From context to decisions.")},
        *dives,
        {"layout": "framework", "tag": "framework"},
        {"layout": "risks"},
        {"layout": "divider", "tag": "divider_plan", "number": "02",
         "title": tr(lang, "plan"), "subtitle": ("Tres fases, un dueño por resultado." if es else "Three phases, one owner per result.")},
        {"layout": "roadmap"},
        {"layout": "recommendations", "tag": "recommendations"},
        {"layout": "closing"},
    ]
    target = plan.get("requested_slides") or min(18, 8 + min(len(dives), 5) + 3)
    target = max(8, min(20, int(target)))
    removal_order = ["divider_plan", "divider_analysis", "agenda", "recommendations", "framework"]
    while len(candidates) > target:
        removed = False
        for tag in removal_order:
            index = next((i for i, spec in enumerate(candidates) if spec.get("tag") == tag), None)
            if index is not None:
                candidates.pop(index)
                removed = True
                break
        if removed:
            continue
        deep_indices = [i for i, spec in enumerate(candidates) if spec.get("tag") == "deep"]
        if len(deep_indices) > 2:
            candidates.pop(deep_indices[-1])
            continue
        break
    return candidates


def _slide_title(spec: dict[str, Any], plan: dict[str, Any]) -> str:
    layout = spec["layout"]
    lang = plan["lang"]
    if layout == "summary":
        return tr(lang, "summary")
    if layout == "context":
        return tr(lang, "context")
    if layout == "findings":
        return tr(lang, "findings")
    if layout == "metrics":
        return tr(lang, "kpi_panel")
    if layout == "deep_dive":
        return spec["dive"]["topic"]
    if layout == "framework":
        return f"{tr(lang, 'framework')}: {plan['framework']['name']}"
    if layout == "risks":
        return tr(lang, "risks")
    if layout == "roadmap":
        return tr(lang, "roadmap")
    if layout == "recommendations":
        return tr(lang, "recommendations")
    if layout == "divider":
        return spec.get("title", "")
    return ""


def _agenda_items(slides: Sequence[dict[str, Any]], plan: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for spec in slides:
        if spec["layout"] in {"cover", "agenda", "closing", "divider"}:
            continue
        title = _slide_title(spec, plan)
        if title:
            items.append(title)
    return items[:10]


_KIND_METRIC_HINTS: dict[str, tuple[str, ...]] = {
    "summary": ("ingreso", "revenue", "margen", "margin", "conversión", "conversion"),
    "context": ("crecimiento", "growth", "demanda", "demand", "margen", "margin"),
    "objectives": ("conversión", "conversion", "ingreso", "revenue", "avance", "progress"),
    "metrics": ("conversión", "conversion", "margen", "margin", "ingreso", "revenue"),
    "products": ("producto", "product", "margen", "margin", "unidad", "unit"),
    "regions": ("mercado", "market", "ingreso", "revenue", "cobertura", "coverage"),
    "customers": ("cliente", "customer", "retención", "retention", "ltv", "ticket", "satisfacción", "satisfaction"),
    "competition": ("cuota", "share", "precio", "price", "margen", "margin"),
    "risks": ("exposición", "exposure", "incidente", "incident", "pérdida", "loss"),
    "budget": ("costo", "cost", "margen", "margin", "roi", "presupuesto", "budget"),
    "timeline": ("avance", "progress", "hito", "milestone", "ciclo", "cycle"),
    "team": ("rotación", "turnover", "productividad", "productivity", "cobertura", "coverage"),
    "marketing": ("cac", "roas", "conversión", "conversion", "alcance", "reach"),
    "sales": ("ingreso", "revenue", "conversión", "conversion", "ciclo", "cycle", "pipeline"),
    "channels": ("cac", "roas", "canal", "channel", "contribución", "contribution"),
    "conversion": ("conversión", "conversion", "tasa", "rate", "cvr", "cierre", "close"),
    "pricing": ("precio", "price", "ticket", "margen", "margin", "descuento", "discount"),
    "data": ("calidad", "quality", "cobertura", "coverage", "latencia", "latency"),
    "ai": ("precisión", "precision", "adopción", "adoption", "ahorro", "saving"),
    "innovation": ("ingreso", "revenue", "tiempo", "time", "éxito", "success"),
    "customer_experience": ("nps", "satisfacción", "satisfaction", "retención", "retention", "churn"),
    "framework": ("adopción", "adoption", "avance", "progress", "conversión", "conversion"),
    "research": ("conversión", "conversion", "crecimiento", "growth", "margen", "margin"),
}

_KIND_DEFAULT_METRIC: dict[str, tuple[str, str]] = {
    "conversion": ("Tasa de conversión", "Conversion rate"),
    "channels": ("CAC", "CAC"),
    "pricing": ("Ticket medio", "Average deal size"),
    "customers": ("Retención de clientes", "Customer retention"),
    "products": ("Margen por producto", "Margin per product"),
    "regions": ("Ingreso por mercado", "Revenue per market"),
    "competition": ("Cuota de mercado", "Market share"),
    "data": ("Calidad del dato", "Data quality"),
    "ai": ("Retorno del caso de uso", "Use-case return"),
    "innovation": ("Ingreso de nuevas iniciativas", "New-initiative revenue"),
    "customer_experience": ("NPS", "NPS"),
    "marketing": ("CAC", "CAC"),
    "sales": ("Ingreso por vendedor", "Revenue per rep"),
    "team": ("Rotación del equipo", "Team turnover"),
    "budget": ("ROI del presupuesto", "Budget ROI"),
    "timeline": ("Avance de hitos", "Milestone progress"),
    "risks": ("Exposición residual", "Residual exposure"),
    "framework": ("Adopción del marco", "Framework adoption"),
}

_KIND_RISK: dict[str, tuple[str, str]] = {
    "conversion": ("Embudo con fuga no medida", "Unmeasured funnel leak"),
    "channels": ("Dispersión en demasiados canales", "Spread across too many channels"),
    "pricing": ("Descuentos sin disciplina", "Undisciplined discounting"),
    "customers": ("Segmentos sin validación", "Unvalidated segments"),
    "products": ("Portafolio sin foco", "Unfocused portfolio"),
    "regions": ("Expansión sin demanda validada", "Expansion without validated demand"),
    "competition": ("Diferenciador fácil de imitar", "Easily imitated differentiator"),
    "data": ("Datos incompletos o inconsistentes", "Incomplete or inconsistent data"),
    "ai": ("Caso de uso sin retorno medible", "Use case without measurable return"),
    "innovation": ("Apuestas sin criterio de corte", "Bets without stop criteria"),
    "customer_experience": ("Fricción no medida", "Unmeasured friction"),
    "marketing": ("Atribución incompleta", "Incomplete attribution"),
    "sales": ("Pipeline sin calificar", "Unqualified pipeline"),
    "team": ("Roles sin dueño único", "Roles without a single owner"),
    "budget": ("Presupuesto sin retorno", "Budget without return"),
    "timeline": ("Fechas sin capacidad", "Dates without capacity"),
    "risks": ("Riesgo sin dueño", "Risk without an owner"),
    "framework": ("Marco aplicado en abstracto", "Framework applied in the abstract"),
}


def _metric_for_kind(plan: dict[str, Any], kind: str) -> str:
    """Pick the metric that actually belongs to this analysis topic."""
    es = plan["lang"] == "es"
    hints = _KIND_METRIC_HINTS.get(kind, ())
    metric = _pick_metric(plan.get("metrics") or [], hints)
    if metric:
        return f"{metric['label']} {metric['display']}"
    for kpi in plan.get("kpis") or []:
        label = _strip_accents(str(kpi).lower())
        if any(_strip_accents(hint) in label for hint in hints):
            return str(kpi)
    default = _KIND_DEFAULT_METRIC.get(kind)
    if default:
        return default[0] if es else default[1]
    if plan.get("kpis"):
        return str(plan["kpis"][0])
    return "Avance" if es else "Progress"


def _implication(plan: dict[str, Any], kind: str) -> tuple[str, str, str]:
    es = plan["lang"] == "es"
    decisions = {
        "summary": ("Aprobar el enfoque y la primera fase." if es else "Approve the approach and the first phase."),
        "context": ("Validar el contexto con datos internos." if es else "Validate the context with internal data."),
        "objectives": ("Convertir los objetivos en OKR con dueño." if es else "Turn objectives into owned OKRs."),
        "metrics": ("Instrumentar y revisar cada semana." if es else "Instrument and review every week."),
        "products": ("Priorizar el portafolio por contribución." if es else "Prioritize the portfolio by contribution."),
        "regions": ("Elegir 1-2 mercados y probar." if es else "Choose 1-2 markets and test."),
        "customers": ("Validar segmentos con entrevistas." if es else "Validate segments through interviews."),
        "competition": ("Definir un diferenciador defendible." if es else "Define a defensible differentiator."),
        "risks": ("Asignar dueño y plan de mitigación." if es else "Assign an owner and a mitigation plan."),
        "budget": ("Aprobar presupuesto por fases." if es else "Approve budget in phases."),
        "timeline": ("Reservar capacidad y fechas." if es else "Reserve capacity and dates."),
        "team": ("Asignar un dueño único por resultado." if es else "Assign one owner per result."),
        "marketing": ("Concentrar canales y medir incremento." if es else "Concentrate channels and measure lift."),
        "sales": ("Calificar pipeline y revisar conversión." if es else "Qualify the pipeline and review conversion."),
        "channels": ("Sostener 2-3 canales con evidencia y podar el resto." if es else "Sustain 2-3 channels with evidence and prune the rest."),
        "conversion": ("Atacar la mayor caída del embudo con un experimento." if es else "Fix the biggest funnel drop with one experiment."),
        "pricing": ("Probar precio en un segmento acotado antes de escalar." if es else "Test price in a bounded segment before scaling."),
        "data": ("Definir una métrica, un dueño y una fuente por decisión." if es else "Define one metric, owner and source per decision."),
        "ai": ("Elegir un caso de uso medible y revisar el retorno." if es else "Choose one measurable use case and review the return."),
        "innovation": ("Separar apuestas y fijar criterios de escala o corte." if es else "Separate bets and set scale-or-stop criteria."),
        "customer_experience": ("Eliminar fricción antes de añadir funciones." if es else "Remove friction before adding features."),
        "framework": ("Aplicar el marco en un taller de 90 minutos." if es else "Apply the framework in a 90-minute workshop."),
        "research": ("Convertir hallazgos en hipótesis verificables." if es else "Turn findings into testable hypotheses."),
        "conclusions": ("Aprobar las tres decisiones." if es else "Approve the three decisions."),
        "closing": ("Cerrar con dueño y fecha." if es else "Close with an owner and a date."),
        "plan": ("Empezar por los primeros 30 días." if es else "Start with the first 30 days."),
    }
    decision = decisions.get(kind, "Definir dueño, métrica y fecha." if es else "Define owner, metric and date.")
    metric = _metric_for_kind(plan, kind)
    risk_pair = _KIND_RISK.get(kind)
    if risk_pair:
        risk = risk_pair[0] if es else risk_pair[1]
    elif plan["risks"]:
        risk = plan["risks"][0]["risk"]
    else:
        risk = "Ejecución sin foco" if es else "Execution without focus"
    return decision, metric, risk


def _render_cover(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    W, Hh = 13.333, 7.5
    add_rect, add_text, add_chip = H["add_rect"], H["add_text"], H["add_chip"]
    add_rect(slide, _in(0), _in(0), _in(W), _in(Hh), theme["bg"])
    style = theme.get("cover", "band")
    if style == "orbit":
        add_rect(slide, _in(9.2), _in(-1.2), _in(5.4), _in(5.4), None, MSO_SHAPE.OVAL, theme["accent"], 1.2)
        add_rect(slide, _in(10.4), _in(0.6), _in(3.8), _in(3.8), None, MSO_SHAPE.OVAL, theme["accent2"], 0.8)
        add_rect(slide, _in(11.4), _in(4.5), _in(0.8), _in(0.8), theme["accent2"], MSO_SHAPE.OVAL)
    elif style == "split":
        add_rect(slide, _in(8.75), _in(0), _in(4.58), _in(Hh), theme["panel"])
        add_rect(slide, _in(8.75), _in(0), _in(0.06), _in(Hh), theme["accent"])
        for i, yy in enumerate((1.3, 2.0, 2.7)):
            add_rect(slide, _in(9.35), _in(yy), _in(2.7 - i * 0.4), _in(0.045), theme["accent2"])
    elif style == "band":
        add_rect(slide, _in(0), _in(6.1), _in(W), _in(1.4), theme["panel"])
        add_rect(slide, _in(0), _in(6.1), _in(W), _in(0.05), theme["accent"])
    else:  # grid
        line = _blend(theme["bg"], (255, 255, 255), 0.12) if theme["dark"] else _blend(theme["bg"], (18, 35, 55), 0.10)
        for i in range(1, 7):
            add_rect(slide, _in(i * 1.9), _in(0), _in(0.012), _in(Hh), line)
        for i in range(1, 5):
            add_rect(slide, _in(0), _in(i * 1.5), _in(W), _in(0.012), line)
        add_rect(slide, _in(9.0), _in(0.8), _in(3.3), _in(0.06), theme["accent"])

    kicker = f"{tr(plan['lang'], 'executive_report').upper()}  ·  {plan['domain_label'].upper()}"
    kicker_box = add_text(slide, _in(0.75), _in(1.55), _in(10.8), _in(0.3), kicker, 9, theme["accent2"], bold=True)
    title_width = 7.35 if style == "split" else 11.6
    size = 42 if len(plan["title"]) <= 45 else 34 if len(plan["title"]) <= 72 else 29
    title_box = add_text(slide, _in(0.75), _in(1.98), _in(title_width), _in(1.85), plan["title"], size,
                         theme["text"], bold=True, spacing=0.95)
    add_rect(slide, _in(0.77), _in(3.9), _in(1.15), _in(0.06), theme["accent"])
    subtitle = ("Análisis, hallazgos y plan de acción" if plan["lang"] == "es" else "Analysis, findings and action plan")
    subtitle_box = add_text(slide, _in(0.75), _in(4.14), _in(title_width), _in(0.5), subtitle, 17,
                            theme["muted"])
    date_box = add_text(slide, _in(0.75), _in(6.62), _in(5.8), _in(0.3),
                        f"{tr(plan['lang'], 'prepared_by')}  ·  {plan['generated_at']}", 9, theme["muted"])
    add_text(slide, _in(W - 3.4), _in(6.62), _in(2.7), _in(0.3), tr(plan["lang"], "confidential").upper(),
             8, theme["muted"], align=PP_ALIGN.RIGHT)

    chips: list[Any] = []
    if plan["metrics"]:
        max_chips = 2 if style == "split" else 4
        count = min(max_chips, len(plan["metrics"]))
        gap = 0.18
        total_w = 7.55 if style == "split" else 11.85
        chip_w = (total_w - gap * (count - 1)) / count if count else 2.45
        for i, metric in enumerate(plan["metrics"][:count]):
            x = 0.75 + i * (chip_w + gap)
            add_chip(slide, _in(x), _in(5.0), _in(chip_w), _in(0.82), "", theme["panel"] if theme["dark"] else theme["card"], theme["text"])
            add_text(slide, _in(x + 0.16), _in(5.08), _in(chip_w - 0.3), _in(0.22), _short(metric["label"], 26), 8, theme["muted"])
            value_box = add_text(slide, _in(x + 0.16), _in(5.31), _in(chip_w - 0.3), _in(0.38), _short(metric["display"], 20), 12.5,
                                 theme["accent2"], bold=True)
            chips.append(value_box)

    animations = [(kicker_box, "fade", 0), (title_box, "wipe", 100), (subtitle_box, "fade", 480),
                  (date_box, "fade", 900)]
    animations += [(chip, "fade", 650 + i * 130) for i, chip in enumerate(chips)]
    _add_animations(slide, animations, "fade")
    slide.notes_slide.notes_text_frame.text = (
        f"Propósito: presentar {plan['title']} con una narrativa ejecutiva. "
        f"Tema visual: {theme['name']}. Dominio: {plan['domain_label']}."
    )
    return slide


def _render_agenda(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int,
                   items: Sequence[str]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "agenda"), tr(plan["lang"], "executive_report"), page, total, plan["domain_label"])
    add_rect = H["add_rect"]
    half = math.ceil(len(items) / 2) if items else 0
    rows = max(half, len(items) - half) if items else 1
    row_gap = 0.72
    block_h = rows * row_gap
    top = 1.55 + max(0.0, (5.2 - block_h) / 2)
    if items:
        add_rect(slide, _in(6.52), _in(top - 0.05), _in(0.015), _in(block_h - 0.12), theme["border"])
    boxes: list[Any] = []
    for index, item in enumerate(items):
        column = 0 if index < half else 1
        row = index if column == 0 else index - half
        x = 0.9 + column * 6.05
        y = top + row * row_gap
        number = H["add_text"](slide, _in(x), _in(y), _in(0.5), _in(0.4), f"{index + 1:02d}", 15,
                               theme["accent"], bold=True)
        text = H["add_text"](slide, _in(x + 0.55), _in(y), _in(4.7), _in(0.45), item, 13.5,
                             theme["content_text"], spacing=0.95)
        boxes.extend([number, text])
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 100 + i * 55) for i, box in enumerate(boxes)], "push")
    slide.notes_slide.notes_text_frame.text = "Recorrido del documento: contexto, evidencia, análisis y plan."
    return slide


def _render_summary(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "summary"), tr(plan["lang"], "executive_report"), page, total, plan["domain_label"])
    summary_box = H["add_text"](slide, _in(0.7), _in(1.45), _in(7.15), _in(1.75), plan["executive_summary"], 13.5,
                                theme["content_text"], spacing=1.12)
    H["add_text"](slide, _in(0.7), _in(3.22), _in(4.0), _in(0.25), tr(plan["lang"], "key_messages").upper(), 8.5,
                  theme["accent"], bold=True)
    boxes: list[Any] = []
    for i, message in enumerate(plan["key_messages"]):
        y = 3.55 + i * 0.9
        H["add_rect"](slide, _in(0.7), _in(y + 0.03), _in(0.3), _in(0.3), theme["accent"], MSO_SHAPE.ROUNDED_RECTANGLE)
        H["add_text"](slide, _in(0.7), _in(y + 0.03), _in(0.3), _in(0.3), str(i + 1), 10, (255, 255, 255),
                      bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        boxes.append(H["add_text"](slide, _in(1.15), _in(y), _in(6.55), _in(0.8), message, 12.2, theme["content_text"], spacing=1.0))

    panel_x, panel_y, panel_w, panel_h = 8.15, 1.45, 4.45, 5.0
    H["add_rect"](slide, _in(panel_x), _in(panel_y), _in(panel_w), _in(panel_h), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
    H["add_rect"](slide, _in(panel_x), _in(panel_y), _in(panel_w), _in(0.07), theme["accent"])
    H["add_text"](slide, _in(panel_x + 0.25), _in(panel_y + 0.22), _in(panel_w - 0.5), _in(0.3),
                  tr(plan["lang"], "baseline") if plan["metrics"] else tr(plan["lang"], "recommended_kpis"), 10,
                  theme["accent"], bold=True)
    if plan["metrics"]:
        for i, metric in enumerate(plan["metrics"][:4]):
            y = panel_y + 0.7 + i * 1.02
            H["add_text"](slide, _in(panel_x + 0.25), _in(y), _in(panel_w - 0.5), _in(0.24), _short(metric["label"], 40), 9,
                          theme["content_muted"])
            H["add_text"](slide, _in(panel_x + 0.25), _in(y + 0.24), _in(panel_w - 0.5), _in(0.42), _short(metric["display"], 24),
                          16, theme["content_text"], bold=True)
            if i < 3:
                H["add_rect"](slide, _in(panel_x + 0.25), _in(y + 0.78), _in(panel_w - 0.5), _in(0.008), theme["border"])
    else:
        for i, kpi in enumerate(plan["kpis"][:4]):
            y = panel_y + 0.7 + i * 0.95
            H["add_text"](slide, _in(panel_x + 0.25), _in(y), _in(panel_w - 0.5), _in(0.55), f"•  {kpi}", 11.5,
                          theme["content_text"], spacing=1.0)

    H["add_text"](slide, _in(0.7), _in(6.62), _in(7.3), _in(0.3),
                  tr(plan["lang"], "data_from_request") if plan["metrics"] else tr(plan["lang"], "needs_data"),
                  8, theme["content_muted"])
    _add_animations(slide, [(title_box, "wipe", 0), (summary_box, "fade", 120)] +
                    [(box, "fade", 280 + i * 110) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Resumen: línea base, apuesta y ritmo de ejecución. No añadir iniciativas sin dueño."
    return slide


def _render_context(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "context"), tr(plan["lang"], "executive_report"), page, total, plan["domain_label"])
    callout = plan["context"][3] if len(plan["context"]) > 3 else (
        f"Foco: {_pick(plan['domain']['focus'], plan['lang'])}."
    )
    panels = [(str(plan["context"][i]), f"0{i + 1}", False) for i in range(3)]
    panels.append((callout, tr(plan["lang"], "implication").upper(), True))
    boxes: list[Any] = []
    for i, (paragraph, label, is_callout) in enumerate(panels):
        x = 0.7 + (i % 2) * 6.08
        y = 1.45 + (i // 2) * 2.4
        H["add_rect"](slide, _in(x), _in(y), _in(5.85), _in(2.18), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        H["add_rect"](slide, _in(x), _in(y), _in(5.85), _in(0.065), theme["accent"])
        H["add_text"](slide, _in(x + 0.24), _in(y + 0.18), _in(4.6), _in(0.24), label, 8.5,
                      theme["accent"], bold=True)
        boxes.append(H["add_text"](slide, _in(x + 0.24), _in(y + 0.52), _in(5.35), _in(1.5), paragraph, 12.2,
                                   theme["content_text"], spacing=1.08))
    H["add_text"](slide, _in(0.7), _in(6.35), _in(11.9), _in(0.3),
                  tr(plan["lang"], "data_from_request") + "  ·  " + tr(plan["lang"], "assumptions_text")[:96] + "…",
                  7.8, theme["content_muted"])
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 120 + i * 120) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Contexto: qué está cambiando, por qué importa y cuál es la implicación para la decisión."
    return slide


def _render_findings(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "findings"), tr(plan["lang"], "analysis"), page, total, plan["domain_label"])
    boxes: list[Any] = []
    for i, item in enumerate(plan["findings"][:3]):
        x = 0.7 + i * 4.05
        H["add_rect"](slide, _in(x), _in(1.45), _in(3.85), _in(3.4), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        H["add_rect"](slide, _in(x), _in(1.45), _in(3.85), _in(0.065), theme["accent"])
        H["add_chip"](slide, _in(x + 0.22), _in(1.66), _in(1.75), _in(0.28), _short(item["source"], 22), theme["accent"],
                      (255, 255, 255), size=7.5)
        H["add_text"](slide, _in(x + 0.22), _in(2.08), _in(3.4), _in(0.85), item["title"], 12.4, theme["content_text"], bold=True, spacing=1.0)
        boxes.append(H["add_text"](slide, _in(x + 0.22), _in(2.98), _in(3.4), _in(1.7), item["snippet"], 9.8,
                                   theme["content_muted"], spacing=1.1))
    implication = (
        plan["key_messages"][1] if len(plan.get("key_messages") or []) > 1
        else ("Contrastar estos hallazgos con datos propios antes de asignar presupuesto."
              if plan["lang"] == "es"
              else "Contrast these findings with internal data before allocating budget.")
    )
    H["add_rect"](slide, _in(0.7), _in(5.05), _in(11.93), _in(0.95), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
    H["add_rect"](slide, _in(0.7), _in(5.05), _in(0.08), _in(0.95), theme["accent"])
    H["add_text"](slide, _in(0.95), _in(5.18), _in(3.0), _in(0.22), tr(plan["lang"], "implication").upper(), 8.5,
                  theme["accent"], bold=True)
    implication_box = H["add_text"](slide, _in(0.95), _in(5.42), _in(11.35), _in(0.45), implication, 11,
                                    theme["content_text"], spacing=1.0)
    boxes.append(implication_box)
    if plan["sources"]:
        names: list[str] = []
        for source in plan["sources"][:3]:
            label = str(source.get("source") or "").strip()
            if not label:
                label = urlparse(str(source.get("url") or "")).netloc.replace("www.", "")
            if label and label not in names:
                names.append(label)
        listed = ", ".join(names[:3]) or plan["generated_at"]
        note = f"{tr(plan['lang'], 'sources_note')}: {listed} · {plan['generated_at']}."
    else:
        note = tr(plan["lang"], "no_external_sources")
    H["add_text"](slide, _in(0.7), _in(6.25), _in(11.9), _in(0.45), note, 8.2, theme["content_muted"], spacing=1.0)
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 150 + i * 150) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Hallazgos: señales externas y tendencias. Distinguir evidencia de interpretación."
    return slide


def _add_native_chart(slide, x, y, w, h, metrics: Sequence[dict], theme: dict[str, Any], lang: str) -> bool:
    try:
        from pptx.chart.data import CategoryChartData  # type: ignore
        from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION  # type: ignore
        from pptx.util import Pt  # type: ignore

        data = CategoryChartData()
        label_limit = 24 if len(metrics) <= 3 else 16
        data.categories = [_short(m["label"], label_limit) for m in metrics]
        data.add_series(tr(lang, "value"), [float(m.get("value") or 0) for m in metrics])
        chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, _in(x), _in(y), _in(w), _in(h), data).chart
        chart.has_legend = False
        chart.has_title = False
        chart.font.name = "Segoe UI"
        chart.font.size = Pt(9)
        plot = chart.plots[0]
        plot.gap_width = 55
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(8.5)
        plot.data_labels.font.color.rgb = _rgb(theme["content_text"])
        plot.data_labels.number_format = "#,##0"
        plot.data_labels.number_format_is_linked = False
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        series = plot.series[0]
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = _rgb(theme["accent"])
        series.format.line.fill.background()
        chart.value_axis.has_major_gridlines = True
        chart.value_axis.major_gridlines.format.line.color.rgb = _rgb(theme["border"])
        chart.value_axis.tick_labels.font.size = Pt(8)
        chart.value_axis.tick_labels.font.color.rgb = _rgb(theme["content_muted"])
        chart.category_axis.tick_labels.font.size = Pt(8)
        chart.category_axis.tick_labels.font.color.rgb = _rgb(theme["content_muted"])
        chart.category_axis.format.line.color.rgb = _rgb(theme["border"])
        chart.value_axis.format.line.fill.background()
        # Force the chart locale so thousands separators match the document
        # language (187 500 in Spanish, 187,500 in English).
        try:
            from pptx.oxml.ns import qn as _qn  # type: ignore
            from pptx.oxml.xmlchemy import OxmlElement  # type: ignore
            lang_el = chart._chartSpace.find(_qn("c:lang"))
            if lang_el is None:
                lang_el = OxmlElement("c:lang")
                chart_el = chart._chartSpace.find(_qn("c:chart"))
                if chart_el is not None:
                    chart_el.addprevious(lang_el)
                else:
                    chart._chartSpace.append(lang_el)
            lang_el.set("val", "es-ES" if lang == "es" else "en-US")
        except Exception:
            pass
        return True
    except Exception:
        return False


def _metrics_table(slide, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], x: float, y: float, w: float, h: float):
    add_rect, add_text = H["add_rect"], H["add_text"]
    add_rect(slide, _in(x), _in(y), _in(w), _in(h), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
    add_text(slide, _in(x + 0.22), _in(y + 0.16), _in(w - 0.44), _in(0.24), tr(plan["lang"], "metric").upper(), 8,
             theme["content_muted"], bold=True)
    add_text(slide, _in(x + w - 2.1), _in(y + 0.16), _in(1.85), _in(0.24), tr(plan["lang"], "value").upper(), 8,
             theme["content_muted"], bold=True, align=PP_ALIGN.RIGHT)
    rows = plan["metrics"][:6]
    gap = min(0.42, (h - 0.55) / max(1, len(rows)))
    for i, metric in enumerate(rows):
        yy = y + 0.55 + i * gap
        add_text(slide, _in(x + 0.22), _in(yy), _in(w - 2.3), _in(gap), _short(metric["label"], 42), 9.5,
                 theme["content_text"])
        add_text(slide, _in(x + w - 2.1), _in(yy), _in(1.85), _in(gap), _short(metric["display"], 22), 9.5,
                 theme["content_text"], bold=True, align=PP_ALIGN.RIGHT)
        add_rect(slide, _in(x + 0.22), _in(yy + gap - 0.01), _in(w - 0.44), _in(0.006), theme["border"])


def _render_metrics(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "kpi_panel"), tr(plan["lang"], "analysis"), page, total, plan["domain_label"])
    add_rect, add_text, add_metric_card = H["add_rect"], H["add_text"], H["add_metric_card"]
    boxes: list[Any] = []
    metrics = plan["metrics"]
    chart_metrics = _chart_metrics(metrics)

    if metrics:
        for i, metric in enumerate(metrics[:4]):
            x = 0.7 + i * 3.12
            add_metric_card(slide, _in(x), _in(1.42), _in(2.92), _in(1.55), metric)
        chart_note = (
            "Solo métricas comparables: misma unidad y escala."
            if plan["lang"] == "es"
            else "Comparable metrics only: same unit and scale."
        )
        if chart_metrics and len(chart_metrics) >= 2:
            ok = _add_native_chart(slide, 0.7, 3.22, 7.75, 3.18, chart_metrics, theme, plan["lang"])
            if not ok:
                _metrics_table(slide, plan, theme, H, 0.7, 3.22, 7.75, 3.12)
            else:
                add_text(slide, _in(0.72), _in(6.5), _in(7.7), _in(0.24),
                         chart_note, 7.8, theme["content_muted"], spacing=1.0)
        else:
            _metrics_table(slide, plan, theme, H, 0.7, 3.22, 7.75, 3.12)
            add_text(slide, _in(0.72), _in(6.5), _in(7.7), _in(0.24),
                     ("Unidades distintas: se muestran por separado, sin suma ni promedio."
                      if plan["lang"] == "es"
                      else "Mixed units: shown separately, without sum or average."),
                     7.8, theme["content_muted"], spacing=1.0)

        # Reading panel
        px, py, pw, ph = 8.7, 3.22, 3.95, 3.35
        add_rect(slide, _in(px), _in(py), _in(pw), _in(ph), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_rect(slide, _in(px), _in(py), _in(pw), _in(0.065), theme["accent"])
        add_text(slide, _in(px + 0.22), _in(py + 0.18), _in(pw - 0.44), _in(0.25), tr(plan["lang"], "reading").upper(), 8.5,
                 theme["accent"], bold=True)
        readings: list[str] = []
        if chart_metrics:
            values = [float(m["value"]) for m in chart_metrics]
            top = max(chart_metrics, key=lambda m: float(m["value"]))
            low = min(chart_metrics, key=lambda m: float(m["value"]))
            avg = sum(values) / len(values)
            positive = [abs(v) for v in values if v]
            spread = (max(positive) / min(positive)) if positive and min(positive) > 0 else 99
            readings.append((f"Mayor valor: {top['label']} ({top['display']})." if plan["lang"] == "es"
                             else f"Highest: {top['label']} ({top['display']})."))
            if spread <= 2.5:
                readings.append((f"Promedio del grupo: {_fmt_value(avg, chart_metrics[0].get('unit', ''), plan['lang'])}." if plan["lang"] == "es"
                                 else f"Group average: {_fmt_value(avg, chart_metrics[0].get('unit', ''), plan['lang'])}."))
            else:
                readings.append((f"Menor valor: {low['label']} ({low['display']})." if plan["lang"] == "es"
                                 else f"Lowest: {low['label']} ({low['display']})."))
                readings.append((f"Escala: el mayor valor es {spread:.0f}x el menor; no se usa promedio." if plan["lang"] == "es"
                                 else f"Scale: the highest value is {spread:.0f}x the lowest; no average is used."))
        else:
            readings.append(("Unidades distintas: no se comparan en un solo eje." if plan["lang"] == "es"
                             else "Mixed units: they are not compared on a single axis."))
            readings.append((f"Foco: {_pick(plan['domain']['focus'], plan['lang'])}." if plan["lang"] == "es"
                             else f"Focus: {_pick(plan['domain']['focus'], plan['lang'])}."))
        readings.append(("Validar las cifras antes de compartir." if plan["lang"] == "es"
                         else "Validate the figures before sharing."))
        y = py + 0.55
        for reading in readings[:3]:
            boxes.append(add_text(slide, _in(px + 0.22), _in(y), _in(pw - 0.44), _in(0.75), f"•  {reading}", 10.2,
                                  theme["content_text"], spacing=1.05))
            y += 0.82
    else:
        for i, kpi in enumerate(plan["kpis"][:4]):
            x = 0.7 + i * 3.12
            add_rect(slide, _in(x), _in(1.42), _in(2.92), _in(1.55), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
            add_rect(slide, _in(x), _in(1.42), _in(2.92), _in(0.065), theme["accent"])
            add_text(slide, _in(x + 0.22), _in(1.62), _in(2.5), _in(0.22), tr(plan["lang"], "recommended_kpis").upper(), 7.5,
                     theme["content_muted"], bold=True)
            add_text(slide, _in(x + 0.22), _in(1.95), _in(2.5), _in(0.8), kpi, 13, theme["content_text"], bold=True, spacing=1.0)
        px, py, pw, ph = 0.7, 3.22, 11.93, 3.35
        add_rect(slide, _in(px), _in(py), _in(pw), _in(ph), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_text(slide, _in(px + 0.25), _in(py + 0.2), _in(pw - 0.5), _in(0.3), tr(plan["lang"], "recommended_kpis"), 10,
                 theme["accent"], bold=True)
        text = (f"No se recibieron métricas. Se propone medir {', '.join(plan['kpis'][:4])}. "
                "La línea base se completa con datos reales antes de decidir." if plan["lang"] == "es"
                else f"No metrics were provided. The proposal is to measure {', '.join(plan['kpis'][:4])}. "
                     "The baseline is completed with real data before deciding.")
        boxes.append(add_text(slide, _in(px + 0.25), _in(py + 0.65), _in(pw - 0.5), _in(1.0), text, 12, theme["content_text"], spacing=1.1))
        add_text(slide, _in(px + 0.25), _in(py + 2.55), _in(pw - 0.5), _in(0.45), tr(plan["lang"], "needs_data"), 8.5,
                 theme["content_muted"])

    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 120 + i * 80) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Panel de métricas: leer volumen, precio y margen por separado; no mezclar unidades en un solo eje."
    return slide


def _render_divider(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int,
                    spec: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect, add_text = H["add_rect"], H["add_text"]
    add_rect(slide, _in(0), _in(0), _in(13.333), _in(7.5), theme["bg"])
    add_rect(slide, _in(8.9), _in(-1.0), _in(5.2), _in(5.2), None, MSO_SHAPE.OVAL, theme["accent"], 1.0)
    add_rect(slide, _in(10.3), _in(4.9), _in(2.2), _in(2.2), None, MSO_SHAPE.OVAL, theme["accent2"], 0.8)
    number = add_text(slide, _in(0.75), _in(1.35), _in(3.0), _in(1.3), spec["number"], 82, theme["accent2"], bold=True)
    title = add_text(slide, _in(0.78), _in(3.0), _in(9.0), _in(0.8), spec["title"], 36, theme["text"], bold=True)
    subtitle = add_text(slide, _in(0.78), _in(3.95), _in(9.0), _in(0.5), spec["subtitle"], 15, theme["muted"])
    add_rect(slide, _in(0.8), _in(4.7), _in(1.8), _in(0.06), theme["accent"])
    add_text(slide, _in(0.78), _in(6.62), _in(7.0), _in(0.3), "Orunex  ·  " + plan["domain_label"], 9, theme["muted"])
    _add_animations(slide, [(number, "fade", 0), (title, "wipe", 120), (subtitle, "fade", 500)], "fade")
    slide.notes_slide.notes_text_frame.text = f"Sección {spec['number']}: {spec['title']}."
    return slide


def _render_deep_dive(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int,
                      spec: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    dive = spec["dive"]
    title_box = H["add_header"](slide, dive["topic"], tr(plan["lang"], "analysis"), page, total, plan["domain_label"])
    add_rect, add_text, add_bullets = H["add_rect"], H["add_text"], H["add_bullets"]
    panel_left = spec["index"] % 2 == 1
    panel_x = 0.7 if panel_left else 8.3
    bullets_x = 5.4 if panel_left else 0.7
    bullets_w = 7.1

    boxes: list[Any] = []
    add_bullets(slide, _in(bullets_x), _in(1.55), _in(bullets_w), dive["bullets"], theme["content_text"], theme["accent"],
                size=14.5, gap=1.14, max_items=4, animate=boxes)

    decision, metric, risk = _implication(plan, dive["kind"])
    add_rect(slide, _in(panel_x), _in(1.45), _in(4.3), _in(4.85), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
    add_rect(slide, _in(panel_x), _in(1.45), _in(4.3), _in(0.07), theme["accent"])
    add_text(slide, _in(panel_x + 0.25), _in(1.65), _in(3.8), _in(0.25), tr(plan["lang"], "implication").upper(), 8.5,
             theme["accent"], bold=True)
    add_text(slide, _in(panel_x + 0.25), _in(1.98), _in(3.8), _in(0.85), decision, 13, theme["content_text"], bold=True, spacing=1.02)
    add_rect(slide, _in(panel_x + 0.25), _in(3.02), _in(3.8), _in(0.008), theme["border"])
    add_text(slide, _in(panel_x + 0.25), _in(3.2), _in(3.8), _in(0.22), tr(plan["lang"], "metric").upper(), 8,
             theme["content_muted"], bold=True)
    add_text(slide, _in(panel_x + 0.25), _in(3.45), _in(3.8), _in(0.55), metric, 10.5, theme["content_text"], spacing=1.0)
    add_text(slide, _in(panel_x + 0.25), _in(4.2), _in(3.8), _in(0.22), tr(plan["lang"], "risk").upper(), 8,
             theme["content_muted"], bold=True)
    add_text(slide, _in(panel_x + 0.25), _in(4.45), _in(3.8), _in(0.65), risk, 10, theme["content_muted"], spacing=1.0)
    evidence = (
        f"{tr(plan['lang'], 'data_from_request')} · {_metric_for_kind(plan, dive['kind'])}"
        if plan["metrics"]
        else tr(plan["lang"], "internal_framework")
    )
    add_text(slide, _in(panel_x + 0.25), _in(5.22), _in(3.8), _in(0.22), tr(plan["lang"], "evidence").upper(), 8,
             theme["content_muted"], bold=True)
    add_text(slide, _in(panel_x + 0.25), _in(5.47), _in(3.8), _in(0.7), evidence, 9.5, theme["content_text"], spacing=1.0)

    next_box = add_text(slide, _in(0.95), _in(6.5), _in(11.45), _in(0.45),
                        f"{tr(plan['lang'], 'next_step').upper()}: {_short(plan['actions']['30'][0], 120)}", 9.5,
                        theme["content_text"], bold=True, anchor=MSO_ANCHOR.MIDDLE)
    add_rect(slide, _in(0.7), _in(6.52), _in(0.07), _in(0.38), theme["accent"])
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 100 + i * 110) for i, box in enumerate(boxes)] +
                    [(next_box, "fade", 700)], "fade")
    slide.notes_slide.notes_text_frame.text = f"{dive['topic']}: {decision} Métrica: {metric}. Riesgo: {risk}."
    return slide


def _render_framework(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    framework = plan["framework"]
    title_box = H["add_header"](slide, f"{tr(plan['lang'], 'framework')}: {framework['name']}",
                                tr(plan["lang"], "analysis"), page, total, plan["domain_label"])
    add_rect, add_text = H["add_rect"], H["add_text"]
    add_text(slide, _in(0.7), _in(1.35), _in(11.9), _in(0.4), framework["desc"], 12, theme["content_muted"])
    steps = framework["steps"][:4]
    n = len(steps)
    gap = 0.2
    card_w = (11.9 - gap * (n - 1)) / n
    boxes: list[Any] = []
    for i, step in enumerate(steps):
        x = 0.7 + i * (card_w + gap)
        add_rect(slide, _in(x), _in(2.0), _in(card_w), _in(2.95), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_rect(slide, _in(x), _in(2.0), _in(card_w), _in(0.07), theme["accent"])
        add_rect(slide, _in(x + 0.24), _in(2.28), _in(0.42), _in(0.42), theme["accent"], MSO_SHAPE.OVAL)
        add_text(slide, _in(x + 0.24), _in(2.28), _in(0.42), _in(0.42), str(i + 1), 11, (255, 255, 255), bold=True,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        boxes.append(add_text(slide, _in(x + 0.24), _in(2.92), _in(card_w - 0.48), _in(1.85), step, 13,
                              theme["content_text"], spacing=1.08))
    add_rect(slide, _in(0.7), _in(5.3), _in(11.93), _in(0.85), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
    add_rect(slide, _in(0.7), _in(5.3), _in(0.08), _in(0.85), theme["accent"])
    application = (f"Aplicación: usar {framework['name']} para ordenar {plan['title']} en un taller con dueño y fecha."
                   if plan["lang"] == "es" else
                   f"Application: use {framework['name']} to structure {plan['title']} in a workshop with an owner and a date.")
    app_box = add_text(slide, _in(0.95), _in(5.48), _in(11.35), _in(0.5), application, 10.8, theme["content_text"])
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 120 + i * 120) for i, box in enumerate(boxes)] +
                    [(app_box, "fade", 650)], "fade")
    slide.notes_slide.notes_text_frame.text = f"Marco {framework['name']}: {framework['desc']} Aplicarlo con un caso real, no en abstracto."
    return slide


def _render_risks(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "risks"), tr(plan["lang"], "plan"), page, total, plan["domain_label"])
    add_rect, add_text, add_chip = H["add_rect"], H["add_text"], H["add_chip"]
    add_text(slide, _in(0.7), _in(1.35), _in(4.0), _in(0.22), tr(plan["lang"], "risk").upper(), 8, theme["content_muted"], bold=True)
    add_text(slide, _in(4.95), _in(1.35), _in(1.2), _in(0.22), tr(plan["lang"], "impact").upper(), 8, theme["content_muted"], bold=True)
    add_text(slide, _in(6.35), _in(1.35), _in(6.0), _in(0.22), tr(plan["lang"], "mitigation").upper(), 8, theme["content_muted"], bold=True)
    rows = plan["risks"][:4]
    count = max(1, len(rows))
    row_h = min(1.55, 4.55 / count)
    step = min(1.72, (4.75 - row_h) / max(1, count - 1)) if count > 1 else 0
    boxes: list[Any] = []
    for i, item in enumerate(rows):
        y = 1.75 + i * step
        fill = theme["card"] if i % 2 == 0 else theme["content_bg"]
        add_rect(slide, _in(0.7), _in(y), _in(11.93), _in(row_h), fill, MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_rect(slide, _in(0.7), _in(y), _in(0.06), _in(row_h), theme["accent"])
        text_h = row_h - 0.2
        boxes.append(add_text(slide, _in(0.95), _in(y + 0.1), _in(3.85), _in(text_h), item["risk"], 11.4,
                              theme["content_text"], bold=True, spacing=1.0, anchor=MSO_ANCHOR.MIDDLE))
        level = item["level"]
        level_color = theme["accent"] if level in {"Alto", "High"} else (theme["accent2"] if level in {"Medio", "Medium"} else theme["muted"])
        add_chip(slide, _in(4.95), _in(y + row_h / 2 - 0.16), _in(1.0), _in(0.32), level, level_color, (255, 255, 255), size=8)
        boxes.append(add_text(slide, _in(6.35), _in(y + 0.1), _in(6.0), _in(text_h), item["mitigation"], 10.6,
                              theme["content_text"], spacing=1.0, anchor=MSO_ANCHOR.MIDDLE))
    add_text(slide, _in(0.7), _in(6.35), _in(11.9), _in(0.35),
             "Revisar los riesgos en la misma cadencia que los resultados." if plan["lang"] == "es"
             else "Review risks on the same cadence as results.", 9, theme["content_muted"])
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 100 + i * 90) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Riesgos: nivel, mitigación y dueño. No se acepta un riesgo sin responsable."
    return slide


def _render_roadmap(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "roadmap"), tr(plan["lang"], "plan"), page, total, plan["domain_label"])
    add_rect, add_text = H["add_rect"], H["add_text"]
    add_rect(slide, _in(1.0), _in(2.08), _in(11.3), _in(0.025), theme["border"])
    labels = [("30 días" if plan["lang"] == "es" else "30 days", 2.0),
              ("60 días" if plan["lang"] == "es" else "60 days", 6.55),
              ("90 días" if plan["lang"] == "es" else "90 days", 11.1)]
    boxes: list[Any] = []
    for label, cx in labels:
        add_rect(slide, _in(cx - 0.09), _in(1.99), _in(0.18), _in(0.18), theme["accent"], MSO_SHAPE.OVAL)
        boxes.append(add_text(slide, _in(cx - 0.65), _in(1.62), _in(1.3), _in(0.25), label, 10, theme["accent"], bold=True,
                              align=PP_ALIGN.CENTER))
    for i, horizon in enumerate(("30", "60", "90")):
        x = 0.7 + i * 4.1
        add_rect(slide, _in(x), _in(2.45), _in(3.75), _in(3.65), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_rect(slide, _in(x), _in(2.45), _in(3.75), _in(0.07), theme["accent"])
        add_text(slide, _in(x + 0.24), _in(2.62), _in(3.3), _in(0.3), labels[i][0].upper(), 10, theme["accent"], bold=True)
        yy = 3.05
        for action in plan["actions"][horizon][:3]:
            add_rect(slide, _in(x + 0.26), _in(yy + 0.11), _in(0.08), _in(0.08), theme["accent2"], MSO_SHAPE.OVAL)
            boxes.append(add_text(slide, _in(x + 0.48), _in(yy), _in(3.0), _in(0.78), action, 10.6, theme["content_text"], spacing=1.0))
            yy += 0.92
    add_text(slide, _in(0.7), _in(6.35), _in(11.9), _in(0.35),
             "Cadencia: revisión semanal de avance y mensual de resultados." if plan["lang"] == "es"
             else "Cadence: weekly progress review and monthly results review.", 9, theme["content_muted"])
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 100 + i * 70) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Plan 30/60/90: cada acción debe tener dueño, métrica y fecha."
    return slide


def _render_recommendations(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_box = H["add_header"](slide, tr(plan["lang"], "recommendations"), tr(plan["lang"], "plan"), page, total, plan["domain_label"])
    add_rect, add_text = H["add_rect"], H["add_text"]
    outcomes_es = ["Decisión clara y cartera enfocada.", "Responsabilidad y ritmo de ejecución.", "Menos riesgo y aprendizaje más rápido."]
    outcomes_en = ["A clear decision and a focused portfolio.", "Accountability and execution rhythm.", "Less risk and faster learning."]
    outcomes = outcomes_es if plan["lang"] == "es" else outcomes_en
    boxes: list[Any] = []
    for i, recommendation in enumerate(plan["recommendations"][:3]):
        x = 0.7 + i * 4.1
        add_rect(slide, _in(x), _in(1.55), _in(3.75), _in(3.45), theme["card"], MSO_SHAPE.ROUNDED_RECTANGLE, line=theme["border"])
        add_rect(slide, _in(x), _in(1.55), _in(3.75), _in(0.07), theme["accent"])
        add_text(slide, _in(x + 0.24), _in(1.72), _in(0.7), _in(0.55), f"0{i + 1}", 24, theme["accent2"], bold=True)
        boxes.append(add_text(slide, _in(x + 0.24), _in(2.3), _in(3.25), _in(1.45), recommendation, 12.2,
                              theme["content_text"], spacing=1.05))
        add_text(slide, _in(x + 0.24), _in(3.85), _in(3.25), _in(0.22), tr(plan["lang"], "expected_result").upper(), 8,
                 theme["accent"], bold=True)
        boxes.append(add_text(slide, _in(x + 0.24), _in(4.1), _in(3.25), _in(0.75), outcomes[i], 10, theme["content_muted"], spacing=1.0))
    add_rect(slide, _in(0.7), _in(5.35), _in(11.93), _in(0.7), theme["accent"], MSO_SHAPE.ROUNDED_RECTANGLE)
    next_text = (f"Siguiente paso: aprobar la primera fase y revisar a 30 días." if plan["lang"] == "es"
                 else "Next step: approve the first phase and review at 30 days.")
    next_box = add_text(slide, _in(0.95), _in(5.47), _in(11.4), _in(0.45), next_text, 12, (255, 255, 255), bold=True,
                        anchor=MSO_ANCHOR.MIDDLE)
    _add_animations(slide, [(title_box, "wipe", 0)] + [(box, "fade", 120 + i * 120) for i, box in enumerate(boxes)] +
                    [(next_box, "fade", 750)], "fade")
    slide.notes_slide.notes_text_frame.text = "Decisiones: tres apuestas, dueño por resultado y revisión a 30 días."
    return slide


def _render_closing(prs, plan: dict[str, Any], theme: dict[str, Any], H: dict[str, Any], page: int, total: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect, add_text = H["add_rect"], H["add_text"]
    add_rect(slide, _in(0), _in(0), _in(13.333), _in(7.5), theme["bg"])
    add_rect(slide, _in(9.4), _in(-1.4), _in(5.6), _in(5.6), None, MSO_SHAPE.OVAL, theme["accent"], 1.0)
    add_rect(slide, _in(10.6), _in(4.8), _in(2.4), _in(2.4), None, MSO_SHAPE.OVAL, theme["accent2"], 0.8)
    title = add_text(slide, _in(0.8), _in(2.0), _in(8.0), _in(1.0), tr(plan["lang"], "closing"), 54, theme["text"], bold=True)
    subtitle = add_text(slide, _in(0.82), _in(3.15), _in(8.0), _in(0.5), tr(plan["lang"], "closing_sub"), 18, theme["muted"])
    add_rect(slide, _in(0.84), _in(3.95), _in(1.8), _in(0.06), theme["accent"])
    steps = plan["actions"]["30"][:3]
    boxes: list[Any] = []
    for i, step in enumerate(steps):
        boxes.append(add_text(slide, _in(0.84), _in(4.35 + i * 0.55), _in(8.4), _in(0.42), f"0{i + 1}  {step}", 11.5,
                              theme["muted"], spacing=1.0))
    add_text(slide, _in(0.84), _in(6.65), _in(7.0), _in(0.3), "Orunex  ·  Inteligencia aplicada", 9, theme["muted"])
    _add_animations(slide, [(title, "fade", 0), (subtitle, "wipe", 250)] + [(box, "fade", 450 + i * 100) for i, box in enumerate(boxes)], "fade")
    slide.notes_slide.notes_text_frame.text = "Cierre: agradecer, confirmar la decisión y los próximos pasos."
    return slide


def write_pptx(path: str, plan: dict[str, Any]) -> dict[str, Any]:
    from pptx import Presentation  # type: ignore
    from pptx.util import Inches  # type: ignore

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    theme = THEMES.get(plan.get("theme", "navy"), THEMES["navy"])
    H = _pptx_helpers(prs, theme)
    specs = _select_slides(plan)
    total = len(specs)
    agenda = _agenda_items(specs, plan)

    for page, spec in enumerate(specs, start=1):
        layout = spec["layout"]
        if layout == "cover":
            _render_cover(prs, plan, theme, H, page, total)
        elif layout == "agenda":
            _render_agenda(prs, plan, theme, H, page, total, agenda)
        elif layout == "summary":
            _render_summary(prs, plan, theme, H, page, total)
        elif layout == "context":
            _render_context(prs, plan, theme, H, page, total)
        elif layout == "findings":
            _render_findings(prs, plan, theme, H, page, total)
        elif layout == "metrics":
            _render_metrics(prs, plan, theme, H, page, total)
        elif layout == "divider":
            _render_divider(prs, plan, theme, H, page, total, spec)
        elif layout == "deep_dive":
            _render_deep_dive(prs, plan, theme, H, page, total, spec)
        elif layout == "framework":
            _render_framework(prs, plan, theme, H, page, total)
        elif layout == "risks":
            _render_risks(prs, plan, theme, H, page, total)
        elif layout == "roadmap":
            _render_roadmap(prs, plan, theme, H, page, total)
        elif layout == "recommendations":
            _render_recommendations(prs, plan, theme, H, page, total)
        elif layout == "closing":
            _render_closing(prs, plan, theme, H, page, total)

    if not plan.get("animations", True):
        from pptx.oxml.ns import qn  # type: ignore
        for slide in prs.slides:
            timing = slide.element.find(qn("p:timing"))
            if timing is not None:
                slide.element.remove(timing)

    prs.core_properties.title = plan["title"]
    prs.core_properties.author = "Orunex"
    prs.core_properties.subject = plan["domain_label"]
    prs.core_properties.comments = "Generated by Orunex Office Expert Studio"
    prs.save(path)
    return {
        "slides": len(prs.slides),
        "theme": theme["name"],
        "agenda": agenda,
        "animated": bool(plan.get("animations", True)),
    }


# ---------------------------------------------------------------------------
# Excel workbook
# ---------------------------------------------------------------------------

def _hex(triple: Sequence[int]) -> str:
    return "%02X%02X%02X" % (int(triple[0]), int(triple[1]), int(triple[2]))


def write_xlsx(path: str, plan: dict[str, Any]) -> dict[str, Any]:
    from openpyxl import Workbook  # type: ignore
    from openpyxl.chart import BarChart, Reference  # type: ignore
    from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule  # type: ignore
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # type: ignore
    from openpyxl.utils import get_column_letter  # type: ignore
    from openpyxl.worksheet.datavalidation import DataValidation  # type: ignore

    lang = plan["lang"]
    es = lang == "es"
    theme = THEMES.get(plan.get("theme", "navy"), THEMES["navy"])
    navy = _hex(theme["bg"])
    accent = _hex(theme["accent"])
    accent2 = _hex(theme["accent2"])
    light = _hex(theme["card"])
    border_color = _hex(theme["border"])
    text_color = _hex(theme["content_text"])
    muted = _hex(theme["content_muted"])

    thin = Side(style="thin", color=border_color)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill("solid", fgColor=accent)
    title_font = Font(bold=True, color="FFFFFF", size=20)
    title_fill = PatternFill("solid", fgColor=navy)
    label_font = Font(bold=True, color=muted, size=9)
    body_font = Font(color=text_color, size=10)

    def fill_cell(cell, color: str):
        cell.fill = PatternFill("solid", fgColor=color)

    def title_block(ws, title: str, subtitle: str, last_col: int):
        ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=last_col)
        cell = ws.cell(row=1, column=1, value=title)
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        for row in ws.iter_rows(min_row=1, max_row=2, min_col=1, max_col=last_col):
            for item in row:
                item.fill = title_fill
        ws.row_dimensions[1].height = 28
        ws.row_dimensions[2].height = 10
        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=last_col)
        sub = ws.cell(row=3, column=1, value=subtitle)
        sub.font = Font(italic=True, color=muted, size=9)
        sub.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[3].height = 18

    def style_header(ws, row: int, last_col: int):
        for col in range(1, last_col + 1):
            cell = ws.cell(row=row, column=col)
            if cell.value is None:
                continue
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border
        ws.row_dimensions[row].height = 26

    def set_widths(ws, widths: dict[str, int]):
        for letter, width in widths.items():
            ws.column_dimensions[letter].width = width

    wb = Workbook()
    dashboard = wb.active
    dashboard.title = tr(lang, "dashboard")
    dashboard.sheet_view.showGridLines = False
    data_sheet = wb.create_sheet(tr(lang, "data"))
    analysis_sheet = wb.create_sheet(tr(lang, "analysis_sheet"))
    plan_sheet = wb.create_sheet(tr(lang, "plan_sheet"))
    research_sheet = wb.create_sheet(tr(lang, "research_sheet"))
    chart_sheet = wb.create_sheet("ChartData")
    chart_sheet.sheet_state = "hidden"

    metrics = plan["metrics"]
    chart_metrics = _chart_metrics(metrics)
    comparable = bool(chart_metrics)
    n = len(metrics)

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    dashboard.sheet_view.zoomScale = 90
    set_widths(dashboard, {"A": 2, "B": 17, "C": 17, "D": 17, "E": 17, "F": 17, "G": 17, "H": 17, "I": 17, "J": 2})
    title_block(dashboard, plan["title"], f"{tr(lang, 'executive_report')}  ·  {plan['domain_label']}  ·  {plan['generated_at']}", 9)
    dashboard.merge_cells("B5:I5")
    dash_label = dashboard["B5"]
    dash_label.value = (tr(lang, "baseline") if metrics else tr(lang, "recommended_kpis")).upper()
    dash_label.font = Font(bold=True, color=accent, size=9)
    dash_label.alignment = Alignment(horizontal="left", vertical="center")

    cards = metrics[:4] if metrics else [{"label": kpi, "display": "KPI", "value": None, "unit": ""} for kpi in plan["kpis"][:4]]
    card_colors = [accent, accent2, navy, accent]
    for i, metric in enumerate(cards):
        start_col = 2 + i * 2
        end_col = start_col + 1
        dashboard.merge_cells(start_row=6, start_column=start_col, end_row=8, end_column=end_col)
        dashboard.merge_cells(start_row=9, start_column=start_col, end_row=9, end_column=end_col)
        value_cell = dashboard.cell(row=6, column=start_col, value=metric.get("display") or "—")
        value_cell.font = Font(bold=True, color=card_colors[i], size=18)
        value_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        label_cell = dashboard.cell(row=9, column=start_col, value=_short(str(metric.get("label") or ""), 38))
        label_cell.font = Font(color=muted, size=9)
        label_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
        for row in dashboard.iter_rows(min_row=6, max_row=9, min_col=start_col, max_col=end_col):
            for cell in row:
                cell.fill = PatternFill("solid", fgColor=light)
                cell.border = border
        for col in range(start_col, end_col + 1):
            dashboard.cell(row=6, column=col).border = Border(left=thin, right=thin, top=Side(style="thick", color=card_colors[i]), bottom=thin)
        dashboard.row_dimensions[6].height = 22
        dashboard.row_dimensions[7].height = 14
        dashboard.row_dimensions[8].height = 14
        dashboard.row_dimensions[9].height = 30

    if len(cards) < 4:
        focus_start = 2 + len(cards) * 2
        dashboard.merge_cells(start_row=6, start_column=focus_start, end_row=9, end_column=9)
        focus = dashboard.cell(row=6, column=focus_start)
        focus.value = ("FOCO\n" if es else "FOCUS\n") + _pick(plan["domain"]["focus"], lang)
        focus.font = Font(color="FFFFFF", size=10)
        focus.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left", indent=1)
        for row in dashboard.iter_rows(min_row=6, max_row=9, min_col=focus_start, max_col=9):
            for cell in row:
                cell.fill = PatternFill("solid", fgColor=navy)

    # Chart data (hidden sheet)
    chart_sheet["A1"] = tr(lang, "metric")
    chart_sheet["B1"] = tr(lang, "value")
    for i, metric in enumerate(chart_metrics or []):
        chart_sheet.cell(row=i + 2, column=1, value=_short(metric["label"], 28))
        chart_sheet.cell(row=i + 2, column=2, value=float(metric["value"]))
    chart_sheet.column_dimensions["A"].width = 30
    chart_sheet.column_dimensions["B"].width = 14

    if chart_metrics:
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = tr(lang, "kpi_panel")
        chart.y_axis.title = None
        chart.height = 9.5
        chart.width = 22
        chart.gapWidth = 80
        chart.legend = None
        values = Reference(chart_sheet, min_col=2, min_row=1, max_row=len(chart_metrics) + 1)
        categories = Reference(chart_sheet, min_col=1, min_row=2, max_row=len(chart_metrics) + 1)
        chart.add_data(values, titles_from_data=True)
        chart.set_categories(categories)
        from openpyxl.chart.label import DataLabelList  # type: ignore
        chart.dataLabels = DataLabelList()
        chart.dataLabels.showVal = True
        chart.dataLabels.showCatName = False
        chart.dataLabels.showSerName = False
        chart.dataLabels.showLegendKey = False
        chart.dataLabels.showPercent = False
        chart.dataLabels.showBubbleSize = False
        chart.dataLabels.numberFormat = "#,##0"
        chart.dataLabels.position = "outEnd"
        chart.series[0].graphicalProperties.solidFill = accent
        chart.series[0].graphicalProperties.line.solidFill = accent
        chart.x_axis.delete = False
        chart.x_axis.tickLblPos = "low"
        chart.x_axis.title = None
        chart.y_axis.delete = False
        chart.y_axis.majorGridlines = None
        dashboard.add_chart(chart, "B11")
        dashboard.merge_cells("B27:I30")
        reading = dashboard["B27"]
        values = [float(m["value"]) for m in chart_metrics]
        top = max(chart_metrics, key=lambda m: float(m["value"]))
        low = min(chart_metrics, key=lambda m: float(m["value"]))
        avg = sum(values) / len(values)
        positive = [abs(v) for v in values if v]
        spread = (max(positive) / min(positive)) if positive and min(positive) > 0 else 99
        if spread <= 2.5:
            reading.value = (
                f"{tr(lang, 'reading')}: {top['label']} = {top['display']}. "
                f"{tr(lang, 'average')}: {_fmt_value(avg, chart_metrics[0].get('unit', ''), lang)}. "
                + ("Validar las cifras antes de compartir." if es else "Validate the figures before sharing.")
            )
        else:
            reading.value = (
                f"{tr(lang, 'reading')}: {top['label']} = {top['display']}; {low['label']} = {low['display']}. "
                + (f"El mayor valor es {spread:.0f}x el menor; no se usa promedio. "
                   if es else f"The highest value is {spread:.0f}x the lowest; no average is used. ")
                + ("Validar las cifras antes de compartir." if es else "Validate the figures before sharing.")
            )
    else:
        dashboard.merge_cells("B11:I11")
        dashboard["B11"] = tr(lang, "metric").upper()
        dashboard["B11"].font = Font(bold=True, color="FFFFFF", size=10)
        dashboard["B11"].fill = header_fill
        dashboard["B11"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        for i, metric in enumerate(metrics[:6] or cards):
            row = 12 + i
            dashboard.cell(row=row, column=2, value=_short(str(metric.get("label") or ""), 44)).font = body_font
            dashboard.cell(row=row, column=3, value=metric.get("display") or "—").font = Font(bold=True, color=accent, size=10)
            dashboard.cell(row=row, column=3).alignment = Alignment(horizontal="right")
            dashboard.merge_cells(start_row=row, start_column=4, end_row=row, end_column=9)
            dashboard.cell(row=row, column=4, value=tr(lang, "data_from_request") if metrics else tr(lang, "needs_data")).font = Font(color=muted, size=9)
            for col in range(2, 10):
                dashboard.cell(row=row, column=col).border = border
        dashboard.merge_cells("B19:I22")
        reading = dashboard["B19"]
        reading.value = (
            f"{tr(lang, 'reading')}: " + ("las métricas no comparten unidad y magnitud; se presentan como tabla, no como un solo eje." if es
                                           else "metrics do not share unit and magnitude; they are shown as a table, not a single axis.")
        )
        reading.font = Font(color=text_color, size=10)
        reading.alignment = Alignment(wrap_text=True, vertical="top")
        reading.fill = PatternFill("solid", fgColor=light)
        reading.border = border
        dashboard.merge_cells("B24:I24")
        priority_head = dashboard["B24"]
        priority_head.value = ("PRIORIDADES 30 DÍAS" if es else "30-DAY PRIORITIES")
        priority_head.font = Font(bold=True, color=accent, size=9)
        priority_head.alignment = Alignment(horizontal="left", vertical="center")
        for i, action in enumerate(plan["actions"]["30"][:3]):
            row = 25 + i
            dashboard.merge_cells(start_row=row, start_column=2, end_row=row, end_column=9)
            cell = dashboard.cell(row=row, column=2, value=f"{i + 1}.  {action}")
            cell.font = Font(color=text_color, size=10)
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            for col in range(2, 10):
                dashboard.cell(row=row, column=col).border = border

    dashboard.merge_cells("B32:I32")
    nav = dashboard["B32"]
    nav.value = ("Navegación: Datos · Análisis · Plan · Investigación" if es else "Navigation: Data · Analysis · Plan · Research")
    nav.font = Font(bold=True, color=accent, size=9)
    nav.alignment = Alignment(horizontal="left", vertical="center")
    dashboard.merge_cells("B33:I33")
    note = dashboard["B33"]
    note.value = tr(lang, "research_query_note") if plan["sources"] else tr(lang, "no_external_sources")
    note.font = Font(italic=True, color=muted, size=8)
    note.alignment = Alignment(wrap_text=True, vertical="top")

    # ------------------------------------------------------------------
    # Data sheet
    # ------------------------------------------------------------------
    data_sheet.sheet_view.showGridLines = False
    data_sheet.sheet_view.zoomScale = 90
    set_widths(data_sheet, {"A": 34, "B": 18, "C": 12, "D": 14, "E": 16, "F": 12})
    title_block(data_sheet, tr(lang, "data"), plan["title"], 6)
    headers = [tr(lang, "metric"), tr(lang, "value"), tr(lang, "unit"), tr(lang, "weight"), tr(lang, "vs_avg"), tr(lang, "ranking")]
    for col, header in enumerate(headers, start=1):
        data_sheet.cell(row=4, column=col, value=header)
    style_header(data_sheet, 4, 6)
    start_row = 5
    if metrics:
        for i, metric in enumerate(metrics):
            row = start_row + i
            data_sheet.cell(row=row, column=1, value=metric["label"]).font = Font(bold=True, color=text_color, size=10)
            data_sheet.cell(row=row, column=2, value=float(metric["value"])).number_format = "#,##0.00"
            data_sheet.cell(row=row, column=3, value=metric.get("unit") or "").alignment = Alignment(horizontal="center")
            if comparable:
                data_sheet.cell(row=row, column=4, value=f'=IFERROR(B{row}/SUM($B${start_row}:$B${start_row + n - 1}),"")')
                data_sheet.cell(row=row, column=4).number_format = "0.0%"
                data_sheet.cell(row=row, column=5, value=f'=IFERROR(B{row}/AVERAGE($B${start_row}:$B${start_row + n - 1})-1,"")')
                data_sheet.cell(row=row, column=5).number_format = "+0.0%;-0.0%;0.0%"
                data_sheet.cell(row=row, column=6, value=f'=IFERROR(RANK(B{row},$B${start_row}:$B${start_row + n - 1},0),"")')
            else:
                data_sheet.cell(row=row, column=4, value="—")
                data_sheet.cell(row=row, column=5, value="—")
                data_sheet.cell(row=row, column=6, value="—")
            for col in range(1, 7):
                cell = data_sheet.cell(row=row, column=col)
                cell.border = border
                if col >= 4:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                if col == 2:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
        if comparable:
            total_row = start_row + n
            data_sheet.cell(row=total_row, column=1, value=tr(lang, "total")).font = Font(bold=True, color="FFFFFF")
            data_sheet.cell(row=total_row, column=1).fill = PatternFill("solid", fgColor=navy)
            data_sheet.cell(row=total_row, column=2, value=f"=SUM(B{start_row}:B{start_row + n - 1})").font = Font(bold=True, color=navy)
            data_sheet.cell(row=total_row, column=2).number_format = "#,##0.00"
            data_sheet.cell(row=total_row, column=2).fill = PatternFill("solid", fgColor=light)
            for col in range(1, 7):
                data_sheet.cell(row=total_row, column=col).border = border
            note_row = total_row + 2
        else:
            note_row = start_row + n + 1
        data_sheet.auto_filter.ref = f"A4:F{start_row + n - 1}"
        data_sheet.freeze_panes = "A5"
        if comparable:
            data_sheet.conditional_formatting.add(
                f"B{start_row}:B{start_row + n - 1}",
                DataBarRule(start_type="num", start_value=0, end_type="max", color=accent, showValue=True),
            )
            data_sheet.conditional_formatting.add(
                f"D{start_row}:D{start_row + n - 1}",
                ColorScaleRule(start_type="min", start_color="E8F1FF", end_type="max", end_color=accent),
            )
            data_sheet.conditional_formatting.add(
                f"E{start_row}:E{start_row + n - 1}",
                CellIsRule(operator="greaterThan", formula=["0"], fill=PatternFill("solid", fgColor="E8F8EE")),
            )
            data_sheet.conditional_formatting.add(
                f"E{start_row}:E{start_row + n - 1}",
                CellIsRule(operator="lessThan", formula=["0"], fill=PatternFill("solid", fgColor="FDEBEC")),
            )
        data_sheet.merge_cells(start_row=note_row, start_column=1, end_row=note_row + 1, end_column=6)
        note_cell = data_sheet.cell(row=note_row, column=1)
        note_cell.value = (
            "Las columnas de peso, promedio y ranking solo se calculan cuando las métricas comparten unidad y magnitud."
            if es else "Weight, average and ranking are only calculated when metrics share unit and magnitude."
        )
        note_cell.font = Font(italic=True, color=muted, size=9)
        note_cell.alignment = Alignment(wrap_text=True, vertical="top")
    else:
        for i, kpi in enumerate(plan["kpis"][:5]):
            row = start_row + i
            data_sheet.cell(row=row, column=1, value=kpi).font = Font(bold=True, color=text_color, size=10)
            data_sheet.cell(row=row, column=2, value="")
            data_sheet.cell(row=row, column=3, value="")
            data_sheet.cell(row=row, column=4, value=tr(lang, "needs_data")).font = Font(italic=True, color=muted, size=9)
            data_sheet.merge_cells(start_row=row, start_column=4, end_row=row, end_column=6)
            for col in range(1, 7):
                data_sheet.cell(row=row, column=col).border = border
        data_sheet.freeze_panes = "A5"

    # ------------------------------------------------------------------
    # Analysis sheet
    # ------------------------------------------------------------------
    analysis_sheet.sheet_view.showGridLines = False
    analysis_sheet.sheet_view.zoomScale = 90
    set_widths(analysis_sheet, {"A": 28, "B": 18, "C": 4, "D": 30, "E": 18, "F": 18, "G": 18, "H": 14})
    title_block(analysis_sheet, tr(lang, "analysis_sheet"), f"{tr(lang, 'methodology')}: {tr(lang, 'assumptions_text')[:110]}…", 8)
    analysis_sheet["A5"] = tr(lang, "metric")
    analysis_sheet["B5"] = tr(lang, "value")
    style_header(analysis_sheet, 5, 2)
    if comparable:
        stats = [
            (tr(lang, "total"), f'=IFERROR(SUM({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1}),"")'),
            (tr(lang, "average"), f'=IFERROR(AVERAGE({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1}),"")'),
            ("Mediana" if es else "Median", f'=IFERROR(MEDIAN({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1}),"")'),
            ("Máximo" if es else "Maximum", f'=IFERROR(MAX({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1}),"")'),
            ("Mínimo" if es else "Minimum", f'=IFERROR(MIN({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1}),"")'),
            ("Desviación estándar" if es else "Standard deviation", f'=IFERROR(STDEV({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1}),"")'),
            ("Conteo" if es else "Count", f'=COUNT({tr(lang, "data")}!B{start_row}:B{start_row + max(n, 1) - 1})'),
        ]
        for i, (label, formula) in enumerate(stats):
            row = 6 + i
            analysis_sheet.cell(row=row, column=1, value=label).font = Font(bold=True, color=text_color, size=10)
            cell = analysis_sheet.cell(row=row, column=2, value=formula)
            cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="right")
            for col in (1, 2):
                analysis_sheet.cell(row=row, column=col).border = border
                analysis_sheet.cell(row=row, column=col).fill = PatternFill("solid", fgColor=light)
    else:
        for i, metric in enumerate(metrics[:8]):
            row = 6 + i
            label = str(metric["label"])
            unit = str(metric.get("unit") or "").strip()
            if unit:
                label += f" ({unit})"
            analysis_sheet.cell(row=row, column=1, value=label).font = Font(bold=True, color=text_color, size=10)
            cell = analysis_sheet.cell(row=row, column=2, value=float(metric["value"]))
            cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="right")
            for col in (1, 2):
                analysis_sheet.cell(row=row, column=col).border = border
                analysis_sheet.cell(row=row, column=col).fill = PatternFill("solid", fgColor=light)
        note_row = 6 + min(len(metrics), 8)
        analysis_sheet.merge_cells(start_row=note_row, start_column=1, end_row=note_row + 1, end_column=2)
        note = analysis_sheet.cell(row=note_row, column=1)
        note.value = ("No se calcula total ni promedio: las métricas no comparten unidad y magnitud."
                      if es else "No total or average is calculated: metrics do not share unit and magnitude.")
        note.font = Font(italic=True, color=muted, size=9)
        note.alignment = Alignment(wrap_text=True, vertical="top")

    analysis_sheet["D5"] = tr(lang, "scenario")
    analysis_sheet["E5"] = tr(lang, "base")
    analysis_sheet["F5"] = tr(lang, "conservative")
    analysis_sheet["G5"] = tr(lang, "optimistic")
    analysis_sheet["H5"] = "Rango" if es else "Range"
    style_header(analysis_sheet, 5, 8)
    if metrics:
        for i, metric in enumerate(metrics[:8]):
            row = 6 + i
            analysis_sheet.cell(row=row, column=4, value=metric["label"]).font = Font(bold=True, color=text_color, size=10)
            analysis_sheet.cell(row=row, column=5, value=f"={tr(lang, 'data')}!B{start_row + i}").number_format = "#,##0.00"
            analysis_sheet.cell(row=row, column=6, value=f"=E{row}*0.9").number_format = "#,##0.00"
            analysis_sheet.cell(row=row, column=7, value=f"=E{row}*1.1").number_format = "#,##0.00"
            analysis_sheet.cell(row=row, column=8, value=f"=G{row}-F{row}").number_format = "#,##0.00"
            for col in range(4, 9):
                analysis_sheet.cell(row=row, column=col).border = border
                if col >= 5:
                    analysis_sheet.cell(row=row, column=col).alignment = Alignment(horizontal="right")
        note_row = 6 + min(len(metrics), 8)
        analysis_sheet.merge_cells(start_row=note_row, start_column=4, end_row=note_row + 1, end_column=8)
        analysis_sheet.cell(row=note_row, column=4, value=tr(lang, "sensitivity_note")).font = Font(italic=True, color=muted, size=9)
        analysis_sheet.cell(row=note_row, column=4).alignment = Alignment(wrap_text=True, vertical="top")

    analysis_sheet.merge_cells("A15:H21")
    interpretation = analysis_sheet["A15"]
    interpretation.value = (
        f"{tr(lang, 'reading')}: {plan['executive_summary']}\n\n"
        f"{tr(lang, 'methodology')}: {tr(lang, 'assumptions_text')}"
    )
    interpretation.font = Font(color=text_color, size=10)
    interpretation.alignment = Alignment(wrap_text=True, vertical="top")
    interpretation.fill = PatternFill("solid", fgColor=light)
    interpretation.border = border

    # ------------------------------------------------------------------
    # Plan sheet
    # ------------------------------------------------------------------
    plan_sheet.sheet_view.showGridLines = False
    plan_sheet.sheet_view.zoomScale = 90
    set_widths(plan_sheet, {"A": 14, "B": 62, "C": 20, "D": 28, "E": 16})
    title_block(plan_sheet, tr(lang, "plan_sheet"), f"{tr(lang, 'roadmap')}  ·  {tr(lang, 'owner')} / {tr(lang, 'status')}", 5)
    plan_headers = [tr(lang, "horizon"), tr(lang, "action"), tr(lang, "owner"), tr(lang, "metric"), tr(lang, "status")]
    for col, header in enumerate(plan_headers, start=1):
        plan_sheet.cell(row=5, column=col, value=header)
    style_header(plan_sheet, 5, 5)
    row = 6
    status_pending = tr(lang, "pending")
    for horizon in ("30", "60", "90"):
        label = f"{horizon} " + ("días" if es else "days")
        for action in plan["actions"][horizon][:3]:
            plan_sheet.cell(row=row, column=1, value=label).font = Font(bold=True, color=accent, size=9)
            plan_sheet.cell(row=row, column=2, value=action).font = body_font
            plan_sheet.cell(row=row, column=3, value="Por asignar" if es else "To assign").font = Font(color=muted, size=9)
            plan_sheet.cell(row=row, column=4, value=plan["kpis"][(row - 6) % len(plan["kpis"])]).font = Font(color=muted, size=9)
            plan_sheet.cell(row=row, column=5, value=status_pending).font = Font(color=muted, size=9)
            for col in range(1, 6):
                cell = plan_sheet.cell(row=row, column=col)
                cell.border = border
                cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left" if col in (2, 4) else "center")
            plan_sheet.row_dimensions[row].height = 32
            row += 1
    last_row = row - 1
    plan_sheet.auto_filter.ref = f"A5:E{last_row}"
    plan_sheet.freeze_panes = "A6"
    statuses = [status_pending, tr(lang, "in_progress"), tr(lang, "done"), tr(lang, "blocked")]
    validation = DataValidation(type="list", formula1='"' + ",".join(statuses) + '"', allow_blank=True)
    plan_sheet.add_data_validation(validation)
    validation.add(f"E6:E{last_row}")
    plan_sheet.conditional_formatting.add(f"E6:E{last_row}", CellIsRule(operator="equal", formula=[f'"{statuses[2]}"'], fill=PatternFill("solid", fgColor="D9F7E5")))
    plan_sheet.conditional_formatting.add(f"E6:E{last_row}", CellIsRule(operator="equal", formula=[f'"{statuses[1]}"'], fill=PatternFill("solid", fgColor="FFF4D6")))
    plan_sheet.conditional_formatting.add(f"E6:E{last_row}", CellIsRule(operator="equal", formula=[f'"{statuses[3]}"'], fill=PatternFill("solid", fgColor="FDE2E4")))

    # ------------------------------------------------------------------
    # Research sheet
    # ------------------------------------------------------------------
    research_sheet.sheet_view.showGridLines = False
    research_sheet.sheet_view.zoomScale = 90
    set_widths(research_sheet, {"A": 5, "B": 64, "C": 26, "D": 48})
    title_block(research_sheet, tr(lang, "research_sheet"), f"{tr(lang, 'sources')}  ·  {plan['generated_at']}", 4)
    research_sheet["A5"] = tr(lang, "context")
    research_sheet["A5"].font = Font(bold=True, color=accent, size=11)
    research_sheet.merge_cells("A6:D10")
    context_text = "\n\n".join(plan["context"])
    research_sheet["A6"] = context_text
    research_sheet["A6"].alignment = Alignment(wrap_text=True, vertical="top")
    research_sheet["A6"].font = Font(color=text_color, size=10)
    research_sheet["A6"].fill = PatternFill("solid", fgColor=light)

    research_sheet["A12"] = tr(lang, "findings")
    research_sheet["A12"].font = Font(bold=True, color=accent, size=11)
    research_headers = ["#", tr(lang, "findings"), tr(lang, "source"), "URL"]
    for col, header in enumerate(research_headers, start=1):
        research_sheet.cell(row=13, column=col, value=header)
    style_header(research_sheet, 13, 4)
    if plan["sources"]:
        for i, item in enumerate(plan["sources"]):
            row = 14 + i
            research_sheet.cell(row=row, column=1, value=i + 1).alignment = Alignment(horizontal="center")
            research_sheet.cell(row=row, column=2, value=item["title"]).font = Font(bold=True, color=text_color, size=10)
            research_sheet.cell(row=row, column=3, value=item["source"]).font = Font(color=muted, size=9)
            url_cell = research_sheet.cell(row=row, column=4, value=item["url"])
            url_cell.hyperlink = item["url"]
            url_cell.font = Font(color=accent, underline="single", size=9)
            for col in range(1, 5):
                research_sheet.cell(row=row, column=col).border = border
                research_sheet.cell(row=row, column=col).alignment = Alignment(wrap_text=True, vertical="top")
        next_row = 14 + len(plan["sources"]) + 1
    else:
        research_sheet.merge_cells("A14:D15")
        research_sheet["A14"] = tr(lang, "no_external_sources")
        research_sheet["A14"].alignment = Alignment(wrap_text=True, vertical="top")
        research_sheet["A14"].font = Font(italic=True, color=muted, size=10)
        next_row = 17

    research_sheet.cell(row=next_row, column=1, value=tr(lang, "framework")).font = Font(bold=True, color=accent, size=11)
    header_row = next_row + 1
    research_sheet.merge_cells(start_row=header_row, start_column=1, end_row=header_row, end_column=2)
    research_sheet.cell(row=header_row, column=1, value=("Marco" if es else "Framework"))
    research_sheet.merge_cells(start_row=header_row, start_column=3, end_row=header_row, end_column=4)
    research_sheet.cell(row=header_row, column=3, value=("Uso" if es else "Use"))
    for col in (1, 3):
        cell = research_sheet.cell(row=header_row, column=col)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
    research_sheet.row_dimensions[header_row].height = 26
    for i, framework in enumerate(plan["frameworks"][:3]):
        row = header_row + 1 + i
        research_sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        research_sheet.cell(row=row, column=1, value=framework["name"]).font = Font(bold=True, color=text_color, size=10)
        research_sheet.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
        research_sheet.cell(row=row, column=3, value=framework["desc"] + " " + " / ".join(framework["steps"])).font = Font(color=muted, size=9)
        for col in (1, 3):
            cell = research_sheet.cell(row=row, column=col)
            cell.border = border
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.fill = PatternFill("solid", fgColor=light)
        research_sheet.row_dimensions[row].height = 44

    research_sheet.cell(row=next_row + 6, column=1, value=tr(lang, "assumptions")).font = Font(bold=True, color=accent, size=11)
    research_sheet.merge_cells(start_row=next_row + 7, start_column=1, end_row=next_row + 9, end_column=4)
    assumptions = research_sheet.cell(row=next_row + 7, column=1, value=tr(lang, "assumptions_text"))
    assumptions.alignment = Alignment(wrap_text=True, vertical="top")
    assumptions.font = Font(color=muted, size=9)
    assumptions.fill = PatternFill("solid", fgColor=light)

    # ------------------------------------------------------------------
    # Workbook cosmetics
    # ------------------------------------------------------------------
    for sheet, color in (
        (dashboard, accent), (data_sheet, accent2), (analysis_sheet, navy),
        (plan_sheet, "10B981"), (research_sheet, "F59E0B"),
    ):
        sheet.sheet_properties.tabColor = color
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.print_options.horizontalCentered = True

    wb.properties.title = plan["title"]
    wb.properties.creator = "Orunex"
    wb.properties.subject = plan["domain_label"]
    wb.properties.description = "Generated by Orunex Office Expert Studio"
    wb.save(path)
    return {
        "sheets": wb.sheetnames,
        "dashboard": tr(lang, "dashboard"),
        "charts": 1 if chart_metrics else 0,
        "comparable": comparable,
    }


# ---------------------------------------------------------------------------
# Word executive report
# ---------------------------------------------------------------------------

def _docx_hex(triple: Sequence[int]) -> str:
    return "%02X%02X%02X" % (int(triple[0]), int(triple[1]), int(triple[2]))


def _docx_shade(cell, color: str) -> None:
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore

    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def _docx_cell_margins(cell, top=60, bottom=60, left=90, right=90) -> None:
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore

    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for side, value in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tc_pr.append(mar)


def _docx_field(paragraph, instruction: str, placeholder: str = "1") -> None:
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore

    begin_run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin_run._r.append(begin)

    instr_run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    instr_run._r.append(instr)

    sep_run = paragraph.add_run()
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    sep_run._r.append(sep)

    paragraph.add_run(placeholder)

    end_run = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    end_run._r.append(end)


def _docx_hyperlink(paragraph, url: str, text: str, color: str = "2563EB", size: float = 9.5) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE  # type: ignore
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
    from docx.shared import Pt, RGBColor  # type: ignore

    relationship = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    r_fonts = OxmlElement("w:rFonts")
    r_fonts.set(qn("w:ascii"), "Segoe UI")
    r_fonts.set(qn("w:hAnsi"), "Segoe UI")
    props.append(r_fonts)
    r_color = OxmlElement("w:color")
    r_color.set(qn("w:val"), color)
    props.append(r_color)
    r_size = OxmlElement("w:sz")
    r_size.set(qn("w:val"), str(int(size * 2)))
    props.append(r_size)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    run.append(props)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    link.append(run)
    paragraph._p.append(link)


def _docx_table(doc, headers, rows, widths, theme, lang: str, first_bold: bool = True):
    from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT  # type: ignore
    from docx.enum.text import WD_ALIGN_PARAGRAPH  # type: ignore
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
    from docx.shared import Cm, Pt, RGBColor  # type: ignore

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    accent = _docx_hex(theme["accent"])
    border = _docx_hex(theme["border"])
    light = _docx_hex(theme["card"])
    text = _docx_hex(theme["content_text"])
    muted = _docx_hex(theme["content_muted"])

    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.width = Cm(widths[index])
        _docx_shade(cell, accent)
        _docx_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(str(header))
        run.font.name = "Segoe UI"
        run.font.size = Pt(9)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cell = cells[index]
            cell.width = Cm(widths[index])
            _docx_shade(cell, light if row_index % 2 == 0 else "FFFFFF")
            _docx_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
            run = paragraph.add_run(str(value))
            run.font.name = "Segoe UI"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor.from_string(text if index == 0 or not first_bold else muted)
            run.font.bold = bool(index == 0 and first_bold)

    for column, width in enumerate(widths):
        table.columns[column].width = Cm(width)
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)

    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), border)
        borders.append(node)
    tbl_pr.append(borders)
    return table


def _docx_chart(plan: dict[str, Any]) -> Optional[str]:
    metrics = _chart_metrics(plan["metrics"])
    if len(metrics) < 2:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        return None

    lang = plan["lang"]
    theme = THEMES.get(plan.get("theme", "navy"), THEMES["navy"])
    width, height = 1600, 860
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    def font(size: int, bold: bool = False):
        names = ("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")
        base = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for name in names:
            try:
                return ImageFont.truetype(os.path.join(base, name), size)
            except Exception:
                continue
        return ImageFont.load_default()

    text_color = tuple(theme["content_text"])
    muted = tuple(theme["content_muted"])
    accent = tuple(theme["accent"])
    accent2 = tuple(theme["accent2"])
    border = tuple(theme["border"])

    draw.text((64, 38), tr(lang, "kpi_panel"), font=font(38, True), fill=text_color)
    draw.text((64, 92), f"{plan['domain_label']}  ·  {plan['generated_at']}", font=font(20), fill=muted)

    left, right, top, bottom = 520, 1480, 180, 780
    max_value = max(abs(float(m["value"])) for m in metrics) or 1.0
    slot = (bottom - top) / len(metrics)
    bar_height = min(64, slot * 0.52)

    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        x = left + (right - left) * tick
        draw.line([(x, top - 10), (x, bottom + 6)], fill=border, width=2)
        label = _fmt_value(max_value * tick, metrics[0].get("unit", ""), lang)
        draw.text((x, bottom + 16), label, font=font(18), fill=muted, anchor="ma")

    for index, metric in enumerate(metrics):
        y = top + index * slot + (slot - bar_height) / 2
        value = abs(float(metric["value"]))
        bar_width = max(4, (right - left) * value / max_value)
        draw.text((left - 24, y + bar_height / 2), _short(metric["label"], 34), font=font(22, True),
                  fill=text_color, anchor="rm")
        draw.rounded_rectangle([left, y, left + bar_width, y + bar_height], radius=8,
                               fill=accent if index % 2 == 0 else accent2)
        draw.text((left + bar_width + 18, y + bar_height / 2), metric["display"], font=font(21, True),
                  fill=text_color, anchor="lm")

    draw.line([(left, bottom + 4), (right, bottom + 4)], fill=text_color, width=2)
    path = os.path.join(tempfile.gettempdir(), f"orunex_chart_{os.getpid()}_{abs(hash(plan['title'])) % 99999}.png")
    image.save(path)
    return path


def write_docx(path: str, plan: dict[str, Any]) -> dict[str, Any]:
    from docx import Document  # type: ignore
    from docx.enum.section import WD_SECTION  # type: ignore
    from docx.enum.table import WD_ALIGN_VERTICAL  # type: ignore
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT  # type: ignore
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
    from docx.shared import Cm, Pt, RGBColor  # type: ignore

    lang = plan["lang"]
    es = lang == "es"
    theme = THEMES.get(plan.get("theme", "navy"), THEMES["navy"])
    accent = _docx_hex(theme["accent"])
    accent2 = _docx_hex(theme["accent2"])
    dark = _docx_hex(theme["bg"])
    text_hex = _docx_hex(theme["content_text"])
    muted_hex = _docx_hex(theme["content_muted"])
    card_hex = _docx_hex(theme["card"])
    border_hex = _docx_hex(theme["border"])

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.9)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)
    section.header_distance = Cm(0.9)
    section.footer_distance = Cm(0.9)
    section.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name = "Segoe UI"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(text_hex)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.16
    r_pr = normal.element.get_or_add_rPr()
    r_fonts = r_pr.get_or_add_rFonts()
    r_fonts.set(qn("w:eastAsia"), "Segoe UI")

    for level, size, before in ((1, 17, 16), (2, 12.5, 10), (3, 11, 8)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Segoe UI"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(accent)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    # ---- Header / footer ------------------------------------------------
    header = section.header
    header_paragraph = header.paragraphs[0]
    header_paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(16.6), WD_TAB_ALIGNMENT.RIGHT)
    run = header_paragraph.add_run(f"Orunex  ·  {plan['domain_label']}")
    run.font.name = "Segoe UI"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(muted_hex)
    header_paragraph.add_run("\t")
    run = header_paragraph.add_run(tr(lang, "confidential").upper())
    run.font.name = "Segoe UI"
    run.font.size = Pt(7.5)
    run.font.color.rgb = RGBColor.from_string(muted_hex)
    p_pr = header_paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), border_hex)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)

    footer = section.footer
    footer_paragraph = footer.paragraphs[0]
    footer_paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(16.6), WD_TAB_ALIGNMENT.RIGHT)
    run = footer_paragraph.add_run(f"Orunex  ·  {plan['generated_at']}")
    run.font.name = "Segoe UI"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(muted_hex)
    footer_paragraph.add_run("\t")
    run = footer_paragraph.add_run(tr(lang, "page") + " ")
    run.font.name = "Segoe UI"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(muted_hex)
    _docx_field(footer_paragraph, "PAGE", "1")
    run = footer_paragraph.add_run(f" {tr(lang, 'of')} ")
    run.font.name = "Segoe UI"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(muted_hex)
    _docx_field(footer_paragraph, "NUMPAGES", "1")
    for field_run in footer_paragraph.runs:
        field_run.font.name = "Segoe UI"
        field_run.font.size = Pt(8)
        field_run.font.color.rgb = RGBColor.from_string(muted_hex)

    # ---- Cover ----------------------------------------------------------
    cover = doc.add_table(rows=1, cols=1)
    cover.autofit = False
    cover.alignment = 1
    cell = cover.rows[0].cells[0]
    cell.width = Cm(16.6)
    cover.columns[0].width = Cm(16.6)
    _docx_shade(cell, dark)
    _docx_cell_margins(cell, top=300, bottom=300, left=520, right=420)
    cover.rows[0].height = Cm(20.5 if plan["metrics"] else 24.0)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    def cover_paragraph(value: str, size: float, color: str, bold: bool = False, space: float = 6,
                        italic: bool = False):
        paragraph = cell.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(space)
        paragraph.paragraph_format.line_spacing = 1.02
        run = paragraph.add_run(value)
        run.font.name = "Segoe UI"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = RGBColor.from_string(color)
        return paragraph

    kicker = f"{tr(lang, 'executive_report').upper()}  ·  {plan['domain_label'].upper()}"
    cover_paragraph(kicker, 9.5, accent2, bold=True, space=18)
    cover_paragraph(plan["title"], 33 if len(plan["title"]) <= 52 else 27, "FFFFFF", bold=True, space=14)
    cover_paragraph("Análisis, hallazgos y plan de acción" if es else "Analysis, findings and action plan",
                    13, _docx_hex(theme["muted"]), space=30)
    cover_paragraph(f"{tr(lang, 'prepared_by')}  ·  {plan['generated_at']}", 10, _docx_hex(theme["muted"]), space=2)
    cover_paragraph(tr(lang, "confidential"), 8.5, _docx_hex(theme["muted"]), space=0)

    if plan["metrics"]:
        doc.add_paragraph().paragraph_format.space_after = Pt(0)
        chips = doc.add_table(rows=1, cols=min(3, len(plan["metrics"])))
        chips.autofit = False
        chips.alignment = 1
        for index, metric in enumerate(plan["metrics"][:3]):
            chip = chips.rows[0].cells[index]
            chip.width = Cm(5.35)
            chips.columns[index].width = Cm(5.35)
            _docx_shade(chip, card_hex)
            _docx_cell_margins(chip, top=160, bottom=160, left=180, right=180)
            paragraph = chip.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(2)
            run = paragraph.add_run(_short(metric["label"], 28))
            run.font.name = "Segoe UI"
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor.from_string(muted_hex)
            paragraph = chip.add_paragraph()
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(metric["display"])
            run.font.name = "Segoe UI"
            run.font.size = Pt(15)
            run.font.bold = True
            run.font.color.rgb = RGBColor.from_string(accent)

    doc.add_page_break()

    # ---- Table of contents ---------------------------------------------
    toc_heading = doc.add_paragraph()
    toc_heading.paragraph_format.space_after = Pt(10)
    run = toc_heading.add_run(tr(lang, "index"))
    run.font.name = "Segoe UI"
    run.font.size = Pt(17)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(accent)
    toc_paragraph = doc.add_paragraph()
    _docx_field(toc_paragraph, 'TOC \\o "1-2" \\h \\z \\u',
                "Actualiza el índice en Word con F9." if es else "Update the table of contents in Word with F9.")
    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(8)
    run = note.add_run("El índice se actualiza automáticamente al abrir el documento en Word."
                       if es else "The table of contents updates automatically when the document opens in Word.")
    run.font.size = Pt(8)
    run.font.italic = True
    run.font.color.rgb = RGBColor.from_string(muted_hex)
    doc.add_page_break()

    # ---- Executive summary ---------------------------------------------
    doc.add_heading(tr(lang, "summary"), level=1)
    doc.add_paragraph(plan["executive_summary"])
    doc.add_heading(tr(lang, "key_messages"), level=2)
    for message in plan["key_messages"]:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.add_run(message)

    # ---- Context --------------------------------------------------------
    doc.add_heading(tr(lang, "context"), level=1)
    for paragraph_text in plan["context"]:
        doc.add_paragraph(paragraph_text)

    # ---- Metrics --------------------------------------------------------
    doc.add_heading(tr(lang, "kpi_panel"), level=1)
    if plan["metrics"]:
        metrics = plan["metrics"]
        comparable = bool(_chart_metrics(metrics))
        values = [float(m["value"]) for m in metrics]
        total = sum(values) if comparable and all(v >= 0 for v in values) and sum(values) else 0
        average = (sum(values) / len(values)) if values else 0
        rows = []
        for index, metric in enumerate(metrics):
            value = float(metric["value"])
            weight = f"{value / total * 100:.1f}%" if total else "—"
            vs_avg = f"{(value / average - 1) * 100:+.1f}%" if average and comparable else "—"
            rows.append([metric["label"], metric["display"], metric.get("unit") or "—", weight, vs_avg])
        _docx_table(doc, [tr(lang, "metric"), tr(lang, "value"), tr(lang, "unit"), tr(lang, "weight"), tr(lang, "vs_avg")],
                    rows, [5.3, 3.3, 2.4, 2.8, 2.8], theme, lang)
        chart_path = _docx_chart(plan)
        if chart_path:
            doc.add_paragraph().paragraph_format.space_after = Pt(2)
            doc.add_picture(chart_path, width=Cm(16.2))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            caption = doc.add_paragraph()
            caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = caption.add_run(
                ("Solo se grafican métricas con unidad y magnitud comparables." if es
                 else "Only metrics with comparable unit and magnitude are charted.")
            )
            run.font.size = Pt(8)
            run.font.italic = True
            run.font.color.rgb = RGBColor.from_string(muted_hex)
        note = doc.add_paragraph()
        run = note.add_run(tr(lang, "data_from_request") + ". " + tr(lang, "sensitivity_note"))
        run.font.size = Pt(8)
        run.font.italic = True
        run.font.color.rgb = RGBColor.from_string(muted_hex)
    else:
        doc.add_paragraph(tr(lang, "no_metrics") + ". " + tr(lang, "recommended_kpis") + ": " + ", ".join(plan["kpis"][:5]) + ".")
        _docx_table(
            doc,
            (["KPI", "Qué mide", "Fuente", "Dueño"] if es
             else ["KPI", "What it measures", "Source", "Owner"]),
            [[kpi,
              ("Por definir con fórmula y unidad" if es else "To define with formula and unit"),
              ("Datos internos" if es else "Internal data"),
              ("Por asignar" if es else "To assign")]
             for kpi in plan["kpis"][:5]],
            [4.4, 7.2, 2.8, 2.2], theme, lang,
        )
        note = doc.add_paragraph()
        run = note.add_run(tr(lang, "needs_data") + ".")
        run.font.size = Pt(8)
        run.font.italic = True
        run.font.color.rgb = RGBColor.from_string(muted_hex)

    # ---- Findings -------------------------------------------------------
    doc.add_heading(tr(lang, "findings"), level=1)
    for item in plan["findings"]:
        doc.add_heading(item["title"], level=3)
        doc.add_paragraph(item["snippet"])
        source = doc.add_paragraph()
        source.paragraph_format.space_after = Pt(8)
        run = source.add_run(f"{tr(lang, 'source')}: {item['source']}")
        run.font.size = Pt(8)
        run.font.italic = True
        run.font.color.rgb = RGBColor.from_string(muted_hex)

    # ---- Deep dives -----------------------------------------------------
    for dive in plan["deep_dives"]:
        doc.add_heading(dive["topic"], level=1)
        for bullet in dive["bullets"]:
            paragraph = doc.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(4)
            paragraph.add_run(bullet)

    # ---- Framework ------------------------------------------------------
    framework = plan["framework"]
    doc.add_heading(f"{tr(lang, 'framework')}: {framework['name']}", level=1)
    doc.add_paragraph(framework["desc"])
    _docx_table(doc, ["#", tr(lang, "action")],
                [[str(index + 1), step] for index, step in enumerate(framework["steps"])],
                [1.6, 15.0], theme, lang, first_bold=False)

    # ---- Risks ----------------------------------------------------------
    doc.add_heading(tr(lang, "risks"), level=1)
    _docx_table(doc, [tr(lang, "risk"), tr(lang, "impact"), tr(lang, "mitigation")],
                [[item["risk"], item["level"], item["mitigation"]] for item in plan["risks"]],
                [4.7, 2.1, 9.8], theme, lang)

    # ---- Roadmap --------------------------------------------------------
    doc.add_page_break()
    doc.add_heading(tr(lang, "roadmap"), level=1)
    roadmap_rows = []
    for horizon in ("30", "60", "90"):
        label = f"{horizon} " + ("días" if es else "days")
        for index, action in enumerate(plan["actions"][horizon][:3]):
            roadmap_rows.append([
                label if index == 0 else "",
                action,
                "Por asignar" if es else "To assign",
                plan["kpis"][(len(roadmap_rows)) % len(plan["kpis"])],
                tr(lang, "pending"),
            ])
    _docx_table(doc, [tr(lang, "horizon"), tr(lang, "action"), tr(lang, "owner"), tr(lang, "metric"), tr(lang, "status")],
                roadmap_rows, [2.3, 7.3, 2.5, 2.6, 1.9], theme, lang)

    # ---- Recommendations -----------------------------------------------
    doc.add_heading(tr(lang, "recommendations"), level=1)
    for recommendation in plan["recommendations"]:
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(4)
        paragraph.add_run(recommendation)

    # ---- Sources and methodology ---------------------------------------
    doc.add_heading(tr(lang, "sources"), level=1)
    if plan["sources"]:
        for item in plan["sources"]:
            paragraph = doc.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(3)
            run = paragraph.add_run(f"{item['source']}: {item['title']} — ")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor.from_string(text_hex)
            _docx_hyperlink(paragraph, item["url"], item["url"], color=accent)
    else:
        doc.add_paragraph(tr(lang, "no_external_sources"))
    doc.add_heading(tr(lang, "methodology"), level=2)
    doc.add_paragraph(tr(lang, "assumptions_text"))

    # ---- Version control ------------------------------------------------
    doc.add_heading(tr(lang, "version_control"), level=1)
    _docx_table(doc, [tr(lang, "version"), tr(lang, "date"), tr(lang, "author"), tr(lang, "change")],
                [["1.0", plan["generated_at"], "Orunex", "Generación inicial del informe" if es else "Initial report generation"]],
                [2.0, 3.3, 3.2, 8.1], theme, lang)
    closing = doc.add_paragraph()
    closing.paragraph_format.space_before = Pt(0)
    closing.paragraph_format.space_after = Pt(0)
    closing.paragraph_format.line_spacing = Pt(1)
    closing_pr = closing._p.get_or_add_pPr()
    closing_rpr = OxmlElement("w:rPr")
    for tag in ("w:sz", "w:szCs"):
        node = OxmlElement(tag)
        node.set(qn("w:val"), "2")
        closing_rpr.append(node)
    closing_pr.append(closing_rpr)

    # ---- Update fields on open -----------------------------------------
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)

    doc.core_properties.title = plan["title"]
    doc.core_properties.author = "Orunex"
    doc.core_properties.subject = plan["domain_label"]
    doc.core_properties.comments = "Generated by Orunex Office Expert Studio"
    doc.save(path)
    return {
        "sections": len(plan["deep_dives"]) + 8,
        "tables": 5,
        "chart": bool(_chart_metrics(plan["metrics"])),
        "toc": True,
    }


# ---------------------------------------------------------------------------
# HTML / plain text / dispatch
# ---------------------------------------------------------------------------

def write_html(path: str, plan: dict[str, Any]) -> dict[str, Any]:
    lang = plan["lang"]
    es = lang == "es"
    theme = THEMES.get(plan.get("theme", "navy"), THEMES["navy"])

    def css_rgb(triple: Sequence[int]) -> str:
        return "rgb(%d,%d,%d)" % (int(triple[0]), int(triple[1]), int(triple[2]))

    accent = css_rgb(theme["accent"])
    accent2 = css_rgb(theme["accent2"])
    bg = css_rgb(theme["bg"])
    card = css_rgb(theme["card"])
    text = css_rgb(theme["content_text"])
    muted = css_rgb(theme["content_muted"])
    border = css_rgb(theme["border"])
    white = "#ffffff" if theme["dark"] else text

    parts: list[str] = [
        "<!doctype html><html lang='%s'><head><meta charset='utf-8'>" % lang,
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{html.escape(plan['title'])}</title>",
        "<style>",
        f":root{{--accent:{accent};--accent2:{accent2};--bg:{bg};--card:{card};--text:{text};--muted:{muted};--border:{border};}}",
        "*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Arial,sans-serif;color:var(--text);background:#f6f8fc;line-height:1.55}",
        ".page{max-width:1080px;margin:0 auto;background:#fff;box-shadow:0 12px 40px rgba(15,28,55,.08)}",
        f".cover{{background:var(--bg);color:{white};padding:64px 56px 48px}}",
        ".kicker{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent2);font-weight:700}",
        ".cover h1{font-size:42px;line-height:1.08;margin:18px 0 16px;font-weight:800}",
        ".cover p{color:rgba(255,255,255,.72);font-size:15px;margin:0}",
        ".chips{display:flex;gap:12px;flex-wrap:wrap;margin-top:32px}",
        f".chip{{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:12px 16px;min-width:150px}}",
        ".chip small{display:block;color:rgba(255,255,255,.62);font-size:10px;text-transform:uppercase;letter-spacing:.06em}",
        ".chip strong{display:block;color:var(--accent2);font-size:20px;margin-top:4px}",
        ".body{padding:40px 56px 56px}",
        "h2{font-size:23px;color:var(--accent);margin:34px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--border)}",
        "h3{font-size:15px;margin:20px 0 6px}",
        "p{margin:8px 0}ul{margin:8px 0 8px 20px;padding:0}li{margin:5px 0}",
        ".meta{color:var(--muted);font-size:12px}",
        f".kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}}",
        f".kpi{{background:var(--card);border:1px solid var(--border);border-top:4px solid var(--accent);border-radius:10px;padding:14px 16px}}",
        ".kpi span{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}",
        ".kpi strong{display:block;font-size:22px;color:var(--accent);margin-top:5px}",
        "table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}",
        "th{background:var(--accent);color:#fff;text-align:left;padding:9px 10px;font-weight:600}",
        "td{border-bottom:1px solid var(--border);padding:9px 10px;vertical-align:top}",
        "tr:nth-child(even) td{background:var(--card)}",
        f".finding{{background:var(--card);border-left:4px solid var(--accent);border-radius:8px;padding:14px 16px;margin:12px 0}}",
        f".source{{color:var(--muted);font-size:11px;margin-top:6px}}",
        f".note{{color:var(--muted);font-size:11px;margin-top:18px}}",
        f"a{{color:var(--accent)}}",
        "@media print{body{background:#fff}.page{box-shadow:none;max-width:none}}",
        "</style></head><body><div class='page'>",
        "<header class='cover'>",
        f"<div class='kicker'>{html.escape(tr(lang, 'executive_report'))} · {html.escape(plan['domain_label'])}</div>",
        f"<h1>{html.escape(plan['title'])}</h1>",
        f"<p>{html.escape('Análisis, hallazgos y plan de acción' if es else 'Analysis, findings and action plan')}</p>",
        f"<p style='margin-top:18px'>{html.escape(tr(lang, 'prepared_by'))} · {html.escape(plan['generated_at'])}</p>",
    ]
    if plan["metrics"]:
        parts.append("<div class='chips'>")
        for metric in plan["metrics"][:3]:
            parts.append(
                f"<div class='chip'><small>{html.escape(metric['label'])}</small>"
                f"<strong>{html.escape(metric['display'])}</strong></div>"
            )
        parts.append("</div>")
    parts.append("</header><main class='body'>")

    parts += [f"<h2>{html.escape(tr(lang, 'summary'))}</h2>", f"<p>{html.escape(plan['executive_summary'])}</p>"]
    parts.append(f"<h3>{html.escape(tr(lang, 'key_messages'))}</h3><ul>")
    parts += [f"<li>{html.escape(message)}</li>" for message in plan["key_messages"]]
    parts.append("</ul>")

    parts.append(f"<h2>{html.escape(tr(lang, 'context'))}</h2>")
    parts += [f"<p>{html.escape(paragraph)}</p>" for paragraph in plan["context"]]

    parts.append(f"<h2>{html.escape(tr(lang, 'kpi_panel'))}</h2>")
    if plan["metrics"]:
        parts.append("<div class='kpis'>")
        for metric in plan["metrics"]:
            parts.append(
                f"<div class='kpi'><span>{html.escape(metric['label'])}</span>"
                f"<strong>{html.escape(metric['display'])}</strong></div>"
            )
        parts.append("</div>")
        chart_metrics = _chart_metrics(plan["metrics"])
        if chart_metrics:
            parts.append("<table><thead><tr><th>%s</th><th>%s</th></tr></thead><tbody>" % (
                html.escape(tr(lang, "metric")), html.escape(tr(lang, "value"))))
            for metric in chart_metrics:
                parts.append(f"<tr><td>{html.escape(metric['label'])}</td><td>{html.escape(metric['display'])}</td></tr>")
            parts.append("</tbody></table>")
        parts.append(f"<p class='note'>{html.escape(tr(lang, 'data_from_request'))}. {html.escape(tr(lang, 'sensitivity_note'))}</p>")
    else:
        parts.append(f"<p>{html.escape(tr(lang, 'no_metrics'))}. {html.escape(tr(lang, 'recommended_kpis'))}: "
                     f"{html.escape(', '.join(plan['kpis'][:5]))}.</p>")

    parts.append(f"<h2>{html.escape(tr(lang, 'findings'))}</h2>")
    for item in plan["findings"]:
        parts.append("<div class='finding'>")
        parts.append(f"<h3>{html.escape(item['title'])}</h3>")
        parts.append(f"<p>{html.escape(item['snippet'])}</p>")
        parts.append(f"<div class='source'>{html.escape(tr(lang, 'source'))}: {html.escape(item['source'])}</div>")
        parts.append("</div>")

    for dive in plan["deep_dives"]:
        parts.append(f"<h2>{html.escape(dive['topic'])}</h2><ul>")
        parts += [f"<li>{html.escape(bullet)}</li>" for bullet in dive["bullets"]]
        parts.append("</ul>")

    framework = plan["framework"]
    parts.append(f"<h2>{html.escape(tr(lang, 'framework'))}: {html.escape(framework['name'])}</h2>")
    parts.append(f"<p>{html.escape(framework['desc'])}</p><table><tbody>")
    for index, step in enumerate(framework["steps"]):
        parts.append(f"<tr><td style='width:36px;font-weight:700'>{index + 1}</td><td>{html.escape(step)}</td></tr>")
    parts.append("</tbody></table>")

    parts.append(f"<h2>{html.escape(tr(lang, 'risks'))}</h2><table><thead><tr>"
                 f"<th>{html.escape(tr(lang, 'risk'))}</th><th>{html.escape(tr(lang, 'impact'))}</th>"
                 f"<th>{html.escape(tr(lang, 'mitigation'))}</th></tr></thead><tbody>")
    for item in plan["risks"]:
        parts.append(f"<tr><td><strong>{html.escape(item['risk'])}</strong></td><td>{html.escape(item['level'])}</td>"
                     f"<td>{html.escape(item['mitigation'])}</td></tr>")
    parts.append("</tbody></table>")

    parts.append(f"<h2>{html.escape(tr(lang, 'roadmap'))}</h2><table><thead><tr>"
                 f"<th>{html.escape(tr(lang, 'horizon'))}</th><th>{html.escape(tr(lang, 'action'))}</th>"
                 f"<th>{html.escape(tr(lang, 'owner'))}</th><th>{html.escape(tr(lang, 'status'))}</th>"
                 f"</tr></thead><tbody>")
    for horizon in ("30", "60", "90"):
        label = f"{horizon} " + ("días" if es else "days")
        for index, action in enumerate(plan["actions"][horizon][:3]):
            parts.append(f"<tr><td>{html.escape(label if index == 0 else '')}</td><td>{html.escape(action)}</td>"
                         f"<td>{html.escape('Por asignar' if es else 'To assign')}</td>"
                         f"<td>{html.escape(tr(lang, 'pending'))}</td></tr>")
    parts.append("</tbody></table>")

    parts.append(f"<h2>{html.escape(tr(lang, 'recommendations'))}</h2><ul>")
    parts += [f"<li>{html.escape(item)}</li>" for item in plan["recommendations"]]
    parts.append("</ul>")

    parts.append(f"<h2>{html.escape(tr(lang, 'sources'))}</h2>")
    if plan["sources"]:
        parts.append("<ul>")
        for item in plan["sources"]:
            parts.append(f"<li><a href='{html.escape(item['url'])}' target='_blank' rel='noopener'>"
                         f"{html.escape(item['source'])}</a>: {html.escape(item['title'])}</li>")
        parts.append("</ul>")
    else:
        parts.append(f"<p>{html.escape(tr(lang, 'no_external_sources'))}</p>")
    parts.append(f"<p class='note'>{html.escape(tr(lang, 'assumptions_text'))}</p>")
    parts.append("</main></div></body></html>")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts))
    return {"sections": len(plan["deep_dives"]) + 7, "chart": bool(_chart_metrics(plan["metrics"]))}


def write_text(path: str, plan: dict[str, Any]) -> dict[str, Any]:
    lang = plan["lang"]
    es = lang == "es"
    lines: list[str] = [plan["title"], "=" * len(plan["title"]), ""]
    lines += [f"{tr(lang, 'executive_report')} · Orunex · {plan['generated_at']}", "", tr(lang, "summary").upper(), ""]
    lines += [plan["executive_summary"], ""]
    lines += [tr(lang, "key_messages").upper(), ""]
    lines += [f"- {message}" for message in plan["key_messages"]]
    lines += ["", tr(lang, "context").upper(), ""]
    lines += [paragraph for paragraph in plan["context"]]
    if plan["metrics"]:
        lines += ["", tr(lang, "kpi_panel").upper(), ""]
        lines += [f"- {m['label']}: {m['display']}" for m in plan["metrics"]]
    lines += ["", tr(lang, "findings").upper(), ""]
    for item in plan["findings"]:
        lines += [item["title"], item["snippet"], f"{tr(lang, 'source')}: {item['source']}", ""]
    for dive in plan["deep_dives"]:
        lines += [dive["topic"].upper(), ""]
        lines += [f"- {bullet}" for bullet in dive["bullets"]]
        lines.append("")
    lines += [f"{tr(lang, 'framework').upper()}: {plan['framework']['name']}", plan["framework"]["desc"], ""]
    lines += [f"- {step}" for step in plan["framework"]["steps"]]
    lines += ["", tr(lang, "risks").upper(), ""]
    lines += [f"- {item['risk']} ({item['level']}): {item['mitigation']}" for item in plan["risks"]]
    lines += ["", tr(lang, "roadmap").upper(), ""]
    for horizon in ("30", "60", "90"):
        lines.append(f"{horizon} " + ("días" if es else "days"))
        lines += [f"  - {action}" for action in plan["actions"][horizon]]
    lines += ["", tr(lang, "recommendations").upper(), ""]
    lines += [f"- {item}" for item in plan["recommendations"]]
    lines += ["", tr(lang, "sources").upper(), ""]
    if plan["sources"]:
        lines += [f"- {item['source']}: {item['title']} ({item['url']})" for item in plan["sources"]]
    else:
        lines.append(tr(lang, "no_external_sources"))
    lines += ["", tr(lang, "assumptions_text")]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).strip() + "\n")
    return {"sections": len(plan["deep_dives"]) + 7}


def build_artifact(path: str, kind: str, plan: dict[str, Any]) -> dict[str, Any]:
    kind = str(kind or "").lower().lstrip(".")
    if kind == "pptx":
        return write_pptx(path, plan)
    if kind == "xlsx":
        return write_xlsx(path, plan)
    if kind == "docx":
        return write_docx(path, plan)
    if kind == "html":
        return write_html(path, plan)
    if kind == "txt":
        return write_text(path, plan)
    if kind == "md":
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(plan_to_markdown(plan))
        return {"sections": len(plan["deep_dives"]) + 7}
    raise ValueError(f"Office Expert cannot build kind: {kind}")


# === APPEND_POINT ===
