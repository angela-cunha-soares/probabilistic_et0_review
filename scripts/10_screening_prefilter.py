"""
Pré-filtro semiautomático de triagem (apoio à etapa PRISMA de screening).

NÃO decide sozinho — apenas SUGERE, para acelerar a triagem manual. Para cada
documento único do corpus atribui uma sugestão:
  KEEP           -> tem sinal claro de ET/irrigação e nenhum marcador fora-do-tema
  CHECK          -> ambíguo (sem sinal claro de ET, ou sinal + marcador fora-do-tema)
  LIKELY_EXCLUDE -> marcador fora-do-tema e sem sinal de ET (ex.: 'engineer-to-order')

Saída: data/processed/screening_sheet_prefiltered.csv
  (colunas prefilter_suggestion, prefilter_reason + a planilha de triagem manual)
"""

import os
import re
import pandas as pd

from config import PROCESSED_DIR

CORPUS = os.path.join(PROCESSED_DIR, "corpus_classified.csv")

# Sinal ON-TOPIC (ET / irrigação / hidrologia)
ON_TOPIC = [
    "evapotranspiration", "evapotranspiración", "evapotranspiração",
    "penman", "monteith", "hargreaves", "priestley", "reference et",
    "reference evapotranspiration", "potential evapotranspiration",
    "actual evapotranspiration", "crop water", "crop coefficient",
    "irrigation", "soil moisture", "soil water", "water balance",
    "water requirement", "hydrolog", "fao-56", "fao 56", "aridity",
    "surface energy balance", "sebal", "ssebop", " metric ", "cropwat",
    "aquacrop", "eddy covariance", "lysimeter", "kc ", "et0", "eto ",
]

# Marcadores OFF-TOPIC (domínios que compartilham o token 'ETo/ET')
OFF_TOPIC = {
    "engineer-to-order (manufacturing)": ["engineer-to-order", "engineer to order",
        "make-to-order", "production planning", "assembly line", "job shop",
        "manufacturing lead time"],
    "medicine/clinical": ["endotracheal", "patient", "clinical trial", "tumou",
        "carcinoma", "in vitro fertil", "embryo transfer", "endometri"],
    "finance/economics/marketing": ["stock market", "engineer-to-order",
        "marketing strategy", "consumer behaviour", "cryptocurrenc"],
    "electronics/materials": ["etching", "photolithograph", "transistor",
        "semiconductor wafer"],
}


def prefilter(row):
    text = " ".join(str(row.get(c, "")) for c in ("title", "abstract", "keywords")).lower()
    has_on = any(t in text for t in ON_TOPIC)
    off_domain = None
    for domain, terms in OFF_TOPIC.items():
        if any(t in text for t in terms):
            off_domain = domain
            break
    if off_domain and not has_on:
        return "LIKELY_EXCLUDE", f"off-topic: {off_domain}"
    if off_domain and has_on:
        return "CHECK", f"ET signal + off-topic token ({off_domain})"
    if not has_on:
        return "CHECK", "no clear ET/irrigation signal in title/abstract"
    return "KEEP", "clear ET/irrigation signal"


def main():
    df = pd.read_csv(CORPUS, dtype=str)
    sug = df.apply(prefilter, axis=1, result_type="expand")
    df["prefilter_suggestion"] = sug[0]
    df["prefilter_reason"] = sug[1]
    df["Include_Title_Abstract"] = ""   # decisão manual (S/N)
    df["Exclusion_Reason"] = ""

    cols = ["prefilter_suggestion", "prefilter_reason",
            "Include_Title_Abstract", "Exclusion_Reason",
            "id", "doi", "title", "abstract", "keywords", "venue", "year",
            "block", "tool_type", "method_class", "sources_found"]
    cols = [c for c in cols if c in df.columns]
    out = os.path.join(PROCESSED_DIR, "screening_sheet_prefiltered.csv")
    df[cols].to_csv(out, index=False, encoding="utf-8-sig")

    counts = df["prefilter_suggestion"].value_counts()
    print("Sugestões do pré-filtro:")
    for k in ("KEEP", "CHECK", "LIKELY_EXCLUDE"):
        print(f"  {k:14s}: {int(counts.get(k, 0)):>5,}")
    print(f"\n[OK] {out}")
    print("Exemplos sinalizados para exclusão:")
    ex = df[df["prefilter_suggestion"] == "LIKELY_EXCLUDE"]
    for _, r in ex.head(8).iterrows():
        print(f"  - {str(r['title'])[:80]} | {r['prefilter_reason']}")


if __name__ == "__main__":
    main()
