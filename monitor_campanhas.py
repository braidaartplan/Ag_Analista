import os
from typing import Optional
from pathlib import Path
from agno.agent import Agent
from agno.tools.sql import SQLTools
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv
from agno.playground import Playground, serve_playground_app
from agno.storage.agent.sqlite import SqliteAgentStorage as SqliteStorage
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from textwrap import dedent
import streamlit as st


# Carrega variáveis de ambiente com as chaves de API e credenciais do banco
def get_db_config():
    """Carrega configuração do banco de dados"""
    try:
        # Streamlit Cloud
        return {
            'usuario': st.secrets["DB_USUARIO"],
            'senha': st.secrets["DB_SENHA"], 
            'host': st.secrets["DB_HOST"],
            'nome': st.secrets["DB_NOME"]
        }
    except (KeyError, AttributeError, st.errors.StreamlitSecretNotFoundError) as e:
        # Desenvolvimento local
        from dotenv import load_dotenv
        import os
        
        # Busca .env no diretório atual e pais
        env_path = Path('.env')
        if not env_path.exists():
            env_path = Path('../.env')
        
        load_dotenv(env_path)
        
        config = {
            'usuario': os.getenv('DB_USUARIO'),
            'senha': os.getenv('DB_SENHA'),
            'host': os.getenv('DB_HOST'), 
            'nome': os.getenv('DB_NOME')
        }
        
        # Validação
        missing = [k for k, v in config.items() if not v]
        if missing:
            raise ValueError(f"Variáveis de ambiente faltando: {missing}")
        
        return config

# Usar a função
db_config = get_db_config()
db_url = f"mysql+pymysql://{db_config['usuario']}:{db_config['senha']}@{db_config['host']}/{db_config['nome']}"
db_file = "tmp/agent.db"
db_conversations = SqliteStorage(table_name="Sessoes_Agentes", db_file=db_file)

# Configuração da nova API de memória v2
memory_db = SqliteMemoryDb(table_name="agent_memories", db_file="tmp/memory.db")
memory = Memory(db=memory_db)


def get_agent_assistente(
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model_name: str = "gpt-5-nano",
        debug_mode: bool = True,
) -> Agent:
    """Retorna o agente configurado para análise de campanhas."""
    
    model = OpenAIChat(id=model_name)
    
    description = open('prompts/analista.md').read()        
    instructions = (
        "Sempre que precisar consultar dados, utilize a VIEW Metricas, que contém as seguintes colunas:\n"
        "- Cliente: Nome do cliente responsável pela campanha. Exemplos incluem: Eletrobras, BNDES, CNI, SEBRAE e SEBRAE RJ.\n"
        "- Campanha: Nome da campanha. Nem todas as campanhas estão ativas atualmente.\n"
        "- Veiculo: Plataforma em que os anúncios foram veiculados, como: Instagram, Facebook, TikTok, Pinterest, LinkedIn, Google Discovery, YouTube, entre outras.\n"
        "- Data: Data de ocorrência do registro.\n"
        "- Impressoes: Quantidade de vezes que o anúncio foi exibido (impressões).\n"
        "- Investimento: Valor investido no anúncio nesse dia específico.\n"
        "- Visualizacoes_ate_100: Número de visualizações que chegaram até o fim do vídeo (100%).\n"
        "- Video_Play: Quantidade de vezes que o vídeo foi iniciado.\n"
        "- Formato: Tipo de formato do criativo, como: Card, Carrossel, Coleção, Discovery, Estático, Reels, Stories, Vídeo.\n"
        "- Criativo: Nome ou identificador do criativo utilizado no anúncio.\n"
        "- Objetivo: Objetivo da campanha, como: Alcance, Visualização, Tráfego, Engajamento, Consideração ou Conversão.\n"
        "- Editoria: Subdivisão editorial dentro da campanha.\n"
        "- Link_do_Anuncio: URL do anúncio correspondente."
    )
    return Agent(
        name="sql_agent",
        read_chat_history=True,
        session_id=session_id,
        tools=[SQLTools(db_url=db_url)],
        model=model,
        num_history_runs=10,
        memory=memory,
        enable_user_memories=True,
        add_history_to_messages=True,
        show_tool_calls=True,
        add_datetime_to_instructions=True,
        debug_mode=False,
        read_tool_call_history=True,
        storage=db_conversations,
        description=description,
        instructions=instructions,
        cache_session=True
    )


# Playground

if __name__ == "__main__":
    sql_agent = get_agent_assistente()
    playground_app = Playground(agents=[sql_agent])
    app = playground_app.get_app()
    serve_playground_app("Monitor_Campanhas:app", reload=True)