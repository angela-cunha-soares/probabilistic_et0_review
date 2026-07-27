"""
Geração de figuras (alta resolução) a partir das tabelas reais em results/tables/.
Nenhum número é hard-coded: tudo vem dos CSVs gerados por 05_bibliometric_analysis.py.
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


def fig_macro_gap():
    df = _read("macro_contrast.csv")
    if df is None:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(df["Documents"], labels=df["Approach"], autopct="%1.1f%%",
           startangle=90, colors=["#1f77b4", "#d62728"], pctdistance=0.8,
           wedgeprops=dict(width=0.4, edgecolor="w", linewidth=2),
           textprops={"fontsize": 12, "fontweight": "bold"})
    plt.title("Macro-Bibliometric Contrast\n(deterministic vs probabilistic)",
              fontweight="bold", pad=20)
    plt.savefig(os.path.join(FIGURES_DIR, "fig0_macro_gap_donut.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_trend():
    df = _read("publications_per_year.csv")
    if df is None:
        return
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="Year", y="Publications", marker="o",
                 color=ACCENT, linewidth=2.5)
    plt.title("Annual Scientific Production", fontweight="bold")
    plt.xlabel("Year"); plt.ylabel("Documents")
    plt.xticks(rotation=45); sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig1_publications_trend.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_keywords():
    df = _read("top_keywords.csv")
    if df is None or df.empty:
        return
    plt.figure(figsize=(10, 7))
    sns.barplot(data=df, x="Frequency", y="Keyword", color=ACCENT, width=0.6)
    plt.title("Most Frequent Keywords", fontweight="bold", pad=15)
    plt.xlabel("Frequency"); plt.ylabel(""); sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig2_top_keywords.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_countries():
    df = _read("top_countries.csv")
    if df is None or df.empty:
        return
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="Publications", y="Country", color=ACCENT, width=0.6)
    plt.title("Distribution by Country", fontweight="bold", pad=15)
    plt.xlabel("Documents"); plt.ylabel(""); sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig3_top_countries.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_gap_teleconnections():
    df = _read("gap_oceanic_indices.csv")
    if df is None or df.empty:
        return
    df = df.sort_values("Percentage (%)")
    plt.figure(figsize=(10, 6))
    colors = ["#d62728" if v == 0 else ACCENT for v in df["Percentage (%)"]]
    sns.barplot(data=df, x="Percentage (%)", y="Oceanic_Index", palette=colors)
    plt.title("Stochastic Decision Gap:\nOceanic teleconnections & climatological "
              "priors in the corpus", fontweight="bold", pad=15)
    plt.xlabel("% of documents mentioning"); plt.ylabel("")
    sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig4_gap_teleconnections.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_method_split():
    df = _read("method_classification.csv")
    if df is None or df.empty:
        return
    colors = {"Deterministic": "#1f77b4", "Non-deterministic": "#d62728",
              "Hybrid (both)": "#2ca02c", "Unclassified": "#bbbbbb"}
    c = [colors.get(m, "#888") for m in df["Method_class"]]
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(df["Documents"], labels=df["Method_class"], autopct="%1.1f%%",
           startangle=90, colors=c, pctdistance=0.8,
           wedgeprops=dict(width=0.42, edgecolor="w", linewidth=2),
           textprops={"fontsize": 11, "fontweight": "bold"})
    plt.title("How ET₀ is computed/forecast:\ndeterministic vs non-deterministic",
              fontweight="bold", pad=20)
    plt.savefig(os.path.join(FIGURES_DIR, "fig13_method_split.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_method_by_year():
    df = _read("method_by_year.csv")
    if df is None or df.empty:
        return
    df = df[(df["year"] >= 2000) & (df["year"] <= 2026)]
    cols = [c for c in ["Deterministic", "Non-deterministic", "Hybrid (both)",
                        "Unclassified"] if c in df.columns]
    palette = {"Deterministic": "#1f77b4", "Non-deterministic": "#d62728",
               "Hybrid (both)": "#2ca02c", "Unclassified": "#cccccc"}
    plt.figure(figsize=(11, 6))
    plt.stackplot(df["year"], *[df[c] for c in cols], labels=cols,
                  colors=[palette[c] for c in cols], alpha=0.9)
    plt.legend(loc="upper left", frameon=False)
    plt.title("Evolution of ET₀ computation approaches over time",
              fontweight="bold")
    plt.xlabel("Year"); plt.ylabel("Documents")
    sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig14_method_by_year.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_tool_types():
    df = _read("tool_type_distribution.csv")
    if df is None or df.empty:
        return
    df = df[df["Documents"] > 0].sort_values("Documents")
    plt.figure(figsize=(11, 6))
    sns.barplot(data=df, x="Documents", y="Tool_type", color=ACCENT, width=0.65)
    for i, (v, p) in enumerate(zip(df["Documents"], df["Percentage (%)"])):
        plt.text(v, i, f" {v} ({p:.0f}%)", va="center", fontsize=9)
    plt.title("Types of ET₀ tools/software in the corpus", fontweight="bold", pad=15)
    plt.xlabel("Documents"); plt.ylabel(""); sns.despine(); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig15_tool_types.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def main():
    fig_macro_gap()
    fig_trend()
    fig_keywords()
    fig_countries()
    fig_gap_teleconnections()
    fig_method_split()
    fig_method_by_year()
    fig_tool_types()
    print(f"[OK] Figuras salvas em {FIGURES_DIR}")


if __name__ == "__main__":
    main()
