# Primeira análise dos dados - Projeto de Análise de Dados e BI
# Grupo: Rafael Magno Guimarães Tabosa Braga e Levi Adler Borges de Albuquerque
#
# Usa as bases de dados_tratados (geradas pelo limpeza.py). Primeiro confere nossos números com os
# publicados pelas fontes, depois responde as perguntas P1 a P5.
# Saídas: dados_tratados/conferencia.csv e os gráficos na pasta figuras.
# Como rodar: python analise.py

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.formula.api as smf

PASTA_TRATADOS = Path("dados_tratados")
PASTA_FIGURAS = Path("figuras")
PASTA_FIGURAS.mkdir(exist_ok=True)
PERCENTUAL = "Percentual de alunos (%)"
NOTA_MATEMATICA = "Nota média em Matemática"


def calcular_media_ponderada(valores, pesos):
    validos = valores.notna() & pesos.notna()  # ignora quem não tem valor ou peso
    return (valores[validos] * pesos[validos]).sum() / pesos[validos].sum()


def calcular_media_por_grupo(tabela, coluna_grupo, coluna_valor, coluna_peso):
    medias = {}
    for grupo, linhas in tabela.groupby(coluna_grupo):
        medias[grupo] = calcular_media_ponderada(linhas[coluna_valor], linhas[coluna_peso])
    return pd.Series(medias)


def salvar_grafico(grafico, titulo, nome_arquivo):
    grafico.set_title(titulo, loc="left")
    plt.tight_layout()
    plt.savefig(PASTA_FIGURAS / f"{nome_arquivo}.png", dpi=150, bbox_inches="tight")
    plt.close()


ideb = pd.read_csv(PASTA_TRATADOS / "ideb_brasil_regioes_ufs.csv")
saeb = pd.read_csv(PASTA_TRATADOS / "saeb_2023_alunos.csv.gz")
tic_educacao = pd.read_csv(PASTA_TRATADOS / "tic_educacao.csv")
tic_kids = pd.read_csv(PASTA_TRATADOS / "tic_kids_em.csv")
tic_kids_finalidades = pd.read_csv(PASTA_TRATADOS / "tic_kids_em_finalidades.csv")
pisa = pd.read_csv(PASTA_TRATADOS / "pisa_brasil_compendio.csv")


# Conferência: nosso cálculo x número publicado pela fonte
lista_conferencia = []


def adicionar_conferencia(base, o_que_foi_conferido, publicado, calculado, fonte, tolerancia):
    lista_conferencia.append({"base": base, "o_que_foi_conferido": o_que_foi_conferido, "valor_publicado": publicado,
                              "nosso_calculo": round(calculado, 2), "diferenca": round(calculado - publicado, 2),
                              "bate": "Sim" if abs(calculado - publicado) <= tolerancia else "Não", "fonte": fonte})


brasil = ideb[(ideb["nivel"] == "Brasil") & (ideb["rede"] == "Total")].set_index("ano")
adicionar_conferencia("Ideb", "Ideb do ensino médio, Brasil, 2023", 4.3, brasil.loc[2023, "ideb"],
                      "Inep, resultados do Ideb 2025", 0.05)
adicionar_conferencia("Ideb", "Ideb do ensino médio, Brasil, 2025", 4.5, brasil.loc[2025, "ideb"],
                      "Inep, resultados do Ideb 2025", 0.05)
# Ideb = N x P; refazemos a conta em todas as linhas (o Inep arredonda em 1 casa)
completas = ideb.dropna(subset=["ideb", "nota_media_padronizada_N", "indicador_rendimento_P"])
diferenca = (completas["nota_media_padronizada_N"] * completas["indicador_rendimento_P"] - completas["ideb"]).abs()
adicionar_conferencia("Ideb", "Maior diferença entre N x P e o Ideb publicado", 0, diferenca.max(),
                      "Fórmula do Ideb (Inep)", 0.051)

# Saeb: média calculada dos microdados x nota do Saeb 2023 que aparece na planilha do Ideb
media_mt = calcular_media_ponderada(saeb["nota_mt"], saeb["peso_mt"])
media_lp = calcular_media_ponderada(saeb["nota_lp"], saeb["peso_lp"])
adicionar_conferencia("Saeb 2023", "Nota média de Matemática no ensino médio, Brasil",
                      brasil.loc[2023, "nota_saeb_matematica"], media_mt, "Planilha do Ideb 2025 (nota Saeb 2023)", 0.5)
adicionar_conferencia("Saeb 2023", "Nota média de Língua Portuguesa no ensino médio, Brasil",
                      brasil.loc[2023, "nota_saeb_portugues"], media_lp, "Planilha do Ideb 2025 (nota Saeb 2023)", 0.5)


def buscar_percentual_tic(indicador, recorte, texto_do_item=""):
    linha = tic_educacao[(tic_educacao["indicador"] == indicador) & (tic_educacao["recorte"] == recorte)
                         & (tic_educacao["resposta"] == "Sim")
                         & tic_educacao["item"].str.contains(texto_do_item, regex=False)]
    return linha["valor"].iloc[0]


usa_ia_tic = buscar_percentual_tic("G6", "Ensino Médio", "Inteligência")
adicionar_conferencia("TIC Educação 2024", "Alunos do EM que usam IA em pesquisas e atividades escolares (%)", 70.0,
                      usa_ia_tic, "Cetic.br, tabela G6", 0.5)

# TIC Kids: a Cetic.br divulga para 9 a 17 e 15 a 17 anos, então refazemos a conta no arquivo original
kids_original = pd.read_csv("dados_originais/tic_kids_online_brasil_2025_base_de_microdados_v1.0.csv", sep=";",
                            dtype=str, usecols=["FAIXA_ETARIA", "N4_A", "N4_B", "N4_C", "N4_D", "PESO"])
kids_original["PESO"] = pd.to_numeric(kids_original["PESO"].str.replace(",", "."))
kids_original = kids_original[kids_original["N4_A"] != "99"]  # só quem usa Internet
publicados = {"9 a 17 anos": {"N4_B": 59, "N4_A": 42, "N4_D": 21, "N4_C": 10},
              "15 a 17 anos": {"N4_B": 68, "N4_A": 60, "N4_D": 32, "N4_C": 12}}
for faixa, valores in publicados.items():
    grupo = kids_original if faixa == "9 a 17 anos" else kids_original[kids_original["FAIXA_ETARIA"] == "4"]
    for variavel, publicado in valores.items():
        respostas = grupo[~grupo[variavel].isin(["97", "98"])]
        percentual = 100 * calcular_media_ponderada((respostas[variavel] == "1").astype(float), respostas["PESO"])
        adicionar_conferencia("TIC Kids Online 2025", f"Usou IA ({variavel}), {faixa} (%)", publicado, percentual,
                              "Cetic.br, divulgação dos resultados", 0.5)


def refazer_media_pisa(variavel):
    # o compêndio não traz a média geral do Brasil, mas dá para refazer: soma(percentual x nota) de cada resposta
    tabela = pisa[pisa["variavel"] == variavel].pivot_table(index="categoria", columns="medida", values="valor")
    percentual, nota = tabela[PERCENTUAL], tabela[NOTA_MATEMATICA]
    nao_aplicada = "Not applicable / missing"
    respondeu = percentual.index != nao_aplicada
    media = (percentual[respondeu] * nota[respondeu]).sum() / percentual[respondeu].sum()
    if percentual[nao_aplicada] == 0 or pd.isna(nota[nao_aplicada]):
        return media
    parte_que_respondeu = (100 - percentual[nao_aplicada]) / 100
    return parte_que_respondeu * media + (1 - parte_que_respondeu) * nota[nao_aplicada]


# por sexo e por ST438Q01 a média tem de dar a mesma, porque as duas contas cobrem os mesmos alunos
adicionar_conferencia("Pisa 2025", "Nota média em Matemática refeita por ST438Q01 x refeita por sexo",
                      round(refazer_media_pisa("ST004D01T"), 2), refazer_media_pisa("ST438Q01DA"),
                      "Compêndio da OCDE (as duas contas cobrem os mesmos alunos)", 1.0)
respostas_pisa = pisa[(pisa["medida"] == PERCENTUAL) & (pisa["categoria"] != "Not applicable / missing")]
soma_por_pergunta = respostas_pisa.groupby("variavel")["valor"].sum()
pior_soma = soma_por_pergunta[(soma_por_pergunta - 100).abs().idxmax()]
adicionar_conferencia("Pisa 2025", "Soma dos percentuais das respostas (pior pergunta)", 100.0, pior_soma,
                      "As respostas somam 100%", 0.1)

conferencia = pd.DataFrame(lista_conferencia)
conferencia.to_csv(PASTA_TRATADOS / "conferencia.csv", index=False, encoding="utf-8-sig")
print(conferencia[["base", "o_que_foi_conferido", "valor_publicado", "nosso_calculo", "bate"]].to_string(index=False))


# P1 - Desempenho no ensino médio e evolução desde 2017 (Ideb)
total = ideb[ideb["rede"] == "Total"]
ideb_brasil = ideb[(ideb["nivel"] == "Brasil") & (ideb["ano"] >= 2017)]
ideb_por_rede = ideb_brasil.pivot_table(index="ano", columns="rede", values="ideb")
print("\nP1 - Ideb do ensino médio no Brasil, por rede\n", ideb_por_rede)
regioes = total[(total["nivel"] == "Região") & total["ano"].isin([2017, 2025])]
print("\nP1 - Ideb por região, 2017 e 2025\n", regioes.pivot_table(index="local", columns="ano", values="ideb"))
nordeste = total[(total["regiao"] == "Nordeste") & (total["nivel"] == "UF") & (total["ano"] == 2025)]
print("\nP1 - Ideb 2025 dos estados do Nordeste\n", nordeste.set_index("uf")["ideb"].sort_values(ascending=False))

# em cada UF: de 2017 a 2025 o Ideb subiu pela nota (N), pela aprovação (P) ou pelas duas?
ufs_2017 = total[(total["nivel"] == "UF") & (total["ano"] == 2017)].set_index("uf")
ufs_2025 = total[(total["nivel"] == "UF") & (total["ano"] == 2025)].set_index("uf")
nota_subiu = ufs_2025["nota_media_padronizada_N"] > ufs_2017["nota_media_padronizada_N"]
aprovacao_subiu = ufs_2025["indicador_rendimento_P"] > ufs_2017["indicador_rendimento_P"]
print("\nP1 - UFs em que subiram nota e aprovação:", (nota_subiu & aprovacao_subiu).sum())
print("P1 - UFs em que só a aprovação subiu:", list(ufs_2025.index[~nota_subiu & aprovacao_subiu]))
print("P1 - Maior e menor Ideb em 2025:", ufs_2025["ideb"].idxmax(), ufs_2025["ideb"].max(), "|",
      ufs_2025["ideb"].idxmin(), ufs_2025["ideb"].min())

grafico = ideb_por_rede[["Privada", "Total", "Estadual"]].plot(marker="o", ylim=(3, 6.5), ylabel="Ideb",
                                                               xticks=ideb_por_rede.index, figsize=(7, 3.6))
salvar_grafico(grafico, "Ideb do ensino médio no Brasil, por rede (2017 a 2025)", "p1_ideb_brasil")


# P2 - Frequência de uso de IA nos estudos (Pisa ST438, TIC Educação G6 e TIC Kids)
ordem_frequencia = ["Nunca ou quase nunca", "1 ou 2 vezes por ano", "1 ou 2 vezes por mês", "1 ou 2 vezes por semana",
                    "Todo dia ou quase todo dia", "Sem resposta"]
usos_pisa = {"ST438Q01DA": "Resumir um texto", "ST438Q02DA": "Pesquisa inicial sobre tema novo",
             "ST438Q03DA": "Rascunhar textos de trabalhos", "ST438Q04DA": "Ajudar a aprender"}
st438 = pisa[pisa["variavel"].isin(usos_pisa.keys())]
frequencia = st438[st438["medida"] == PERCENTUAL].pivot_table(index="variavel", columns="categoria_pt", values="valor")
frequencia = frequencia[ordem_frequencia].rename(index=usos_pisa)
semanal = frequencia["1 ou 2 vezes por semana"] + frequencia["Todo dia ou quase todo dia"]
semanal = 100 * semanal / (100 - frequencia["Sem resposta"])  # entre quem respondeu
print("\nP2 - Pisa: usa IA toda semana ou mais (% de quem respondeu)\n", semanal.round(1))
print(f"P2 - TIC Educação G6: {usa_ia_tic:.0f}% dos alunos do EM usam IA nas atividades escolares")
print(f"P2 - TIC Kids: {100 * calcular_media_ponderada(tic_kids['usa_ia_alguma'], tic_kids['peso']):.0f}% "
      f"usaram IA para alguma finalidade (n = {len(tic_kids)})")
percentual_por_regiao = 100 * calcular_media_por_grupo(tic_kids, "regiao", "usa_ia_alguma", "peso")
alunos_por_regiao = tic_kids["regiao"].value_counts()
uso_por_regiao = pd.DataFrame({"usou IA (%)": percentual_por_regiao, "alunos na amostra": alunos_por_regiao})
print("P2 - TIC Kids por região\n", uso_por_regiao.round(0))

cores = ["#d5d4cf", "#b3cbe9", "#7aa6e0", "#2a78d6", "#174a8a", "#f0f0f0"]
frequencia_ordenada = frequencia.loc[semanal.sort_values().index]
grafico = frequencia_ordenada.plot(kind="barh", stacked=True, color=cores, xlim=(0, 100), figsize=(8, 3.8),
                                   xlabel="% dos alunos de 15 anos", ylabel="")
grafico.legend(ncol=3, fontsize=8, loc="upper center", bbox_to_anchor=(0.4, -0.25))
salvar_grafico(grafico, "Pisa 2025: com que frequência usa chatbot de IA nas tarefas escolares", "p2_frequencia_pisa")


# P3 - Para que os alunos usam a IA (TIC Kids; a frequência por finalidade do Pisa está na P2)
uso_por_finalidade = 100 * calcular_media_por_grupo(tic_kids_finalidades, "finalidade", "usou", "peso")
uso_por_finalidade = uso_por_finalidade.sort_values()
print("\nP3 - TIC Kids, alunos do EM que usaram IA para...\n", uso_por_finalidade.round(1))
grafico = uso_por_finalidade.plot(kind="barh", xlim=(0, 100), figsize=(7, 3))
salvar_grafico(grafico, "TIC Kids 2025: alunos do ensino médio que usaram IA para... (%)", "p3_finalidades_tic_kids")


# P4 - Tecnologia e notas (Pisa e Saeb)
notas_st438 = st438[st438["medida"] == NOTA_MATEMATICA]
notas_por_frequencia = notas_st438.pivot_table(index="variavel", columns="categoria_pt", values="valor")
print("\nP4 - Pisa, nota em Matemática por frequência de uso de IA\n",
      notas_por_frequencia[ordem_frequencia].rename(index=usos_pisa).round(0).to_string())
ic173 = pisa[(pisa["variavel"] == "IC173Q02JA") & (pisa["medida"] == NOTA_MATEMATICA)]
print("\nP4 - Pisa, nota em Matemática por uso de recursos digitais nas aulas de Matemática\n",
      ic173.set_index("categoria_pt")["valor"].round(0))
st437 = pisa[(pisa["variavel"] == "ST437Q01DA") & (pisa["medida"] == PERCENTUAL)].set_index("categoria_pt")["valor"]
concordam = 100 * (st437["Concorda"] + st437["Concorda totalmente"]) / (100 - st437["Sem resposta"])
print(f"P4 - Pisa: {concordam:.1f}% dos que responderam concordam que recursos digitais ajudam a aprender "
      "coisas complexas")

# Saeb: diferença de nota de quem tem computador e Wi-Fi em casa, antes e depois de comparar
# alunos do mesmo nível socioeconômico (INSE) e da mesma rede (regressão com o peso de cada aluno)
regressao = saeb.dropna(subset=["nota_mt", "peso_mt", "tem_computador", "wifi", "inse"]).copy()
regressao["computador"] = (regressao["tem_computador"] == "Sim").astype(int)
regressao["wifi_casa"] = (regressao["wifi"] == "Sim").astype(int)
regressao["privada"] = (regressao["rede"] == "Privada").astype(int)
sem_controle = smf.wls("nota_mt ~ computador + wifi_casa", data=regressao, weights=regressao["peso_mt"]).fit()
com_controle = smf.wls("nota_mt ~ computador + wifi_casa + inse + privada", data=regressao,
                       weights=regressao["peso_mt"]).fit()
print(f"\nP4 - Saeb, {len(regressao)} alunos. Sem controle: computador +{sem_controle.params['computador']:.1f}, "
      f"Wi-Fi +{sem_controle.params['wifi_casa']:.1f}. Com INSE e rede: computador "
      f"+{com_controle.params['computador']:.1f}, Wi-Fi +{com_controle.params['wifi_casa']:.1f}")

niveis = ["Nível I", "Nível II", "Nível III", "Nível IV", "Nível V", "Nível VI", "Nível VII", "Nível VIII"]
nota_por_nivel = pd.DataFrame({
    "Sem computador em casa": calcular_media_por_grupo(saeb[saeb["tem_computador"] == "Não"], "nivel_inse",
                                                       "nota_mt", "peso_mt"),
    "Com computador em casa": calcular_media_por_grupo(saeb[saeb["tem_computador"] == "Sim"], "nivel_inse",
                                                       "nota_mt", "peso_mt"),
}).loc[niveis]
grafico = nota_por_nivel.plot(marker="o", figsize=(7, 3.6), xlabel="Nível socioeconômico (INSE)",
                              ylabel="Nota média em Matemática")
salvar_grafico(grafico, "Saeb 2023: nota em Matemática por nível socioeconômico", "p4_saeb_computador")


# P5 - Preparo de escolas e professores (TIC Educação)
escolas_ate_em = "Até Ensino Médio ou Educação Profissional"
preparo = pd.Series({
    "Alunos que usam IA nas atividades escolares (G6)": usa_ia_tic,
    "Alunos cujo professor falou sobre como usar IA (H4D)":
        buscar_percentual_tic("H4D", "Ensino Médio", "como usar aplicações"),
    "Alunos ensinados a checar erros da IA (H4D)": buscar_percentual_tic("H4D", "Ensino Médio", "Ensinou a verificar"),
    "Professores com formação em IA, entre os que fizeram formação (H7)":
        buscar_percentual_tic("H7", "Ensino Médio", "Inteligência Artificial"),
    "Escolas que permitem o uso de IA pelos alunos (E5B)": buscar_percentual_tic("E5B", escolas_ate_em),
    "Escolas com guia sobre uso de IA (E5A)": buscar_percentual_tic("E5A", escolas_ate_em),
})
print("\nP5 - TIC Educação, ensino médio (%)\n", preparo.round(1))
grafico = preparo.iloc[::-1].plot(kind="barh", xlim=(0, 100), figsize=(8, 3.4))  # invertido: o primeiro fica em cima
salvar_grafico(grafico, "TIC Educação: uso de IA pelos alunos x preparo de professores e escolas (%)", "p5_preparo")
