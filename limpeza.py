from io import BytesIO
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

PASTA_ORIGINAIS = Path("dados_originais")
PASTA_TRATADOS = Path("dados_tratados")
PASTA_TRATADOS.mkdir(exist_ok=True)
passos_limpeza = []


def registrar_passo(base, o_que_foi_feito, por_que, linhas_antes, linhas_depois):
    numero_passo = len(
        [passo for passo in passos_limpeza if passo["base"] == base]) + 1
    passos_limpeza.append({"base": base, "passo": numero_passo, "o_que_foi_feito": o_que_foi_feito,
                           "por_que": por_que, "linhas_antes": linhas_antes, "linhas_depois": linhas_depois})


def salvar_csv(tabela, nome_arquivo):
    tabela.to_csv(PASTA_TRATADOS /
                  f"{nome_arquivo}.csv", index=False, encoding="utf-8-sig")
    print(f"{nome_arquivo}.csv: {len(tabela)} linhas")


def formatar_numero(numero):  # 1234567 -> 1.234.567
    return f"{numero:,}".replace(",", ".")


def formatar_decimal(numero):  # 2.6 -> 2,6
    return f"{numero:.1f}".replace(".", ",")


def calcular_limites_iqr(coluna):
    primeiro_quartil, terceiro_quartil = coluna.quantile(
        0.25), coluna.quantile(0.75)
    intervalo = terceiro_quartil - primeiro_quartil
    return primeiro_quartil - 1.5 * intervalo, terceiro_quartil + 1.5 * intervalo


def ler_do_zip(nome_zip, nome_arquivo):
    with zipfile.ZipFile(PASTA_ORIGINAIS / nome_zip) as arquivo_zip:
        return BytesIO(arquivo_zip.read(nome_arquivo))


def ler_planilha_inep(nome, aba=0):
    # no zip do Inep a planilha fica numa pasta com o mesmo nome; os nomes das colunas estão na linha 10
    return pd.read_excel(ler_do_zip(f"{nome}.zip", f"{nome}/{nome}.xlsx"), sheet_name=aba, header=9, dtype=str)


# colunas do Ideb que se repetem para cada ano ({ano} é trocado pelo ano)
indicadores_ideb = {"VL_APROVACAO_{ano}_SI_4": "taxa_aprovacao", "VL_INDICADOR_REND_{ano}": "indicador_rendimento_P",
                    "VL_NOTA_MATEMATICA_{ano}": "nota_saeb_matematica",
                    "VL_NOTA_PORTUGUES_{ano}": "nota_saeb_portugues", "VL_NOTA_MEDIA_{ano}": "nota_media_padronizada_N",
                    "VL_OBSERVADO_{ano}": "ideb", "VL_PROJECAO_{ano}": "meta_ideb"}


# 1. Ideb 2025 - Brasil, regiões e estados (ensino médio)
base = "Ideb 2025 (Brasil, regiões e estados)"
partes = []
linhas_lidas = 0
planilhas_ideb = {
    "divulgacao_brasil_ideb_2025": "Brasil (EM)", "divulgacao_regioes_ufs_ideb_2025": "UF e Regiões (EM)"}
for nome, aba in planilhas_ideb.items():
    planilha = ler_planilha_inep(nome, aba)
    linhas_lidas += len(planilha)
    planilha = planilha.rename(
        columns={planilha.columns[0]: "local", planilha.columns[1]: "rede"})
    linha_rodape = list(planilha["local"].isna()).index(
        True)  # depois da primeira linha vazia só tem notas
    partes.append(planilha.iloc[:linha_rodape])
ideb_largo = pd.concat(partes, ignore_index=True)
registrar_passo(base, "Lemos as planilhas a partir da linha com os nomes das colunas e cortamos as notas do rodapé",
                "Título e notas não são dados", linhas_lidas, len(ideb_largo))

estados_por_regiao = {
    "Norte": {"Rondônia": "RO", "Acre": "AC", "Amazonas": "AM", "Roraima": "RR", "Pará": "PA", "Amapá": "AP",
              "Tocantins": "TO"},
    "Nordeste": {"Maranhão": "MA", "Piauí": "PI", "Ceará": "CE", "Rio Grande do Norte": "RN", "Paraíba": "PB",
                 "Pernambuco": "PE", "Alagoas": "AL", "Sergipe": "SE", "Bahia": "BA"},
    "Sudeste": {"Minas Gerais": "MG", "Espírito Santo": "ES", "Rio de Janeiro": "RJ", "São Paulo": "SP"},
    "Sul": {"Paraná": "PR", "Santa Catarina": "SC", "Rio Grande do Sul": "RS"},
    "Centro-Oeste": {"Mato Grosso do Sul": "MS", "Mato Grosso": "MT", "Goiás": "GO", "Distrito Federal": "DF"},
}
nomes_abreviados = {"R. G. do Norte": "Rio Grande do Norte", "R. G. do Sul": "Rio Grande do Sul",
                    "M. G. do Sul": "Mato Grosso do Sul"}

ideb_largo["local"] = ideb_largo["local"].str.strip().replace(nomes_abreviados)
ideb_largo["rede"] = ideb_largo["rede"].str.replace(
    r"\s*\(\d\)", "", regex=True).str.strip()  # "Total (4)" -> "Total"
ideb_largo["nivel"] = "UF"
ideb_largo.loc[ideb_largo["local"].isin(
    estados_por_regiao.keys()), "nivel"] = "Região"
ideb_largo.loc[ideb_largo["local"] == "Brasil", "nivel"] = "Brasil"
for regiao, estados in estados_por_regiao.items():
    ideb_largo.loc[ideb_largo["local"] == regiao, "regiao"] = regiao
    for estado, sigla in estados.items():
        ideb_largo.loc[ideb_largo["local"] == estado, "regiao"] = regiao
        ideb_largo.loc[ideb_largo["local"] == estado, "uf"] = sigla
registrar_passo(base, 'Tiramos as marcas de nota dos nomes das redes (ex.: "Total (4)") '
                "e separamos região e estado em colunas",
                'Sem isso "Total" e "Total (4)" viram redes diferentes e não dá para filtrar o Nordeste',
                len(ideb_largo), len(ideb_largo))

# a planilha tem uma coluna por ano; aqui fica uma linha por local, rede e ano
blocos = []
for ano in range(2005, 2026, 2):
    bloco = ideb_largo[["nivel", "regiao", "uf", "local", "rede"]].copy()
    bloco["ano"] = ano
    for coluna, indicador in indicadores_ideb.items():
        bloco[indicador] = ideb_largo.get(coluna.format(ano=ano), np.nan)
    blocos.append(bloco)
ideb = pd.concat(blocos, ignore_index=True)
registrar_passo(base, "Passamos de uma coluna por ano para uma linha por local, rede e ano (2005 a 2025)",
                "Facilita montar a série histórica", len(ideb_largo), len(ideb))

total_tracos = 0
for indicador in indicadores_ideb.values():
    total_tracos += int((ideb[indicador] == "-").sum())
    ideb[indicador] = pd.to_numeric(ideb[indicador].replace("-", np.nan))
registrar_passo(base, f'Trocamos os {total_tracos} "-" por vazio (Ideb e notas da rede privada em 2009)',
                "O Inep não calculou esses valores, então não preenchemos", len(ideb), len(ideb))

faixa_valida = {"taxa_aprovacao": 100, "indicador_rendimento_P": 1, "nota_saeb_matematica": 500,
                "nota_saeb_portugues": 500, "nota_media_padronizada_N": 10, "ideb": 10, "meta_ideb": 10}
fora_da_faixa = 0
for indicador, maximo in faixa_valida.items():
    fora_da_faixa += int(((ideb[indicador] < 0) |
                         (ideb[indicador] > maximo)).sum())
estados_2025 = ideb[(ideb["nivel"] == "UF") & (
    ideb["ano"] == 2025) & (ideb["rede"] == "Total")]
limite_inferior, limite_superior = calcular_limites_iqr(estados_2025["ideb"])
outliers = estados_2025[(estados_2025["ideb"] < limite_inferior) | (
    estados_2025["ideb"] > limite_superior)]
ideb["outlier_iqr"] = False
ideb.loc[outliers.index, "outlier_iqr"] = True
registrar_passo(base, f"Conferimos se os valores estão dentro da escala ({fora_da_faixa} fora) e procuramos outliers "
                f"no Ideb 2025 dos estados pelo IQR ({len(outliers)} casos)",
                "Para achar erro de leitura; nada foi apagado", len(ideb), len(ideb))
salvar_csv(ideb, "ideb_brasil_regioes_ufs")


# 2. Ideb 2025 - escolas de ensino médio
base = "Ideb 2025 (escolas)"
escolas_bruto = ler_planilha_inep("divulgacao_ensino_medio_escolas_2025")
escolas = escolas_bruto[escolas_bruto["REDE"].notna()]  # o rodapé não tem rede
escolas = escolas.drop(
    columns=[coluna for coluna in escolas.columns if coluna.startswith("Unnamed")])
registrar_passo(base, "Cortamos as 13 linhas de notas do rodapé e a coluna vazia do fim", "Não são escolas",
                len(escolas_bruto), len(escolas))

# códigos que o Inep usa quando a escola ficou sem valor
motivo_do_codigo = {"-": "Não calculado", "ND": "Não divulgado (participação insuficiente no Saeb)",
                    "ND*": "Não divulgado (código ND*)", "ND***": "Não divulgado (material extraviado)"}
contagem_codigos = []
for codigo in motivo_do_codigo:
    total = int((escolas.filter(like="VL_") == codigo).sum().sum())
    contagem_codigos.append(f'"{codigo}": {formatar_numero(total)}')

blocos = []
for ano in range(2017, 2026, 2):
    bloco = escolas[["SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
                     "ID_ESCOLA", "NO_ESCOLA", "REDE"]].copy()
    bloco["ano"] = ano
    bloco["situacao_ideb"] = escolas[f"VL_OBSERVADO_{ano}"].map(
        motivo_do_codigo).fillna("Calculado")
    for coluna, indicador in indicadores_ideb.items():
        if coluna.format(ano=ano) in escolas.columns:
            bloco[indicador] = escolas[coluna.format(ano=ano)]
    blocos.append(bloco)
ideb_escolas = pd.concat(blocos, ignore_index=True)
registrar_passo(base, "Passamos para uma linha por escola e ano (2017 a 2025)",
                "Deixa a série de cada escola em sequência", len(escolas), len(ideb_escolas))

for indicador in indicadores_ideb.values():
    if indicador in ideb_escolas.columns:
        ideb_escolas[indicador] = pd.to_numeric(
            ideb_escolas[indicador].replace(list(motivo_do_codigo), np.nan))
registrar_passo(base, f"Trocamos os códigos de ausência por vazio ({', '.join(contagem_codigos)}) "
                "e guardamos o motivo na coluna situacao_ideb",
                "O motivo explica por que a escola ficou sem Ideb", len(ideb_escolas), len(ideb_escolas))

escolas_2025 = ideb_escolas[(ideb_escolas["ano"] == 2025)
                            & ideb_escolas["ideb"].notna()]
limite_inferior, limite_superior = calcular_limites_iqr(escolas_2025["ideb"])
fora_do_intervalo = (ideb_escolas["ideb"] < limite_inferior) | (
    ideb_escolas["ideb"] > limite_superior)
ideb_escolas["outlier_iqr"] = (ideb_escolas["ano"] == 2025) & fora_do_intervalo
registrar_passo(base, f"Procuramos outliers no Ideb 2025 pelo IQR: {ideb_escolas['outlier_iqr'].sum()} escolas fora de "
                f"{formatar_decimal(limite_inferior)} a {formatar_decimal(limite_superior)}. "
                "Ficaram na base, marcadas na coluna outlier_iqr",
                "São resultados oficiais, não erros", len(ideb_escolas), len(ideb_escolas))
ideb_escolas = ideb_escolas.rename(columns={"SG_UF": "uf", "CO_MUNICIPIO": "cod_municipio", "NO_MUNICIPIO": "municipio",
                                            "ID_ESCOLA": "cod_escola", "NO_ESCOLA": "escola", "REDE": "rede"})
salvar_csv(ideb_escolas, "ideb_escolas")


# 3. Saeb 2023 - alunos da 3ª e 4ª série do ensino médio (recorte do arquivo TS_ALUNO_34EM.csv)
base = "Saeb 2023 (alunos)"
with zipfile.ZipFile(PASTA_ORIGINAIS / "saeb_2023_TS_ALUNO_34EM_recorte.zip") as arquivo_zip:
    with arquivo_zip.open("TS_ALUNO_34EM_recorte.csv") as arquivo_csv:
        saeb = pd.read_csv(arquivo_csv, sep=";", dtype=str, encoding="latin-1")
registrar_passo(base, "Lemos só as 17 colunas usadas, das 117 do arquivo", "O resto não entra em nenhuma métrica",
                len(saeb), len(saeb))

for coluna in ["PESO_ALUNO_LP", "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_MT", "PROFICIENCIA_MT_SAEB", "INSE_ALUNO"]:
    saeb[coluna] = pd.to_numeric(saeb[coluna])
linhas_antes = len(saeb)
saeb = saeb[(saeb["IN_PROFICIENCIA_MT"] == "1") | (
    saeb["IN_PROFICIENCIA_LP"] == "1")].copy()
registrar_passo(base, f"Tiramos {formatar_numero(linhas_antes - len(saeb))} alunos que faltaram ou ficaram sem nota "
                "nas duas provas", "Sem nota não dá para medir desempenho", linhas_antes, len(saeb))

# quem não fez uma das provas fica com essa nota vazia
saeb.loc[saeb["IN_PROFICIENCIA_MT"] != "1", "PROFICIENCIA_MT_SAEB"] = np.nan
saeb.loc[saeb["IN_PROFICIENCIA_LP"] != "1", "PROFICIENCIA_LP_SAEB"] = np.nan
sem_peso = int((saeb["PROFICIENCIA_MT_SAEB"].notna()
               & saeb["PESO_ALUNO_MT"].isna()).sum())
registrar_passo(base, f"Deixamos fora das médias {formatar_numero(sem_peso)} alunos com nota de Matemática "
                "mas sem peso",
                "As médias do Saeb são calculadas com peso", len(saeb), len(saeb))

# quando o aluno não tem INSE (IN_INSE = 0), o arquivo coloca "1" no nível, como se fosse Nível I
sem_inse = int(((saeb["IN_INSE"] == "0") & (
    saeb["NU_TIPO_NIVEL_INSE"] == "1")).sum())
saeb.loc[saeb["IN_INSE"] != "1", ["NU_TIPO_NIVEL_INSE", "INSE_ALUNO"]] = np.nan
registrar_passo(base, f"Trocamos por vazio o nível socioeconômico de {formatar_numero(sem_inse)} alunos sem INSE "
                'calculado, que o arquivo marcava como "Nível I"', "Senão o grupo mais pobre ficaria maior do que é",
                len(saeb), len(saeb))

invalidas = {}  # "*" e "." são respostas em branco ou inválidas
for pergunta in ["TX_RESP_Q12b", "TX_RESP_Q13b"]:
    invalidas[pergunta] = formatar_numero(
        int(saeb[pergunta].isin(["*", "."]).sum()))
    saeb[pergunta] = saeb[pergunta].replace({"*": np.nan, ".": np.nan})
registrar_passo(base, f'Trocamos por vazio as respostas "*" e "." nas perguntas de computador '
                f'({invalidas["TX_RESP_Q12b"]}) e Wi-Fi ({invalidas["TX_RESP_Q13b"]})',
                "Não dá para saber a resposta; esses alunos ficam fora só das contas com a pergunta",
                len(saeb), len(saeb))

# significado dos códigos, tirado do dicionário do Inep
codigo_para_uf = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA",
                  "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
                  "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
                  "51": "MT", "52": "GO", "53": "DF"}
saeb["uf"] = saeb["ID_UF"].map(codigo_para_uf)
saeb["regiao"] = saeb["ID_REGIAO"].map(
    {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"})
saeb["rede"] = saeb["IN_PUBLICA"].map({"1": "Pública", "0": "Privada"})
saeb["localizacao"] = saeb["ID_LOCALIZACAO"].map({"1": "Urbana", "2": "Rural"})
saeb["serie"] = saeb["ID_SERIE"].map(
    {"12": "EM tradicional", "13": "EM integrado"})
saeb["computador"] = saeb["TX_RESP_Q12b"].map(
    {"A": "Nenhum", "B": "1", "C": "2", "D": "3 ou mais"})
saeb["tem_computador"] = saeb["TX_RESP_Q12b"].map(
    {"A": "Não", "B": "Sim", "C": "Sim", "D": "Sim"})
saeb["wifi"] = saeb["TX_RESP_Q13b"].map({"A": "Não", "B": "Sim"})
codigo_para_nivel = {"1": "Nível I", "2": "Nível II", "3": "Nível III", "4": "Nível IV", "5": "Nível V",
                     "6": "Nível VI", "7": "Nível VII", "8": "Nível VIII"}
saeb["nivel_inse"] = saeb["NU_TIPO_NIVEL_INSE"].map(codigo_para_nivel)
registrar_passo(base, "Trocamos os códigos pelos nomes do dicionário do Inep (UF, região, rede, computador, Wi-Fi, "
                "nível INSE)", "Para a base ficar legível", len(saeb), len(saeb))

outliers = {}
for coluna in ["PROFICIENCIA_MT_SAEB", "PROFICIENCIA_LP_SAEB"]:
    limite_inferior, limite_superior = calcular_limites_iqr(saeb[coluna])
    outliers[coluna] = formatar_numero(
        int(((saeb[coluna] < limite_inferior) | (saeb[coluna] > limite_superior)).sum()))
limite_inferior, limite_superior = calcular_limites_iqr(saeb["PESO_ALUNO_MT"])
pesos_altos = formatar_numero(
    int((saeb["PESO_ALUNO_MT"] > limite_superior).sum()))
registrar_passo(base, f"Procuramos outliers pelo IQR: {outliers['PROFICIENCIA_MT_SAEB']} notas de Matemática, "
                f"{outliers['PROFICIENCIA_LP_SAEB']} de Português e {pesos_altos} pesos altos. Nada foi apagado",
                "As notas são calculadas pelo Inep e os pesos altos vêm da rede privada, que é amostral",
                len(saeb), len(saeb))

alunos = saeb[["regiao", "uf", "rede", "localizacao", "serie", "ID_ESCOLA", "PROFICIENCIA_MT_SAEB", "PESO_ALUNO_MT",
               "PROFICIENCIA_LP_SAEB", "PESO_ALUNO_LP", "INSE_ALUNO", "nivel_inse", "computador", "tem_computador",
               "wifi"]]
alunos = alunos.rename(columns={"ID_ESCOLA": "id_escola_mascarado", "PROFICIENCIA_MT_SAEB": "nota_mt",
                                "PESO_ALUNO_MT": "peso_mt", "PROFICIENCIA_LP_SAEB": "nota_lp",
                                "PESO_ALUNO_LP": "peso_lp", "INSE_ALUNO": "inse"})
alunos.to_csv(PASTA_TRATADOS / "saeb_2023_alunos.csv.gz",
              index=False, compression="gzip")  # compactado, é grande
print(f"saeb_2023_alunos.csv.gz: {len(alunos)} linhas")

# versão agregada: média ponderada = soma(nota x peso) / soma(peso), só com quem tem nota e peso
agrupar = alunos.fillna({"nivel_inse": "Sem resposta",
                        "tem_computador": "Sem resposta", "wifi": "Sem resposta"})
for materia in ["mt", "lp"]:
    agrupar[f"nota_x_peso_{materia}"] = agrupar[f"nota_{materia}"] * \
        agrupar[f"peso_{materia}"]
    agrupar[f"soma_peso_{materia}"] = agrupar[f"peso_{materia}"].where(
        agrupar[f"nota_{materia}"].notna())
grupos = agrupar.groupby(
    ["regiao", "uf", "rede", "nivel_inse", "tem_computador", "wifi"])
somas = grupos[["soma_peso_mt", "nota_x_peso_mt",
                "soma_peso_lp", "nota_x_peso_lp"]].sum()
saeb_agregado = pd.DataFrame({"alunos": grupos.size(), "soma_peso_mt": somas["soma_peso_mt"],
                              "nota_mt": somas["nota_x_peso_mt"] / somas["soma_peso_mt"],
                              "soma_peso_lp": somas["soma_peso_lp"],
                              "nota_lp": somas["nota_x_peso_lp"] / somas["soma_peso_lp"]}).reset_index()
registrar_passo(base, "Salvamos também uma versão agregada por UF, rede, nível INSE, computador e Wi-Fi, com a média "
                "ponderada e a soma dos pesos", "A base por aluno não cabe na planilha",
                len(alunos), len(saeb_agregado))
salvar_csv(saeb_agregado.round(3), "saeb_2023_agregado")


# 4. TIC Educação 2024 e 2025 - tabelas G6, H4D, H7, E5A e E5B
base = "TIC Educação 2024 e 2025"


def ler_tabela_tic(nome_zip, nome_planilha, nome_aba):
    # transforma a tabela da Cetic.br em lista: uma linha por recorte, item e resposta
    aba = openpyxl.load_workbook(ler_do_zip(
        nome_zip, nome_planilha), read_only=True)[nome_aba]
    aba.reset_dimensions()  # o tamanho gravado nesses arquivos vem errado
    linhas = list(aba.iter_rows(values_only=True))
    itens, respostas = linhas[2], linhas[3]
    registros = []
    linhas_da_tabela = 0
    for linha in linhas[4:]:
        if linha[0] is None or str(linha[0]).startswith("Fonte"):  # fim da tabela
            break
        linhas_da_tabela += 1
        for coluna in range(2, min(len(linha), len(respostas))):
            if respostas[coluna] is not None:
                registros.append({"indicador": nome_aba, "titulo": linhas[0][0], "publico": linhas[1][0],
                                  "recorte_tipo": linha[0], "recorte": linha[1],
                                  "item": " ".join(str(itens[coluna] or "").split()),
                                  "resposta": respostas[coluna], "valor": linha[coluna]})
    return pd.DataFrame(registros), linhas_da_tabela


partes = []
linhas_lidas = 0
tabelas_tic = [("Alunos", 2024, ["G6", "H4D"]), ("Professores",
                                                 2024, ["H7"]), ("Escolas", 2025, ["E5A", "E5B"])]
chave = ["indicador", "recorte_tipo", "recorte", "item", "resposta"]
for publico, ano, abas in tabelas_tic:
    nome = f"tic_educacao_{ano}_{publico.lower()}"
    for nome_aba in abas:
        # a margem de erro vem em outro arquivo, com a mesma estrutura da tabela de proporções
        proporcoes, linhas_da_tabela = ler_tabela_tic(f"{nome}_tabelas_xlsx_v1.0.zip",
                                                      f"{nome}_tabela_proporcao_v1.0.xlsx", nome_aba)
        margens, _ = ler_tabela_tic(f"{nome}_tabelas_xlsx_v1.0.zip",
                                    f"{nome}_tabela_margem_de_erro_v1.0.xlsx", nome_aba)
        linhas_lidas += linhas_da_tabela
        margens = margens.rename(columns={"valor": "margem_erro"})
        tabela = proporcoes.merge(
            margens[chave + ["margem_erro"]], on=chave, how="left")
        tabela["pesquisa"], tabela["publico_curto"] = f"TIC Educação {ano}", publico
        partes.append(tabela)
tic_educacao = pd.concat(partes, ignore_index=True)
registrar_passo(base, "Transformamos cada tabela em lista (uma linha por recorte, item e resposta) e juntamos com a "
                "margem de erro, que vem em outro arquivo",
                "As tabelas vêm prontas para leitura, com cabeçalho em duas linhas e recortes empilhados",
                linhas_lidas, len(tic_educacao))

total_tracos = int((tic_educacao["valor"] == "-").sum())
for coluna in ["valor", "margem_erro"]:
    tic_educacao.loc[tic_educacao[coluna] == "-", coluna] = np.nan
    tic_educacao[coluna] = pd.to_numeric(tic_educacao[coluna])
registrar_passo(base, f'Trocamos os {formatar_numero(total_tracos)} "-" por vazio',
                'O "-" quer dizer "não se aplica", não é zero', len(tic_educacao), len(tic_educacao))

# nas tabelas E5A e E5B o item só repete "Sim", então colocamos o nome da pergunta
nome_da_pergunta = {"E5A": "Escola possui guia de orientações sobre o uso de IA",
                    "E5B": "Escola permite que os alunos usem IA em atividades educacionais"}
for indicador, pergunta in nome_da_pergunta.items():
    tic_educacao.loc[tic_educacao["indicador"] == indicador, "item"] = pergunta
registrar_passo(base, 'Nas tabelas E5A e E5B colocamos o nome da pergunta no lugar do item, que só repetia "Sim"',
                "Para saber de que pergunta é cada valor", len(tic_educacao), len(tic_educacao))

fora_da_faixa = int(
    ((tic_educacao["valor"] < 0) | (tic_educacao["valor"] > 100)).sum())
registrar_passo(base, f"Conferimos se algum percentual ficou fora de 0 a 100 ({fora_da_faixa} casos)",
                "Para achar erro de leitura", len(tic_educacao), len(tic_educacao))
salvar_csv(tic_educacao[["pesquisa", "publico_curto", "indicador", "titulo", "publico", "recorte_tipo", "recorte",
                         "item", "resposta", "valor", "margem_erro"]], "tic_educacao")


# 5. TIC Kids Online Brasil 2025 - microdados
base = "TIC Kids Online Brasil 2025"
tic_kids = pd.read_csv(PASTA_ORIGINAIS / "tic_kids_online_brasil_2025_base_de_microdados_v1.0.csv", sep=";", dtype=str,
                       usecols=["QUEST", "ESC1", "IDADE_KIDS", "SEXO_KIDS", "COD_REGIAO_2", "CLASSE_2015_REC", "AREA",
                                "IDADE_INTERNET", "N4_A", "N4_B", "N4_C", "N4_D", "PESO"])
tic_kids["PESO"] = pd.to_numeric(tic_kids["PESO"].str.replace(",", "."))
registrar_passo(base, "Convertemos o peso, que vem como texto com vírgula, para número",
                "Os percentuais são calculados com peso", len(tic_kids), len(tic_kids))

linhas_antes = len(tic_kids)
tic_kids = tic_kids[tic_kids["ESC1"].isin(["10", "11", "12"])]
registrar_passo(base, "Ficamos só com os alunos do 1º ao 3º ano do ensino médio (ESC1 = 10, 11 e 12)",
                "O projeto é sobre o ensino médio", linhas_antes, len(tic_kids))

linhas_antes = len(tic_kids)
# quem não usou Internet tem 99 nas perguntas de IA
tic_kids = tic_kids[tic_kids["IDADE_INTERNET"] == "1"].copy()
registrar_passo(base, f"Tiramos {linhas_antes - len(tic_kids)} alunos que não usaram Internet nos últimos 3 meses "
                "(código 99 nas perguntas de IA)", "A Cetic.br só faz essas perguntas para quem usa Internet",
                linhas_antes, len(tic_kids))

perguntas_ia = {"N4_A": "Procurar informações", "N4_B": "Fazer pesquisas escolares ou estudar",
                "N4_C": "Conversar sobre problemas pessoais ou emoções",
                "N4_D": "Criar conteúdo (textos, imagens, vídeos ou códigos)"}
codigos_especiais = 0
for pergunta in perguntas_ia:
    codigos_especiais += int(tic_kids[pergunta].isin(["97", "98"]).sum())
    tic_kids[pergunta] = pd.to_numeric(
        tic_kids[pergunta]).replace({97: np.nan, 98: np.nan})
registrar_passo(base, 'Procuramos "não sabe" (97) e "não respondeu" (98) nas perguntas de IA para trocar por vazio '
                f"({codigos_especiais} casos)", "Não dá para saber a resposta", len(tic_kids), len(tic_kids))

tic_kids["serie"] = tic_kids["ESC1"].map(
    {"10": "1º ano EM", "11": "2º ano EM", "12": "3º ano EM"})
tic_kids["regiao"] = tic_kids["COD_REGIAO_2"].map({"1": "Sudeste", "2": "Nordeste", "3": "Sul", "4": "Norte",
                                                   "5": "Centro-Oeste"})
tic_kids["sexo"] = tic_kids["SEXO_KIDS"].map(
    {"1": "Masculino", "2": "Feminino"})
tic_kids["classe_social"] = tic_kids["CLASSE_2015_REC"].map(
    {"1": "AB", "2": "C", "3": "DE"})
tic_kids["area"] = tic_kids["AREA"].map({"1": "Urbana", "2": "Rural"})
tic_kids["usa_ia_alguma"] = tic_kids[list(perguntas_ia)].max(
    axis=1)  # 1 se usou IA para alguma finalidade
registrar_passo(base, "Trocamos os códigos pelos nomes do dicionário da Cetic.br", "Para a base ficar legível",
                len(tic_kids), len(tic_kids))

limite_inferior, limite_superior = calcular_limites_iqr(tic_kids["PESO"])
pesos_altos = int((tic_kids["PESO"] > limite_superior).sum())
registrar_passo(base, f"Procuramos outliers no peso pelo IQR ({pesos_altos} casos). Ficaram na base",
                "O peso é da própria pesquisa; cortar mudaria os percentuais", len(tic_kids), len(tic_kids))

tic_kids = tic_kids.rename(
    columns={"QUEST": "id_entrevistado", "PESO": "peso"})
colunas_aluno = ["id_entrevistado", "serie",
                 "regiao", "sexo", "classe_social", "area"]
salvar_csv(tic_kids[colunas_aluno + list(perguntas_ia) +
           ["usa_ia_alguma", "peso"]], "tic_kids_em")

partes = []  # uma linha por aluno e finalidade
for pergunta, finalidade in perguntas_ia.items():
    parte = tic_kids[colunas_aluno + ["peso"]].copy()
    parte["variavel"], parte["usou"], parte["finalidade"] = pergunta, tic_kids[pergunta], finalidade
    partes.append(parte)
salvar_csv(pd.concat(partes, ignore_index=True), "tic_kids_em_finalidades")


# 6. Pisa 2025 - compêndio da OCDE (resultados do Brasil por pergunta)
# os microdados por aluno dependem de um formulário da OCDE, então usamos o compêndio
base = "Pisa 2025 (compêndio)"
arquivos_pisa = {"Percentual de alunos (%)": "overall", "Nota média em Matemática": "math",
                 "Nota média em Leitura": "read"}
perguntas_pisa = {
    "ST001D01T": "Ano escolar do aluno", "ST004D01T": "Sexo do aluno",
    "ST438Q01DA": "Usa chatbot de IA nas tarefas escolares para resumir um texto que precisava ler",
    "ST438Q02DA": "Usa chatbot de IA nas tarefas escolares para fazer uma pesquisa inicial sobre um tema novo",
    "ST438Q03DA": "Usa chatbot de IA nas tarefas escolares para rascunhar textos de trabalhos escritos",
    "ST438Q04DA": "Usa chatbot de IA nas tarefas escolares para ajudar a aprender",
    "ST437Q01DA": "Recursos digitais me ajudam a aprender coisas complexas",
    "ST437Q02DA": "Recursos digitais deixam o conteúdo mais interessante",
    "IC173Q01JA": "Frequência de uso de recursos digitais nas aulas de Língua Portuguesa",
    "IC173Q02JA": "Frequência de uso de recursos digitais nas aulas de Matemática",
}
traducao = {
    "Never or almost never": "Nunca ou quase nunca", "About once or twice a year": "1 ou 2 vezes por ano",
    "About once or twice a month": "1 ou 2 vezes por mês", "About once or twice a week": "1 ou 2 vezes por semana",
    "Every day or almost every day": "Todo dia ou quase todo dia", "no response": "Sem resposta",
    "Strongly disagree": "Discorda totalmente", "Disagree": "Discorda", "Agree": "Concorda",
    "Strongly Agree": "Concorda totalmente", "In less than half of the lessons": "Em menos da metade das aulas",
    "In about half of the lessons": "Em cerca de metade das aulas",
    "In more than half of the lessons": "Em mais da metade das aulas",
    "In every or almost every lesson": "Em todas ou quase todas as aulas",
    "I do not have this subject": "Não tem a disciplina", "Female": "Feminino", "Male": "Masculino",
    "Not applicable / missing": "Pergunta não aplicada", "7": "7º ano (EF)", "8": "8º ano (EF)", "9": "9º ano (EF)",
    "10": "10º ano (1ª série EM)", "11": "11º ano (2ª série EM)", "12": "12º ano (3ª série EM)", "13": "13º ano",
}

registros = []
for medida, arquivo in arquivos_pisa.items():
    planilha = openpyxl.load_workbook(PASTA_ORIGINAIS / "pisa_2025_compendio" /
                                      f"pisa2025_ms_bkg_stu_{arquivo}_compendium.xlsx", read_only=True)
    for variavel in perguntas_pisa:
        aba = planilha[variavel]
        aba.reset_dimensions()
        linhas = list(aba.iter_rows(values_only=True))
        cabecalho = linhas[1]
        for linha in linhas:
            if linha and linha[0] == "Brazil":
                linha_brasil = linha
                break
        # coluna 2: alunos que não receberam a pergunta; da coluna 4 em diante vêm pares (valor, erro padrão)
        registros.append({"variavel": variavel, "medida": medida, "categoria": "Not applicable / missing",
                          "valor": linha_brasil[2], "erro_padrao": None})
        for coluna in range(4, len(cabecalho), 2):
            if cabecalho[coluna]:
                registros.append({"variavel": variavel, "medida": medida, "categoria": str(cabecalho[coluna]),
                                  "valor": linha_brasil[coluna], "erro_padrao": linha_brasil[coluna + 1]})
pisa = pd.DataFrame(registros)
registrar_passo(base, "Pegamos só a linha do Brasil em cada aba (10 perguntas, 3 arquivos) e juntamos tudo numa tabela",
                "Cada aba traz uma pergunta com todos os países", len(arquivos_pisa) * len(perguntas_pisa), len(pisa))

total_tracos = int((pisa["valor"] == "—").sum() +
                   (pisa["erro_padrao"] == "—").sum())
for coluna in ["valor", "erro_padrao"]:
    pisa.loc[pisa[coluna] == "—", coluna] = np.nan
    pisa[coluna] = pd.to_numeric(pisa[coluna])
registrar_passo(base, f'Trocamos os {total_tracos} "—" por vazio',
                "A OCDE não publica o valor quando há poucos alunos na resposta", len(pisa), len(pisa))

pisa["categoria_pt"] = pisa["categoria"].map(
    traducao).fillna(pisa["categoria"])
pisa["pergunta"] = pisa["variavel"].map(perguntas_pisa)
registrar_passo(base, "Traduzimos perguntas e respostas para o português, mantendo o código da OCDE",
                "Para a base ficar legível", len(pisa), len(pisa))

sem_resposta = pisa[(pisa["categoria"] == "no response") & (pisa["medida"] == "Percentual de alunos (%)")
                    & pisa["variavel"].str.startswith("ST438")]["valor"]
menor, maior = formatar_decimal(
    sem_resposta.min()), formatar_decimal(sem_resposta.max())
registrar_passo(base, f"Mantivemos os alunos sem resposta como uma categoria ({menor}% a {maior}% nas perguntas de IA)",
                "Esse grupo tem nota bem menor; tirar deixaria a média dos outros maior do que é", len(pisa), len(pisa))

maximo = pisa["medida"].map({"Percentual de alunos (%)": 100, "Nota média em Matemática": 1000,
                             "Nota média em Leitura": 1000})
fora_da_faixa = int(((pisa["valor"] < 0) | (pisa["valor"] > maximo)).sum())
registrar_passo(base, f"Conferimos se percentuais e notas estão dentro da escala ({fora_da_faixa} fora)",
                "Para achar erro de leitura", len(pisa), len(pisa))
salvar_csv(pisa[["variavel", "pergunta", "medida", "categoria", "categoria_pt", "valor", "erro_padrao"]],
           "pisa_brasil_compendio")


# Registro de todos os passos da limpeza
salvar_csv(pd.DataFrame(passos_limpeza), "registro_limpeza")
