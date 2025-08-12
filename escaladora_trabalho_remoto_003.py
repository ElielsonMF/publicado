import streamlit as st
import pandas as pd
import math

# --- INTERFACE DA APLICAÇÃO WEB ---

st.set_page_config(
    page_title="Gerador de Escala Híbrida",
    page_icon="📅",
    layout="centered"
)

# --- INSERÇÃO DA LOGO ---
# O arquivo "inovadoria_fundo escuro 1b.png" deve estar na mesma pasta que este script.
try:
    st.image("inovadoria_fundo escuro 1b.png", width=300)  # Você pode ajustar a largura (width)
except FileNotFoundError:
    st.warning("Logo 'inovadoria_fundo escuro 1b.png' não encontrada. Verifique o nome e o local do arquivo.")

st.title("📅 Gerador de Escala de Trabalho Híbrido")
st.markdown("Preencha os dados da sua equipe na barra lateral à esquerda para gerar o relatório.")


# --- FUNÇÃO DE CÁLCULO ---
def processar_dados_e_gerar_relatorio(nome_setor, dias_uteis, dados_equipe, limites_por_cargo):
    """
    Processa os dados inseridos no front-end e retorna os resultados
    para exibição no relatório.
    """
    total_servidores_lotacao = len(dados_equipe)
    servidores_disponiveis = [s for s in dados_equipe if s["status"] == "Disponível"]
    num_servidores_disponiveis = len(servidores_disponiveis)

    # --- LÓGICA ATUALIZADA CONFORME ART. 12 E 16 DA PORTARIA ---
    # 1. Separa os servidores em Teletrabalho (Art. 16) dos servidores em Regime Híbrido
    servidores_teletrabalho = [s for s in servidores_disponiveis if s.get("regime_teletrabalho")]
    servidores_hibrido = [s for s in servidores_disponiveis if not s.get("regime_teletrabalho")]

    # 2. Calcula o limite diário de 50% sobre a lotação efetiva da unidade.
    # Este limite se aplica APENAS aos servidores do regime HÍBRIDO.
    limite_diario_hibrido = math.ceil(total_servidores_lotacao * 0.5)

    # O número de servidores em regime híbrido que podem ficar remotos por dia é o menor valor entre o limite de 50% e o total de servidores híbridos disponíveis.
    limite_efetivo_diario_hibrido = min(limite_diario_hibrido, len(servidores_hibrido))

    dias_nao_uteis = len(["Seg", "Ter", "Qua", "Qui", "Sex"]) - len(dias_uteis)
    deducao_feriado = 0
    if 1 <= dias_nao_uteis <= 2:
        deducao_feriado = 1
    elif dias_nao_uteis >= 3:
        deducao_feriado = 2

    limites_individuais = {}
    # Calcula limites para servidores do regime HÍBRIDO
    for servidor in servidores_hibrido:
        limite_base_cargo = limites_por_cargo.get(servidor["cargo"], 0)
        limite_final = max(0, limite_base_cargo - deducao_feriado)
        limites_individuais[servidor["nome"]] = limite_final

    # Servidores em Teletrabalho têm limite igual ao número de dias úteis
    for servidor in servidores_teletrabalho:
        limites_individuais[servidor["nome"]] = len(dias_uteis)

    # --- MONTAGEM DA ESCALA ---
    escala_semanal = {dia: [] for dia in dias_uteis}

    # 3. Adiciona PRIMEIRO todos os servidores de Teletrabalho em TODOS os dias
    for dia in dias_uteis:
        for servidor in servidores_teletrabalho:
            escala_semanal[dia].append(servidor["nome"])

    # 4. Distribui os servidores do regime HÍBRIDO nos dias restantes, respeitando o limite
    dias_remotos_restantes_hibrido = {s['nome']: limites_individuais[s['nome']] for s in servidores_hibrido}
    servidores_hibrido_ordenados = sorted(servidores_hibrido,
                                          key=lambda s: dias_remotos_restantes_hibrido.get(s['nome'], 0), reverse=True)

    for dia in dias_uteis:
        # O número de vagas para híbridos é o limite de 50% MENOS os que já estão em teletrabalho (que é 0, pois eles não contam)
        # No entanto, a lógica é que o total de híbridos não pode passar do limite_diario_hibrido.
        for servidor in servidores_hibrido_ordenados:
            nome_servidor = servidor["nome"]
            # Verifica se o servidor ainda tem dias e se o número de HÍBRIDOS remotos no dia é menor que o limite
            if dias_remotos_restantes_hibrido.get(nome_servidor, 0) > 0 and len([s for s in escala_semanal[dia] if
                                                                                 s not in [st['nome'] for st in
                                                                                           servidores_teletrabalho]]) < limite_diario_hibrido:
                escala_semanal[dia].append(nome_servidor)
                dias_remotos_restantes_hibrido[nome_servidor] -= 1

    return {
        "nome_setor": nome_setor,
        "total_servidores": total_servidores_lotacao,
        "num_servidores_disponiveis": num_servidores_disponiveis,
        "limite_efetivo_diario": f"{limite_diario_hibrido} (para regime híbrido)",  # Exibição mais clara
        "dados_equipe": dados_equipe,
        "limites_individuais": limites_individuais,
        "escala_semanal": escala_semanal
    }


# --- FUNÇÃO PARA CRIAR A PLANILHA ---
def criar_dataframe_para_csv(relatorio):
    """
    Transforma os dados do relatório em uma tabela (DataFrame) do pandas
    pronta para ser exportada como CSV.
    """
    servidores = relatorio['dados_equipe']
    escala = relatorio['escala_semanal']
    dias_uteis = sorted(list(escala.keys()), key=["Seg", "Ter", "Qua", "Qui", "Sex"].index)

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
    colunas = ['Servidor'] + dias_uteis
    df = df[colunas]
    return df


# --- BARRA LATERAL PARA ENTRADA DE DADOS ---

CARGOS_E_LIMITES = {
    "Não ocupante de CC/FC": 3, "FC": 3, "Assessor CC1-CC4": 3, "Chefe CC1-CC3": 3,
    "Assessor CC5-CC7": 2, "Chefe CC4-CC7": 2,
}

with st.sidebar:
    st.header("⚙️ Insira os Dados da Equipe")

    nome_setor_input = st.text_input("Nome do Setor", "SELOG")

    opcoes_dias = ["Seg", "Ter", "Qua", "Qui", "Sex"]
    dias_uteis_lista = st.multiselect(
        "Selecione os dias úteis da semana",
        options=opcoes_dias,
        default=opcoes_dias
    )

    num_servidores = st.number_input("Número total de servidores na equipe", min_value=1, value=3, step=1)

    dados_equipe_input = []

    for i in range(num_servidores):
        with st.expander(f"👤 Servidor {i + 1}", expanded=i < 3):
            nome = st.text_input(f"Nome do Servidor {i + 1}", key=f"nome_{i}")
            cargo = st.selectbox(f"Cargo do Servidor {i + 1}", options=list(CARGOS_E_LIMITES.keys()), key=f"cargo_{i}")
            status = st.selectbox(f"Status do Servidor {i + 1}", options=["Disponível", "Afastado"], key=f"status_{i}")

            # --- CHECKBOX ATUALIZADO CONFORME PORTARIA ---
            regime_teletrabalho_input = st.checkbox(
                "Regime de Teletrabalho (Art. 16)",
                key=f"teletrabalho_{i}",
                help="Marque para servidores com condições especiais (PCD, gestantes, etc.) que não entram no limite de 50%."
            )

            motivo_afastamento = ""
            if status == "Afastado":
                motivo_afastamento = st.text_input("Motivo do afastamento", key=f"motivo_{i}")
                status_final = f"Afastado ({motivo_afastamento})"
            else:
                status_final = "Disponível"

            dados_equipe_input.append({
                "nome": nome,
                "cargo": cargo,
                "status": status_final,
                "regime_teletrabalho": regime_teletrabalho_input
            })

    submit_button = st.button("Gerar Relatório de Escala")

# --- LÓGICA PRINCIPAL E EXIBIÇÃO DO RELATÓRIO ---

if submit_button:
    if not all(s['nome'] for s in dados_equipe_input):
        st.error("Erro: Todos os servidores devem ter um nome.")
    elif not dias_uteis_lista:
        st.error("Erro: Selecione pelo menos um dia útil da semana.")
    else:
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
        **Limite Diário de Servidores em Regime Híbrido:** {relatorio['limite_efetivo_diario']}
        """)

        st.subheader("1. Resumo Individual da Equipe")
        for servidor in sorted(relatorio['dados_equipe'], key=lambda x: x['nome']):
            if servidor["status"] == "Disponível":
                limite = relatorio['limites_individuais'].get(servidor["nome"], 0)
                nota_especial = "**(Regime de Teletrabalho - Art. 16)**" if servidor.get("regime_teletrabalho") else ""
                st.markdown(
                    f"- **{servidor['nome']}**: Limite de **{limite}** dias remotos nesta semana. {nota_especial}")
            else:
                st.markdown(f"- **{servidor['nome']}**: {servidor['status']}")

        st.subheader("2. Sugestão de Escala Semanal")
        st.markdown("Baseado nos limites, uma possível escala é:")
        for dia in sorted(relatorio['escala_semanal'].keys(), key=opcoes_dias.index):
            nomes = relatorio['escala_semanal'][dia]
            nomes_str = ", ".join(sorted(nomes)) if nomes else "Ninguém"
            st.markdown(f"- **{dia}:** {nomes_str}")

        # --- SEÇÃO DE EXPORTAÇÃO ---
        st.markdown("---")
        st.subheader("📥 Exportar Escala")

        df_escala = criar_dataframe_para_csv(relatorio)

        st.write("Prévia da planilha a ser exportada:")
        st.dataframe(df_escala)

        csv = df_escala.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="Baixar escala em formato CSV",
            data=csv,
            file_name=f"escala_{nome_setor_input.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )
