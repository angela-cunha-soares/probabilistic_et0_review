"""
Gera o relatório legível SEARCH_TERMS.md A PARTIR do config.py.

IMPORTANTE: o config.py é a FONTE DA VERDADE. Este script apenas exporta os termos
para um Markdown de consulta (usado no Apêndice do artigo). Edite sempre o config.py,
depois rode este script (ou o run_pipeline) para atualizar o SEARCH_TERMS.md.
"""

import os
import config as c

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def joinq(terms):
    return ", ".join(f"`{t}`" for t in terms)


def main():
    L = ["# Termos de busca e conectivos — ET₀ review", "",
         "> Gerado automaticamente a partir de `scripts/config.py` "
         "(não edite este arquivo à mão; edite o config.py).", "",
         f"Janela temporal: **{c.YEAR_MIN}–{c.YEAR_MAX}**. Conectivos: dentro de cada "
         "grupo os termos são unidos por **OR**; grupos diferentes por **AND**. No "
         "Bloco A, o núcleo de ET₀ é exigido no **título**; os demais no **título+resumo**.",
         "", "## Bloco A — Software/ferramentas de ET₀", "",
         "**Núcleo ET₀ (exigido no TÍTULO):**", joinq(c.CORE_ET0), "",
         "**Tipos de ferramenta (título+resumo, OR):**", joinq(c.TOOL_TYPES), "",
         "**Nomes de softwares conhecidos (título+resumo, OR):**", joinq(c.NAMED_TOOLS),
         "", "## Bloco B — Irrigação/decisão sob incerteza", "",
         "**Irrigação/balanço hídrico (OR):**", joinq(c.CORE_IRRIGATION), "",
         "**Métodos probabilísticos (OR):**", joinq(c.METHOD_PROB), "",
         "**Teleconexões (OR):**", joinq(c.TELECONNECTION), "",
         "## Vocabulário de CLASSIFICAÇÃO (mineração pós-coleta, não é busca)", "",
         "**Determinístico:**", joinq(c.DET_METHODS), "",
         "**Não-determinístico:**", joinq(c.NONDET_METHODS), "",
         "**Tipos de ferramenta (taxonomia):** " +
         ", ".join(f"`{lbl}`" for lbl, _ in c.TOOL_TYPE_TAXONOMY), ""]
    path = os.path.join(ROOT, "SEARCH_TERMS.md")
    open(path, "w", encoding="utf-8").write("\n".join(L))
    print(f"[OK] {path} atualizado a partir do config.py")


if __name__ == "__main__":
    main()
