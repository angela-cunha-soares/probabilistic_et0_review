"""
Utilitários compartilhados: construção de queries, HTTP com rate-limit/retry,
e esquema unificado de registro para fundir múltiplas bases.

Esquema unificado (uma linha = um documento):
  id, source, doi, title, abstract, year, venue, authors,
  country_codes, cited_by_count, keywords, block
"""

import json
import time
import urllib.parse
import urllib.request

from config import CONTACT_EMAIL

UNIFIED_COLS = [
    "id", "source", "doi", "title", "abstract", "year", "venue",
    "authors", "institutions", "country_codes", "cited_by_count",
    "is_oa", "oa_status", "issn", "keywords", "block",
]


# ----------------------------------------------------------------------
# HTTP educado com retry exponencial (trata 429/503)
# ----------------------------------------------------------------------
def http_get_json(url, tries=5, pause=1.0):
    headers = {"User-Agent": f"EVAonline-review ({CONTACT_EMAIL})",
               "Accept": "application/json"}
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < tries - 1:
                wait = pause * (2 ** attempt)
                print(f"    HTTP {e.code}; aguardando {wait:.0f}s...")
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt < tries - 1:
                time.sleep(pause * (2 ** attempt))
                continue
            raise
    return None


# ----------------------------------------------------------------------
# Construção de query booleana a partir dos grupos AND/OR do config
# ----------------------------------------------------------------------
def _q(term):
    """Coloca aspas em termos multi-palavra."""
    return f'"{term}"' if " " in term else term


def build_boolean(and_groups):
    """[[a,b],[c,d]] -> (a OR b) AND (c OR d)"""
    parts = []
    for group in and_groups:
        parts.append("(" + " OR ".join(_q(t) for t in group) + ")")
    return " AND ".join(parts)


# ----------------------------------------------------------------------
# Normalização do abstract invertido do OpenAlex
# ----------------------------------------------------------------------
def openalex_abstract(inv_index):
    if not inv_index:
        return ""
    positions = []
    for word, idxs in inv_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)
