import pandas as pd
import os
from pybliometrics.scopus import ScopusSearch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
os.makedirs(RAW_DATA_DIR, exist_ok=True)

def run_tier_1():
    print("\n" + "="*50)
    print("TIER 1: MACRO-BIBLIOMETRIC CONTRAST (VOLUME ONLY)")
    print("="*50)
    
    query_det = 'TITLE-ABS-KEY(("irrigation scheduling" OR "water balance") AND ("FAO-56" OR "Penman-Monteith" OR "AquaCrop"))'
    search_det = ScopusSearch(query_det, download=False, subscriber=True)
    print(f"-> Total Deterministic Articles (FAO-56/Penman): {search_det.get_results_size()}")
    
    query_stoc = 'TITLE-ABS-KEY(("irrigation scheduling" OR "water balance") AND ("Bayesian" OR "stochastic forecast*" OR "MCMC"))'
    search_stoc = ScopusSearch(query_stoc, download=False, subscriber=True)
    print(f"-> Total Stochastic/Bayesian Articles: {search_stoc.get_results_size()}")

def run_tier_2_unified():
    print("\n" + "="*50)
    print("TIER 2: SYSTEMATIC REVIEW (PRISMA GAP ANALYSIS)")
    print("="*50)
    
    query_software = '''TITLE-ABS-KEY(
        ("evapotranspiration" OR "reference evapotranspiration" OR "ET0") 
        AND ("Bayesian" OR "stochastic" OR "probabilistic" OR "uncertainty quantification" OR "Kalman filter" OR "data fusion" OR "multi-source") 
        AND ("model*" OR "predict*" OR "software" OR "platform" OR "decision support")
    )'''

    query_decision = '''TITLE-ABS-KEY(
        ("irrigation scheduling" OR "water balance" OR "soil moisture" OR "crop water requirement")
        AND ("Bayesian" OR "stochastic" OR "probabilistic forecast*" OR "MCMC" OR "posterior predictive")
        AND ("teleconnection*" OR "ENSO" OR "climatological prior*" OR "climate uncertaint*" OR "risk-aware" OR "decision support")
    )'''

    query_reviews = '''TITLE-ABS-KEY(
        ("water resource*" OR "hydrolog*" OR "evapotranspiration" OR "irrigation") 
        AND ("Bayesian" OR "probabilistic" OR "stochastic") 
        AND ("systematic review" OR "bibliometric" OR "meta-analysis" OR "state of the art")
    )'''
    
    print("Buscando String 1 (Software Gap)...")
    search_software = ScopusSearch(query_software, subscriber=True)
    df_software = pd.DataFrame(search_software.results) if search_software.results else pd.DataFrame()

    print("Buscando String 2 (Decision/Climate Gap)...")
    search_decision = ScopusSearch(query_decision, subscriber=True)
    df_decision = pd.DataFrame(search_decision.results) if search_decision.results else pd.DataFrame()

    print("Buscando String 3 (Systematic Reviews & Bibliometrics)...")
    search_reviews = ScopusSearch(query_reviews, subscriber=True)
    df_reviews = pd.DataFrame(search_reviews.results) if search_reviews.results else pd.DataFrame()

    print("\nUnificando bases e removendo duplicatas...")
    df_unified = pd.concat([df_software, df_decision, df_reviews], ignore_index=True)
    
    if not df_unified.empty:
        initial_count = len(df_unified)
        df_unified.drop_duplicates(subset=['eid'], inplace=True)
        final_count = len(df_unified)
        print(f"-> Duplicatas removidas: {initial_count - final_count}")
        print(f"-> TOTAL DE ARTIGOS ÚNICOS PARA O PRISMA: {final_count}")
        
        # CORREÇÃO AQUI: 'affilname' no lugar de 'affiliation'
        cols_to_keep = ['eid', 'doi', 'title', 'creator', 'publicationName', 
                        'coverDate', 'description', 'authkeywords', 'citedby_count', 'affilname']
        existing_cols = [c for c in cols_to_keep if c in df_unified.columns]
        df_clean = df_unified[existing_cols]
        
        output_path = os.path.join(RAW_DATA_DIR, 'tier2_prisma_unified.csv')
        df_clean.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[SUCESSO] Base de dados rica salva em: {output_path}")
    else:
        print("\n[AVISO] Nenhum artigo foi encontrado nas buscas do Tier 2.")

if __name__ == "__main__":
    run_tier_1()
    run_tier_2_unified()