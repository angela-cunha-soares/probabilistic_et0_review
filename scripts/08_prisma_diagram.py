"""
Fluxograma PRISMA 2020 (identificação -> triagem -> elegibilidade -> inclusão).

As contagens de IDENTIFICAÇÃO e DEDUPLICAÇÃO vêm automaticamente de
results/tables/prisma_counts.csv e das fontes brutas. As contagens de TRIAGEM
manual (exclusões por título/resumo, elegibilidade, inclusão final) são
placeholders editáveis abaixo — preencha após a triagem e rode de novo.

Saída: results/figures/fig_prisma_flow.png
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from config import TABLES_DIR, FIGURES_DIR, RAW_DIR, PROCESSED_DIR

# ----------------------------------------------------------------------
# Contagens automáticas (identificação + deduplicação)
# ----------------------------------------------------------------------
def _counts():
    pc = pd.read_csv(os.path.join(TABLES_DIR, "prisma_counts.csv"))
    d = dict(zip(pc["Stage"], pc["Count"]))
    raw = int(d.get("Records identified (raw, all sources)", 0))
    unique = int(d.get("Records after duplicate removal (unique)", 0))
    dupes = int(d.get("Duplicates removed", 0))
    # quebra por bloco
    corpus = pd.read_csv(os.path.join(PROCESSED_DIR, "corpus_unified.csv"))
    per_block = corpus["block"].value_counts().to_dict()
    # bases contribuintes
    ov = pd.read_csv(os.path.join(TABLES_DIR, "source_overlap.csv"))
    sources = sorted({s for row in ov["sources"] for s in str(row).split(";")})
    return raw, unique, dupes, per_block, sources


# ----------------------------------------------------------------------
# >>> EDITE APÓS A TRIAGEM MANUAL <<<
#   Deixe como None para exibir "a definir".
# ----------------------------------------------------------------------
EXCLUDED_TITLE_ABS = None      # excluídos na triagem por título/resumo
REPORTS_ASSESSED = None        # relatórios avaliados para elegibilidade
EXCLUDED_ELIGIBILITY = {       # motivos de exclusão -> n
    # "Not ET0/irrigation focus": 0,
    # "No uncertainty/Bayesian component": 0,
    # "No software/tool": 0,
}
STUDIES_INCLUDED = None        # estudos incluídos na revisão


def _fmt(v):
    return str(v) if v is not None else "a definir"


def box(ax, x, y, w, h, text, fc="#eaf3f8", ec="#008CBA"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                                linewidth=1.5, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=9.5, zorder=3, wrap=True)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=16, linewidth=1.4,
                                 color="#555555", zorder=1))


def main():
    raw, unique, dupes, per_block, sources = _counts()
    blockA = per_block.get("ETo_Software_Tools", 0)
    blockB = per_block.get("Irrigation_Decision", 0)
    src_txt = ", ".join(sources) if sources else "OpenAlex"

    fig, ax = plt.subplots(figsize=(11, 13))
    ax.set_xlim(0, 10); ax.set_ylim(0, 14); ax.axis("off")

    # faixas de fase (rótulos à esquerda)
    phases = [("IDENTIFICATION", 12.4, "#1f77b4"),
              ("SCREENING", 8.6, "#2ca02c"),
              ("ELIGIBILITY", 5.2, "#ff7f0e"),
              ("INCLUDED", 2.0, "#d62728")]
    for label, y, col in phases:
        ax.text(0.15, y, label, rotation=90, ha="center", va="center",
                fontsize=11, fontweight="bold", color=col)

    cx, w = 2.0, 5.2
    # Identificação
    box(ax, cx, 12.0, w, 1.4,
        f"Records identified from databases ({src_txt})\n"
        f"n = {raw}\n"
        f"(Block A – ET0 Software/Tools: {blockA};  "
        f"Block B – Irrigation Decision: {blockB})")
    # remoção antes da triagem
    box(ax, cx + w + 0.4, 12.1, 2.0, 1.2,
        f"Records removed before\nscreening:\nduplicates n = {dupes}",
        fc="#f5f5f5", ec="#999999")
    arrow(ax, cx + w, 12.7, cx + w + 0.4, 12.7)

    # Triagem
    box(ax, cx, 9.4, w, 1.0, f"Records screened (title/abstract)\nn = {unique}")
    arrow(ax, cx + w / 2, 12.0, cx + w / 2, 10.4)
    box(ax, cx + w + 0.4, 9.45, 2.0, 0.9,
        f"Records excluded\nn = {_fmt(EXCLUDED_TITLE_ABS)}",
        fc="#f5f5f5", ec="#999999")
    arrow(ax, cx + w, 9.9, cx + w + 0.4, 9.9)

    # Elegibilidade
    box(ax, cx, 6.0, w, 1.0,
        f"Reports assessed for eligibility\nn = {_fmt(REPORTS_ASSESSED)}")
    arrow(ax, cx + w / 2, 9.4, cx + w / 2, 7.0)
    reasons = ("\n".join(f"• {k}: {v}" for k, v in EXCLUDED_ELIGIBILITY.items())
               or "reasons to be defined")
    box(ax, cx + w + 0.4, 5.7, 2.0, 1.6,
        f"Reports excluded\n{reasons}", fc="#f5f5f5", ec="#999999")
    arrow(ax, cx + w, 6.5, cx + w + 0.4, 6.5)

    # Incluídos
    box(ax, cx, 2.4, w, 1.0,
        f"Studies included in the review\nn = {_fmt(STUDIES_INCLUDED)}",
        fc="#fdecec", ec="#d62728")
    arrow(ax, cx + w / 2, 6.0, cx + w / 2, 3.4)

    ax.set_title("PRISMA 2020 flow diagram — Probabilistic ET₀ review",
                 fontweight="bold", fontsize=14, pad=14)
    out = os.path.join(FIGURES_DIR, "fig_prisma_flow.png")
    plt.tight_layout()
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[OK] {out}")
    print(f"     identificados={raw} | únicos={unique} | duplicatas={dupes} "
          f"| A={blockA} B={blockB}")


if __name__ == "__main__":
    main()
