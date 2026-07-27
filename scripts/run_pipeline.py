"""
Orquestrador do pipeline — roda todo o projeto em ordem.

Use quando alterar as palavras-chave (config.py) e quiser atualizar TODO o projeto:
dados + tabelas + figuras.

    python scripts/run_pipeline.py            # recoleta do zero e regenera tudo
    python scripts/run_pipeline.py --no-reset # NÃO recoleta; só reprocessa/refaz figuras
    python scripts/run_pipeline.py --no-collect  # pula coleta (usa dados já baixados)

Pré-requisitos:
    export CONTACT_EMAIL="voce@exemplo.com"     (OpenAlex/Crossref)
    export SCOPUS_API_KEY="..."                  (para a etapa Scopus)
    (Web of Science: coloque os arquivos exportados em data/raw/wos_export/)
"""

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), "data", "raw")
PY = sys.executable


def run(script):
    print(f"\n===== {script} =====")
    r = subprocess.run([PY, os.path.join(HERE, script)], cwd=HERE)
    if r.returncode != 0:
        print(f"!! {script} terminou com código {r.returncode}")
    return r.returncode


def reset_raw():
    print("Limpando dados brutos antigos (data/raw)...")
    pats = ["openalex_*.csv", "openalex_*.cursor", "scopus_*.csv",
            "scopus_*.cursor", "crossref_raw.csv"]
    for p in pats:
        for f in glob.glob(os.path.join(RAW, p)):
            try:
                os.remove(f)
            except OSError as e:
                print(f"  (não removeu {os.path.basename(f)}: {e})")
    print("  (WoS export e wos_raw.csv preservados)")


def main():
    args = set(sys.argv[1:])
    do_reset = "--no-reset" not in args and "--no-collect" not in args
    do_collect = "--no-collect" not in args

    if do_reset:
        reset_raw()

    if do_collect:
        run("00_collect_openalex.py")          # OpenAlex (gratuito)
        run("01_collect_scopus.py")            # Scopus (precisa SCOPUS_API_KEY)
        run("11_ingest_wos_export.py")         # WoS (se houver export em wos_export/)

    # processamento + análise
    run("04_merge_dedup_prisma.py")            # fusão + dedup + PRISMA
    run("05_bibliometric_analysis.py")         # tabelas (inclui instituições/OA)
    run("12_journal_metrics.py")               # métricas de periódico (impacto)

    # figuras
    run("06_generate_figures.py")              # básicas + método/tipo
    run("07_advanced_figures.py")              # mapas, redes, nuvem, Sankey
    run("13_metadata_figures.py")              # instituições, OA, impacto
    run("08_prisma_diagram.py")                # fluxograma PRISMA

    # apoio à síntese e triagem
    run("09_top_cited_by_category.py")         # semente do estado da arte
    run("10_screening_prefilter.py")           # pré-filtro (99 duvidosos)
    run("14_relevance_prescreen.py")           # pré-triagem do corpus todo

    print("\n===== PIPELINE CONCLUÍDO =====")
    print("Depois da triagem manual, rode: python scripts/15_apply_screening.py")


if __name__ == "__main__":
    main()
