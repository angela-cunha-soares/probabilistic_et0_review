import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
PROCESSED_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')

def prepare_prisma_screening():
    input_file = os.path.join(RAW_DATA_DIR, 'tier2_prisma_unified.csv')
    output_file = os.path.join(PROCESSED_DATA_DIR, 'screening_sheet.csv')
    
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    print("Iniciando a preparação da planilha de Screening (PRISMA)...")
    
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print(f"Erro: Arquivo {input_file} não encontrado.")
        return

    df['Include_Title_Abstract'] = "" 
    df['Exclusion_Reason'] = ""       
    
    cols_order = ['eid', 'Include_Title_Abstract', 'Exclusion_Reason', 'title', 
                  'description', 'authkeywords', 'publicationName', 'coverDate', 'doi']
    
    cols_order = [c for c in cols_order if c in df.columns]
    df_screening = df[cols_order]
    
    df_screening.to_csv(output_file, index=False, encoding='utf-8')
    print(f"[SUCESSO] Planilha de triagem criada com {len(df_screening)} artigos.")
    print(f"-> Salvo em: {output_file}")

if __name__ == "__main__":
    prepare_prisma_screening()