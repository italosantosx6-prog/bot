-- ============================================================
--  MORFEL / INFINITY STORE — Schema Supabase (sincronizado com database/db.py)
--
--  IDENTIFICAÇÃO DE USUÁRIOS
--  • Cada pessoa do Telegram é única pelo campo telegram_id (BIGINT).
--  • Todas as tabelas que ligam ação ao cliente usam telegram_id.
--  • PIX pendente/aprovado: tabela pagamentos.telegram_id → mesmo usuário em users.
--
--  Execute no SQL Editor do projeto Supabase (ou migrações).
--  Service Role Key no bot só para backend — não exponha no cliente.
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
-- cargo: 1=Revendedor | 2=Moderador | 3=Admin (OWNER_ID no config = dono fora da tabela)
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

-- ── CCs ────────────────────────────────────────────────────────────
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

-- ── Pagamentos PIX (novo sistema) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    id                 BIGSERIAL PRIMARY KEY,
    telegram_id        BIGINT NOT NULL,
    external_reference TEXT UNIQUE NOT NULL,
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
--  Migrações leves para projeto JÁ criado (rode se faltar índice)
-- ============================================================
-- CREATE INDEX IF NOT EXISTS idx_users_telegram ON users (telegram_id);
-- CREATE INDEX IF NOT EXISTS idx_pagamentos_telegram ON pagamentos (telegram_id);
-- ALTER TABLE users ALTER COLUMN saldo TYPE NUMERIC(12,2);
-- ALTER TABLE users ALTER COLUMN comissao TYPE NUMERIC(12,2);
-- ALTER TABLE pagamentos ALTER COLUMN valor TYPE NUMERIC(12,2);
