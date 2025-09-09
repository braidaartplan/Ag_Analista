import os
from datetime import datetime
from typing import List, Dict, Optional
import mysql.connector
from mysql.connector import Error
import streamlit as st
from pathlib import Path
import uuid

class ChatManager:
    """Gerencia as sessões de chat e histórico de conversas."""
    
    def __init__(self):
        self.db_config = self.get_db_config()
        self.init_database()
    
    def get_db_config(self):
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
    
    def init_database(self):
        """Inicializa o banco de dados MySQL e verifica se a tabela IA_Memoria existe"""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            if connection.is_connected():
                cursor = connection.cursor()
                
                # Verifica se a tabela IA_Memoria existe
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'IA_Memoria'
                """, (self.db_config['nome'],))
                
                table_exists = cursor.fetchone()[0] > 0
                
                if not table_exists:
                    # Cria a tabela IA_Memoria se não existir
                    cursor.execute("""
                        CREATE TABLE IA_Memoria (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id VARCHAR(255) NOT NULL,
                            session_id VARCHAR(255) NOT NULL,
                            title VARCHAR(500),
                            role ENUM('user', 'assistant') NOT NULL,
                            content TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            INDEX idx_user_session (user_id, session_id),
                            INDEX idx_session (session_id)
                        )
                    """)
                    connection.commit()
                    print("Tabela IA_Memoria criada com sucesso!")
                
                cursor.close()
                connection.close()
                
        except Error as e:
            print(f"Erro ao conectar com MySQL: {e}")
            raise e
    
    def create_user(self, username: str) -> str:
        """Cria um novo usuário e retorna o ID (usando a tabela IA_Memoria para verificar usuários existentes)."""
        user_id = str(uuid.uuid4())
        
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            
            # Verifica se o usuário já existe na tabela IA_Memoria
            cursor.execute("SELECT DISTINCT user_id FROM IA_Memoria WHERE user_id = %s LIMIT 1", (username,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                return username  # Retorna o username como user_id
            else:
                return username  # Para novos usuários, usamos o username como user_id
                
        except Error as e:
            print(f"Erro ao verificar usuário: {e}")
            return username
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_user_id(self, username: str) -> Optional[str]:
        """Busca o ID do usuário pelo nome (usando a tabela IA_Memoria)."""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM IA_Memoria WHERE user_id = %s LIMIT 1", (username,))
            result = cursor.fetchone()
            return result[0] if result else username  # Retorna o username como user_id
            
        except Error as e:
            print(f"Erro ao buscar usuário: {e}")
            return username
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def create_session(self, user_id: str, title: str = None) -> str:
        """Cria uma nova sessão de chat (usando a tabela IA_Memoria)."""
        session_id = str(uuid.uuid4())
        if not title:
            title = f"Chat {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            # Insere uma entrada inicial na tabela IA_Memoria para marcar a criação da sessão
            cursor.execute(
                "INSERT INTO IA_Memoria (user_id, session_id, title, role, content) VALUES (%s, %s, %s, %s, %s)",
                (user_id, session_id, title, 'assistant', f'Sessão criada: {title}')
            )
            connection.commit()
            
        except Error as e:
            print(f"Erro ao criar sessão: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
        
        return session_id
    
    def get_user_sessions(self, user_id: str) -> List[Dict]:
        """Retorna todas as sessões de um usuário (usando a tabela IA_Memoria)."""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            cursor.execute(
                """SELECT DISTINCT session_id, 
                          COALESCE(MAX(CASE WHEN title IS NOT NULL AND title != '' THEN title END), 
                                   CONCAT('Chat ', DATE_FORMAT(MIN(created_at), '%d/%m/%Y %H:%i'))) as title,
                          MIN(created_at) as created_at
                   FROM IA_Memoria 
                   WHERE user_id = %s 
                   GROUP BY session_id 
                   ORDER BY MIN(created_at) DESC""",
                (user_id,)
            )
            sessions = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'title': row[1],
                    'created_at': row[2]
                }
                for row in sessions
            ]
            
        except Error as e:
            print(f"Erro ao buscar sessões: {e}")
            return []
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def save_message(self, session_id: str, role: str, content: str, user_id: str = None):
        """Salva uma mensagem na tabela IA_Memoria."""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            
            # Se user_id não foi fornecido, busca pela sessão
            if not user_id:
                cursor.execute("SELECT DISTINCT user_id FROM IA_Memoria WHERE session_id = %s LIMIT 1", (session_id,))
                result = cursor.fetchone()
                user_id = result[0] if result else 'unknown'
            
            cursor.execute(
                "INSERT INTO IA_Memoria (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                (user_id, session_id, role, content)
            )
            
            connection.commit()
            
        except Error as e:
            print(f"Erro ao salvar mensagem: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        """Retorna todas as mensagens de uma sessão (usando a tabela IA_Memoria)."""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            cursor.execute(
                """SELECT role, content, created_at 
                   FROM IA_Memoria 
                   WHERE session_id = %s AND role IN ('user', 'assistant') 
                   ORDER BY created_at""",
                (session_id,)
            )
            messages = cursor.fetchall()
            
            return [
                {
                    'role': row[0],
                    'content': row[1],
                    'timestamp': row[2]
                }
                for row in messages
            ]
            
        except Error as e:
            print(f"Erro ao buscar mensagens: {e}")
            return []
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def update_session_title(self, session_id: str, title: str):
        """Atualiza o título de uma sessão na tabela IA_Memoria."""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE IA_Memoria SET title = %s WHERE session_id = %s",
                (title, session_id)
            )
            connection.commit()
            
        except Error as e:
            print(f"Erro ao atualizar título da sessão: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def delete_session(self, session_id: str):
        """Deleta uma sessão e todas suas mensagens da tabela IA_Memoria."""
        try:
            connection = mysql.connector.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            
            # Deleta todas as mensagens da sessão
            cursor.execute("DELETE FROM IA_Memoria WHERE session_id = %s", (session_id,))
            
            connection.commit()
            
        except Error as e:
            print(f"Erro ao deletar sessão: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    
    def generate_session_title(self, first_message: str) -> str:
        """Gera um título baseado na primeira mensagem."""
        # Pega as primeiras palavras da mensagem
        words = first_message.split()[:5]
        title = ' '.join(words)
        if len(title) > 50:
            title = title[:47] + "..."
        return title or f"Chat {datetime.now().strftime('%d/%m/%Y %H:%M')}"