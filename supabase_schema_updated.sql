-- ============================================================
--  MORFEL / INFINITY STORE — Schema Supabase Atualizado
--  Inclui índices recomendados e políticas RLS básicas para
--  restringir acessos a clientes; backend (service_role) tem acesso.
--  Execute no SQL Editor do projeto Supabase (Service Role Key necessário).
-- ============================================================

-- ── Usuários (cadastro automático pelo bot: /start, menu, /pix, etc.) ──
CREATE TABLE IF NOT EXISTS users (
    id           BIGSERIAL PRIMARY KEY,
    telegram_id  BIGINT UNIQUE NOT NULL,
    username     TEXT DEFAULT '',
    saldo        NUMERIC(12,2) DEFAULT 0,
    comissao     NUMERIC(12,2) DEFAULT 0,
    referido_por BIGINT,
    banido       BOOLEAN DEFAULT FALSE,
    banido_por   BIGINT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_telegram ON users (telegram_id);

-- ── Staff (painel /adm) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS staff (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username    TEXT DEFAULT '',
    cargo       INT NOT NULL,
    dado_por    BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── GGGs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gggs (
    id           BIGSERIAL PRIMARY KEY,
    numero       TEXT NOT NULL,
    validade     TEXT NOT NULL,
    cvv          TEXT DEFAULT '',
    banco        TEXT DEFAULT '',
    bandeira     TEXT DEFAULT '',
    bin          TEXT DEFAULT '',
    preco        NUMERIC(10,2) DEFAULT 8,
    vendido      BOOLEAN DEFAULT FALSE,
    comprador_id BIGINT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gggs_banco    ON gggs (LOWER(banco));
CREATE INDEX IF NOT EXISTS idx_gggs_bin      ON gggs (bin);
CREATE INDEX IF NOT EXISTS idx_gggs_bandeira ON gggs (LOWER(bandeira));
CREATE INDEX IF NOT EXISTS idx_gggs_vendido  ON gggs (vendido);

-- ── CCs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ccs (
    id           BIGSERIAL PRIMARY KEY,
    numero       TEXT NOT NULL,
    validade     TEXT NOT NULL,
    cvv          TEXT DEFAULT '',
    banco        TEXT DEFAULT '',
    bandeira     TEXT DEFAULT '',
    bin          TEXT DEFAULT '',
    preco        NUMERIC(10,2) DEFAULT 10,
    vendido      BOOLEAN DEFAULT FALSE,
    comprador_id BIGINT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ccs_banco    ON ccs (LOWER(banco));
CREATE INDEX IF NOT EXISTS idx_ccs_bin      ON ccs (bin);
CREATE INDEX IF NOT EXISTS idx_ccs_bandeira ON ccs (LOWER(bandeira));
CREATE INDEX IF NOT EXISTS idx_ccs_vendido  ON ccs (vendido);

-- ── Logins ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS logins (
    id           BIGSERIAL PRIMARY KEY,
    tipo         TEXT NOT NULL,
    credencial   TEXT NOT NULL,
    preco        NUMERIC(10,2) DEFAULT 10,
    vendido      BOOLEAN DEFAULT FALSE,
    comprador_id BIGINT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Histórico de compras ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS historico (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    tipo        TEXT NOT NULL,
    item_id     BIGINT,
    valor       NUMERIC(10,2),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_historico_user ON historico (telegram_id);

-- ── Pagamentos PIX (fluxo atual: pending → approved no painel admin) ──
CREATE TABLE IF NOT EXISTS pagamentos (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    payment_id  TEXT UNIQUE NOT NULL,
    valor       NUMERIC(12,2),
    status      TEXT DEFAULT 'pending',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pagamentos_payment_id ON pagamentos (payment_id);
CREATE INDEX IF NOT EXISTS idx_pagamentos_status    ON pagamentos (status);
CREATE INDEX IF NOT EXISTS idx_pagamentos_telegram ON pagamentos (telegram_id);

-- ── Pagamentos PIX (novo sistema com dados extra) ────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id                 BIGSERIAL PRIMARY KEY,
    telegram_id        BIGINT NOT NULL,
    external_reference TEXT UNIQUE,
    payment_id         TEXT UNIQUE NOT NULL,
    amount             NUMERIC(12,2) NOT NULL,
    status             TEXT DEFAULT 'pending',
    qr_code            TEXT,
    pix_copy_text      TEXT,
    approved_at        TIMESTAMPTZ,
    raw_response       JSONB,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payments_payment_id ON payments (payment_id);
CREATE INDEX IF NOT EXISTS idx_payments_external_reference ON payments (external_reference);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);
CREATE INDEX IF NOT EXISTS idx_payments_telegram ON payments (telegram_id);

-- ── Gift codes ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gift_codes (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,
    valor       NUMERIC(10,2) NOT NULL,
    telegram_id BIGINT DEFAULT 0,
    used        BOOLEAN DEFAULT FALSE,
    used_by     BIGINT,
    criado_por  BIGINT,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gift_codes_code ON gift_codes (code);
CREATE INDEX IF NOT EXISTS idx_gift_codes_used ON gift_codes (used);

-- ============================================================
--  POLÍTICAS RLS (Row Level Security) — aumenta segurança
--  Observação: o backend (bot) deve usar a Service Role Key.
--  Estas políticas permitem apenas o acesso total quando o JWT
--  indica role = 'service_role' (requests do servidor). Para outros
--  roles, o acesso é negado por padrão. Ajuste conforme necessário.
-- ============================================================

-- Habilita RLS e cria policy que permite acesso completo somente para service_role
DO $$
BEGIN
    -- Lista de tabelas para habilitar RLS
    PERFORM 1;
END$$;

-- Usuários
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY users_service_role_all ON users FOR ALL USING (auth.role() = 'service_role');

-- Pagamentos (antigo)
ALTER TABLE pagamentos ENABLE ROW LEVEL SECURITY;
CREATE POLICY pagamentos_service_role_all ON pagamentos FOR ALL USING (auth.role() = 'service_role');

-- Novo payments
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
CREATE POLICY payments_service_role_all ON payments FOR ALL USING (auth.role() = 'service_role');

-- GGGs
ALTER TABLE gggs ENABLE ROW LEVEL SECURITY;
CREATE POLICY gggs_service_role_all ON gggs FOR ALL USING (auth.role() = 'service_role');

-- CCs
ALTER TABLE ccs ENABLE ROW LEVEL SECURITY;
CREATE POLICY ccs_service_role_all ON ccs FOR ALL USING (auth.role() = 'service_role');

-- Logins
ALTER TABLE logins ENABLE ROW LEVEL SECURITY;
CREATE POLICY logins_service_role_all ON logins FOR ALL USING (auth.role() = 'service_role');

-- Historico
ALTER TABLE historico ENABLE ROW LEVEL SECURITY;
CREATE POLICY historico_service_role_all ON historico FOR ALL USING (auth.role() = 'service_role');

-- Gift codes
ALTER TABLE gift_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY gift_codes_service_role_all ON gift_codes FOR ALL USING (auth.role() = 'service_role');

-- Staff
ALTER TABLE staff ENABLE ROW LEVEL SECURITY;
CREATE POLICY staff_service_role_all ON staff FOR ALL USING (auth.role() = 'service_role');

-- ============================================================
--  MIGRAÇÕES E OTIMIZAÇÕES RÁPIDAS (execute se necessário)
-- ============================================================
-- CREATE INDEX IF NOT EXISTS idx_users_telegram ON users (telegram_id);
-- CREATE INDEX IF NOT EXISTS idx_pagamentos_telegram ON pagamentos (telegram_id);
-- ALTER TABLE users ALTER COLUMN saldo TYPE NUMERIC(12,2);
-- ALTER TABLE users ALTER COLUMN comissao TYPE NUMERIC(12,2);
-- ALTER TABLE pagamentos ALTER COLUMN valor TYPE NUMERIC(12,2);

-- ============================================================
--  INSTRUÇÕES
--  1) No Supabase SQL Editor cole e execute este arquivo como Service Role.
--  2) Se usar RLS com JWT de usuários clients, adapte policies para permitir
--     SELECT/INSERT apenas nas colunas e condições necessárias.
--  3) Não exponha sua Service Role Key no cliente (frontend).
-- ============================================================
