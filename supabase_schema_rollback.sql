-- Rollback for supabase_schema_updated.sql
-- Reverte índices, policies e tabelas criadas (USE COM CAUTELA)

-- Disable RLS policies
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_service_role_all ON users;

ALTER TABLE pagamentos DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS pagamentos_service_role_all ON pagamentos;

ALTER TABLE payments DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payments_service_role_all ON payments;

ALTER TABLE gggs DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gggs_service_role_all ON gggs;

ALTER TABLE ccs DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ccs_service_role_all ON ccs;

ALTER TABLE logins DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS logins_service_role_all ON logins;

ALTER TABLE historico DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS historico_service_role_all ON historico;

ALTER TABLE gift_codes DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gift_codes_service_role_all ON gift_codes;

ALTER TABLE staff DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff_service_role_all ON staff;

-- Optionally drop added tables (uncomment if you really want to drop)
-- DROP TABLE IF EXISTS payments;
-- DROP TABLE IF EXISTS gift_codes;
-- DROP TABLE IF EXISTS pagamentos;
-- DROP TABLE IF EXISTS historico;
-- DROP TABLE IF EXISTS logins;
-- DROP TABLE IF EXISTS ccs;
-- DROP TABLE IF EXISTS gggs;
-- DROP TABLE IF EXISTS staff;
-- DROP TABLE IF EXISTS users;

-- Remove indexes (if left)
DROP INDEX IF EXISTS idx_payments_payment_id;
DROP INDEX IF EXISTS idx_payments_external_reference;
DROP INDEX IF EXISTS idx_payments_status;
DROP INDEX IF EXISTS idx_payments_telegram;
DROP INDEX IF EXISTS idx_pagamentos_payment_id;
DROP INDEX IF EXISTS idx_pagamentos_status;
DROP INDEX IF EXISTS idx_pagamentos_telegram;
DROP INDEX IF EXISTS idx_users_telegram;

-- NOTE: Execute as Service Role if needed.
