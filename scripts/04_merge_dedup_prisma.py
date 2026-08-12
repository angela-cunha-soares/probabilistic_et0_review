"""
Fusão multi-base + deduplicação + contagem PRISMA.

Lê todos os *_raw.csv (e openalex_block*.csv) presentes em data/raw/,
deduplica por DOI e por título normalizado, registra a proveniência
(quais bases contêm cada documento) e gera:
  - data/processed/corpus_unified.csv    (corpus final único)
  - data/processed/screening_sheet.csv   (planilha de triagem PRISMA)
  - results/tables/prisma_counts.csv      (números do fluxograma PRISMA)
  - results/tables/source_overlap.csv     (sobreposição entre bases)
"""

import glob
import os
import re
import pandas as pd

from config import RAW_DIR, PROCESSED_DIR, TABLES_DIR
from lib_sources import UNIFIED_COLS


def norm_title(t):
    if not isinstance(t, str):
        return ""
    t = t.lower()
    t = re.sub(r"<[^>]+>", " ", t)          # remove tags (abstracts jats)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_all():
    frames = []
    patterns = ["openalex_block*.csv", "openalex_raw.csv", "scopus_raw.csv",
                "wos_raw.csv", "ieee_raw.csv", "crossref_raw.csv",
                "semanticscholar_raw.csv"]
    for pat in patterns:
        for fp in sorted(glob.glob(os.path.join(RAW_DIR, pat))):
            try:
                df = pd.read_csv(fp)
                if len(df):
                    frames.append(df[[c for c in UNIFIED_COLS if c in df.columns]])
                    print(f"  + {os.path.basename(fp):32s} {len(df):>6,} registros")
            except Exception as e:
                print(f"  ! {fp}: {e}")
    if not frames:
        raise SystemExit("Nenhum arquivo *_raw encontrado em data/raw/.")
    return pd.concat(frames, ignore_index=True)


def main():
    print("[Merge] Lendo fontes...")
    df = load_all()
    n_records = len(df)

    df["doi"] = df["doi"].fillna("").astype(str).str.lower().str.strip()
    df["title_key"] = df["title"].map(norm_title)
    # chave de título "estrita": só letras/números (ignora espaços e pontuação),
    # captura variantes como "LANDS AT" vs "LANDSAT", "ET0" vs "ET 0".
    df["title_strict"] = df["title"].fillna("").str.lower().map(
        lambda t: re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", " ", t)))

    df = df.reset_index(drop=True)

    # ---- deduplicação por UNIÃO: mesmo DOI OU mesmo título estrito ----
    # (antes: dedup só por título deixava passar mesmo-DOI/título-diferente)
    parent = list(range(len(df)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for key, min_len in (("doi", 1), ("title_strict", 16)):
        for val, idx in df.groupby(key).groups.items():
            if not isinstance(val, str) or len(val) < min_len:
                continue
            idx = list(idx)
            for j in idx[1:]:
                union(idx[0], j)
    df["cluster"] = [find(i) for i in range(len(df))]
    df = df[(df["doi"] != "") | (df["title_key"] != "")]

    # proveniência: bases que contêm cada documento (por cluster)
    prov = (df.groupby("cluster")["source"]
              .apply(lambda s: ";".join(sorted(set(s)))).rename("sources_found"))

    # tipo de documento: propaga o valor confiável do WoS para todo o cluster
    if "doc_type" not in df.columns:
        df["doc_type"] = ""
    dtype = (df.groupby("cluster")["doc_type"]
               .apply(lambda s: next((x for x in s
                                      if isinstance(x, str) and x.strip()), ""))
               .rename("doc_type_c"))

    # representante de cada cluster: prefere DOI de periódico e maior abstract
    df["abs_len"] = df["abstract"].fillna("").astype(str).str.len()
    df["is_journal"] = (~df["doi"].str.startswith("10.5281")) & (df["doi"] != "")
    df = df.sort_values(["is_journal", "abs_len"], ascending=[False, False])
    dedup = df.drop_duplicates(subset="cluster", keep="first").copy()
    dedup = dedup.merge(prov, on="cluster", how="left")
    dedup = dedup.merge(dtype, on="cluster", how="left")
    dedup["doc_type"] = dedup["doc_type_c"].fillna("")

    # canonicaliza a CAIXA do nome do periódico (WoS exporta em CAIXA ALTA;
    # junta "REMOTE SENSING" com "Remote Sensing" usando a forma mais comum)
    vk = (dedup["venue"].fillna("").str.lower()
          .str.replace(r"[^a-z0-9]", " ", regex=True).str.replace(r"\s+", " ", regex=True)
          .str.strip())
    canon = dedup.assign(_vk=vk).groupby("_vk")["venue"].transform(
        lambda s: s.mode().iloc[0] if not s.mode().empty else s.iloc[0])
    dedup["venue"] = canon.where(vk != "", dedup["venue"])
    n_unique = len(dedup)

    # ---- PRISMA: identificação -> remoção de duplicatas -> triagem ----
    dupes_removed = n_records - n_unique
    dedup["Include_Title_Abstract"] = ""   # a preencher na triagem manual
    dedup["Exclusion_Reason"] = ""

    # saídas
    corpus_cols = UNIFIED_COLS + ["sources_found"]
    dedup[corpus_cols].to_csv(
        os.path.join(PROCESSED_DIR, "corpus_unified.csv"),
        index=False, encoding="utf-8-sig")

    screen_cols = ["id", "doi", "Include_Title_Abstract", "Exclusion_Reason",
                   "title", "abstract", "keywords", "venue", "year",
                   "block", "sources_found"]
    dedup[screen_cols].to_csv(
        os.path.join(PROCESSED_DIR, "screening_sheet.csv"),
        index=False, encoding="utf-8")

    # contagens PRISMA
    per_source = df.groupby("source")["cluster"].nunique()
    prisma = pd.DataFrame({
        "Stage": ["Records identified (raw, all sources)",
                  "Records after duplicate removal (unique)",
                  "Duplicates removed",
                  "Records to screen (title/abstract)"],
        "Count": [n_records, n_unique, dupes_removed, n_unique]})
    prisma.to_csv(os.path.join(TABLES_DIR, "prisma_counts.csv"), index=False)

    # sobreposição entre bases
    overlap = (dedup["sources_found"].value_counts()
               .rename_axis("sources").reset_index(name="unique_documents"))
    overlap.to_csv(os.path.join(TABLES_DIR, "source_overlap.csv"), index=False)

    print("\n===== PRISMA =====")
    print(prisma.to_string(index=False))
    print("\nÚnicos por base (contribuição):")
    print(per_source.to_string())
    print("\nSobreposição entre bases:")
    print(overlap.to_string(index=False))
    print(f"\n[OK] corpus_unified.csv e screening_sheet.csv em {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
