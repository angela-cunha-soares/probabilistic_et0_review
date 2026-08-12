"""
Coletor OpenAlex — fonte PRIMÁRIA (gratuita, aberta, reprodutível sem chave).

Para cada bloco temático (config.BLOCKS) constrói uma query booleana,
pagina via cursor e grava um CSV unificado em data/raw/openalex_raw.csv.
"""

import time
import urllib.parse
import pandas as pd

from config import BLOCKS, YEAR_MIN, YEAR_MAX, CONTACT_EMAIL, RAW_DIR
from lib_sources import (http_get_json, build_boolean, openalex_abstract,
                         UNIFIED_COLS)
import os

BASE = "https://api.openalex.org/works"


def collect_block(block, time_budget=None, start_cursor="*", sink=None):
    """Coleta um bloco. Se time_budget (segundos) for dado, para graciosamente
    ao estourar o tempo e retorna (rows, next_cursor) para retomada.
    Se sink (função) for dado, cada página é escrita imediatamente."""
    segs = []
    if block.get("title"):
        segs.append(f"title.search:{build_boolean(block['title'])}")
    segs.append(f"title_and_abstract.search:{build_boolean(block['abs'])}")
    filt = (",".join(segs) +
            f",from_publication_date:{YEAR_MIN}-01-01,"
            f"to_publication_date:{YEAR_MAX}-12-31")
    rows, cursor, page = [], start_cursor, 0
    t0 = time.time()
    print(f"\n[OpenAlex] Bloco '{block['name']}'")
    while cursor:
        if time_budget and (time.time() - t0) > time_budget:
            print(f"    [tempo esgotado] retomar com cursor salvo")
            return rows, cursor
        url = (f"{BASE}?filter={urllib.parse.quote(filt)}"
               f"&per-page=200&cursor={cursor}&mailto={CONTACT_EMAIL}")
        data = http_get_json(url)
        if not data:
            break
        page_rows = []
        for w in data.get("results", []):
            authorships = w.get("authorships", [])
            countries = sorted({c for a in authorships
                                for c in a.get("countries", [])})
            authors = "; ".join(a.get("author", {}).get("display_name", "")
                                for a in authorships)
            institutions = "; ".join(sorted({
                inst.get("display_name", "")
                for a in authorships for inst in a.get("institutions", [])
                if inst.get("display_name")}))
            kws = "; ".join(k.get("display_name", "")
                            for k in w.get("keywords", []))
            src = (w.get("primary_location") or {}).get("source") or {}
            venue = src.get("display_name", "")
            issn = src.get("issn_l", "") or (src.get("issn") or [""])[0]
            oa = w.get("open_access", {}) or {}
            field = (((w.get("primary_topic") or {}).get("field") or {})
                     .get("display_name", ""))
            page_rows.append({
                "id": w.get("id"),
                "source": "openalex",
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "title": w.get("title") or "",
                "abstract": openalex_abstract(w.get("abstract_inverted_index")),
                "year": w.get("publication_year"),
                "venue": venue,
                "authors": authors,
                "institutions": institutions,
                "country_codes": ";".join(countries),
                "cited_by_count": w.get("cited_by_count", 0),
                "is_oa": oa.get("is_oa", ""),
                "oa_status": oa.get("oa_status", ""),
                "issn": issn,
                "field": field,
                "keywords": kws,
                "block": block["name"],
            })
        rows.extend(page_rows)
        if sink:
            sink(page_rows)
        cursor = (data.get("meta") or {}).get("next_cursor")
        page += 1
        print(f"    página {page}: acumulado {len(rows):,}")
        time.sleep(0.2)  # polite pool
    return rows, None


def main():
    all_rows = []
    for block in BLOCKS:
        rows, _ = collect_block(block)
        all_rows.extend(rows)
    df = pd.DataFrame(all_rows, columns=UNIFIED_COLS)
    out = os.path.join(RAW_DIR, "openalex_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[OpenAlex] {len(df):,} registros brutos -> {out}")


if __name__ == "__main__":
    main()
