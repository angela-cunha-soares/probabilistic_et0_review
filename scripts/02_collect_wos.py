"""
Coletor Web of Science — **WoS API Expanded** (confirmatório/triangulação).

Endpoint : https://wos-api.clarivate.com/api/wos
Auth     : header  X-ApiKey: <WOS_API_KEY>
Query    : usrQuery=TS=(...) AND TI=(...)   (linguagem de busca do WoS)
Paginação: firstRecord (1-based) + count (máx 100)

A resposta é um JSON profundamente aninhado (Records.records.REC[...]); usamos
acessos defensivos e convertemos país (nome) -> ISO alpha-2 para bater com as
outras bases. Retomável/time-boxed no mesmo padrão dos demais coletores.

Configuração:
    export WOS_API_KEY="sua_chave_expanded"
Se não houver chave, o script avisa e sai.
"""

import os
import time
import json
import urllib.parse
import urllib.request
import pandas as pd

from config import BLOCKS, YEAR_MIN, YEAR_MAX, RAW_DIR, WOS_API_KEY
from lib_sources import UNIFIED_COLS

BASE = "https://wos-api.clarivate.com/api/wos"
COUNT = 100  # máx por página na Expanded

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


# ----------------------------------------------------------------------
# Acesso defensivo a estruturas aninhadas (campos ora dict, ora lista)
# ----------------------------------------------------------------------
def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _dig(d, *keys):
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def wos_query(block):
    def grp(groups):
        parts = []
        for g in groups:
            ors = " OR ".join(f'"{t}"' if " " in t else t for t in g)
            parts.append(f"({ors})")
        return " AND ".join(parts)
    segs = []
    if block.get("title"):
        segs.append(f"TI=({grp(block['title'])})")
    segs.append(f"TS=({grp(block['abs'])})")
    yr = f"PY=({YEAR_MIN}-{YEAR_MAX})"
    return " AND ".join(segs) + f" AND {yr}"


def _get(query, first_record):
    params = urllib.parse.urlencode({
        "databaseId": "WOS", "usrQuery": query,
        "count": COUNT, "firstRecord": first_record})
    req = urllib.request.Request(
        f"{BASE}?{params}",
        headers={"X-ApiKey": WOS_API_KEY, "Accept": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** attempt); continue
            raise


def _parse_rec(rec, block_name):
    # título do artigo e do periódico
    titles = _as_list(_dig(rec, "static_data", "summary", "titles", "title"))
    title = venue = ""
    for t in titles:
        if isinstance(t, dict):
            if t.get("type") == "item":
                title = t.get("content", "")
            elif t.get("type") == "source":
                venue = t.get("content", "")
    # ano
    year = _dig(rec, "static_data", "summary", "pub_info", "pubyear")
    # autores
    names = _as_list(_dig(rec, "static_data", "summary", "names", "name"))
    authors = "; ".join(n.get("full_name", "") for n in names if isinstance(n, dict))
    # países (afiliações)
    addrs = _as_list(_dig(rec, "static_data", "fullrecord_metadata",
                          "addresses", "address_name"))
    iso = set()
    for a in addrs:
        c = _dig(a, "address_spec", "country")
        code = to_iso2(c)
        if code:
            iso.add(code)
    # palavras-chave de autor
    kws = _as_list(_dig(rec, "static_data", "fullrecord_metadata",
                        "keywords", "keyword"))
    keywords = "; ".join(k if isinstance(k, str) else k.get("content", "")
                         for k in kws)
    # abstract
    paras = _as_list(_dig(rec, "static_data", "fullrecord_metadata",
                          "abstracts", "abstract", "abstract_text", "p"))
    abstract = " ".join(p if isinstance(p, str) else p.get("content", "")
                        for p in paras)
    # citações
    tc = _dig(rec, "dynamic_data", "citation_related", "tc_list",
              "silo_tc", "local_count") or 0
    # DOI
    doi = ""
    ids = _as_list(_dig(rec, "dynamic_data", "cluster_related",
                        "identifiers", "identifier"))
    for i in ids:
        if isinstance(i, dict) and i.get("type") in ("doi", "xref_doi"):
            doi = i.get("value", ""); break
    return {
        "id": rec.get("UID", ""), "source": "wos",
        "doi": doi, "title": title, "abstract": abstract,
        "year": int(year) if year else None,
        "venue": venue, "authors": authors,
        "country_codes": ";".join(sorted(iso)),
        "cited_by_count": int(tc) if str(tc).isdigit() else 0,
        "keywords": keywords, "block": block_name,
    }


def collect_block(block, time_budget=None, start_cursor="1", sink=None):
    query = wos_query(block)
    rows = []
    first = int(start_cursor)
    total = None
    t0 = time.time()
    print(f"\n[WoS] Bloco '{block['name']}'")
    while True:
        if time_budget and (time.time() - t0) > time_budget:
            print("    [tempo esgotado] retomar com firstRecord salvo")
            return rows, str(first)
        data = _get(query, first)
        qr = _dig(data, "QueryResult") or {}
        if total is None:
            total = qr.get("RecordsFound", 0)
            print(f"    total encontrado: {total}")
        recs = _as_list(_dig(data, "Data", "Records", "records", "REC"))
        if not recs:
            break
        page_rows = [_parse_rec(r, block["name"]) for r in recs]
        rows.extend(page_rows)
        if sink:
            sink(page_rows)
        first += len(recs)
        print(f"    {min(first-1, total)}/{total}")
        if first > (total or 0):
            break
        time.sleep(0.5)  # respeita rate-limit (2-5 req/s conforme plano)
    return rows, None


def main():
    if not WOS_API_KEY:
        print("[WoS] WOS_API_KEY não definida — etapa pulada. "
              "Defina a variável de ambiente (WoS API Expanded).")
        return
    all_rows = []
    for block in BLOCKS:
        rows, _ = collect_block(block)
        all_rows.extend(rows)
    df = pd.DataFrame(all_rows, columns=UNIFIED_COLS)
    out = os.path.join(RAW_DIR, "wos_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[WoS] {len(df):,} registros -> {out}")


if __name__ == "__main__":
    main()
