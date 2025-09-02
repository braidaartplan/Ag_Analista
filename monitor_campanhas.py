import os
from typing import Optional
from agno.agent import Agent
from agno.tools.sql import SQLTools
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv
from agno.playground import Playground, serve_playground_app
from agno.storage.sqlite import SqliteStorage
from textwrap import dedent
from agno.memory.v2.memory import Memory
from agno.memory.v2.db.sqlite import SqliteMemoryDb
import streamlit as st


# Carrega variáveis de ambiente com as chaves de API e credenciais do banco
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
    except:
        # Desenvolvimento local
        from dotenv import load_dotenv
        load_dotenv('/Users/braida/Dev/Python/Stremlit/GitHub/AgentAgno/.env')
        return {
            'usuario': os.getenv('DB_USUARIO'),
            'senha': os.getenv('DB_SENHA'),
            'host': os.getenv('DB_HOST'), 
            'nome': os.getenv('DB_NOME')
        }

# Usar a função
db_config = get_db_config()
db_url = f"mysql+pymysql://{db_config['usuario']}:{db_config['senha']}@{db_config['host']}/{db_config['nome']}"
db_file = "tmp/agent.db"
db_conversations = SqliteStorage(table_name="Sessoes_Agentes", db_file=db_file)


def get_agent_assistente(
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model_name: str = "gpt-4.1-mini",
        debug_mode: bool = True,
) -> Agent:
    """Retorna o agente configurado para análise de campanhas."""
    
    model = OpenAIChat(id=model_name)
    
    memory = Memory(
        model=model,
        db=SqliteMemoryDb(table_name="Memoria_usuario", db_file=db_file)
    )
    
    description = dedent("""
        Você é um analista de dados de marketing digital com experiência em campanhas pagas. Sua tarefa é realizar o acompanhamento semanal das campanhas de marketing dos clientes, com foco na performance dos criativos.
        Analise os dados da semana e destaque os criativos com melhor e pior desempenho, considerando o objetivo da campanha.
        Para cada destaque positivo e negativo, apresente as seguintes métricas:
        Impressões, CPM (Custo por mil impressões)
        Visualizações até 100%, CPV (Custo por visualização)
        A análise deve considerar o contexto do objetivo da campanha: por exemplo, para campanhas de alcance, o foco deve estar em impressões e CPM; para campanhas de visualização, dê mais peso para visualizações 100% e CPV.
        Evite trazer listas longas: selecione apenas os criativos com performance mais relevante — tanto positiva quanto negativa — com base nos dados. 
        A resposta deve ser estruturada por cliente e campanha, destacando o criativo e suas métricas associadas.
        Faça:
        1. 🧠 Um resumo analítico da performance (bom/ruim e por quê)
        2. 📊 Interpretação dos KPIs principais
        3. ✅ Recomendações acionáveis para otimização                       
    """)

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
        add_history_to_messages=True,
        show_tool_calls=True,
        add_datetime_to_instructions=True,
        debug_mode=debug_mode,
        read_tool_call_history=True,
        storage=db_conversations,
        description=description,
        instructions=instructions,
    )


# Playground

if __name__ == "__main__":
    sql_agent = get_agent_assistente()
    playground_app = Playground(agents=[sql_agent])
    app = playground_app.get_app()
    serve_playground_app("Monitor_Campanhas:app", reload=True)