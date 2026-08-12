"""
Gerador de queries multi-base a partir do config.py (fonte única de verdade).

Você edita APENAS as listas de palavras-chave em `config.py`
(CORE_ET0, SOFTWARE_SPECIFIC, CORE_IRRIGATION, METHOD_PROB, TELECONNECTION)
e este script gera, para CADA base, a string de busca já na sintaxe nativa,
pronta para colar. Assim a mesma lógica é aplicada em todas as bases e a
estratégia fica documentada e reprodutível (requisito PRISMA).

Saídas:
  results/queries/queries_all.md         -> documento único (todas as bases)
  results/queries/<base>_blocoA.txt      -> string pronta p/ colar (Bloco A)
  results/queries/<base>_blocoB.txt      -> string pronta p/ colar (Bloco B)

Uso:
  python scripts/gen_queries.py

Observações de projeto:
  - Bloco A: núcleo de ET0 EXIGIDO no título  AND  termos de ferramenta no
    título/resumo/keywords.
  - Bloco B: irrigação  AND  método probabilístico  AND  teleconexão
    (todos no título/resumo/keywords).
  - Algumas bases têm limites de sintaxe (nº de operadores, tamanho): para
    Google Scholar e ScienceDirect também geramos uma versão COMPACTA.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

OUT_DIR = os.path.join(C.PROJECT_ROOT, "results", "queries")
os.makedirs(OUT_DIR, exist_ok=True)

Y0, Y1 = C.YEAR_MIN, C.YEAR_MAX

# Núcleo COMPACTO de ET0 (para bases com limite de operadores/tamanho).
CORE_ET0_COMPACT = [
    "reference evapotranspiration", "evapotranspiration", "ET0", "ETo",
    "crop water requirement",
]
# Termos de ferramenta COMPACTOS (os mais discriminantes).
TOOLS_COMPACT = [
    "software", "model", "decision support system", "web tool", "platform",
    "package", "google earth engine", "machine learning", "remote sensing",
]


# --------------------------------------------------------------------------
# Utilitários de formatação
# --------------------------------------------------------------------------
def q(term):
    """Coloca o termo entre aspas se tiver espaço/hífen; senão deixa cru."""
    t = term.strip()
    if any(ch in t for ch in (" ", "-")):
        return f'"{t}"'
    return t


def or_join(terms, quote=True):
    items = [q(t) if quote else t for t in terms]
    return " OR ".join(items)


def dedent_terms(terms):
    """Remove duplicados preservando a ordem (case-insensitive)."""
    seen, out = set(), []
    for t in terms:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            out.append(t)
    return out


CORE = dedent_terms(C.CORE_ET0)
TOOLS = dedent_terms(C.SOFTWARE_SPECIFIC)          # TOOL_TYPES + NAMED_TOOLS
IRR = dedent_terms(C.CORE_IRRIGATION)
METH = dedent_terms(C.METHOD_PROB)
TELE = dedent_terms(C.TELECONNECTION)


# --------------------------------------------------------------------------
# Formatadores por base
# --------------------------------------------------------------------------
def scopus():
    a = (f'TITLE({or_join(CORE)}) '
         f'AND TITLE-ABS-KEY({or_join(TOOLS)}) '
         f'AND PUBYEAR > {Y0 - 1} AND PUBYEAR < {Y1 + 1} '
         f'AND (LIMIT-TO(DOCTYPE,"ar")) AND (LIMIT-TO(LANGUAGE,"English"))')
    b = (f'TITLE-ABS-KEY(({or_join(IRR)}) AND ({or_join(METH)}) '
         f'AND ({or_join(TELE)})) '
         f'AND PUBYEAR > {Y0 - 1} AND PUBYEAR < {Y1 + 1} '
         f'AND (LIMIT-TO(DOCTYPE,"ar")) AND (LIMIT-TO(LANGUAGE,"English"))')
    return a, b


def wos():
    # Web of Science Core Collection — Advanced Search. Defina o Timespan
    # (1990-2026) e o idioma no próprio formulário, OU use PY= e LA=.
    a = (f'TI=({or_join(CORE)}) AND TS=({or_join(TOOLS)}) '
         f'AND PY=({Y0}-{Y1}) AND LA=(English)')
    b = (f'TS=(({or_join(IRR)}) AND ({or_join(METH)}) AND ({or_join(TELE)})) '
         f'AND PY=({Y0}-{Y1}) AND LA=(English)')
    return a, b


def ieee():
    # IEEE Xplore — Command Search. Campos: "Document Title", "Abstract",
    # "Author Keywords", "All Metadata". Filtre ano/tipo na barra lateral.
    tools_meta = " OR ".join(f'"All Metadata":{q(t)}' for t in TOOLS)
    core_title = " OR ".join(f'"Document Title":{q(t)}' for t in CORE)
    a = f'({core_title}) AND ({tools_meta})'
    irr_m = " OR ".join(f'"All Metadata":{q(t)}' for t in IRR)
    met_m = " OR ".join(f'"All Metadata":{q(t)}' for t in METH)
    tel_m = " OR ".join(f'"All Metadata":{q(t)}' for t in TELE)
    b = f'({irr_m}) AND ({met_m}) AND ({tel_m})'
    return a, b


def sciencedirect():
    # ScienceDirect Advanced Search: NO máx. 8 conectores booleanos, sem
    # parênteses aninhados, sem curinga. Geramos versão COMPACTA para o campo
    # "Title, abstract, keywords". Rode variações se precisar de mais cobertura.
    core = or_join(CORE_ET0_COMPACT)
    tools = or_join(TOOLS_COMPACT)
    a = f'({core}) AND ({tools})'
    b = ('("irrigation scheduling" OR "water balance") '
         'AND (Bayesian OR stochastic OR probabilistic OR uncertainty) '
         'AND (ENSO OR teleconnection OR "sea surface temperature")')
    return a, b


def springer():
    # SpringerLink Advanced Search / caixa de busca: suporta AND/OR/NOT e aspas.
    # Restrinja a data e o tipo (Article) nos filtros da esquerda.
    a = f'({or_join(CORE)}) AND ({or_join(TOOLS)})'
    b = (f'({or_join(IRR)}) AND ({or_join(METH)}) AND ({or_join(TELE)})')
    return a, b


def google_scholar():
    # Google Scholar: sem booleano complexo, OR deve ser MAIÚSCULO, ~256 chars.
    # Use `allintitle:` p/ o núcleo e rode variações. RECOMENDADO: rodar via
    # "Publish or Perish" (Harzing) e exportar CSV/RIS. Ver o guia.
    a = ('allintitle: evapotranspiration '
         '(software OR model OR platform OR "decision support")')
    a2 = ('"reference evapotranspiration" '
          '(software OR "decision support system" OR "google earth engine" '
          'OR "machine learning")')
    b = ('"irrigation scheduling" (Bayesian OR stochastic OR probabilistic) '
         '(ENSO OR teleconnection OR "sea surface temperature")')
    return a, b, a2


def discovery():
    # Serviço de descoberta institucional (Primo/EBSCO/EDS).
    # ATENÇÃO: Kanchan et al. usaram a "Murdoch University Library" porque são
    # de Murdoch. Você é da USP -> use o "Portal de Busca Integrada da USP"
    # e/ou o "Portal de Periódicos CAPES", que são o equivalente institucional.
    a = f'({or_join(CORE)}) AND ({or_join(TOOLS)})'
    b = f'({or_join(IRR)}) AND ({or_join(METH)}) AND ({or_join(TELE)})'
    return a, b


# --------------------------------------------------------------------------
# Montagem das saídas
# --------------------------------------------------------------------------
def write_txt(name, content):
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")


def main():
    sc_a, sc_b = scopus()
    wo_a, wo_b = wos()
    ie_a, ie_b = ieee()
    sd_a, sd_b = sciencedirect()
    sp_a, sp_b = springer()
    gs_a, gs_b, gs_a2 = google_scholar()
    di_a, di_b = discovery()

    files = {
        "scopus_blocoA.txt": sc_a, "scopus_blocoB.txt": sc_b,
        "wos_blocoA.txt": wo_a, "wos_blocoB.txt": wo_b,
        "ieee_blocoA.txt": ie_a, "ieee_blocoB.txt": ie_b,
        "sciencedirect_blocoA.txt": sd_a, "sciencedirect_blocoB.txt": sd_b,
        "springerlink_blocoA.txt": sp_a, "springerlink_blocoB.txt": sp_b,
        "googlescholar_blocoA.txt": gs_a, "googlescholar_blocoB.txt": gs_b,
        "googlescholar_blocoA_alt.txt": gs_a2,
        "discovery_blocoA.txt": di_a, "discovery_blocoB.txt": di_b,
    }
    for name, content in files.items():
        write_txt(name, content)

    md = []
    md.append("# Queries geradas por base\n")
    md.append(f"> Geradas automaticamente por `scripts/gen_queries.py` a partir "
              f"de `config.py`. Janela: **{Y0}–{Y1}**. **Não edite à mão** — "
              f"edite as listas no `config.py` e rode o script de novo.\n")
    md.append("Convenção: **Bloco A** = ferramentas/software de ET₀; "
              "**Bloco B** = irrigação sob incerteza + teleconexões.\n")

    def block(title, a, b, note=""):
        s = [f"## {title}\n"]
        if note:
            s.append(note + "\n")
        s.append("**Bloco A**\n\n```\n" + a + "\n```\n")
        s.append("**Bloco B**\n\n```\n" + b + "\n```\n")
        return "\n".join(s)

    md.append(block("Scopus (Advanced Search API / web)", sc_a, sc_b,
                    "Cole no Advanced Search do Scopus (ou já vai via API no "
                    "`01_collect_scopus.py`). `ar` = article; ajuste se quiser "
                    "incluir mais tipos."))
    md.append(block("Web of Science (Core Collection · Advanced Search)", wo_a, wo_b,
                    "Defina *Editions* e *Timespan* no formulário. Exporte em "
                    "BibTeX (Full Record), ≤1000 por lote."))
    md.append(block("IEEE Xplore (Command Search)", ie_a, ie_b,
                    "Cole no **Command Search**. Filtre ano e *Content Type = "
                    "Journals* na barra lateral. Ou use a API (`02_collect_ieee.py`)."))
    md.append(block("ScienceDirect (Advanced Search) — versão COMPACTA", sd_a, sd_b,
                    "⚠️ ScienceDirect limita a **8 operadores booleanos**, sem "
                    "curinga e sem parênteses aninhados. Use no campo *Title, "
                    "abstract, keywords*. Rode variações se precisar de recall."))
    md.append(block("SpringerLink (Advanced Search)", sp_a, sp_b,
                    "Cole na caixa de busca (suporta AND/OR/NOT e aspas). "
                    "Filtre *Content Type = Article* e a data à esquerda. "
                    "Alternativa reprodutível: **Springer Nature Metadata API**."))
    md.append(block("Google Scholar (busca simples)", gs_a, gs_b,
                    "Sem booleano complexo; `OR` em MAIÚSCULAS; ~256 caracteres. "
                    "**Recomendado**: rodar via *Publish or Perish* e exportar CSV/RIS.\n\n"
                    "Variação alternativa do Bloco A:\n\n```\n" + gs_a2 + "\n```"))
    md.append(block("Descoberta institucional (USP / CAPES) — no lugar de Murdoch",
                    di_a, di_b,
                    "Você é da USP: use o **Portal de Busca Integrada da USP** e/ou "
                    "o **Portal de Periódicos CAPES** como equivalente ao discovery "
                    "de Murdoch usado por Kanchan et al."))

    with open(os.path.join(OUT_DIR, "queries_all.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"[OK] {len(files)} arquivos .txt + queries_all.md em {OUT_DIR}")
    for name in sorted(files):
        print("   -", name)


if __name__ == "__main__":
    main()
