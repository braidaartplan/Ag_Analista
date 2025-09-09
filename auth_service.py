import re
import os
from datetime import datetime
from typing import Optional, Dict, Tuple
import pymysql
from pymysql import Error
import streamlit as st
from pathlib import Path
import uuid
import hashlib

class AuthService:
    """Serviço de autenticação que verifica emails e gerencia usuários."""
    
    def __init__(self):
        self.db_config = self.get_db_config()
        self.init_auth_tables()
    
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
    
    def init_auth_tables(self):
        """Inicializa as tabelas de autenticação no banco MySQL"""
        try:
            connection = pymysql.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            if connection.open:
                cursor = connection.cursor()
                
                # Cria tabela de usuários se não existir
                create_users_table = """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id VARCHAR(36) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    nome VARCHAR(255) NOT NULL,
                    senha_hash VARCHAR(255),
                    ativo BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_email (email)
                )
                """
                
                cursor.execute(create_users_table)
                connection.commit()
                
        except Error as e:
            print(f"Erro ao inicializar tabelas de autenticação: {e}")
        finally:
            if connection.open:
                cursor.close()
                connection.close()
    
    def validate_email(self, email: str) -> bool:
        """Valida o formato do email usando regex"""
        if not email or not isinstance(email, str):
            return False
        
        # Regex para validação de email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email.strip()) is not None
    
    def email_exists(self, email: str) -> bool:
        """Verifica se o email já existe no banco de dados"""
        try:
            connection = pymysql.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE email = %s AND ativo = TRUE", (email.strip().lower(),))
            result = cursor.fetchone()
            
            return result is not None
            
        except Error as e:
            print(f"Erro ao verificar email: {e}")
            return False
        finally:
            if connection.open:
                cursor.close()
                connection.close()
    
    def create_user_with_email(self, email: str, nome: str, senha: str = None) -> Tuple[bool, str, Optional[str]]:
        """Cria um novo usuário com email validado
        
        Returns:
            Tuple[bool, str, Optional[str]]: (sucesso, mensagem, user_id)
        """
        # Validações
        if not self.validate_email(email):
            return False, "Email inválido. Por favor, digite um email válido.", None
        
        if not nome or not nome.strip():
            return False, "Nome é obrigatório.", None
        
        email = email.strip().lower()
        nome = nome.strip()
        
        # Verifica se email já existe
        if self.email_exists(email):
            return False, "Este email já está cadastrado no sistema.", None
        
        try:
            connection = pymysql.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            user_id = str(uuid.uuid4())
            
            # Hash da senha se fornecida
            senha_hash = None
            if senha:
                senha_hash = hashlib.sha256(senha.encode()).hexdigest()
            
            # Insere novo usuário
            insert_query = """
                INSERT INTO usuarios (id, email, nome, senha_hash, ativo, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                user_id,
                email,
                nome,
                senha_hash,
                True,
                datetime.now()
            ))
            
            connection.commit()
            
            return True, f"Usuário {nome} criado com sucesso!", user_id
            
        except Error as e:
            print(f"Erro ao criar usuário: {e}")
            return False, f"Erro interno do sistema: {str(e)}", None
        finally:
            if connection.open:
                cursor.close()
                connection.close()
    
    def authenticate_user_by_email(self, email: str, senha: str = None) -> Tuple[bool, str, Optional[Dict]]:
        """Autentica usuário por email
        
        Returns:
            Tuple[bool, str, Optional[Dict]]: (sucesso, mensagem, dados_usuario)
        """
        if not self.validate_email(email):
            return False, "Email inválido.", None
        
        email = email.strip().lower()
        
        try:
            connection = pymysql.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, email, nome, senha_hash, ativo FROM usuarios WHERE email = %s AND ativo = TRUE",
                (email,)
            )
            user = cursor.fetchone()
            
            if not user:
                return False, "Email não encontrado ou usuário inativo.", None
            
            # Se não há senha cadastrada, permite acesso direto
            if not user['senha_hash']:
                return True, "Login realizado com sucesso!", {
                    'id': user['id'],
                    'email': user['email'],
                    'nome': user['nome']
                }
            
            # Se há senha cadastrada, verifica
            if senha:
                senha_hash = hashlib.sha256(senha.encode()).hexdigest()
                if senha_hash == user['senha_hash']:
                    return True, "Login realizado com sucesso!", {
                        'id': user['id'],
                        'email': user['email'],
                        'nome': user['nome']
                    }
                else:
                    return False, "Senha incorreta.", None
            else:
                return False, "Senha é obrigatória para este usuário.", None
            
        except Error as e:
            print(f"Erro ao autenticar usuário: {e}")
            return False, f"Erro interno do sistema: {str(e)}", None
        finally:
            if connection.open:
                cursor.close()
                connection.close()
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Busca usuário por email
        
        Returns:
            Optional[Dict]: dados do usuário ou None
        """
        if not self.validate_email(email):
            return None
        
        email = email.strip().lower()
        
        try:
            connection = pymysql.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, email, nome, ativo, created_at FROM usuarios WHERE email = %s AND ativo = TRUE",
                (email,)
            )
            user = cursor.fetchone()
            
            return user
            
        except Error as e:
            print(f"Erro ao buscar usuário: {e}")
            return None
        finally:
            if connection.open:
                cursor.close()
                connection.close()
    
    def update_user_password(self, email: str, nova_senha: str) -> Tuple[bool, str]:
        """Atualiza a senha do usuário
        
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        if not self.validate_email(email):
            return False, "Email inválido."
        
        if not nova_senha or len(nova_senha.strip()) < 6:
            return False, "Senha deve ter pelo menos 6 caracteres."
        
        email = email.strip().lower()
        senha_hash = hashlib.sha256(nova_senha.encode()).hexdigest()
        
        try:
            connection = pymysql.connect(
                host=self.db_config['host'],
                database=self.db_config['nome'],
                user=self.db_config['usuario'],
                password=self.db_config['senha']
            )
            
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE usuarios SET senha_hash = %s, updated_at = %s WHERE email = %s AND ativo = TRUE",
                (senha_hash, datetime.now(), email)
            )
            
            if cursor.rowcount > 0:
                connection.commit()
                return True, "Senha atualizada com sucesso!"
            else:
                return False, "Usuário não encontrado."
            
        except Error as e:
            print(f"Erro ao atualizar senha: {e}")
            return False, f"Erro interno do sistema: {str(e)}"
        finally:
            if connection.open:
                cursor.close()
                connection.close()