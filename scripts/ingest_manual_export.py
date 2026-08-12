"""
Ingestão GENÉRICA de exportações manuais -> esquema unificado do pipeline.

Um único script para TODAS as bases que você baixa à mão (ScienceDirect,
SpringerLink, Google Scholar/Publish-or-Perish, descoberta institucional, e
qualquer outra). Detecta o formato pelo conteúdo/extensão: **RIS**, **BibTeX**
ou **CSV** — sem dependências externas (só a biblioteca padrão + pandas).

USO
---
    # um arquivo:
    python scripts/ingest_manual_export.py data/raw/springer_export/springer_A.ris \
        --source springerlink --block A

    # uma pasta inteira (junta todos os .ris/.bib/.csv):
    python scripts/ingest_manual_export.py data/raw/sciencedirect_export \
        --source sciencedirect --block A

Saída: data/raw/<source>_raw.csv  (nomeie sempre com sufixo _raw para o merge
achar). Depois rode `python scripts/04_merge_dedup_prisma.py`.

IMPORTANTE (uma melhoria de 1 linha no merge): para que o merge capture
qualquer *_raw.csv automaticamente, troque em `04_merge_dedup_prisma.py`
a lista fixa `patterns` por:
    import glob as _g
    patterns = sorted({os.path.basename(p) for p in
                       _g.glob(os.path.join(RAW_DIR, '*_raw.csv'))} |
                      {os.path.basename(p) for p in
                       _g.glob(os.path.join(RAW_DIR, 'openalex_block*.csv'))})
"""

import argparse
import csv
import glob
import hashlib
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import RAW_DIR

# Esquema unificado de saída (superconjunto do que o merge consome).
UNIFIED = ["id", "source", "doi", "title", "abstract", "keywords", "venue",
           "year", "doc_type", "language", "authors", "cited_by_count", "block"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def clean(s):
    if s is None:
        return ""
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s


def norm_doi(s):
    s = clean(s).lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    return s


def year_of(s):
    m = re.search(r"(19|20)\d{2}", str(s))
    return m.group(0) if m else ""


def make_id(source, doi, title):
    key = norm_doi(doi) or re.sub(r"[^a-z0-9]", "", clean(title).lower())
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:12] if key else "na"
    return f"{source}:{h}"


# --------------------------------------------------------------------------
# Parsers (sem dependências externas)
# --------------------------------------------------------------------------
def parse_ris(text):
    """RIS: tags de 2 letras + '  - '. Registros separados por ER."""
    records, cur = [], {}
    kw, au = [], []
    for raw in text.splitlines():
        m = re.match(r"^([A-Z0-9]{2})\s+-\s?(.*)$", raw)
        if not m:
            # continuação de linha do campo anterior (abstracts longos)
            if raw.strip() and cur.get("_last"):
                cur[cur["_last"]] = clean(cur.get(cur["_last"], "") + " " + raw)
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "ER":
            cur["keywords"] = "; ".join(kw)
            cur["authors"] = "; ".join(au)
            records.append(cur)
            cur, kw, au = {}, [], []
            continue
        if tag in ("TI", "T1"):
            cur["title"] = val; cur["_last"] = "title"
        elif tag in ("AB", "N2"):
            cur["abstract"] = clean(cur.get("abstract", "") + " " + val); cur["_last"] = "abstract"
        elif tag == "KW":
            kw.append(val)
        elif tag == "AU":
            au.append(val)
        elif tag == "DO":
            cur["doi"] = val
        elif tag in ("JO", "JF", "T2", "J2"):
            cur.setdefault("venue", val)
        elif tag in ("PY", "Y1", "DA"):
            cur.setdefault("year", year_of(val))
        elif tag == "LA":
            cur["language"] = val
        elif tag == "TY":
            cur["doc_type"] = val
    if cur:  # arquivo sem ER final
        cur["keywords"] = "; ".join(kw); cur["authors"] = "; ".join(au)
        records.append(cur)
    return records


def parse_bibtex(text):
    """BibTeX minimalista: pega entradas @type{key, campo = {valor}, ...}."""
    records = []
    # separa entradas por '@' de nível superior
    for chunk in re.split(r"\n@", "\n" + text):
        chunk = chunk.strip()
        if not chunk or "{" not in chunk:
            continue
        mtype = re.match(r"^@?(\w+)\s*\{", "@" + chunk if not chunk.startswith("@") else chunk)
        dtype = mtype.group(1).lower() if mtype else ""
        rec = {"doc_type": dtype}
        # campos: nome = {..} | "..." | ..
        for fm in re.finditer(r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)", chunk):
            name = fm.group(1).lower()
            val = fm.group(2).strip().strip("{}").strip('"').strip()
            val = clean(re.sub(r"[{}]", "", val))
            if name in ("title",):
                rec["title"] = val
            elif name in ("abstract",):
                rec["abstract"] = val
            elif name in ("keywords", "author_keywords"):
                rec["keywords"] = val.replace(",", ";")
            elif name in ("doi",):
                rec["doi"] = val
            elif name in ("journal", "journaltitle", "booktitle", "series"):
                rec.setdefault("venue", val)
            elif name in ("year",):
                rec.setdefault("year", year_of(val))
            elif name in ("author",):
                rec["authors"] = val.replace(" and ", "; ")
            elif name in ("language",):
                rec["language"] = val
        if rec.get("title"):
            records.append(rec)
    return records


# Aliases de colunas para CSV (Scopus, WoS, IEEE, Google Scholar/PoP, Springer)
CSV_ALIASES = {
    "title": ["title", "document title", "article title", "ti"],
    "abstract": ["abstract", "ab"],
    "keywords": ["author keywords", "keywords", "index keywords", "de", "id"],
    "doi": ["doi", "di"],
    "venue": ["source title", "journal", "publication title", "so", "source", "venue"],
    "year": ["year", "publication year", "py"],
    "doc_type": ["document type", "type", "dt"],
    "language": ["language", "language of original document", "la"],
    "authors": ["authors", "author", "au", "author full names"],
    "cited_by_count": ["cited by", "citations", "cited by count", "times cited",
                       "cited by, all databases", "tc", "gs_cited"],
}


def parse_csv(path):
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", engine="python",
                     on_bad_lines="skip", quoting=csv.QUOTE_MINIMAL)
    lower = {c.lower().strip(): c for c in df.columns}
    out = []
    for _, row in df.iterrows():
        rec = {}
        for field, aliases in CSV_ALIASES.items():
            for a in aliases:
                if a in lower and clean(row.get(lower[a])):
                    rec[field] = clean(row.get(lower[a]))
                    break
        if rec.get("title"):
            out.append(rec)
    return out


def load_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".tsv"):
        return parse_csv(path)
    text = open(path, encoding="utf-8-sig", errors="ignore").read()
    if ext in (".bib", ".bibtex"):
        return parse_bibtex(text)
    if ext in (".ris", ".txt", ".nbib"):
        # heurística: se tem "TY  -" é RIS; se tem "@article" é bibtex
        if re.search(r"^TY\s+-", text, re.M):
            return parse_ris(text)
        if re.search(r"@\w+\s*\{", text):
            return parse_bibtex(text)
        return parse_ris(text)
    # fallback pela assinatura
    if re.search(r"^TY\s+-", text, re.M):
        return parse_ris(text)
    if re.search(r"@\w+\s*\{", text):
        return parse_bibtex(text)
    raise SystemExit(f"Formato não reconhecido: {path}")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Ingestão genérica de exportações manuais.")
    ap.add_argument("path", help="arquivo .ris/.bib/.csv OU pasta com vários")
    ap.add_argument("--source", required=True,
                    help="rótulo da base: springerlink | sciencedirect | "
                         "googlescholar | discovery | ...")
    ap.add_argument("--block", default="A", choices=["A", "B"],
                    help="A = ferramentas de ET0 ; B = irrigação sob incerteza")
    ap.add_argument("--out", default=None,
                    help="nome do CSV de saída (padrão: <source>_raw.csv)")
    args = ap.parse_args()

    if os.path.isdir(args.path):
        files = []
        for pat in ("*.ris", "*.bib", "*.bibtex", "*.csv", "*.txt", "*.nbib"):
            files += glob.glob(os.path.join(args.path, pat))
    else:
        files = [args.path]
    files = sorted(set(files))
    if not files:
        raise SystemExit(f"Nenhum arquivo encontrado em {args.path}")

    all_recs = []
    for fp in files:
        recs = load_file(fp)
        print(f"  + {os.path.basename(fp):40s} {len(recs):>6} registros")
        all_recs += recs

    rows = []
    for r in all_recs:
        title = clean(r.get("title"))
        if not title:
            continue
        doi = norm_doi(r.get("doi"))
        rows.append({
            "id": make_id(args.source, doi, title),
            "source": args.source,
            "doi": doi,
            "title": title,
            "abstract": clean(r.get("abstract")),
            "keywords": clean(r.get("keywords")),
            "venue": clean(r.get("venue")),
            "year": clean(r.get("year")) or year_of(r.get("year")),
            "doc_type": clean(r.get("doc_type")),
            "language": clean(r.get("language")),
            "authors": clean(r.get("authors")),
            "cited_by_count": clean(r.get("cited_by_count")),
            "block": args.block,
        })
    df = pd.DataFrame(rows, columns=UNIFIED)
    # dedup interno leve por (doi) ou (título normalizado)
    df["_k"] = df["doi"].where(df["doi"] != "",
                               df["title"].str.lower().str.replace(r"[^a-z0-9]", "", regex=True))
    before = len(df)
    df = df.drop_duplicates("_k").drop(columns="_k")

    out = args.out or f"{args.source}_raw.csv"
    out_path = os.path.join(RAW_DIR, out)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n[OK] {len(df):,} registros ({before - len(df)} duplicados internos "
          f"removidos) -> {out_path}")
    print(f"     source='{args.source}'  block='{args.block}'")


if __name__ == "__main__":
    main()
