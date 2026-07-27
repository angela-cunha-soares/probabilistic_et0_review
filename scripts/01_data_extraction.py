import pandas as pd
import os
from pybliometrics.scopus import ScopusSearch
import time
from datetime import datetime

# ===================== CONFIGURAÇÕES =====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
os.makedirs(RAW_DATA_DIR, exist_ok=True)

# Configurações de busca
YEARS = "PUBYEAR > 1999"  # 2000 até hoje


def run_tier_1():
    """Tier 1: Comparação macro de volume (Determinístico vs Estocástico/Bayesian)"""
    print("\n" + "="*60)
    print("TIER 1: MACRO-BIBLIOMETRIC CONTRAST (VOLUME ONLY)")
    print("="*60)
    
    query_det = f'TITLE-ABS-KEY(("irrigation scheduling" OR "water balance" OR "soil water balance") AND ("FAO-56" OR "Penman-Monteith" OR "AquaCrop" OR "CropWat")) AND {YEARS}'
    
    query_stoc = f'TITLE-ABS-KEY(("irrigation scheduling" OR "water balance" OR "soil water balance") AND ("Bayesian" OR "stochastic" OR "MCMC" OR "probabilistic" OR "uncertainty quantification")) AND {YEARS}'
    
    try:
        search_det = ScopusSearch(query_det, download=False, subscriber=True)
        search_stoc = ScopusSearch(query_stoc, download=False, subscriber=True)
        
        print(f"→ Deterministic approaches (FAO-56, AquaCrop, etc.): {search_det.get_results_size():,} artigos")
        print(f"→ Stochastic/Bayesian approaches: {search_stoc.get_results_size():,} artigos")
        print(f"→ Razão Bayesian vs Determinístico: {search_stoc.get_results_size()/max(search_det.get_results_size(),1):.2f}x")
        
    except Exception as e:
        print(f"Erro no Tier 1: {e}")


def run_tier_2_unified():
    """Tier 2: Busca unificada para PRISMA + Bibliometria"""
    print("\n" + "="*60)
    print("TIER 2: SYSTEMATIC REVIEW + BIBLIOMETRIC ANALYSIS")
    print("="*60)
    
    queries = {
        "Software_DataFusion": '''
            TITLE-ABS-KEY(
                ("evapotranspiration" OR "ET0" OR "ET_0" OR "reference evapotranspiration") 
                AND ("Bayesian" OR "stochastic" OR "probabilistic" OR "uncertainty quantification" 
                     OR "Kalman filter" OR "data fusion" OR "multi-source" OR "data assimilation")
                AND ("model*" OR "software" OR "platform" OR "decision support" OR "tool")
            )
        ''',
        
        "Irrigation_Decision": '''
            TITLE-ABS-KEY(
                ("irrigation scheduling" OR "irrigation depth" OR "lâmina de irrigação" OR 
                 "balanço hídrico" OR "soil moisture" OR "root zone depletion")
                AND ("Bayesian" OR "MCMC" OR "stochastic" OR "probabilistic" OR "posterior")
                AND ("ENSO" OR "teleconnection" OR "climate risk" OR "risk-aware" OR "decision support")
            )
        ''',
        
        "Reviews_Bibliometrics": '''
            TITLE-ABS-KEY(
                ("evapotranspiration" OR "irrigation scheduling" OR "hydrology" OR "water resources")
                AND ("Bayesian" OR "stochastic" OR "probabilistic")
                AND ("systematic review" OR "bibliometric" OR "meta-analysis" OR "scoping review")
            )
        '''
    }
    
    all_dfs = []
    
    for name, query in queries.items():
        print(f"\n🔍 Buscando: {name}...")
        try:
            search = ScopusSearch(query.strip() + f" AND {YEARS}", 
                                subscriber=True, 
                                verbose=True)
            
            if search.results:
                df = pd.DataFrame(search.results)
                print(f"   ✓ Encontrados: {len(df):,} artigos")
                df['search_tier'] = name
                all_dfs.append(df)
            else:
                print(f"   ⚠️ Nenhum resultado encontrado.")
                
            time.sleep(1)  # Evitar rate limit
            
        except Exception as e:
            print(f"   ❌ Erro na busca {name}: {e}")
    
    # ===================== UNIFICAÇÃO =====================
    if all_dfs:
        df_unified = pd.concat(all_dfs, ignore_index=True)
        
        initial = len(df_unified)
        df_unified.drop_duplicates(subset=['eid'], inplace=True)
        final = len(df_unified)
        
        print("\n" + "="*50)
        print("RESULTADO FINAL")
        print("="*50)
        print(f"Total bruto: {initial:,} registros")
        print(f"Após remoção de duplicatas: {final:,} artigos únicos")
        
        # Colunas mais úteis
        cols_to_keep = ['eid', 'doi', 'title', 'creator', 'author_names', 
                       'publicationName', 'coverDate', 'description', 
                       'authkeywords', 'citedby_count', 'affilname', 'affiliation_city',
                       'search_tier']
        
        existing_cols = [c for c in cols_to_keep if c in df_unified.columns]
        df_clean = df_unified[existing_cols].copy()
        
        # Formatação de data
        df_clean['coverDate'] = pd.to_datetime(df_clean['coverDate'], errors='coerce')
        df_clean['year'] = df_clean['coverDate'].dt.year
        
        # Salvar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = os.path.join(RAW_DATA_DIR, f'tier2_prisma_unified_{timestamp}.csv')
        df_clean.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"\n✅ Arquivo salvo com sucesso em:")
        print(f"   {output_path}")
        print(f"   Total de artigos únicos: {final:,}")
        
        # Salvar também versão Excel (facilita análise)
        excel_path = os.path.join(RAW_DATA_DIR, f'tier2_prisma_unified_{timestamp}.xlsx')
        df_clean.to_excel(excel_path, index=False)
        print(f"   Excel salvo em: {excel_path}")
        
    else:
        print("\n❌ Nenhuma busca retornou resultados.")


if __name__ == "__main__":
    print("🚀 Iniciando Análise Bibliométrica Scopus - EVAonline Project")
    print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    run_tier_1()
    run_tier_2_unified()
    
    print("\n🎉 Processo finalizado!")