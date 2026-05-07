import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
INPUT_FILE = os.path.join(PROJECT_ROOT, 'data', 'raw', 'tier2_prisma_unified.csv')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'tables')
os.makedirs(RESULTS_DIR, exist_ok=True)

def mine_teleconnections(df):
    indices_dict = {
        'ONI / ENSO (Geral)': r'\b(?:oni|enso|el ni[ñn]o|la ni[ñn]a)\b',
        'MEI (Multivariate ENSO)': r'\b(?:mei|multivariate enso)\b',
        'AMM (Atlantic Meridional Mode)': r'\b(?:amm|atlantic meridional mode)\b',
        'AMO (Atlantic Multidecadal)': r'\b(?:amo|atlantic multidecadal)\b',
        'PDO (Pacific Decadal)': r'\b(?:pdo|pacific decadal)\b',
        'MJO (Madden-Julian)': r'\b(?:mjo|madden-julian)\b',
        'IOD / DMI (Indian Ocean)': r'\b(?:iod|dmi|indian ocean dipole)\b',
        'Teleconnections (Termo Geral)': r'\b(?:teleconnection|teleconnections)\b',
        'Climatological Priors': r'\b(?:climatological prior|climate prior)\b'
    }
    text_corpus = (df['title'].fillna('') + " " + df.get('description', pd.Series(dtype=str)).fillna('')).str.lower()
    results = [{'Oceanic_Index': k, 'Articles_Mentioning': text_corpus.str.contains(v, regex=True).sum()} for k, v in indices_dict.items()]
    df_indices = pd.DataFrame(results)
    df_indices['Percentage (%)'] = (df_indices['Articles_Mentioning'] / len(df) * 100).round(2)
    df_indices.to_csv(os.path.join(RESULTS_DIR, 'gap_oceanic_indices.csv'), index=False)

def extract_countries(df):
    # CORREÇÃO AQUI: Lendo a coluna correta affilname
    if 'affilname' not in df.columns: return
    affiliations = df['affilname'].dropna().astype(str).str.split(';')
    countries = []
    for affil_list in affiliations:
        for affil in affil_list:
            partes = affil.split(',')
            if len(partes) > 0:
                pais = partes[-1].strip()
                if pais in ['USA', 'United States of America']: pais = 'United States'
                if pais in ['UK', 'United Kingdom of Great Britain']: pais = 'United Kingdom'
                if pais in ['PR China']: pais = 'China'
                
                if not any(char.isdigit() for char in pais) and len(pais) > 2:
                    countries.append(pais)
                    
    df_countries = pd.Series(countries).value_counts().head(10).reset_index()
    df_countries.columns = ['Country', 'Publications']
    df_countries.to_csv(os.path.join(RESULTS_DIR, 'top_countries.csv'), index=False)

def run_basic_analysis():
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        return

    if 'coverDate' in df.columns:
        df['Year'] = df['coverDate'].astype(str).str[:4]
        pubs_per_year = df['Year'].value_counts().sort_index().reset_index()
        pubs_per_year.columns = ['Year', 'Publications']
        pubs_per_year.to_csv(os.path.join(RESULTS_DIR, 'publications_per_year.csv'), index=False)

    if 'publicationName' in df.columns:
        top_journals = df['publicationName'].value_counts().head(10).reset_index()
        top_journals.columns = ['Journal', 'Publications']
        top_journals.to_csv(os.path.join(RESULTS_DIR, 'top_journals.csv'), index=False)

    if 'authkeywords' in df.columns:
        raw_keywords = df['authkeywords'].dropna().astype(str)
        clean_keys = raw_keywords.str.replace(r'[|;,]', ';', regex=True)
        all_keywords = clean_keys.str.split(';').explode().str.lower().str.strip()
        all_keywords = all_keywords[(all_keywords != '') & (all_keywords != '|') & (all_keywords.str.len() > 2)]
        top_keywords = all_keywords.value_counts().head(15).reset_index()
        top_keywords.columns = ['Keyword', 'Frequency']
        top_keywords.to_csv(os.path.join(RESULTS_DIR, 'top_keywords.csv'), index=False)

    mine_teleconnections(df)
    extract_countries(df)
    print("Script 03: Tabelas geradas com sucesso!")

if __name__ == "__main__":
    run_basic_analysis()