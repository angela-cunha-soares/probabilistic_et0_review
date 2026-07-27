"""
Ingestão de EXPORTAÇÕES da Web of Science (sem API).

Lê arquivos exportados da plataforma WoS (formato Tab-delimited com field-tags,
ou RIS) colocados em data/raw/wos_export/, normaliza para o esquema unificado e
grava data/raw/wos_raw.csv — que o 04_merge_dedup_prisma.py já sabe fundir.

Uso:
  1. Exporte da WoS (ver WOS_EXPORT_GUIDE.md), "Full Record".
  2. Coloque os arquivos em data/raw/wos_export/  (.txt/.tsv tab-delimited, ou .ris)
  3. python scripts/11_ingest_wos_export.py
"""

import os
import glob
import pandas as pd

from config import RAW_DIR
from lib_sources import UNIFIED_COLS

EXPORT_DIR = os.path.join(RAW_DIR, "wos_export")

try:
    import pycountry
    def to_iso2(name):
        try:
            return pycountry.countries.lookup(name.strip()).alpha_2
        except Exception:
            try:
                m = pycountry.countries.search_fuzzy(name.strip())
                return m[0].alpha_2 if m else None
            except Exception:
                return None
except ImportError:
    def to_iso2(name):
        return None


def _countries_from_addresses(addr_field):
    """C1/addresses WoS: cada endereço termina no país (último token por vírgula)."""
    iso = set()
    if not addr_field:
        return ""
    # separadores comuns: '; ' entre endereços, e '[...]' de autores
    import re
    for chunk in re.split(r";|\[", str(addr_field)):
        parts = [p.strip() for p in chunk.split(",") if p.strip()]
        if parts:
            code = to_iso2(parts[-1].replace(".", ""))
            if code:
                iso.add(code)
    return ";".join(sorted(iso))


# ----------------------------------------------------------------------
# Tab-delimited (field tags: TI, AB, DE, DI, PY, SO, TC, AU, C1, UT ...)
# ----------------------------------------------------------------------
def parse_tab(path):
    df = pd.read_csv(path, sep="\t", dtype=str, quoting=3, on_bad_lines="skip",
                     encoding="utf-8-sig")
    def col(*names):
        for n in names:
            if n in df.columns:
                return df[n]
        return pd.Series([""] * len(df))
    out = pd.DataFrame({
        "id": col("UT", "Accession Number").fillna(""),
        "source": "wos",
        "doi": col("DI", "DOI").fillna(""),
        "title": col("TI", "Article Title").fillna(""),
        "abstract": col("AB", "Abstract").fillna(""),
        "year": pd.to_numeric(col("PY", "Publication Year"), errors="coerce"),
        "venue": col("SO", "Source Title").fillna(""),
        "authors": col("AU", "Authors").fillna("").str.replace("; ", "; "),
        "country_codes": col("C1", "Addresses").fillna("").map(_countries_from_addresses),
        "cited_by_count": pd.to_numeric(
            col("TC", "Times Cited, WoS Core", "Times Cited, All Databases"),
            errors="coerce").fillna(0).astype(int),
        "keywords": col("DE", "Author Keywords").fillna(""),
        "block": "",
    })
    return out


# ----------------------------------------------------------------------
# RIS (TY/AU/TI/T2/AB/KW/DO/PY/UT)
# ----------------------------------------------------------------------
def parse_ris(path):
    recs, cur = [], {}
    for line in open(path, encoding="utf-8-sig", errors="ignore"):
        line = line.rstrip("\n")
        if len(line) >= 6 and line[:2].isalnum() and line[2:6] == "  - ":
            tag, val = line[:2], line[6:]
            if tag == "TY":
                cur = {"kw": [], "au": []}
            if tag in ("KW",):
                cur["kw"].append(val)
            elif tag in ("AU", "A1"):
                cur["au"].append(val)
            else:
                cur[tag] = val
        elif line.strip() == "ER" or line.startswith("ER  -"):
            if cur:
                recs.append(cur); cur = {}
    rows = []
    for r in recs:
        rows.append({
            "id": r.get("UT", r.get("DO", "")), "source": "wos",
            "doi": r.get("DO", ""), "title": r.get("TI", r.get("T1", "")),
            "abstract": r.get("AB", ""),
            "year": pd.to_numeric(r.get("PY", ""), errors="coerce"),
            "venue": r.get("T2", r.get("JO", "")),
            "authors": "; ".join(r.get("au", [])),
            "country_codes": _countries_from_addresses(r.get("AD", "")),
            "cited_by_count": pd.to_numeric(r.get("Z9", r.get("TC", "0")),
                                            errors="coerce") or 0,
            "keywords": "; ".join(r.get("kw", [])), "block": "",
        })
    return pd.DataFrame(rows)


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(EXPORT_DIR, "*"))
    if not files:
        print(f"[WoS] Nenhum arquivo em {EXPORT_DIR}. "
              f"Exporte da WoS (ver WOS_EXPORT_GUIDE.md) e coloque os arquivos lá.")
        return
    frames = []
    for f in files:
        try:
            head = open(f, encoding="utf-8-sig", errors="ignore").read(400)
            if "TY  -" in head or "\nER" in head:
                d = parse_ris(f)
            else:
                d = parse_tab(f)
            d = d[d["title"].fillna("").str.len() > 0]
            frames.append(d[[c for c in UNIFIED_COLS if c in d.columns]])
            print(f"  + {os.path.basename(f):40s} {len(d):>6} registros")
        except Exception as e:
            print(f"  ! {os.path.basename(f)}: {type(e).__name__}: {str(e)[:80]}")
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset="id")
    out = os.path.join(RAW_DIR, "wos_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[WoS] {len(df):,} registros -> {out}")
    print("Agora rode: python scripts/04_merge_dedup_prisma.py")


if __name__ == "__main__":
    main()
