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
from lib_sources import UNIFIED_COLS, normalize_doctype

EXPORT_DIR = os.path.join(RAW_DIR, "wos_export")

_ISO_CACHE = {}
# nomes de país como aparecem na WoS que o lookup direto não resolve
_WOS_FIX = {
    "usa": "US", "united states": "US", "u arab emirates": "AE",
    "peoples r china": "CN", "china": "CN", "england": "GB", "scotland": "GB",
    "wales": "GB", "north ireland": "GB", "u k": "GB", "south korea": "KR",
    "russia": "RU", "iran": "IR", "vietnam": "VN", "taiwan": "TW",
    "czech republic": "CZ", "byelarus": "BY", "trinid & tobago": "TT",
    "bosnia & herceg": "BA", "cote ivoire": "CI", "dem rep congo": "CD",
}
try:
    import pycountry

    def to_iso2(name):
        key = (name or "").strip().lower().rstrip(".")
        if not key:
            return None
        if key in _ISO_CACHE:
            return _ISO_CACHE[key]
        res = _WOS_FIX.get(key)
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
            "id": r.get("UT") or r.get("AN") or r.get("DO", ""), "source": "wos",
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


def _bib_fields(body):
    """Extrai os campos de um corpo de entrada BibTeX (uma passada, rápido)."""
    import re as _re
    fields, pos, L = {}, 0, len(body)
    c = body.find(",")
    pos = c + 1 if c >= 0 else 0          # pula a chave de citação
    while pos < L:
        eq = body.find("=", pos)
        if eq < 0:
            break
        name = body[pos:eq].strip().lower()
        v = eq + 1
        while v < L and body[v] in " \t\r\n":
            v += 1
        if v >= L:
            break
        if body[v] == "{":
            depth, s = 0, v
            while v < L:
                if body[v] == "{":
                    depth += 1
                elif body[v] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                v += 1
            value = body[s + 1:v]
            pos = v + 1
        elif body[v] == '"':
            s = v + 1
            v = s
            while v < L and body[v] != '"':
                v += 1
            value = body[s:v]
            pos = v + 1
        else:
            s = v
            while v < L and body[v] not in ",\n":
                v += 1
            value = body[s:v].strip()
            pos = v
        nc = body.find(",", pos)
        pos = nc + 1 if nc >= 0 else L
        if name:
            fields[name] = _re.sub(r"\s+", " ", value).strip()
    return fields


def _wos_countries(aff_singular):
    """No BibTeX da WoS, o campo 'Affiliation' (singular) traz endereços completos
    separados por '.', cada um terminando em ', País'. Extrai os países -> ISO."""
    iso = set()
    for chunk in str(aff_singular).split("."):
        parts = [p.strip() for p in chunk.split(",") if p.strip()]
        if parts:
            code = to_iso2(parts[-1])
            if code:
                iso.add(code)
    return ";".join(sorted(iso))


def parse_bib(path):
    """BibTeX da WoS (Full Record): traz Keywords, Affiliations e Times-Cited,
    que o RIS omite. Parser manual (rápido)."""
    import re as _re
    text = open(path, encoding="utf-8-sig", errors="ignore").read()
    rows, n = [], len(text)
    starts = [m.start() for m in _re.finditer(r"(?m)^@\w+\s*\{", text)]
    for k, at in enumerate(starts):
        br = text.find("{", at)
        depth, j = 0, br
        while j < n:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        e = _bib_fields(text[br + 1:j])
        if not e.get("title"):
            continue
        insts = e.get("affiliations", "")   # plural = nomes de instituição
        tc = "".join(c for c in e.get("times-cited", "") if c.isdigit())
        rows.append({
            "id": e.get("unique-id", "") or e.get("doi", ""), "source": "wos",
            "doi": e.get("doi", ""),
            "title": e.get("title", "").replace("{", "").replace("}", ""),
            "abstract": e.get("abstract", ""),
            "year": pd.to_numeric(e.get("year", ""), errors="coerce"),
            "venue": e.get("journal", "") or e.get("journal-iso", ""),
            "authors": "; ".join(a.strip() for a in e.get("author", "").split(" and ")),
            "institutions": "; ".join(x.strip() for x in insts.split(";") if x.strip()),
            "country_codes": _wos_countries(e.get("affiliation", "")),
            "cited_by_count": int(tc) if tc else 0,
            "is_oa": "", "oa_status": "",
            "issn": e.get("issn", "") or e.get("eissn", ""),
            "field": e.get("research-areas", ""),
            "doc_type": normalize_doctype(e.get("type", "")),
            "keywords": e.get("keywords", "") or e.get("keywords-plus", ""),
            "block": "",
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
            if f.lower().endswith(".bib") or head.lstrip().startswith("@"):
                d = parse_bib(f)
            elif "TY  -" in head or "\nER" in head:
                d = parse_ris(f)
            else:
                d = parse_tab(f)
            d = d[d["title"].fillna("").str.len() > 0]
            # infere o bloco pelo nome do arquivo (wos_blocoA_* / wos_blocoB_*)
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
    df = df.drop_duplicates(subset="id")
    out = os.path.join(RAW_DIR, "wos_raw.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[WoS] {len(df):,} registros -> {out}")
    print("Agora rode: python scripts/04_merge_dedup_prisma.py")


if __name__ == "__main__":
    main()
