"""
Figuras bibliométricas ricas (estilo do artigo-modelo) sobre o corpus ET0.

Gera em results/figures/:
  fig5_map_documents.png        Mapa mundi: nº de documentos por país
  fig6_map_citations.png        Mapa mundi: nº de citações por país
  fig7_country_collaboration.png Mapa de colaboração (coautoria entre países)
  fig8_author_network.png       Rede de coautoria entre autores (clusters)
  fig8_author_network.html      versão interativa (pyvis)
  fig9_keyword_wordcloud.png    Nuvem de palavras-chave
  fig10_keyword_treemap.png     Treemap de palavras-chave
  fig11_thematic_evolution.png  Evolução temática (Sankey) [+ .html]
  fig12_strategic_map.png       Mapa estratégico (motor/niche/basic/emerging)

Cada figura é isolada em try/except: uma falha não interrompe as demais.
"""

import os
import re
import itertools
from collections import Counter, defaultdict

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import PROCESSED_DIR, FIGURES_DIR, RAW_DIR

CORPUS = os.path.join(PROCESSED_DIR, "corpus_unified.csv")
WORLD_GEOJSON = os.path.join(RAW_DIR, "world.geojson")
WORLD_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
             "master/geojson/ne_110m_admin_0_countries.geojson")
ACCENT = "#008CBA"

KW_STOP = {
    "environmental science", "geography", "geology", "meteorology",
    "mathematics", "computer science", "physics", "biology", "engineering",
    "materials science", "chemistry", "economics", "cartography",
    "atmospheric sciences", "hydrology", "soil science", "geodesy",
    "statistics", "geomorphology", "oceanography", "ecology",
    "environmental resource management", "physical geography", "geotechnical engineering",
}


def load():
    df = pd.read_csv(CORPUS)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    return df


def _ensure_world():
    if not os.path.exists(WORLD_GEOJSON):
        import urllib.request
        print("  baixando mapa-base natural earth...")
        urllib.request.urlretrieve(WORLD_URL, WORLD_GEOJSON)
    import geopandas as gpd
    return gpd.read_file(WORLD_GEOJSON)


# ----------------------------------------------------------------------
def _country_counts(df, weight_col=None):
    counts = Counter()
    for _, row in df.iterrows():
        codes = [c.strip() for c in str(row["country_codes"]).split(";") if c.strip()]
        codes = set(codes)  # conta uma vez por documento
        w = 1 if weight_col is None else (row.get(weight_col) or 0)
        for c in codes:
            counts[c] += w
    return counts


def _choropleth(df, weight_col, title, out, cmap):
    world = _ensure_world()
    counts = _country_counts(df, weight_col)
    iso_col = "ISO_A2_EH" if "ISO_A2_EH" in world.columns else "ISO_A2"
    world["value"] = world[iso_col].map(lambda c: counts.get(c, 0))
    fig, ax = plt.subplots(figsize=(14, 7))
    world.plot(ax=ax, color="#e8e8e8", edgecolor="white", linewidth=0.4)
    world[world["value"] > 0].plot(ax=ax, column="value", cmap=cmap,
                                   edgecolor="white", linewidth=0.4,
                                   legend=True,
                                   legend_kwds={"shrink": 0.5, "label": title})
    ax.set_title(title, fontweight="bold", fontsize=15)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()


def fig_map_documents(df):
    _choropleth(df, None, "Documents per country",
                os.path.join(FIGURES_DIR, "fig5_map_documents.png"), "Blues")


def fig_map_citations(df):
    _choropleth(df, "cited_by_count", "Citations per country",
                os.path.join(FIGURES_DIR, "fig6_map_citations.png"), "OrRd")


# ----------------------------------------------------------------------
def fig_country_collaboration(df):
    world = _ensure_world()
    iso_col = "ISO_A2_EH" if "ISO_A2_EH" in world.columns else "ISO_A2"
    # centroides
    cent = world.copy()
    cent["cx"] = cent.geometry.centroid.x
    cent["cy"] = cent.geometry.centroid.y
    coord = {r[iso_col]: (r["cx"], r["cy"]) for _, r in cent.iterrows()}

    edges = Counter()
    node_w = Counter()
    for _, row in df.iterrows():
        codes = sorted({c.strip() for c in str(row["country_codes"]).split(";")
                        if c.strip()})
        for c in codes:
            node_w[c] += 1
        for a, b in itertools.combinations(codes, 2):
            edges[(a, b)] += 1

    fig, ax = plt.subplots(figsize=(14, 7))
    world.plot(ax=ax, color="#eef2f5", edgecolor="white", linewidth=0.4)
    # arcos
    maxw = max(edges.values()) if edges else 1
    for (a, b), w in edges.items():
        if a in coord and b in coord:
            x1, y1 = coord[a]; x2, y2 = coord[b]
            ax.plot([x1, x2], [y1, y2], color="#d1495b",
                    alpha=min(0.15 + 0.6 * w / maxw, 0.85),
                    linewidth=0.3 + 3.5 * w / maxw, solid_capstyle="round", zorder=2)
    # nós
    maxn = max(node_w.values()) if node_w else 1
    for c, w in node_w.items():
        if c in coord:
            x, y = coord[c]
            ax.scatter(x, y, s=20 + 400 * w / maxn, color=ACCENT,
                       edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_title("International collaboration (co-authorship between countries)",
                 fontweight="bold", fontsize=15)
    ax.axis("off"); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig7_country_collaboration.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


# ----------------------------------------------------------------------
def fig_author_network(df, top_n=60, min_edge=1):
    import networkx as nx
    try:
        import community as community_louvain
    except Exception:
        community_louvain = None

    counts = Counter()
    papers = []
    for _, row in df.iterrows():
        auth = [a.strip() for a in str(row["authors"]).split(";") if a.strip()]
        papers.append(auth)
        for a in auth:
            counts[a] += 1
    top = {a for a, _ in counts.most_common(top_n)}

    G = nx.Graph()
    for a in top:
        G.add_node(a, weight=counts[a])
    ew = Counter()
    for auth in papers:
        sub = [a for a in auth if a in top]
        for a, b in itertools.combinations(sorted(set(sub)), 2):
            ew[(a, b)] += 1
    for (a, b), w in ew.items():
        if w >= min_edge:
            G.add_edge(a, b, weight=w)
    G.remove_nodes_from(list(nx.isolates(G)))
    if G.number_of_nodes() == 0:
        print("  [author_network] sem arestas suficientes"); return

    if community_louvain:
        part = community_louvain.best_partition(G, random_state=42)
    else:
        part = {n: 0 for n in G.nodes()}
    import matplotlib.cm as cm
    ncol = max(part.values()) + 1
    palette = cm.get_cmap("tab20", ncol)

    pos = nx.spring_layout(G, k=0.6, seed=42, weight="weight")
    fig, ax = plt.subplots(figsize=(13, 10))
    nx.draw_networkx_edges(G, pos, alpha=0.25, width=[0.3 + G[u][v]["weight"]
                           for u, v in G.edges()], edge_color="#999999", ax=ax)
    sizes = [120 + 90 * G.nodes[n]["weight"] for n in G.nodes()]
    colors = [palette(part[n]) for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors,
                           edgecolors="white", linewidths=0.8, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7.5, ax=ax)
    ax.set_title("Author co-authorship network (top authors, coloured by cluster)",
                 fontweight="bold", fontsize=14)
    ax.axis("off"); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig8_author_network.png"),
                dpi=300, bbox_inches="tight")
    plt.close()

    # versão interativa
    try:
        from pyvis.network import Network
        net = Network(height="750px", width="100%", bgcolor="#ffffff", notebook=False)
        for n in G.nodes():
            net.add_node(n, label=n, value=G.nodes[n]["weight"], group=part[n])
        for u, v in G.edges():
            net.add_edge(u, v, value=G[u][v]["weight"])
        net.force_atlas_2based()
        net.write_html(os.path.join(FIGURES_DIR, "fig8_author_network.html"),
                       notebook=False)
    except Exception as e:
        print("  [author_network html] pulado:", str(e)[:60])


# ----------------------------------------------------------------------
def _keyword_series(df):
    kw = (df["keywords"].dropna().astype(str)
          .str.replace(r"[|,]", ";", regex=True)
          .str.split(";").explode().str.lower().str.strip())
    return kw[(kw != "") & (kw.str.len() > 2) & (~kw.isin(KW_STOP))]


def fig_wordcloud(df):
    from wordcloud import WordCloud
    freq = _keyword_series(df).value_counts().to_dict()
    if not freq:
        return
    wc = WordCloud(width=1600, height=800, background_color="white",
                   colormap="tab10", prefer_horizontal=0.9,
                   max_words=180).generate_from_frequencies(freq)
    plt.figure(figsize=(16, 8))
    plt.imshow(wc, interpolation="bilinear"); plt.axis("off")
    plt.title("Keyword word cloud", fontweight="bold", fontsize=16)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig9_keyword_wordcloud.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


def fig_treemap(df, n=12):
    import squarify
    top = _keyword_series(df).value_counts().head(n)
    if top.empty:
        return
    import matplotlib.cm as cm
    colors = [cm.tab20(i) for i in range(len(top))]
    plt.figure(figsize=(13, 8))
    squarify.plot(sizes=top.values,
                  label=[f"{k}\n{v}" for k, v in top.items()],
                  color=colors, text_kwargs={"fontsize": 11, "color": "white",
                                             "fontweight": "bold"})
    plt.title("Keyword tree map", fontweight="bold", fontsize=15)
    plt.axis("off"); plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig10_keyword_treemap.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


# ----------------------------------------------------------------------
def fig_thematic_evolution(df, periods=((2000, 2011), (2012, 2018), (2019, 2026)),
                           top_k=8):
    import plotly.graph_objects as go
    labels, label_idx = [], {}

    def idx(name):
        if name not in label_idx:
            label_idx[name] = len(labels)
            labels.append(name)
        return label_idx[name]

    period_top = []
    for (lo, hi) in periods:
        sub = df[(df["year"] >= lo) & (df["year"] <= hi)]
        top = _keyword_series(sub).value_counts().head(top_k).index.tolist()
        period_top.append(top)

    src, tgt, val = [], [], []
    for p in range(len(periods) - 1):
        loA, hiA = periods[p]; loB, hiB = periods[p + 1]
        subB = df[(df["year"] >= loB) & (df["year"] <= hiB)]
        for ka in period_top[p]:
            for kb in period_top[p + 1]:
                # co-ocorrência dos dois termos no período seguinte
                corpus = (subB["title"].fillna("") + " " +
                          subB["keywords"].fillna("")).str.lower()
                w = int(corpus.str.contains(re.escape(ka)).__and__(
                        corpus.str.contains(re.escape(kb))).sum())
                if w > 0:
                    src.append(idx(f"{ka} ({loA}-{hiA})"))
                    tgt.append(idx(f"{kb} ({loB}-{hiB})"))
                    val.append(w)
    if not src:
        print("  [thematic_evolution] sem fluxos"); return
    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=15, thickness=16,
                  color=ACCENT, line=dict(color="white", width=0.5)),
        link=dict(source=src, target=tgt, value=val,
                  color="rgba(0,140,186,0.3)")))
    fig.update_layout(title_text="Thematic evolution across periods",
                      font_size=11, width=1300, height=750)
    html = os.path.join(FIGURES_DIR, "fig11_thematic_evolution.html")
    fig.write_html(html)
    try:
        fig.write_image(os.path.join(FIGURES_DIR, "fig11_thematic_evolution.png"),
                        scale=2)
    except Exception as e:
        print("  [thematic PNG] pulado (kaleido):", str(e)[:60])


# ----------------------------------------------------------------------
def fig_strategic_map(df, n_terms=40):
    """Mapa estratégico: centralidade (x) vs densidade (y) por termo,
    aproximando o thematic map do bibliometrix."""
    import networkx as nx
    kw_lists = []
    for _, row in df.iterrows():
        ks = [k.strip().lower() for k in
              re.split(r"[;|,]", str(row["keywords"])) if k.strip()]
        ks = [k for k in set(ks) if len(k) > 2 and k not in KW_STOP]
        if ks:
            kw_lists.append(ks)
    freq = Counter(k for ks in kw_lists for k in ks)
    top = [k for k, _ in freq.most_common(n_terms)]
    top_set = set(top)
    co = Counter()
    for ks in kw_lists:
        for a, b in itertools.combinations(sorted(set(ks) & top_set), 2):
            co[(a, b)] += 1
    G = nx.Graph()
    G.add_nodes_from(top)
    for (a, b), w in co.items():
        G.add_edge(a, b, weight=w)

    # centralidade = grau ponderado (relevância externa); densidade = clustering
    deg = dict(G.degree(weight="weight"))
    clust = nx.clustering(G, weight="weight")
    xs = np.array([deg.get(k, 0) for k in top], float)
    ys = np.array([clust.get(k, 0) for k in top], float)
    sizes = np.array([freq[k] for k in top], float)
    xm, ym = np.median(xs), np.median(ys)

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.axvline(xm, color="gray", ls="--", lw=1)
    ax.axhline(ym, color="gray", ls="--", lw=1)
    ax.scatter(xs, ys, s=40 + 800 * sizes / sizes.max(), alpha=0.55,
               color=ACCENT, edgecolor="white")
    for k, x, y in zip(top, xs, ys):
        ax.annotate(k, (x, y), fontsize=8, ha="center", va="center")
    ax.text(0.98, 0.98, "Motor themes", transform=ax.transAxes, ha="right",
            va="top", fontsize=11, color="gray")
    ax.text(0.02, 0.98, "Niche themes", transform=ax.transAxes, ha="left",
            va="top", fontsize=11, color="gray")
    ax.text(0.98, 0.02, "Basic themes", transform=ax.transAxes, ha="right",
            va="bottom", fontsize=11, color="gray")
    ax.text(0.02, 0.02, "Emerging/declining", transform=ax.transAxes, ha="left",
            va="bottom", fontsize=11, color="gray")
    ax.set_xlabel("Relevance / Centrality (weighted degree)")
    ax.set_ylabel("Development / Density (clustering)")
    ax.set_title("Strategic (thematic) map of keywords", fontweight="bold",
                 fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURES_DIR, "fig12_strategic_map.png"),
                dpi=300, bbox_inches="tight")
    plt.close()


FIGS = [
    ("mapa de documentos", fig_map_documents),
    ("mapa de citações", fig_map_citations),
    ("colaboração entre países", fig_country_collaboration),
    ("rede de autores", fig_author_network),
    ("nuvem de palavras", fig_wordcloud),
    ("treemap", fig_treemap),
    ("evolução temática", fig_thematic_evolution),
    ("mapa estratégico", fig_strategic_map),
]


def main():
    df = load()
    for name, fn in FIGS:
        try:
            print(f"→ {name}")
            fn(df)
        except Exception as e:
            print(f"  ! falhou ({name}): {type(e).__name__}: {str(e)[:120]}")
    print(f"[OK] Figuras avançadas em {FIGURES_DIR}")


if __name__ == "__main__":
    main()
