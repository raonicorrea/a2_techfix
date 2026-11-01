"""Painel de Gerenciamento - Assistência Técnica de Computadores.

Painel Streamlit para o gerente administrar clientes e ordens de serviço no Supabase.
Credenciais: .streamlit/secrets.toml ou variáveis de ambiente / arquivo .env
(SUPABASE_URL e SUPABASE_KEY). Nunca escreva as chaves no código.

Executar:  streamlit run app_streamlit.py
"""

import os
import re

import pandas as pd
import streamlit as st
from supabase import create_client

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

STATUS_OPCOES = ["Aberto", "Em análise", "Aguardando peça", "Em andamento", "Concluído", "Entregue", "Cancelado"]
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")

st.set_page_config(page_title="Painel de Ordens de Serviço", page_icon="🛠️", layout="wide")


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------
def ler_credencial(nome):
    """Lê do secrets.toml; se não existir, cai para variável de ambiente/.env."""
    try:
        if nome in st.secrets:
            return st.secrets[nome]
    except Exception:  # secrets.toml ausente
        pass
    return os.environ.get(nome)


@st.cache_resource
def conectar():
    url, key = ler_credencial("SUPABASE_URL"), ler_credencial("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Credenciais não encontradas. Defina SUPABASE_URL e SUPABASE_KEY "
            "em .streamlit/secrets.toml ou no arquivo .env."
        )
    return create_client(url, key)


try:
    supabase = conectar()
except Exception as exc:
    st.error(f"Não foi possível conectar ao Supabase. {exc}")
    st.stop()


# ---------------------------------------------------------------------------
# Acesso a dados
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    """Retorna (clientes, ordens) como DataFrames; ordens já vêm com os dados do cliente."""
    clientes = pd.DataFrame(
        supabase.table("clientes").select("*").order("nome").execute().data,
        columns=["id", "nome", "endereco", "email", "celular_whatsapp", "data_cadastro"],
    )
    ordens = pd.DataFrame(
        supabase.table("ordens_servico").select("*").order("id", desc=True).execute().data,
        columns=["id", "cliente_id", "modelo_computador", "problema_relatado", "status", "data_abertura"],
    )
    ordens = ordens.merge(
        clientes.rename(columns={"id": "cliente_id"}), on="cliente_id", how="left"
    )
    return clientes, ordens


def recarregar():
    carregar_dados.clear()
    st.rerun()


def executar(operacao, sucesso):
    """Executa uma operação no banco com mensagem amigável; retorna True se deu certo."""
    try:
        operacao()
    except Exception as exc:
        msg = str(exc)
        if "23505" in msg or "duplicate key" in msg:
            st.error("Já existe um registro com esse valor (ex.: e-mail já cadastrado).")
        elif "23503" in msg or "foreign key" in msg:
            st.error("Este registro está vinculado a outros dados e não pode ser removido.")
        elif "42501" in msg or "row-level security" in msg:
            st.error("Sem permissão para esta operação no banco (verifique as policies de RLS).")
        else:
            st.error(f"Ocorreu um erro ao acessar o banco de dados: {msg}")
        return False
    st.session_state["flash"] = sucesso
    return True


def validar_cliente(nome, endereco, email, celular):
    erros = []
    for rotulo, valor in {"Nome": nome, "Endereço": endereco, "E-mail": email, "Celular/WhatsApp": celular}.items():
        if not valor.strip():
            erros.append(f"O campo {rotulo} é obrigatório.")
    if email.strip() and not EMAIL_RE.match(email.strip()):
        erros.append("E-mail com formato inválido.")
    if celular.strip() and not celular.strip().isdigit():
        erros.append("Celular/WhatsApp deve conter apenas números.")
    return erros


def rotulo_os(linha):
    return f"OS {linha.id} — {linha.nome or 'cliente removido'} — {linha.modelo_computador} ({linha.status})"


def rotulo_cliente(linha):
    return f"{linha.nome} — {linha.email}"


try:
    clientes, ordens = carregar_dados()
except Exception as exc:
    st.error(f"Não foi possível carregar os dados do Supabase: {exc}")
    st.stop()

# ---------------------------------------------------------------------------
# Cabeçalho e filtros (barra lateral)
# ---------------------------------------------------------------------------
st.title("🛠️ Painel de Gerenciamento de Ordens de Serviço")
if msg := st.session_state.pop("flash", None):
    st.success(msg)

# Mantém a ordem do fluxo e acrescenta status que existam no banco mas não estejam na lista
status_existentes = STATUS_OPCOES + sorted(set(ordens["status"].dropna()) - set(STATUS_OPCOES))

with st.sidebar:
    st.header("🔎 Filtros")
    f_nome = st.text_input("Nome do cliente", placeholder="Parte do nome")
    f_email = st.text_input("E-mail", placeholder="Parte do e-mail")
    f_status = st.multiselect("Status", status_existentes, placeholder="Todos")
    if st.button("🔄 Atualizar dados", width="stretch"):
        recarregar()

filtradas = ordens
if f_nome:
    filtradas = filtradas[filtradas["nome"].fillna("").str.contains(f_nome, case=False, regex=False)]
if f_email:
    filtradas = filtradas[filtradas["email"].fillna("").str.contains(f_email, case=False, regex=False)]
if f_status:
    filtradas = filtradas[filtradas["status"].isin(f_status)]

aba_consultar, aba_cadastrar, aba_editar, aba_indicadores = st.tabs(
    ["📋 Consultar", "➕ Cadastrar", "✏️ Editar/Excluir", "📊 Indicadores"]
)

# ---------------------------------------------------------------------------
# Consultar
# ---------------------------------------------------------------------------
with aba_consultar:
    st.subheader(f"Ordens de serviço ({len(filtradas)} de {len(ordens)})")
    tabela = filtradas[
        ["id", "status", "nome", "email", "celular_whatsapp", "endereco",
         "modelo_computador", "problema_relatado", "data_abertura"]
    ].rename(columns={
        "id": "OS", "status": "Status", "nome": "Cliente", "email": "E-mail",
        "celular_whatsapp": "Celular/WhatsApp", "endereco": "Endereço",
        "modelo_computador": "Modelo", "problema_relatado": "Problema",
        "data_abertura": "Abertura",
    })
    st.dataframe(tabela, width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Exportar dados filtrados (CSV)",
        data=tabela.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="ordens_servico.csv",
        mime="text/csv",
        disabled=tabela.empty,
    )

# ---------------------------------------------------------------------------
# Cadastrar
# ---------------------------------------------------------------------------
with aba_cadastrar:
    st.subheader("Nova ordem de serviço")
    tipo = st.radio("Cliente", ["Cliente já cadastrado", "Novo cliente"], horizontal=True)

    with st.form("form_nova_os", clear_on_submit=True):
        if tipo == "Cliente já cadastrado":
            if clientes.empty:
                st.info("Nenhum cliente cadastrado ainda. Escolha \"Novo cliente\".")
                cliente_sel = None
            else:
                cliente_sel = st.selectbox(
                    "Selecione o cliente", list(clientes.itertuples(index=False)), format_func=rotulo_cliente
                )
        else:
            c1, c2 = st.columns(2)
            novo_nome = c1.text_input("Nome do Cliente", placeholder="Ex.: Maria da Silva")
            novo_email = c2.text_input("E-mail", placeholder="Ex.: maria@email.com")
            novo_end = c1.text_input("Endereço", placeholder="Ex.: Rua das Flores, 123 - Centro")
            novo_cel = c2.text_input("Celular/WhatsApp", placeholder="Somente números. Ex.: 11987654321")

        modelo = st.text_input("Modelo do Computador", placeholder="Ex.: Dell Inspiron 15 3520")
        problema = st.text_area("Problema Apresentado", placeholder="Descreva o defeito relatado")
        status_ini = st.selectbox("Status inicial", STATUS_OPCOES, index=0)
        enviar = st.form_submit_button("Cadastrar OS", type="primary")

    if enviar:
        erros = []
        if not modelo.strip():
            erros.append("O campo Modelo do Computador é obrigatório.")
        if not problema.strip():
            erros.append("O campo Problema Apresentado é obrigatório.")
        if tipo == "Novo cliente":
            erros += validar_cliente(novo_nome, novo_end, novo_email, novo_cel)
        elif cliente_sel is None:
            erros.append("Selecione um cliente.")

        if erros:
            for e in erros:
                st.warning(e)
        else:
            resultado = {}

            def inserir_os():
                if tipo == "Novo cliente":
                    email = novo_email.strip().lower()
                    existente = supabase.table("clientes").select("id").eq("email", email).limit(1).execute()
                    if existente.data:
                        cliente_id = existente.data[0]["id"]
                    else:
                        cliente_id = supabase.table("clientes").insert({
                            "nome": novo_nome.strip(),
                            "endereco": novo_end.strip(),
                            "email": email,
                            "celular_whatsapp": novo_cel.strip(),
                        }).execute().data[0]["id"]
                else:
                    cliente_id = int(cliente_sel.id)
                resultado["os"] = supabase.table("ordens_servico").insert({
                    "cliente_id": cliente_id,
                    "modelo_computador": modelo.strip(),
                    "problema_relatado": problema.strip(),
                    "status": status_ini,
                }).execute().data[0]["id"]

            if executar(inserir_os, "Ordem de serviço cadastrada com sucesso!"):
                st.session_state["flash"] = f"Ordem de serviço nº {resultado['os']} cadastrada com sucesso!"
                recarregar()

# ---------------------------------------------------------------------------
# Editar / Excluir
# ---------------------------------------------------------------------------
with aba_editar:
    col_os, col_cli = st.columns(2, gap="large")

    with col_os:
        st.subheader("Ordem de serviço")
        if ordens.empty:
            st.info("Nenhuma ordem de serviço cadastrada.")
        else:
            os_sel = st.selectbox("Selecione a OS", list(ordens.itertuples(index=False)), format_func=rotulo_os)
            st.caption(f"Problema: {os_sel.problema_relatado}")

            with st.form("form_status"):
                idx = status_existentes.index(os_sel.status) if os_sel.status in status_existentes else 0
                novo_status = st.selectbox("Novo status", status_existentes, index=idx)
                if st.form_submit_button("Salvar status", type="primary"):
                    if executar(
                        lambda: supabase.table("ordens_servico")
                        .update({"status": novo_status}).eq("id", int(os_sel.id)).execute(),
                        f"Status da OS {os_sel.id} alterado para \"{novo_status}\".",
                    ):
                        recarregar()

            with st.expander("🗑️ Excluir esta OS"):
                st.warning(f"A OS {os_sel.id} será excluída permanentemente.")
                conf_os = st.checkbox("Confirmo que desejo excluir esta OS", key=f"conf_os_{os_sel.id}")
                if st.button("Excluir OS", type="primary", disabled=not conf_os, key="btn_del_os"):
                    if executar(
                        lambda: supabase.table("ordens_servico").delete().eq("id", int(os_sel.id)).execute(),
                        f"OS {os_sel.id} excluída.",
                    ):
                        recarregar()

    with col_cli:
        st.subheader("Cliente")
        if clientes.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            cli_sel = st.selectbox("Selecione o cliente", list(clientes.itertuples(index=False)),
                                   format_func=rotulo_cliente, key="cli_edit")

            with st.form("form_cliente"):
                st.text_input("Nome", value=cli_sel.nome, disabled=True)
                ed_end = st.text_input("Endereço", value=cli_sel.endereco or "")
                ed_email = st.text_input("E-mail", value=cli_sel.email or "")
                ed_cel = st.text_input("Celular/WhatsApp", value=cli_sel.celular_whatsapp or "",
                                       placeholder="Somente números")
                if st.form_submit_button("Salvar cliente", type="primary"):
                    erros = validar_cliente(cli_sel.nome, ed_end, ed_email, ed_cel)
                    if erros:
                        for e in erros:
                            st.warning(e)
                    elif executar(
                        lambda: supabase.table("clientes").update({
                            "endereco": ed_end.strip(),
                            "email": ed_email.strip().lower(),
                            "celular_whatsapp": ed_cel.strip(),
                        }).eq("id", int(cli_sel.id)).execute(),
                        f"Dados de {cli_sel.nome} atualizados.",
                    ):
                        recarregar()

            qtd_os = int((ordens["cliente_id"] == cli_sel.id).sum())
            with st.expander("🗑️ Excluir este cliente"):
                st.warning(
                    f"O cliente {cli_sel.nome} será excluído permanentemente"
                    + (f", junto com suas {qtd_os} ordem(ns) de serviço." if qtd_os else ".")
                )
                conf_cli = st.checkbox("Confirmo que desejo excluir este cliente", key=f"conf_cli_{cli_sel.id}")
                if st.button("Excluir cliente", type="primary", disabled=not conf_cli, key="btn_del_cli"):
                    def excluir_cliente():
                        supabase.table("ordens_servico").delete().eq("cliente_id", int(cli_sel.id)).execute()
                        supabase.table("clientes").delete().eq("id", int(cli_sel.id)).execute()

                    if executar(excluir_cliente, f"Cliente {cli_sel.nome} excluído."):
                        recarregar()

# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------
with aba_indicadores:
    st.subheader("Ordens de serviço por status")
    st.caption("Considera todas as OS, independentemente dos filtros.")
    contagem = ordens["status"].value_counts().reindex(status_existentes, fill_value=0)

    st.metric("Total de OS", len(ordens))
    cols = st.columns(3)
    for i, (status, qtd) in enumerate(contagem.items()):
        cols[i % 3].metric(status, int(qtd))

    if ordens.empty:
        st.info("Cadastre ordens de serviço para ver o gráfico.")
    else:
        st.bar_chart(contagem.rename("Quantidade"), x_label="Status", y_label="Quantidade de OS", sort=False)
