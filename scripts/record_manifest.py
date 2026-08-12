"""
Registra a DATA DE BUSCA e a contagem por base (exigência do PRISMA 2020).

Varre data/raw/, conta registros por arquivo/base e grava um manifesto
versionável com a data da extração. Rode logo APÓS coletar/ingerir cada base
(antes do merge). O `search_date` de cada base é preservado entre execuções;
só é atualizado para as bases cujos arquivos mudaram.

Uso:
    python scripts/record_manifest.py                 # usa a data de hoje
    python scripts/record_manifest.py --date 2026-08-12
    python scripts/record_manifest.py --note "recoleta após adicionar IEEE"

Saída: data/raw/_manifest.json  (cite este arquivo na seção de Métodos)
"""

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import RAW_DIR, YEAR_MIN, YEAR_MAX

MANIFEST = os.path.join(RAW_DIR, "_manifest.json")


def count_rows(path):
    # conta linhas menos o cabeçalho, robusto a arquivos grandes
    try:
        with open(path, "rb") as f:
            n = sum(1 for _ in f)
        return max(n - 1, 0)
    except OSError:
        return 0


def file_sig(path):
    h = hashlib.md5()
    h.update(str(os.path.getsize(path)).encode())
    h.update(str(int(os.path.getmtime(path))).encode())
    return h.hexdigest()[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat(),
                    help="data da busca (YYYY-MM-DD); padrão = hoje")
    ap.add_argument("--note", default="", help="observação livre desta extração")
    args = ap.parse_args()

    prev = {}
    if os.path.exists(MANIFEST):
        try:
            prev = json.load(open(MANIFEST, encoding="utf-8")).get("sources", {})
        except Exception:
            prev = {}

    files = sorted(set(glob.glob(os.path.join(RAW_DIR, "*_raw.csv")) +
                       glob.glob(os.path.join(RAW_DIR, "openalex_block*.csv")) +
                       glob.glob(os.path.join(RAW_DIR, "scopus_block*.csv"))))
    sources = {}
    total = 0
    for fp in files:
        name = os.path.basename(fp)
        sig = file_sig(fp)
        rows = count_rows(fp)
        total += rows
        old = prev.get(name, {})
        # mantém a data original se o arquivo não mudou
        search_date = old.get("search_date", args.date) if old.get("sig") == sig else args.date
        sources[name] = {"records": rows, "search_date": search_date, "sig": sig}

    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "window": f"{YEAR_MIN}-{YEAR_MAX}",
        "note": args.note,
        "total_records_raw": total,
        "sources": sources,
    }
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"[OK] {MANIFEST}")
    print(f"  Janela: {YEAR_MIN}-{YEAR_MAX} | total bruto: {total:,}")
    for name, meta in sources.items():
        print(f"   - {name:32s} {meta['records']:>7,}  (busca: {meta['search_date']})")


if __name__ == "__main__":
    main()
