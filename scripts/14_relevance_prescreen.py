"""
Pré-triagem de relevância para TODO o corpus (apoio à triagem PRISMA completa).

Motivação: a busca tem alta cobertura (recall), mas inclui artigos de clima/
hidrologia que apenas MENCIONAM evapotranspiração sem CALCULAR ET0 nem apresentar
uma ferramenta. Este escore transparente ordena e sugere uma decisão para cada
documento, para que a triagem manual do conjunto inteiro seja viável.

Calibrado contra as decisões manuais das 99 amostras (S/N):
  - inclusões manuais pontuaram 5–8; exclusões, majoritariamente <= 2.

NÃO substitui a leitura humana — apenas ORDENA e SUGERE. Decisões manuais já
tomadas são preservadas (bloqueadas).

Saída: data/processed/full_screening.csv (todos os documentos, ordenados)
"""

import os
import pandas as pd

from config import PROCESSED_DIR

CORPUS = os.path.join(PROCESSED_DIR, "corpus_classified.csv")
DECISIONS = os.path.join(PROCESSED_DIR, "decisions_99.csv")  # opcional

# Sinais de ET0-específico / ferramenta (inclusão)
ET0_SPECIFIC = ["penman-monteith", "penman monteith", "fao-56", "fao 56", "fao56",
                "hargreaves", "priestley-taylor", "blaney-criddle", "thornthwaite",
                "makkink", "reference evapotranspiration", "reference et",
                "potential evapotranspiration", "crop coefficient",
                "crop water requirement", "et0", "eto ", "et₀"]
NAMED = ["cropwat", "aquacrop", "ref-et", "eto calculator", "pyfao56", "simdualkc",
         "pyeto", "sebal", "metric", "ssebop", "sebs", "openet", "dssat"]
TOOLWORDS = ["software", "platform", "web-based", "web application", "online tool",
             "decision support", "package", "toolbox", "calculator", " api ",
             "user interface", "google earth engine", "web service"]
COMPUTE = ["estimat", "comput", "calculat", "predict", "simulat", "forecast",
           "retriev", "mapping "]
ET = ["evapotranspiration", "et0", "eto ", "et₀"]
# Marcadores de processo/clima sem ferramenta (peso negativo fraco)
NEG = ["climate change", "streamflow", "runoff", "drought monitoring",
       "gross primary", "carbon flux", "land surface temperature",
       "teleconnection", "precipitation trend", "groundwater recharge", "sea level"]


def score_row(row):
    t = " ".join(str(row.get(c, "")) for c in ("title", "abstract", "keywords")).lower()
    s, why = 0, []
    if any(m in t for m in ET0_SPECIFIC):
        s += 3; why.append("ET0-specific term/method")
    if any(n in t for n in NAMED):
        s += 3; why.append("named ET tool")
    if any(w in t for w in TOOLWORDS):
        s += 2; why.append("software/tool term")
    if any(c in t for c in COMPUTE) and any(e in t for e in ET):
        s += 2; why.append("computes/estimates ET")
    if any(n in t for n in NEG) and s < 3:
        s -= 1; why.append("climate/hydrology-process marker")
    return pd.Series([s, "; ".join(why) or "no strong signal"])


def bucket(s):
    if s >= 5:
        return "1-LIKELY_INCLUDE"
    if s >= 3:
        return "2-REVIEW"
    return "3-LIKELY_EXCLUDE"


def main():
    df = pd.read_csv(CORPUS, dtype=str)
    df[["relevance", "relevance_reason"]] = df.apply(score_row, axis=1)
    df["relevance"] = df["relevance"].astype(int)
    df["suggestion"] = df["relevance"].map(bucket)
    df["Include_Title_Abstract"] = ""
    df["Exclusion_Reason"] = ""

    # aplica decisões manuais já tomadas (bloqueadas)
    n_locked = 0
    if os.path.exists(DECISIONS):
        dec = pd.read_csv(DECISIONS, dtype=str)
        inc = [c for c in dec.columns if "include" in c.lower()][0]
        dec = dec[["id", inc]].rename(columns={inc: "manual"})
        dec["manual"] = dec["manual"].fillna("").str.upper().str.strip()
        df = df.merge(dec, on="id", how="left")
        mask = df["manual"].isin(["S", "N"])
        df.loc[mask, "Include_Title_Abstract"] = df.loc[mask, "manual"]
        n_locked = int(mask.sum())
        df.drop(columns="manual", inplace=True)

    order = {"1-LIKELY_INCLUDE": 0, "2-REVIEW": 1, "3-LIKELY_EXCLUDE": 2}
    df["_o"] = df["suggestion"].map(order)
    df = df.sort_values(["_o", "relevance"], ascending=[True, False]).drop(columns="_o")

    cols = ["suggestion", "relevance", "relevance_reason",
            "Include_Title_Abstract", "Exclusion_Reason",
            "id", "doi", "title", "abstract", "keywords", "venue", "year",
            "block", "tool_type", "method_class", "cited_by_count", "sources_found"]
    cols = [c for c in cols if c in df.columns]
    out = os.path.join(PROCESSED_DIR, "full_screening.csv")
    df[cols].to_csv(out, index=False, encoding="utf-8-sig")

    print(f"[OK] {out}  ({len(df):,} documentos; {n_locked} decisões manuais preservadas)")
    print("\nDistribuição das sugestões:")
    print(df["suggestion"].value_counts().sort_index().to_string())
    dec_done = df["Include_Title_Abstract"].isin(["S", "N"]).sum()
    print(f"\nJá decididos: {dec_done} | Faltam triar: {len(df)-dec_done}")


if __name__ == "__main__":
    main()
