E2E Test & Deployment notes

1) Pré-requisitos
- Defina no `.env`: `SUPABASE_URL`, `SUPABASE_KEY` (service role), `BOT_TOKEN`, `MP_ACCESS_TOKEN`/`STRIPE_SECRET_KEY` se usar.
- Aplique `supabase_schema_updated.sql` no projeto Supabase (SQL Editor) usando Service Role.

2) Rodar bot + webhooks localmente
- Use duas sessões ou `honcho`/`foreman` com `Procfile`:

```bash
# ativa venv
source .venv/bin/activate
# usando foreman (instale foreman/honcho se quiser)
foreman start
# ou rodar processos separadamente
python webhooks.py &
python bot.py
```

3) Rodar teste E2E (executa operações direto no Supabase)

```bash
source .venv/bin/activate
python tests/e2e_payment.py
```

4) Notas de segurança
- Nunca exponha `SUPABASE_KEY` (service role) em frontend. Mantenha no backend.
- Se usar webhooks, configure URL pública segura e segredos `MP_WEBHOOK_SECRET`/`STRIPE_WEBHOOK_SECRET`.

5) Rollback
- `supabase_schema_rollback.sql` contém comandos para desabilitar políticas e remover índices; revise antes de executar.
