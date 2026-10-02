"""Painel: Custo e Acessibilidade de uma Dieta Saudável (dados FAO/FAOSTAT).

Execução: streamlit run app.py
"""

import base64
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ======================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ======================================================================
st.set_page_config(
    page_title="Custo e Acessibilidade de uma Dieta Saudável",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================================
# 2. CONSTANTES
# ======================================================================
# Caminhos dos arquivos usados pelo painel.
BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_DADOS = BASE_DIR / "Custo_Dieta_Saudavel_Traduzido_Completo.csv"
ARQUIVO_LOGO = BASE_DIR / "assets" / "logo_fao_branco.png"
PASTA_BANDEIRAS = BASE_DIR / "assets" / "bandeiras"

# Paleta do tema escuro: cores das séries (ordem fixa), texto, grade e fundos.
AZUL_FAO = "#116EAA"
CORES_SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
TEXTO, TEXTO_SECUNDARIO, TEXTO_MUDO = "#ffffff", "#c3c2b7", "#898781"
GRADE, EIXO, SUPERFICIE, FUNDO = "#2c2c2a", "#383835", "#1a1a19", "#0d0d0d"
BARRA_NEUTRA = "#5c5b57"
ESCALA_MAPA = [[0, "#0d366b"], [0.5, "#3987e5"], [1, "#cde2fb"]]

# Unidades: a moeda local não permite comparar países (cada um usa a sua).
UNIDADE_PADRAO = "Poder de Compra por Pessoa/Dia"
UNIDADE_MOEDA_LOCAL = "Moeda Local por per capita por dia"
UNIDADE_PERCENTUAL = "Sem Dados"  # nome definido no CSV para os valores em %

INDICADOR_PADRAO = "Custo de uma dieta saudável (CoHD)"
PAISES_PADRAO = ("Brasil", "Mundo")
MAX_SELECAO = 8  # igual ao número de cores disponíveis em CORES_SERIES

# Continente do filtro -> escopo do mapa do Plotly (o padrão é o mundo todo).
ESCOPO_MAPA = {
    "África": "africa",
    "Ásia": "asia",
    "Europa": "europe",
    "América do Sul": "south america",
    "América do Norte": "north america",
    "América Central e Caribe": "north america",
}

GLOSSARIO = {
    "Custo de uma dieta saudável (CoHD)": "Custo mínimo, em cada país, de uma dieta que atende às diretrizes alimentares nacionais.",
    "Prevalência de inacessibilidade (PUA)": "Percentual da população que não consegue pagar por uma dieta saudável.",
    "Número de pessoas sem acesso a uma dieta saudável (NUA)": "Quantidade de pessoas, em milhões, que não conseguem pagar por uma dieta saudável.",
    "Grupos de alimentos": "Custo isolado de cada grupo: amido, origem animal, frutas, leguminosas/nozes/sementes, vegetais e óleos/gorduras.",
    "Poder de Compra por Pessoa/Dia": "Valores em dólares internacionais (PPC), que permitem comparar países com moedas diferentes.",
}

# Estilo visual (banner, cartões e título de cada país).
CSS = f"""
<style>
.block-container {{ padding-top: 2rem; max-width: 1400px; }}
.banner {{
    display: flex; align-items: center; gap: 2.5rem;
    background: linear-gradient(120deg, {AZUL_FAO} 0%, #0c4f7d 100%);
    border-radius: 14px; padding: 1.4rem 2.2rem; margin-bottom: 1.2rem;
}}
.banner > div {{ flex: 1; min-width: 0; }}
.banner img.logo {{ height: 88px; flex: none; }}
.banner h1 {{ color: #fff; font-size: 1.75rem; line-height: 1.15; margin: 0; padding: 0; }}
.banner p {{ color: rgba(255,255,255,.85); margin: .35rem 0 .7rem 0; }}
.chip {{
    display: inline-block; background: rgba(255,255,255,.16); color: #fff;
    border-radius: 999px; padding: .2rem .8rem; font-size: .8rem; margin-right: .5rem;
}}
.grade-cartoes {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: .8rem; margin: .4rem 0 .6rem 0;
}}
.cartao {{
    background: {SUPERFICIE}; border: 1px solid rgba(255,255,255,.08);
    border-radius: 12px; padding: .8rem 1rem;
}}
.cartao-rotulo {{ color: {TEXTO_MUDO}; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }}
.cartao-valor {{ color: {TEXTO}; font-size: 1.75rem; font-weight: 600; line-height: 1.25; }}
.cartao-detalhe {{ color: {TEXTO_SECUNDARIO}; font-size: .82rem; }}
.titulo-pais {{ display: flex; align-items: center; margin: 1.4rem 0 .2rem 0; font-size: 1.5rem; font-weight: 700; }}
.titulo-pais img {{ height: 1.6rem; border-radius: 3px; margin-right: .7rem; }}
</style>
"""


# ======================================================================
# 3. FUNÇÕES AUXILIARES: DADOS, FORMATAÇÃO E HTML
# ======================================================================
@st.cache_data(show_spinner=False)
def carregar_dados(caminho: Path) -> pd.DataFrame:
    """Lê o CSV, valida as colunas obrigatórias e converte os tipos."""
    # keep_default_na=False evita que o código ISO "na" (Namíbia) vire valor ausente.
    dados = pd.read_csv(caminho, keep_default_na=False, na_values=[""])

    obrigatorias = {"Pais_Regiao", "Codigo_ISO", "Codigo_ISO3", "Item_Analise",
                    "Continente", "Ano", "Unidade", "Valor", "Publicacao"}
    ausentes = obrigatorias.difference(dados.columns)
    if ausentes:
        raise ValueError("O CSV não contém as colunas obrigatórias: " + ", ".join(sorted(ausentes)))

    # Regiões e grupos não têm código de país: ficam com texto vazio.
    dados[["Codigo_ISO", "Codigo_ISO3"]] = dados[["Codigo_ISO", "Codigo_ISO3"]].fillna("")
    dados["Ano"] = pd.to_numeric(dados["Ano"], errors="coerce").astype("Int64")
    dados["Valor"] = pd.to_numeric(dados["Valor"], errors="coerce")
    return dados.dropna(subset=["Ano"])


def ordenar_sem_acento(valores) -> list[str]:
    """Ordena alfabeticamente ignorando acentos (África junto do A, não no fim)."""
    return sorted(valores, key=lambda v: unicodedata.normalize("NFD", v))


def numero_br(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro: 1.234,56."""
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_valor(valor: float, unidade: str) -> str:
    """Formata um valor conforme a unidade (%, milhões de pessoas ou número simples)."""
    if pd.isna(valor):
        return "—"
    if unidade == UNIDADE_PERCENTUAL:
        return f"{numero_br(valor, 1)}%"
    sufixo = " mi" if "milhões" in unidade.lower() else ""
    return f"{numero_br(valor)}{sufixo}"


def rotulo_unidade(unidade: str) -> str:
    """Nome da unidade para textos (o CSV guarda os percentuais como 'Sem Dados')."""
    return "% da população" if unidade == UNIDADE_PERCENTUAL else unidade


@st.cache_data(show_spinner=False)
def imagem_base64(caminho: Path) -> str:
    """Lê uma imagem e a converte em texto base64 para embutir no HTML."""
    return base64.b64encode(caminho.read_bytes()).decode() if caminho.exists() else ""


def renderizar_html(bloco: str) -> None:
    """Exibe HTML sem quebras de linha (o Markdown trataria o recuo como código)."""
    st.markdown(re.sub(r"\n\s*", "", bloco), unsafe_allow_html=True)


def bandeira_html(codigo_iso: str) -> str:
    """Tag <img> da bandeira do país; vazia para regiões e grupos."""
    imagem = imagem_base64(PASTA_BANDEIRAS / f"{codigo_iso}.png") if codigo_iso else ""
    return f'<img src="data:image/png;base64,{imagem}" alt="Bandeira">' if imagem else ""


def cores_por_entidade(selecionados: list[str]) -> dict[str, str]:
    """Mantém a mesma cor para cada país/região enquanto ele estiver selecionado."""
    atuais = st.session_state.get("mapa_cores", {})
    mapa = {pais: cor for pais, cor in atuais.items() if pais in selecionados}
    livres = [cor for cor in CORES_SERIES if cor not in mapa.values()]
    for pais in selecionados:
        if pais not in mapa and livres:
            mapa[pais] = livres.pop(0)
    st.session_state["mapa_cores"] = mapa
    return mapa


def cartao_html(rotulo: str, valor: str, detalhe: str) -> str:
    """Um cartão de indicador (rótulo, valor grande e detalhe)."""
    return (
        f'<div class="cartao"><div class="cartao-rotulo">{rotulo}</div>'
        f'<div class="cartao-valor">{valor}</div><div class="cartao-detalhe">{detalhe}</div></div>'
    )


def cartoes_indicadores(dados_pais: pd.DataFrame, unidade: str) -> str:
    """Monta os 5 cartões de um país: valor atual, variação, média, menor e maior valor."""
    primeiro, ultimo = dados_pais.iloc[0], dados_pais.iloc[-1]
    menor = dados_pais.loc[dados_pais["Valor"].idxmin()]
    maior = dados_pais.loc[dados_pais["Valor"].idxmax()]

    # Variação: em pontos percentuais para valores em %, e em % para os demais.
    if len(dados_pais) > 1 and primeiro["Valor"]:
        if unidade == UNIDADE_PERCENTUAL:
            delta, sufixo = ultimo["Valor"] - primeiro["Valor"], " p.p."
        else:
            delta, sufixo = (ultimo["Valor"] / primeiro["Valor"] - 1) * 100, "%"
        seta = "▲" if delta > 0 else "▼" if delta < 0 else "■"
        variacao = f"{seta} {numero_br(abs(delta), 1)}{sufixo}"
        periodo = f"{int(primeiro['Ano'])} → {int(ultimo['Ano'])}"
    else:
        variacao, periodo = "—", "Só há um ano"

    return (
        '<div class="grade-cartoes">'
        + cartao_html(f"Valor em {int(ultimo['Ano'])}", formatar_valor(ultimo["Valor"], unidade), "Último ano do período")
        + cartao_html("Variação no período", variacao, periodo)
        + cartao_html("Média", formatar_valor(dados_pais["Valor"].mean(), unidade), "No período selecionado")
        + cartao_html("Menor valor", formatar_valor(menor["Valor"], unidade), f"Em {int(menor['Ano'])}")
        + cartao_html("Maior valor", formatar_valor(maior["Valor"], unidade), f"Em {int(maior['Ano'])}")
        + "</div>"
    )


def escolher_ano(anos: list[int], rotulo: str, chave: str) -> int:
    """Slider de ano; se houver um único ano, apenas o exibe."""
    if len(anos) == 1:
        st.caption(f"Ano: {anos[0]} (único disponível)")
        return anos[0]
    # A chave inclui os anos para o estado reiniciar quando as opções mudam.
    return st.select_slider(rotulo, options=anos, value=anos[-1], key=f"{chave}_{anos[0]}_{anos[-1]}")


def rodape(total_registros: int, publicacao: str) -> None:
    """Rodapé com a fonte dos dados, a licença e a quantidade de registros."""
    registros = f"{total_registros:,}".replace(",", ".")
    st.divider()
    st.caption(
        "**Fonte dos dados:** FAO — Organização das Nações Unidas para a Alimentação e a Agricultura. "
        "[FAOSTAT: Cost and Affordability of a Healthy Diet (CoAHD)](https://www.fao.org/faostat/en/#data/CAHD), "
        "em parceria com o Banco Mundial. "
        f"Publicação: {publicacao}. "
        "Licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). "
        f"{registros} registros carregados."
    )


# ======================================================================
# 4. FUNÇÕES DE GRÁFICOS (Plotly)
# ======================================================================
def aplicar_tema(fig: go.Figure, altura: int) -> go.Figure:
    """Aplica o tema escuro comum a todos os gráficos."""
    fig.update_layout(
        height=altura,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Source Sans Pro, Segoe UI, sans-serif", size=14, color=TEXTO_SECUNDARIO),
        separators=",.",  # decimal com vírgula e milhar com ponto
        showlegend=False,
        hoverlabel=dict(bgcolor=SUPERFICIE, bordercolor=EIXO, font=dict(color=TEXTO, size=14)),
    )
    return fig


def grafico_pais(dados: pd.DataFrame, cor: str, unidade: str) -> go.Figure:
    """Linha da evolução de um país, com rótulo no primeiro e no último ponto."""
    anos, valores = dados["Ano"].astype(int), dados["Valor"]
    minimo, maximo = valores.min(), valores.max()
    folga = (maximo - minimo) * 0.25 or abs(maximo) * 0.1 or 1  # espaço para os rótulos

    fig = go.Figure()
    # Linha com marcadores e texto de hover.
    fig.add_trace(go.Scatter(
        x=anos, y=valores, mode="lines+markers",
        line=dict(color=cor, width=2.5),
        marker=dict(size=8, color=cor, line=dict(color=FUNDO, width=2)),
        customdata=[formatar_valor(v, unidade) for v in valores],
        hovertemplate="<b>%{x}</b><br>%{customdata}<extra></extra>",
    ))
    # Destaque do primeiro e do último ponto, com o valor escrito.
    extremos = dados.iloc[[0, -1]] if len(dados) > 1 else dados
    fig.add_trace(go.Scatter(
        x=extremos["Ano"].astype(int), y=extremos["Valor"], mode="markers+text",
        marker=dict(size=12, color=cor, line=dict(color=FUNDO, width=2)),
        text=[formatar_valor(v, unidade) for v in extremos["Valor"]],
        textposition="top center", textfont=dict(color=TEXTO, size=14),
        hoverinfo="skip", cliponaxis=False,
    ))
    aplicar_tema(fig, 320)
    fig.update_xaxes(dtick=1, tickformat="d", showgrid=False, linecolor=EIXO, tickcolor=EIXO,
                     automargin=True, range=[anos.min() - 0.5, anos.max() + 0.5])
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, tickformat=",.2~f", automargin=True,
                     range=[minimo - folga, maximo + folga])
    return fig


def grafico_comparacao(filtrado: pd.DataFrame, paises: list[str], cores: dict[str, str]) -> go.Figure:
    """Todos os países no mesmo gráfico, indexados: primeiro ano = 100."""
    fig = go.Figure()
    rotular = len(paises) <= 4  # com muitas linhas, só a legenda identifica as séries
    for pais in paises:
        dados = filtrado[filtrado["Pais_Regiao"].eq(pais)].sort_values("Ano")
        if dados.empty or dados["Valor"].iloc[0] == 0:
            continue  # sem valor inicial não é possível calcular o índice
        indice = dados["Valor"] / dados["Valor"].iloc[0] * 100
        cor = cores.get(pais, TEXTO_MUDO)
        fig.add_trace(go.Scatter(
            x=dados["Ano"].astype(int), y=indice, name=pais, mode="lines+markers",
            line=dict(color=cor, width=2.5),
            marker=dict(size=7, color=cor, line=dict(color=FUNDO, width=2)),
            customdata=dados["Valor"],
            hovertemplate="%{customdata:,.2f} (índice %{y:,.0f})<extra>" + pais + "</extra>",
        ))
        if rotular:  # nome da série ao lado do último ponto
            nome = pais if len(pais) <= 24 else pais[:23] + "…"
            fig.add_annotation(x=int(dados["Ano"].iloc[-1]), y=indice.iloc[-1], text=nome,
                               showarrow=False, xanchor="left", xshift=10,
                               font=dict(color=TEXTO_SECUNDARIO, size=13))
    fig.add_hline(y=100, line=dict(color=EIXO, width=1, dash="dot"))  # referência: 100

    aplicar_tema(fig, 460)
    fig.update_layout(showlegend=True, hovermode="x unified",
                      legend=dict(orientation="h", y=1.1, x=0, font=dict(color=TEXTO_SECUNDARIO)))
    anos = sorted(int(a) for a in filtrado["Ano"].unique())
    fig.update_xaxes(tickmode="array", tickvals=anos, tickformat="d", showgrid=False,
                     linecolor=EIXO, automargin=True,
                     range=[anos[0] - 0.5, anos[-1] + (3.2 if rotular else 0.5)])
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, tickformat=",.0f", automargin=True)
    return fig


def grafico_ranking(dados_ano: pd.DataFrame, cores: dict[str, str], unidade: str, quantidade: int) -> go.Figure:
    """Barras horizontais com os maiores valores; os países selecionados ficam coloridos."""
    ordenado = dados_ano.sort_values("Valor", ascending=False)
    topo = ordenado.head(quantidade)
    # Países selecionados que ficaram fora do topo são acrescentados ao final.
    extras = ordenado[ordenado["Pais_Regiao"].isin(cores) & ~ordenado["Pais_Regiao"].isin(topo["Pais_Regiao"])]
    dados = pd.concat([topo, extras]).sort_values("Valor")
    textos = [formatar_valor(v, unidade) for v in dados["Valor"]]

    fig = go.Figure(go.Bar(
        x=dados["Valor"], y=dados["Pais_Regiao"], orientation="h",
        marker=dict(color=[cores.get(p, BARRA_NEUTRA) for p in dados["Pais_Regiao"]], cornerradius=4),
        text=textos, textposition="outside", textfont=dict(color=TEXTO_SECUNDARIO, size=13),
        customdata=textos, hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
        cliponaxis=False,
    ))
    aplicar_tema(fig, 90 + 27 * len(dados))
    fig.update_layout(bargap=0.35, margin=dict(l=10, r=70, t=10, b=10))
    fig.update_xaxes(showgrid=False, showticklabels=False, zeroline=False)
    fig.update_yaxes(showgrid=False, linecolor=EIXO, tickfont=dict(color=TEXTO, size=13), automargin=True)
    return fig


def grafico_mapa(dados_ano: pd.DataFrame, unidade: str, escopo: str) -> go.Figure:
    """Mapa coroplético: tons mais claros indicam valores maiores."""
    fig = go.Figure(go.Choropleth(
        locations=dados_ano["Codigo_ISO3"], z=dados_ano["Valor"], text=dados_ano["Pais_Regiao"],
        customdata=[formatar_valor(v, unidade) for v in dados_ano["Valor"]],
        hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
        colorscale=ESCALA_MAPA, marker_line_color=FUNDO, marker_line_width=0.5,
        colorbar=dict(thickness=12, len=0.7, tickfont=dict(color=TEXTO_SECUNDARIO), outlinewidth=0),
    ))
    aplicar_tema(fig, 520)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    fig.update_geos(
        scope=escopo, projection_type="natural earth", projection_rotation=dict(lon=0),
        lataxis_range=[-58, 85] if escopo == "world" else None,  # oculta a Antártida
        showframe=False, showcoastlines=False, showland=True, landcolor="#33322e",
        showcountries=True, countrycolor=FUNDO, showocean=False, showlakes=False,
        bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ======================================================================
# 5. CARREGAMENTO DOS DADOS
# ======================================================================
try:
    df = carregar_dados(ARQUIVO_DADOS)
except (FileNotFoundError, pd.errors.ParserError, UnicodeDecodeError, ValueError) as erro:
    st.error(f"Não foi possível carregar a base de dados: {erro}")
    st.stop()

# ======================================================================
# 6. BANNER DE ABERTURA
# ======================================================================
st.markdown(CSS, unsafe_allow_html=True)

# Países têm código ISO-3; regiões e grupos (Mundo, África, faixas de renda) não têm.
total_paises = df.loc[df["Codigo_ISO3"].ne(""), "Pais_Regiao"].nunique()
total_regioes = df["Pais_Regiao"].nunique() - total_paises

renderizar_html(f"""
<div class="banner">
  <img class="logo" src="data:image/png;base64,{imagem_base64(ARQUIVO_LOGO)}" alt="FAO">
  <div>
    <h1>Custo e Acessibilidade de uma Dieta Saudável</h1>
    <p>Indicadores da FAO por país e região, de {int(df['Ano'].min())} a {int(df['Ano'].max())}</p>
    <span class="chip">{total_paises} países</span>
    <span class="chip">{total_regioes} regiões e grupos</span>
    <span class="chip">Fonte: FAOSTAT</span>
  </div>
</div>
""")

# ======================================================================
# 7. FILTROS (BARRA LATERAL)
# ======================================================================
with st.sidebar:
    st.header("Filtros")

    # Indicador (o que está sendo medido).
    indicadores = ordenar_sem_acento(df["Item_Analise"].dropna().unique())
    indice_indicador = indicadores.index(INDICADOR_PADRAO) if INDICADOR_PADRAO in indicadores else 0
    indicador = st.selectbox("Indicador", indicadores, index=indice_indicador)

    # Unidade: só as que existem para o indicador escolhido.
    unidades = sorted(df.loc[df["Item_Analise"].eq(indicador), "Unidade"].dropna().unique())
    indice_unidade = unidades.index(UNIDADE_PADRAO) if UNIDADE_PADRAO in unidades else 0
    unidade = st.selectbox("Unidade", unidades, index=indice_unidade)
    base = df[df["Item_Analise"].eq(indicador) & df["Unidade"].eq(unidade)]

    # Continente: restringe a lista de países e o zoom do mapa ("Grupos globais" por último).
    continentes = ["Todos"] + sorted(
        base["Continente"].dropna().unique(),
        key=lambda c: (c == "Grupos globais", unicodedata.normalize("NFD", c)),
    )
    continente = st.selectbox("Continente", continentes)
    if continente != "Todos":
        base = base[base["Continente"].eq(continente)]

    # Países e regiões (até 8, cada um com sua cor).
    opcoes_paises = ordenar_sem_acento(base["Pais_Regiao"].dropna().unique())
    selecao_inicial = [p for p in PAISES_PADRAO if p in opcoes_paises] or opcoes_paises[:1]
    paises = st.multiselect("Países ou regiões", opcoes_paises, default=selecao_inicial,
                            max_selections=MAX_SELECAO, placeholder=f"Selecione até {MAX_SELECAO} opções")

    # Período: o slider só existe quando há mais de um ano.
    ano_inicial, ano_final = int(base["Ano"].min()), int(base["Ano"].max())
    if ano_inicial == ano_final:
        st.caption(f"Período: {ano_inicial} (único ano disponível)")
        periodo = (ano_inicial, ano_final)
    else:
        periodo = st.slider("Período", ano_inicial, ano_final, (ano_inicial, ano_final))

# ======================================================================
# 8. PREPARAÇÃO DOS DADOS FILTRADOS
# ======================================================================
cores = cores_por_entidade(paises)

# Selecionados no período: alimenta as abas Evolução e Dados.
selecionados = base[base["Pais_Regiao"].isin(paises) & base["Ano"].between(*periodo)].dropna(subset=["Valor"])

# Todos os países (sem regiões) com valor: alimenta o Ranking e o Mapa.
com_valor = base.dropna(subset=["Valor"])
somente_paises = com_valor[com_valor["Codigo_ISO3"].ne("")]
anos_com_dados = sorted(int(a) for a in com_valor["Ano"].unique())

st.markdown(f"**{indicador}** · {rotulo_unidade(unidade)}")
aba_evolucao, aba_ranking, aba_mapa, aba_dados = st.tabs(
    ["📈 Evolução", "🏆 Ranking", "🗺️ Mapa", "📋 Dados e glossário"]
)

# ======================================================================
# 9. ABA EVOLUÇÃO: um gráfico por país, ou todos comparados por índice
# ======================================================================
with aba_evolucao:
    if selecionados.empty:
        st.info("Selecione ao menos um país ou região na barra lateral, com dados no período escolhido.")
    else:
        comparar = len(paises) > 1 and st.toggle(
            "Comparar todos no mesmo gráfico (índice: primeiro ano = 100)",
            help="Coloca países de escalas diferentes lado a lado: cada linha começa em 100 e mostra quanto cresceu ou caiu.",
        )
        if comparar:
            st.plotly_chart(grafico_comparacao(selecionados, paises, cores), theme=None, key="grafico_comparacao")
            st.caption("Passe o mouse sobre as linhas para ver o valor real de cada ano.")
        else:
            for pais in paises:
                dados_pais = selecionados[selecionados["Pais_Regiao"].eq(pais)].sort_values("Ano")
                if dados_pais.empty:
                    continue
                renderizar_html(f'<div class="titulo-pais">{bandeira_html(dados_pais["Codigo_ISO"].iloc[0])}{pais}</div>')
                renderizar_html(cartoes_indicadores(dados_pais, unidade))
                st.plotly_chart(grafico_pais(dados_pais, cores.get(pais, CORES_SERIES[0]), unidade),
                                theme=None, key=f"grafico_{pais}")

# ======================================================================
# 10. ABA RANKING: maiores valores entre os países em um ano
# ======================================================================
AVISO_MOEDA = (
    "Valores em moeda local não são comparáveis entre países, porque cada país usa uma moeda diferente. "
    f"Troque a unidade para **{UNIDADE_PADRAO}** para ver {{recurso}}."
)

with aba_ranking:
    if unidade == UNIDADE_MOEDA_LOCAL:
        st.info(AVISO_MOEDA.format(recurso="o ranking"))
    elif somente_paises.empty:
        st.info("Este indicador, com esta unidade e este continente, não tem países para ranquear.")
    else:
        coluna_ano, coluna_quantidade = st.columns([3, 1])
        with coluna_ano:
            ano_ranking = escolher_ano(anos_com_dados, "Ano do ranking", "ano_ranking")
        with coluna_quantidade:
            quantidade = st.selectbox("Mostrar", [10, 15, 20, 30], index=1)

        continente_texto = f" · {continente}" if continente != "Todos" else ""
        st.markdown(f"**Maiores valores em {ano_ranking}** · {rotulo_unidade(unidade)}{continente_texto}")
        st.plotly_chart(
            grafico_ranking(somente_paises[somente_paises["Ano"].eq(ano_ranking)], cores, unidade, quantidade),
            theme=None, key="grafico_ranking",
        )
        st.caption("Os países selecionados na barra lateral aparecem destacados com a própria cor, mesmo fora do topo.")

# ======================================================================
# 11. ABA MAPA: valor por país em um ano
# ======================================================================
with aba_mapa:
    if unidade == UNIDADE_MOEDA_LOCAL:
        st.info(AVISO_MOEDA.format(recurso="o mapa"))
    elif somente_paises.empty:
        st.info("Este indicador, com esta unidade e este continente, não tem países para o mapa.")
    else:
        ano_mapa = escolher_ano(anos_com_dados, "Ano do mapa", "ano_mapa")
        st.markdown(f"**{rotulo_unidade(unidade)} em {ano_mapa}** · tons mais claros indicam valores maiores")
        st.plotly_chart(
            grafico_mapa(somente_paises[somente_paises["Ano"].eq(ano_mapa)], unidade,
                         ESCOPO_MAPA.get(continente, "world")),
            theme=None, key="grafico_mapa",
        )
        st.caption("Países em cinza não têm dado para este ano. Use o filtro Continente para aproximar o mapa.")

# ======================================================================
# 12. ABA DADOS E GLOSSÁRIO: tabela filtrada, download e definições
# ======================================================================
with aba_dados:
    if selecionados.empty:
        st.info("Selecione ao menos um país ou região para ver a tabela.")
    else:
        tabela = selecionados[["Pais_Regiao", "Ano", "Valor"]].sort_values(["Pais_Regiao", "Ano"])
        st.dataframe(
            tabela, width="stretch", hide_index=True,
            column_config={
                "Pais_Regiao": "País / região",
                "Ano": st.column_config.NumberColumn("Ano", format="%d"),
                "Valor": st.column_config.NumberColumn(rotulo_unidade(unidade), format="%.2f"),
            },
        )
        st.download_button("Baixar dados filtrados (CSV)", tabela.to_csv(index=False).encode("utf-8-sig"),
                           file_name="dados_filtrados.csv", mime="text/csv")

    st.subheader("O que significam os indicadores?")
    for termo, explicacao in GLOSSARIO.items():
        st.markdown(f"**{termo}** — {explicacao}")

# ======================================================================
# 13. RODAPÉ
# ======================================================================
rodape(len(df), df["Publicacao"].iloc[0])
