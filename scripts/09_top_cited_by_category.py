"""
Espinha dorsal da síntese qualitativa do estado da arte.

A partir do corpus classificado (data/processed/corpus_classified.csv), lista os
documentos MAIS CITADOS por categoria — tipo de ferramenta e paradigma de método —
para servir de base à discussão in-depth (critério 2 da EMS).

Saídas:
  results/tables/top_cited_by_tool_type.csv
  results/tables/top_cited_by_method.csv
  results/tables/top_cited_overall.csv
  results/tables/STATE_OF_THE_ART_SEED.md   (leitura humana, pronto para redigir)
"""

import os
import pandas as pd

from config import PROCESSED_DIR, TABLES_DIR

CORPUS = os.path.join(PROCESSED_DIR, "corpus_classified.csv")
TOP_N = 10


def _clean(df):
    df = df.copy()
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0).astype(int)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    for c in ("title", "venue", "doi", "tool_type", "method_class"):
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("")
    return df


def top_by(df, col, out_csv):
    rows = []
    for cat, g in df[df[col] != ""].groupby(col):
        g = g.sort_values("cited_by_count", ascending=False).head(TOP_N)
        for _, r in g.iterrows():
            rows.append({
                col: cat, "citations": r["cited_by_count"],
                "year": int(r["year"]) if pd.notna(r["year"]) else "",
                "title": r["title"], "venue": r["venue"],
                "method_class": r["method_class"], "doi": r["doi"],
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(TABLES_DIR, out_csv), index=False, encoding="utf-8-sig")
    return out


def write_seed(df, by_type, by_method):
    lines = ["# State-of-the-art seed — most-cited works per category",
             "",
             "Backbone for the qualitative synthesis (EMS review criterion 2). "
             "Each entry = a candidate to describe in depth (what the tool/method "
             "does, inputs/outputs, strengths, limitations).", ""]
    # visão geral
    top = df.sort_values("cited_by_count", ascending=False).head(15)
    lines += ["## Most-cited documents overall", ""]
    for _, r in top.iterrows():
        yr = int(r["year"]) if pd.notna(r["year"]) else ""
        lines.append(f"- **{r['cited_by_count']} cit.** ({yr}) — {r['title']} "
                     f"*[{r['venue']}]* — `{r['tool_type']}` / `{r['method_class']}`")
    lines.append("")

    lines += ["## Most-cited by tool type", ""]
    for cat, g in by_type.groupby("tool_type"):
        lines += [f"### {cat}", ""]
        for _, r in g.iterrows():
            lines.append(f"- **{r['citations']} cit.** ({r['year']}) — {r['title']} "
                         f"*[{r['venue']}]* — `{r['method_class']}`")
        lines.append("")

    lines += ["## Most-cited by computational paradigm", ""]
    for cat, g in by_method.groupby("method_class"):
        lines += [f"### {cat}", ""]
        for _, r in g.iterrows():
            lines.append(f"- **{r['citations']} cit.** ({r['year']}) — {r['title']} "
                         f"*[{r['venue']}]*")
        lines.append("")

    path = os.path.join(TABLES_DIR, "STATE_OF_THE_ART_SEED.md")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    return path


def main():
    df = _clean(pd.read_csv(CORPUS, dtype=str))
    by_type = top_by(df[df["tool_type"] != ""], "tool_type",
                     "top_cited_by_tool_type.csv")
    by_method = top_by(df, "method_class", "top_cited_by_method.csv")
    df.sort_values("cited_by_count", ascending=False).head(30)[
        ["cited_by_count", "year", "title", "venue", "tool_type", "method_class", "doi"]
    ].to_csv(os.path.join(TABLES_DIR, "top_cited_overall.csv"), index=False,
             encoding="utf-8-sig")
    seed = write_seed(df, by_type, by_method)
    print(f"[OK] tabelas em {TABLES_DIR}")
    print(f"[OK] síntese semente: {seed}")


if __name__ == "__main__":
    main()
