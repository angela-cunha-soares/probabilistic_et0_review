"""
Validação do classificador por palavra-chave (tipo de ferramenta e paradigma).

Por que existe: os revisores da CEA vão questionar a classificação automática
(keyword matching). Este script mede a concordância entre o rótulo AUTOMÁTICO e
um rótulo de OURO feito à mão numa amostra aleatória, reportando **acurácia** e
**kappa de Cohen** — que você cita na seção de Métodos e nas Limitações.

Fluxo em dois passos
--------------------
1) Gerar a amostra de ouro (uma vez):
       python scripts/validate_classifier.py --make-sample 100
   Isso cria:
     results/tables/classifier_gold_TEMPLATE.csv   <- VOCÊ preenche à mão
     results/tables/classifier_gold_key.csv        <- rótulos automáticos (não abra
                                                       antes de rotular; evita viés)
   No TEMPLATE, leia título+resumo e preencha as colunas
   `gold_tool_type` e `gold_method_class`.

2) Pontuar a concordância (depois de preencher):
       python scripts/validate_classifier.py --score
   Gera results/tables/classifier_validation.md (+ .csv) com acurácia, kappa e
   a matriz de confusão por dimensão.

Sem dependências além de pandas (kappa implementado à mão).
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PROCESSED_DIR, TABLES_DIR

CORPUS = os.path.join(PROCESSED_DIR, "corpus_classified.csv")
TEMPLATE = os.path.join(TABLES_DIR, "classifier_gold_TEMPLATE.csv")
KEY = os.path.join(TABLES_DIR, "classifier_gold_key.csv")
OUT_MD = os.path.join(TABLES_DIR, "classifier_validation.md")
OUT_CSV = os.path.join(TABLES_DIR, "classifier_validation.csv")

DIMS = {"tool_type": "gold_tool_type", "method_class": "gold_method_class"}


def cohen_kappa(a, b):
    """Kappa de Cohen entre duas listas de rótulos (mesmo tamanho)."""
    pair = [(x, y) for x, y in zip(a, b)
            if str(x).strip() and str(y).strip()]
    n = len(pair)
    if n == 0:
        return float("nan"), 0
    labels = sorted({x for x, _ in pair} | {y for _, y in pair})
    po = sum(1 for x, y in pair if x == y) / n
    # concordância esperada por acaso
    pe = 0.0
    for lab in labels:
        pa = sum(1 for x, _ in pair if x == lab) / n
        pb = sum(1 for _, y in pair if y == lab) / n
        pe += pa * pb
    kappa = (po - pe) / (1 - pe) if pe != 1 else 1.0
    return kappa, n


def interpret(k):
    if k != k:  # nan
        return "sem dados"
    if k < 0:
        return "pior que o acaso"
    if k < 0.20:
        return "leve"
    if k < 0.40:
        return "razoável (fair)"
    if k < 0.60:
        return "moderada"
    if k < 0.80:
        return "substancial"
    return "quase perfeita"


def make_sample(n):
    df = pd.read_csv(CORPUS, dtype=str).fillna("")
    for col in ("tool_type", "method_class"):
        if col not in df.columns:
            raise SystemExit(f"Coluna '{col}' não existe em {CORPUS}. "
                             "Rode a classificação (05_...) antes.")
    # amostra estratificada por tool_type (garante cobrir todas as classes)
    n = min(n, len(df))
    frac = n / len(df)
    samp = df.groupby("tool_type", group_keys=False).sample(
        frac=frac, random_state=42)
    if len(samp) > n:
        samp = samp.sample(n, random_state=42)

    tmpl = samp[["id", "title", "abstract", "keywords"]].copy()
    tmpl["gold_tool_type"] = ""      # <- preencher à mão
    tmpl["gold_method_class"] = ""   # <- preencher à mão
    tmpl.to_csv(TEMPLATE, index=False, encoding="utf-8-sig")

    key = samp[["id", "tool_type", "method_class"]].copy()
    key.to_csv(KEY, index=False, encoding="utf-8-sig")

    print(f"[OK] amostra de {len(samp)} documentos.")
    print(f"  Preencha à mão: {TEMPLATE}")
    print("  Classes de tool_type sugeridas (use exatamente estes rótulos):")
    for name, _ in __import__("config").TOOL_TYPE_TAXONOMY:
        print("     -", name)
    print("     - Other/unspecified")
    print("  Classes de method_class: Deterministic | Non-deterministic | "
          "Hybrid | Unclassified")


def score():
    if not (os.path.exists(TEMPLATE) and os.path.exists(KEY)):
        raise SystemExit("Rode primeiro: --make-sample N (e preencha o TEMPLATE).")
    gold = pd.read_csv(TEMPLATE, dtype=str).fillna("")
    key = pd.read_csv(KEY, dtype=str).fillna("")
    m = key.merge(gold[["id", "gold_tool_type", "gold_method_class"]], on="id")

    lines = ["# Validação do classificador (auto × ouro)\n"]
    rows = []
    for auto_col, gold_col in DIMS.items():
        sub = m[(m[gold_col].str.strip() != "")]
        if len(sub) == 0:
            lines.append(f"## {auto_col}\n\n_(nenhum rótulo de ouro preenchido)_\n")
            continue
        acc = (sub[auto_col].str.strip().str.lower()
               == sub[gold_col].str.strip().str.lower()).mean()
        k, nn = cohen_kappa(sub[auto_col].str.strip().str.lower().tolist(),
                            sub[gold_col].str.strip().str.lower().tolist())
        rows.append({"dimension": auto_col, "n": nn,
                     "accuracy": round(acc, 3), "cohen_kappa": round(k, 3),
                     "agreement": interpret(k)})
        lines.append(f"## {auto_col}\n")
        lines.append(f"- Amostra avaliada: **{nn}**")
        lines.append(f"- Acurácia (concordância bruta): **{acc:.1%}**")
        lines.append(f"- Kappa de Cohen: **{k:.3f}** ({interpret(k)})\n")
        # matriz de confusão compacta
        conf = pd.crosstab(sub[gold_col], sub[auto_col])
        lines.append("Matriz de confusão (linhas = ouro, colunas = automático):\n")
        lines.append("```\n" + conf.to_string() + "\n```\n")

    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines))
    print(f"[OK] {OUT_MD}")
    print(f"     {OUT_CSV}")
    for r in rows:
        print(f"   - {r['dimension']:14s} n={r['n']:>4}  acc={r['accuracy']:.1%}  "
              f"kappa={r['cohen_kappa']:.3f} ({r['agreement']})")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--make-sample", type=int, metavar="N",
                   help="cria a amostra de ouro com N documentos")
    g.add_argument("--score", action="store_true",
                   help="pontua a concordância (após preencher o TEMPLATE)")
    args = ap.parse_args()
    if args.make_sample:
        make_sample(args.make_sample)
    else:
        score()


if __name__ == "__main__":
    main()
