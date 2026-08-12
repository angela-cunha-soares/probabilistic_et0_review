"""
Coletor IEEE Xplore (confirmatório) — IEEE Xplore Metadata Search API.

Autenticação por API key (variável de ambiente IEEE_API_KEY). Retorna metadados
+ resumo (view "Metadata Search"). Limites: 10 chamadas/s e 200 chamadas/dia;
cada chamada traz até 200 registros -> ~40 mil registros/dia, folgado.

Retomável: grava o próximo start_record por bloco em ieee_block{idx}.cursor e faz
append em ieee_block{idx}.csv, então recombina em ieee_raw.csv (que o merge lê).

Uso:
  setx IEEE_API_KEY "..."   (PowerShell; feche e reabra o terminal)
  python scripts/02_collect_ieee.py
"""

import os
import glob
import time
import json
import urllib.parse
import urllib.request
import pandas as pd

from config import BLOCKS, YEAR_MIN, YEAR_MAX, RAW_DIR, IEEE_API_KEY
from lib_sources import UNIFIED_COLS

BASE = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
PER_CALL = 200            # máximo do IEEE
DAILY_CALL_CAP = 190      # margem sob o limite de 200/dia

# ------------------------------------------------------------- país -> ISO2
_ISO = {}
_FIX = {"usa": "US", "united states": "US", "uk": "GB", "u k": "GB",
        "england": "GB", "scotland": "GB", "wales": "GB", "china": "CN",
        "p r china": "CN", "peoples r china": "CN", "south korea": "KR",
        "korea": "KR", "russia": "RU", "iran": "IR", "vietnam": "VN",
        "taiwan": "TW", "uae": "AE", "netherlands": "NL", "the netherlands": "NL"}
try:
    import pycountry

    def to_iso2(name):
        k = (name or "").strip().lower().rstrip(".")
        if not k:
            return None
        if k in _ISO:
            return _ISO[k]
        r = _FIX.get(k)
        if r is None:
            try:
                r = pycountry.countries.lookup(k).alpha_2
            except Exception:
                r = None
        _ISO[k] = r
        return r
except ImportError:
    def to_iso2(name):
        return None


def _or(terms):
    return "(" + " OR ".join(f'"{t}"' if (" " in t or "-" in t) else t
                             for t in terms) + ")"


def _and(groups):
    return " AND ".join(_or(g) for g in groups)


def _country_from_aff(aff):
    if not aff:
        return None
    parts = [p.strip() for p in str(aff).split(",") if p.strip()]
    return to_iso2(parts[-1]) if parts else None


def _doctype(content_type):
    t = (content_type or "").lower()
    if "conference" in t or "proceeding" in t:
        return "Proceedings"
    if "book" in t or "course" in t or "standard" in t:
        return "Book chapter"
    return "Article"          # Journals / Magazines / Early Access / Letters


def _params_for(block):
    """Monta os parâmetros de busca. Bloco A usa article_title (ET0 no título) E
    querytext (termos de ferramenta/IA). Bloco B usa querytext booleano."""
    p = {}
    if block.get("title"):
        p["article_title"] = _and(block["title"])   # (ET0 OR ...) no título
        p["querytext"] = _and(block["abs"])          # ferramentas/IA nos metadados
    else:
        p["querytext"] = _and(block["abs"])          # (irrig) AND (método) AND ...
    return p


def _get(search_params, start_record):
    q = dict(search_params)
    q.update({"apikey": IEEE_API_KEY, "format": "json",
              "max_records": PER_CALL, "start_record": start_record,
              "start_year": YEAR_MIN, "end_year": YEAR_MAX,
              "sort_field": "publication_year", "sort_order": "asc"})
    url = f"{BASE}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 401):
                body = e.read().decode("utf-8", "ignore")[:200]
                raise SystemExit(
                    f"[IEEE] HTTP {e.code}: chave inativa ou não autorizada.\n"
                    f"       A chave recém-criada costuma ficar 'waiting' por "
                    f"algumas horas/dias. Detalhe: {body}")
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


def _parse(a, block_name):
    authors, insts, isos = [], [], set()
    au = (a.get("authors") or {}).get("authors", []) or []
    for x in au:
        if x.get("full_name"):
            authors.append(x["full_name"])
        aff = x.get("affiliation")
        if aff:
            insts.append(aff)
            c = _country_from_aff(aff)
            if c:
                isos.add(c)
    it = a.get("index_terms") or {}
    kws = ((it.get("author_terms") or {}).get("terms", []) or [])
    ieee_terms = ((it.get("ieee_terms") or {}).get("terms", []) or [])
    return {
        "id": (a.get("doi") or a.get("article_number") or a.get("title", ""))[:120],
        "source": "ieee",
        "doi": a.get("doi", "") or "",
        "title": a.get("title", "") or "",
        "abstract": a.get("abstract", "") or "",
        "year": pd.to_numeric(a.get("publication_year"), errors="coerce"),
        "venue": a.get("publication_title", "") or "",
        "authors": "; ".join(authors),
        "institutions": "; ".join(dict.fromkeys(insts)),
        "country_codes": ";".join(sorted(isos)),
        "cited_by_count": int(a.get("citing_paper_count", 0) or 0),
        "is_oa": bool(a.get("is_open_access", False)),
        "oa_status": "gold" if a.get("is_open_access") else "",
        "issn": (a.get("issn") or a.get("isbn") or "") or "",
        "field": "; ".join(ieee_terms),
        "doc_type": _doctype(a.get("content_type")),
        "keywords": "; ".join(kws),
        "block": block_name,
    }


def collect_block(block, idx, calls_left):
    cur_fp = os.path.join(RAW_DIR, f"ieee_block{idx}.cursor")
    out_fp = os.path.join(RAW_DIR, f"ieee_block{idx}.csv")
    start = 1
    if os.path.exists(cur_fp):
        v = open(cur_fp).read().strip()
        if v == "DONE":
            print(f"[IEEE] Bloco '{block['name']}' já concluído.")
            return calls_left
        start = int(v or "1")
    params = _params_for(block)
    print(f"\n[IEEE] Bloco '{block['name']}' (a partir do registro {start})")
    total = None
    while calls_left > 0:
        data = _get(params, start)
        if total is None:
            total = int(data.get("total_records", 0) or 0)
            print(f"    total_records = {total:,}")
        calls_left -= 1
        arts = data.get("articles", []) or []
        if not arts:
            open(cur_fp, "w").write("DONE")
            break
        rows = [_parse(a, block["name"]) for a in arts]
        df = pd.DataFrame(rows, columns=UNIFIED_COLS)
        df.to_csv(out_fp, mode="a", header=not os.path.exists(out_fp),
                  index=False, encoding="utf-8-sig")
        start += len(arts)
        open(cur_fp, "w").write(str(start))
        print(f"    +{len(arts)} (acumulado até registro {start-1} de {total:,}); "
              f"chamadas restantes hoje ~{calls_left}")
        if total and start > total:
            open(cur_fp, "w").write("DONE")
            break
        time.sleep(0.2)          # < 10 chamadas/s
    if calls_left <= 0:
        print("    [limite diário] pare e retome amanhã — o cursor foi salvo.")
    return calls_left


def combine():
    frames = []
    for fp in sorted(glob.glob(os.path.join(RAW_DIR, "ieee_block*.csv"))):
        d = pd.read_csv(fp, dtype=str)
        if len(d):
            frames.append(d)
    if not frames:
        return 0
    df = pd.concat(frames, ignore_index=True)
    # dedup interno por DOI (mantém maior abstract), depois por título
    df["_l"] = df["abstract"].fillna("").str.len()
    df = df.sort_values("_l", ascending=False)
    has = df["doi"].fillna("").str.strip() != ""
    df = pd.concat([df[has].drop_duplicates("doi"),
                    df[~has].drop_duplicates("title")]).drop(columns="_l")
    out = os.path.join(RAW_DIR, "ieee_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return len(df)


def main():
    if not IEEE_API_KEY:
        print("[IEEE] IEEE_API_KEY não definida — etapa pulada. "
              "Rode: setx IEEE_API_KEY \"...\" e reabra o terminal.")
        return
    calls_left = DAILY_CALL_CAP
    for idx, block in enumerate(BLOCKS):
        calls_left = collect_block(block, idx, calls_left)
        if calls_left <= 0:
            break
    n = combine()
    print(f"\n[IEEE] ieee_raw.csv com {n:,} registros únicos.")
    print("Agora rode: python scripts/04_merge_dedup_prisma.py")


if __name__ == "__main__":
    main()
