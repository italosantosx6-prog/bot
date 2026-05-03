# Telegram PIX Bot completo

Bot Telegram pronto para rodar como um único processo com:
- `bot.py` → entrada principal
- `config.py` → variáveis de ambiente
- `services/` → Mercado Pago + Supabase
- `requirements.txt`
- `supabase_schema.sql` → criar tabelas necessárias

---

## 📁 Estrutura principal

```
/morfel_bot/
├── bot.py
├── config.py
├── requirements.txt
├── .env.example
├── supabase_schema.sql
├── services/
│   ├── mercadopago_service.py
│   └── supabase_service.py
└── README.md
```

> Atenção: existem arquivos legados de versões antigas do bot (`bot_client.py`, `bot_admin.py`, `app_setup.py`). O sistema atual usa apenas `bot.py`.

---

## 🚀 Como rodar

1. Copie `.env.example` para `.env`:

```bash
cp .env.example .env
```

2. Preencha as variáveis no `.env`.

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Execute o bot:

```bash
python bot.py
```

O bot inicia o polling do Telegram e o webhook Flask no mesmo processo.

---

## ✅ O que está funcionando

- Recebe `/pix`
- O usuário envia um valor
- Gera PIX Mercado Pago automaticamente
- Envia QR Code, cópia e cola e valor
- Webhook automático valida pagamento `approved`
- Atualiza saldo no Supabase
- Envia mensagem automática no Telegram
- Evita pagamentos duplicados pendentes

---

## 🧩 Configuração do Mercado Pago

No `.env` preencha:

```env
MP_PUBLIC_KEY=APP_USR-b4203d16-50cc-485b-9aa9-5bb8a5e32400
MP_ACCESS_TOKEN=APP_USR-3443876455718163-092317-a6de2754ab3bf881dddbada2a543db10-318028023
```

No Mercado Pago, configure o webhook para:

```
http://<SEU_DOMINIO>:<WEBHOOK_PORT><WEBHOOK_PATH>
```

Se usar `WEBHOOK_SECRET`, defina o mesmo segredo no painel de webhooks do Mercado Pago.

---

## 🚀 Deploy

### VPS / servidor dedicado

1. Preencha `.env`
2. Instale dependências
3. Rode `python bot.py`
4. Garanta que a porta `WEBHOOK_PORT` esteja aberta

### Vercel

Vercel não é ideal para este bot, porque o processo precisa ficar sempre ativo para polling do Telegram. Prefira VPS ou um serviço com processo persistente.

---

## 🔎 Health check

O serviço expõe:

```
http://<SEU_DOMINIO>:<WEBHOOK_PORT>/health
```

Use essa rota para verificar se o processo está ativo.

---

## 📌 Observações

- O bot atual é um único processo (`bot.py`)
- Você não precisa rodar `bot_client.py` ou `bot_admin.py`
- O webhook Flask roda dentro do mesmo processo do bot Telegram

---

## 🚀 Deploy e webhook

### Rodando localmente ou em VPS

1. Copie o `.env.example` para `.env` e preencha todas as variáveis.
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Execute o bot:

```bash
python bot.py
```

O Flask webhook e o polling do Telegram rodam juntos no mesmo processo.

### Configurando o webhook do Mercado Pago

- Use `WEBHOOK_HOST`, `WEBHOOK_PORT` e `WEBHOOK_PATH` do `.env`.
- No Mercado Pago, configure o endpoint para:

```
http://<SEU_DOMINIO>:<WEBHOOK_PORT><WEBHOOK_PATH>
```

- Se quiser mais segurança, defina `WEBHOOK_SECRET` em `.env` e configure o mesmo segredo no Mercado Pago.

### Preparando para Vercel

O Vercel não é ideal para `infinity_polling` de bots Telegram porque o processo pode não ficar sempre ativo.

Para produção em nuvem, prefira VPS ou um serviço com processo persistente (como Docker em DigitalOcean, AWS EC2, Railway, Render etc.).

### Checagem de saúde

A URL de saúde está disponível em:

```
http://<SEU_DOMINIO>:<WEBHOOK_PORT>/health
```

Use essa URL para verificar se o serviço está ativo.
