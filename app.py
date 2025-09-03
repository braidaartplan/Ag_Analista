# agent_agno_streamlit.py
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import streamlit as st

from custom_uploader import custom_uploader
import base64
from dotenv import load_dotenv

from agno.agent import Agent
from agno.tools.sql import SQLTools
from agno.models.openai import OpenAIChat
from agno.memory.v2.memory import Memory
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.storage.sqlite import SqliteStorage
from agno.document.reader.pdf_reader import PDFReader
from agno.document.reader.csv_reader import CSVReader

from utils import doc_text

# ------------------------------------------------------
# Configurações
# ------------------------------------------------------
load_dotenv('/Users/braida/Dev/Python/GitHub/agentRAG/.env')


PASTA_ARQUIVOS = Path(__file__).parent / 'arquivos'
PASTA_ARQUIVOS.mkdir(parents=True, exist_ok=True)

CLIENTES = [
    "ELETROBRÁS",
    "BNDES",
    "CNI",
    "SEBRAE",
    "SEBRAE RJ"
]

MODELOS_OPENAI = [
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5",
    "gpt-4o",
    "gpt-4.1",    
]

# ------------------------------------------------------
# Helpers
# ------------------------------------------------------
def get_reader(file_type: str):
    """Retorna o leitor apropriado de acordo com o tipo de arquivo."""
    readers = {
        "pdf": PDFReader(),
        "csv": CSVReader(),
    }
    return readers.get(file_type.lower(), None)

def _extract_text(raw_resp) -> str:
    """Extrai texto de diferentes shapes de retorno do agente."""
    if getattr(raw_resp, "content", None):
        return raw_resp.content
    msg = getattr(raw_resp, "message", None)
    if msg and getattr(msg, "content", None):
        return msg.content
    msgs = getattr(raw_resp, "messages", None)
    if msgs:
        last = msgs[-1]
        if isinstance(last, dict):
            return last.get("content") or str(last)
        return getattr(last, "content", None) or str(last)
    if getattr(raw_resp, "text", None):
        return raw_resp.text
    if getattr(raw_resp, "output_text", None):
        return raw_resp.output_text
    return str(raw_resp)

def _doc_text(doc) -> str:
    # aceita Document, dict ou string
    if isinstance(doc, str):
        return doc
    # atributos mais comuns
    for attr in ("text", "content", "page_content", "pageContent"):
        val = getattr(doc, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    # alguns readers expõem .to_dict() / .dict()
    try:
        to_dict = getattr(doc, "to_dict", None) or getattr(doc, "dict", None)
        if callable(to_dict):
            d = to_dict()
            for k in ("text", "content", "page_content"):
                if isinstance(d.get(k), str) and d[k].strip():
                    return d[k]
    except Exception:
        pass
    # último recurso
    return str(doc)

def inject_upload_button_styles():
    """Estiliza o file_uploader para parecer um botão, sem quebrar o clique."""
    st.markdown(
        """
        <style>
        /* Título do grupo */
        .sidebar-section-title {
            font-weight: 700; font-size: 1rem; margin: .5rem 0 .25rem 0;
        }

        /* Mantém o dropzone visível e clicável, com cara de botão */
        [data-testid="stFileUploaderDropzone"] {
            border: 1px solid #d0d5dd !important;
            background: #f8fafc !important;
            border-radius: 10px !important;
            padding: 10px 14px !important;
            min-height: 44px !important;
            box-shadow: 0 1px 1px rgba(16,24,40,.04);
            display: flex; align-items: center; justify-content: center;
            cursor: pointer;
        }
        [data-testid="stFileUploaderDropzone"]:hover {
            background: #eef2f7 !important;
        }

        /* Rótulo acima do dropzone (fica como título do botão) */
        .stFileUploader > label {
            display: inline-flex !important;
            align-items: center;
            gap: .5rem;
            font-weight: 600;
            color: #111827;
            margin-bottom: 6px;
        }

        /* Opcional: reduz ícone e texto internos para parecer compacto */
        [data-testid="stFileUploaderDropzone"] svg {
            width: 0; height: 0; /* oculta ícone padrão */
        }
        [data-testid="stFileUploaderDropzone"] div:first-child {
            margin: 0 !important;
            padding: 0 !important;
        }
        /* Normaliza tipografia interna */
        [data-testid="stFileUploaderDropzone"] * {
            font-size: 0.95rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------
# Sidebar (Upload + Filtros + Modelo)
# ------------------------------------------------------
def sidebar():
    inject_upload_button_styles()

    st.title("⚙️ Filtros & Configurações")

    # --- Seletor de modelo (mantido como você enviou) ---
    if "model_name" not in st.session_state:
        st.session_state.model_name = MODELOS_OPENAI[0]

    selected_model = st.selectbox(
        "Modelo OpenAI",
        options=MODELOS_OPENAI,
        index=MODELOS_OPENAI.index(st.session_state.model_name),
        help="Escolha o modelo para o agente usar nas respostas."
    )
    if selected_model != st.session_state.model_name:
        st.session_state.model_name = selected_model
        st.session_state.agent = None  # força recriação
        st.toast(f"Modelo alterado para: {selected_model}", icon="🤖")

    # --- Filtros de data/cliente ---
    today = date.today()
    start = st.date_input("Data inicial", value=today.replace(day=1), max_value=today)
    end = st.date_input("Data final", value=today, min_value=start, max_value=today)
    cliente_sel = st.selectbox("Cliente", options=CLIENTES, index=0)
    cliente_val = cliente_sel

    if st.button("🗑️ Limpar conversa"):
        st.session_state.history.clear()
        st.toast("Histórico limpo ✅", icon="🗑️")

    st.session_state.sidebar_filters = {
        "start_date": start,
        "end_date": end,
        "cliente": cliente_val.strip(),
    }

    st.markdown("---")
    st.markdown('<div class="sidebar-section-title">Adicionar contexto</div>', unsafe_allow_html=True)

    # --- Abas para upload estilo mock ---
    tabs = st.tabs(["📄 PDF", "📊 CSV"])
    textos = []

    # PDF
    with tabs[0]:
        pdfs = st.file_uploader(
            "⬆️ Upload a PDF file",
            type=["pdf"],
            accept_multiple_files=True,
            key="uploader_pdf",
            label_visibility="visible"
        )
        if pdfs:
            # limpa a pasta para manter somente os últimos
            for arquivo in PASTA_ARQUIVOS.glob('*'):
                arquivo.unlink()

            reader = get_reader("pdf")
            for pdf in pdfs:
                file_path = PASTA_ARQUIVOS / pdf.name
                with open(file_path, "wb") as f:
                    f.write(pdf.read())
                if reader:
                    documents = list(reader.read(file_path))
                    textos.append("\n\n".join(doc_text(doc) for doc in documents))
            if not reader:
                st.warning("Não há leitor configurado para PDF.")

    # CSV
    with tabs[1]:
        csvs = st.file_uploader(
            "⬆️ Upload a CSV file",
            type=["csv"],
            accept_multiple_files=True,
            key="uploader_csv",
            label_visibility="visible"
        )
        if csvs:
            for arquivo in PASTA_ARQUIVOS.glob('*'):
                arquivo.unlink()

            reader = get_reader("csv")
            for csv in csvs:
                file_path = PASTA_ARQUIVOS / csv.name
                with open(file_path, "wb") as f:
                    f.write(csv.read())
                if reader:
                    documents = list(reader.read(file_path))
                    textos.append("\n\n".join(doc_text(doc) for doc in documents))
            if not reader:
                st.warning("Não há leitor configurado para CSV.")

    # Consolida no estado para uso no prompt
    st.session_state.uploaded_docs = "\n\n".join(textos)

def render_history():
    for item in st.session_state.history:
        chat = st.chat_message("human" if item["role"] == "user" else "ai")
        chat.markdown(item["content"], unsafe_allow_html=True)

# ------------------------------------------------------
# Página principal
# ------------------------------------------------------
def pagina_chat():
    st.set_page_config(page_title="🎯 Monitoramento de Campanhas", layout="wide")
    st.header("🤖 Olá, sou seu analista de campanhas", divider=True)

    # Estados iniciais
    if "history" not in st.session_state:
        st.session_state.history = []
    if "sidebar_filters" not in st.session_state:
        today = date.today()
        st.session_state.sidebar_filters = {
            "start_date": today.replace(day=1),
            "end_date": today,
            "cliente": "None",
        }
    if "model_name" not in st.session_state:
        st.session_state.model_name = MODELOS_OPENAI[0]
    if "uploaded_docs" not in st.session_state:
        st.session_state.uploaded_docs = ""

    # Sidebar (modelo, filtros e upload)
    with st.sidebar:
        sidebar()

    # (Re)cria o agente se necessário (pode ter sido invalidado ao trocar o modelo)
    if "agent" not in st.session_state or st.session_state.agent is None:
        from monitor_campanhas import get_agent_assistente  # sua factory
        st.session_state.agent = get_agent_assistente(
            session_id="sessao_streamlit",
            model_name=st.session_state.model_name
        )

    # Render histórico
    render_history()

    # Chat
    prompt = st.chat_input("Pergunte algo sobre a performance das campanhas…")

    if prompt:
        filters = st.session_state.sidebar_filters
        filtro_texto = ""
        if filters.get("cliente"):
            filtro_texto += f" Cliente: {filters['cliente']}."
        if filters.get("start_date") and filters.get("end_date"):
            filtro_texto += (
                f" Intervalo de dados: {filters['start_date'].strftime('%d/%m/%Y')} "
                f"até {filters['end_date'].strftime('%d/%m/%Y')}."
            )

        contexto_docs = st.session_state.get("uploaded_docs", "")
        if contexto_docs:
            final_prompt = f"{contexto_docs}\n\n{filtro_texto}\n{prompt}"
        else:
            final_prompt = f"{filtro_texto}\n{prompt}" if filtro_texto else prompt

        # Renderiza imediatamente a mensagem do usuário
        st.chat_message("human").markdown(prompt, unsafe_allow_html=True)
        st.session_state.history.append({"role": "user", "content": prompt})

        # Executa o agente e renderiza a resposta
        with st.spinner("Analisando…"):
            try:
                raw_resp = st.session_state.agent.run(final_prompt)
                answer = _extract_text(raw_resp)
            except Exception as e:
                answer = f"❌ Erro ao processar: {e}"

        st.chat_message("ai").markdown(answer, unsafe_allow_html=True)
        st.session_state.history.append({"role": "assistant", "content": answer})

# ------------------------------------------------------
# Main
# ------------------------------------------------------
if __name__ == "__main__":
    pagina_chat()
