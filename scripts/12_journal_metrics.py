"""
Métricas de periódico (proxy de fator de impacto) via OpenAlex Sources.

O JIF oficial (Clarivate/JCR) não é acessível gratuitamente. Como proxies aceitos
em bibliometria, o OpenAlex fornece, por periódico:
  - 2yr_mean_citedness  -> equivalente ao fator de impacto de 2 anos
  - h_index, i10_index
  - works_count, is_in_doaj (DOAJ = periódico OA legítimo)

Gera:
  results/tables/journal_metrics.csv        (por ISSN/periódico)
  results/tables/top_journals_by_impact.csv (top do corpus, min. de documentos)
"""

import os
import time
import urllib.parse
import pandas as pd

from config import PROCESSED_DIR, TABLES_DIR, CONTACT_EMAIL
from lib_sources import http_get_json

CORPUS = os.path.join(PROCESSED_DIR, "corpus_classified.csv")
MIN_DOCS = 5  # só rankear periódicos com pelo menos N documentos no corpus


def fetch_metrics(issns):
    """Consulta OpenAlex Sources por ISSN, em lotes."""
    rows = {}
    issns = [i for i in issns if i]
    for k in range(0, len(issns), 50):
        batch = issns[k:k + 50]
        filt = "issn:" + "|".join(batch)
        url = (f"https://api.openalex.org/sources?filter={urllib.parse.quote(filt)}"
               f"&per-page=200&mailto={CONTACT_EMAIL}")
        data = http_get_json(url)
        for s in (data or {}).get("results", []):
            ss = s.get("summary_stats", {}) or {}
            for issn in s.get("issn", []) or []:
                rows[issn] = {
                    "source_name": s.get("display_name", ""),
                    "impact_2yr_mean_citedness": round(ss.get("2yr_mean_citedness", 0), 3),
                    "h_index": ss.get("h_index", 0),
                    "i10_index": ss.get("i10_index", 0),
                    "works_count": s.get("works_count", 0),
                    "is_in_doaj": s.get("is_in_doaj", False),
                }
        time.sleep(0.3)
    return rows


def main():
    df = pd.read_csv(CORPUS, dtype=str)
    df["issn"] = df["issn"].fillna("").astype(str)
    issns = sorted({i.strip() for i in df["issn"] if i.strip()})
    print(f"[Journal] consultando {len(issns)} ISSNs no OpenAlex...")
    metrics = fetch_metrics(issns)

    m = pd.DataFrame.from_dict(metrics, orient="index").rename_axis("issn").reset_index()
    m.to_csv(os.path.join(TABLES_DIR, "journal_metrics.csv"), index=False)

    # junta ao corpus e rankeia por nº de documentos, mostrando o impacto
    counts = (df[df["issn"] != ""].groupby(["venue", "issn"]).size()
              .reset_index(name="corpus_docs"))
    top = counts.merge(m, on="issn", how="left")
    top = top[top["corpus_docs"] >= MIN_DOCS].sort_values(
        "corpus_docs", ascending=False)
    cols = ["venue", "corpus_docs", "impact_2yr_mean_citedness", "h_index",
            "works_count", "is_in_doaj"]
    top[[c for c in cols if c in top.columns]].to_csv(
        os.path.join(TABLES_DIR, "top_journals_by_impact.csv"), index=False)
    print(f"[OK] journal_metrics.csv ({len(m)} periódicos) e "
          f"top_journals_by_impact.csv ({len(top)} do corpus)")
    if not top.empty:
        print(top[["venue", "corpus_docs", "impact_2yr_mean_citedness",
                   "h_index"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
