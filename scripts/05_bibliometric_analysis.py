"""
Análise bibliométrica sobre o corpus unificado (data/processed/corpus_unified.csv).

Gera em results/tables/:
  - publications_per_year.csv
  - top_journals.csv
  - top_countries.csv          (CORRIGIDO: usa códigos ISO de país, não afiliação)
  - top_keywords.csv
  - gap_oceanic_indices.csv     (mineração de teleconexões — evidência do Gap 2)
  - macro_contrast.csv          (determinístico vs probabilístico — Gap 1)
"""

import os
import re
import urllib.parse
import pandas as pd

from config import (PROCESSED_DIR, TABLES_DIR, YEAR_MIN, YEAR_MAX,
                    CONTACT_EMAIL, MACRO_DETERMINISTIC, MACRO_PROBABILISTIC,
                    DET_METHODS, NONDET_METHODS, TOOL_TYPE_TAXONOMY)
from lib_sources import http_get_json

CORPUS = os.path.join(PROCESSED_DIR, "corpus_unified.csv")

# ISO alpha-2 -> nome (subconjunto suficiente; fallback = próprio código)
try:
    import pycountry
    def iso_to_name(code):
        try:
            return pycountry.countries.get(alpha_2=code).name
        except Exception:
            return code
except ImportError:
    _MAP = {"CN": "China", "US": "United States", "BR": "Brazil", "IN": "India",
            "IR": "Iran", "AU": "Australia", "DE": "Germany", "GB": "United Kingdom",
            "IT": "Italy", "ES": "Spain", "FR": "France", "CA": "Canada",
            "NL": "Netherlands", "JP": "Japan", "PT": "Portugal", "MA": "Morocco",
            "EG": "Egypt", "PK": "Pakistan", "SA": "Saudi Arabia", "TR": "Turkey",
            "KR": "South Korea", "BE": "Belgium", "CH": "Switzerland", "AT": "Austria",
            "MX": "Mexico", "CL": "Chile", "AR": "Argentina", "ZA": "South Africa"}
    def iso_to_name(code):
        return _MAP.get(code, code)


def top_countries(df):
    codes = (df["country_codes"].fillna("").astype(str)
             .str.split(";").explode().str.strip())
    codes = codes[codes != ""]
    names = codes.map(iso_to_name)
    out = names.value_counts().head(12).reset_index()
    out.columns = ["Country", "Publications"]
    out.to_csv(os.path.join(TABLES_DIR, "top_countries.csv"), index=False)


def per_year(df):
    d = df[(df["year"] >= YEAR_MIN) & (df["year"] <= YEAR_MAX)]
    out = d["year"].astype(int).value_counts().sort_index().reset_index()
    out.columns = ["Year", "Publications"]
    out.to_csv(os.path.join(TABLES_DIR, "publications_per_year.csv"), index=False)


def top_institutions(df):
    inst = (df["institutions"].dropna().astype(str)
            .str.split(";").explode().str.strip())
    inst = inst[inst.str.len() > 2]
    out = inst.value_counts().head(15).reset_index()
    out.columns = ["Institution", "Publications"]
    out.to_csv(os.path.join(TABLES_DIR, "top_institutions.csv"), index=False)


def open_access_summary(df):
    oa = df["is_oa"].astype(str).str.lower().isin(["true", "1"])
    overall = pd.DataFrame({
        "Category": ["Open Access", "Closed / other"],
        "Documents": [int(oa.sum()), int((~oa).sum())]})
    overall["Percentage (%)"] = (overall["Documents"] / len(df) * 100).round(2)
    overall.to_csv(os.path.join(TABLES_DIR, "oa_summary.csv"), index=False)
    # OA por tipo de ferramenta (só bloco A classificado)
    if "tool_type" in df.columns:
        sub = df[df["tool_type"].fillna("") != ""].copy()
        sub["oa"] = sub["is_oa"].astype(str).str.lower().isin(["true", "1"])
        by = (sub.groupby("tool_type")["oa"].agg(["sum", "count"])
              .rename(columns={"sum": "OA_docs", "count": "Total"}))
        by["OA_%"] = (by["OA_docs"] / by["Total"] * 100).round(1)
        by.reset_index().to_csv(os.path.join(TABLES_DIR, "oa_by_tool_type.csv"),
                                index=False)


def top_journals(df):
    out = df["venue"].dropna().replace("", pd.NA).dropna()
    out = out.value_counts().head(12).reset_index()
    out.columns = ["Journal", "Publications"]
    out.to_csv(os.path.join(TABLES_DIR, "top_journals.csv"), index=False)


# Rótulos de campo/disciplina atribuídos automaticamente pelo OpenAlex
# (não são palavras-chave de autor; poluem a análise e são removidos).
KW_STOP = {
    "environmental science", "geography", "geology", "meteorology",
    "mathematics", "computer science", "physics", "biology", "engineering",
    "materials science", "chemistry", "economics", "cartography",
    "atmospheric sciences", "hydrology", "soil science", "geodesy",
    "remote sensing", "statistics", "geomorphology", "oceanography",
    "environmental resource management", "agronomy", "physical geography",
}


def top_keywords(df):
    kw = (df["keywords"].dropna().astype(str)
          .str.replace(r"[|,]", ";", regex=True)
          .str.split(";").explode().str.lower().str.strip())
    kw = kw[(kw != "") & (kw.str.len() > 2) & (~kw.isin(KW_STOP))]
    out = kw.value_counts().head(20).reset_index()
    out.columns = ["Keyword", "Frequency"]
    out.to_csv(os.path.join(TABLES_DIR, "top_keywords.csv"), index=False)


def mine_teleconnections(df):
    idx = {
        "ONI / ENSO": r"\b(?:oni|enso|el ni[ñn]o|la ni[ñn]a)\b",
        "MEI": r"\b(?:mei|multivariate enso)\b",
        "AMM (Atlantic Meridional Mode)": r"\b(?:amm|atlantic meridional mode)\b",
        "AMO (Atlantic Multidecadal)": r"\b(?:amo|atlantic multidecadal)\b",
        "PDO (Pacific Decadal)": r"\b(?:pdo|pacific decadal)\b",
        "MJO (Madden-Julian)": r"\b(?:mjo|madden-julian)\b",
        "IOD / DMI (Indian Ocean)": r"\b(?:iod|dmi|indian ocean dipole)\b",
        "Teleconnections (geral)": r"\b(?:teleconnection|teleconnections)\b",
        "Climatological priors": r"\b(?:climatological prior|climate prior)\b",
    }
    corpus = (df["title"].fillna("") + " " + df["abstract"].fillna("")).str.lower()
    rows = [{"Oceanic_Index": k,
             "Articles_Mentioning": int(corpus.str.contains(v, regex=True).sum())}
            for k, v in idx.items()]
    out = pd.DataFrame(rows)
    out["Percentage (%)"] = (out["Articles_Mentioning"] / len(df) * 100).round(2)
    out.to_csv(os.path.join(TABLES_DIR, "gap_oceanic_indices.csv"), index=False)


def classify_methods(df):
    """Dimensão central: como cada artigo calcula/prevê a ETo —
    determinístico, não-determinístico, híbrido (ambos) ou não-classificado."""
    text = (df["title"].fillna("") + " " + df["abstract"].fillna("") + " " +
            df["keywords"].fillna("")).str.lower()
    det = pd.Series(False, index=df.index)
    for t in DET_METHODS:
        det |= text.str.contains(re.escape(t), regex=True)
    non = pd.Series(False, index=df.index)
    for t in NONDET_METHODS:
        non |= text.str.contains(re.escape(t), regex=True)

    def cat(d, n):
        if d and n:
            return "Hybrid (both)"
        if d:
            return "Deterministic"
        if n:
            return "Non-deterministic"
        return "Unclassified"
    df = df.assign(method_class=[cat(d, n) for d, n in zip(det, non)])

    order = ["Deterministic", "Non-deterministic", "Hybrid (both)", "Unclassified"]
    counts = (df["method_class"].value_counts().reindex(order).fillna(0).astype(int)
              .rename_axis("Method_class").reset_index(name="Documents"))
    counts["Percentage (%)"] = (counts["Documents"] / len(df) * 100).round(2)
    counts.to_csv(os.path.join(TABLES_DIR, "method_classification.csv"), index=False)

    # evolução temporal das abordagens
    d = df[(df["year"] >= YEAR_MIN) & (df["year"] <= YEAR_MAX)].copy()
    d["year"] = d["year"].astype(int)
    by_year = (d.groupby(["year", "method_class"]).size()
               .unstack(fill_value=0).reindex(columns=order, fill_value=0)
               .reset_index())
    by_year.to_csv(os.path.join(TABLES_DIR, "method_by_year.csv"), index=False)
    print("[Method] " + " | ".join(f"{r.Method_class}={r.Documents}"
                                    for r in counts.itertuples()))
    # devolve o corpus anotado para salvar
    return df


def classify_tool_type(df):
    """Classifica cada documento do eixo de ferramentas (Bloco A) no TIPO de
    ferramenta (reproduz a coluna 'Type' da tabela EVAonline). Atribui a
    primeira categoria correspondente por ordem de prioridade e grava a coluna
    'tool_type' de volta no corpus (Bloco B fica vazio)."""
    mask = df["block"] == "ETo_Software_Tools"
    if not mask.any():
        df["tool_type"] = ""
        return df
    text = (df["title"].fillna("") + " " + df["abstract"].fillna("") + " " +
            df["keywords"].fillna("")).str.lower()

    def assign(t):
        # pontuação por categoria = nº de termos DISTINTOS encontrados;
        # vence a categoria com mais evidência (empate -> ordem da taxonomia).
        best_label, best_score, best_rank = "Other / unspecified", 0, 99
        for rank, (label, terms) in enumerate(TOOL_TYPE_TAXONOMY):
            score = sum(1 for term in terms if term in t)
            if score > best_score or (score == best_score and score > 0
                                      and rank < best_rank):
                best_label, best_score, best_rank = label, score, rank
        return best_label
    df["tool_type"] = ""
    df.loc[mask, "tool_type"] = text[mask].map(assign)

    order = [lbl for lbl, _ in TOOL_TYPE_TAXONOMY] + ["Other / unspecified"]
    counts = (df.loc[mask, "tool_type"].value_counts().reindex(order)
              .fillna(0).astype(int).rename_axis("Tool_type")
              .reset_index(name="Documents"))
    counts["Percentage (%)"] = (counts["Documents"] / int(mask.sum()) * 100).round(2)
    counts.to_csv(os.path.join(TABLES_DIR, "tool_type_distribution.csv"), index=False)
    print("[ToolType] " + " | ".join(f"{r.Tool_type.split(' /')[0]}={r.Documents}"
                                      for r in counts.itertuples()))
    return df


def macro_contrast():
    """Gap 1 quantificado via contagem OpenAlex (determinístico vs probabilístico)."""
    def count(search):
        filt = (f"title_and_abstract.search:{search},"
                f"from_publication_date:{YEAR_MIN}-01-01,"
                f"to_publication_date:{YEAR_MAX}-12-31")
        url = (f"https://api.openalex.org/works?filter={urllib.parse.quote(filt)}"
               f"&per-page=1&mailto={CONTACT_EMAIL}")
        d = http_get_json(url)
        return d["meta"]["count"] if d else None
    det = count(MACRO_DETERMINISTIC)
    prob = count(MACRO_PROBABILISTIC)
    out = pd.DataFrame({
        "Approach": ["Deterministic (FAO-56/AquaCrop/CropWat)",
                     "Probabilistic/Bayesian"],
        "Documents": [det, prob]})
    out.to_csv(os.path.join(TABLES_DIR, "macro_contrast.csv"), index=False)
    if det and prob:
        print(f"[Macro] determinístico={det:,} | probabilístico={prob:,} "
              f"| razão={prob/det:.3f}")


def main():
    df = pd.read_csv(CORPUS)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    per_year(df)
    top_journals(df)
    top_countries(df)
    top_institutions(df)
    top_keywords(df)
    mine_teleconnections(df)
    df = classify_methods(df)
    df = classify_tool_type(df)
    open_access_summary(df)
    # salva corpus anotado com classe de método E tipo de ferramenta
    df.to_csv(os.path.join(PROCESSED_DIR, "corpus_classified.csv"),
              index=False, encoding="utf-8-sig")
    macro_contrast()
    print(f"[OK] Tabelas geradas em {TABLES_DIR} (corpus: {len(df):,} docs)")


if __name__ == "__main__":
    main()
