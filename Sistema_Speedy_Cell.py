import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timezone, timedelta
import requests
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")


def converter_para_sp(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        dt_str = dt.strip()
        if not dt_str:
            return None
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except Exception:
            parsed = False
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    parsed = True
                    break
                except Exception:
                    pass
            if not parsed:
                return None
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt_sp = dt.astimezone(timezone(timedelta(hours=-3)))
        else:
            dt_sp = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=-3)))
        return dt_sp.replace(tzinfo=None)
    elif hasattr(dt, 'year') and hasattr(dt, 'month') and hasattr(dt, 'day'):
        return datetime(dt.year, dt.month, dt.day)
    return None

def obter_agora_sp():
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3))).replace(tzinfo=None)

def formatar_brl(valor):
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
    except (ValueError, TypeError):
        return f"R$ {valor}"

import re

# Configurações iniciais da página do Streamlit
st.set_page_config(page_title="Speedy Cell ERP", layout="wide", page_icon="📱")


import sqlite3

# =========================================================================
# 1. FUNÇÃO DE CONEXÃO E AUXILIARES DE BANCO DE DADOS (DUAL-ENGINE: POSTGRES / SQLITE)
# =========================================================================
SQLITE_DB_PATH = os.path.join(BASE_DIR, "speedycell.db")

if "db_engine" not in st.session_state:
    st.session_state.db_engine = None  # "postgres" ou "sqlite"
if "db_error_msg" not in st.session_state:
    st.session_state.db_error_msg = ""

def testar_conexao_postgres():
    """Tenta conectar ao PostgreSQL / Supabase utilizando st.secrets"""
    try:
        if "DB_HOST" not in st.secrets:
            return False, ""
        host = str(st.secrets.get("DB_HOST", "")).strip()
        user = str(st.secrets.get("DB_USER", "")).strip()
        password = str(st.secrets.get("DB_PASSWORD", "")).strip()
        
        if not host or not user or not password:
            return False, ""
            
        conn = psycopg2.connect(
            host=host,
            database=st.secrets.get("DB_NAME", "postgres"),
            user=user,
            password=password,
            port=st.secrets.get("DB_PORT", 5432),
            connect_timeout=3
        )
        conn.close()
        return True, "Conectado ao Supabase com sucesso."
    except Exception as e:
        return False, str(e)

def inicializar_banco():
    """Determina o mecanismo de banco de dados e assegura que as tabelas existam."""
    if st.session_state.db_engine is None:
        pg_ok, err = testar_conexao_postgres()
        if pg_ok:
            st.session_state.db_engine = "postgres"
            st.session_state.db_error_msg = ""
        else:
            st.session_state.db_engine = "sqlite"
            st.session_state.db_error_msg = err

    if st.session_state.db_engine == "postgres":
        try:
            conn = psycopg2.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASSWORD"],
                port=st.secrets["DB_PORT"]
            )
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS Usuarios (
                IdUsuario SERIAL PRIMARY KEY,
                Usuario VARCHAR(100) UNIQUE NOT NULL,
                Senha VARCHAR(255) NOT NULL,
                Nome VARCHAR(255) NOT NULL,
                Role VARCHAR(50) NOT NULL
            );
            CREATE TABLE IF NOT EXISTS Clientes (
                IdCliente SERIAL PRIMARY KEY,
                Nome VARCHAR(255) NOT NULL,
                WhatsApp VARCHAR(50),
                Email VARCHAR(255),
                Documento VARCHAR(50),
                CEP VARCHAR(20),
                Logradouro VARCHAR(255),
                Numero VARCHAR(50),
                Complemento VARCHAR(255),
                Bairro VARCHAR(100),
                Cidade VARCHAR(100),
                Estado VARCHAR(50)
            );
            CREATE TABLE IF NOT EXISTS Produtos (
                IdProduto SERIAL PRIMARY KEY,
                Marca VARCHAR(100) NOT NULL,
                Modelo VARCHAR(100) NOT NULL,
                CustoProduto NUMERIC(10,2) DEFAULT 0,
                ValorMinimo NUMERIC(10,2) DEFAULT 0,
                ValorVenda NUMERIC(10,2) DEFAULT 0,
                Ativo BOOLEAN DEFAULT true
            );
            CREATE TABLE IF NOT EXISTS ItensEstoque (
                IdItem SERIAL PRIMARY KEY,
                IdProduto INT NOT NULL,
                NumeroSerie VARCHAR(100),
                Status VARCHAR(50) DEFAULT 'Disponivel',
                FOREIGN KEY(IdProduto) REFERENCES Produtos(IdProduto)
            );
            CREATE TABLE IF NOT EXISTS FluxoCaixa (
                IdLancamento SERIAL PRIMARY KEY,
                DataLancamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                Tipo VARCHAR(10) NOT NULL,
                Descricao TEXT,
                Valor NUMERIC(10,2) DEFAULT 0,
                IdCliente INT,
                IdItem INT,
                CustoHistorico NUMERIC(10,2) DEFAULT 0,
                CodigoVenda VARCHAR(100)
            );
            CREATE TABLE IF NOT EXISTS dividas (
                iddivida SERIAL PRIMARY KEY,
                credor VARCHAR(255) NOT NULL,
                descricao TEXT,
                valor NUMERIC(10,2) DEFAULT 0,
                data_divida DATE,
                data_vencimento DATE,
                id_os INT,
                observacoes TEXT,
                status VARCHAR(50) DEFAULT 'Pendente',
                data_pagamento TIMESTAMP
            );
            """)
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            st.session_state.db_engine = "sqlite"
            st.session_state.db_error_msg = str(e)

    if st.session_state.db_engine == "sqlite":
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Usuarios (
            IdUsuario INTEGER PRIMARY KEY AUTOINCREMENT,
            Usuario TEXT UNIQUE NOT NULL,
            Senha TEXT NOT NULL,
            Nome TEXT NOT NULL,
            Role TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Clientes (
            IdCliente INTEGER PRIMARY KEY AUTOINCREMENT,
            Nome TEXT NOT NULL,
            WhatsApp TEXT,
            Email TEXT,
            Documento TEXT,
            CEP TEXT,
            Logradouro TEXT,
            Numero TEXT,
            Complemento TEXT,
            Bairro TEXT,
            Cidade TEXT,
            Estado TEXT
        );
        CREATE TABLE IF NOT EXISTS Produtos (
            IdProduto INTEGER PRIMARY KEY AUTOINCREMENT,
            Marca TEXT NOT NULL,
            Modelo TEXT NOT NULL,
            CustoProduto REAL DEFAULT 0,
            ValorMinimo REAL DEFAULT 0,
            ValorVenda REAL DEFAULT 0,
            Ativo INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS ItensEstoque (
            IdItem INTEGER PRIMARY KEY AUTOINCREMENT,
            IdProduto INTEGER NOT NULL,
            NumeroSerie TEXT,
            Status TEXT DEFAULT 'Disponivel',
            FOREIGN KEY(IdProduto) REFERENCES Produtos(IdProduto)
        );
        CREATE TABLE IF NOT EXISTS FluxoCaixa (
            IdLancamento INTEGER PRIMARY KEY AUTOINCREMENT,
            DataLancamento DATETIME DEFAULT CURRENT_TIMESTAMP,
            Tipo TEXT NOT NULL,
            Descricao TEXT,
            Valor REAL DEFAULT 0,
            IdCliente INTEGER,
            IdItem INTEGER,
            CustoHistorico REAL DEFAULT 0,
            CodigoVenda TEXT
        );
        CREATE TABLE IF NOT EXISTS dividas (
            iddivida INTEGER PRIMARY KEY AUTOINCREMENT,
            credor TEXT NOT NULL,
            descricao TEXT,
            valor REAL DEFAULT 0,
            data_divida TEXT,
            data_vencimento TEXT,
            id_os INTEGER,
            observacoes TEXT,
            status TEXT DEFAULT 'Pendente',
            data_pagamento TEXT
        );
        """)
        conn.commit()
        conn.close()

inicializar_banco()

def traduzir_query_sqlite(query, params):
    if params is None:
        params = ()
    else:
        params = list(params)

    # Substitui ILIKE por LIKE (compatibilidade SQLite)
    query = re.sub(r'\bILIKE\b', 'LIKE', query, flags=re.IGNORECASE)

    # Trata = ANY(%s) -> IN (?, ?, ...)
    if "= ANY(%s)" in query or "= any(%s)" in query:
        new_params = []
        for p in params:
            if isinstance(p, (list, tuple, set)):
                lst = list(p)
                if not lst:
                    placeholders = "NULL"
                else:
                    placeholders = ",".join(["?"] * len(lst))
                    new_params.extend(lst)
                query = re.sub(r'=\s*(?:ANY|any)\(%s\)', f'IN ({placeholders})', query, count=1)
            else:
                new_params.append(p)
                query = query.replace("%s", "?", 1)
        params = new_params

    # Substitui %s restantes por ?
    query = query.replace("%s", "?")
    
    # Literais Booleanos
    query = query.replace("p.Ativo = true", "p.Ativo = 1")
    query = query.replace("p.Ativo = false", "p.Ativo = 0")
    query = query.replace("p.Ativo = TRUE", "p.Ativo = 1")
    query = query.replace("p.Ativo = FALSE", "p.Ativo = 0")
    query = query.replace("Ativo = true", "Ativo = 1")
    query = query.replace("Ativo = false", "Ativo = 0")

    # Funções de data
    query = query.replace("CURRENT_DATE - INTERVAL '30 days'", "date('now', '-30 days')")
    query = query.replace("CURRENT_DATE", "date('now')")
    query = re.sub(r'CAST\s*\(\s*DataLancamento\s+AS\s+DATE\s*\)', "date(DataLancamento)", query, flags=re.IGNORECASE)
    query = re.sub(r'CAST\s*\(\s*data_pagamento\s+AS\s+DATE\s*\)', "date(data_pagamento)", query, flags=re.IGNORECASE)

    # Escapar porcentagem do psycopg2
    query = query.replace("%%", "%")

    return query, tuple(params)

class SQLiteCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.last_returning_id = None

    def execute(self, query, params=None):
        if params is None:
            params = ()
        else:
            params = list(params)

        match_returning = re.search(r'\s+RETURNING\s+([a-zA-Z0-9_]+)', query, flags=re.IGNORECASE)
        has_returning = bool(match_returning)
        if has_returning:
            query = re.sub(r'\s+RETURNING\s+([a-zA-Z0-9_]+)', '', query, flags=re.IGNORECASE)

        q_trans, p_trans = traduzir_query_sqlite(query, params)
        res = self.cursor.execute(q_trans, p_trans)
        if has_returning:
            self.last_returning_id = self.cursor.lastrowid
        else:
            self.last_returning_id = None
        return res

    def fetchone(self):
        if self.last_returning_id is not None:
            val = self.last_returning_id
            self.last_returning_id = None
            return (val,)
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        return self.cursor.close()

class SQLiteConnWrapper:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self):
        return SQLiteCursorWrapper(self.conn.cursor())

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        return self.conn.close()

def abrir_conexao():
    """Retorna uma conexão (PostgreSQL ou SQLite Wrapper)."""
    if st.session_state.get("db_engine") == "postgres":
        return psycopg2.connect(
            host=st.secrets["DB_HOST"],
            database=st.secrets["DB_NAME"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            port=st.secrets["DB_PORT"]
        )
    else:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        return SQLiteConnWrapper(conn)

def executar_query(query, params=None, fetch=None):
    """
    Executa uma query no banco de dados com tratamento automático de exceções e compatibilidade.
    fetch: None, 'one', 'all'
    """
    conn = abrir_conexao()
    cursor = conn.cursor()
    resultado = None
    try:
        cursor.execute(query, params)
        if fetch == 'one':
            resultado = cursor.fetchone()
        elif fetch == 'all':
            resultado = cursor.fetchall()
        conn.commit()
    except Exception as e:
        conn.rollback()
        if isinstance(e, sqlite3.IntegrityError):
            raise psycopg2.IntegrityError(str(e))
        raise e
    finally:
        cursor.close()
        conn.close()
    return resultado

def adicionar_nota_os(id_lanc, nota):
    try:
        desc_atual_db = executar_query("SELECT Descricao FROM FluxoCaixa WHERE IdLancamento = %s", (id_lanc,), fetch='one')
        if desc_atual_db:
            desc_os = desc_atual_db[0] if desc_atual_db[0] else ""
            partes_desc = desc_os.split("--- NOTAS TÉCNICAS ---")
            defeito_atual = partes_desc[0].strip()
            notas_atuais_raw = partes_desc[1].strip() if len(partes_desc) > 1 else ""
            
            agora_str = obter_agora_sp().strftime('%d/%m/%Y %H:%M')
            linha_nova = f"[{agora_str}] {nota.strip()}"
            
            if notas_atuais_raw:
                notas_atualizadas = notas_atuais_raw + "\n" + linha_nova
            else:
                notas_atualizadas = linha_nova
                
            desc_final = defeito_atual + "\n\n--- NOTAS TÉCNICAS ---\n" + notas_atualizadas
            executar_query("UPDATE FluxoCaixa SET Descricao = %s WHERE IdLancamento = %s", (desc_final, id_lanc))
    except Exception:
        pass

def extrair_metodo_pagamento(desc):
    if not desc:
        return "Outro/Avulso"
    desc_upper = desc.upper()
    if "PAGAMENTO: PIX" in desc_upper or "PIX" in desc_upper:
        return "Pix"
    if "PAGAMENTO: DINHEIRO" in desc_upper or "DINHEIRO" in desc_upper or "ESPECIE" in desc_upper:
        return "Dinheiro"
    if "PAGAMENTO: CARTÃO DE CRÉDITO" in desc_upper or "CREDITO" in desc_upper or "CRÉDITO" in desc_upper:
        return "Cartão de Crédito"
    if "PAGAMENTO: CARTÃO DE DÉBITO" in desc_upper or "DEBITO" in desc_upper or "DÉBITO" in desc_upper:
        return "Cartão de Débito"
    if "CARTÃO" in desc_upper or "CARTAO" in desc_upper:
        return "Cartão (Geral)"
    return "Outro/Avulso"

def validar_cpf(cpf):
    # Remove caracteres nao numericos
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11:
        return False
    # CPFs com todos os digitos repetidos sao invalidos
    if cpf in [d * 11 for d in "0123456789"]:
        return False
    
    # Valida primeiro digito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    if resto in [10, 11]:
        resto = 0
    if resto != int(cpf[9]):
        return False
        
    # Valida segundo digito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    if resto in [10, 11]:
        resto = 0
    if resto != int(cpf[10]):
        return False
        
    return True

def validar_cnpj(cnpj):
    # Remove caracteres nao numericos
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) != 14:
        return False
    # CNPJs com todos os digitos repetidos sao invalidos
    if cnpj in [d * 14 for d in "0123456789"]:
        return False
        
    # Valida primeiro digito verificador
    mult1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * mult1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    if int(cnpj[12]) != digito1:
        return False
        
    # Valida segundo digito verificador
    mult2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * mult2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    if int(cnpj[13]) != digito2:
        return False
        
    return True

def validar_documento(doc):
    if not doc:
        return False
    doc_clean = re.sub(r'\D', '', doc)
    if len(doc_clean) == 11:
        return validar_cpf(doc_clean)
    elif len(doc_clean) == 14:
        return validar_cnpj(doc_clean)
    return False

def buscar_cep(cep):
    # Remove caracteres nao numericos
    cep_clean = re.sub(r'\D', '', cep)
    if len(cep_clean) != 8:
        return None
    try:
        response = requests.get(f"https://viacep.com.br/ws/{cep_clean}/json/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "erro" not in data:
                return data
    except Exception:
        pass
    return None

# =========================================================================
# 2. SISTEMA DE DESIGN (CSS CUSTOMIZADO - SPEEDY CELL)
# =========================================================================
st.markdown("""
<script>
    try {
        if (window.parent && window.parent.document) {
            window.parent.document.title = "Speedy Cell ERP";
        }
        document.title = "Speedy Cell ERP";
    } catch(e) {}
</script>
<style>
    /* Carrega fonte Outfit do Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

    /* Estilos Globais */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        font-family: 'Outfit', sans-serif;
    }

    /* Títulos e Headers */
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        color: #0A223B;
    }

    /* Cartão de Métrica Customizado */
    .metric-card {
        background: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        padding: 24px;
        transition: all 0.25s ease-in-out;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #00AEEF, #0077C8);
        opacity: 0;
        transition: opacity 0.25s ease-in-out;
    }
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 24px -8px rgba(0, 174, 239, 0.25);
        border-color: #00AEEF;
    }
    .metric-card:hover::before {
        opacity: 1;
    }
    .metric-title {
        font-size: 13px;
        color: #64748B;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 32px;
        color: #0A223B;
        font-weight: 800;
        margin-top: 8px;
    }
    
    /* Cores de Métricas */
    .val-primary { color: #00AEEF; font-weight: 800; }
    .val-success { color: #10B981; }
    .val-warning { color: #F59E0B; }
    .val-danger { color: #EF4444; }

    /* Botões Globais do Sistema */
    button[kind="primary"], .stButton > button, div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(135deg, #00AEEF 0%, #0077C8 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(0, 174, 239, 0.35) !important;
        transition: all 0.2s ease-in-out !important;
    }
    button[kind="primary"]:hover, .stButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0, 174, 239, 0.55) !important;
        background: linear-gradient(135deg, #00C2FF 0%, #0088E8 100%) !important;
    }

    /* Badges de Status do Estoque / O.S. */
    .badge {
        padding: 6px 14px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 700;
        display: inline-block;
        text-align: center;
    }
    .badge-available { background-color: rgba(16, 185, 129, 0.12); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.2); }
    .badge-sold { background-color: rgba(0, 174, 239, 0.12); color: #00AEEF; border: 1px solid rgba(0, 174, 239, 0.25); }
    .badge-maintenance { background-color: rgba(245, 158, 11, 0.12); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.2); }
    .badge-ready { background-color: rgba(0, 194, 255, 0.15); color: #0088CC; border: 1px solid rgba(0, 194, 255, 0.3); }
    .badge-delivered { background-color: rgba(100, 116, 139, 0.12); color: #64748B; border: 1px solid rgba(100, 116, 139, 0.2); }

    /* Estilo do Menu Sidebar */
    .sidebar-header {
        text-align: center;
        padding: 15px 0;
        border-bottom: 1px solid #E2E8F0;
        margin-bottom: 20px;
    }
    .sidebar-title {
        font-size: 22px;
        font-weight: 800;
        background: linear-gradient(135deg, #00AEEF 0%, #0077C8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .sidebar-subtitle {
        font-size: 12px;
        color: #64748B;
        font-weight: 500;
        margin-top: 4px;
    }

    /* Logo na barra lateral */
    [data-testid="stSidebar"] [data-testid="stImage"] img {
        border-radius: 14px !important;
        box-shadow: 0 4px 14px rgba(0, 174, 239, 0.15) !important;
        border: 1px solid rgba(0, 174, 239, 0.25) !important;
        background-color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================================
# 3. CONTROLE DE SESSÃO E LOGIN
# =========================================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "ocultar_valores" not in st.session_state:
    st.session_state.ocultar_valores = False

def realizar_login(usuario, senha):
    try:
        usuario_clean = usuario.strip().lower()
        user_data = executar_query("""
            SELECT Senha, Role, Nome, Usuario 
            FROM Usuarios 
            WHERE LOWER(TRIM(Usuario)) = %s
        """, (usuario_clean,), fetch='one')
        
        if not user_data:
            st.error(f"Usuário '{usuario.strip()}' não foi encontrado. Se você ainda não possui conta neste banco de dados, acesse a aba '📝 Criar Conta'.")
        elif user_data[0] == senha:
            st.session_state.logged_in = True
            st.session_state.user_role = user_data[1]
            st.session_state.user_name = user_data[2]
            st.session_state.ocultar_valores = False
            st.success(f"Bem-vindo, {user_data[2]}!")
            st.rerun()
        else:
            st.error("Senha incorreta. Verifique a senha digitada.")
    except Exception as e:
        st.error(f"Erro de conexão com o banco: {e}")

if not st.session_state.logged_in:
    # CSS customizado para fundo escuro e estilização premium da tela de login
    st.markdown("""
    <style>
        /* Fundo escuro radial matching com o logo da Speedy Cell */
        [data-testid="stAppViewContainer"] {
            background-color: #050B14 !important;
            background-image: radial-gradient(circle at 30% 30%, #08243E 0%, #050B14 85%) !important;
        }
        [data-testid="stHeader"] {
            background: transparent !important;
        }
        
        /* Ajusta o espaçamento do container principal */
        .block-container {
            padding-top: 4rem !important;
            padding-bottom: 2rem !important;
        }
        
        /* Rótulos (Labels) */
        label {
            color: #94A3B8 !important;
            font-size: 14px !important;
            font-weight: 500 !important;
        }
        
        /* Inputs de texto escuros (Prevenção de fundo branco e letra branca invisível) */
        .stTextInput input {
            color: #FFFFFF !important;
            background-color: #0E1726 !important;
            border-radius: 10px !important;
            border: none !important;
        }
        
        /* Containers internos do baseweb do Streamlit */
        div[data-baseweb="base-input"], div[data-baseweb="input"] {
            background-color: #0E1726 !important;
            border: 1px solid #162A45 !important;
            border-radius: 10px !important;
        }
        div[data-baseweb="input"]:focus-within {
            border-color: #00AEEF !important;
            box-shadow: 0 0 0 2px rgba(0, 174, 239, 0.25) !important;
        }
        
        /* Garantir texto legível nas opções de Radio Buttons */
        .stRadio p, .stRadio label, .stRadio span {
            color: #E2E8F0 !important;
            font-size: 14px !important;
        }
        
        /* Estilização para as Abas (Tabs) do Streamlit no tema escuro */
        button[data-baseweb="tab"] {
            background-color: transparent !important;
            border: none !important;
        }
        button[data-baseweb="tab"] p {
            color: #94A3B8 !important;
            font-weight: 600 !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] p {
            color: #00C2FF !important;
            font-weight: 700 !important;
        }
        div[data-baseweb="tab-highlight"] {
            background-color: #00AEEF !important;
        }
        div[data-baseweb="tab-border"] {
            background-color: #162A45 !important;
        }
        
        /* Card do formulário de login */
        .login-card {
            background-color: rgba(10, 22, 38, 0.85);
            border: 1px solid rgba(0, 174, 239, 0.3);
            border-radius: 20px;
            padding: 35px;
            box-shadow: 0 15px 35px -10px rgba(0, 0, 0, 0.8), 0 0 25px rgba(0, 174, 239, 0.15);
            backdrop-filter: blur(12px);
        }

        /* Estilização elegante da imagem do logo */
        [data-testid="stImage"] img {
            border-radius: 20px !important;
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.4), 0 0 20px rgba(0, 174, 239, 0.3) !important;
            border: 2px solid rgba(0, 174, 239, 0.4) !important;
            background-color: #FFFFFF !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Layout em duas colunas: Esquerda (Logo completo), Direita (Formulário)
    col_l1, col_l2 = st.columns([1.1, 0.9], gap="large")
    
    with col_l1:
        # Exibir logotipo da Speedy Cell
        st.image(LOGO_PATH, use_container_width=True)
        
    with col_l2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="background: linear-gradient(135deg, #00C2FF 0%, #0077C8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; font-family: 'Outfit'; font-size: 34px; font-weight: 800; letter-spacing: -0.5px;">Speedy Cell ERP</h2>
            <p style="color: #94A3B8; font-size: 14px; margin-top: 6px; font-weight: 500;">⚡ Gestão & Assistência Técnica Especializada</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Verifica se o banco já possui usuários cadastrados
        total_usuarios = 0
        try:
            total_usuarios = executar_query("SELECT COUNT(*) FROM Usuarios", fetch='one')[0]
        except Exception:
            pass

        tab_login, tab_cadastro = st.tabs(["🔒 Entrar", "📝 Criar Conta"])
        
        with tab_login:
            if total_usuarios == 1:
                st.caption("💡 *Dica:* Se este for seu primeiro acesso no banco local, use **adm** (senha: **admin**) ou cadastre sua conta na aba 'Criar Conta'.")
            
            with st.form("form_login", clear_on_submit=False):
                user_input = st.text_input("Usuário:", key="login_usuario")
                pass_input = st.text_input("Senha:", type="password", key="login_senha")
                
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                submit_btn = st.form_submit_button("Acessar Sistema", type="primary", use_container_width=True)
                
                if submit_btn:
                    if user_input and pass_input:
                        realizar_login(user_input, pass_input)
                    else:
                        st.warning("Preencha o usuário e a senha.")
                        
        with tab_cadastro:
            with st.form("form_cadastro", clear_on_submit=False):
                cad_nome = st.text_input("Nome Completo:", placeholder="Ex: Kaue Arruda", key="cad_nome")
                cad_usuario = st.text_input("Nome de Usuário (login):", placeholder="Ex: kaue", key="cad_usuario")
                cad_senha = st.text_input("Senha:", type="password", key="cad_senha")
                
                cad_role_desc = st.radio(
                    "Tipo de Conta (Nível de Acesso):",
                    ["Lojista (Permissão padrão para vendas/cadastro)", "Administrador (Permissão completa)"],
                    key="cad_role"
                )
                
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                submit_cad = st.form_submit_button("Finalizar Cadastro", type="primary", use_container_width=True)
                if submit_cad:
                    if cad_nome and cad_usuario and cad_senha:
                        cad_usuario_clean = cad_usuario.strip().lower()
                        role_desejada = "adm" if "Administrador" in cad_role_desc else "lojista"
                        
                        try:
                            executar_query("""
                                INSERT INTO Usuarios (Usuario, Senha, Nome, Role)
                                VALUES (%s, %s, %s, %s)
                            """, (cad_usuario_clean, cad_senha, cad_nome, role_desejada))
                            st.session_state.logged_in = True
                            st.session_state.user_role = role_desejada
                            st.session_state.user_name = cad_nome
                            st.session_state.ocultar_valores = False
                            st.toast(f"Conta '{cad_usuario_clean}' criada com sucesso!", icon="🎉")
                            st.rerun()
                        except psycopg2.IntegrityError:
                            st.error("Erro: Este nome de usuário já está sendo utilizado.")
                        except Exception as e:
                            st.error(f"Erro ao cadastrar conta: {e}")
                    else:
                        st.warning("Preencha todos os campos obrigatórios para se cadastrar.")
                    
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# =========================================================================
# 4. SIDEBAR - MENU DE NAVEGAÇÃO
# =========================================================================
with st.sidebar:
    # Exibir logotipo da Speedy Cell centralizado no topo da barra lateral
    st.image(LOGO_PATH, use_container_width=True)
    
    st.markdown("""
    <div class="sidebar-header" style="margin-top: 5px; margin-bottom: 15px;">
        <h2 class="sidebar-title">⚡ Speedy Cell ERP</h2>
        <p class="sidebar-subtitle">Gestão & Assistência Técnica</p>
    </div>
    """, unsafe_allow_html=True)
    
    opcoes_menu = [
        "🏠 Painel Geral (Dashboard)", 
        "👤 Clientes (CRM)", 
        "📦 Produtos & Estoque", 
        "📝 Ordens de Serviço (O.S.)"
    ]
    if st.session_state.user_role == 'adm':
        opcoes_menu.append("📊 Financeiro & Caixa")
        opcoes_menu.append("👥 Contas & Acessos")
        
    opcao = st.radio("Navegação do Sistema:", opcoes_menu)
    
    st.write("---")
    # Indicador e Configuração do Banco de Dados
    if st.session_state.get("db_engine") == "postgres":
        st.success("🟢 Conectado à Nuvem (Supabase)")
    else:
        st.info("💾 **Banco Local Ativo (SQLite)**")
        # Mostra o status somente se o usuário realmente configurou credenciais que não conectaram
        host_configurado = str(st.secrets.get("DB_HOST", "")).strip() if "DB_HOST" in st.secrets else ""
        if host_configurado and st.session_state.get("db_error_msg"):
            with st.expander("ℹ️ Status da Conexão Nuvem"):
                st.caption(f"Supabase offline/aguardando: {st.session_state.db_error_msg[:120]}...")
                if st.button("🔄 Tentar Reconectar", use_container_width=True):
                    st.session_state.db_engine = None
                    st.rerun()

    st.caption(f"Usuário: {st.session_state.user_name}")
    
    # Botão para ocultar/mostrar valores financeiros
    label_olho = "👁️ Mostrar Valores" if st.session_state.ocultar_valores else "🙈 Ocultar Valores"
    if st.button(label_olho, use_container_width=True, key="btn_toggle_olho"):
        st.session_state.ocultar_valores = not st.session_state.ocultar_valores
        st.rerun()
        
    if st.button("Sair", use_container_width=True, key="btn_sair"):
        st.session_state.logged_in = False
        st.session_state.user_role = ""
        st.session_state.user_name = ""
        st.session_state.ocultar_valores = False
        st.rerun()

# =========================================================================
# 4. TELA: PAINEL GERAL (DASHBOARD)
# =========================================================================
if opcao == "🏠 Painel Geral (Dashboard)":
    st.title("🏠 Painel de Indicadores Gerais")
    st.markdown("Visão consolidada da saúde da loja em tempo real.")
    st.write("---")
    
    try:
        # Busca faturamento e despesas
        financeiro = executar_query("""
            SELECT 
                SUM(CASE WHEN Tipo = 'E' THEN Valor ELSE 0 END) as receita,
                SUM(CASE WHEN Tipo = 'S' THEN Valor ELSE 0 END) as despesa
            FROM FluxoCaixa
        """, fetch='one')
        receita = float(financeiro[0]) if financeiro[0] else 0.0
        despesa = float(financeiro[1]) if financeiro[1] else 0.0
        saldo = receita - despesa

        # Busca quantidade de clientes
        total_clientes = executar_query("SELECT COUNT(*) FROM Clientes", fetch='one')[0]

        # Busca quantidade de O.S. ativas (Manutencao ou Pronto)
        total_os_ativas = executar_query("""
            SELECT COUNT(*) FROM ItensEstoque WHERE Status IN ('Orcamento', 'Manutencao', 'Pronto', 'Recusado')
        """, fetch='one')[0]

        # Busca quantidade de produtos com estoque baixo (menor ou igual a 1 unidade disponível), desconsiderando aparelhos de O.S.
        baixo_estoque = executar_query("""
            SELECT p.Marca, p.Modelo, COUNT(i.IdItem) AS Qtd
            FROM Produtos p
            LEFT JOIN ItensEstoque i ON p.IdProduto = i.IdProduto AND LOWER(i.Status) = 'disponivel'
            WHERE p.Ativo = true
              AND p.IdProduto NOT IN (
                  SELECT DISTINCT IdProduto 
                  FROM ItensEstoque 
                  WHERE Status IN ('Orcamento', 'Manutencao', 'Pronto', 'Recusado', 'Entregue')
              )
            GROUP BY p.IdProduto, p.Marca, p.Modelo
            HAVING COUNT(i.IdItem) <= 1
        """, fetch='all')
        total_baixo_estoque = len(baixo_estoque)

        # Renderizando as métricas
        if st.session_state.user_role == 'adm':
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                saldo_display = formatar_brl(saldo) if not st.session_state.ocultar_valores else "R$ ••••••"
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Saldo Líquido</div>
                    <div class="metric-value val-success">{saldo_display}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Clientes Cadastrados</div>
                    <div class="metric-value val-primary">{total_clientes}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Ordens de Serviço Ativas</div>
                    <div class="metric-value val-warning">{total_os_ativas}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Alertas de Estoque Baixo</div>
                    <div class="metric-value val-danger">{total_baixo_estoque}</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("---")
            
            # 📈 Desempenho Financeiro Recente (Gráfico)
            st.subheader("📈 Desempenho Financeiro (Últimos 30 Dias)")
            
            chart_dados = executar_query("""
                SELECT 
                    CAST(DataLancamento AS DATE) as data_dia,
                    SUM(CASE WHEN Tipo = 'E' THEN Valor ELSE 0 END) as receitas,
                    SUM(CASE WHEN Tipo = 'S' THEN Valor ELSE 0 END) as despesas
                FROM FluxoCaixa
                WHERE DataLancamento >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY CAST(DataLancamento AS DATE)
                ORDER BY data_dia ASC
            """, fetch='all')
            
            if chart_dados:
                df_chart = pd.DataFrame(chart_dados, columns=["Data", "Receitas (R$)", "Despesas (R$)"])
                # Converte as colunas de tipo Decimal para float (corrige escala e orientacao vertical do grafico)
                df_chart["Receitas (R$)"] = df_chart["Receitas (R$)"].astype(float)
                df_chart["Despesas (R$)"] = df_chart["Despesas (R$)"].astype(float)
                df_chart["Data"] = df_chart["Data"].apply(lambda d: d.strftime('%d/%m'))
                df_chart = df_chart.set_index("Data")
                
                if not st.session_state.ocultar_valores:
                    st.bar_chart(df_chart, use_container_width=True)
                else:
                    st.info("📊 Gráfico de desempenho financeiro ocultado.")
                
                # Exibe um resumo explicativo legivel abaixo do grafico
                soma_rec = df_chart["Receitas (R$)"].sum()
                soma_des = df_chart["Despesas (R$)"].sum()
                saldo_total = soma_rec - soma_des
                
                soma_rec_display = formatar_brl(soma_rec) if not st.session_state.ocultar_valores else "R$ ••••••"
                soma_des_display = formatar_brl(soma_des) if not st.session_state.ocultar_valores else "R$ ••••••"
                saldo_total_display = formatar_brl(saldo_total) if not st.session_state.ocultar_valores else "R$ ••••••"
                
                col_c1, col_c2, col_c3 = st.columns(3)
                with col_c1:
                    st.markdown(f"**Total Receitas no Período:** <span style='color:#10B981;'>{soma_rec_display}</span>", unsafe_allow_html=True)
                with col_c2:
                    st.markdown(f"**Total Despesas no Período:** <span style='color:#EF4444;'>{soma_des_display}</span>", unsafe_allow_html=True)
                with col_c3:
                    st.markdown(f"**Saldo Líquido do Período:** <span style='color:#3B82F6; font-weight:bold;'>{saldo_total_display}</span>", unsafe_allow_html=True)
            else:
                st.info("Nenhuma transação financeira registrada nos últimos 30 dias para exibir no gráfico.")
                
            st.write("---")
            
            # Grid inferior com Alertas de Estoque Baixo e O.S. Pendentes
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.subheader("⚠️ Produtos com Estoque Baixo ou Crítico")
                if baixo_estoque:
                    df_baixo = pd.DataFrame(baixo_estoque, columns=["Marca", "Modelo", "Qtd Disponível"])
                    st.dataframe(df_baixo, use_container_width=True, hide_index=True)
                else:
                    st.success("Estoque saudável! Nenhum produto com estoque crítico.")
                    
            with col_g2:
                st.subheader("🛠️ Ordens de Serviço Ativas (Recentes)")
                os_ativas = executar_query("""
                    SELECT f.IdLancamento, c.Nome, p.Marca, p.Modelo, i.Status, f.Valor
                    FROM FluxoCaixa f
                    JOIN Clientes c ON f.IdCliente = c.IdCliente
                    JOIN ItensEstoque i ON f.IdItem = i.IdItem
                    JOIN Produtos p ON i.IdProduto = p.IdProduto
                    WHERE i.Status IN ('Orcamento', 'Manutencao', 'Pronto', 'Recusado') AND f.Descricao LIKE '[ASSISTENCIA]%%'
                    ORDER BY f.IdLancamento DESC LIMIT 5
                """, fetch='all')
                if os_ativas:
                    df_os = pd.DataFrame(os_ativas, columns=["Nº OS", "Cliente", "Marca", "Modelo", "Status", "Preço (R$)"])
                    if st.session_state.ocultar_valores:
                        df_os["Preço (R$)"] = "••••"
                    st.dataframe(df_os, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma Ordem de Serviço em aberto no momento.")
        else:
            # Lojista vê apenas Clientes Cadastrados e OS Ativas
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Clientes Cadastrados</div>
                    <div class="metric-value val-primary">{total_clientes}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Ordens de Serviço Ativas</div>
                    <div class="metric-value val-warning">{total_os_ativas}</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("---")
            st.subheader("🛠️ Ordens de Serviço Ativas (Recentes)")
            os_ativas = executar_query("""
                SELECT f.IdLancamento, c.Nome, p.Marca, p.Modelo, i.Status
                FROM FluxoCaixa f
                JOIN Clientes c ON f.IdCliente = c.IdCliente
                JOIN ItensEstoque i ON f.IdItem = i.IdItem
                JOIN Produtos p ON i.IdProduto = p.IdProduto
                WHERE i.Status IN ('Orcamento', 'Manutencao', 'Pronto', 'Recusado') AND f.Descricao LIKE '[ASSISTENCIA]%%'
                ORDER BY f.IdLancamento DESC LIMIT 5
            """, fetch='all')
            if os_ativas:
                df_os = pd.DataFrame(os_ativas, columns=["Nº OS", "Cliente", "Marca", "Modelo", "Status"])
                st.dataframe(df_os, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma Ordem de Serviço em aberto no momento.")

    except Exception as e:
        st.error(f"Erro ao carregar painel de indicadores: {e}")

# =========================================================================
# 5. TELA: CLIENTES (CRUD COMPLETO)
# =========================================================================
elif opcao == "👤 Clientes (CRM)":
    st.title("👤 Gerenciamento de Clientes (CRM)")
    aba_lista, aba_cadastrar = st.tabs(["🔍 Consultar e Editar Clientes", "➕ Cadastrar Novo Cliente"])
    
    with aba_cadastrar:
        st.header("Cadastrar Novo Cliente")
        
        # Inicializando session state do CEP de cadastro se nao existir
        if "ultimo_cep_inserido" not in st.session_state:
            st.session_state.ultimo_cep_inserido = ""
        if "cep_data_inserido" not in st.session_state:
            st.session_state.cep_data_inserido = {"logradouro": "", "bairro": "", "localidade": "", "uf": ""}
        if "cep_key_counter" not in st.session_state:
            st.session_state.cep_key_counter = 0

        with st.container(border=True):
            st.markdown("<h3 style='margin-top:0;'>Ficha de Cadastro</h3>", unsafe_allow_html=True)
            
            st.markdown("##### Informações Pessoais")
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                nome = st.text_input("Nome Completo:", key="cad_nome")
                whatsapp = st.text_input("WhatsApp (com DDD):", placeholder="Ex: 11988887777", key="cad_whatsapp")
            with col_p2:
                cpf_input = st.text_input("CPF ou CNPJ (somente numeros):", placeholder="Ex: 12345678909 ou 12345678000195", max_chars=14, key="cad_cpf")
                email = st.text_input("E-mail:", key="cad_email")
            
            st.markdown("##### Endereço Residencial")
            
            # Row 1 of address: CEP, Logradouro, Número, Complemento
            col_e1, col_e2, col_e3, col_e4 = st.columns([1.5, 3, 1, 1.5])
            with col_e1:
                cep_key = f"inserir_cep_{st.session_state.cep_key_counter}"
                cep_val = st.text_input("CEP (somente numeros):", placeholder="Ex: 01103010", max_chars=8, key=cep_key, help="Digite os 8 numeros do CEP para buscar o endereco automaticamente")
            
            cep_clean = re.sub(r'\D', '', cep_val)
            if len(cep_clean) == 8 and cep_clean != st.session_state.ultimo_cep_inserido:
                data_cep = buscar_cep(cep_clean)
                if data_cep:
                    st.session_state.cep_data_inserido = data_cep
                    st.session_state.ultimo_cep_inserido = cep_clean
                    st.session_state["cad_logradouro"] = data_cep.get("logradouro", "")
                    st.session_state["cad_bairro"] = data_cep.get("bairro", "")
                    st.session_state["cad_cidade"] = data_cep.get("localidade", "")
                    st.session_state["cad_estado"] = data_cep.get("uf", "")
                    st.toast("Endereço preenchido automaticamente!", icon="📍")
                else:
                    st.error("CEP nao localizado.")
            
            with col_e2:
                logradouro = st.text_input("Logradouro (Rua/Avenida):", value=st.session_state.cep_data_inserido.get("logradouro", ""), key="cad_logradouro")
            with col_e3:
                numero = st.text_input("Numero:", key="cad_numero")
            with col_e4:
                complemento = st.text_input("Complemento:", key="cad_complemento")
                
            col_e5, col_e6, col_e7 = st.columns([2, 2, 1])
            with col_e5:
                bairro = st.text_input("Bairro:", value=st.session_state.cep_data_inserido.get("bairro", ""), key="cad_bairro")
            with col_e6:
                cidade = st.text_input("Cidade:", value=st.session_state.cep_data_inserido.get("localidade", ""), key="cad_cidade")
            with col_e7:
                estado = st.text_input("UF:", value=st.session_state.cep_data_inserido.get("uf", ""), key="cad_estado")
                
            st.write("")
            if st.button("Salvar Cliente", type="primary", use_container_width=True, key="btn_salvar_cliente_novo"):
                if nome and whatsapp:
                    cpf_clean = re.sub(r'\D', '', cpf_input) if cpf_input else ""
                    if cpf_clean and not validar_documento(cpf_clean):
                        st.error("Erro: O CPF/CNPJ digitado é inválido!")
                    else:
                        salvou_com_sucesso = False
                        try:
                            executar_query("""
                                INSERT INTO Clientes (Nome, WhatsApp, Email, Documento, CEP, Logradouro, Numero, Complemento, Bairro, Cidade, Estado)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (nome, whatsapp, email if email else None, cpf_clean if cpf_clean else None, 
                                  cep_clean if cep_clean else None, logradouro, numero, complemento, bairro, cidade, estado))
                            salvou_com_sucesso = True
                        except psycopg2.IntegrityError as e:
                            err_msg = str(e)
                            if "whatsapp" in err_msg:
                                st.error("Erro: O WhatsApp digitado já está cadastrado para outro cliente.")
                            elif "documento" in err_msg:
                                st.error("Erro: O CPF/CNPJ digitado já está cadastrado para outro cliente.")
                            else:
                                st.error("Erro: WhatsApp ou CPF/CNPJ já cadastrado no sistema.")
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                            
                        if salvou_com_sucesso:
                            # Limpa os campos do formulário redefinindo as chaves no session_state
                            st.session_state.ultimo_cep_inserido = ""
                            st.session_state.cep_data_inserido = {"logradouro": "", "bairro": "", "localidade": "", "uf": ""}
                            st.session_state.cep_key_counter += 1
                            
                            for k in ["cad_nome", "cad_whatsapp", "cad_cpf", "cad_email", "cad_logradouro", "cad_numero", "cad_complemento", "cad_bairro", "cad_cidade", "cad_estado"]:
                                if k in st.session_state:
                                    try:
                                        st.session_state[k] = ""
                                    except Exception:
                                        pass
                                    
                            st.success(f"Cliente '{nome}' cadastrado com sucesso!")
                            st.toast(f"Cliente '{nome}' cadastrado com sucesso!", icon="🎉")
                            st.rerun()
                else:
                    st.warning("Nome e WhatsApp são obrigatórios.")
                        
    with aba_lista:
        st.header("Lista de Clientes")
        termo_busca = st.text_input("Buscar cliente por Nome, WhatsApp, CPF/CNPJ ou CEP:")
        
        # Query com filtro atualizada para trazer todos os campos
        query_busca = """
            SELECT IdCliente, Nome, WhatsApp, Email, Documento, CEP, Logradouro, Numero, Complemento, Bairro, Cidade, Estado
            FROM Clientes 
            WHERE Nome ILIKE %s OR WhatsApp ILIKE %s OR Documento ILIKE %s OR CEP ILIKE %s
            ORDER BY Nome ASC
        """
        param_busca = f"%{termo_busca}%"
        clientes = executar_query(query_busca, (param_busca, param_busca, param_busca, param_busca), fetch='all')
        
        if clientes:
            # Mostra tabela simples
            tabela_dados = []
            for c in clientes:
                tabela_dados.append([c[0], c[1], c[2], c[3] if c[3] else "---", c[4] if c[4] else "---", f"{c[6] if c[6] else ''}, {c[7] if c[7] else ''} - {c[10] if c[10] else ''}"])
            df_clientes = pd.DataFrame(tabela_dados, columns=["ID", "Nome", "WhatsApp", "E-mail", "CPF/CNPJ", "Endereco"])
            st.dataframe(df_clientes, use_container_width=True, hide_index=True)
            
            # Botão de exportação de Clientes
            df_export = df_clientes.copy()
            df_export["WhatsApp"] = df_export["WhatsApp"].apply(lambda x: f'="{x}"' if x and x != "---" else x)
            df_export["CPF/CNPJ"] = df_export["CPF/CNPJ"].apply(lambda x: f'="{x}"' if x and x != "---" else x)
            csv_clientes = df_export.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button(
                label="📥 Exportar Clientes para Excel (CSV)",
                data=csv_clientes,
                file_name="clientes_speedycell.csv",
                mime="text/csv",
                key="btn_download_clientes"
            )
            
            st.write("---")
            st.subheader("Editar / Excluir Cadastro de Cliente")
            
            lista_clientes_select = {f"{c[1]} (WA: {c[2]})": c for c in clientes}
            cliente_selecionado_str = st.selectbox("Selecione o Cliente para Modificar:", list(lista_clientes_select.keys()))
            
            if cliente_selecionado_str:
                cli = lista_clientes_select[cliente_selecionado_str]
                id_cli, nome_cli, wa_cli, email_cli, doc_cli, cep_cli, log_cli, num_cli, comp_cli, bai_cli, cid_cli, est_cli = cli
                
                # Inicializando session state do CEP de edicao para este cliente se nao existir ou se mudou o cliente
                if "cliente_selecionado_id" not in st.session_state or st.session_state.cliente_selecionado_id != id_cli:
                    st.session_state.cliente_selecionado_id = id_cli
                    cep_clean_val = re.sub(r'\D', '', cep_cli) if cep_cli else ""
                    st.session_state.ultimo_cep_editado = cep_clean_val
                    st.session_state["edit_cep_input"] = cep_clean_val
                    
                    # Se o cliente já tem CEP no banco, mas o endereço está vazio (ex: falha de rede ao cadastrar),
                    # tenta buscar na API para preencher os dados de endereço automaticamente na edição.
                    data_cep_edit = None
                    if len(cep_clean_val) == 8 and (not log_cli or not bai_cli or not cid_cli):
                        data_cep_edit = buscar_cep(cep_clean_val)
                    
                    if data_cep_edit:
                        st.session_state.cep_data_editado = data_cep_edit
                        st.session_state["edit_logradouro"] = data_cep_edit.get("logradouro", "")
                        st.session_state["edit_bairro"] = data_cep_edit.get("bairro", "")
                        st.session_state["edit_cidade"] = data_cep_edit.get("localidade", "")
                        st.session_state["edit_estado"] = data_cep_edit.get("uf", "")
                    else:
                        st.session_state.cep_data_editado = {
                            "logradouro": log_cli if log_cli else "",
                            "bairro": bai_cli if bai_cli else "",
                            "localidade": cid_cli if cid_cli else "",
                            "uf": est_cli if est_cli else ""
                        }
                        st.session_state["edit_logradouro"] = log_cli if log_cli else ""
                        st.session_state["edit_bairro"] = bai_cli if bai_cli else ""
                        st.session_state["edit_cidade"] = cid_cli if cid_cli else ""
                        st.session_state["edit_estado"] = est_cli if est_cli else ""
                        
                    st.session_state["edit_nome"] = nome_cli
                    st.session_state["edit_whatsapp"] = wa_cli
                    st.session_state["edit_cpf"] = doc_cli if doc_cli else ""
                    st.session_state["edit_email"] = email_cli if email_cli else ""
                    st.session_state["edit_numero"] = num_cli if num_cli else ""
                    st.session_state["edit_complemento"] = comp_cli if comp_cli else ""

                with st.container(border=True):
                    st.markdown(f"#### ✏️ Edicao de Ficha: {nome_cli}")
                    
                    st.markdown("##### Informacoes Pessoais")
                    col_pe1, col_pe2 = st.columns(2)
                    with col_pe1:
                        novo_nome = st.text_input("Nome Completo:", value=nome_cli, key="edit_nome")
                        novo_whatsapp = st.text_input("WhatsApp:", value=wa_cli, key="edit_whatsapp")
                    with col_pe2:
                        novo_documento = st.text_input("CPF ou CNPJ (somente numeros):", value=doc_cli if doc_cli else "", max_chars=14, key="edit_cpf")
                        novo_email = st.text_input("E-mail:", value=email_cli if email_cli else "", key="edit_email")
                        
                    st.markdown("##### Endereco Residencial")
                    col_ee1, col_ee2, col_ee3, col_ee4 = st.columns([1.5, 3, 1, 1.5])
                    with col_ee1:
                        cep_edit_input = st.text_input("CEP (somente numeros):", value=st.session_state.ultimo_cep_editado, key="edit_cep_input", max_chars=8)
                        
                    cep_edit_clean = re.sub(r'\D', '', cep_edit_input)
                    if len(cep_edit_clean) == 8 and cep_edit_clean != re.sub(r'\D', '', st.session_state.ultimo_cep_editado):
                        data_cep_edit = buscar_cep(cep_edit_clean)
                        if data_cep_edit:
                            st.session_state.cep_data_editado = data_cep_edit
                            st.session_state.ultimo_cep_editado = cep_edit_clean
                            st.session_state["edit_logradouro"] = data_cep_edit.get("logradouro", "")
                            st.session_state["edit_bairro"] = data_cep_edit.get("bairro", "")
                            st.session_state["edit_cidade"] = data_cep_edit.get("localidade", "")
                            st.session_state["edit_estado"] = data_cep_edit.get("uf", "")
                            st.toast("Endereco de edicao auto-preenchido!", icon="📍")
                            st.rerun()
                        else:
                            st.error("CEP nao localizado.")

                    with col_ee2:
                        novo_log = st.text_input("Logradouro:", value=st.session_state.cep_data_editado.get("logradouro", ""), key="edit_logradouro")
                    with col_ee3:
                        novo_num = st.text_input("Numero:", value=num_cli if num_cli else "", key="edit_numero")
                    with col_ee4:
                        novo_comp = st.text_input("Complemento:", value=comp_cli if comp_cli else "", key="edit_complemento")
                        
                    col_ee5, col_ee6, col_ee7 = st.columns([2, 2, 1])
                    with col_ee5:
                        novo_bai = st.text_input("Bairro:", value=st.session_state.cep_data_editado.get("bairro", ""), key="edit_bairro")
                    with col_ee6:
                        novo_cid = st.text_input("Cidade:", value=st.session_state.cep_data_editado.get("localidade", ""), key="edit_cidade")
                    with col_ee7:
                        novo_est = st.text_input("UF:", value=st.session_state.cep_data_editado.get("uf", ""), key="edit_estado")
                        
                    st.write("")
                    if st.button("Salvar Alteracoes", type="primary", use_container_width=True, key="btn_salvar_alteracoes_cliente"):
                        if novo_nome and novo_whatsapp:
                            cpf_edit_clean = re.sub(r'\D', '', novo_documento) if novo_documento else ""
                            if cpf_edit_clean and not validar_documento(cpf_edit_clean):
                                st.error("Erro: O CPF/CNPJ digitado é inválido!")
                            else:
                                atualizou_com_sucesso = False
                                try:
                                    executar_query("""
                                        UPDATE Clientes 
                                        SET Nome = %s, Documento = %s, WhatsApp = %s, Email = %s,
                                            CEP = %s, Logradouro = %s, Numero = %s, Complemento = %s,
                                            Bairro = %s, Cidade = %s, Estado = %s
                                        WHERE IdCliente = %s
                                    """, (novo_nome, cpf_edit_clean if cpf_edit_clean else None, novo_whatsapp, novo_email if novo_email else None,
                                          cep_edit_clean if cep_edit_clean else None, novo_log, novo_num, novo_comp, novo_bai, novo_cid, novo_est, id_cli))
                                    atualizou_com_sucesso = True
                                except psycopg2.IntegrityError as e:
                                    err_msg = str(e)
                                    if "whatsapp" in err_msg:
                                        st.error("Erro: O WhatsApp digitado já está cadastrado para outro cliente.")
                                    elif "documento" in err_msg:
                                        st.error("Erro: O CPF/CNPJ digitado já está cadastrado para outro cliente.")
                                    else:
                                        st.error("Erro: WhatsApp ou CPF/CNPJ já cadastrado no sistema.")
                                except Exception as e:
                                    st.error(f"Erro ao atualizar: {e}")
                                    
                                if atualizou_com_sucesso:
                                    # Limpa estado de edicao
                                    if "cliente_selecionado_id" in st.session_state:
                                        try:
                                            del st.session_state.cliente_selecionado_id
                                        except Exception:
                                            pass
                                        
                                    st.success(f"Cadastro de '{novo_nome}' atualizado com sucesso!")
                                    st.rerun()
                        else:
                            st.warning("Nome e WhatsApp sao obrigatorios.")
                    
                    # Exclusão fora do formulário (apenas ADM)
                    if st.session_state.user_role == 'adm':
                        st.write("---")
                        st.write("🗑️ **Excluir Cliente**")
                        confirmar_exclusao = st.checkbox(f"Confirmo que desejo excluir permanentemente o cliente '{nome_cli}' e desvincular suas ordens antigas.", key="conf_del_cli")
                        if st.button("Excluir Cliente Permanentemente", type="primary", disabled=not confirmar_exclusao, use_container_width=True):
                            try:
                                executar_query("DELETE FROM Clientes WHERE IdCliente = %s", (id_cli,))
                                st.success(f"Cliente '{nome_cli}' excluido com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir cliente: {e}")
        else:
            st.info("Nenhum cliente cadastrado ou correspondente a busca.")

# =========================================================================
# 6. TELA: PRODUTOS & ESTOQUE (CRUD COMPLETO)
# =========================================================================
elif opcao == "📦 Produtos & Estoque":
    st.title("📦 Controle de Estoque & Catálogo de Produtos")
    
    if st.session_state.user_role == 'adm':
        aba_inventario, aba_novo_prod = st.tabs(["🔍 Consultar Catálogo & Estoque", "➕ Adicionar Novo Produto ao Catálogo"])
    else:
        aba_inventario = st.container()
        
    if st.session_state.user_role == 'adm':
        with aba_novo_prod:
            st.header("Cadastrar Novo Modelo no Catálogo")
            with st.form("form_novo_produto", clear_on_submit=True):
                tipo_item = st.text_input(
                    "Tipo do Produto / Categoria (Livre para digitar):",
                    placeholder="Ex: Smartphone, Película, Capa, Fone, Carregador, Bateria, Cabo, etc."
                )
                marca = st.text_input("Marca (Ex: Apple, Samsung, Xiaomi, Motorola, JBL):", placeholder="Ex: Apple")
                modelo = st.text_input("Modelo / Configuração / Descrição:", placeholder="Ex: iPhone 13 128GB, Capa Silicone, Película 3D...")
                custo = st.number_input("Custo de Aquisição (R$):", min_value=0.0, step=10.0)
                val_minimo = st.number_input("Valor Mínimo de Venda (R$):", min_value=0.0, step=10.0)
                val_venda = st.number_input("Valor Comercial Sugerido (R$):", min_value=0.0, step=10.0)
                quantidade = st.number_input("Quantidade Inicial de Entrada (Unidades Físicas):", min_value=0, step=1, value=1)
                
                if st.form_submit_button("Adicionar ao Catálogo e Gerar Lote", type="primary"):
                    if marca and modelo:
                        try:
                            tipo_clean = tipo_item.strip()
                            if tipo_clean:
                                modelo_com_tipo = f"[{tipo_clean}] {modelo.strip()}"
                            else:
                                modelo_com_tipo = modelo.strip()
                            
                            conn = abrir_conexao()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO Produtos (Marca, Modelo, CustoProduto, ValorMinimo, ValorVenda)
                                VALUES (%s, %s, %s, %s, %s) RETURNING IdProduto
                            """, (marca.strip(), modelo_com_tipo, custo, val_minimo, val_venda))
                            id_prod = cursor.fetchone()[0]
                            
                            # Inserindo unidades físicas iniciais
                            for i in range(int(quantidade)):
                                sn_gerado = f"REF-{id_prod}-{i+1}"
                                cursor.execute("""
                                    INSERT INTO ItensEstoque (IdProduto, NumeroSerie, Status) 
                                    VALUES (%s, %s, 'Disponivel')
                                """, (id_prod, sn_gerado))
                                
                            conn.commit()
                            conn.close()
                            st.success(f"Produto '{marca.strip()} - {modelo_com_tipo}' cadastrado e {quantidade} unidades adicionadas ao estoque!")
                        except Exception as e:
                            st.error(f"Erro ao salvar produto: {e}")
                    else:
                        st.warning("Marca e Modelo são obrigatórios.")
                        
    with aba_inventario:
        st.header("Catálogo Geral da Loja")
        termo_busca = st.text_input("Pesquisar por Marca ou Modelo de Produto:")
        
        # Carrega produtos ativos no catálogo
        query_produtos = """
            SELECT p.IdProduto, p.Marca, p.Modelo, p.CustoProduto, p.ValorMinimo, p.ValorVenda,
                   COUNT(CASE WHEN LOWER(i.Status) = 'disponivel' THEN 1 END) as disponivel,
                   COUNT(CASE WHEN LOWER(i.Status) NOT IN ('orcamento', 'manutencao', 'pronto', 'recusado', 'entregue') THEN 1 END) as total
            FROM Produtos p
            LEFT JOIN ItensEstoque i ON p.IdProduto = i.IdProduto
            WHERE p.Ativo = true AND (p.Marca ILIKE %s OR p.Modelo ILIKE %s)
            GROUP BY p.IdProduto, p.Marca, p.Modelo, p.CustoProduto, p.ValorMinimo, p.ValorVenda
            HAVING (COUNT(i.IdItem) = 0 OR COUNT(CASE WHEN LOWER(i.Status) NOT IN ('orcamento', 'manutencao', 'pronto', 'recusado', 'entregue') THEN 1 END) > 0)
            ORDER BY p.Marca, p.Modelo
        """
        param_busca = f"%{termo_busca}%"
        dados_produtos = executar_query(query_produtos, (param_busca, param_busca), fetch='all')
        
        if dados_produtos:
            df_prod = pd.DataFrame(dados_produtos, columns=["ID", "Marca", "Modelo", "Custo (R$)", "Mínimo (R$)", "Venda (R$)", "Disponível", "Total Cadastrado"])
            st.dataframe(df_prod, use_container_width=True, hide_index=True)
            
            # Botão de exportação do Estoque
            csv_prod = df_prod.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button(
                label="📥 Exportar Catálogo de Estoque para Excel (CSV)",
                data=csv_prod,
                file_name="estoque_speedycell.csv",
                mime="text/csv",
                key="btn_download_estoque"
            )
            
            st.write("---")
            st.subheader("Gerenciar Catálogo & Unidades de Estoque")
            
            lista_select_produtos = {f"{p[1]} - {p[2]}": p for p in dados_produtos}
            prod_selecionado_str = st.selectbox("Selecione o Produto para Modificar/Gerenciar:", list(lista_select_produtos.keys()))
            
            if prod_selecionado_str:
                prod = lista_select_produtos[prod_selecionado_str]
                id_p, marca_p, modelo_p, custo_p, min_p, venda_p, disp_p, tot_p = prod
                
                if st.session_state.user_role == 'adm':
                    # Layout colunas para dividir edição do produto e gerenciamento de unidades físicas
                    col_edit, col_itens = st.columns([1, 1])
                    
                    with col_edit:
                        st.markdown("#### ✏️ Editar Informações do Catálogo")
                        with st.form(f"form_editar_prod_{id_p}"):
                            nova_marca = st.text_input("Marca:", value=marca_p)
                            novo_modelo = st.text_input("Modelo/Descrição:", value=modelo_p)
                            novo_custo = st.number_input("Custo de Aquisição (R$):", value=float(custo_p), step=10.0)
                            novo_min = st.number_input("Valor Mínimo (R$):", value=float(min_p), step=10.0)
                            novo_venda = st.number_input("Valor Venda (R$):", value=float(venda_p), step=10.0)
                            nova_qtd_disp = st.number_input("Quantidade Disponível em Estoque (Unidades):", value=int(disp_p), min_value=0, step=1, help="Altere para aumentar ou diminuir as unidades físicas disponíveis deste produto.")
                            
                            if st.form_submit_button("Salvar Alterações no Catálogo", type="primary"):
                                try:
                                    conn = abrir_conexao()
                                    cursor = conn.cursor()
                                    
                                    # 1. Atualizar informações básicas do produto
                                    cursor.execute("""
                                        UPDATE Produtos
                                        SET Marca = %s, Modelo = %s, CustoProduto = %s, ValorMinimo = %s, ValorVenda = %s
                                        WHERE IdProduto = %s
                                    """, (nova_marca, novo_modelo, novo_custo, novo_min, novo_venda, id_p))
                                    
                                    # 2. Ajustar quantidade física em estoque
                                    qtd_atual = int(disp_p)
                                    qtd_nova = int(nova_qtd_disp)
                                    
                                    if qtd_nova > qtd_atual:
                                        # Adicionar novas unidades disponíveis
                                        diff = qtd_nova - qtd_atual
                                        for i in range(diff):
                                            cursor.execute("SELECT COUNT(*) FROM ItensEstoque WHERE IdProduto = %s", (id_p,))
                                            contagem = cursor.fetchone()[0]
                                            sn_gerado = f"REF-{id_p}-{contagem + 1}"
                                            cursor.execute("""
                                                INSERT INTO ItensEstoque (IdProduto, NumeroSerie, Status) 
                                                VALUES (%s, %s, 'Disponivel')
                                            """, (id_p, sn_gerado))
                                    elif qtd_nova < qtd_atual:
                                        # Remover unidades disponíveis excedentes (começando pelas mais recentes)
                                        diff = qtd_atual - qtd_nova
                                        cursor.execute("""
                                            SELECT IdItem FROM ItensEstoque 
                                            WHERE IdProduto = %s AND LOWER(Status) = 'disponivel'
                                            ORDER BY IdItem DESC LIMIT %s
                                        """, (id_p, diff))
                                        ids_deletar = [row[0] for row in cursor.fetchall()]
                                        if ids_deletar:
                                            cursor.execute("""
                                                DELETE FROM ItensEstoque
                                                WHERE IdItem = ANY(%s)
                                            """, (ids_deletar,))
                                            
                                    conn.commit()
                                    conn.close()
                                    st.success("Catálogo e quantidade de estoque atualizados com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar alterações: {e}")
                                    
                        st.write("---")
                        st.markdown("#### 🗑️ Desativar Produto do Catálogo")
                        confirmar_excluir_prod = st.checkbox(f"Confirmo que desejo ocultar/desativar o produto '{marca_p} - {modelo_p}' para novas vendas (preservando o histórico antigo no banco).", key=f"conf_del_prod_{id_p}")
                        if st.button("Desativar Produto", type="primary", disabled=not confirmar_excluir_prod, key=f"btn_del_prod_{id_p}"):
                            try:
                                # Seta Ativo = false para preservar as vendas e ordens de serviço passadas
                                executar_query("UPDATE Produtos SET Ativo = false WHERE IdProduto = %s", (id_p,))
                                st.success("Produto desativado e ocultado do catálogo com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao desativar produto: {e}")
                                
                    with col_itens:
                        st.markdown("#### 📋 Unidades Físicas (Estoque Individual)")
                        
                        # Carrega as unidades desse produto específico
                        itens_fisicos = executar_query("""
                            SELECT IdItem, NumeroSerie, Status 
                            FROM ItensEstoque 
                            WHERE IdProduto = %s AND LOWER(Status) NOT IN ('orcamento', 'manutencao', 'pronto', 'recusado', 'entregue')
                            ORDER BY IdItem ASC
                        """, (id_p,), fetch='all')
                        
                        if itens_fisicos:
                            df_itens = pd.DataFrame(itens_fisicos, columns=["ID Item", "Número de Série / REF", "Status"])
                            st.dataframe(df_itens, use_container_width=True, hide_index=True)
                            
                            # Ações rápidas para alterar status ou remover uma unidade
                            st.write("⚙️ **Modificar Unidade Física Específica**")
                            lista_select_itens = {f"ID: {it[0]} - S/N: {it[1]} ({it[2]})": it for it in itens_fisicos}
                            item_selecionado_str = st.selectbox("Selecione a unidade:", list(lista_select_itens.keys()))
                            
                            if item_selecionado_str:
                                it = lista_select_itens[item_selecionado_str]
                                id_item_it, sn_it, status_it = it
                                
                                col_i1, col_i2 = st.columns(2)
                                with col_i1:
                                    novo_status_it = st.selectbox(
                                        "Novo Status da Unidade:",
                                        ["Disponivel", "Vendido", "Orcamento", "Manutencao", "Pronto", "Recusado", "Entregue"],
                                        index=["Disponivel", "Vendido", "Orcamento", "Manutencao", "Pronto", "Recusado", "Entregue"].index(status_it)
                                    )
                                    if st.button("Atualizar Status", key=f"btn_status_item_{id_item_it}"):
                                        try:
                                            executar_query("UPDATE ItensEstoque SET Status = %s WHERE IdItem = %s", (novo_status_it, id_item_it))
                                            st.success("Status atualizado!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(e)
                                with col_i2:
                                    st.write("Ações")
                                    if st.button("🗑️ Deletar Unidade", key=f"btn_del_item_{id_item_it}", type="primary"):
                                        try:
                                            executar_query("DELETE FROM ItensEstoque WHERE IdItem = %s", (id_item_it,))
                                            st.success("Unidade removida!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro ao remover: {e}")
                        else:
                            st.warning("Nenhuma unidade física em estoque.")
                            
                        # Formulário para adicionar nova unidade física desse produto
                        st.write("---")
                        st.markdown("#### ➕ Adicionar Unidade Física Individual")
                        with st.form(f"form_add_unidade_{id_p}", clear_on_submit=True):
                            novo_sn_individual = st.text_input("Número de Série (ou deixe em branco para gerar auto):")
                            if st.form_submit_button("Cadastrar Nova Unidade no Estoque"):
                                try:
                                    conn = abrir_conexao()
                                    cursor = conn.cursor()
                                    if not novo_sn_individual.strip():
                                        cursor.execute("SELECT COUNT(*) FROM ItensEstoque WHERE IdProduto = %s", (id_p,))
                                        contagem = cursor.fetchone()[0]
                                        sn_final_un = f"REF-{id_p}-{contagem + 1}"
                                    else:
                                        sn_final_un = novo_sn_individual
                                        
                                    cursor.execute("""
                                        INSERT INTO ItensEstoque (IdProduto, NumeroSerie, Status) 
                                        VALUES (%s, %s, 'Disponivel')
                                    """, (id_p, sn_final_un))
                                    conn.commit()
                                    conn.close()
                                    st.success(f"Unidade '{sn_final_un}' adicionada com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                else:
                    # Lojista vê apenas a listagem geral de unidades físicas
                    st.markdown("#### 📋 Unidades Físicas (Estoque Individual)")
                    try:
                        itens_fisicos = executar_query("""
                            SELECT IdItem, NumeroSerie, Status 
                            FROM ItensEstoque 
                            WHERE IdProduto = %s AND LOWER(Status) NOT IN ('orcamento', 'manutencao', 'pronto', 'recusado', 'entregue')
                            ORDER BY IdItem ASC
                        """, (id_p,), fetch='all')
                        
                        if itens_fisicos:
                            df_itens = pd.DataFrame(itens_fisicos, columns=["ID Item", "Número de Série / REF", "Status"])
                            st.dataframe(df_itens, use_container_width=True, hide_index=True)
                        else:
                            st.warning("Nenhuma unidade física em estoque.")
                    except Exception as e:
                        st.error(f"Erro: {e}")
        else:
            st.info("Nenhum produto cadastrado no catálogo.")

# =========================================================================
# 7. TELA: ORDENS DE SERVIÇO / ATENDIMENTOS (CRUD COMPLETO)
# =========================================================================
elif opcao == "📝 Ordens de Serviço (O.S.)":
    st.title("📝 Gerenciamento de Ordens de Serviço & Atendimentos")
    aba_os_consulta, aba_os_abrir = st.tabs(["🔍 Consultar e Atualizar O.S.", "➕ Abrir Novo Atendimento / Venda"])
    
    with aba_os_abrir:
        st.header("Abertura de Atendimento")
        
        # Passo 1: Selecionar Cliente
        lista_clientes_db = executar_query("SELECT IdCliente, Nome, WhatsApp FROM Clientes ORDER BY Nome ASC", fetch='all')
        if not lista_clientes_db:
            st.warning("⚠️ Cadastre um cliente primeiro na aba de Clientes para abrir uma O.S.")
        else:
            dic_cli = {f"{c[1]} (WA: {c[2]})": c[0] for c in lista_clientes_db}
            cliente_os_selecionado = st.selectbox("Selecione o Cliente:", list(dic_cli.keys()))
            id_cli_os = dic_cli[cliente_os_selecionado]
            
            st.write("---")
            tipo_atendimento = st.radio("O que este cliente está solicitando?", ["🛒 Venda de Mercadoria do Estoque", "🛠️ Ordem de Serviço (Conserto / Assistência)"])
            st.write("---")
            
            if tipo_atendimento == "🛒 Venda de Mercadoria do Estoque":
                # Inicializar carrinho no session state caso não exista
                if "carrinho_venda" not in st.session_state:
                    st.session_state.carrinho_venda = []

                # Carregar produtos ativos com estoque disponível
                prod_disp_db = executar_query("""
                    SELECT p.IdProduto, p.Marca, p.Modelo, p.ValorVenda, COUNT(i.IdItem)
                    FROM Produtos p
                    JOIN ItensEstoque i ON p.IdProduto = i.IdProduto
                    WHERE p.Ativo = true AND LOWER(i.Status) = 'disponivel'
                    GROUP BY p.IdProduto, p.Marca, p.Modelo, p.ValorVenda
                """, fetch='all')
                
                if not prod_disp_db:
                    st.error("Não há produtos no catálogo com unidades físicas 'Disponíveis'. Abasteça o estoque primeiro.")
                else:
                    st.markdown("### 🛒 Montagem da Venda (Carrinho)")
                    
                    # Seletor de produtos e quantidades
                    col_sel1, col_sel2, col_sel3 = st.columns([2, 1, 1])
                    
                    with col_sel1:
                        dic_prod = {f"{p[1]} - {p[2]} (Qtd Disp: {p[4]})": p for p in prod_disp_db}
                        prod_selecionado_venda = st.selectbox("Selecione o Produto:", list(dic_prod.keys()), key="select_prod_cart")
                    
                    p_info = dic_prod[prod_selecionado_venda]
                    id_prod_venda, marca_venda, modelo_venda, preco_venda, qtd_disponivel_item = p_info
                    
                    with col_sel2:
                        qtd_venda = st.number_input(
                            "Quantidade:", 
                            min_value=1, 
                            max_value=int(qtd_disponivel_item), 
                            value=1, 
                            step=1,
                            key="input_qtd_cart"
                        )
                    
                    with col_sel3:
                        preco_final_unitario = st.number_input(
                            "Preço Unitário (R$):", 
                            min_value=0.0, 
                            value=float(preco_venda), 
                            step=10.0,
                            key="input_preco_cart"
                        )
                    
                    # Botão para adicionar ao carrinho
                    if st.button("➕ Adicionar ao Carrinho", use_container_width=True, key="btn_add_ao_carrinho"):
                        # Verifica se o produto já está no carrinho
                        existente = False
                        for item in st.session_state.carrinho_venda:
                            if item["id_produto"] == id_prod_venda:
                                # Verifica se a soma das quantidades não excede o estoque disponível
                                nova_qtd_total = item["qtd"] + qtd_venda
                                if nova_qtd_total > qtd_disponivel_item:
                                    st.error(f"Erro: Quantidade total no carrinho ({nova_qtd_total}) excede o estoque disponível ({qtd_disponivel_item}).")
                                else:
                                    item["qtd"] = nova_qtd_total
                                    item["preco_unitario"] = preco_final_unitario  # Atualiza o preço
                                existente = True
                                break
                        
                        if not existente:
                            st.session_state.carrinho_venda.append({
                                "id_produto": id_prod_venda,
                                "marca": marca_venda,
                                "modelo": modelo_venda,
                                "qtd": int(qtd_venda),
                                "preco_unitario": float(preco_final_unitario)
                            })
                        st.toast("Item adicionado ao carrinho!", icon="🛒")
                        st.rerun()

                    # Exibição do Carrinho
                    if st.session_state.carrinho_venda:
                        st.write("---")
                        st.markdown("#### 📦 Itens no Carrinho")
                        
                        tabela_carrinho = []
                        total_geral = 0.0
                        for idx, item in enumerate(st.session_state.carrinho_venda):
                            subtotal = item["qtd"] * item["preco_unitario"]
                            total_geral += subtotal
                            tabela_carrinho.append([
                                f"{item['marca']} - {item['modelo']}",
                                item["qtd"],
                                f"R$ {item['preco_unitario']:.2f}",
                                f"R$ {subtotal:.2f}",
                                idx
                            ])
                        
                        # Mostra em uma tabela do Pandas para visualização limpa
                        df_cart = pd.DataFrame(
                            [[row[0], row[1], row[2], row[3]] for row in tabela_carrinho], 
                            columns=["Produto", "Quantidade", "Preço Unitário", "Subtotal"]
                        )
                        st.dataframe(df_cart, use_container_width=True, hide_index=True)
                        
                        # Opção para remover item individual do carrinho
                        col_rem1, col_rem2 = st.columns([3, 1])
                        with col_rem1:
                            st.markdown(f"### ⚖️ **Total Geral da Venda:** <span style='color:#10B981; font-weight: 700; font-size: 24px;'>R$ {total_geral:,.2f}</span>", unsafe_allow_html=True)
                        with col_rem2:
                            item_remover_idx = st.selectbox(
                                "Remover item:", 
                                options=range(len(st.session_state.carrinho_venda)),
                                format_func=lambda x: f"{st.session_state.carrinho_venda[x]['marca']} - {st.session_state.carrinho_venda[x]['modelo']}",
                                key="remove_select_cart"
                            )
                            if st.button("🗑️ Remover", key="btn_remove_cart"):
                                st.session_state.carrinho_venda.pop(item_remover_idx)
                                st.toast("Item removido do carrinho!", icon="🗑️")
                                st.rerun()
                                
                        st.write("---")
                        col_pay1, col_pay2 = st.columns(2)
                        with col_pay1:
                            forma_pagamento_venda = st.selectbox(
                                "Forma de Pagamento Principal:",
                                ["Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito", "Outro"]
                            )
                        with col_pay2:
                            observacoes_venda = st.text_input("Observações Adicionais / Detalhes:", placeholder="Ex: Venda parcelada em 3x.")
                        
                        col_actions1, col_actions2 = st.columns(2)
                        with col_actions1:
                            if st.button("❌ Limpar Carrinho", use_container_width=True, key="btn_limpar_carrinho_venda"):
                                st.session_state.carrinho_venda = []
                                st.toast("Carrinho limpo!", icon="🧹")
                                st.rerun()
                                
                        with col_actions2:
                            if st.button("🛒 Confirmar e Finalizar Venda", type="primary", use_container_width=True, key="btn_finalizar_carrinho_venda"):
                                try:
                                    conn = abrir_conexao()
                                    cursor = conn.cursor()
                                    
                                    # Gera o CodigoVenda único para esta venda agrupada
                                    codigo_venda = f"VND-{obter_agora_sp().strftime('%Y%m%d-%H%M%S')}-{id_cli_os}"
                                    
                                    # Processa cada item do carrinho
                                    for item in st.session_state.carrinho_venda:
                                        id_p_venda = item["id_produto"]
                                        qtd_solicitada = item["qtd"]
                                        preco_u = item["preco_unitario"]
                                        
                                        # Pega a quantidade de unidades físicas disponíveis correspondente
                                        cursor.execute("""
                                            SELECT IdItem FROM ItensEstoque 
                                            WHERE IdProduto = %s AND LOWER(Status) = 'disponivel' 
                                            ORDER BY IdItem ASC LIMIT %s
                                        """, (id_p_venda, qtd_solicitada))
                                        itens_fisicos = cursor.fetchall()
                                        
                                        if len(itens_fisicos) < qtd_solicitada:
                                            st.error(f"Erro: As unidades disponíveis para '{item['marca']} {item['modelo']}' foram vendidas por outro terminal.")
                                            conn.rollback()
                                            conn.close()
                                            st.stop()
                                            
                                        # Atualiza e insere cada unidade física no caixa
                                        for row_it in itens_fisicos:
                                            id_item_venda = row_it[0]
                                            # Atualiza status do item físico para Vendido
                                            cursor.execute("UPDATE ItensEstoque SET Status = 'Vendido' WHERE IdItem = %s", (id_item_venda,))
                                            
                                            # Grava no fluxo de caixa individualmente para rastreamento de número de série e fechamento financeiro, vinculando ao mesmo CodigoVenda
                                            cursor.execute("""
                                                INSERT INTO FluxoCaixa (IdItem, IdCliente, Tipo, Valor, Descricao, CodigoVenda)
                                                VALUES (%s, %s, 'E', %s, %s, %s)
                                            """, (id_item_venda, id_cli_os, preco_u, f"[VENDA MULTIPLA][PAGAMENTO: {forma_pagamento_venda.upper()}] - {observacoes_venda}", codigo_venda))
                                            
                                    conn.commit()
                                    conn.close()
                                    st.session_state.carrinho_venda = []  # Limpa o carrinho pós venda
                                    st.success("Venda múltipla efetuada e gravada com sucesso!")
                                    st.balloons()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao processar venda múltipla: {e}")
                    else:
                        st.info("O carrinho está vazio. Selecione um produto acima e clique em 'Adicionar ao Carrinho' para iniciar a venda.")
            else:
                # Ordem de Serviço / Assistência
                col_m1, col_m2 = st.columns(2)
                with col_m1: marca_equipamento = st.text_input("Marca do Aparelho (Ex: Dell, Apple):")
                with col_m2: modelo_equipamento = st.text_input("Modelo / Configuração (Ex: Inspiron 15, Macbook Pro):")
                
                col_val1, col_val2 = st.columns(2)
                with col_val1:
                    valor_os = st.number_input("Preço Estimado do Conserto (R$):", value=0.0, min_value=0.0)
                with col_val2:
                    custo_os = st.number_input("Custo Inicial da(s) Peça(s) (R$):", value=0.0, min_value=0.0)
                
                col_opt1, col_opt2 = st.columns(2)
                with col_opt1:
                    sn_equipamento = st.text_input("Número de Série do Equipamento (Opcional):")
                with col_opt2:
                    tipo_os_inicial = st.selectbox(
                        "Tipo de Entrada:",
                        ["📋 Apenas Orçamento (Aparelho em Análise)", "🛠️ O.S. Aprovada (Iniciar Manutenção)"]
                    )
                
                defeito_os = st.text_area("Defeito / Relato do Cliente / Diagnóstico Inicial:")
                
                if st.button("Abrir Ordem de Serviço", type="primary", key="btn_abrir_os_nova"):
                    if marca_equipamento and modelo_equipamento:
                        try:
                            status_inicial = 'Orcamento' if "Orçamento" in tipo_os_inicial else 'Manutencao'
                            conn = abrir_conexao()
                            cursor = conn.cursor()
                            
                            # Cadastra um "produto" temporário para esta O.S. no catálogo
                            modelo_os_com_tipo = f"[Notebook] {modelo_equipamento}"
                            cursor.execute("""
                                INSERT INTO Produtos (Marca, Modelo, CustoProduto, ValorMinimo, ValorVenda)
                                VALUES (%s, %s, %s, 0, %s) RETURNING IdProduto;
                            """, (marca_equipamento, modelo_os_com_tipo, custo_os, valor_os))
                            id_prod_os = cursor.fetchone()[0]
                            
                            # Cadastra o item com o status inicial correspondente
                            sn_final_os = sn_equipamento if sn_equipamento.strip() else f"OS-{id_prod_os}"
                            cursor.execute("""
                                INSERT INTO ItensEstoque (IdProduto, NumeroSerie, Status)
                                VALUES (%s, %s, %s) RETURNING IdItem;
                            """, (id_prod_os, sn_final_os, status_inicial))
                            id_item_os = cursor.fetchone()[0]
                            
                            # Cria a O.S. no Caixa/Lançamentos
                            desc_prefixo = "[ASSISTENCIA][ORCAMENTO]" if status_inicial == 'Orcamento' else "[ASSISTENCIA]"
                            cursor.execute("""
                                INSERT INTO FluxoCaixa (IdItem, IdCliente, Tipo, Valor, Descricao)
                                VALUES (%s, %s, 'E', %s, %s) RETURNING IdLancamento;
                            """, (id_item_os, id_cli_os, valor_os, f"{desc_prefixo} - {defeito_os}"))
                            id_lancamento_os = cursor.fetchone()[0]
                            
                            # Se houver custo inicial, lança a saída correspondente no caixa (despesa)
                            if custo_os > 0:
                                desc_despesa_peca = f"[CUSTO PEÇA] - OS #{id_lancamento_os} - {marca_equipamento} {modelo_equipamento}"
                                cursor.execute("""
                                    INSERT INTO FluxoCaixa (IdItem, IdCliente, Tipo, Valor, Descricao)
                                    VALUES (%s, %s, 'S', %s, %s)
                                """, (id_item_os, id_cli_os, custo_os, desc_despesa_peca))
                            
                            conn.commit()
                            conn.close()
                            st.success(f"Ordem de Serviço Nº {id_lancamento_os} aberta com sucesso para o aparelho '{marca_equipamento} - {modelo_equipamento}'!")
                        except Exception as e:
                            st.error(f"Erro ao criar O.S.: {e}")
                    else:
                        st.warning("Marca e Modelo do Equipamento são obrigatórios.")
                        
    with aba_os_consulta:
        st.header("Gerenciar Atendimentos & Ordens de Serviço")
        termo_busca_os = st.text_input("Pesquisar O.S. por ID (Número), Nome do Cliente ou Serial:")
        
        # Query detalhada de O.S. e Vendas (incluindo WhatsApp do cliente, custo do produto e ID do produto)
        query_os = """
            SELECT f.IdLancamento, c.Nome, p.Marca, p.Modelo, i.NumeroSerie, i.Status, f.Valor, f.Descricao, f.DataLancamento, i.IdItem, c.IdCliente, c.WhatsApp, f.CodigoVenda, p.CustoProduto, p.IdProduto
            FROM FluxoCaixa f
            JOIN Clientes c ON f.IdCliente = c.IdCliente
            JOIN ItensEstoque i ON f.IdItem = i.IdItem
            JOIN Produtos p ON i.IdProduto = p.IdProduto
            WHERE (CAST(f.IdLancamento AS TEXT) ILIKE %s OR c.Nome ILIKE %s OR i.NumeroSerie ILIKE %s OR f.CodigoVenda ILIKE %s)
              AND f.Descricao NOT LIKE '[CUSTO PEÇA]%%'
            ORDER BY f.IdLancamento DESC
        """
        param_busca_os = f"%{termo_busca_os}%"
        atendimentos = executar_query(query_os, (param_busca_os, param_busca_os, param_busca_os, param_busca_os), fetch='all')
        
        if atendimentos:
            # Agrupar atendimentos por CodigoVenda para vendas agrupadas, mantendo O.S. e vendas avulsas separadas
            atendimentos_agrupados = {}
            for a in atendimentos:
                id_lanc, nome_cli, marca, modelo, sn, status, valor, desc, data, id_item, id_cli, whats, codigo_venda, custo_prod, id_prod_os = a
                data = converter_para_sp(data)
                is_assistencia = desc.startswith("[ASSISTENCIA]")
                
                if is_assistencia:
                    key = f"OS-{id_lanc}"
                    atendimentos_agrupados[key] = {
                        "tipo": "OS",
                        "id_lanc": id_lanc,
                        "nome_cli": nome_cli,
                        "produtos_resumo": f"{marca} {modelo}",
                        "seriais": sn,
                        "status": status,
                        "valor_total": float(valor),
                        "descricao": desc,
                        "data": data,
                        "id_cli": id_cli,
                        "whats": whats,
                        "custo_produto": float(custo_prod) if custo_prod else 0.0,
                        "id_prod_os": id_prod_os,
                        "itens": [{
                            "id_lanc": id_lanc,
                            "id_item": id_item,
                            "marca": marca,
                            "modelo": modelo,
                            "sn": sn,
                            "valor": float(valor),
                            "desc": desc
                        }],
                        "codigo_venda": None
                    }
                else:
                    if codigo_venda:
                        key = codigo_venda
                    else:
                        data_minuto = data.strftime('%Y%m%d-%H%M')
                        key = f"VND-OLD-{id_cli}-{data_minuto}"
                        
                    if key not in atendimentos_agrupados:
                        atendimentos_agrupados[key] = {
                            "tipo": "VENDA",
                            "id_lanc": id_lanc,
                            "nome_cli": nome_cli,
                            "produtos_resumo_dict": {},
                            "seriais_list": [],
                            "status": status,
                            "valor_total": 0.0,
                            "descricao": desc,
                            "data": data,
                            "id_cli": id_cli,
                            "whats": whats,
                            "custo_produto": 0.0,
                            "id_prod_os": None,
                            "itens": [],
                            "codigo_venda": codigo_venda
                        }
                    
                    group = atendimentos_agrupados[key]
                    group["valor_total"] += float(valor)
                    prod_key = f"{marca} {modelo}"
                    group["produtos_resumo_dict"][prod_key] = group["produtos_resumo_dict"].get(prod_key, 0) + 1
                    if sn:
                        group["seriais_list"].append(sn)
                    group["itens"].append({
                        "id_lanc": id_lanc,
                        "id_item": id_item,
                        "marca": marca,
                        "modelo": modelo,
                        "sn": sn,
                        "valor": float(valor),
                        "desc": desc
                    })

            lista_atendimentos_processada = []
            for key, group in atendimentos_agrupados.items():
                if group["tipo"] == "VENDA":
                    prod_parts = [f"{qtd}x {prod}" for prod, qtd in group["produtos_resumo_dict"].items()]
                    group["produtos_resumo"] = ", ".join(prod_parts)
                    group["seriais"] = ", ".join(sorted(list(set(group["seriais_list"]))))
                lista_atendimentos_processada.append(group)

            # Transforma em DataFrame para listar
            dados_df = []
            for a in lista_atendimentos_processada:
                no_exibicao = a["codigo_venda"] if a["codigo_venda"] else f"Venda Avulsa #{a['id_lanc']}"
                if a["tipo"] == "OS":
                    no_exibicao = f"OS #{a['id_lanc']}"
                    
                dados_df.append([
                    no_exibicao,
                    a["nome_cli"],
                    a["produtos_resumo"],
                    a["seriais"],
                    a["status"].upper(),
                    a["valor_total"],
                    a["data"].strftime('%d/%m/%Y %H:%M')
                ])
            df_atend = pd.DataFrame(dados_df, columns=["Nº OS/Venda", "Cliente", "Equipamento/Produto", "Nº Série", "Status", "Preço (R$)", "Data"])
            st.dataframe(df_atend, use_container_width=True, hide_index=True)
            
            st.write("---")
            st.subheader("Atualizar Informações ou Excluir Lançamento de O.S./Venda")
            
            dic_selecao_os = {}
            for a in lista_atendimentos_processada:
                if a["tipo"] == "OS":
                    key = f"OS Nº {a['id_lanc']} - Cliente: {a['nome_cli']} ({a['produtos_resumo']})"
                else:
                    ref_id = a["codigo_venda"] if a["codigo_venda"] else f"ANTIGA-{a['id_lanc']}"
                    key = f"VENDA: {ref_id} - Cliente: {a['nome_cli']} (Total: R$ {a['valor_total']:.2f})"
                dic_selecao_os[key] = a
                
            os_selecionada_str = st.selectbox("Selecione o Atendimento para Editar/Deletar:", list(dic_selecao_os.keys()))
            
            if os_selecionada_str:
                atend_sel = dic_selecao_os[os_selecionada_str]
                
                if atend_sel["tipo"] == "OS":
                    item_os = atend_sel["itens"][0]
                    id_lanc_os = atend_sel["id_lanc"]
                    nome_cli = atend_sel["nome_cli"]
                    marca_p = item_os["marca"]
                    modelo_p = item_os["modelo"]
                    sn_os = item_os["sn"]
                    status_os = atend_sel["status"]
                    valor_os = atend_sel["valor_total"]
                    desc_os = atend_sel["descricao"]
                    data_os = atend_sel["data"]
                    id_item_os = item_os["id_item"]
                    id_cli_os = atend_sel["id_cli"]
                    whats_cli = atend_sel["whats"]
                    custo_os = atend_sel["custo_produto"]
                    id_prod_os = atend_sel["id_prod_os"]
                    
                    col_os_e, col_os_d = st.columns([2, 1])
                    
                    with col_os_e:
                        st.markdown(f"#### ✏️ Modificar Detalhes da OS Nº {id_lanc_os}")
                        with st.form(f"form_editar_os_{id_lanc_os}"):
                            # Detecta forma de pagamento atual no texto da descrição
                            forma_pag_atual = "Não Informado"
                            for f in ["Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito", "Outro"]:
                                if f"[PAGAMENTO: {f.upper()}]" in desc_os:
                                    forma_pag_atual = f
                                    break
                            
                            novo_valor_os = st.number_input("Valor Final Cobrado (R$):", value=float(valor_os), min_value=0.0)
                            novo_custo_os = st.number_input("Custo da(s) Peça(s) Comprada(s) (R$):", value=float(custo_os), min_value=0.0)
                            
                            forma_pagamento_os = st.selectbox(
                                "Forma de Pagamento:",
                                ["Não Informado", "Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito", "Outro"],
                                index=["Não Informado", "Dinheiro", "Pix", "Cartão de Crédito", "Cartão de Débito", "Outro"].index(forma_pag_atual)
                            )
                            
                            novo_sn_os = st.text_input("Número de Série/REF:", value=sn_os)
                            # Remove o prefixo de pagamento ao editar a descrição do defeito e separa as notas técnicas
                            desc_defeito_only = re.sub(r'\[PAGAMENTO:\s*[^\]]+\]\s*-?\s*', '', desc_os.split("--- NOTAS TÉCNICAS ---")[0].strip())
                            novo_desc_os = st.text_area("Histórico / Diagnóstico Técnico / Detalhes:", value=desc_defeito_only)
                            
                            col_os_btn = st.columns(2)
                            with col_os_btn[0]:
                                if st.form_submit_button("Salvar Modificações", type="primary"):
                                    try:
                                        conn = abrir_conexao()
                                        cursor = conn.cursor()
                                        # Remove tags de pagamento anteriores da descrição para evitar duplicação
                                        desc_limpa = re.sub(r'\[PAGAMENTO:\s*[^\]]+\]\s*-?\s*', '', novo_desc_os)
                                        # Pega as notas técnicas existentes da descrição original
                                        partes_originais = desc_os.split("--- NOTAS TÉCNICAS ---")
                                        notas_existentes = partes_originais[1].strip() if len(partes_originais) > 1 else ""
                                        
                                        if forma_pagamento_os != "Não Informado":
                                            desc_salvar = f"[PAGAMENTO: {forma_pagamento_os.upper()}] - {desc_limpa}"
                                        else:
                                            desc_salvar = desc_limpa
                                            
                                        if notas_existentes:
                                            desc_salvar = desc_salvar + "\n\n--- NOTAS TÉCNICAS ---\n" + notas_existentes

                                        # Atualiza valor e descrição no FluxoCaixa (Receita da O.S.)
                                        cursor.execute("""
                                            UPDATE FluxoCaixa 
                                            SET Valor = %s, Descricao = %s 
                                            WHERE IdLancamento = %s
                                        """, (novo_valor_os, desc_salvar, id_lanc_os))
                                        # Atualiza custo do produto em Produtos
                                        cursor.execute("""
                                            UPDATE Produtos 
                                            SET CustoProduto = %s 
                                            WHERE IdProduto = %s
                                        """, (novo_custo_os, id_prod_os))
                                        # Atualiza número de série do equipamento no ItensEstoque
                                        cursor.execute("""
                                            UPDATE ItensEstoque 
                                            SET NumeroSerie = %s 
                                            WHERE IdItem = %s
                                        """, (novo_sn_os, id_item_os))
                                        
                                        # Gerencia a Saída de Caixa para o custo da peça
                                        cursor.execute("""
                                            SELECT IdLancamento FROM FluxoCaixa 
                                            WHERE IdItem = %s AND Tipo = 'S'
                                        """, (id_item_os,))
                                        row_despesa = cursor.fetchone()
                                        
                                        if novo_custo_os > 0:
                                            desc_despesa_peca = f"[CUSTO PEÇA] - OS #{id_lanc_os} - {marca_p} {modelo_p}"
                                            if row_despesa:
                                                # Se já existe, atualiza o valor
                                                cursor.execute("""
                                                    UPDATE FluxoCaixa 
                                                    SET Valor = %s, Descricao = %s 
                                                    WHERE IdLancamento = %s
                                                """, (novo_custo_os, desc_despesa_peca, row_despesa[0]))
                                            else:
                                                # Se não existe, cria novo lançamento de Saída (S)
                                                cursor.execute("""
                                                    INSERT INTO FluxoCaixa (IdItem, IdCliente, Tipo, Valor, Descricao)
                                                    VALUES (%s, %s, %s, %s, %s)
                                                """, (id_item_os, id_cli_os, 'S', novo_custo_os, desc_despesa_peca))
                                        else:
                                            # Se o custo foi zerado, remove a despesa correspondente do caixa
                                            if row_despesa:
                                                cursor.execute("DELETE FROM FluxoCaixa WHERE IdLancamento = %s", (row_despesa[0],))
                                                
                                        conn.commit()
                                        conn.close()
                                        st.success("O.S. atualizada com sucesso!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao salvar alterações: {e}")
                                        
                        # Notas Técnicas e Acompanhamento
                        st.write("---")
                        st.markdown("#### 📜 Notas Técnicas e Acompanhamento")
                        partes_desc = desc_os.split("--- NOTAS TÉCNICAS ---")
                        defeito_atual = partes_desc[0].strip()
                        notas_atuais_raw = partes_desc[1].strip() if len(partes_desc) > 1 else ""
                        
                        if notas_atuais_raw:
                            linhas_notas = [l.strip() for l in notas_atuais_raw.split("\n") if l.strip()]
                            for l_nota in linhas_notas:
                                st.info(l_nota)
                        else:
                            st.caption("Nenhuma nota técnica de progresso registrada.")
                            
                        with st.form(f"form_add_nota_{id_lanc_os}", clear_on_submit=True):
                            nova_nota = st.text_input("Nova Anotação de Progresso:")
                            if st.form_submit_button("➕ Adicionar Nota"):
                                if nova_nota.strip():
                                    agora_str = obter_agora_sp().strftime('%d/%m/%Y %H:%M')
                                    linha_nova = f"[{agora_str}] {nova_nota.strip()}"
                                    
                                    if notas_atuais_raw:
                                        notas_atualizadas = notas_atuais_raw + "\n" + linha_nova
                                    else:
                                        notas_atualizadas = linha_nova
                                        
                                    desc_final = defeito_atual + "\n\n--- NOTAS TÉCNICAS ---\n" + notas_atualizadas
                                    executar_query("UPDATE FluxoCaixa SET Descricao = %s WHERE IdLancamento = %s", (desc_final, id_lanc_os))
                                    st.success("Nota adicionada com sucesso!")
                                    st.rerun()
                                        
                        st.write("---")
                        st.markdown("#### ⚙️ Controle de Status da Assistência")
                        col_st1, col_st2, col_st3, col_st4, col_st5 = st.columns(5)
                        with col_st1:
                            if st.button("📋 Em Orçamento", key=f"btn_st_orc_{id_lanc_os}", disabled=(status_os == "Orcamento"), use_container_width=True):
                                executar_query("UPDATE ItensEstoque SET Status = 'Orcamento' WHERE IdItem = %s", (id_item_os,))
                                adicionar_nota_os(id_lanc_os, f"Status alterado para 'Em Orçamento' por {st.session_state.user_name}")
                                st.success("Status: Em Orçamento")
                                st.rerun()
                        with col_st2:
                            if st.button("🛠️ Em Manutenção", key=f"btn_st_man_{id_lanc_os}", disabled=(status_os == "Manutencao"), use_container_width=True):
                                executar_query("UPDATE ItensEstoque SET Status = 'Manutencao' WHERE IdItem = %s", (id_item_os,))
                                adicionar_nota_os(id_lanc_os, f"Status alterado para 'Em Manutenção' por {st.session_state.user_name}")
                                st.success("Status: Em Manutenção")
                                st.rerun()
                        with col_st3:
                            if st.button("🔵 Pronto p/ Retirada", key=f"btn_st_pro_{id_lanc_os}", disabled=(status_os == "Pronto"), use_container_width=True):
                                executar_query("UPDATE ItensEstoque SET Status = 'Pronto' WHERE IdItem = %s", (id_item_os,))
                                adicionar_nota_os(id_lanc_os, f"Status alterado para 'Pronto para Retirada' por {st.session_state.user_name}")
                                st.success("Status: Pronto para Retirada")
                                st.rerun()
                        with col_st4:
                            if st.button("❌ Recusado", key=f"btn_st_rec_{id_lanc_os}", disabled=(status_os == "Recusado"), use_container_width=True):
                                executar_query("UPDATE ItensEstoque SET Status = 'Recusado' WHERE IdItem = %s", (id_item_os,))
                                adicionar_nota_os(id_lanc_os, f"Status alterado para 'Orçamento Recusado' por {st.session_state.user_name}")
                                st.success("Status: Orçamento Recusado")
                                st.rerun()
                        with col_st5:
                            if st.button("🟢 Entregue", key=f"btn_st_ent_{id_lanc_os}", disabled=(status_os == "Entregue"), use_container_width=True):
                                executar_query("UPDATE ItensEstoque SET Status = 'Entregue' WHERE IdItem = %s", (id_item_os,))
                                adicionar_nota_os(id_lanc_os, f"Status alterado para 'Entregue' por {st.session_state.user_name}")
                                st.success("Status: Finalizado e Entregue")
                                st.rerun()
                        
                        st.write("")
                        st.markdown("#### 📲 Comunicar Cliente via WhatsApp")
                        
                        whats_limpo = re.sub(r'\D', '', whats_cli) if whats_cli else ""
                        if whats_limpo:
                            if not whats_limpo.startswith("55"):
                                whats_limpo = "55" + whats_limpo
                                
                            msg_abertura = f"Olá, {nome_cli}! Aqui é da Speedy Cell. Recebemos o seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) para análise. A sua Ordem de Serviço é a Nº {id_lanc_os}. Assim que realizarmos o diagnóstico, entraremos em contato!"
                            msg_orcamento = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O orçamento para o conserto do seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da OS Nº {id_lanc_os} ficou em R$ {valor_os:.2f}. Podemos prosseguir com o serviço?"
                            msg_recusado = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O orçamento para o conserto do seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da OS Nº {id_lanc_os} foi recusado. O seu aparelho já está pronto para devolução/retirada na nossa loja."
                            msg_aguardando = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da OS Nº {id_lanc_os} está aguardando a chegada de peças para finalizarmos a manutenção."
                            msg_manutencao = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da Ordem de Serviço Nº {id_lanc_os} já está em manutenção na nossa assistência técnica. Assim que estiver pronto, entraremos em contato!"
                            msg_pronto = f"Olá, {nome_cli}! Aqui é da Speedy Cell. Temos boas notícias: o seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da Ordem de Serviço Nº {id_lanc_os} está PRONTO! Você já pode vir retirá-lo na nossa loja. Valor final: R$ {valor_os:.2f}."
                            msg_entregue = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da Ordem de Serviço Nº {id_lanc_os} foi entregue com sucesso e a O.S. foi finalizada. Agradecemos a preferência!"
                            
                            import urllib.parse
                            link_abe = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_abertura)}"
                            link_orc = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_orcamento)}"
                            link_rec = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_recusado)}"
                            link_agu = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_aguardando)}"
                            link_man = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_manutencao)}"
                            link_pro = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_pronto)}"
                            link_ent = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_entregue)}"
                            
                            col_w1, col_w2, col_w3, col_w4 = st.columns(4)
                            with col_w1:
                                st.link_button("📝 Enviar: Recebido", link_abe, use_container_width=True)
                                st.link_button("🛠️ Enviar: Em Manutenção", link_man, use_container_width=True)
                            with col_w2:
                                st.link_button("💸 Enviar: Orçamento", link_orc, use_container_width=True)
                                st.link_button("❌ Enviar: Recusado/Devolver", link_rec, use_container_width=True)
                            with col_w3:
                                st.link_button("⏳ Enviar: Aguardando Peças", link_agu, use_container_width=True)
                                st.link_button("🔵 Enviar: Pronto p/ Retirada", link_pro, use_container_width=True)
                            with col_w4:
                                st.link_button("🟢 Enviar: Entregue", link_ent, use_container_width=True)
                        else:
                            st.warning("⚠️ Cliente não possui WhatsApp cadastrado para enviar atualizações.")
                            
                        # Exclusão fora do formulário (apenas ADM)
                        if st.session_state.user_role == 'adm':
                            st.write("---")
                            st.markdown("#### 🗑️ Cancelar / Excluir Ordem de Serviço")
                            confirmar_excluir_os = st.checkbox(f"Confirmo que desejo apagar definitivamente a OS Nº {id_lanc_os}.", key=f"conf_del_os_{id_lanc_os}")
                            if st.button("Excluir Ordem de Serviço", type="primary", disabled=not confirmar_excluir_os, key=f"btn_del_os_{id_lanc_os}"):
                                try:
                                    # Remove todos os registros de fluxo de caixa (receitas e despesas de peças) vinculados a esta OS
                                    executar_query("DELETE FROM FluxoCaixa WHERE IdItem = %s", (id_item_os,))
                                    st.success("Ordem de Serviço apagada com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir O.S.: {e}")
                                    
                    with col_os_d:
                        # Define título, texto de valor e termos com base no status
                        if status_os.lower() == "orcamento":
                            titulo_doc = "COMPROVANTE DE ENTRADA (ORÇAMENTO)"
                            texto_valor = "VALOR ESTIMADO: SOB ANÁLISE / ORÇAMENTO"
                            termo_titulo = "TERMOS DE RECEBIMENTO:"
                            termo_texto = "Este comprovante atesta que o equipamento acima foi deixado para analise tecnica e elaboracao de orcamento. O cliente deve apresentar este papel para a retirada do equipamento, seja o orcamento aprovado ou recusado."
                        elif status_os.lower() == "recusado":
                            titulo_doc = "COMPROVANTE DE DEVOLUÇÃO (RECUSADO)"
                            texto_valor = "VALOR TOTAL: R$ 0,00 (Orçamento Recusado)"
                            termo_titulo = "TERMOS DE RETIRADA:"
                            termo_texto = "O cliente declara ter retirado o equipamento nas mesmas condicoes de entrada, sem a realizacao de servicos devido a nao aprovacao do orcamento."
                        else:
                            titulo_doc = f"COMPROVANTE O.S. Nº {id_lanc_os}"
                            texto_valor = f"VALOR BRUTO: R$ {valor_os:.2f}"
                            termo_titulo = "TERMOS DE GARANTIA:"
                            termo_texto = "Garantia de 90 dias sobre a mao de obra e pecas trocadas a partir da data de retirada/entrega, cobrindo apenas defeitos associados ao servico realizado."

                        st.markdown("#### 🖨️ Impressão de Comprovante")
                        html_recibo = f"""
                        <html>
                        <head>
                            <style>
                                @media print {{ body {{ width: 72mm; font-family: monospace; font-size: 11px; margin: 0; }} }}
                                .recibo {{ width: 240px; font-family: monospace; padding: 2px; line-height: 1.2; color: #000; }}
                                .centralizado {{ text-align: center; }}
                                .linha {{ border-top: 1px dashed #000; margin: 4px 0; }}
                                .espaco-assinatura {{ margin-top: 25px; text-align: center; }}
                            </style>
                        </head>
                        <body>
                            <div class="recibo">
                                <div class="centralizado">
                                    <strong>⚡ SPEEDY CELL ⚡</strong><br>
                                    <span style="font-size: 10px;">SPEEDY CELL COM. DE CELULARES LTDA</span><br>
                                    CNPJ: 68.423.262/0001-00<br>
                                    Assistencia Tecnica e Celulares<br>
                                    Av. Luis Stamatis, 8 - Loja A - Vila Constanca<br>
                                    Sao Paulo - SP - CEP: 02260-000<br>
                                    Whats/Tel: (11) 4737-2379<br>
                                    ----------------------------
                                </div>
                                <strong>{titulo_doc}</strong><br>
                                Data: {data_os.strftime('%d/%m/%Y %H:%M')}<br>
                                <div class="linha"></div>
                                <strong>CLIENTE:</strong> {nome_cli}<br>
                                <strong>WHATS:</strong> (Disponível no sistema)<br>
                                <div class="linha"></div>
                                <strong>PROD/APARELHO:</strong> {marca_p} {modelo_p}<br>
                                <strong>S/N ou REF:</strong> {sn_os}<br>
                                <strong>STATUS:</strong> {status_os.upper()}<br>
                                <strong>DETALHES:</strong> {re.sub(r'\[PAGAMENTO:\s*[^\]]+\]\s*-?\s*', '', desc_os.split('--- NOTAS TÉCNICAS ---')[0].strip())}<br>
                                <div class="linha"></div>
                                <strong>{texto_valor}</strong><br>
                                <div class="linha"></div>
                                <div style='font-size: 9px; text-align: justify; margin-top: 5px; line-height: 1.1;'>
                                    <strong>{termo_titulo}</strong><br>
                                    {termo_texto}
                                </div>
                                <div class="espaco-assinatura">___________________________<br>Assinatura do Cliente</div>
                                <div class="espaco-assinatura">___________________________<br>Assinatura Speedy Cell</div>
                            </div>
                            <script>window.print();</script>
                        </body>
                        </html>
                        """
                        if st.button("🖨️ Imprimir Comprovante / Cupom", key=f"btn_print_{id_lanc_os}"):
                            components.html(html_recibo, height=1)
                            st.info("💡 Janela de impressão enviada ao navegador.")
                            
                else:
                    # É uma VENDA agrupada ou individual
                    codigo_venda = atend_sel["codigo_venda"]
                    id_lanc_ref = atend_sel["id_lanc"]
                    nome_cli = atend_sel["nome_cli"]
                    valor_total = atend_sel["valor_total"]
                    desc_venda = atend_sel["descricao"]
                    data_venda = atend_sel["data"]
                    id_cli_os = atend_sel["id_cli"]
                    whats_cli = atend_sel["whats"]
                    itens_venda = atend_sel["itens"]
                    
                    col_os_e, col_os_d = st.columns([2, 1])
                    
                    with col_os_e:
                        st.markdown(f"#### ✏️ Detalhes da Venda: {codigo_venda if codigo_venda else f'Nº {id_lanc_ref}'}")
                        
                        # Tabela de itens da venda
                        tabela_detalhe_itens = []
                        for it in itens_venda:
                            tabela_detalhe_itens.append([
                                f"{it['marca']} - {it['modelo']}",
                                it["sn"] if it["sn"] else "---",
                                f"R$ {it['valor']:.2f}"
                            ])
                        df_detalhe = pd.DataFrame(tabela_detalhe_itens, columns=["Produto", "Número de Série / REF", "Valor Unitário"])
                        st.dataframe(df_detalhe, use_container_width=True, hide_index=True)
                        st.markdown(f"### ⚖️ **Total Geral:** <span style='color:#10B981; font-weight: 700; font-size: 24px;'>R$ {valor_total:,.2f}</span>", unsafe_allow_html=True)
                        
                        # Form para editar observação/pagamento
                        with st.form(f"form_editar_venda_{codigo_venda if codigo_venda else id_lanc_ref}"):
                            nova_desc_venda = st.text_area("Observações da Venda / Forma de Pagamento:", value=desc_venda)
                            if st.form_submit_button("Salvar Observações", type="primary"):
                                try:
                                    if codigo_venda:
                                        executar_query("""
                                            UPDATE FluxoCaixa 
                                            SET Descricao = %s 
                                            WHERE CodigoVenda = %s
                                        """, (nova_desc_venda, codigo_venda))
                                    else:
                                        ids_lanc_agrupados = [it["id_lanc"] for it in itens_venda]
                                        executar_query("""
                                            UPDATE FluxoCaixa 
                                            SET Descricao = %s 
                                            WHERE IdLancamento = ANY(%s)
                                        """, (nova_desc_venda, ids_lanc_agrupados))
                                    st.success("Observações atualizadas com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar: {e}")
                                    
                        # Controle de Status da Venda / Assistência
                        st.write("---")
                        st.markdown("#### ⚙️ Controle de Status da Venda / Assistência")
                        
                        status_venda = atend_sel["status"]
                        ids_itens_venda = [it["id_item"] for it in itens_venda if it["id_item"] is not None]
                        
                        col_st1, col_st2, col_st3 = st.columns(3)
                        with col_st1:
                            if st.button("🛠️ Em Manutenção", key=f"btn_st_man_venda_{id_lanc_ref}", disabled=(status_venda == "Manutencao")):
                                if ids_itens_venda:
                                    executar_query("UPDATE ItensEstoque SET Status = 'Manutencao' WHERE IdItem = ANY(%s)", (ids_itens_venda,))
                                for it in itens_venda:
                                    adicionar_nota_os(it["id_lanc"], f"Status alterado para 'Em Manutenção' por {st.session_state.user_name}")
                                st.success("Status: Em Manutenção")
                                st.rerun()
                        with col_st2:
                            if st.button("🔵 Pronto para Retirada", key=f"btn_st_pro_venda_{id_lanc_ref}", disabled=(status_venda == "Pronto")):
                                if ids_itens_venda:
                                    executar_query("UPDATE ItensEstoque SET Status = 'Pronto' WHERE IdItem = ANY(%s)", (ids_itens_venda,))
                                for it in itens_venda:
                                    adicionar_nota_os(it["id_lanc"], f"Status alterado para 'Pronto para Retirada' por {st.session_state.user_name}")
                                st.success("Status: Pronto para Retirada")
                                st.rerun()
                        with col_st3:
                            if st.button("🟢 Entregue / Finalizado", key=f"btn_st_ent_venda_{id_lanc_ref}", disabled=(status_venda == "Entregue")):
                                if ids_itens_venda:
                                    executar_query("UPDATE ItensEstoque SET Status = 'Entregue' WHERE IdItem = ANY(%s)", (ids_itens_venda,))
                                for it in itens_venda:
                                    adicionar_nota_os(it["id_lanc"], f"Status alterado para 'Entregue' por {st.session_state.user_name}")
                                st.success("Status: Finalizado e Entregue")
                                st.rerun()
                                
                        # Comunicar Cliente via WhatsApp
                        st.write("---")
                        st.markdown("#### 📲 Comunicar Cliente via WhatsApp")
                        
                        whats_limpo = re.sub(r'\D', '', whats_cli) if whats_cli else ""
                        if whats_limpo:
                            if not whats_limpo.startswith("55"):
                                whats_limpo = "55" + whats_limpo
                                
                            primeiro_item = itens_venda[0] if itens_venda else {"marca": "", "modelo": "", "sn": "", "valor": 0.0}
                            marca_p = primeiro_item["marca"]
                            modelo_p = primeiro_item["modelo"]
                            sn_os = primeiro_item["sn"] if primeiro_item["sn"] else "N/A"
                            id_ref = codigo_venda if codigo_venda else f"Nº {id_lanc_ref}"
                            
                            itens_msg_list = []
                            for it in itens_venda:
                                sn_str = f" (S/N: {it['sn']})" if it['sn'] else ""
                                itens_msg_list.append(f"- {it['marca']} {it['modelo']}{sn_str}: R$ {it['valor']:.2f}")
                            itens_msg = "\n".join(itens_msg_list)
                            
                            msg_comprovante = (
                                f"Olá, {nome_cli}! Aqui é da Speedy Cell. 🌟\n\n"
                                f"Segue o detalhamento da sua compra realizada em {data_venda.strftime('%d/%m/%Y %H:%M')}:\n\n"
                                f"{itens_msg}\n\n"
                                f"*Valor Total: R$ {valor_total:.2f}*\n\n"
                                f"Agradecemos a preferência! Se precisar de algo, estamos à disposição. 👍"
                            )
                            
                            msg_orcamento = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O orçamento para a manutenção/serviço da sua compra {id_ref} ficou em R$ {valor_total:.2f}. Podemos prosseguir com o serviço?"
                            msg_aguardando = f"Olá, {nome_cli}! Aqui é da Speedy Cell. A sua Ordem de Serviço/Venda {id_ref} está aguardando a chegada de peças para finalizarmos o serviço."
                            msg_manutencao = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da Ordem de Serviço/Venda {id_ref} já está em manutenção na nossa assistência técnica. Assim que estiver pronto, entraremos em contato!"
                            msg_pronto = f"Olá, {nome_cli}! Aqui é da Speedy Cell. Temos boas notícias: o seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da Ordem de Serviço/Venda {id_ref} está PRONTO! Você já pode vir retirá-lo na nossa loja. Valor final: R$ {valor_total:.2f}."
                            msg_entregue = f"Olá, {nome_cli}! Aqui é da Speedy Cell. O seu equipamento {marca_p} {modelo_p} (Serial: {sn_os}) da Ordem de Serviço/Venda {id_ref} foi entregue com sucesso e a O.S. foi finalizada. Agradecemos a preferência!"
                            
                            import urllib.parse
                            link_comp = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_comprovante)}"
                            link_orc = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_orcamento)}"
                            link_agu = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_aguardando)}"
                            link_man = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_manutencao)}"
                            link_pro = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_pronto)}"
                            link_ent = f"https://wa.me/{whats_limpo}?text={urllib.parse.quote(msg_entregue)}"
                            
                            col_w1, col_w2, col_w3 = st.columns(3)
                            with col_w1:
                                st.link_button("📲 Enviar: Comprovante de Compra", link_comp, use_container_width=True)
                                st.link_button("🛠️ Enviar: Em Manutenção", link_man, use_container_width=True)
                            with col_w2:
                                st.link_button("💸 Enviar: Orçamento", link_orc, use_container_width=True)
                                st.link_button("🔵 Enviar: Pronto p/ Retirada", link_pro, use_container_width=True)
                            with col_w3:
                                st.link_button("⏳ Enviar: Aguardando Peças", link_agu, use_container_width=True)
                                st.link_button("🟢 Enviar: Equipamento Entregue", link_ent, use_container_width=True)
                        else:
                            st.warning("⚠️ Cliente não possui WhatsApp cadastrado para enviar atualizações.")
                                    
                        # Exclusão da venda (apenas ADM)
                        if st.session_state.user_role == 'adm':
                            st.write("---")
                            st.markdown("#### 🗑️ Cancelar / Excluir Venda")
                            confirmar_excluir_venda = st.checkbox(f"Confirmo que desejo cancelar esta venda. Isso removerá os registros financeiros e retornará os itens ao estoque como 'Disponível'.", key=f"conf_del_vnd_{codigo_venda if codigo_venda else id_lanc_ref}")
                            if st.button("Excluir Venda e Devolver Itens ao Estoque", type="primary", disabled=not confirmar_excluir_venda, key=f"btn_del_vnd_{codigo_venda if codigo_venda else id_lanc_ref}"):
                                try:
                                    conn = abrir_conexao()
                                    cursor = conn.cursor()
                                    
                                    # Pega todos os itens da venda para estornar estoque
                                    ids_itens_estornar = [it["id_item"] for it in itens_venda if it["id_item"] is not None]
                                    
                                    if ids_itens_estornar:
                                        cursor.execute("""
                                            UPDATE ItensEstoque 
                                            SET Status = 'Disponivel' 
                                            WHERE IdItem = ANY(%s)
                                        """, (ids_itens_estornar,))
                                        
                                    if codigo_venda:
                                        cursor.execute("DELETE FROM FluxoCaixa WHERE CodigoVenda = %s", (codigo_venda,))
                                    else:
                                        ids_lanc_agrupados = [it["id_lanc"] for it in itens_venda]
                                        cursor.execute("DELETE FROM FluxoCaixa WHERE IdLancamento = ANY(%s)", (ids_lanc_agrupados,))
                                        
                                    conn.commit()
                                    conn.close()
                                    st.success("Venda cancelada com sucesso e estoque devolvido!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao cancelar: {e}")
                                    
                    with col_os_d:
                        st.markdown("#### 🖨️ Comprovante de Balcão")
                        
                        # Constrói a listagem HTML dos itens vendidos
                        itens_html_list = ""
                        for it in itens_venda:
                            itens_html_list += f"""
                            <tr>
                                <td style='padding: 3px 0; font-family: monospace; font-size: 11px;'>{it['marca']} {it['modelo']}<br><small>S/N: {it['sn'] if it['sn'] else 'N/A'}</small></td>
                                <td style='text-align: right; vertical-align: top; font-family: monospace; font-size: 11px;'>R$ {it['valor']:.2f}</td>
                            </tr>
                            """
                            
                        html_recibo_venda = f"""
                        <html>
                        <head>
                            <style>
                                @media print {{ body {{ width: 72mm; font-family: monospace; font-size: 11px; margin: 0; }} }}
                                .recibo {{ width: 240px; font-family: monospace; padding: 2px; line-height: 1.2; color: #000; }}
                                .centralizado {{ text-align: center; }}
                                .linha {{ border-top: 1px dashed #000; margin: 4px 0; }}
                                .espaco-assinatura {{ margin-top: 25px; text-align: center; }}
                                table {{ width: 100%; border-collapse: collapse; }}
                            </style>
                        </head>
                        <body>
                            <div class="recibo">
                                <div class="centralizado">
                                    <strong>⚡ SPEEDY CELL ⚡</strong><br>
                                    <span style="font-size: 10px;">SPEEDY CELL COM. DE CELULARES LTDA</span><br>
                                    CNPJ: 68.423.262/0001-00<br>
                                    Assistencia Tecnica e Celulares<br>
                                    Av. Luis Stamatis, 8 - Loja A - Vila Constanca<br>
                                    Sao Paulo - SP - CEP: 02260-000<br>
                                    Whats/Tel: (11) 4737-2379<br>
                                    ----------------------------
                                </div>
                                <strong>COMPROVANTE DE VENDA</strong><br>
                                ID: {codigo_venda if codigo_venda else f'VND-{id_lanc_ref}'}<br>
                                Data: {data_venda.strftime('%d/%m/%Y %H:%M')}<br>
                                <div class="linha"></div>
                                <strong>CLIENTE:</strong> {nome_cli}<br>
                                <div class="linha"></div>
                                <table>
                                    <thead>
                                        <tr style='border-bottom: 1px dashed #000;'>
                                            <th style='text-align: left; font-family: monospace; font-size: 11px;'>Item</th>
                                            <th style='text-align: right; font-family: monospace; font-size: 11px;'>Preço</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {itens_html_list}
                                    </tbody>
                                </table>
                                <div class="linha"></div>
                                <strong>TOTAL GERAL: R$ {valor_total:.2f}</strong><br>
                                <div class="linha"></div>
                                <div style='font-size: 10px; margin-top: 5px;'>
                                    <strong>Obs:</strong> {desc_venda}
                                </div>
                                <div style='font-size: 9px; text-align: justify; margin-top: 5px; line-height: 1.1;'>
                                    <strong>TERMOS DE GARANTIA:</strong><br>
                                    Garantia de 90 dias contra defeitos de fabricacao a partir desta data, mediante apresentacao deste comprovante.
                                </div>
                                <div class="espaco-assinatura">___________________________<br>Assinatura do Cliente</div>
                                <div class="espaco-assinatura">___________________________<br>Assinatura Speedy Cell</div>
                            </div>
                            <script>window.print();</script>
                        </body>
                        </html>
                        """
                        if st.button("🖨️ Imprimir Cupom de Venda", key=f"btn_print_venda_{codigo_venda if codigo_venda else id_lanc_ref}"):
                            components.html(html_recibo_venda, height=1)
                            st.info("💡 Janela de impressão enviada ao navegador.")
        else:
            st.info("Nenhuma ordem de serviço ou atendimento localizado.")

# =========================================================================
# 8. TELA: FINANCEIRO & CAIXA (CRUD COMPLETO)
# =========================================================================
elif opcao == "📊 Financeiro & Caixa":
    st.title("📊 Painel Financeiro & Fluxo de Caixa")
    aba_lancamentos, aba_novo_lanc, aba_dividas = st.tabs(["📊 Histórico de Caixa", "💸 Lançar Entrada/Saída Manual", "🤝 Contas a Pagar / Dívidas de Peças"])
    
    with aba_novo_lanc:
        st.header("Lançamento Financeiro Manual")
        st.markdown("Use esta tela para registrar despesas operacionais (aluguel, peças, café) ou receitas diretas avulsas.")
        with st.form("form_novo_lancamento", clear_on_submit=True):
            tipo_lanc = st.selectbox("Tipo de Lançamento:", ["Entrada (Receita)", "Saída (Despesa)"])
            valor_lanc = st.number_input("Valor do Lançamento (R$):", min_value=0.01, step=1.00)
            desc_lanc = st.text_area("Descrição/Justificativa:")
            
            if st.form_submit_button("Gravar Transação"):
                try:
                    tipo_char = 'E' if tipo_lanc == "Entrada (Receita)" else 'S'
                    executar_query("""
                        INSERT INTO FluxoCaixa (Tipo, Valor, Descricao)
                        VALUES (%s, %s, %s)
                    """, (tipo_char, valor_lanc, desc_lanc))
                    st.success("Lançamento financeiro registrado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar lançamento: {e}")
                    
    with aba_lancamentos:
        st.header("Histórico de Fluxo de Caixa")
        
        # Filtros de data e tipo
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            agora_sp = obter_agora_sp()
            data_inicio = st.date_input("De:", value=datetime(agora_sp.year, agora_sp.month, 1))
        with col_f2:
            data_fim = st.date_input("Até:", value=obter_agora_sp())
        with col_f3:
            tipo_filtro = st.selectbox("Filtrar por Tipo:", ["Todos", "Entradas (Receitas)", "Saídas (Despesas)"])
        with col_f4:
            metodo_filtro = st.selectbox("Forma de Pagamento:", ["Todos", "Pix", "Dinheiro", "Cartão de Crédito", "Cartão de Débito", "Outro/Avulso"])
            
        # Montagem da Query Dinâmica
        query_caixa = """
            SELECT f.IdLancamento, f.Tipo, f.Valor, f.Descricao, f.DataLancamento, c.Nome
            FROM FluxoCaixa f
            LEFT JOIN Clientes c ON f.IdCliente = c.IdCliente
            WHERE CAST(f.DataLancamento AS DATE) BETWEEN %s AND %s
        """
        params_caixa = [data_inicio, data_fim]
        
        if tipo_filtro == "Entradas (Receitas)":
            query_caixa += " AND f.Tipo = 'E'"
        elif tipo_filtro == "Saídas (Despesas)":
            query_caixa += " AND f.Tipo = 'S'"
            
        query_caixa += " ORDER BY f.IdLancamento DESC"
        
        caixa_dados = executar_query(query_caixa, params_caixa, fetch='all')
        
        if caixa_dados:
            total_e = 0.0
            total_s = 0.0
            tabela_final = []
            
            # Métricas de formas de pagamento (apenas para Entradas/Receitas)
            dados_metodos = {"Pix": 0.0, "Dinheiro": 0.0, "Cartão de Crédito": 0.0, "Cartão de Débito": 0.0, "Outro/Avulso": 0.0}
            
            for item in caixa_dados:
                id_l, tipo_l, valor_l, desc_l, date_l, nome_c = item
                date_l = converter_para_sp(date_l)
                nome_c_final = nome_c if nome_c else "Lançamento Avulso"
                tipo_str = "🟢 Entrada" if tipo_l == 'E' else "🔴 Saída"
                
                # Extrair método de pagamento
                metodo_item = extrair_metodo_pagamento(desc_l)
                if tipo_l == 'E':
                    dados_metodos[metodo_item] = dados_metodos.get(metodo_item, 0.0) + float(valor_l)
                
                # Aplicar filtro de método de pagamento
                if metodo_filtro != "Todos" and metodo_item != metodo_filtro:
                    continue
                
                if tipo_l == 'E':
                    total_e += float(valor_l)
                else:
                    total_s += float(valor_l)
                    
                tabela_final.append([id_l, tipo_str, valor_l, desc_l, nome_c_final, date_l.strftime('%d/%m/%Y %H:%M')])
                
            if not tabela_final:
                st.info("Nenhum lançamento corresponde à forma de pagamento selecionada.")
            else:
                df_fin = pd.DataFrame(tabela_final, columns=["ID Lançamento", "Tipo", "Valor (R$)", "Descrição", "Cliente/Origem", "Data"])
                if st.session_state.ocultar_valores:
                    df_fin["Valor (R$)"] = "••••"
                st.dataframe(df_fin, use_container_width=True, hide_index=True)
                
                # Botão de exportação do caixa filtrado
                csv_fin = df_fin.to_csv(index=False, sep=';').encode('utf-8-sig')
                st.download_button(
                    label="📥 Exportar Fluxo de Caixa para Excel (CSV)",
                    data=csv_fin,
                    file_name="fluxo_caixa_speedycell.csv",
                    mime="text/csv",
                    key="btn_download_caixa"
                )
                
                # Resumo financeiro do período
                st.write("---")
                total_e_display = formatar_brl(total_e) if not st.session_state.ocultar_valores else "R$ ••••••"
                total_s_display = formatar_brl(total_s) if not st.session_state.ocultar_valores else "R$ ••••••"
                saldo_p_display = formatar_brl(total_e - total_s) if not st.session_state.ocultar_valores else "R$ ••••••"
                
                col_res1, col_res2, col_res3 = st.columns(3)
                with col_res1:
                    st.info(f"🟢 **Total de Entradas:** {total_e_display}")
                with col_res2:
                    st.warning(f"🔴 **Total de Saídas:** {total_s_display}")
                with col_res3:
                    st.success(f"⚖️ **Saldo do Período:** {saldo_p_display}")
                    
                # Exibir gráfico de barras das formas de pagamento no faturamento
                if sum(dados_metodos.values()) > 0:
                    st.write("---")
                    st.subheader("📈 Faturamento por Forma de Pagamento (No Período)")
                    if not st.session_state.ocultar_valores:
                        df_chart_metodos = pd.DataFrame(list(dados_metodos.items()), columns=["Forma de Pagamento", "Valor (R$)"]).set_index("Forma de Pagamento")
                        st.bar_chart(df_chart_metodos, use_container_width=True)
                    else:
                        st.info("📈 Gráfico de faturamento ocultado.")
                
            # CRUD: Editar/Excluir lançamento do caixa
            st.write("---")
            st.subheader("Editar / Excluir Lançamento Financeiro")
            
            dic_selecao_fin = {}
            for c in caixa_dados:
                valor_display_fin = formatar_brl(c[2]) if not st.session_state.ocultar_valores else "••••"
                dic_selecao_fin[f"Lançamento Nº {c[0]} - {c[1]} - {valor_display_fin}"] = c
            lanc_selecionado_str = st.selectbox("Selecione o Lançamento para Modificar:", list(dic_selecao_fin.keys()))
            
            if lanc_selecionado_str:
                lanc_sel = dic_selecao_fin[lanc_selecionado_str]
                id_lanc_f, tipo_lanc_f, valor_lanc_f, desc_lanc_f, date_lanc_f, _ = lanc_sel
                
                with st.form(f"form_editar_fin_{id_lanc_f}"):
                    novo_tipo_f = st.selectbox("Tipo:", ["Entrada (Receita)", "Saída (Despesa)"], index=0 if tipo_lanc_f == 'E' else 1)
                    novo_valor_f = st.number_input("Valor (R$):", value=float(valor_lanc_f), min_value=0.0)
                    nova_desc_f = st.text_area("Descrição:", value=desc_lanc_f)
                    
                    if st.form_submit_button("Salvar Alterações Financeiras", type="primary"):
                        try:
                            char_tipo_f = 'E' if novo_tipo_f == "Entrada (Receita)" else 'S'
                            executar_query("""
                                UPDATE FluxoCaixa 
                                SET Tipo = %s, Valor = %s, Descricao = %s 
                                WHERE IdLancamento = %s
                            """, (char_tipo_f, novo_valor_f, nova_desc_f, id_lanc_f))
                            st.success("Transação atualizada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                
                st.write("🗑️ **Excluir Registro**")
                confirmar_excluir_fin = st.checkbox(f"Confirmo que desejo apagar permanentemente o registro financeiro Nº {id_lanc_f}.", key=f"conf_del_fin_{id_lanc_f}")
                if st.button("Excluir Lançamento Financeiro", type="primary", disabled=not confirmar_excluir_fin, key=f"btn_del_fin_{id_lanc_f}"):
                    try:
                        executar_query("DELETE FROM FluxoCaixa WHERE IdLancamento = %s", (id_lanc_f,))
                        st.success("Lançamento excluído com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao deletar: {e}")
        else:
            st.info("Nenhum lançamento financeiro registrado neste período.")

    with aba_dividas:
        st.header("Controle de Dívidas & Contas a Pagar")
        st.markdown("Registre e gerencie as dívidas com parceiros e fornecedores para compra de peças e serviços.")
        
        try:
            # 1. Total Pendente
            sum_pendente = executar_query("""
                SELECT COALESCE(SUM(valor), 0) FROM dividas WHERE status = 'Pendente'
            """, fetch='one')[0]

            # 2. Vencidas/Overdue
            sum_vencido = executar_query("""
                SELECT COALESCE(SUM(valor), 0) FROM dividas WHERE status = 'Pendente' AND data_vencimento < CURRENT_DATE
            """, fetch='one')[0]

            # 3. Pago no mês atual
            agora_sp = obter_agora_sp()
            primeiro_dia_mes = datetime(agora_sp.year, agora_sp.month, 1).date()
            sum_pago_mes = executar_query("""
                SELECT COALESCE(SUM(valor), 0) FROM dividas 
                WHERE status = 'Pago' AND CAST(data_pagamento AS DATE) >= %s
            """, (primeiro_dia_mes,), fetch='one')[0]

            col_d1, col_d2, col_d3 = st.columns(3)
            sum_pendente_display = formatar_brl(sum_pendente) if not st.session_state.ocultar_valores else "R$ ••••••"
            sum_vencido_display = formatar_brl(sum_vencido) if not st.session_state.ocultar_valores else "R$ ••••••"
            sum_pago_mes_display = formatar_brl(sum_pago_mes) if not st.session_state.ocultar_valores else "R$ ••••••"
            
            with col_d1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Total Pendente</div>
                    <div class="metric-value val-danger">{sum_pendente_display}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_d2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Dívidas Vencidas</div>
                    <div class="metric-value val-warning">{sum_vencido_display}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_d3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">Pago neste Mês</div>
                    <div class="metric-value val-success">{sum_pago_mes_display}</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("---")
            sub_aba_consulta, sub_aba_cadastro = st.tabs(["🔍 Consultar Dívidas", "➕ Registrar Nova Dívida"])

            with sub_aba_cadastro:
                st.subheader("Registrar Nova Dívida")
                with st.form("form_nova_divida", clear_on_submit=True):
                    credor = st.text_input("Credor (Fornecedor / Parceiro / Nome):", placeholder="Ex: Distribuidora São Paulo, Parceiro João")
                    valor = st.number_input("Valor da Dívida (R$):", min_value=0.01, step=1.00)
                    
                    # O.S. Vinculada dropdown
                    os_list_db = executar_query("""
                        SELECT f.IdLancamento, c.Nome, p.Marca, p.Modelo
                        FROM FluxoCaixa f
                        JOIN Clientes c ON f.IdCliente = c.IdCliente
                        JOIN ItensEstoque i ON f.IdItem = i.IdItem
                        JOIN Produtos p ON i.IdProduto = p.IdProduto
                        WHERE f.Descricao LIKE '[ASSISTENCIA]%%'
                        ORDER BY f.IdLancamento DESC
                    """, fetch='all')
                    
                    os_options = {"Nenhuma OS Vinculada": None}
                    if os_list_db:
                        for row in os_list_db:
                            os_options[f"OS #{row[0]} - {row[1]} ({row[2]} {row[3]})"] = row[0]
                            
                    os_selecionada = st.selectbox("Vincular a uma Ordem de Serviço (Opcional):", list(os_options.keys()))
                    id_os_fk = os_options[os_selecionada]
                    
                    col_fd1, col_fd2 = st.columns(2)
                    with col_fd1:
                        data_d = st.date_input("Data da Dívida:", value=obter_agora_sp().date())
                    with col_fd2:
                        data_v = st.date_input("Data de Vencimento:", value=obter_agora_sp().date() + timedelta(days=7))
                        
                    descricao = st.text_input("Descrição da Peça / Serviço:", placeholder="Ex: Tela LCD Dell Inspiron, Teclado Mecânico Razer")
                    obs = st.text_area("Observações Adicionais:")
                    
                    if st.form_submit_button("Gravar Dívida"):
                        if credor and descricao:
                            try:
                                executar_query("""
                                    INSERT INTO dividas (credor, descricao, valor, data_divida, data_vencimento, id_os, observacoes, status)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendente')
                                """, (credor, descricao, valor, data_d, data_v, id_os_fk, obs))
                                st.success("Dívida registrada com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar dívida: {e}")
                        else:
                            st.warning("Credor e Descrição são campos obrigatórios.")

            with sub_aba_consulta:
                st.subheader("Filtros de Busca")
                col_fc1, col_fc2 = st.columns(2)
                with col_fc1:
                    filtro_status = st.selectbox("Status da Dívida:", ["Todas", "Pendente", "Pago"], key="filtro_divida_status")
                with col_fc2:
                    termo_busca_divida = st.text_input("Buscar por Credor ou Descrição:", key="busca_divida_termo")
                    
                query_dividas = """
                    SELECT d.iddivida, d.credor, d.descricao, d.valor, d.data_divida, d.data_vencimento, d.status, d.data_pagamento, d.id_os, d.observacoes
                    FROM dividas d
                    WHERE 1=1
                """
                params_dividas = []
                
                if filtro_status == "Pendente":
                    query_dividas += " AND d.status = 'Pendente'"
                elif filtro_status == "Pago":
                    query_dividas += " AND d.status = 'Pago'"
                    
                if termo_busca_divida:
                    query_dividas += " AND (d.credor ILIKE %s OR d.descricao ILIKE %s OR d.observacoes ILIKE %s)"
                    busca_val = f"%{termo_busca_divida}%"
                    params_dividas.extend([busca_val, busca_val, busca_val])
                    
                query_dividas += " ORDER BY d.iddivida DESC"
                
                dados_dividas = executar_query(query_dividas, params_dividas, fetch='all')
                
                if dados_dividas:
                    tabela_dividas = []
                    hoje_date = obter_agora_sp().date()
                    
                    for item in dados_dividas:
                        id_d, credor_d, desc_d, valor_d, date_div, date_venc, stat_d, date_pag, id_os_d, obs_d = item
                        
                        os_ref_str = f"OS #{id_os_d}" if id_os_d else "Sem vínculo"
                        venc_str = date_venc.strftime('%d/%m/%Y') if date_venc else "Sem prazo"
                        pag_str = converter_para_sp(date_pag).strftime('%d/%m/%Y %H:%M') if date_pag else "---"
                        
                        if stat_d == 'Pendente':
                            if date_venc and date_venc < hoje_date:
                                stat_display = "⚠️ Vencida"
                            else:
                                stat_display = "🔴 Pendente"
                        else:
                            stat_display = "🟢 Pago"
                            
                        tabela_dividas.append([
                            id_d,
                            credor_d,
                            desc_d,
                            valor_d,
                            stat_display,
                            date_div.strftime('%d/%m/%Y') if date_div else "---",
                            venc_str,
                            pag_str,
                            os_ref_str
                        ])
                        
                    df_div = pd.DataFrame(tabela_dividas, columns=[
                        "ID", "Credor", "Descrição", "Valor (R$)", "Status", "Data Início", "Vencimento", "Data Pagamento", "Vínculo O.S."
                    ])
                    if st.session_state.ocultar_valores:
                        df_div["Valor (R$)"] = "••••"
                    st.dataframe(df_div, use_container_width=True, hide_index=True)
                    
                    st.write("---")
                    st.subheader("Gerenciar / Quitar Dívida")
                    
                    lista_select_dividas = {}
                    for item in dados_dividas:
                        id_d, credor_d, desc_d, valor_d, _, _, stat_d, _, _, _ = item
                        status_ind = "Pendente" if stat_d == 'Pendente' else "Paga"
                        valor_display_sel = formatar_brl(valor_d) if not st.session_state.ocultar_valores else "••••"
                        lista_select_dividas[f"ID {id_d} - {credor_d} - {valor_display_sel} ({status_ind})"] = item
                        
                    divida_selecionada_str = st.selectbox("Selecione a Dívida para atualizar:", list(lista_select_dividas.keys()))
                    
                    if divida_selecionada_str:
                        d_sel = lista_select_dividas[divida_selecionada_str]
                        id_d, credor_d, desc_d, valor_d, date_div, date_venc, stat_d, date_pag, id_os_d, obs_d = d_sel
                        
                        col_ad1, col_ad2 = st.columns(2)
                        with col_ad1:
                            st.markdown(f"**Credor:** {credor_d}")
                            st.markdown(f"**Item/Descrição:** {desc_d}")
                            valor_display_det = formatar_brl(valor_d) if not st.session_state.ocultar_valores else "••••"
                            st.markdown(f"**Valor:** {valor_display_det}")
                            st.markdown(f"**Status Atual:** {stat_d}")
                            if obs_d:
                                st.markdown(f"**Anotações:** {obs_d}")
                        with col_ad2:
                            if stat_d == 'Pendente':
                                st.write("🔒 **Quitação de Dívida**")
                                quitar_caixa = st.checkbox("Lançar automaticamente saída no fluxo de caixa", value=True, key=f"quitar_caixa_check_{id_d}")
                                if st.button("Quitar Dívida (Marcar como Pago)", type="primary", key=f"btn_quitar_{id_d}"):
                                    try:
                                        agora_timestamp = obter_agora_sp()
                                        conn = abrir_conexao()
                                        cursor = conn.cursor()
                                        
                                        cursor.execute("""
                                            UPDATE dividas 
                                            SET status = 'Pago', data_pagamento = %s 
                                            WHERE iddivida = %s
                                        """, (agora_timestamp, id_d))
                                        
                                        if quitar_caixa:
                                            id_cliente_os = None
                                            id_item_os = None
                                            if id_os_d:
                                                cursor.execute("SELECT IdCliente, IdItem FROM FluxoCaixa WHERE IdLancamento = %s", (id_os_d,))
                                                row_os = cursor.fetchone()
                                                if row_os:
                                                    id_cliente_os = row_os[0]
                                                    id_item_os = row_os[1]
                                            
                                            desc_fluxo = f"[CUSTO PEÇA][DÍVIDA QUITADA] - Credor: {credor_d} - Item: {desc_d}"
                                            cursor.execute("""
                                                INSERT INTO FluxoCaixa (Tipo, Valor, Descricao, IdCliente, IdItem)
                                                VALUES ('S', %s, %s, %s, %s)
                                            """, (valor_d, desc_fluxo, id_cliente_os, id_item_os))
                                            
                                        conn.commit()
                                        conn.close()
                                        st.success(f"Dívida para {credor_d} quitada com sucesso!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao quitar dívida: {e}")
                            else:
                                st.success("Esta dívida já está quitada!")
                                st.markdown(f"**Pago em:** {converter_para_sp(date_pag).strftime('%d/%m/%Y %H:%M') if date_pag else '---'}")
                                
                        st.write("---")
                        st.write("🗑️ **Excluir Dívida**")
                        confirmar_excluir_divida = st.checkbox(f"Confirmo que desejo apagar permanentemente a dívida ID {id_d} (isso NÃO afeta o fluxo de caixa antigo caso já lançado).", key=f"conf_del_div_{id_d}")
                        if st.button("Apagar Registro de Dívida", type="primary", disabled=not confirmar_excluir_divida, key=f"btn_del_div_{id_d}"):
                            try:
                                executar_query("DELETE FROM dividas WHERE iddivida = %s", (id_d,))
                                st.success("Registro de dívida apagado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao apagar dívida: {e}")
                else:
                    st.info("Nenhuma dívida cadastrada ou correspondente aos filtros.")
        except Exception as e:
            st.error(f"Erro ao carregar aba de dívidas: {e}")

# =========================================================================
# 9. TELA: CONTAS & ACESSOS (CRUD DE USUÁRIOS - APENAS ADM)
# =========================================================================
elif opcao == "👥 Contas & Acessos":
    st.title("👥 Gerenciamento de Contas & Níveis de Acesso")
    st.markdown("Cadastre novos colaboradores e selecione suas permissões.")
    st.write("---")
    
    # Apenas admin pode ver
    if st.session_state.user_role != 'adm':
        st.error("Acesso negado.")
        st.stop()
        
    aba_lista_contas, aba_cadastrar_conta = st.tabs(["🔍 Contas Cadastradas", "➕ Cadastrar Nova Conta"])
    
    with aba_cadastrar_conta:
        st.header("Cadastrar Novo Usuário")
        with st.form("form_cadastrar_usuario", clear_on_submit=True):
            novo_usuario = st.text_input("Nome de Usuário (login):", placeholder="Ex: kaue.arruda")
            novo_nome_real = st.text_input("Nome Completo (exibido na tela):", placeholder="Ex: Kaue Arruda")
            nova_senha = st.text_input("Senha de Acesso:", type="password")
            
            # Aqui é a parte que mostra ADM e Lojista
            nivel_acesso = st.radio(
                "Nível de Acesso (Perfil):",
                ["Lojista (Acesso básico a vendas e cadastros)", "Administrador (Acesso completo a financeiro e estoque)"]
            )
            
            if st.form_submit_button("Criar Conta", type="primary", use_container_width=True):
                if novo_usuario and novo_nome_real and nova_senha:
                    # Remove espaços
                    novo_usuario_clean = novo_usuario.strip().lower()
                    role_final = "adm" if "Administrador" in nivel_acesso else "lojista"
                    
                    try:
                        executar_query("""
                            INSERT INTO Usuarios (Usuario, Senha, Nome, Role)
                            VALUES (%s, %s, %s, %s)
                        """, (novo_usuario_clean, nova_senha, novo_nome_real, role_final))
                        st.success(f"Conta '{novo_nome_real}' cadastrada com sucesso como {role_final.upper()}!")
                        st.rerun()
                    except psycopg2.IntegrityError:
                        st.error("Erro: Este nome de usuário já está sendo utilizado.")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.warning("Preencha todos os campos obrigatórios (Usuário, Nome Completo e Senha).")
                    
    with aba_lista_contas:
        st.header("Usuários com Acesso ao Sistema")
        try:
            usuarios_db = executar_query("""
                SELECT IdUsuario, Usuario, Nome, Role 
                FROM Usuarios 
                ORDER BY Nome ASC
            """, fetch='all')
            
            if usuarios_db:
                dados_tabela_usuarios = []
                for u in usuarios_db:
                    role_display = "👑 Administrador (adm)" if u[3] == 'adm' else "💼 Lojista"
                    dados_tabela_usuarios.append([u[0], u[1], u[2], role_display])
                    
                df_usr = pd.DataFrame(dados_tabela_usuarios, columns=["ID", "Nome de Usuário", "Nome Exibido", "Perfil de Acesso"])
                st.dataframe(df_usr, use_container_width=True, hide_index=True)
                
                # Opção para excluir usuário
                st.write("---")
                st.subheader("Excluir Conta de Usuário")
                
                lista_exclusao = {f"{u[2]} (Usuário: {u[1]})": u for u in usuarios_db}
                usuario_excluir_str = st.selectbox("Selecione a conta para remover:", list(lista_exclusao.keys()))
                
                if usuario_excluir_str:
                    usr_sel = lista_exclusao[usuario_excluir_str]
                    id_usr, user_usr, nome_usr, role_usr = usr_sel
                    
                    # Impede que o usuário logado exclua a si mesmo
                    if user_usr == st.session_state.user_name.lower() or user_usr == "kaue":
                        st.warning("Você não pode excluir a sua própria conta ativa ou a conta administradora principal.")
                    else:
                        confirmar_usr_del = st.checkbox(f"Confirmo que desejo revogar o acesso de '{nome_usr}'.")
                        if st.button("Excluir Usuário", type="primary", disabled=not confirmar_usr_del, key="btn_excluir_usuario_remover"):
                            try:
                                executar_query("DELETE FROM Usuarios WHERE IdUsuario = %s", (id_usr,))
                                st.success(f"Acesso de '{nome_usr}' revogado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir usuário: {e}")
            else:
                st.warning("Nenhum usuário cadastrado.")
        except Exception as e:
            st.error(f"Erro ao buscar usuários: {e}")