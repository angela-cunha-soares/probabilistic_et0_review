"""
Aplica as decisões de triagem (full_screening.csv preenchido) e gera o conjunto
final incluído, além de atualizar as contagens PRISMA.

Uso:
  1. Preencha a coluna Include_Title_Abstract em data/processed/full_screening.csv
     com S (incluir) ou N (excluir).
  2. python scripts/15_apply_screening.py
  3. Depois, tabelas/figuras podem ser regeneradas sobre corpus_included.csv
     (a etapa de regeneração é feita em conjunto após a triagem).

Saídas:
  data/processed/corpus_included.csv
  results/tables/prisma_counts.csv  (atualizado com triagem/inclusão)
"""

import os
import pandas as pd

from config import PROCESSED_DIR, TABLES_DIR

FULL = os.path.join(PROCESSED_DIR, "full_screening.csv")
CLASSIFIED = os.path.join(PROCESSED_DIR, "corpus_classified.csv")


def main():
    scr = pd.read_csv(FULL, dtype=str)
    scr["dec"] = scr["Include_Title_Abstract"].fillna("").str.upper().str.strip()
    n_total = len(scr)
    n_inc = int((scr["dec"] == "S").sum())
    n_exc = int((scr["dec"] == "N").sum())
    n_pend = n_total - n_inc - n_exc

    inc_ids = set(scr.loc[scr["dec"] == "S", "id"])
    corpus = pd.read_csv(CLASSIFIED, dtype=str)
    included = corpus[corpus["id"].isin(inc_ids)].copy()
    included.to_csv(os.path.join(PROCESSED_DIR, "corpus_included.csv"),
                    index=False, encoding="utf-8-sig")

    # PRISMA atualizado
    prev = pd.read_csv(os.path.join(TABLES_DIR, "prisma_counts.csv"))
    d = dict(zip(prev["Stage"], prev["Count"]))
    raw = int(d.get("Records identified (raw, all sources)", 0))
    uniq = int(d.get("Records after duplicate removal (unique)", n_total))
    dup = int(d.get("Duplicates removed", 0))
    prisma = pd.DataFrame({
        "Stage": ["Records identified (raw, all sources)",
                  "Duplicates removed",
                  "Records after duplicate removal (unique)",
                  "Records screened (title/abstract)",
                  "Records excluded in screening",
                  "Records pending screening",
                  "Studies included"],
        "Count": [raw, dup, uniq, n_total, n_exc, n_pend, n_inc]})
    prisma.to_csv(os.path.join(TABLES_DIR, "prisma_counts.csv"), index=False)

    print("===== TRIAGEM =====")
    print(f"Total a triar     : {n_total:,}")
    print(f"Incluídos (S)     : {n_inc:,}")
    print(f"Excluídos (N)     : {n_exc:,}")
    print(f"Pendentes         : {n_pend:,}")
    print(f"\n[OK] corpus_included.csv ({n_inc:,} estudos) e prisma_counts.csv atualizados.")
    if n_pend:
        print(f"⚠️  Ainda faltam {n_pend:,} sem decisão (S/N).")


if __name__ == "__main__":
    main()
