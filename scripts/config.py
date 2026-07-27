"""
Configuração central do pipeline bibliométrico (EVAonline / Probabilistic ET0).

Estratégia de busca multi-base em Python (sem R):
  - OpenAlex  ......... fonte PRIMÁRIA (gratuita, aberta, reprodutível sem chave)
  - Scopus    ......... confirmatória (requer chave institucional Elsevier)
  - Web of Science .... confirmatória (requer chave Clarivate, porém a USP não fornece, tenho que pesquisar manualemente)
  - Crossref .......... complementar (gratuita)
  - Semantic Scholar .. complementar (gratuita; sujeita a rate-limit sem chave)

Dois blocos temáticos, espelhando os dois gaps do artigo:
  BLOCO A - Software & Data Fusion Gap  -> justifica o EVAonline
  BLOCO B - Stochastic Decision Gap     -> justifica o método Bayesiano de irrigação
"""

import os

# ----------------------------------------------------------------------
# Diretórios
# ----------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
TABLES_DIR = os.path.join(PROJECT_ROOT, "results", "tables")
FIGURES_DIR = os.path.join(PROJECT_ROOT, "results", "figures")
for _d in (RAW_DIR, PROCESSED_DIR, TABLES_DIR, FIGURES_DIR):
    os.makedirs(_d, exist_ok=True)

# ----------------------------------------------------------------------
# Janela temporal
# ----------------------------------------------------------------------
YEAR_MIN = 1990
YEAR_MAX = 2026

# ----------------------------------------------------------------------
# Identificação (OpenAlex "polite pool" e Crossref pedem e-mail de contato)
# ----------------------------------------------------------------------
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "angelassilviane@gmail.com")

# ----------------------------------------------------------------------
# Chaves de API (definir como variáveis de ambiente; NUNCA versionar)
#   export SCOPUS_API_KEY="..."
#   export WOS_API_KEY="..."
#   export S2_API_KEY="..."   (opcional)
# ----------------------------------------------------------------------
SCOPUS_API_KEY = os.environ.get("SCOPUS_API_KEY")
WOS_API_KEY = os.environ.get("WOS_API_KEY")
S2_API_KEY = os.environ.get("S2_API_KEY")

# ----------------------------------------------------------------------
# Blocos de termos de busca
#   Cada bloco é uma lista de "grupos" combinados em AND;
#   dentro de cada grupo os termos entram em OR.
# ----------------------------------------------------------------------
CORE_ET0 = [
    "evapotranspiration", "reference evapotranspiration", "ET0", "ETo",
    "potential evapotranspiration", "actual evapotranspiration",
    "crop water requirement",
]
CORE_IRRIGATION = [
    "irrigation scheduling", "irrigation depth", "soil water balance",
    "root zone depletion", "soil moisture", "water balance",
]
METHOD_PROB = [
    "Bayesian", "stochastic", "probabilistic", "uncertainty quantification",
    "MCMC", "posterior", "Kalman filter", "data assimilation", "ensemble",
]
# Termos de TIPO de ferramenta que calcula ET (cobre TODOS os tipos:
# web/app, API, nuvem/analytics, crop model, balanço de energia/sensoriamento
# remoto, DSS, pacotes de programação, desktop). Objetivo: máxima cobertura,
# independentemente de como a ferramenta produz o resultado.
TOOL_TYPES = [
    # web / app / online
    "software", "web-based tool", "online tool", "web application", "web platform",
    "mobile application", "mobile app", "web service", "online calculator",
    "graphical user interface", "user interface",
    # nuvem / analytics / API
    "cloud-based", "cloud platform", "google earth engine", "weather API",
    "climate data API", "analytics platform",
    # crop model / DSS
    "crop model", "crop simulation model", "crop growth model",
    "decision support system", "irrigation scheduling tool",
    # balanço de energia / sensoriamento remoto
    "energy balance model", "surface energy balance", "remote sensing model",
    # pacotes de programação / desktop
    "R package", "python package", "open-source", "open source software",
    "software package", "computer program", "toolbox", "toolkit",
    "desktop software",
]
# Nomes de ferramentas/softwares conhecidos de ET.
NAMED_TOOLS = [
    "CROPWAT", "AquaCrop", "DSSAT", "SEBAL", "METRIC model", "SSEBop", "SEBS",
    "OpenET", "Climate Engine", "Open-Meteo", "REF-ET", "SIMDualKc", "pyfao56",
    "PyETo", "EToCalculator", "DataMetProcess",
]
# Lista combinada usada na busca do Bloco A (título ET0 + este OR-group).
SOFTWARE_SPECIFIC = TOOL_TYPES + NAMED_TOOLS

# Taxonomia de TIPO de ferramenta (reproduz a coluna "Type" da tabela EVAonline,
# mas aplicada a todo o corpus). Prioridade de cima para baixo na classificação.
# Web/nuvem vêm ANTES de "programming/desktop" para que uma plataforma web
# open-source (ex.: EVAonline) seja classificada como Web tool, não como pacote.
TOOL_TYPE_TAXONOMY = [
    ("Remote-sensing / energy-balance model",
     ["sebal", "metric model", "ssebop", "sebs", "energy balance",
      "surface energy balance", "remote sensing model", "satellite-based"]),
    ("Crop model / irrigation DSS",
     ["cropwat", "aquacrop", "dssat", "crop model", "crop simulation",
      "crop growth model", "decision support system", "irrigation scheduling tool"]),
    ("Cloud / analytics platform",
     ["google earth engine", "climate engine", "openet", "cloud-based",
      "cloud platform", "analytics platform"]),
    ("Web tool / online / API",
     ["web-based tool", "online tool", "web application", "web platform",
      "web service", "online calculator", "weather api", "climate data api",
      "mobile app", "mobile application", "open-meteo", "etocalculator", "ref-et"]),
    ("Programming package / toolbox",
     ["r package", "python package", "pyfao56", "pyeto", "toolbox", "toolkit",
      "datmetprocess", "datametprocess"]),
    ("Desktop / generic software",
     ["desktop software", "computer program", "software package", "software"]),
]
TELECONNECTION = [
    "ENSO", "El Nino", "La Nina", "teleconnection", "climatological prior",
    "climate risk", "sea surface temperature", "oceanic index",
]

# ----------------------------------------------------------------------
# Classificação de MÉTODO (dimensão minerada: determinístico vs não)
# ----------------------------------------------------------------------
DET_METHODS = [
    "penman-monteith", "penman monteith", "fao-56", "fao 56", "fao56",
    "hargreaves", "priestley-taylor", "blaney-criddle", "thornthwaite",
    "makkink", "turc", "jensen-haise", "mass transfer", "radiation-based",
    "temperature-based", "empirical equation", "empirical model",
    "pan evaporation",
    # modelos físicos de balanço de energia / sensoriamento remoto (determinísticos)
    "sebal", "ssebop", "sebs", "energy balance", "surface energy balance",
    "metric model", "cropwat", "aquacrop", "dssat", "swat model",
]
NONDET_METHODS = [
    "machine learning", "deep learning", "neural network", "artificial neural",
    "random forest", "support vector", "xgboost", "gradient boosting",
    "bayesian", "stochastic", "probabilistic", "gaussian process", "ensemble",
    "fuzzy", "genetic algorithm", "lstm", "uncertainty", "monte carlo",
    "extreme learning", "adaptive neuro",
    # assimilação / fusão de dados (Kalman etc.) — abordagens não-determinísticas
    "kalman", "data assimilation", "data fusion", "state-space", "state space",
    "particle filter",
]

# ----------------------------------------------------------------------
# Blocos temáticos (dois eixos).
#   "title": grupos que DEVEM aparecer no título (precisão); None = ignorar
#   "abs":   grupos no título+resumo (title-abs-key)
# ----------------------------------------------------------------------
# EIXO A — Software/ferramentas/aplicativos que calculam ETo
BLOCK_A = {
    "name": "ETo_Software_Tools",
    "title": [CORE_ET0],
    "abs": [SOFTWARE_SPECIFIC],
}
# EIXO B — Irrigação sob incerteza + teleconexões
BLOCK_B = {
    "name": "Irrigation_Decision",
    "title": None,
    "abs": [CORE_IRRIGATION, METHOD_PROB, TELECONNECTION],
}

BLOCKS = [BLOCK_A, BLOCK_B]

# Contraste macro (Tier 1): determinístico vs probabilístico (só volume)
MACRO_DETERMINISTIC = (
    '("irrigation scheduling" OR "water balance") '
    'AND ("FAO-56" OR "Penman-Monteith" OR "AquaCrop" OR "CropWat")'
)
MACRO_PROBABILISTIC = (
    '("irrigation scheduling" OR "water balance") '
    'AND ("Bayesian" OR "stochastic" OR "probabilistic" OR "uncertainty")'
)
