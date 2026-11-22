"""Static, source-linked catalogue of methods tools (C5). No network. Nothing here is a bibliographic claim:
each entry carries a source URL and `verified: None` until Laura / the verifier opens it (LREQ-C5-RET)."""

# topic -> tool ids applicable. Designs are the study-design keys Laura can declare.
DESIGNS = {
    "rct": "Ensayo controlado aleatorizado (paralelo, por conglomerados o cruzado)",
    "nrsi": "Estudio no aleatorizado de intervenciones (cohortes, antes-después controlado)",
    "quasi": "Estudio cuasi-experimental",
    "cohort": "Estudio de cohortes (observacional)",
    "case_control": "Estudio de casos y controles",
    "cross_sectional": "Estudio transversal",
    "case_series": "Serie de casos",
    "qualitative": "Estudio cualitativo",
}

TOOLS = {
    "rob2": {
        "name": "RoB 2 (Cochrane Risk of Bias 2)", "kind": "rob",
        "topics": ["rob:rct"],
        "url": "https://www.riskofbias.info/welcome/rob-2-0-tool",
        "note_es": "Herramienta de riesgo de sesgo para ensayos aleatorizados; existen variantes para ensayos por conglomerados y cruzados. Evalúa dominios de sesgo por resultado.",
    },
    "pedro": {
        "name": "Escala PEDro", "kind": "quality",
        "topics": ["rob:rct"],
        "url": "https://pedro.org.au/english/resources/pedro-scale/",
        "note_es": "Mide calidad metodológica (y de comunicación) de ensayos de fisioterapia. NO es una herramienta de riesgo de sesgo en sentido estricto y no sustituye a RoB 2; puede usarse como complemento si Laura lo decide.",
    },
    "robins_i": {
        "name": "ROBINS-I (versión V2; confirmar la versión vigente)", "kind": "rob",
        "topics": ["rob:nrsi", "rob:quasi", "rob:cohort"],
        "url": "https://www.riskofbias.info/welcome/home/current-version-of-robins-i",
        "note_es": "Riesgo de sesgo en estudios no aleatorizados de intervenciones, comparado con un ensayo diana hipotético. Confirmar en la fuente cuál es la versión vigente.",
    },
    "jbi_rct": {
        "name": "JBI: lista de verificación para ensayos aleatorizados", "kind": "checklist",
        "topics": ["rob:rct"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Alternativa de valoración crítica de JBI; si el equipo ya trabaja con JBI para otros diseños.",
    },
    "jbi_quasi": {
        "name": "JBI: lista para estudios cuasi-experimentales", "kind": "checklist",
        "topics": ["rob:quasi", "rob:nrsi"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Valoración crítica de JBI para diseños cuasi-experimentales.",
    },
    "jbi_cohort": {
        "name": "JBI: lista para estudios de cohortes", "kind": "checklist",
        "topics": ["rob:cohort"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Valoración crítica de JBI para cohortes.",
    },
    "jbi_case_control": {
        "name": "JBI: lista para casos y controles", "kind": "checklist",
        "topics": ["rob:case_control"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Valoración crítica de JBI para casos y controles.",
    },
    "jbi_cross_sectional": {
        "name": "JBI: lista para estudios transversales analíticos", "kind": "checklist",
        "topics": ["rob:cross_sectional"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Valoración crítica de JBI para estudios transversales.",
    },
    "jbi_case_series": {
        "name": "JBI: lista para series de casos", "kind": "checklist",
        "topics": ["rob:case_series"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Valoración crítica de JBI para series de casos.",
    },
    "jbi_qualitative": {
        "name": "JBI: lista para investigación cualitativa", "kind": "checklist",
        "topics": ["rob:qualitative"], "url": "https://jbi.global/critical-appraisal-tools",
        "note_es": "Valoración crítica de JBI para estudios cualitativos.",
    },
    "grade": {
        "name": "GRADE", "kind": "certainty", "topics": ["grade"],
        "url": "https://www.gradeworkinggroup.org/",
        "note_es": "Certeza de la evidencia por desenlace (alta, moderada, baja, muy baja). Se parte de la certeza según el diseño y se baja por riesgo de sesgo, inconsistencia, evidencia indirecta, imprecisión y sesgo de publicación; puede subir por efecto grande, gradiente dosis-respuesta o confusión residual que apunta en sentido contrario.",
    },
    "swim_narrative": {
        "name": "Síntesis narrativa estructurada (guía SWiM)", "kind": "synthesis", "topics": ["synthesis"],
        "url": "https://www.equator-network.org/reporting-guidelines/swim-synthesis-without-meta-analysis/",
        "note_es": "Opción cuando no es apropiado combinar estimaciones: agrupar estudios, indicar la métrica del efecto, el método de síntesis y cómo se explorará la heterogeneidad.",
    },
    "meta_analysis": {
        "name": "Metaanálisis (Manual Cochrane)", "kind": "synthesis", "topics": ["synthesis"],
        "url": "https://training.cochrane.org/handbook",
        "note_es": "Opción condicionada a que haya estudios suficientemente similares (población, intervención, desenlace). Debe fijarse en el protocolo el modelo, la medida del efecto y cómo se evaluará la heterogeneidad. Las decisiones numéricas las toma Laura con su tutor.",
    },
    "tidier": {
        "name": "TIDieR (descripción de intervenciones)", "kind": "reporting", "topics": ["reporting_exercise"],
        "url": "https://www.equator-network.org/reporting-guidelines/tidier/",
        "note_es": "Plantilla para extraer cómo se describe la intervención: nombre, justificación, materiales, procedimientos, quién la aplica, cómo, dónde, cuándo y cuánto, adaptación, modificaciones y fidelidad.",
    },
    "cert": {
        "name": "CERT (Consensus on Exercise Reporting Template)", "kind": "reporting", "topics": ["reporting_exercise"],
        "url": "https://www.equator-network.org/reporting-guidelines/consensus-based-checklist-for-reporting-of-exercise-trials-cert/",
        "note_es": "Lista específica para describir programas de ejercicio: materiales, profesional, entrega, lugar, cuándo y cuánto, adaptación y fidelidad.",
    },
}

SIMPLE_TOPICS = ("grade", "synthesis", "reporting_exercise")


def tools_for(topic):
    return {k: v for k, v in TOOLS.items() if topic in v["topics"]}


def topics_for_designs(designs, exercise=False):
    t = ["rob:%s" % d for d in designs] + ["grade", "synthesis"]
    if exercise:
        t.append("reporting_exercise")
    return t
