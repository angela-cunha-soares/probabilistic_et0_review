"""
Figuras dos metadados enriquecidos:
  fig16_top_institutions.png   top instituições por nº de documentos
  fig17_open_access.png        participação Open Access (rosca) + OA por tipo (barra)
  fig18_journals_by_impact.png periódicos do corpus vs proxy de impacto (OpenAlex)
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from config import TABLES_DIR, FIGURES_DIR

sns.set_theme(style="ticks")
plt.rcParams.update({"font.size": 12, "font.family": "sans-serif"})
ACCENT = "#008CBA"


def _read(name):
    fp = os.path.join(TABLES_DIR, name)
    return pd.read_csv(fp) if os.path.exists(fp) else None


def fig_institutions():
    df = _read("top_institutions.csv")
    if df is None or df.empty:
        return
    df = df.sort_values("Publications")
    plt.figure(figsize=(11, 7))
    sns.barplot(data=df, x="Publications", y="Institution", color=ACCENT, width=0.65)
    plt.title("Top institutions by number of documents", fontweight="bold", pad=15)
    plt.xlabel("Documents"); plt.ylabel(""); sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig16_top_institutions.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_open_access():
    ov = _read("oa_summary.csv")
    byt = _read("oa_by_tool_type.csv")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    if ov is not None and not ov.empty:
        axes[0].pie(ov["Documents"], labels=ov["Category"], autopct="%1.1f%%",
                    startangle=90, colors=["#2ca02c", "#cccccc"], pctdistance=0.8,
                    wedgeprops=dict(width=0.42, edgecolor="w", linewidth=2),
                    textprops={"fontsize": 12, "fontweight": "bold"})
        axes[0].set_title("Open Access share (corpus)", fontweight="bold")
    if byt is not None and not byt.empty:
        byt = byt.sort_values("OA_%")
        sns.barplot(data=byt, x="OA_%", y="tool_type", color="#2ca02c",
                    width=0.65, ax=axes[1])
        axes[1].set_title("Open Access by tool type", fontweight="bold")
        axes[1].set_xlabel("% Open Access"); axes[1].set_ylabel("")
        sns.despine(ax=axes[1])
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig17_open_access.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_journals_impact():
    df = _read("top_journals_by_impact.csv")
    if df is None or df.empty:
        return
    df = df.dropna(subset=["impact_2yr_mean_citedness"]).head(12)
    df = df.sort_values("corpus_docs")
    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(df["venue"], df["corpus_docs"], color=ACCENT, height=0.6)
    ax.set_xlabel("Documents in corpus"); ax.set_ylabel("")
    ax.set_title("Leading journals: corpus output and impact proxy\n"
                 "(labels = OpenAlex 2-yr mean citedness)", fontweight="bold", pad=12)
    for b, imp in zip(bars, df["impact_2yr_mean_citedness"]):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
                f"  IF≈{imp:.1f}", va="center", fontsize=9)
    sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig18_journals_by_impact.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def main():
    fig_institutions()
    fig_open_access()
    fig_journals_impact()
    print(f"[OK] Figuras de metadados em {FIGURES_DIR}")


if __name__ == "__main__":
    main()
