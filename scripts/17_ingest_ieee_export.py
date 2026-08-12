"""
Ingestão de EXPORTAÇÕES do IEEE Xplore (sem API).

Lê os CSV exportados do IEEE Xplore (Export -> Citations -> CSV, "Citation and
Abstract") colocados em data/raw/ieee_export/, normaliza para o esquema unificado
e grava data/raw/ieee_raw.csv — que o 04_merge_dedup_prisma.py já sabe fundir.

Uso:
  1. Exporte do IEEE Xplore (ver IEEE_EXPORT_GUIDE.md), formato CSV com resumo.
  2. Coloque os arquivos em data/raw/ieee_export/  (nomeie com blocoA/blocoB).
  3. python scripts/17_ingest_ieee_export.py
"""

import os
import glob
import re
import pandas as pd

from config import RAW_DIR
from lib_sources import UNIFIED_COLS, normalize_doctype

EXPORT_DIR = os.path.join(RAW_DIR, "ieee_export")

# ---------------------------------------------------------------- país -> ISO2
_ISO_CACHE = {}
_FIX = {
    "usa": "US", "united states": "US", "u arab emirates": "AE", "uae": "AE",
    "peoples r china": "CN", "p r china": "CN", "china": "CN", "england": "GB",
    "scotland": "GB", "wales": "GB", "uk": "GB", "u k": "GB", "south korea": "KR",
    "korea": "KR", "russia": "RU", "iran": "IR", "vietnam": "VN", "taiwan": "TW",
    "czech republic": "CZ", "the netherlands": "NL", "netherlands": "NL",
}
try:
    import pycountry

    def to_iso2(name):
        key = (name or "").strip().lower().rstrip(".")
        if not key:
            return None
        if key in _ISO_CACHE:
            return _ISO_CACHE[key]
        res = _FIX.get(key)
        if res is None:
            try:
                res = pycountry.countries.lookup(key).alpha_2
            except Exception:
                res = None
        _ISO_CACHE[key] = res
        return res
except ImportError:
    def to_iso2(name):
        return None


def _countries(aff_field):
    """Afiliações do IEEE: instituições separadas por ';', cada uma termina no
    país (último token por vírgula). Extrai os países -> ISO2."""
    iso = set()
    if not isinstance(aff_field, str) or not aff_field.strip():
        return ""
    for chunk in re.split(r";", aff_field):
        parts = [p.strip() for p in chunk.split(",") if p.strip()]
        if parts:
            code = to_iso2(parts[-1])
            if code:
                iso.add(code)
    return ";".join(sorted(iso))


def _doctype_from_identifier(val):
    """Coluna 'Document Identifier' do IEEE: 'IEEE Conferences', 'IEEE Journals',
    'IEEE Magazines', 'IEEE Early Access Articles', 'IEEE Books'..."""
    t = (val or "").lower()
    if "conference" in t or "proceeding" in t:
        return "Proceedings"
    if "book" in t or "course" in t or "standard" in t:
        return "Book chapter"
    if "journal" in t or "magazine" in t or "early access" in t or "letter" in t:
        return "Article"
    return normalize_doctype(val)


def parse_ieee_csv(path):
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", on_bad_lines="skip")
    # normaliza cabeçalhos (o IEEE às vezes muda a caixa/underscore)
    df.columns = [c.strip() for c in df.columns]

    def col(*names):
        for n in names:
            for real in df.columns:
                if real.lower() == n.lower():
                    return df[real]
        return pd.Series([""] * len(df), index=df.index)

    doi = col("DOI").fillna("")
    title = col("Document Title", "Title").fillna("")
    out = pd.DataFrame({
        "id": doi.where(doi.str.strip() != "", title),
        "source": "ieee",
        "doi": doi,
        "title": title,
        "abstract": col("Abstract").fillna(""),
        "year": pd.to_numeric(col("Publication Year", "Year"), errors="coerce"),
        "venue": col("Publication Title", "Publication_Title").fillna(""),
        "authors": col("Authors").fillna(""),
        "institutions": col("Author Affiliations", "Author_Affiliations").fillna(""),
        "country_codes": col("Author Affiliations", "Author_Affiliations")
                         .fillna("").map(_countries),
        "cited_by_count": pd.to_numeric(
            col("Article Citation Count", "Citation Count"),
            errors="coerce").fillna(0).astype(int),
        "is_oa": "", "oa_status": "",
        "issn": col("ISSN").fillna(""),
        "field": col("IEEE Terms").fillna(""),
        "doc_type": col("Document Identifier").fillna("").map(_doctype_from_identifier),
        "keywords": col("Author Keywords", "Author_Keywords").fillna(""),
        "block": "",
    })
    return out


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(EXPORT_DIR, "*.csv"))
    if not files:
        print(f"[IEEE] Nenhum CSV em {EXPORT_DIR}. "
              f"Exporte do IEEE Xplore (ver IEEE_EXPORT_GUIDE.md) e coloque os "
              f"arquivos lá.")
        return
    frames = []
    for f in sorted(files):
        try:
            d = parse_ieee_csv(f)
            d = d[d["title"].fillna("").str.len() > 0]
            name = os.path.basename(f).lower()
            if "blocob" in name or "block_b" in name or "blockb" in name:
                d["block"] = "Irrigation_Decision"
            elif "blocoa" in name or "block_a" in name or "blocka" in name:
                d["block"] = "ETo_Software_Tools"
            frames.append(d[[c for c in UNIFIED_COLS if c in d.columns]])
            print(f"  + {os.path.basename(f):40s} {len(d):>6} registros")
        except Exception as e:
            print(f"  ! {os.path.basename(f)}: {type(e).__name__}: {str(e)[:80]}")
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    # dedup interno por DOI (mantém o de maior abstract) e por título
    df["_absl"] = df["abstract"].fillna("").str.len()
    df = df.sort_values("_absl", ascending=False)
    has_doi = df["doi"].fillna("").str.strip() != ""
    dd = pd.concat([
        df[has_doi].drop_duplicates(subset="doi"),
        df[~has_doi].drop_duplicates(subset="title"),
    ]).drop(columns="_absl")
    out = os.path.join(RAW_DIR, "ieee_raw.csv")
    dd.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[IEEE] {len(dd):,} registros -> {out}")
    conf = int((dd["doc_type"] == "Proceedings").sum())
    print(f"       (dos quais {conf} de conferência — serão auto-excluídos na triagem)")
    print("Agora rode: python scripts/04_merge_dedup_prisma.py")


if __name__ == "__main__":
    main()
