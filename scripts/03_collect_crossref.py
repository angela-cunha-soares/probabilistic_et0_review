"""
Coletor Crossref (complementar, gratuito) — sem chave.

Crossref não faz busca booleana estruturada como Scopus/WoS; usamos a busca
bibliográfica (query.bibliographic) por bloco e depois filtramos/deduplicamos
no merge. É útil sobretudo para completar metadados (DOI, ano, periódico).

Obs.: por ser busca "solta", tende a recuperar muitos falsos positivos; por isso
entra como fonte COMPLEMENTAR e o corpus final privilegia OpenAlex/Scopus/WoS.
"""

import os
import time
import urllib.parse
import pandas as pd

from config import BLOCKS, YEAR_MIN, YEAR_MAX, CONTACT_EMAIL, RAW_DIR
from lib_sources import http_get_json, UNIFIED_COLS

BASE = "https://api.crossref.org/works"
MAX_PER_BLOCK = 400  # teto de segurança para a busca solta


def _phrase(block):
    # usa o núcleo temático (título se houver, senão abs) para a busca bibliográfica
    groups = block.get("title") or block.get("abs")
    core = " ".join(groups[0][:2])
    extra = " ".join(block["abs"][-1][:2]) if len(block["abs"]) > 1 else ""
    return f"{core} {extra}".strip()


def main():
    rows = []
    for block in BLOCKS:
        query = _phrase(block)
        print(f"[Crossref] {block['name']}: '{query}'")
        cursor, got = "*", 0
        while got < MAX_PER_BLOCK:
            params = urllib.parse.urlencode({
                "query.bibliographic": query,
                "filter": f"from-pub-date:{YEAR_MIN}-01-01,until-pub-date:{YEAR_MAX}-12-31,type:journal-article",
                "rows": 100, "cursor": cursor, "mailto": CONTACT_EMAIL})
            data = http_get_json(f"{BASE}?{params}")
            items = (data.get("message", {}) or {}).get("items", [])
            if not items:
                break
            for it in items:
                yr = None
                dp = it.get("issued", {}).get("date-parts", [[None]])
                if dp and dp[0]:
                    yr = dp[0][0]
                auth = it.get("author", []) or []
                rows.append({
                    "id": it.get("DOI"), "source": "crossref",
                    "doi": it.get("DOI", ""),
                    "title": (it.get("title", [""]) or [""])[0],
                    "abstract": it.get("abstract", ""),
                    "year": yr,
                    "venue": (it.get("container-title", [""]) or [""])[0],
                    "authors": "; ".join(
                        f"{a.get('given','')} {a.get('family','')}".strip() for a in auth),
                    "country_codes": "",
                    "cited_by_count": it.get("is-referenced-by-count", 0),
                    "keywords": "; ".join(it.get("subject", []) or []),
                    "block": block["name"],
                })
            got += len(items)
            cursor = (data.get("message", {}) or {}).get("next-cursor")
            if not cursor:
                break
            time.sleep(0.3)
        print(f"   coletados: {got}")

    df = pd.DataFrame(rows, columns=UNIFIED_COLS)
    out = os.path.join(RAW_DIR, "crossref_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[Crossref] {len(df):,} registros -> {out}")


if __name__ == "__main__":
    main()
