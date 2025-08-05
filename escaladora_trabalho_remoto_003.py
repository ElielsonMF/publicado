import streamlit as st
import pandas as pd
import math


# --- FUNÇÃO DE CÁLCULO (Lógica principal - sem alterações) ---
def processar_dados_e_gerar_relatorio(nome_setor, dias_uteis, dados_equipe, limites_por_cargo):
    """
    Processa os dados inseridos no front-end e retorna os resultados
    para exibição no relatório.
    """
    total_servidores = len(dados_equipe)
    servidores_disponiveis = [s for s in dados_equipe if s["status"] == "Disponível"]
    num_servidores_disponiveis = len(servidores_disponiveis)

    limite_base = math.ceil(total_servidores * 0.5)
    limite_efetivo_diario = min(int(limite_base), num_servidores_disponiveis)

    dias_nao_uteis = 5 - len(dias_uteis)
    deducao_feriado = 0
    if 1 <= dias_nao_uteis <= 2:
        deducao_feriado = 1
    elif dias_nao_uteis >= 3:
        deducao_feriado = 2

    limites_individuais = {}
    for servidor in servidores_disponiveis:
        limite_base_cargo = limites_por_cargo.get(servidor["cargo"], 0)
        limite_final = max(0, limite_base_cargo - deducao_feriado)
        limites_individuais[servidor["nome"]] = limite_final

    escala_semanal = {dia: [] for dia in dias_uteis}
    dias_remotos_restantes = limites_individuais.copy()

    for dia in dias_uteis:
        for servidor in servidores_disponiveis:
            nome_servidor = servidor["nome"]
            if dias_remotos_restantes.get(nome_servidor, 0) > 0 and len(escala_semanal[dia]) < limite_efetivo_diario:
                escala_semanal[dia].append(nome_servidor)
                dias_remotos_restantes[nome_servidor] -= 1

    return {
        "nome_setor": nome_setor,
        "total_servidores": total_servidores,
        "num_servidores_disponiveis": num_servidores_disponiveis,
        "limite_efetivo_diario": limite_efetivo_diario,
        "dados_equipe": dados_equipe,
        "limites_individuais": limites_individuais,
        "escala_semanal": escala_semanal
    }


# --- NOVA FUNÇÃO PARA CRIAR A PLANILHA ---
def criar_dataframe_para_csv(relatorio):
    """
    Transforma os dados do relatório em uma tabela (DataFrame) do pandas
    pronta para ser exportada como CSV.
    """
    servidores = relatorio['dados_equipe']
    escala = relatorio['escala_semanal']
    dias_uteis = list(escala.keys())

    dados_planilha = []

    for servidor in servidores:
        nome_servidor = servidor['nome']
        linha_servidor = {'Servidor': nome_servidor}

        if servidor['status'] == 'Disponível':
            for dia in dias_uteis:
                if nome_servidor in escala.get(dia, []):
                    linha_servidor[dia] = 'Teletrabalho'
                else:
                    linha_servidor[dia] = 'Presencial'
        else:  # Servidor está afastado
            for dia in dias_uteis:
                linha_servidor[dia] = servidor['status']

        dados_planilha.append(linha_servidor)

    df = pd.DataFrame(dados_planilha)
    return df


# --- INTERFACE DA APLICAÇÃO WEB ---

st.set_page_config(
    page_title="Gerador de Escala Híbrida",
    page_icon="📅",
    layout="centered"
)

st.title("📅 Gerador de Escala de Trabalho Híbrido")
st.markdown("Preencha os dados da sua equipe na barra lateral à esquerda para gerar o relatório.")

CARGOS_E_LIMITES = {
    "Não ocupante de CC/FC": 3, "FC": 3, "Assessor CC1-CC4": 3, "Chefe CC1-CC3": 3,
    "Assessor CC5-CC7": 2, "Chefe CC4-CC7": 2,
    "Teletrabalho (condições especiais Art. 16)": 5
}
LISTA_DE_CARGOS = list(CARGOS_E_LIMITES.keys())

with st.sidebar:
    st.header("⚙️ Insira os Dados da Equipe")

    nome_setor_input = st.text_input("Nome do Setor", "SELOG")
    dias_input = st.text_input("Dias úteis da semana (separados por vírgula)", "Seg,Ter,Qua,Qui,Sex")
    num_servidores = st.number_input("Número total de servidores na equipe", min_value=1, value=3, step=1)

    dados_equipe_input = []

    for i in range(num_servidores):
        with st.expander(f"👤 Servidor {i + 1}", expanded=i < 3):
            nome = st.text_input(f"Nome do Servidor {i + 1}", key=f"nome_{i}")
            cargo = st.selectbox(f"Cargo do Servidor {i + 1}", options=LISTA_DE_CARGOS, key=f"cargo_{i}")
            status = st.selectbox(f"Status do Servidor {i + 1}", options=["Disponível", "Afastado"], key=f"status_{i}")

            motivo_afastamento = ""
            if status == "Afastado":
                motivo_afastamento = st.text_input("Motivo do afastamento", key=f"motivo_{i}")
                status_final = f"Afastado (Motivo: {motivo_afastamento})"
            else:
                status_final = "Disponível"

            dados_equipe_input.append({"nome": nome, "cargo": cargo, "status": status_final})

    submit_button = st.button("Gerar Relatório de Escala")

if submit_button:
    if not all(s['nome'] for s in dados_equipe_input):
        st.error("Erro: Todos os servidores devem ter um nome.")
    else:
        dias_uteis_lista = [dia.strip() for dia in dias_input.split(',')]

        CARGOS_E_LIMITES["Teletrabalho (condições especiais Art. 16)"] = len(dias_uteis_lista)

        relatorio = processar_dados_e_gerar_relatorio(
            nome_setor_input,
            dias_uteis_lista,
            dados_equipe_input,
            CARGOS_E_LIMITES
        )

        st.success("Relatório gerado com sucesso!")

        st.markdown(f"""
        ---
        ### Relatório de Gestão de Trabalho Não Presencial

        **Setor:** {relatorio['nome_setor']}  
        **Total de Servidores na Lotação:** {relatorio['total_servidores']}  
        **Servidores Disponíveis nesta Semana:** {relatorio['num_servidores_disponiveis']}  
        **Limite Diário de Servidores em Teletrabalho:** {relatorio['limite_efetivo_diario']}
        """)

        st.subheader("1. Resumo Individual da Equipe")
        for servidor in relatorio['dados_equipe']:
            if servidor["status"] == "Disponível":
                limite = relatorio['limites_individuais'].get(servidor["nome"], 0)
                st.markdown(f"- **{servidor['nome']}**: Pode trabalhar remotamente até **{limite}** dias nesta semana.")
            else:
                st.markdown(f"- **{servidor['nome']}**: {servidor['status']}")

        st.subheader("2. Sugestão de Escala Semanal")
        st.markdown("Baseado nos limites, uma possível escala é:")
        for dia, nomes in relatorio['escala_semanal'].items():
            nomes_str = ", ".join(nomes) if nomes else "Ninguém"
            st.markdown(f"- **{dia}:** {nomes_str}")

        # --- SEÇÃO DE EXPORTAÇÃO ---
        st.markdown("---")
        st.subheader("📥 Exportar Escala")

        # Cria o DataFrame para a planilha
        df_escala = criar_dataframe_para_csv(relatorio)

        # Mostra uma prévia da tabela na tela
        st.write("Prévia da planilha a ser exportada:")
        st.dataframe(df_escala)

        # Converte o DataFrame para CSV em memória
        csv = df_escala.to_csv(index=False).encode('utf-8')

        # Cria o botão de download
        st.download_button(
            label="Baixar escala em formato CSV",
            data=csv,
            file_name=f"escala_{nome_setor_input.lower()}.csv",
            mime="text/csv",
        )