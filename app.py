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
from agno.memory import AgentMemory
from agno.storage.sqlite import SqliteStorage
from agno.document.reader.pdf_reader import PDFReader
from agno.document.reader.csv_reader import CSVReader

from utils import doc_text
from chat_manager import ChatManager
from auth_service import AuthService

# ------------------------------------------------------
# Configurações
# ------------------------------------------------------
load_dotenv()  # Carrega o .env do diretório atual

# Inicializa o gerenciador de chats e serviço de autenticação
chat_manager = ChatManager()
auth_service = AuthService()

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
    "gpt-5-nano",
    "gpt-5-mini",
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
    """Extrai texto de diferentes shapes de retorno do agente, preservando formatação."""
    # Tenta extrair conteúdo de diferentes estruturas
    content = None
    
    # Verifica atributo content direto
    if hasattr(raw_resp, "content") and raw_resp.content:
        content = raw_resp.content
    
    # Verifica message.content
    elif hasattr(raw_resp, "message") and raw_resp.message:
        if hasattr(raw_resp.message, "content") and raw_resp.message.content:
            content = raw_resp.message.content
    
    # Verifica messages[-1].content
    elif hasattr(raw_resp, "messages") and raw_resp.messages:
        last_msg = raw_resp.messages[-1]
        if isinstance(last_msg, dict):
            content = last_msg.get("content")
        elif hasattr(last_msg, "content"):
            content = last_msg.content
    
    # Verifica outros atributos comuns
    elif hasattr(raw_resp, "text") and raw_resp.text:
        content = raw_resp.text
    elif hasattr(raw_resp, "output_text") and raw_resp.output_text:
        content = raw_resp.output_text
    elif hasattr(raw_resp, "response") and raw_resp.response:
        content = raw_resp.response
    
    # Se encontrou conteúdo, processa e limpa
    if content:
        # Remove caracteres de controle e espaços extras
        content = str(content).strip()
        # Remove sequências de escape comuns
        content = content.replace('\\n', '\n').replace('\\t', '\t')
        return content
    
    # Fallback para conversão direta
    result = str(raw_resp).strip()
    return result if result and result != "None" else "❌ Não foi possível extrair resposta do agente."

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

def authenticate_user():
    """Sistema de autenticação com verificação de email."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.user_email = None
    
    if not st.session_state.user_id:
        st.title("🔐 Login")
        st.markdown("Digite seu email para acessar o sistema:")
        
        # Tabs para Login e Cadastro
        tab_login, tab_cadastro = st.tabs(["Login", "Cadastro"])
        
        with tab_login:
            st.subheader("Fazer Login")
            email_login = st.text_input("Email:", key="login_email", placeholder="seu@email.com")
            senha_login = st.text_input("Senha (Mínimo 6 caracteres):", type="password", key="login_password", 
                                      help="Deixe em branco se não tiver senha cadastrada")
            
            if st.button("Entrar", type="primary", key="btn_login"):
                if email_login.strip():
                    sucesso, mensagem, user_data = auth_service.authenticate_user_by_email(
                        email_login.strip(), 
                        senha_login.strip() if senha_login.strip() else None
                    )
                    
                    if sucesso and user_data:
                        st.session_state.user_id = user_data['id']
                        st.session_state.username = user_data['nome']
                        st.session_state.user_email = user_data['email']
                        st.success(mensagem)
                        st.rerun()
                    else:
                        st.error(mensagem)
                else:
                    st.error("Por favor, digite um email válido.")
        
        with tab_cadastro:
            st.subheader("Criar Nova Conta")
            email_cadastro = st.text_input("Email:", key="cadastro_email", placeholder="seu@email.com")
            nome_cadastro = st.text_input("Nome", key="cadastro_nome", placeholder="Seu Nome")
            senha_cadastro = st.text_input("Senha:", type="password", key="cadastro_password",
                                         help="Deixe em branco para acesso sem senha")
            
            if st.button("Criar Conta", type="secondary", key="btn_cadastro"):
                if email_cadastro.strip() and nome_cadastro.strip():
                    sucesso, mensagem, user_id = auth_service.create_user_with_email(
                        email_cadastro.strip(),
                        nome_cadastro.strip(),
                        senha_cadastro.strip() if senha_cadastro.strip() else None
                    )
                    
                    if sucesso and user_id:
                        st.success(mensagem)
                        st.info("Agora você pode fazer login com seu email.")
                    else:
                        st.error(mensagem)
                else:
                    st.error("Por favor, preencha email e nome.")
        
        return False
    
    return True

def render_chat_sidebar():
    """Renderiza a sidebar com o histórico de chats."""
    # Cabeçalho com usuário e logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**👤 {st.session_state.username}**")
    with col2:
        if st.button("🚪", help="Logout", key="logout_btn"):
            # Limpa sessão
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    st.markdown("### 💬 Conversas")
    
    # Botão para nova conversa
    if st.button("➕ Nova Conversa", use_container_width=True):
        # Cria nova sessão
        session_id = chat_manager.create_session(st.session_state.user_id)
        st.session_state.current_session_id = session_id
        st.session_state.history = []
        st.session_state.agent = None  # força recriação do agente
        st.rerun()
    
    st.markdown("---")
    
    # Lista de conversas
    sessions = chat_manager.get_user_sessions(st.session_state.user_id)
    
    if not sessions:
        st.markdown("*Nenhuma conversa ainda*")
        return
    
    for session in sessions:
        # Trunca o título se muito longo
        display_title = session['title']
        if len(display_title) > 30:
            display_title = display_title[:27] + "..."
        
        # Botão para cada conversa
        col1, col2 = st.columns([4, 1])
        
        with col1:
            if st.button(
                display_title,
                key=f"session_{session['id']}",
                use_container_width=True,
                help=f"Criado em: {session['created_at']}"
            ):
                # Carrega a conversa selecionada
                st.session_state.current_session_id = session['id']
                messages = chat_manager.get_session_messages(session['id'])
                st.session_state.history = messages
                st.session_state.agent = None  # força recriação do agente
                st.rerun()
        
        with col2:
            if st.button("🗑️", key=f"delete_{session['id']}", help="Deletar conversa"):
                chat_manager.delete_session(session['id'])
                # Se era a conversa atual, limpa
                if st.session_state.get('current_session_id') == session['id']:
                    st.session_state.current_session_id = None
                    st.session_state.history = []
                st.rerun()

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
# Sidebar (Chats + Upload + Filtros + Modelo)
# ------------------------------------------------------
def sidebar():
    inject_upload_button_styles()
    
    # Seção de chats
    render_chat_sidebar()
    
    st.markdown("---")
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

    # Toggle removido - sem reasoning

    # --- Filtros de data/cliente ---
    today = date.today()
    start = st.date_input("Data inicial", value=today.replace(day=1), max_value=today)
    end = st.date_input("Data final", value=today, min_value=start, max_value=today)
    cliente_sel = st.selectbox("Cliente", options=CLIENTES, index=0)
    cliente_val = cliente_sel

    if st.button("🗑️ Limpar conversa atual"):
        if st.session_state.current_session_id:
            chat_manager.delete_session(st.session_state.current_session_id)
            # Cria nova sessão
            session_id = chat_manager.create_session(st.session_state.user_id)
            st.session_state.current_session_id = session_id
            st.session_state.history.clear()
            st.session_state.agent = None  # força recriação
            st.toast("Conversa limpa ✅", icon="🗑️")
            st.rerun()

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
    
    # Verifica autenticação
    if not authenticate_user():
        return
    
    # Mostra informações do usuário logado
    st.header(f"🤖 Olá {st.session_state.username}, sou seu analista de campanhas", divider=True)

    # Estados iniciais
    if "history" not in st.session_state:
        st.session_state.history = []
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
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
    
    # Se não há sessão atual, cria uma nova
    if not st.session_state.current_session_id:
        session_id = chat_manager.create_session(st.session_state.user_id)
        st.session_state.current_session_id = session_id

    # Sidebar (modelo, filtros e upload)
    with st.sidebar:
        sidebar()

    # (Re)cria o agente se necessário (pode ter sido invalidado ao trocar o modelo)
    if "agent" not in st.session_state or st.session_state.agent is None:
        from monitor_campanhas import get_agent_assistente  
        st.session_state.agent = get_agent_assistente(
            user_id=st.session_state.user_id,
            session_id=st.session_state.current_session_id,
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
        
        # Salva a mensagem do usuário no banco
        chat_manager.save_message(st.session_state.current_session_id, "user", prompt, st.session_state.user_id)
        
        # Se é a primeira mensagem, gera um título para a sessão
        if len(st.session_state.history) == 1:
            title = chat_manager.generate_session_title(prompt)
            chat_manager.update_session_title(st.session_state.current_session_id, title)

        # Executa o agente e renderiza a resposta
        with st.spinner("Analisando…"):
            try:
                # Execução simples do agente
                raw_resp = st.session_state.agent.run(final_prompt)
                answer = _extract_text(raw_resp)
                            
            except Exception as e:
                answer = f"❌ Erro ao processar: {e}"

        st.chat_message("ai").markdown(answer, unsafe_allow_html=True)
        st.session_state.history.append({"role": "assistant", "content": answer})
        
        # Salva a resposta do agente no banco
        chat_manager.save_message(st.session_state.current_session_id, "assistant", answer, st.session_state.user_id)

# ------------------------------------------------------
# Main
# ------------------------------------------------------
if __name__ == "__main__":
    pagina_chat()
