-- =========================================================================
-- ESQUEMA DO BANCO DE DADOS - SPEEDY CELL ERP (SUPABASE / POSTGRESQL)
-- =========================================================================

-- 1. TABELA DE USUÁRIOS
CREATE TABLE IF NOT EXISTS Usuarios (
    IdUsuario SERIAL PRIMARY KEY,
    Usuario VARCHAR(100) UNIQUE NOT NULL,
    Senha VARCHAR(255) NOT NULL,
    Nome VARCHAR(255) NOT NULL,
    Role VARCHAR(50) NOT NULL
);

-- 2. TABELA DE CLIENTES
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

-- 3. TABELA DE PRODUTOS
CREATE TABLE IF NOT EXISTS Produtos (
    IdProduto SERIAL PRIMARY KEY,
    Marca VARCHAR(100) NOT NULL,
    Modelo VARCHAR(100) NOT NULL,
    CustoProduto NUMERIC(10,2) DEFAULT 0,
    ValorMinimo NUMERIC(10,2) DEFAULT 0,
    ValorVenda NUMERIC(10,2) DEFAULT 0,
    Ativo BOOLEAN DEFAULT true
);

-- 4. TABELA DE ITENS DO ESTOQUE
CREATE TABLE IF NOT EXISTS ItensEstoque (
    IdItem SERIAL PRIMARY KEY,
    IdProduto INT NOT NULL,
    NumeroSerie VARCHAR(100),
    Status VARCHAR(50) DEFAULT 'Disponivel',
    FOREIGN KEY(IdProduto) REFERENCES Produtos(IdProduto)
);

-- 5. TABELA DE FLUXO DE CAIXA / VENDAS E ORDENS DE SERVIÇO
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

-- 6. TABELA DE DÍVIDAS / CONTAS A PAGAR
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

-- ÍNDICES PARA ALTA PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_clientes_whatsapp ON Clientes(WhatsApp);
CREATE INDEX IF NOT EXISTS idx_clientes_documento ON Clientes(Documento);
CREATE INDEX IF NOT EXISTS idx_fluxocaixa_tipo ON FluxoCaixa(Tipo);
CREATE INDEX IF NOT EXISTS idx_fluxocaixa_idcliente ON FluxoCaixa(IdCliente);
CREATE INDEX IF NOT EXISTS idx_itensestoque_status ON ItensEstoque(Status);
