"""Cadastro de Ordens de Serviço - Assistência Técnica de Computadores.

Interface Gradio que grava clientes e ordens de serviço no Supabase.
Requer as variáveis de ambiente SUPABASE_URL e SUPABASE_KEY
(podem estar num arquivo .env na mesma pasta).
"""

import os
import re

import gradio as gr
from supabase import create_client

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
supabase = create_client(url, key)

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def validar(nome, endereco, email, celular, modelo, problema):
    """Retorna a lista de erros de validação (vazia se estiver tudo certo)."""
    erros = []
    campos = {
        "Nome do Cliente": nome,
        "Endereço": endereco,
        "E-mail": email,
        "Celular/WhatsApp": celular,
        "Modelo do Computador": modelo,
        "Problema Apresentado": problema,
    }
    for rotulo, valor in campos.items():
        if not valor or not valor.strip():
            erros.append(f"O campo **{rotulo}** é obrigatório.")

    if email and email.strip() and not EMAIL_RE.match(email.strip()):
        erros.append("O **E-mail** informado não tem um formato válido.")
    if celular and celular.strip() and not celular.strip().isdigit():
        erros.append("O **Celular/WhatsApp** deve conter apenas números (ex.: 11987654321).")
    return erros


def obter_ou_criar_cliente(nome, endereco, email, celular):
    """Reaproveita o cliente pelo e-mail ou cria um novo. Retorna (id, reaproveitado)."""
    existente = (
        supabase.table("clientes").select("id").eq("email", email).limit(1).execute()
    )
    if existente.data:
        return existente.data[0]["id"], True

    novo = (
        supabase.table("clientes")
        .insert(
            {
                "nome": nome,
                "endereco": endereco,
                "email": email,
                "celular_whatsapp": celular,
            }
        )
        .execute()
    )
    return novo.data[0]["id"], False


def cadastrar(nome, endereco, email, celular, modelo, problema):
    erros = validar(nome, endereco, email, celular, modelo, problema)
    if erros:
        return "### ⚠️ Corrija os campos abaixo\n" + "\n".join(f"- {e}" for e in erros)

    nome, endereco, modelo, problema = (
        nome.strip(), endereco.strip(), modelo.strip(), problema.strip()
    )
    email = email.strip().lower()
    celular = celular.strip()

    try:
        cliente_id, reaproveitado = obter_ou_criar_cliente(nome, endereco, email, celular)
        os_criada = (
            supabase.table("ordens_servico")
            .insert(
                {
                    "cliente_id": cliente_id,
                    "modelo_computador": modelo,
                    "problema_relatado": problema,
                    "status": "Aberto",
                }
            )
            .execute()
        )
        numero_os = os_criada.data[0]["id"]
    except Exception as exc:  # erros de rede, RLS, constraints etc.
        return f"### ❌ Erro ao cadastrar\n`{exc}`"

    origem = "Cliente já cadastrado (reaproveitado)" if reaproveitado else "Novo cliente cadastrado"
    return (
        f"### ✅ Ordem de Serviço nº {numero_os} criada com sucesso!\n"
        f"- {origem} — ID {cliente_id}\n"
        f"- Status inicial: **Aberto**"
    )


def limpar():
    return "", "", "", "", "", "", ""


with gr.Blocks(title="Cadastro de Ordem de Serviço") as app:
    gr.Markdown(
        "# 🛠️ Cadastro de Ordem de Serviço\n"
        "Preencha os dados do cliente e do equipamento e clique em **Cadastrar**. "
        "Se o e-mail já estiver cadastrado, o cliente existente será reaproveitado. "
        "Todos os campos são obrigatórios; o celular deve conter apenas números."
    )

    with gr.Row():
        with gr.Column(min_width=280):
            gr.Markdown("### 👤 Dados do Cliente")
            nome = gr.Textbox(label="Nome do Cliente", placeholder="Ex.: Maria da Silva")
            endereco = gr.Textbox(
                label="Endereço", placeholder="Ex.: Rua das Flores, 123 - Centro, São Paulo/SP"
            )
            email = gr.Textbox(label="E-mail", placeholder="Ex.: maria@email.com", type="email")
            celular = gr.Textbox(
                label="Celular/WhatsApp", placeholder="Somente números, com DDD. Ex.: 11987654321"
            )
        with gr.Column(min_width=280):
            gr.Markdown("### 💻 Dados do Equipamento")
            modelo = gr.Textbox(
                label="Modelo do Computador", placeholder="Ex.: Dell Inspiron 15 3520"
            )
            problema = gr.Textbox(
                label="Problema Apresentado",
                placeholder="Descreva o defeito. Ex.: Não liga, tela azul ao iniciar, muito lento...",
                lines=6,
            )

    with gr.Row():
        btn_limpar = gr.Button("Limpar", variant="secondary")
        btn_cadastrar = gr.Button("Cadastrar", variant="primary")

    resultado = gr.Markdown()

    campos = [nome, endereco, email, celular, modelo, problema]
    btn_cadastrar.click(cadastrar, inputs=campos, outputs=resultado)
    btn_limpar.click(limpar, outputs=campos + [resultado])


if __name__ == "__main__":
    app.launch(share=True)
