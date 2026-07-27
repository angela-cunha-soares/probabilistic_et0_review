# Revisão sistemática de software e ferramentas para evapotranspiração de referência (ET₀)

Pipeline **100% Python** (sem R) para uma revisão bibliométrica sistemática, guiada
por PRISMA, do software, aplicativos e ferramentas online que **calculam ET₀**, e de
**como** eles produzem estimativas — de forma **determinística** ou **não-determinística**.
Revista-alvo: *Environmental Modelling & Software* (Elsevier). Tipo: **Review paper**.

Este README ensina, do zero, como instalar, configurar e rodar o projeto.

---

## 1. O que o projeto faz

Em quatro etapas:

1. **Coleta** referências em várias bases (OpenAlex, Scopus e, opcionalmente, Web of
   Science via exportação), usando duas frentes de busca (Bloco A = ferramentas de ET₀;
   Bloco B = irrigação/decisão sob incerteza).
2. **Funde e deduplica** tudo num corpus único, seguindo o fluxo PRISMA.
3. **Analisa** o corpus (produção por ano, países, instituições, periódicos, Open
   Access, palavras-chave, redes de coautoria, evolução temática) e **classifica** cada
   documento por **tipo de ferramenta** e por **paradigma de método** (determinístico
   vs não-determinístico).
4. **Gera** tabelas e figuras de alta resolução e dá apoio à **triagem manual** (PRISMA).

---

## 2. Estrutura de pastas

```
probabilistic_et0_review/
├── README.md                  ← este arquivo
├── requirements.txt           ← dependências Python
├── SEARCH_TERMS.md            ← todas as palavras-chave e conectivos
├── WOS_EXPORT_GUIDE.md        ← como exportar da Web of Science
├── MANUSCRIPT_DRAFT.md        ← rascunho do artigo (Introdução, Métodos, Apêndice)
├── MANUSCRIPT_OUTLINE.md      ← estrutura + inventário de figuras
├── EDITOR_PITCH.md            ← e-mail de pré-submissão ao editor
├── data/
│   ├── raw/                   ← dados brutos por base (openalex_*, scopus_*, wos_*)
│   │   └── wos_export/        ← coloque aqui os arquivos exportados da WoS
│   └── processed/             ← corpus unificado, classificado e planilhas de triagem
├── results/
│   ├── tables/                ← todas as tabelas .csv
│   └── figures/               ← todas as figuras .png (+ .html interativas)
└── scripts/                   ← o código (ver seção 6)
```

---

## 3. Pré-requisitos

- **Python 3.10+**
- Uma **chave de API do Scopus** (Elsevier), usada de rede/IP institucional. Opcional,
  mas recomendada para triangular as bases. O OpenAlex funciona sem chave.
- (Opcional) Acesso à **Web of Science** para exportar registros (ver seção 7).

---

## 4. Instalação

```bash
# 1. Clone o repositório e entre na pasta
git clone <url-do-repo>
cd probabilistic_et0_review

# 2. (recomendado) crie um ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

---

## 5. Configuração (variáveis de ambiente)

As chaves **nunca** ficam no código — são lidas de variáveis de ambiente.

```bash
# Windows (PowerShell)
setx CONTACT_EMAIL "voce@exemplo.com"      # OpenAlex/Crossref pedem um e-mail de contato
setx SCOPUS_API_KEY "sua_chave_elsevier"   # opcional (Scopus)

# Linux/Mac
export CONTACT_EMAIL="voce@exemplo.com"
export SCOPUS_API_KEY="sua_chave_elsevier"
```

Todas as opções de busca ficam em **`scripts/config.py`**: janela temporal, listas de
palavras-chave, blocos de busca e vocabulários de classificação.

---

## 6. Como rodar

### 6.1 Tudo de uma vez (recomendado)

```bash
python scripts/run_pipeline.py
```

Esse orquestrador limpa os dados antigos, recoleta e regenera **todas** as tabelas e
figuras. Variantes:

```bash
python scripts/run_pipeline.py --no-collect   # não recoleta; só reprocessa e refaz figuras
python scripts/run_pipeline.py --no-reset      # mantém os dados e adiciona/atualiza
```

### 6.2 Quando usar cada modo — a regra de ouro

Depende de **onde** você mexeu no `config.py`:

| Você alterou… | O que muda | Comando |
|---|---|---|
| `CORE_ET0`, `TOOL_TYPES`, `NAMED_TOOLS`, `CORE_IRRIGATION`, `METHOD_PROB`, `TELECONNECTION` | a **busca** (traz outros artigos) | `python scripts/run_pipeline.py` (recoleta) |
| `DET_METHODS`, `NONDET_METHODS`, `TOOL_TYPE_TAXONOMY` | só a **classificação** | `python scripts/run_pipeline.py --no-collect` |

> ⚠️ Recoletar regenera o `full_screening.csv` — ou seja, **a triagem manual em
> andamento seria perdida**. Defina as palavras-chave de busca **antes** de triar.

### 6.3 Ordem manual (o que o orquestrador executa)

Se preferir rodar passo a passo:

```bash
python scripts/00_collect_openalex.py     # 1. coleta OpenAlex (grátis)
python scripts/01_collect_scopus.py       # 2. coleta Scopus (precisa da chave)
python scripts/11_ingest_wos_export.py    # 3. ingere export da WoS (se houver)
python scripts/04_merge_dedup_prisma.py   # 4. funde + deduplica + PRISMA
python scripts/05_bibliometric_analysis.py# 5. tabelas (países, instituições, OA, método, tipo)
python scripts/12_journal_metrics.py      # 6. métricas de periódico (impacto)
python scripts/06_generate_figures.py     # 7. figuras básicas + método/tipo
python scripts/07_advanced_figures.py     # 8. mapas, redes, nuvem, Sankey, mapa estratégico
python scripts/13_metadata_figures.py     # 9. instituições, Open Access, impacto
python scripts/08_prisma_diagram.py       # 10. fluxograma PRISMA
python scripts/09_top_cited_by_category.py# 11. mais citados por categoria (síntese)
python scripts/10_screening_prefilter.py  # 12. pré-filtro dos casos duvidosos
python scripts/14_relevance_prescreen.py  # 13. pré-triagem do corpus inteiro
```

---

## 7. Web of Science (por exportação, sem API)

A API Expanded exige entitlement institucional que nem sempre está disponível. A
alternativa padrão é exportar da plataforma web (ver **`WOS_EXPORT_GUIDE.md`**):

1. Rode as queries dos Blocos A e B (estão no guia) na Web of Science.
2. **Export → Tab delimited** (ou RIS/BibTeX), registro **"Full Record"** (até 1.000 por vez).
3. Salve os arquivos em `data/raw/wos_export/`.
4. Rode `python scripts/11_ingest_wos_export.py` e depois o merge.

---

## 8. Fluxo de triagem (PRISMA)

Depois da coleta, a triagem por título/resumo é **manual**, mas assistida:

1. Abra **`data/processed/full_screening.csv`** (já ordenado por relevância, com
   sugestões `LIKELY_INCLUDE` / `REVIEW` / `LIKELY_EXCLUDE`).
2. Preencha a coluna **`Include_Title_Abstract`** com **S** (incluir) ou **N** (excluir).
   Opcionalmente, preencha **`Exclusion_Reason`** nos N com um código curto padronizado.
3. Rode **`python scripts/15_apply_screening.py`** para gerar o conjunto final incluído
   (`corpus_included.csv`) e atualizar o PRISMA.
4. Regenere tabelas/figuras sobre o conjunto incluído.

---

## 9. Principais saídas

**Tabelas** (`results/tables/`): `publications_per_year`, `top_countries`,
`top_institutions`, `top_journals`, `top_journals_by_impact`, `journal_metrics`,
`top_keywords`, `method_classification`, `method_by_year`, `tool_type_distribution`,
`oa_summary`, `oa_by_tool_type`, `gap_oceanic_indices`, `prisma_counts`,
`source_overlap`, `top_cited_*`, `STATE_OF_THE_ART_SEED.md`.

**Figuras** (`results/figures/`): fig1 produção anual · fig2 palavras-chave · fig3
países · fig4 gap de teleconexões · fig5/6 mapas de documentos/citações · fig7
colaboração entre países · fig8 rede de autores (+html) · fig9 nuvem · fig10 treemap
· fig11 evolução temática (Sankey, +html) · fig12 mapa estratégico · fig13 método
(rosca) · fig14 método ao longo do tempo · fig15 tipos de ferramenta · fig16
instituições · fig17 Open Access · fig18 periódicos por impacto · fig_prisma_flow.

---

## 10. Solução de problemas

- **`SCOPUS_API_KEY não definida`** → defina a variável de ambiente (seção 5). Sem ela,
  o pipeline segue só com OpenAlex.
- **Scopus 401/429** → limite de taxa ou IP fora da rede institucional; use a VPN da
  universidade e tente de novo (o coletor já tenta novamente automaticamente).
- **Nada em `data/raw/wos_export/`** → o passo da WoS é pulado; normal se você ainda
  não exportou.
- **Figuras não mudaram** → rode com `--no-collect` para reprocessar, ou verifique se as
  tabelas foram regeradas antes das figuras.

---
