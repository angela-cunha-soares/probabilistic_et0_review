import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TABLES_DIR = os.path.join(PROJECT_ROOT, 'results', 'tables')
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'results', 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)

# Estilo mais limpo, sem a grade pesada de fundo
sns.set_theme(style="ticks")
plt.rcParams.update({'font.size': 12, 'font.family': 'sans-serif'})

def plot_macro_gap_donut():
    # --- LEMBRE-SE DE COLOCAR SEUS NÚMEROS AQUI ---
    deterministic_count = 18500  
    bayesian_count = 1679        
    
    labels = ['Deterministic Frameworks\n(e.g., FAO-56)', 'Probabilistic/Bayesian']
    sizes = [deterministic_count, bayesian_count]
    colors = ['#1f77b4', '#d62728']
    
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                      startangle=90, colors=colors, pctdistance=0.85, 
                                      wedgeprops=dict(width=0.4, edgecolor='w', linewidth=2),
                                      textprops={'fontsize': 12, 'fontweight': 'bold'})
    for autotext in autotexts: autotext.set_color('white')
    plt.title('Macro-Bibliometric Contrast', fontweight='bold', fontsize=14, pad=20)
    plt.savefig(os.path.join(FIGURES_DIR, 'fig0_macro_gap_donut.png'), dpi=300, bbox_inches='tight')
    plt.close()

def plot_publications_trend():
    file_path = os.path.join(TABLES_DIR, 'publications_per_year.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df = df[pd.to_numeric(df['Year'], errors='coerce').notnull()]
        df['Year'] = df['Year'].astype(int)
        df = df[(df['Year'] >= 2000) & (df['Year'] <= 2026)]

        plt.figure(figsize=(10, 6))
        sns.lineplot(data=df, x='Year', y='Publications', marker='o', color='#008CBA', linewidth=2.5)
        plt.title('Annual Scientific Production', fontweight='bold')
        plt.xlabel('Year')
        plt.ylabel('Documents')
        plt.xticks(rotation=45)
        sns.despine() # Remove as bordas superiores e direitas
        plt.tight_layout()
        plt.savefig(os.path.join(FIGURES_DIR, 'fig1_publications_trend.png'), dpi=300, bbox_inches='tight')
        plt.close()

def plot_top_keywords():
    file_path = os.path.join(TABLES_DIR, 'top_keywords.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if not df.empty:
            plt.figure(figsize=(10, 6))
            # Usando uma cor sólida igual ao do Vitor e controlando a largura da barra (width=0.6)
            sns.barplot(data=df, x='Frequency', y='Keyword', color='#008CBA', width=0.6)
            plt.title('Most Frequent Author Keywords', fontweight='bold', pad=15)
            plt.xlabel('Frequency')
            plt.ylabel('')
            sns.despine()
            plt.tight_layout()
            plt.savefig(os.path.join(FIGURES_DIR, 'fig2_top_keywords.png'), dpi=300, bbox_inches='tight')
            plt.close()

def plot_top_countries():
    file_path = os.path.join(TABLES_DIR, 'top_countries.csv')
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if not df.empty:
            plt.figure(figsize=(10, 6))
            # Gráfico de barras idêntico ao do Vitor
            sns.barplot(data=df, x='Publications', y='Country', color='#008CBA', width=0.6)
            plt.title('Distribution by country/territory', fontweight='bold', pad=15)
            plt.xlabel('Documents')
            plt.ylabel('')
            sns.despine()
            plt.tight_layout()
            plt.savefig(os.path.join(FIGURES_DIR, 'fig3_top_countries.png'), dpi=300, bbox_inches='tight')
            plt.close()

if __name__ == "__main__":
    print("Gerando figuras de alta resolução...")
    plot_macro_gap_donut()
    plot_publications_trend()
    plot_top_keywords()
    plot_top_countries()
    print("Concluído! Verifique a pasta results/figures.")