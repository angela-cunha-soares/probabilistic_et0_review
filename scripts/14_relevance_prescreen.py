"""
Pré-triagem de relevância para TODO o corpus (apoio à triagem PRISMA completa).

Motivação: a busca tem alta cobertura (recall), mas inclui artigos de clima/
hidrologia que apenas MENCIONAM evapotranspiração sem CALCULAR ET0 nem apresentar
uma ferramenta. Este escore transparente ordena e sugere uma decisão para cada
documento, para que a triagem manual do conjunto inteiro seja viável.

Calibrado contra as decisões manuais das 99 amostras (S/N):
  - inclusões manuais pontuaram 5–8; exclusões, majoritariamente <= 2.

NÃO substitui a leitura humana — apenas ORDENA e SUGERE. Decisões manuais já
tomadas são preservadas (bloqueadas).

Saída: data/processed/full_screening.csv (todos os documentos, ordenados)
"""

import os
import pandas as pd

from config import PROCESSED_DIR

CORPUS = os.path.join(PROCESSED_DIR, "corpus_classified.csv")
# Decisões manuais a preservar entre recoletas. Prefere o arquivo completo
# (decisions_manual.csv) se existir; senão usa o das 99 amostras.
_manual = os.path.join(PROCESSED_DIR, "decisions_manual.csv")
DECISIONS = _manual if os.path.exists(_manual) else os.path.join(
    PROCESSED_DIR, "decisions_99.csv")

# Sinais de ET0-específico / ferramenta (inclusão)
ET0_SPECIFIC = ["penman-monteith", "penman monteith", "fao-56", "fao 56", "fao56",
                "hargreaves", "priestley-taylor", "blaney-criddle", "thornthwaite",
                "makkink", "reference evapotranspiration", "reference et",
                "potential evapotranspiration", "crop coefficient",
                "crop water requirement", "et0", "eto ", "et₀"]
NAMED = ["cropwat", "aquacrop", "ref-et", "eto calculator", "pyfao56", "simdualkc",
         "pyeto", "sebal", "metric", "ssebop", "sebs", "openet", "dssat"]
TOOLWORDS = ["software", "platform", "web-based", "web application", "online tool",
             "decision support", "package", "toolbox", "calculator", " api ",
             "user interface", "google earth engine", "web service"]
COMPUTE = ["estimat", "comput", "calculat", "predict", "simulat", "forecast",
           "retriev", "mapping "]
ET = ["evapotranspiration", "et0", "eto ", "et₀"]
# Marcadores de processo/clima sem ferramenta (peso negativo fraco)
NEG = ["climate change", "streamflow", "runoff", "drought monitoring",
       "gross primary", "carbon flux", "land surface temperature",
       "teleconnection", "precipitation trend", "groundwater recharge", "sea level"]


def score_row(row):
    t = " ".join(str(row.get(c, "")) for c in ("title", "abstract", "keywords")).lower()
    s, why = 0, []
    if any(m in t for m in ET0_SPECIFIC):
        s += 3; why.append("ET0-specific term/method")
    if any(n in t for n in NAMED):
        s += 3; why.append("named ET tool")
    if any(w in t for w in TOOLWORDS):
        s += 2; why.append("software/tool term")
    if any(c in t for c in COMPUTE) and any(e in t for e in ET):
        s += 2; why.append("computes/estimates ET")
    if any(n in t for n in NEG) and s < 3:
        s -= 1; why.append("climate/hydrology-process marker")
    return pd.Series([s, "; ".join(why) or "no strong signal"])


def bucket(s):
    if s >= 5:
        return "1-LIKELY_INCLUDE"
    if s >= 3:
        return "2-REVIEW"
    return "3-LIKELY_EXCLUDE"


def main():
    df = pd.read_csv(CORPUS, dtype=str)
    df[["relevance", "relevance_reason"]] = df.apply(score_row, axis=1)
    df["relevance"] = df["relevance"].astype(int)
    df["suggestion"] = df["relevance"].map(bucket)
    df["Include_Title_Abstract"] = ""
    df["Exclusion_Reason"] = ""

    # aplica decisões manuais já tomadas — casando por id, DOI OU título
    # normalizado (robusto a mudanças de representante entre re-fusões).
    import re

    def _norm(t):
        return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", " ", str(t).lower()))

    n_locked = 0
    if os.path.exists(DECISIONS):
        dec = pd.read_csv(DECISIONS, dtype=str)
        inc = [c for c in dec.columns if "include" in c.lower()][0]
        dec["d"] = dec[inc].fillna("").str.upper().str.strip()
        dec = dec[dec["d"].isin(["S", "N"])]
        dec["doi_l"] = dec.get("doi", "").fillna("").str.lower().str.strip()
        dec["tk"] = dec.get("title", "").map(_norm)
        by_id = dict(zip(dec["id"], dec["d"]))
        by_doi = {k: v for k, v in zip(dec["doi_l"], dec["d"]) if k}
        by_tk = {k: v for k, v in zip(dec["tk"], dec["d"]) if len(k) > 15}
        df["doi_l"] = df["doi"].fillna("").str.lower().str.strip()
        df["tk"] = df["title"].map(_norm)

        def lookup(r):
            return (by_id.get(r["id"]) or by_doi.get(r["doi_l"])
                    or by_tk.get(r["tk"]) or "")
        df["Include_Title_Abstract"] = df.apply(lookup, axis=1)
        n_locked = int(df["Include_Title_Abstract"].isin(["S", "N"]).sum())
        df.drop(columns=["doi_l", "tk"], inplace=True)

    # exclusão automática por tipo de documento (identificado com segurança pelo
    # WoS): reviews, proceedings, book chapters, editoriais, etc. — passo PRISMA
    # documentado. Respeita decisões manuais já tomadas.
    NONART = {"Review", "Proceedings", "Book chapter", "Editorial",
              "Correction", "Letter", "Meeting abstract", "Note", "Retracted"}
    if "doc_type" in df.columns:
        na = df["doc_type"].isin(NONART) & (df["Include_Title_Abstract"] == "")
        df.loc[na, "Include_Title_Abstract"] = "N"
        df.loc[na, "Exclusion_Reason"] = "wrong doc type: " + df.loc[na, "doc_type"]
        df.loc[na, "suggestion"] = "3-LIKELY_EXCLUDE"
        print(f"[DocType] excluídos automaticamente (não-artigos WoS): {int(na.sum())}")

    # exclusão por ESCOPO de periódico (revistas médicas), com salvaguarda para
    # periódicos agrícolas/ambientais. Respeita decisões manuais.
    try:
        from config import MED_JOURNAL_TERMS, MED_SAFE_TERMS
        v = df["venue"].fillna("")
        medp = "|".join(re.escape(t) for t in MED_JOURNAL_TERMS)
        safep = "|".join(re.escape(t) for t in MED_SAFE_TERMS)
        med = (v.str.contains(medp, case=False, regex=True)
               & ~v.str.contains(safep, case=False, regex=True)
               & (df["Include_Title_Abstract"] == ""))
        df.loc[med, "Include_Title_Abstract"] = "N"
        df.loc[med, "Exclusion_Reason"] = "off-scope journal (medical)"
        df.loc[med, "suggestion"] = "3-LIKELY_EXCLUDE"
        print(f"[Journal] excluídos por revista médica/fora de escopo: {int(med.sum())}")
    except Exception as e:
        print("  [journal filter] pulado:", str(e)[:60])

    # exclusão de PREPRINTS / repositórios (não revisados por pares)
    try:
        from config import PREPRINT_VENUE_TERMS
        v = df["venue"].fillna("").str.lower()
        prep = (v.str.contains("|".join(re.escape(t) for t in PREPRINT_VENUE_TERMS),
                               regex=True) & (df["Include_Title_Abstract"] == ""))
        df.loc[prep, "Include_Title_Abstract"] = "N"
        df.loc[prep, "Exclusion_Reason"] = "preprint/repository (not peer-reviewed)"
        df.loc[prep, "suggestion"] = "3-LIKELY_EXCLUDE"
        print(f"[Preprint] excluídos (preprints/repositórios): {int(prep.sum())}")
    except Exception as e:
        print("  [preprint filter] pulado:", str(e)[:60])

    # exclusão por REVISTA marcada manualmente em journals_review.csv (coluna Exclude)
    jr = os.path.join(PROCESSED_DIR, "journals_review.csv")
    if os.path.exists(jr):
        jrev = pd.read_csv(jr, dtype=str)
        if "Exclude" in jrev.columns:
            def _vk(s):
                return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]", " ", str(s).lower())).strip()
            excl = {_vk(x) for x, m in zip(jrev["venue"], jrev["Exclude"].fillna(""))
                    if str(m).strip()}
            if excl:
                vk = df["venue"].map(_vk)
                m = vk.isin(excl) & (df["Include_Title_Abstract"] == "")
                df.loc[m, "Include_Title_Abstract"] = "N"
                df.loc[m, "Exclusion_Reason"] = "off-scope journal (manual list)"
                df.loc[m, "suggestion"] = "3-LIKELY_EXCLUDE"
                print(f"[JournalList] excluídos por revista marcada: {int(m.sum())}")

    order = {"1-LIKELY_INCLUDE": 0, "2-REVIEW": 1, "3-LIKELY_EXCLUDE": 2}
    df["_o"] = df["suggestion"].map(order)
    df = df.sort_values(["_o", "relevance"], ascending=[True, False]).drop(columns="_o")

    cols = ["suggestion", "relevance", "relevance_reason",
            "Include_Title_Abstract", "Exclusion_Reason",
            "id", "doi", "title", "abstract", "keywords", "venue", "year",
            "doc_type", "block", "tool_type", "method_class", "cited_by_count",
            "sources_found"]
    cols = [c for c in cols if c in df.columns]
    out = os.path.join(PROCESSED_DIR, "full_screening.csv")
    df[cols].to_csv(out, index=False, encoding="utf-8-sig")

    print(f"[OK] {out}  ({len(df):,} documentos; {n_locked} decisões manuais preservadas)")
    print("\nDistribuição das sugestões:")
    print(df["suggestion"].value_counts().sort_index().to_string())
    dec_done = df["Include_Title_Abstract"].isin(["S", "N"]).sum()
    print(f"\nJá decididos: {dec_done} | Faltam triar: {len(df)-dec_done}")


if __name__ == "__main__":
    main()
