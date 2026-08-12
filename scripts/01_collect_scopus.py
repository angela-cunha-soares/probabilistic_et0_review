"""
Coletor Scopus (confirmatório) — Scopus Search API (view COMPLETE).

Autenticação por API key (variável de ambiente SCOPUS_API_KEY). A view COMPLETE
retorna abstract, palavras-chave de autor e afiliação/país. O acesso COMPLETE
depende de a chave/IP estarem habilitados (assinatura institucional / VPN).

Usa a API REST diretamente (urllib), o que evita a configuração interativa do
pybliometrics; o pybliometrics (ScopusSearch/AbstractRetrieval) é uma alternativa
equivalente caso você prefira.

Retomável e time-boxed (mesmo padrão do coletor OpenAlex): grava o cursor e faz
append por página, para caber em execuções curtas.
"""

import os
import time
import urllib.parse
import urllib.request
import pandas as pd

from config import BLOCKS, YEAR_MIN, YEAR_MAX, RAW_DIR, SCOPUS_API_KEY
from lib_sources import UNIFIED_COLS

BASE = "https://api.elsevier.com/content/search/scopus"

# país (nome Scopus) -> ISO alpha-2, para bater com os códigos do OpenAlex
try:
    import pycountry
    def to_iso2(name):
        if not name:
            return None
        try:
            return pycountry.countries.lookup(name).alpha_2
        except Exception:
            try:
                m = pycountry.countries.search_fuzzy(name)
                return m[0].alpha_2 if m else None
            except Exception:
                return None
except ImportError:
    def to_iso2(name):
        return None


def _bool(groups):
    parts = []
    for g in groups:
        ors = " OR ".join(f'"{t}"' if " " in t else t for t in g)
        parts.append(f"({ors})")
    return " AND ".join(parts)


def scopus_query(block):
    segs = []
    if block.get("title"):
        segs.append(f"TITLE({_bool(block['title'])})")
    segs.append(f"TITLE-ABS-KEY({_bool(block['abs'])})")
    return f"{' AND '.join(segs)} AND PUBYEAR > {YEAR_MIN - 1}"


def _get(query, cursor, count=25):
    params = urllib.parse.urlencode({
        "query": query, "count": count, "view": "COMPLETE", "cursor": cursor})
    req = urllib.request.Request(
        f"{BASE}?{params}",
        headers={"X-ELS-APIKey": SCOPUS_API_KEY, "Accept": "application/json"})
    import json
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** attempt); continue
            raise


def _parse_entry(e, block_name):
    aff = e.get("affiliation", []) or []
    iso = sorted({c for c in (to_iso2(a.get("affiliation-country")) for a in aff) if c})
    institutions = "; ".join(sorted({a.get("affilname", "") for a in aff
                                     if a.get("affilname")}))
    authors = e.get("author", []) or []
    auth_names = "; ".join(a.get("authname", "") for a in authors) or e.get("dc:creator", "")
    year = None
    cd = e.get("prism:coverDate")
    if cd:
        year = int(cd[:4])
    kw = (e.get("authkeywords") or "").replace(" | ", ";")
    return {
        "id": e.get("eid"), "source": "scopus",
        "doi": e.get("prism:doi", "") or "",
        "title": e.get("dc:title", "") or "",
        "abstract": e.get("dc:description", "") or "",
        "year": year,
        "venue": e.get("prism:publicationName", "") or "",
        "authors": auth_names,
        "institutions": institutions,
        "country_codes": ";".join(iso),
        "cited_by_count": int(e.get("citedby-count", 0) or 0),
        "is_oa": bool(e.get("openaccessFlag", False)),
        "oa_status": "gold" if str(e.get("openaccess", "0")) == "1" else "",
        "issn": e.get("prism:issn", "") or e.get("prism:eIssn", "") or "",
        "field": "",  # OpenAlex fornece 'field'; Scopus não no retorno da busca
        "keywords": kw,
        "block": block_name,
    }


def collect_block(block, time_budget=None, start_cursor="*", sink=None):
    query = scopus_query(block)
    rows, cursor, page = [], start_cursor, 0
    t0 = time.time()
    print(f"\n[Scopus] Bloco '{block['name']}'")
    while cursor:
        if time_budget and (time.time() - t0) > time_budget:
            print("    [tempo esgotado] retomar com cursor salvo")
            return rows, cursor
        data = _get(query, cursor)
        sr = data.get("search-results", {})
        entries = sr.get("entry", []) or []
        if not entries or "error" in entries[0]:
            break
        page_rows = []
        for e in entries:
            if int(e.get("prism:coverDate", "9999")[:4]) > YEAR_MAX:
                continue
            page_rows.append(_parse_entry(e, block["name"]))
        rows.extend(page_rows)
        if sink:
            sink(page_rows)
        nxt = (sr.get("cursor") or {}).get("@next")
        cursor = nxt if nxt and nxt != cursor else None
        page += 1
        print(f"    página {page}: acumulado {len(rows):,}")
        time.sleep(0.3)
    return rows, None


def main():
    if not SCOPUS_API_KEY:
        print("[Scopus] SCOPUS_API_KEY não definida — etapa pulada.")
        return
    all_rows = []
    for block in BLOCKS:
        rows, _ = collect_block(block)
        all_rows.extend(rows)
    df = pd.DataFrame(all_rows, columns=UNIFIED_COLS)
    out = os.path.join(RAW_DIR, "scopus_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[Scopus] {len(df):,} registros -> {out}")


if __name__ == "__main__":
    main()
